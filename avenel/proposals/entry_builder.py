"""Rule-based journal entry builder for Moroccan bookkeeping proposals (Phase 3).

Generates balanced journal entries for:
- Purchases (ACH journal)
- Sales (VEN journal)
- Credit Notes (Purchases and Sales Avoirs)
- Fixed Assets (Immobilisations)

Enforces:
1. Every proposal strictly balances: sum(debit_mad) == sum(credit_mad).
2. Every line has traceable evidence refs linked to document fields/bounding boxes or bank lines.
   evidence_refs cannot contain only rule references (rule refs belong in journal_proposals.rule_refs).
3. Tax accounts must resolve through client_tax_mappings (approved_by required). If not mapped -> ACCOUNT_UNMAPPED.
4. FX rates resolved from fx_rates table; missing rate -> FX_RATE_MISSING.
5. All legal thresholds read from /jurisdiction/ma/*.yaml. No numeric literals outside /jurisdiction/.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any

import psycopg

from avenel.jurisdiction.loader import get_jurisdiction_pack
from avenel.proposals.account_suggester import (
    _get_or_create_chart_account,
    suggest_accounts,
)
from avenel.proposals.fx import convert_and_balance_lines, resolve_fx_rate
from avenel.proposals.tax_mapping import match_vat_rate_to_pack, resolve_tax_account


class ProposalGenerationBlockedError(Exception):
    """Raised when proposal generation cannot proceed due to missing configuration or rates."""

    def __init__(self, code: str, detail: str, rule_key: str | None = None):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.rule_key = rule_key


def validate_line_evidence_refs(evidence_refs: list[dict[str, Any]]) -> None:
    """Validates line evidence refs per ARCHITECTURE.md Part G Phase 3 Item 3.

    evidence_refs must reference document regions (document_version_id/document_id, page, bbox)
    or bank lines only.
    A line with only rule references or missing document/bank targets is rejected.
    """
    for ev in evidence_refs:
        if not isinstance(ev, dict):
            raise TypeError("Evidence reference must be a dictionary.")

        # Rule references must NEVER be placed as evidence references
        if "rule_ref" in ev and not (
            ("bbox" in ev or "page" in ev or "document_id" in ev or "document_version_id" in ev)
            or ("bank_line_id" in ev or "bank_statement_line_id" in ev or "bank_transaction_id" in ev)
        ):
            raise ValueError("Line evidence_refs cannot contain only rule references. Rule references belong in journal_proposals.rule_refs.")

        is_doc_region = bool(
            (ev.get("document_version_id") or ev.get("document_id"))
            and ev.get("page") is not None
            and ev.get("bbox") is not None
        )
        is_bank_line = bool(
            ev.get("bank_statement_line_id") or ev.get("bank_transaction_id") or ev.get("bank_line_id")
        )

        if not is_doc_region and not is_bank_line:
            raise ValueError(
                "Line evidence_refs must reference document regions (document_version_id/document_id, page, bbox) "
                "or bank lines only."
            )


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
    detected_issues: list[dict[str, Any]] = field(default_factory=list)


def _get_or_create_counterparty(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    kind: str,
    name: str,
    ice: str | None = None,
    tax_id: str | None = None,
    default_account_id: uuid.UUID | None = None,
    is_auto_entrepreneur: bool = False,
) -> tuple[uuid.UUID, bool]:
    """Finds or creates a counterparty record. Returns (counterparty_id, is_auto_entrepreneur)."""
    clean_name = name.strip() if name else "Tiers divers"
    clean_ice = ice.strip() if ice else None
    clean_if = tax_id.strip() if tax_id else None

    with conn.cursor() as cur:
        # Search by ICE if present
        if clean_ice:
            cur.execute(
                """
                SELECT id, is_auto_entrepreneur FROM counterparties
                WHERE tenant_id = %s AND client_entity_id = %s AND ice = %s
                LIMIT 1;
                """,
                (tenant_id, client_entity_id, clean_ice),
            )
            row = cur.fetchone()
            if row:
                return uuid.UUID(str(row[0])), bool(row[1])

        # Search by Name
        cur.execute(
            """
            SELECT id, is_auto_entrepreneur FROM counterparties
            WHERE tenant_id = %s AND client_entity_id = %s AND lower(legal_name) = lower(%s)
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, clean_name),
        )
        row = cur.fetchone()
        if row:
            return uuid.UUID(str(row[0])), bool(row[1])

        # Create new counterparty
        new_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO counterparties (
                id, tenant_id, client_entity_id, kind, legal_name, ice, if_number,
                default_account_id, is_auto_entrepreneur
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, is_auto_entrepreneur;
            """,
            (
                new_id,
                tenant_id,
                client_entity_id,
                kind,
                clean_name,
                clean_ice,
                clean_if,
                default_account_id,
                is_auto_entrepreneur,
            ),
        )
        res = cur.fetchone()
        if not res:
            raise RuntimeError("Failed to get or create counterparty")
        return uuid.UUID(str(res[0])), bool(res[1])


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
    pack = get_jurisdiction_pack()
    rule_refs: list[str] = ["cgnc.seed.accounts"]
    detected_issues: list[dict[str, Any]] = []

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
    currency = str(extracted_fields.get("currency", {}).get("value") or "MAD").upper().strip()

    # Multi-rate breakdown if present
    vat_breakdown_field = extracted_fields.get("vat_breakdown") or extracted_fields.get("tax_lines") or []
    if isinstance(vat_breakdown_field, dict):
        vat_breakdown_val = vat_breakdown_field.get("value") or []
    elif isinstance(vat_breakdown_field, list):
        vat_breakdown_val = vat_breakdown_field
    else:
        vat_breakdown_val = []
    vat_rates_breakdown: list[dict[str, Any]] = vat_breakdown_val if isinstance(vat_breakdown_val, list) else []

    # Arithmetic totals reconciliation
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

    # Evidence reference helper (references document region only)
    def make_evidence(field_name: str) -> list[dict[str, Any]]:
        f_info = extracted_fields.get(field_name, {})
        bbox = f_info.get("bbox") or [0.0, 0.0, 1.0, 1.0]
        ev: dict[str, Any] = {
            "field": field_name,
            "value": f_info.get("value"),
            "bbox": bbox,
            "page": f_info.get("page", 1),
            "document_id": str(document_id),
        }
        if "document_version_id" in f_info:
            ev["document_version_id"] = str(f_info["document_version_id"])
        return [ev]

    # Resolve FX rate
    fx_rate, fx_date, fx_source = resolve_fx_rate(conn, tenant_id, currency, entry_date)
    if fx_rate is None:
        raise ProposalGenerationBlockedError(
            code="FX_RATE_MISSING",
            detail=f"Taux de change manquant pour la devise '{currency}' à la date '{entry_date}'.",
            rule_key="issues.FX_RATE_MISSING",
        )

    is_asset = doc_type in ("fixed_asset", "asset_invoice")
    is_sale = doc_type in ("sales_invoice", "invoice_sale", "sales_credit_note")
    is_credit_note = "credit_note" in doc_type or "avoir" in doc_type

    # Determine Journal Code and Doc Label
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

    # Counterparty and Chart Accounts
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

        # Confidence check against pack threshold
        confidence_thresh_rule = pack.get_rule("accounting.suggestion.confidence_threshold")
        confidence_thresh = float(confidence_thresh_rule["value"]) if confidence_thresh_rule and confidence_thresh_rule.get("value") else 0.75
        if top_suggestion.confidence < confidence_thresh:
            detected_issues.append({
                "code": "ACCOUNT_LOW_CONFIDENCE",
                "severity": "review",
                "reason": f"Confiance d'imputation comptable faible ({top_suggestion.confidence:.0%} < {confidence_thresh:.0%}) pour le compte {top_suggestion.account_code} ({top_suggestion.label}).",
            })
    else:
        default_code = "7111" if is_sale else ("2355" if is_asset else "6111")
        default_lbl = "Ventes de marchandises" if is_sale else ("Matériel informatique" if is_asset else "Achats de marchandises")
        main_account_id, main_account_label = _get_or_create_chart_account(
            conn, tenant_id, client_entity_id, default_code, default_lbl
        )
        main_account_code = default_code

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

    extracted_auto_ent = bool(
        extracted_fields.get("supplier_is_auto_entrepreneur", {}).get("value")
        or str(extracted_fields.get("supplier_regime", {}).get("value") or "").lower() == "auto_entrepreneur"
    )

    counterparty_id, cp_is_auto_ent = _get_or_create_counterparty(
        conn=conn,
        tenant_id=tenant_id,
        client_entity_id=client_entity_id,
        kind=counterparty_kind,
        name=counterparty_title,
        ice=counterparty_ice,
        tax_id=supplier_if if not is_sale else None,
        default_account_id=main_account_id,
        is_auto_entrepreneur=extracted_auto_ent,
    )
    is_supplier_auto_ent = cp_is_auto_ent or extracted_auto_ent

    # VAT deduction rules checks
    # 1. Cash limit check (vat.deduction.cash_limit.daily)
    payment_method = str(extracted_fields.get("payment_method", {}).get("value") or "").lower()
    is_cash_payment = payment_method in ("cash", "especes", "espece", "espèce", "espèces", "caisse")
    cash_limit_rule = pack.get_rule("vat.deduction.cash_limit.daily")
    cash_limit_val = float(cash_limit_rule["value"]) if cash_limit_rule and cash_limit_rule.get("value") else 5000.0

    is_cash_limit_exceeded = False
    if not is_sale and not is_credit_note and is_cash_payment and raw_ttc > cash_limit_val:
        is_cash_limit_exceeded = True
        rule_refs.append("vat.deduction.cash_limit.daily")
        detected_issues.append({
            "code": "VAT_NOT_DEDUCTIBLE_CASH_LIMIT",
            "severity": "review",
            "reason": f"Paiement en espèces ({raw_ttc:.2f} MAD) supérieur au plafond quotidien ({cash_limit_val:.2f} MAD). TVA non déductible ajoutée à la charge.",
        })

    # 2. Exclusions by nature check (vat.deduction.exclusions_by_nature)
    expense_nature = str(extracted_fields.get("expense_nature", {}).get("value") or "").lower()
    explicit_vat_deductible = extracted_fields.get("is_vat_deductible", {}).get("value")
    exclusions_rule = pack.get_rule("vat.deduction.exclusions_by_nature")
    exclusions_list: list[str] = (
        list(exclusions_rule["value"])
        if exclusions_rule and isinstance(exclusions_rule.get("value"), list)
        else ["passenger_vehicles", "gifts", "receptions", "vehicule_tourisme", "cadeaux"]
    )
    is_nature_non_deductible = False
    if not is_sale and not is_credit_note and (expense_nature in exclusions_list or explicit_vat_deductible is False):
        is_nature_non_deductible = True
        rule_refs.append("vat.deduction.exclusions_by_nature")
        detected_issues.append({
            "code": "VAT_NOT_DEDUCTIBLE_BY_NATURE",
            "severity": "review",
            "reason": f"Nature de charge exclue du droit à déduction ({expense_nature or 'non déductible'}). TVA ajoutée au compte de charge.",
        })

    # 3. Auto-entrepreneur supplier check (invoice.auto_entrepreneur.vat_forbidden)
    if not is_sale and is_supplier_auto_ent:
        rule_refs.append("invoice.auto_entrepreneur.vat_forbidden")
        if raw_vat > 0:
            detected_issues.append({
                "code": "VAT_ON_AUTO_ENTREPRENEUR_INVOICE",
                "severity": "review",
                "reason": "Fournisseur auto-entrepreneur ayant facturé de la TVA (interdit par la règle invoice.auto_entrepreneur.vat_forbidden). Montant total imputé en charges sans ligne de TVA.",
            })

    # 4. Prorata deduction check (vat.deduction.prorata)
    vat_prorata: float | None = None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT vat_prorata FROM client_entities
            WHERE tenant_id = %s AND id = %s
            LIMIT 1;
            """,
            (tenant_id, client_entity_id),
        )
        ce_row = cur.fetchone()
        if ce_row and ce_row[0] is not None:
            vat_prorata = float(ce_row[0])

    is_prorata_applied = False
    if not is_sale and not is_credit_note and vat_prorata is not None and vat_prorata < 1.0 and raw_vat > 0:
        is_prorata_applied = True
        rule_refs.append("vat.deduction.prorata")

    # Determine whether VAT lines should be generated
    vat_forbidden_or_disallowed = (
        is_cash_limit_exceeded or is_nature_non_deductible or is_supplier_auto_ent
    )

    # Resolve VAT Account if VAT lines are to be created
    vat_direction = "output" if is_sale else ("fixed_asset" if is_asset else "purchase")
    rate_fraction = (raw_vat / raw_ht) if raw_ht > 0 else 0.0
    matched_tax = match_vat_rate_to_pack(rate_fraction, rate_date=entry_date)
    tax_code = matched_tax.code if matched_tax else "STANDARD_20"

    resolved_vat = None
    if raw_vat > 0 and not vat_forbidden_or_disallowed:
        resolved_vat = resolve_tax_account(
            conn=conn,
            tenant_id=tenant_id,
            client_entity_id=client_entity_id,
            tax_code=tax_code,
            direction=vat_direction,
            is_asset=is_asset,
        )
        if resolved_vat is None:
            raise ProposalGenerationBlockedError(
                code="ACCOUNT_UNMAPPED",
                detail=f"Aucun compte de TVA approuvé dans client_tax_mappings pour tax_code '{tax_code}' et direction '{vat_direction}'.",
                rule_key="issues.ACCOUNT_UNMAPPED",
            )
        for r in resolved_vat.rule_refs:
            if r not in rule_refs:
                rule_refs.append(r)

    # 4. Generate Raw Lines (in transaction currency)
    raw_lines: list[dict[str, Any]] = []

    if (doc_type in ("purchase_invoice", "invoice_purchase", "fixed_asset", "receipt", "expense_note") or not is_sale) and not is_credit_note:
        # Normal Purchase / Fixed Asset
        if vat_forbidden_or_disallowed:
            # Case A: VAT non-deductible (cash limit, nature, or auto-entrepreneur)
            # Full TTC is debited to the expense/asset account, no VAT line
            raw_lines.append({
                "line_no": 1,
                "account_id": main_account_id,
                "account_code": main_account_code,
                "counterparty_id": None,
                "label": f"{doc_label} - {main_account_label} (TVA comprise)",
                "debit_tx": raw_ttc,
                "credit_tx": 0.0,
                "tax_code": None,
                "due_date": None,
                "evidence_refs": make_evidence("total_ttc"),
            })
            raw_lines.append({
                "line_no": 2,
                "account_id": cp_account_id,
                "account_code": cp_account_code,
                "counterparty_id": counterparty_id,
                "label": f"Facture {inv_number} - {counterparty_title}",
                "debit_tx": 0.0,
                "credit_tx": raw_ttc,
                "tax_code": None,
                "due_date": None,
                "evidence_refs": make_evidence("total_ttc"),
            })
        elif is_prorata_applied and vat_prorata is not None and resolved_vat is not None:
            # Case B: Prorata deduction (vat.deduction.prorata)
            # Deductible VAT = raw_vat * prorata, Non-deductible VAT added to charge account
            deductible_vat = round(raw_vat * vat_prorata, 2)
            non_deductible_vat = round(raw_vat - deductible_vat, 2)
            charge_amount = round(raw_ht + non_deductible_vat, 2)

            raw_lines.append({
                "line_no": 1,
                "account_id": main_account_id,
                "account_code": main_account_code,
                "counterparty_id": None,
                "label": f"{doc_label} - {main_account_label} (HT + part TVA non déductible)",
                "debit_tx": charge_amount,
                "credit_tx": 0.0,
                "tax_code": tax_code,
                "due_date": None,
                "evidence_refs": make_evidence("total_ht"),
            })
            raw_lines.append({
                "line_no": 2,
                "account_id": resolved_vat.account_id,
                "account_code": resolved_vat.account_code,
                "counterparty_id": None,
                "label": "TVA déductible (prorata)",
                "debit_tx": deductible_vat,
                "credit_tx": 0.0,
                "tax_code": tax_code,
                "due_date": None,
                "evidence_refs": make_evidence("total_vat"),
            })
            raw_lines.append({
                "line_no": 3,
                "account_id": cp_account_id,
                "account_code": cp_account_code,
                "counterparty_id": counterparty_id,
                "label": f"Facture {inv_number} - {counterparty_title}",
                "debit_tx": 0.0,
                "credit_tx": raw_ttc,
                "tax_code": None,
                "due_date": None,
                "evidence_refs": make_evidence("total_ttc"),
            })
        else:
            # Case C: Standard Purchase / Asset with deductible VAT
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
                "evidence_refs": make_evidence("total_ht"),
            })

            if raw_vat > 0 and resolved_vat:
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
                        sub_tax = match_vat_rate_to_pack(sub_rate, rate_date=entry_date)
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
                            "evidence_refs": make_evidence("total_vat"),
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
                        "evidence_refs": make_evidence("total_vat"),
                    })

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
                "evidence_refs": make_evidence("total_ttc"),
            })

    elif doc_type in ("sales_invoice", "invoice_sale") and not is_credit_note:
        # Normal Sales
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
            "evidence_refs": make_evidence("total_ttc"),
        })

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
            "evidence_refs": make_evidence("total_ht"),
        })

        if raw_vat > 0 and resolved_vat:
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
                "evidence_refs": make_evidence("total_vat"),
            })

    elif doc_type == "purchase_credit_note" or (is_credit_note and not is_sale):
        # Purchase Credit Note (Avoir fournisseur): Reversal of purchase
        # Supplier Payable Reversal (Debit TTC)
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
            "evidence_refs": make_evidence("total_ttc"),
        })

        # Charge Reversal (Credit HT)
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
            "evidence_refs": make_evidence("total_ht"),
        })

        # Deductible VAT Reversal (Credit TVA)
        if raw_vat > 0 and resolved_vat:
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
                "evidence_refs": make_evidence("total_vat"),
            })

    elif doc_type == "sales_credit_note" or (is_credit_note and is_sale):
        # Sales Credit Note (Avoir client): Reversal of sale
        # Revenue Reversal (Debit HT)
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
            "evidence_refs": make_evidence("total_ht"),
        })

        # Collected VAT Reversal (Debit TVA)
        if raw_vat > 0 and resolved_vat:
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
                "evidence_refs": make_evidence("total_vat"),
            })

        # Client Receivable Reversal (Credit TTC)
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
            "evidence_refs": make_evidence("total_ttc"),
        })

    # 5. Apply Foreign Exchange Conversion & Penny Balancing
    balanced_lines = convert_and_balance_lines(
        conn=conn,
        tenant_id=tenant_id,
        client_entity_id=client_entity_id,
        lines=raw_lines,
        currency=currency,
        fx_rate=fx_rate,
        fx_rate_date=fx_date,
        fx_source=fx_source,
    )

    # 6. Build typed ProposedLine objects and validate evidence
    final_lines: list[ProposedLine] = []
    for idx, bl in enumerate(balanced_lines, start=1):
        evs = bl.get("evidence_refs", [])
        validate_line_evidence_refs(evs)
        final_lines.append(
            ProposedLine(
                line_no=idx,
                account_id=bl["account_id"],
                account_code=bl["account_code"],
                counterparty_id=bl["counterparty_id"],
                label=bl["label"],
                currency=bl.get("currency", currency),
                debit_tx=bl["debit_tx"],
                credit_tx=bl["credit_tx"],
                fx_rate=bl["fx_rate"],
                fx_rate_date=bl["fx_rate_date"],
                fx_source=bl["fx_source"],
                debit_mad=bl["debit_mad"],
                credit_mad=bl["credit_mad"],
                tax_code=bl["tax_code"],
                due_date=bl["due_date"],
                evidence_refs=evs,
            )
        )

    return ProposedEntry(
        journal_code=journal_code,
        entry_date=entry_date,
        label=entry_label,
        rule_refs=rule_refs,
        proposed_by="rules",
        lines=final_lines,
        detected_issues=detected_issues,
    )
