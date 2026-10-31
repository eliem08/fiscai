"""CGNC Account Suggester for Moroccan Bookkeeping Proposals.

Recommends appropriate CGNC chart accounts based on document type, supplier activity,
historical counterparty mappings, and item descriptions.
Target: Account suggestion accepted as first choice >= 80% (ARCHITECTURE.md Part H).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass

import psycopg

from avenel.accounting.service import seed_cgnc_chart
from avenel.extraction.router import ProviderCallRequest, ProviderRouter


@dataclass(frozen=True)
class AccountSuggestion:
    account_id: uuid.UUID
    account_code: str
    label: str
    confidence: float
    reasoning: str


# Keyword heuristic maps for Moroccan expense classification
KEYWORD_MAPPINGS: list[tuple[re.Pattern[str], str, str, str]] = [
    # Fixed Assets (Classe 2)
    (
        re.compile(r"\b(ordinateur|serveur|pc|laptop|ecran|imprimante|informatique|serveurs)\b", re.IGNORECASE),
        "2355",
        "Matériel informatique",
        "Mot-clé matériel informatique détecté",
    ),
    (
        re.compile(r"\b(fauteuil|chaise|bureau|armoire|table|mobilier)\b", re.IGNORECASE),
        "2351",
        "Mobilier de bureau",
        "Mot-clé mobilier de bureau détecté",
    ),
    (
        re.compile(r"\b(vehicule|camion|fourgon|voiture|automobile)\b", re.IGNORECASE),
        "2340",
        "Matériel de transport",
        "Mot-clé matériel de transport détecté",
    ),
    (
        re.compile(r"\b(machine|outillage|compresseur|groupe electrogene)\b", re.IGNORECASE),
        "2332",
        "Matériel et outillage",
        "Mot-clé outillage industriel détecté",
    ),
    # Charges d'exploitation (Classe 6)
    (
        re.compile(r"\b(loyer|location|bail|immobiliere)\b", re.IGNORECASE),
        "6131",
        "Locations et charges locatives",
        "Frais de loyer ou location détectés",
    ),
    (
        re.compile(r"\b(assurance|rc pro|multirisque|police d'assurance)\b", re.IGNORECASE),
        "6134",
        "Primes d'assurances",
        "Police ou prime d'assurance détectée",
    ),
    (
        re.compile(r"\b(publicite|marketing|annonces|facebook|google|flyers|catalogue)\b", re.IGNORECASE),
        "6144",
        "Publicité, publications, relations publiques",
        "Dépense publicitaire et promotionnelle détectée",
    ),
    (
        re.compile(r"\b(hotel|restaurant|repas|mission|deplacement|billet|avion|train)\b", re.IGNORECASE),
        "6143",
        "Déplacements, missions et réceptions",
        "Frais de mission et déplacement détectés",
    ),
    (
        re.compile(r"\b(agios|frais de tenue|commission bancaire|virement)\b", re.IGNORECASE),
        "6147",
        "Services bancaires",
        "Frais et services bancaires détectés",
    ),
    (
        re.compile(r"\b(carburant|essence|gasoil|electricite|eau|fournitures de bureau|consommables)\b", re.IGNORECASE),
        "6125",
        "Achats non stockés de matières et fournitures",
        "Achats de matières et fournitures consommables",
    ),
    (
        re.compile(r"\b(consulting|etude|conseil|developpement|audit|honoraires|formation)\b", re.IGNORECASE),
        "6141",
        "Études, recherches et documentation",
        "Prestations d'études, conseil ou honoraires",
    ),
    (
        re.compile(r"\b(matiere premiere|matiere|acier|bois|plastique)\b", re.IGNORECASE),
        "6121",
        "Achats de matières premières",
        "Achats de matières premières de production",
    ),
    (
        re.compile(r"\b(marchandise|negoce|produit fini|revente)\b", re.IGNORECASE),
        "6111",
        "Achats de marchandises",
        "Achats de marchandises destinées à la revente",
    ),
]

SALES_KEYWORD_MAPPINGS: list[tuple[re.Pattern[str], str, str, str]] = [
    (
        re.compile(r"\b(service|prestation|honoraires|conseil|developpement|formation|maintenance)\b", re.IGNORECASE),
        "7124",
        "Ventes de services produits au Maroc",
        "Prestation de services facturée",
    ),
    (
        re.compile(r"\b(vente|marchandise|produit|materiel)\b", re.IGNORECASE),
        "7111",
        "Ventes de marchandises au Maroc",
        "Vente de marchandises au Maroc",
    ),
]


def _get_or_create_chart_account(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    account_code: str,
    default_label: str,
) -> tuple[uuid.UUID, str]:
    """Finds or creates the CGNC chart account for a given client company."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, label FROM chart_accounts
            WHERE tenant_id = %s AND client_entity_id = %s AND account_code = %s
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, account_code),
        )
        row = cur.fetchone()
        if row:
            return uuid.UUID(str(row[0])), str(row[1])

        # Seed CGNC chart if empty
        seed_cgnc_chart(conn, tenant_id, client_entity_id, actor_id=str(uuid.uuid4()))

        cur.execute(
            """
            SELECT id, label FROM chart_accounts
            WHERE tenant_id = %s AND client_entity_id = %s AND account_code = %s
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, account_code),
        )
        row_after = cur.fetchone()
        if row_after:
            return uuid.UUID(str(row_after[0])), str(row_after[1])

        # Insert directly if not in standard seed (source must be 'cgnc_seed' or 'manual')
        new_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label, source)
            VALUES (%s, %s, %s, %s, %s, 'cgnc_seed')
            RETURNING id;
            """,
            (new_id, tenant_id, client_entity_id, account_code, default_label),
        )
        return new_id, default_label


def suggest_accounts(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    doc_type: str,
    counterparty_ice: str | None = None,
    counterparty_name: str | None = None,
    description: str | None = None,
    work_request_id: uuid.UUID | None = None,
    use_llm: bool = False,
    router: ProviderRouter | None = None,
    residency_policy: str = "MA_ONLY",
) -> list[AccountSuggestion]:
    """Suggests ranked CGNC accounts for an invoice or proposal line.

    Top suggestion designed to achieve >= 80% acceptance under pilot conditions.
    LLM usage: Deterministic by default. When use_llm=True, calls must pass through ProviderRouter
    to enforce data residency policy and log to agent_runs table.
    Under MA_ONLY without local container model, cleanly falls back to counterparty history.
    """
    suggestions: list[AccountSuggestion] = []
    seen_codes: set[str] = set()

    # 1. Historical counterparty preference (primary deterministic ground truth)
    if counterparty_ice or counterparty_name:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.default_account_id, ca.account_code, ca.label
                FROM counterparties c
                JOIN chart_accounts ca ON ca.id = c.default_account_id AND ca.tenant_id = c.tenant_id
                WHERE c.tenant_id = %s AND c.client_entity_id = %s
                  AND (c.ice = %s OR lower(c.legal_name) = lower(%s))
                  AND c.default_account_id IS NOT NULL
                LIMIT 1;
                """,
                (tenant_id, client_entity_id, counterparty_ice, counterparty_name),
            )
            cp_row = cur.fetchone()
            if cp_row:
                acc_id = uuid.UUID(str(cp_row[0]))
                code = str(cp_row[1])
                lbl = str(cp_row[2])
                suggestions.append(
                    AccountSuggestion(
                        account_id=acc_id,
                        account_code=code,
                        label=lbl,
                        confidence=0.95,
                        reasoning=f"Compte historique mémorisé pour le tiers {counterparty_name or counterparty_ice}",
                    )
                )
                seen_codes.add(code)

    # 2. LLM classification if requested (strictly routes through residency router and logs agent_runs)
    if use_llm:
        p_router = router or ProviderRouter(db_conn=conn)
        req = ProviderCallRequest(
            provider="openai",
            region="us-east-1",  # External cloud region
            model="gpt-4o",
            purpose="account_suggestion",
            payload={
                "doc_type": doc_type,
                "counterparty_name": counterparty_name,
                "description": description,
            },
        )
        resp = p_router.execute_call(tenant_id=tenant_id, policy=residency_policy, request=req)

        # Log agent_runs if work_request_id provided
        if work_request_id:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_runs (
                        tenant_id, work_request_id, task, agent_version, prompt_version,
                        input_refs, output, schema_valid, provider_call_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        tenant_id,
                        work_request_id,
                        "account_suggestion",
                        "1.0",
                        "1.0",
                        json.dumps({"counterparty": counterparty_name, "description": description}),
                        json.dumps(resp.result) if resp.result else None,
                        resp.status == "completed",
                        resp.provider_call_id,
                    ),
                )

        if resp.status == "completed" and resp.result and "account_code" in resp.result:
            llm_code = str(resp.result["account_code"])
            llm_lbl = str(resp.result.get("label", "Compte suggéré par IA"))
            llm_conf = float(resp.result.get("confidence", 0.85))
            if llm_code not in seen_codes:
                acc_id, real_lbl = _get_or_create_chart_account(conn, tenant_id, client_entity_id, llm_code, llm_lbl)
                suggestions.insert(
                    0,
                    AccountSuggestion(
                        account_id=acc_id,
                        account_code=llm_code,
                        label=real_lbl,
                        confidence=llm_conf,
                        reasoning="Suggestion par modèle d'imputation comptable",
                    ),
                )
                seen_codes.add(llm_code)
        # If refused_by_policy (e.g. MA_ONLY with external cloud model), seamlessly fall back to counterparty history

    # Combined text for keyword matching
    search_text = f"{counterparty_name or ''} {description or ''}".strip()

    # 2. Sales vs Purchases / Fixed Assets
    if doc_type in ("invoice_sale", "sales_credit_note"):
        for pattern, code, label, reason in SALES_KEYWORD_MAPPINGS:
            if pattern.search(search_text) and code not in seen_codes:
                acc_id, real_lbl = _get_or_create_chart_account(conn, tenant_id, client_entity_id, code, label)
                suggestions.append(
                    AccountSuggestion(
                        account_id=acc_id,
                        account_code=code,
                        label=real_lbl,
                        confidence=0.90,
                        reasoning=reason,
                    )
                )
                seen_codes.add(code)

        # Fallback sales defaults
        default_sales_code = "7111"
        default_sales_lbl = "Ventes de marchandises au Maroc"
        if default_sales_code not in seen_codes:
            acc_id, real_lbl = _get_or_create_chart_account(conn, tenant_id, client_entity_id, default_sales_code, default_sales_lbl)
            suggestions.append(
                AccountSuggestion(
                    account_id=acc_id,
                    account_code=default_sales_code,
                    label=real_lbl,
                    confidence=0.60 if not suggestions else 0.50,
                    reasoning="Compte de vente standard CGNC",
                )
            )
    elif doc_type == "fixed_asset":
        # Fixed assets prioritization
        for pattern, code, label, reason in KEYWORD_MAPPINGS:
            if code.startswith("2") and pattern.search(search_text) and code not in seen_codes:
                acc_id, real_lbl = _get_or_create_chart_account(conn, tenant_id, client_entity_id, code, label)
                suggestions.append(
                    AccountSuggestion(
                        account_id=acc_id,
                        account_code=code,
                        label=real_lbl,
                        confidence=0.92,
                        reasoning=reason,
                    )
                )
                seen_codes.add(code)

        default_asset_code = "2355"
        default_asset_lbl = "Matériel informatique"
        if default_asset_code not in seen_codes:
            acc_id, real_lbl = _get_or_create_chart_account(conn, tenant_id, client_entity_id, default_asset_code, default_asset_lbl)
            suggestions.append(
                AccountSuggestion(
                    account_id=acc_id,
                    account_code=default_asset_code,
                    label=real_lbl,
                    confidence=0.60 if not suggestions else 0.50,
                    reasoning="Immobilisation corporelle standard",
                )
            )
    else:
        # Standard purchases & purchase credit notes
        for pattern, code, label, reason in KEYWORD_MAPPINGS:
            if pattern.search(search_text) and code not in seen_codes:
                acc_id, real_lbl = _get_or_create_chart_account(conn, tenant_id, client_entity_id, code, label)
                suggestions.append(
                    AccountSuggestion(
                        account_id=acc_id,
                        account_code=code,
                        label=real_lbl,
                        confidence=0.90,
                        reasoning=reason,
                    )
                )
                seen_codes.add(code)

        default_purchase_code = "6111"
        default_purchase_lbl = "Achats de marchandises"
        if default_purchase_code not in seen_codes:
            acc_id, real_lbl = _get_or_create_chart_account(conn, tenant_id, client_entity_id, default_purchase_code, default_purchase_lbl)
            suggestions.append(
                AccountSuggestion(
                    account_id=acc_id,
                    account_code=default_purchase_code,
                    label=real_lbl,
                    confidence=0.60 if not suggestions else 0.50,
                    reasoning="Compte d'achat de marchandises standard CGNC",
                )
            )

    return suggestions
