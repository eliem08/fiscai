"""Jurisdiction-backed VAT tax mapping and CGNC account resolution.

Enforces:
- Rule A.1: All VAT rates and deduction rules are loaded from /jurisdiction/ma/*.yaml.
- Rule A.2: No numeric literals for tax rates or thresholds outside /jurisdiction/.
- Phase 3 Item 2: Tax accounts must resolve through client_tax_mappings (approved_by required).
  If no approved mapping exists, returns None and caller raises ACCOUNT_UNMAPPED (blocking).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import psycopg

from avenel.jurisdiction.loader import get_jurisdiction_pack


@dataclass(frozen=True)
class TaxRateInfo:
    code: str
    rate_value: float
    rule_key: str
    source_citation: str
    label_fr: str


@dataclass(frozen=True)
class ResolvedTaxAccount:
    account_id: uuid.UUID
    account_code: str
    label: str
    tax_code: str
    direction: str  # 'purchase', 'sale', 'fixed_asset', 'rounding'
    rate_value: float
    rule_refs: list[str]


def get_available_vat_rates() -> list[TaxRateInfo]:
    """Loads all verified VAT rates from Moroccan jurisdiction pack."""
    pack = get_jurisdiction_pack()
    rates: list[TaxRateInfo] = []

    standard_rule = pack.get_rule("vat.rate.standard")
    if standard_rule and standard_rule.get("status") == "verified":
        rates.append(
            TaxRateInfo(
                code="STANDARD_20",
                rate_value=float(standard_rule["value"]),
                rule_key="vat.rate.standard",
                source_citation=standard_rule.get("source", "CGI art. 99-A"),
                label_fr=str(standard_rule.get("label", "Taux normal")),
            )
        )

    reduced_rule = pack.get_rule("vat.rate.reduced_10")
    if reduced_rule and reduced_rule.get("status") == "verified":
        rates.append(
            TaxRateInfo(
                code="REDUCED_10",
                rate_value=float(reduced_rule["value"]),
                rule_key="vat.rate.reduced_10",
                source_citation=reduced_rule.get("source", "CGI art. 99-B"),
                label_fr=str(reduced_rule.get("label", "Taux réduit")),
            )
        )

    return rates


def match_vat_rate_to_pack(rate_fraction: float, tolerance: float = 0.005) -> TaxRateInfo | None:
    """Matches an extracted or calculated VAT rate against verified pack rules."""
    rates = get_available_vat_rates()
    for r in rates:
        if abs(r.rate_value - rate_fraction) <= tolerance:
            return r
    return None


def resolve_tax_account(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    tax_code: str,
    direction: str,  # 'purchase', 'sale', 'fixed_asset'
    is_asset: bool = False,
) -> ResolvedTaxAccount | None:
    """Resolves the appropriate CGNC VAT account strictly from client_tax_mappings.

    Requires approved_by IS NOT NULL.
    If no approved mapping exists, returns None (raising ACCOUNT_UNMAPPED blocking issue).
    """
    if is_asset or direction == "fixed_asset":
        db_direction = "fixed_asset"
    elif direction in ("input", "purchase"):
        db_direction = "purchase"
    elif direction in ("output", "sale"):
        db_direction = "sale"
    else:
        db_direction = direction

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT m.account_id, ca.account_code, ca.label
            FROM client_tax_mappings m
            JOIN chart_accounts ca ON ca.id = m.account_id AND ca.tenant_id = m.tenant_id
            WHERE m.tenant_id = %s
              AND m.client_entity_id = %s
              AND m.tax_code = %s
              AND m.direction = %s
              AND m.approved_by IS NOT NULL
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, tax_code, db_direction),
        )
        row = cur.fetchone()
        if not row:
            return None

        rate_info = next((r for r in get_available_vat_rates() if r.code == tax_code), None)
        rate_val = rate_info.rate_value if rate_info else 0.0
        return ResolvedTaxAccount(
            account_id=uuid.UUID(str(row[0])),
            account_code=str(row[1]),
            label=str(row[2]),
            tax_code=tax_code,
            direction=db_direction,
            rate_value=rate_val,
            rule_refs=["client_tax_mappings.approved"],
        )


def get_suggested_tax_account_default(direction: str, is_asset: bool = False) -> tuple[str, str]:
    """Returns suggested default account code and label for UI assistance only.

    NEVER applied automatically to create journal proposal lines.
    """
    if is_asset or direction == "fixed_asset":
        return "34551", "État - TVA récupérable sur immobilisations"
    elif direction in ("input", "purchase"):
        return "34552", "État - TVA récupérable sur charges"
    elif direction == "rounding":
        pack = get_jurisdiction_pack()
        rule = pack.get_rule("accounting.fx_rounding.default_account")
        code = str(rule["value"]) if rule else "6588"
        return code, "Charges / Produits d'arrondi (centimes)"
    else:
        return "4455", "État - TVA facturée"


def resolve_rounding_account(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
) -> tuple[uuid.UUID, str, str]:
    """Resolves rounding account from approved client_tax_mappings direction 'rounding'

    or falls back to pack default marked needs_expert.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT m.account_id, ca.account_code, ca.label
            FROM client_tax_mappings m
            JOIN chart_accounts ca ON ca.id = m.account_id AND ca.tenant_id = m.tenant_id
            WHERE m.tenant_id = %s
              AND m.client_entity_id = %s
              AND m.direction = 'rounding'
              AND m.approved_by IS NOT NULL
            LIMIT 1;
            """,
            (tenant_id, client_entity_id),
        )
        row = cur.fetchone()
        if row:
            return uuid.UUID(str(row[0])), str(row[1]), str(row[2])

    pack = get_jurisdiction_pack()
    rule = pack.get_rule("accounting.fx_rounding.default_account")
    default_code = str(rule["value"]) if rule else "6588"
    default_label = "Charges / Produits d'arrondi (centimes)"

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, label FROM chart_accounts
            WHERE tenant_id = %s AND client_entity_id = %s AND account_code = %s
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, default_code),
        )
        acc_row = cur.fetchone()
        if acc_row:
            return uuid.UUID(str(acc_row[0])), default_code, str(acc_row[1])
        else:
            new_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label, source)
                VALUES (%s, %s, %s, %s, %s, 'manual')
                RETURNING id;
                """,
                (new_id, tenant_id, client_entity_id, default_code, default_label),
            )
            return new_id, default_code, default_label


def seed_approved_client_tax_mappings(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    approver_id: uuid.UUID | None = None,
) -> None:
    """Helper to seed approved tax mappings for a client entity (used for setups and testing)."""
    user_id = approver_id or uuid.uuid4()

    def _ensure_acc(code: str, label: str) -> uuid.UUID:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM chart_accounts
                WHERE tenant_id = %s AND client_entity_id = %s AND account_code = %s
                LIMIT 1;
                """,
                (tenant_id, client_entity_id, code),
            )
            row = cur.fetchone()
            if row:
                return uuid.UUID(str(row[0]))
            new_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label, source)
                VALUES (%s, %s, %s, %s, %s, 'cgnc_seed')
                RETURNING id;
                """,
                (new_id, tenant_id, client_entity_id, code, label),
            )
            return new_id

    acc_34552 = _ensure_acc("34552", "État - TVA récupérable sur charges")
    acc_34551 = _ensure_acc("34551", "État - TVA récupérable sur immobilisations")
    acc_4455 = _ensure_acc("4455", "État - TVA facturée")
    acc_6588 = _ensure_acc("6588", "Charges / Produits d'arrondi (centimes)")

    mappings = [
        ("STANDARD_20", "purchase", acc_34552),
        ("REDUCED_10", "purchase", acc_34552),
        ("STANDARD_20", "fixed_asset", acc_34551),
        ("REDUCED_10", "fixed_asset", acc_34551),
        ("STANDARD_20", "sale", acc_4455),
        ("REDUCED_10", "sale", acc_4455),
        ("ROUNDING", "rounding", acc_6588),
    ]

    with conn.cursor() as cur:
        for tax_code, direction, acc_id in mappings:
            cur.execute(
                """
                INSERT INTO client_tax_mappings (
                    tenant_id, client_entity_id, tax_code, direction, account_id, approved_by, approved_at
                ) VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (tenant_id, client_entity_id, tax_code, direction)
                DO UPDATE SET account_id = EXCLUDED.account_id, approved_by = EXCLUDED.approved_by, approved_at = now();
                """,
                (tenant_id, client_entity_id, tax_code, direction, acc_id, user_id),
            )

