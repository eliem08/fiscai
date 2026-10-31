"""Deterministic invoice validation service implementing ARCHITECTURE.md D.6.

Runs after every extraction and every user edit.
All tax and legal rules are read strictly from /jurisdiction/ma/ per Rule A.1 and A.2.
"""

from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import asdict, dataclass
from typing import Any

import psycopg

from avenel.jurisdiction.loader import get_jurisdiction_pack


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str  # 'info', 'review', 'blocking'
    title: str
    details: dict[str, Any]


@dataclass(frozen=True)
class ValidationReport:
    is_valid: bool
    blocking_count: int
    review_count: int
    info_count: int
    issues: list[ValidationIssue]

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "blocking_count": self.blocking_count,
            "review_count": self.review_count,
            "info_count": self.info_count,
            "issues": [asdict(i) for i in self.issues],
        }


def get_known_vat_rates_for_date(invoice_date_str: str | None) -> list[float]:
    """Retrieves verified Moroccan VAT rates from jurisdiction pack effective on invoice_date."""
    pack = get_jurisdiction_pack()
    rates: list[float] = []

    target_date: datetime.date | None = None
    if invoice_date_str:
        try:
            target_date = datetime.date.fromisoformat(str(invoice_date_str).strip())
        except (ValueError, TypeError):
            target_date = None

    for rule_key, rule in pack.rules.items():
        if not rule_key.startswith("vat.rate.") or rule_key == "vat.rate.mapping_items":
            continue
        if rule.get("status") != "verified" or rule.get("value") is None:
            continue
        try:
            val = float(rule["value"])
        except (ValueError, TypeError):
            continue

        eff_from = rule.get("effective_from")
        eff_to = rule.get("effective_to")

        if target_date is not None:
            if eff_from and target_date < datetime.date.fromisoformat(str(eff_from)):
                continue
            if eff_to and target_date > datetime.date.fromisoformat(str(eff_to)):
                continue

        rates.append(val)

    # Zero rate (exempted operations per pack)
    rates.append(0.0)
    return sorted(set(rates))


def validate_invoice_extraction(
    fields: dict[str, Any],
    doc_type: str = "purchase_invoice",
    period_start: datetime.date | None = None,
    period_end: datetime.date | None = None,
) -> ValidationReport:
    """Executes all Section D.6 deterministic checks on extracted fields."""
    pack = get_jurisdiction_pack()
    issues: list[ValidationIssue] = []

    tolerance = float(pack.get_value("invoice.arithmetic_tolerance", 0.01))
    cash_limit = float(pack.get_value("vat.deduction.cash_limit.daily", 5000.00))

    # Helper to retrieve field value
    def f_val(field_name: str) -> Any:
        obj = fields.get(field_name)
        if isinstance(obj, dict):
            return obj.get("value")
        return obj

    inv_date_str = f_val("invoice_date")
    known_rates = get_known_vat_rates_for_date(inv_date_str)

    # 1. Mandatory mentions from pack
    if doc_type in ("purchase_invoice", "credit_note", "receipt"):
        mandatory_fields = pack.get_value("invoice.mandatory_mentions.purchase", [])
        missing_severity = "review"  # deductibility at risk for purchases
    else:
        mandatory_fields = pack.get_value("invoice.mandatory_mentions.sale", [])
        missing_severity = "info"  # info for client-prepared sales

    for field_name in mandatory_fields:
        val = f_val(field_name)
        if val is None or (isinstance(val, str) and not val.strip()):
            issues.append(
                ValidationIssue(
                    code="INVOICE_MISSING_MANDATORY_FIELD",
                    severity=missing_severity,
                    title=f"Mention obligatoire manquante : {field_name}",
                    details={"field": field_name, "rule": "invoice.mandatory_mentions"},
                )
            )

    # 2. Per-rate arithmetic check:
    # Σ line HT = HT per rate; HT × rate = TVA (tolerance 0.01 MAD per rate); Σ HT + Σ TVA = TTC
    tot_ht = f_val("total_ht")
    tot_vat = f_val("total_vat")
    tot_ttc = f_val("total_ttc")
    tax_breakdown = fields.get("tax_breakdown", [])

    if tot_ht is not None and tot_vat is not None and tot_ttc is not None:
        # Check overall HT + TVA = TTC
        diff_ttc = abs((tot_ht + tot_vat) - tot_ttc)
        if diff_ttc > tolerance:
            issues.append(
                ValidationIssue(
                    code="TOTALS_INCONSISTENT",
                    severity="blocking",
                    title="Incohérence arithmétique globale (Total HT + TVA ≠ Total TTC)",
                    details={
                        "total_ht": tot_ht,
                        "total_vat": tot_vat,
                        "total_ttc": tot_ttc,
                        "diff": round(diff_ttc, 4),
                        "tolerance": tolerance,
                    },
                )
            )

        # Check per-rate arithmetic in breakdown
        for item in tax_breakdown:
            rate = float(item.get("rate", 0.0))
            base = float(item.get("base_ht", 0.0))
            tax_amt = float(item.get("tax_amount", 0.0))

            expected_tax = base * rate
            if abs(expected_tax - tax_amt) > tolerance:
                issues.append(
                    ValidationIssue(
                        code="TOTALS_INCONSISTENT",
                        severity="blocking",
                        title=f"Incohérence arithmétique TVA au taux {rate:.0%}",
                        details={
                            "rate": rate,
                            "base_ht": base,
                            "tax_amount": tax_amt,
                            "expected_tax": round(expected_tax, 2),
                            "tolerance": tolerance,
                        },
                    )
                )

    # 3. Rate not in pack for invoice date -> VAT_RATE_UNKNOWN (blocking)
    for item in tax_breakdown:
        rate = float(item.get("rate", 0.0))
        # Rate matches if within tolerance of any known rate
        if not any(abs(rate - kr) <= 0.001 for kr in known_rates):
            issues.append(
                ValidationIssue(
                    code="VAT_RATE_UNKNOWN",
                    severity="blocking",
                    title=f"Taux de TVA inconnu dans le pack fiscal ({rate:.1%})",
                    details={"rate": rate, "known_rates": known_rates},
                )
            )

    # 4. Supplier auto-entrepreneur and TVA > 0 -> VAT_ON_AUTO_ENTREPRENEUR_INVOICE (review)
    is_auto = bool(f_val("supplier_is_auto_entrepreneur"))
    if is_auto and tot_vat is not None and tot_vat > 0.0:
        issues.append(
            ValidationIssue(
                code="VAT_ON_AUTO_ENTREPRENEUR_INVOICE",
                severity="review",
                title="TVA facturée par un auto-entrepreneur (hors champ d'application)",
                details={"supplier_is_auto_entrepreneur": True, "total_vat": tot_vat},
            )
        )

    # 5. Paid in cash above pack limit -> VAT_NOT_DEDUCTIBLE_CASH_LIMIT (review)
    payment_method = str(f_val("payment_method") or "").lower()
    if payment_method == "cash" and tot_ttc is not None and tot_ttc > cash_limit:
        issues.append(
            ValidationIssue(
                code="VAT_NOT_DEDUCTIBLE_CASH_LIMIT",
                severity="review",
                title="Plafond de paiement en espèces dépassé (TVA non déductible)",
                details={
                    "payment_method": "cash",
                    "total_ttc": tot_ttc,
                    "cash_limit": cash_limit,
                    "rule": "vat.deduction.cash_limit.daily",
                },
            )
        )

    # 6. Invoice date outside the accounting period -> PERIOD_MISMATCH (review)
    if inv_date_str and (period_start or period_end):
        try:
            inv_date = datetime.date.fromisoformat(inv_date_str)
            if period_start and inv_date < period_start:
                issues.append(
                    ValidationIssue(
                        code="PERIOD_MISMATCH",
                        severity="review",
                        title="Date de la facture antérieure au début de la période comptable",
                        details={"invoice_date": inv_date_str, "period_start": period_start.isoformat()},
                    )
                )
            elif period_end and inv_date > period_end:
                issues.append(
                    ValidationIssue(
                        code="PERIOD_MISMATCH",
                        severity="review",
                        title="Date de la facture postérieure à la clôture de la période comptable",
                        details={"invoice_date": inv_date_str, "period_end": period_end.isoformat()},
                    )
                )
        except ValueError:
            pass

    blocking_count = sum(1 for i in issues if i.severity == "blocking")
    review_count = sum(1 for i in issues if i.severity == "review")
    info_count = sum(1 for i in issues if i.severity == "info")
    is_valid = (blocking_count == 0)

    return ValidationReport(
        is_valid=is_valid,
        blocking_count=blocking_count,
        review_count=review_count,
        info_count=info_count,
        issues=issues,
    )


def persist_validation_results(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
    document_id: uuid.UUID,
    extraction_id: uuid.UUID,
    report: ValidationReport,
) -> None:
    """Updates extractions.validation and synchronizes issues and document status."""
    with conn.cursor() as cur:
        # Clear previously auto-detected open issues for this document
        cur.execute(
            """
            DELETE FROM issues
            WHERE tenant_id = %s AND subject_document_id = %s AND status = 'open';
            """,
            (tenant_id, document_id),
        )

        # Insert fresh issues
        for issue in report.issues:
            cur.execute(
                """
                INSERT INTO issues (
                    tenant_id, client_entity_id, work_request_id, subject_document_id,
                    code, severity, status, evidence_refs
                ) VALUES (%s, %s, %s, %s, %s, %s, 'open', %s);
                """,
                (
                    tenant_id,
                    client_entity_id,
                    work_request_id,
                    document_id,
                    issue.code,
                    issue.severity,
                    json.dumps([issue.details] if issue.details else []),
                ),
            )

        # Determine document status
        if report.blocking_count > 0 or report.review_count > 0:
            new_doc_status = "needs_review"
        else:
            new_doc_status = "read"

        cur.execute(
            """
            UPDATE documents
            SET status = %s
            WHERE tenant_id = %s AND id = %s AND status != 'quarantined';
            """,
            (new_doc_status, tenant_id, document_id),
        )
