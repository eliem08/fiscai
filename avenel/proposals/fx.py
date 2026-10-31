"""Foreign exchange (FX) conversion and penny balancing for Moroccan bookkeeping.

Handles Bank Al-Maghrib (BAM) daily fixing rate resolution from the database `fx_rates` table
and guarantees that converted lines strictly balance in MAD: sum(debit_mad) == sum(credit_mad).
Any residual cents are posted to an explicit rounding line, never to the counterparty account.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import psycopg

from avenel.proposals.tax_mapping import resolve_rounding_account


def resolve_fx_rate(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    currency: str,
    tx_date: datetime.date | str | None,
) -> tuple[float | None, datetime.date | None, str | None]:
    """Resolves FX rate from tenant's fx_rates table for foreign currency and transaction date.

    Returns: (rate, rate_date, source_name).
    For MAD: returns (1.0, None, None) to strictly satisfy DB constraint:
    `currency = 'MAD' OR (fx_rate_date IS NOT NULL AND fx_source IS NOT NULL)`
    `currency <> 'MAD' OR fx_rate = 1`

    If missing for foreign currency: returns (None, rate_date, None) -> caller raises FX_RATE_MISSING.
    """
    currency_norm = currency.upper().strip()
    if currency_norm == "MAD":
        return 1.0, None, None

    date_obj: datetime.date
    if isinstance(tx_date, str):
        try:
            date_obj = datetime.date.fromisoformat(tx_date)
        except ValueError:
            date_obj = datetime.date.today()
    elif isinstance(tx_date, datetime.date):
        date_obj = tx_date
    else:
        date_obj = datetime.date.today()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rate, source
            FROM fx_rates
            WHERE tenant_id = %s
              AND currency = %s
              AND rate_date = %s
            LIMIT 1;
            """,
            (tenant_id, currency_norm, date_obj),
        )
        row = cur.fetchone()
        if row:
            return float(row[0]), date_obj, str(row[1])

    return None, date_obj, None


def record_fx_rate(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    rate_date: datetime.date,
    currency: str,
    rate: float,
    source: str = "bam_fixing",
    created_by: uuid.UUID | None = None,
) -> uuid.UUID:
    """Records an entered or imported FX fixing rate in fx_rates table."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fx_rates (tenant_id, rate_date, currency, rate, source, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, rate_date, currency)
            DO UPDATE SET rate = EXCLUDED.rate, source = EXCLUDED.source
            RETURNING id;
            """,
            (tenant_id, rate_date, currency.upper().strip(), rate, source, created_by),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError("Failed to insert or update FX rate")
        return uuid.UUID(str(row[0]))


def convert_and_balance_lines(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    lines: list[dict[str, Any]],
    currency: str,
    fx_rate: float,
    fx_rate_date: datetime.date | None,
    fx_source: str | None,
    default_evidence_ref: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Converts line debit_tx and credit_tx into debit_mad and credit_mad.

    Counterparty lines strictly equal invoice TTC converted at the stated rate.
    Any residual cents are posted to an explicit rounding line (direction 'rounding'
    from client_tax_mappings or pack default marked needs_expert).
    """
    if not lines:
        return []

    rate_dec = Decimal(str(fx_rate))
    processed: list[dict[str, Any]] = []

    total_debit_mad = Decimal("0.00")
    total_credit_mad = Decimal("0.00")

    for line in lines:
        d_tx = Decimal(str(line.get("debit_tx", 0.0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        c_tx = Decimal(str(line.get("credit_tx", 0.0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if currency == "MAD":
            d_mad = d_tx
            c_mad = c_tx
        else:
            d_mad = (d_tx * rate_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if d_tx > 0 else Decimal("0.00")
            c_mad = (c_tx * rate_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if c_tx > 0 else Decimal("0.00")

        total_debit_mad += d_mad
        total_credit_mad += c_mad

        item = dict(line)
        item["currency"] = currency
        item["debit_tx"] = float(d_tx)
        item["credit_tx"] = float(c_tx)
        item["fx_rate"] = fx_rate
        item["fx_rate_date"] = fx_rate_date.isoformat() if fx_rate_date else None
        item["fx_source"] = fx_source
        item["debit_mad"] = float(d_mad)
        item["credit_mad"] = float(c_mad)
        processed.append(item)

    # Residual cents check: post to an explicit rounding line, NEVER to counterparty
    diff = total_debit_mad - total_credit_mad
    if diff != Decimal("0.00"):
        diff_float = abs(float(diff))
        # diff < 0 means debits are short -> needs debit to balance -> loss
        # diff > 0 means debits exceed credits -> needs credit to balance -> gain
        direction = "rounding_loss" if diff < Decimal("0.00") else "rounding_gain"
        round_acc_id, round_acc_code, round_acc_label = resolve_rounding_account(
            conn, tenant_id, client_entity_id, direction=direction
        )

        evidence = [default_evidence_ref] if default_evidence_ref else []

        rounding_line: dict[str, Any] = {
            "line_no": len(processed) + 1,
            "account_id": round_acc_id,
            "account_code": round_acc_code,
            "counterparty_id": None,
            "label": f"Écart d'arrondi / conversion devises ({round_acc_label})",
            "currency": "MAD",
            "debit_tx": diff_float if diff < Decimal("0.00") else 0.0,
            "credit_tx": diff_float if diff > Decimal("0.00") else 0.0,
            "fx_rate": 1.0,
            "fx_rate_date": None,
            "fx_source": None,
            "debit_mad": diff_float if diff < Decimal("0.00") else 0.0,
            "credit_mad": diff_float if diff > Decimal("0.00") else 0.0,
            "tax_code": None,
            "due_date": None,
            "evidence_refs": evidence,
        }
        processed.append(rounding_line)

    return processed
