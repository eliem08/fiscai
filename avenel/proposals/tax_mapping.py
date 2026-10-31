"""Jurisdiction-backed VAT tax mapping and CGNC account resolution.

Enforces:
- Rule A.1: All VAT rates and deduction rules are loaded from /jurisdiction/ma/*.yaml.
- Rule A.2: No numeric literals for tax rates or thresholds outside /jurisdiction/.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import psycopg

from avenel.accounting.service import seed_cgnc_chart
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
    direction: str  # 'input' (dductible) or 'output' (collecte)
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
    actor_id: str | None = None,
) -> ResolvedTaxAccount:
    """Resolves the appropriate CGNC VAT account (34552, 34551, 4455, or client override)."""
    # Normalize direction to match DB check constraint: ('purchase','sale','fixed_asset','withholding')
    if is_asset or direction == "fixed_asset":
        db_direction = "fixed_asset"
    elif direction in ("input", "purchase"):
        db_direction = "purchase"
    elif direction in ("output", "sale"):
        db_direction = "sale"
    else:
        db_direction = direction

    # 1. Check for client-specific override in client_tax_mappings
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
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, tax_code, db_direction),
        )
        row = cur.fetchone()
        if row:
            rate_info = next((r for r in get_available_vat_rates() if r.code == tax_code), None)
            rate_val = rate_info.rate_value if rate_info else 0.0
            return ResolvedTaxAccount(
                account_id=uuid.UUID(str(row[0])),
                account_code=str(row[1]),
                label=str(row[2]),
                tax_code=tax_code,
                direction=db_direction,
                rate_value=rate_val,
                rule_refs=["client_tax_mappings.override"],
            )

    # 2. Determine default CGNC account code per direction and asset flag
    if db_direction == "purchase":
        target_code = "34552"
        default_label = "État - TVA récupérable sur charges"
    elif db_direction == "fixed_asset":
        target_code = "34551"
        default_label = "État - TVA récupérable sur immobilisations"
    else:
        target_code = "4455"
        default_label = "État - TVA facturée"

    # 3. Fetch or seed chart account for client
    account_id: uuid.UUID | None = None
    account_label: str = default_label

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, label FROM chart_accounts
            WHERE tenant_id = %s AND client_entity_id = %s AND account_code = %s
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, target_code),
        )
        acc_row = cur.fetchone()
        if acc_row:
            account_id = uuid.UUID(str(acc_row[0]))
            account_label = str(acc_row[1])
        else:
            # Seed CGNC chart if empty or missing this account
            if actor_id:
                seed_cgnc_chart(conn, tenant_id, client_entity_id, actor_id=actor_id)
            else:
                seed_cgnc_chart(conn, tenant_id, client_entity_id, actor_id=str(uuid.uuid4()))

            cur.execute(
                """
                SELECT id, label FROM chart_accounts
                WHERE tenant_id = %s AND client_entity_id = %s AND account_code = %s
                LIMIT 1;
                """,
                (tenant_id, client_entity_id, target_code),
            )
            seeded_row = cur.fetchone()
            if seeded_row:
                account_id = uuid.UUID(str(seeded_row[0]))
                account_label = str(seeded_row[1])
            else:
                # Insert directly if not in seed (source must be 'cgnc_seed' or 'manual')
                new_id = uuid.uuid4()
                cur.execute(
                    """
                    INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label, source)
                    VALUES (%s, %s, %s, %s, %s, 'cgnc_seed')
                    RETURNING id;
                    """,
                    (new_id, tenant_id, client_entity_id, target_code, default_label),
                )
                account_id = new_id

    # 4. Find matched rate
    pack_rate = 0.0
    rule_key = "vat.rate.standard"
    rates = get_available_vat_rates()
    for r in rates:
        if r.code == tax_code:
            pack_rate = r.rate_value
            rule_key = r.rule_key
            break

    return ResolvedTaxAccount(
        account_id=account_id,
        account_code=target_code,
        label=account_label,
        tax_code=tax_code,
        direction=direction,
        rate_value=pack_rate,
        rule_refs=[rule_key, "cgnc.seed.accounts"],
    )
