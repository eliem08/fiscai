"""Service layer for Moroccan bank accounts and bank statement ingestion.

Implements:
- Bank account registration with Moroccan RIB validation, hashing and encryption.
- Statement ingestion (CSV, XLSX, PDF) with mathematical balance verification.
- Emission of BANK_BALANCE_BREAK blocking issue on balance discrepancy.
- Idempotent insertion of bank transactions.
"""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any

import psycopg

from avenel.bank.parser import parse_bank_statement
from avenel.bank.rib import (
    clean_rib,
    compute_rib_sha256,
    encrypt_rib,
    extract_bank_code,
    extract_rib_last4,
    mask_rib,
    validate_moroccan_rib,
)


def _record_audit_event(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
    data: dict[str, Any],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_events (
                tenant_id, actor_type, actor_id, action, resource_type, resource_id, data
            )
            VALUES (%s, 'user', %s, %s, %s, %s, %s::jsonb);
            """,
            (tenant_id, actor_id, action, resource_type, str(resource_id), json.dumps(data)),
        )


def _get_or_create_bank_chart_account(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    bank_code: str,
    rib_last4: str,
) -> uuid.UUID:
    """Finds or creates a CGNC 5141 bank account for the client entity."""
    account_code = f"5141{bank_code}"
    label = f"Banque {bank_code} (..{rib_last4})"
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM chart_accounts
            WHERE tenant_id = %s AND client_entity_id = %s AND account_code = %s
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, account_code),
        )
        row = cur.fetchone()
        if row:
            return uuid.UUID(str(row[0]))

        acc_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (acc_id, tenant_id, client_entity_id, account_code, label),
        )
        return acc_id


def create_bank_account(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    rib: str,
    currency: str = "MAD",
    journal_code: str = "BQ",
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Registers a new bank account with Moroccan RIB validation."""
    cleaned = clean_rib(rib)
    if not validate_moroccan_rib(cleaned):
        raise ValueError("RIB marocain invalide : le format ou la clé de contrôle mod-97 est incorrect.")

    bank_code = extract_bank_code(cleaned)
    last4 = extract_rib_last4(cleaned)
    sha256_hash = compute_rib_sha256(cleaned)
    encrypted = encrypt_rib(cleaned)

    ledger_acc_id = _get_or_create_bank_chart_account(conn, tenant_id, client_entity_id, bank_code, last4)
    account_id = uuid.uuid4()

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bank_accounts (
                id, tenant_id, client_entity_id, bank_code, rib_last4,
                rib_encrypted, rib_sha256, currency, ledger_account_id, journal_code
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, bank_code, rib_last4, currency, journal_code;
            """,
            (
                account_id,
                tenant_id,
                client_entity_id,
                bank_code,
                last4,
                encrypted,
                sha256_hash,
                currency,
                ledger_acc_id,
                journal_code,
            ),
        )
        cur.fetchone()

    _record_audit_event(
        conn=conn,
        tenant_id=tenant_id,
        actor_id=actor_id or "system",
        action="bank_account.created",
        resource_type="bank_accounts",
        resource_id=account_id,
        data={"bank_code": bank_code, "rib_masked": mask_rib(cleaned)},
    )

    return {
        "id": account_id,
        "tenant_id": tenant_id,
        "client_entity_id": client_entity_id,
        "bank_code": bank_code,
        "rib_masked": mask_rib(cleaned),
        "rib_last4": last4,
        "currency": currency,
        "journal_code": journal_code,
        "ledger_account_id": ledger_acc_id,
    }


def list_bank_accounts(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Lists registered bank accounts for a client entity."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, bank_code, rib_last4, currency, journal_code, ledger_account_id
            FROM bank_accounts
            WHERE tenant_id = %s AND client_entity_id = %s
            ORDER BY bank_code, rib_last4;
            """,
            (tenant_id, client_entity_id),
        )
        rows = cur.fetchall()

    return [
        {
            "id": uuid.UUID(str(r[0])),
            "bank_code": r[1],
            "rib_last4": r[2],
            "currency": r[3],
            "journal_code": r[4],
            "ledger_account_id": uuid.UUID(str(r[5])),
        }
        for r in rows
    ]


def ingest_bank_statement(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    bank_account_id: uuid.UUID,
    document_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    work_request_id: uuid.UUID | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Parses and stores bank statement and transactions, enforcing balance check."""
    parsed = parse_bank_statement(file_bytes, filename)

    period_start = parsed.period_start or datetime.date.today().replace(day=1)
    period_end = parsed.period_end or datetime.date.today()

    statement_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bank_statements (
                id, tenant_id, client_entity_id, bank_account_id, document_id,
                period_start, period_end, opening_balance, closing_balance, balance_check
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                statement_id,
                tenant_id,
                client_entity_id,
                bank_account_id,
                document_id,
                period_start,
                period_end,
                parsed.opening_balance,
                parsed.closing_balance,
                parsed.balance_check,
            ),
        )

    # If balance break detected, raise blocking issue BANK_BALANCE_BREAK
    created_issue_id = None
    if parsed.has_balance_break and work_request_id is not None:
        created_issue_id = uuid.uuid4()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO issues (
                    id, tenant_id, client_entity_id, work_request_id, code, severity, status,
                    evidence_refs, subject_document_id
                )
                VALUES (%s, %s, %s, %s, 'BANK_BALANCE_BREAK', 'blocking', 'open', %s, %s);
                """,
                (
                    created_issue_id,
                    tenant_id,
                    client_entity_id,
                    work_request_id,
                    json.dumps([{
                        "statement_id": str(statement_id),
                        "opening_balance": parsed.opening_balance,
                        "closing_balance": parsed.closing_balance,
                        "computed_closing": parsed.computed_closing_balance,
                        "difference": parsed.balance_difference,
                    }]),
                    document_id,
                ),
            )

    # Insert transactions
    inserted_tx_ids: list[uuid.UUID] = []
    with conn.cursor() as cur:
        for tx in parsed.transactions:
            tx_id = uuid.uuid4()
            evidence = json.dumps([{"document_id": str(document_id), "line_index": tx.line_index}])
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    id, tenant_id, client_entity_id, bank_account_id, bank_statement_id,
                    line_index, booking_date, value_date, amount, currency, description,
                    external_reference, source_hash, evidence_ref
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, bank_account_id, source_hash) DO NOTHING
                RETURNING id;
                """,
                (
                    tx_id,
                    tenant_id,
                    client_entity_id,
                    bank_account_id,
                    statement_id,
                    tx.line_index,
                    tx.booking_date,
                    tx.value_date,
                    tx.amount,
                    tx.currency,
                    tx.clean_label,
                    tx.external_reference,
                    tx.source_hash,
                    evidence,
                ),
            )
            r = cur.fetchone()
            if r:
                inserted_tx_ids.append(uuid.UUID(str(r[0])))

    # Generate initial suspense proposal for every bank line ingested in this work request
    if work_request_id:
        from avenel.proposals.bank_proposals import (
            create_initial_suspense_proposal_for_bank_tx,
        )

        for bt_id in inserted_tx_ids:
            create_initial_suspense_proposal_for_bank_tx(
                conn=conn,
                tenant_id=tenant_id,
                client_entity_id=client_entity_id,
                work_request_id=work_request_id,
                bank_transaction_id=bt_id,
            )

    _record_audit_event(
        conn=conn,
        tenant_id=tenant_id,
        actor_id=actor_id or "system",
        action="bank_statement.ingested",
        resource_type="bank_statements",
        resource_id=statement_id,
        data={
            "transaction_count": len(inserted_tx_ids),
            "balance_check": parsed.balance_check,
            "opening_balance": parsed.opening_balance,
            "closing_balance": parsed.closing_balance,
            "computed_closing": parsed.computed_closing_balance,
        },
    )

    return {
        "statement_id": statement_id,
        "balance_check": parsed.balance_check,
        "opening_balance": parsed.opening_balance,
        "closing_balance": parsed.closing_balance,
        "computed_closing": parsed.computed_closing_balance,
        "difference": parsed.balance_difference,
        "transaction_count": len(inserted_tx_ids),
        "issue_id": created_issue_id,
    }
