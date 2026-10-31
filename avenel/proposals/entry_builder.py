"""Rule-based journal entry builder for Moroccan bookkeeping proposals (Phase 3).

Generates balanced journal entries for:
- Purchases (ACH journal)
- Sales (VEN journal)
- Credit Notes (Purchases and Sales Avoirs)
- Fixed Assets (Immobilisations)
Enforces:
1. Every proposal strictly balances: sum(debit_mad) == sum(credit_mad).
2. Every line has traceable evidence refs linked to document fields and bounding boxes.
3. Database line constraints strictly satisfied.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg

from avenel.proposals.account_suggester import (
    _get_or_create_chart_account,
    suggest_accounts,
)
from avenel.proposals.fx import convert_and_balance_lines, resolve_fx_rate
from avenel.proposals.tax_mapping import match_vat_rate_to_pack, resolve_tax_account


@dataclass(frozen=True)
class ProposedLine:
    line_no: int
    account_id: uuid.UUID
    account_code: str
    counterparty_id: uuid.UUID | None
    label: str
    currency: str
    debit_tx: float
    credit_tx: float
    fx_rate: float
    fx_rate_date: str | None
    fx_source: str | None
    debit_mad: float
    credit_mad: float
    tax_code: str | None
    due_date: str | None
    evidence_refs: list[dict[str, Any]]


@dataclass(frozen=True)
class ProposedEntry:
    journal_code: str
    entry_date: datetime.date
    label: str
    rule_refs: list[str]
    proposed_by: str
    lines: list[ProposedLine]


def _get_or_create_counterparty(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    kind: str,
    name: str,
    ice: str | None = None,
    tax_id: str | None = None,
    default_account_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Finds or creates a counterparty record (supplier or client) for client entity."""
    clean_name = name.strip() if name else "Tiers divers"
    clean_ice = ice.strip() if ice else None
    clean_if = tax_id.strip() if tax_id else None

    with conn.cursor() as cur:
        # Search by ICE if present
        if clean_ice:
            cur.execute(
                """
                SELECT id FROM counterparties
                WHERE tenant_id = %s AND client_entity_id = %s AND ice = %s
                LIMIT 1;
                """,
                (tenant_id, client_entity_id, clean_ice),
            )
            row = cur.fetchone()
            if row:
                return uuid.UUID(str(row[0]))

        # Search by Name
        cur.execute(
            """
            SELECT id FROM counterparties
            WHERE tenant_id = %s AND client_entity_id = %s AND lower(legal_name) = lower(%s)
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, clean_name),
        )
        row = cur.fetchone()
        if row:
            return uuid.UUID(str(row[0]))

        # Create new counterparty
        new_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO counterparties (
                id, tenant_id, client_entity_id, kind, legal_name, ice, if_number, default_account_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (new_id, tenant_id, client_entity_id, kind, clean_name, clean_ice, clean_if, default_account_id),
        )
        return new_id


def build_journal_proposal(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    document_id: uuid.UUID,
    doc_type: str,
    extracted_fields: dict[str, Any],
    actor_id: str | None = None,
) -> ProposedEntry:
    """Constructs balanced Moroccan CGNC journal lines with evidence links for an invoice extraction."""
    # 1. Parse extraction fields
    inv_number = extracted_fields.get("invoice_number", {}).get("value") or "SANS-NUMERO"
    date_str = extracted_fields.get("invoice_date", {}).get("value")
    supplier_ice = extracted_fields.get("supplier_ice", {}).get("value")
    supplier_if = extracted_fields.get("supplier_if", {}).get("value")
    supplier_name = extracted_fields.get("supplier_name", {}).get("value") or "Fournisseur"
    client_name = extracted_fields.get("client_name", {}).get("value") or "Client"

    raw_ht = float(extracted_fields.get("total_ht", {}).get("value") or 0.0)
    raw_vat = float(extracted_fields.get("total_vat", {}).get("value") or extracted_fields.get("total_tva", {}).get("value") or 0.0)
    raw_ttc = float(extracted_fields.get("total_ttc", {}).get("value") or 0.0)
    currency = extracted_fields.get("currency", {}).get("value") or "MAD"

    # Multi-rate breakdown if present
    vat_breakdown_field = extracted_fields.get("vat_breakdown") or extracted_fields.get("tax_lines") or []
    if isinstance(vat_breakdown_field, dict):
        vat_breakdown_val = vat_breakdown_field.get("value") or []
    elif isinstance(vat_breakdown_field, list):
        vat_breakdown_val = vat_breakdown_field
    else:
        vat_breakdown_val = []
    vat_rates_breakdown: list[dict[str, Any]] = vat_breakdown_val if isinstance(vat_breakdown_val, list) else []

    # Ensure arithmetic balance in extracted totals
    if raw_ttc == 0.0 and (raw_ht > 0.0 or raw_vat > 0.0):
        raw_ttc = round(raw_ht + raw_vat, 2)
    elif raw_ht == 0.0 and raw_ttc > 0.0:
        raw_ht = round(raw_ttc - raw_vat, 2)

    entry_date: datetime.date
    if date_str:
        try:
            entry_date = datetime.date.fromisoformat(str(date_str).strip())
        except ValueError:
            entry_date = datetime.date.today()
    else:
        entry_date = datetime.date.today()

    # Evidence references helper
    def make_evidence(field_name: str, fallback_rule: str) -> list[dict[str, Any]]:
        f_info = extracted_fields.get(field_name, {})
        return [
            {
                "field": field_name,
                "value": f_info.get("value"),
                "bbox": f_info.get("bbox"),
                "page": f_info.get("page", 1),
                "confidence": f_info.get("confidence", 1.0),
                "document_id": str(document_id),
                "rule_ref": fallback_rule,
            }
        ]

    # Resolve FX rates
    fx_rate, fx_date, fx_source = resolve_fx_rate(currency, entry_date)

    is_asset = (doc_type in ("fixed_asset", "asset_invoice"))
    is_sale = doc_type in ("sales_invoice", "invoice_sale", "sales_credit_note")
    is_credit_note = "credit_note" in doc_type

    # 2. Determine Journal Code and Label
    if is_sale:
        journal_code = "VEN"
        doc_label = "Avoir client" if is_credit_note else "Facture vente"
        counterparty_kind = "customer"
        counterparty_title = client_name
        counterparty_ice = extracted_fields.get("client_ice", {}).get("value")
    elif is_asset:
        journal_code = "ACH"
        doc_label = "Acquisition immobilisation"
        counterparty_kind = "supplier"
        counterparty_title = supplier_name
        counterparty_ice = supplier_ice
    else:
        journal_code = "ACH"
        doc_label = "Avoir fournisseur" if is_credit_note else "Facture achat"
        counterparty_kind = "supplier"
        counterparty_title = supplier_name
        counterparty_ice = supplier_ice

    entry_label = f"{doc_label} N° {inv_number} - {counterparty_title}".strip()

    # 3. Resolve Counterparty and Accounts
    rule_refs: list[str] = ["cgnc.seed.accounts"]

    # Main charge or revenue account suggestion
    suggestions = suggest_accounts(
        conn=conn,
        tenant_id=tenant_id,
        client_entity_id=client_entity_id,
        doc_type=doc_type,
        counterparty_ice=supplier_ice if not is_sale else None,
        counterparty_name=supplier_name if not is_sale else None,
        description=extracted_fields.get("line_items", {}).get("value"),
    )
    top_suggestion = suggestions[0] if suggestions else None
    if top_suggestion:
        main_account_id = top_suggestion.account_id
        main_account_code = top_suggestion.account_code
        main_account_label = top_suggestion.label
    else:
        default_code = "7111" if is_sale else ("2355" if is_asset else "6111")
        default_lbl = "Ventes de marchandises" if is_sale else ("Matériel informatique" if is_asset else "Achats de marchandises")
        main_account_id, main_account_label = _get_or_create_chart_account(
            conn, tenant_id, client_entity_id, default_code, default_lbl
        )
        main_account_code = default_code

    # Counterparty Account (4411 Fournisseurs / 4481 Immobilisations / 3421 Clients)
    if is_sale:
        cp_account_code = "3421"
        cp_default_label = "Clients"
    elif is_asset:
        cp_account_code = "4481"
        cp_default_label = "Dettes sur acquisitions d'immobilisations"
    else:
        cp_account_code = "4411"
        cp_default_label = "Fournisseurs"

    cp_account_id, _cp_account_label = _get_or_create_chart_account(
        conn, tenant_id, client_entity_id, cp_account_code, cp_default_label
    )
    counterparty_id = _get_or_create_counterparty(
        conn=conn,
        tenant_id=tenant_id,
        client_entity_id=client_entity_id,
        kind=counterparty_kind,
        name=counterparty_title,
        ice=counterparty_ice,
        tax_id=supplier_if if not is_sale else None,
        default_account_id=main_account_id,
    )

    # Resolve VAT Account and Tax Code
    # Determine effective tax code from rate fraction
    vat_direction = "output" if is_sale else "input"
    rate_fraction = (raw_vat / raw_ht) if raw_ht > 0 else 0.0
    matched_tax = match_vat_rate_to_pack(rate_fraction)
    tax_code = matched_tax.code if matched_tax else "STANDARD_20"

    resolved_vat = resolve_tax_account(
        conn=conn,
        tenant_id=tenant_id,
        client_entity_id=client_entity_id,
        tax_code=tax_code,
        direction=vat_direction,
        is_asset=is_asset,
        actor_id=actor_id,
    )
    for r in resolved_vat.rule_refs:
        if r not in rule_refs:
            rule_refs.append(r)

    # 4. Generate Raw Lines (in transaction currency)
    raw_lines: list[dict[str, Any]] = []

    if (doc_type in ("purchase_invoice", "invoice_purchase", "fixed_asset", "receipt", "expense_note") or not is_sale) and not is_credit_note:
        # Normal Purchase / Fixed Asset
        # Line 1: Expense / Asset (Debit HT)
        raw_lines.append({
            "line_no": 1,
            "account_id": main_account_id,
            "account_code": main_account_code,
            "counterparty_id": None,
            "label": f"{doc_label} - {main_account_label}",
            "debit_tx": raw_ht,
            "credit_tx": 0.0,
            "tax_code": tax_code,
            "due_date": None,
            "evidence_refs": make_evidence("total_ht", "cgnc.seed.accounts"),
        })

        # Line 2 (and sub-lines if multi-rate): VAT (Debit TVA)
        if raw_vat > 0:
            if vat_rates_breakdown:
                for sub in vat_rates_breakdown:
                    rate_val = sub.get("rate")
                    sub_rate = float(rate_val) if rate_val is not None else (matched_tax.rate_value if matched_tax else 0.0)
                    sub_vat = float(sub.get("vat_amount") or sub.get("amount_tva") or sub.get("amount") or sub.get("tva") or 0.0)
                    if sub_vat <= 0.0 and "base_ht" in sub and sub_rate > 0:
                        sub_vat = round(float(sub["base_ht"]) * sub_rate, 2)
                    if sub_vat <= 0.0 and len(vat_rates_breakdown) == 1 and raw_vat > 0.0:
                        sub_vat = raw_vat
                    if sub_vat <= 0.0:
                        continue
                    sub_tax = match_vat_rate_to_pack(sub_rate)
                    sub_code = sub_tax.code if sub_tax else tax_code
                    raw_lines.append({
                        "line_no": len(raw_lines) + 1,
                        "account_id": resolved_vat.account_id,
                        "account_code": resolved_vat.account_code,
                        "counterparty_id": None,
                        "label": f"TVA déductible ({sub_code})",
                        "debit_tx": sub_vat,
                        "credit_tx": 0.0,
                        "tax_code": sub_code,
                        "due_date": None,
                        "evidence_refs": make_evidence("total_vat", resolved_vat.rule_refs[0]),
                    })
            else:
                raw_lines.append({
                    "line_no": 2,
                    "account_id": resolved_vat.account_id,
                    "account_code": resolved_vat.account_code,
                    "counterparty_id": None,
                    "label": "TVA déductible",
                    "debit_tx": raw_vat,
                    "credit_tx": 0.0,
                    "tax_code": tax_code,
                    "due_date": None,
                    "evidence_refs": make_evidence("total_vat", resolved_vat.rule_refs[0]),
                })

        # Line 3: Supplier Payable (Credit TTC)
        raw_lines.append({
            "line_no": len(raw_lines) + 1,
            "account_id": cp_account_id,
            "account_code": cp_account_code,
            "counterparty_id": counterparty_id,
            "label": f"Facture {inv_number} - {counterparty_title}",
            "debit_tx": 0.0,
            "credit_tx": raw_ttc,
            "tax_code": None,
            "due_date": None,
            "evidence_refs": make_evidence("total_ttc", "cgnc.seed.accounts"),
        })

    elif doc_type in ("sales_invoice", "invoice_sale") and not is_credit_note:
        # Normal Sales
        # Line 1: Customer Receivable (Debit TTC)
        raw_lines.append({
            "line_no": 1,
            "account_id": cp_account_id,
            "account_code": cp_account_code,
            "counterparty_id": counterparty_id,
            "label": f"Facture {inv_number} - {counterparty_title}",
            "debit_tx": raw_ttc,
            "credit_tx": 0.0,
            "tax_code": None,
            "due_date": None,
            "evidence_refs": make_evidence("total_ttc", "cgnc.seed.accounts"),
        })

        # Line 2: Revenue (Credit HT)
        raw_lines.append({
            "line_no": 2,
            "account_id": main_account_id,
            "account_code": main_account_code,
            "counterparty_id": None,
            "label": f"{doc_label} - {main_account_label}",
            "debit_tx": 0.0,
            "credit_tx": raw_ht,
            "tax_code": tax_code,
            "due_date": None,
            "evidence_refs": make_evidence("total_ht", "cgnc.seed.accounts"),
        })

        # Line 3: Collected VAT (Credit TVA)
        if raw_vat > 0:
            raw_lines.append({
                "line_no": 3,
                "account_id": resolved_vat.account_id,
                "account_code": resolved_vat.account_code,
                "counterparty_id": None,
                "label": "TVA facturée",
                "debit_tx": 0.0,
                "credit_tx": raw_vat,
                "tax_code": tax_code,
                "due_date": None,
                "evidence_refs": make_evidence("total_vat", resolved_vat.rule_refs[0]),
            })

    elif doc_type == "purchase_credit_note" or (is_credit_note and not is_sale):
        # Purchase Credit Note (Avoir fournisseur): Reversal of purchase
        # Line 1: Supplier Payable Reversal (Debit TTC)
        raw_lines.append({
            "line_no": 1,
            "account_id": cp_account_id,
            "account_code": cp_account_code,
            "counterparty_id": counterparty_id,
            "label": f"Avoir {inv_number} - {counterparty_title}",
            "debit_tx": raw_ttc,
            "credit_tx": 0.0,
            "tax_code": None,
            "due_date": None,
            "evidence_refs": make_evidence("total_ttc", "cgnc.seed.accounts"),
        })

        # Line 2: Charge Reversal (Credit HT)
        raw_lines.append({
            "line_no": 2,
            "account_id": main_account_id,
            "account_code": main_account_code,
            "counterparty_id": None,
            "label": f"Avoir - {main_account_label}",
            "debit_tx": 0.0,
            "credit_tx": raw_ht,
            "tax_code": tax_code,
            "due_date": None,
            "evidence_refs": make_evidence("total_ht", "cgnc.seed.accounts"),
        })

        # Line 3: Deductible VAT Reversal (Credit TVA)
        if raw_vat > 0:
            raw_lines.append({
                "line_no": 3,
                "account_id": resolved_vat.account_id,
                "account_code": resolved_vat.account_code,
                "counterparty_id": None,
                "label": "Régularisation TVA déductible",
                "debit_tx": 0.0,
                "credit_tx": raw_vat,
                "tax_code": tax_code,
                "due_date": None,
                "evidence_refs": make_evidence("total_vat", resolved_vat.rule_refs[0]),
            })

    elif doc_type == "sales_credit_note" or (is_credit_note and is_sale):
        # Sales Credit Note (Avoir client): Reversal of sale
        # Line 1: Revenue Reversal (Debit HT)
        raw_lines.append({
            "line_no": 1,
            "account_id": main_account_id,
            "account_code": main_account_code,
            "counterparty_id": None,
            "label": f"Avoir client - {main_account_label}",
            "debit_tx": raw_ht,
            "credit_tx": 0.0,
            "tax_code": tax_code,
            "due_date": None,
            "evidence_refs": make_evidence("total_ht", "cgnc.seed.accounts"),
        })

        # Line 2: Collected VAT Reversal (Debit TVA)
        if raw_vat > 0:
            raw_lines.append({
                "line_no": 2,
                "account_id": resolved_vat.account_id,
                "account_code": resolved_vat.account_code,
                "counterparty_id": None,
                "label": "Régularisation TVA facturée",
                "debit_tx": raw_vat,
                "credit_tx": 0.0,
                "tax_code": tax_code,
                "due_date": None,
                "evidence_refs": make_evidence("total_vat", resolved_vat.rule_refs[0]),
            })

        # Line 3: Client Receivable Reversal (Credit TTC)
        raw_lines.append({
            "line_no": 3,
            "account_id": cp_account_id,
            "account_code": cp_account_code,
            "counterparty_id": counterparty_id,
            "label": f"Avoir client {inv_number} - {counterparty_title}",
            "debit_tx": 0.0,
            "credit_tx": raw_ttc,
            "tax_code": None,
            "due_date": None,
            "evidence_refs": make_evidence("total_ttc", "cgnc.seed.accounts"),
        })

    # 5. Apply Foreign Exchange Conversion & Penny Balancing
    balanced_lines = convert_and_balance_lines(
        lines=raw_lines,
        currency=currency,
        fx_rate=fx_rate,
        fx_rate_date=fx_date,
        fx_source=fx_source,
    )

    # 6. Build typed ProposedLine objects
    final_lines: list[ProposedLine] = []
    for idx, bl in enumerate(balanced_lines, start=1):
        final_lines.append(
            ProposedLine(
                line_no=idx,
                account_id=bl["account_id"],
                account_code=bl["account_code"],
                counterparty_id=bl["counterparty_id"],
                label=bl["label"],
                currency=currency,
                debit_tx=bl["debit_tx"],
                credit_tx=bl["credit_tx"],
                fx_rate=bl["fx_rate"],
                fx_rate_date=bl["fx_rate_date"],
                fx_source=bl["fx_source"],
                debit_mad=bl["debit_mad"],
                credit_mad=bl["credit_mad"],
                tax_code=bl["tax_code"],
                due_date=bl["due_date"],
                evidence_refs=bl["evidence_refs"],
            )
        )

    return ProposedEntry(
        journal_code=journal_code,
        entry_date=entry_date,
        label=entry_label,
        rule_refs=rule_refs,
        proposed_by="rules",
        lines=final_lines,
    )
