"""Data Processing Agreement (DPA) generator for Moroccan accounting firms under Loi n° 09-08."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

DPA_NEEDS_EXPERT_KEYS = [
    "compliance.cndp.dpa_wording",
    "compliance.cybersecurity.loi_05_20",
    "compliance.oec.professional_secrecy",
]


def generate_dpa_document(
    tenant_id: uuid.UUID,
    firm_legal_name: str,
    representative_name: str,
    firm_ice: str | None = None,
    firm_city: str = "Casablanca",
) -> dict[str, Any]:
    """Generates a project DPA between the accounting firm (controller) and AVENEL (processor).
    
    Titled strictly as a project to be validated by legal counsel.
    Includes explicit references to needs_expert jurisdiction keys.
    Does not use the word 'conforme'.
    """
    effective_date = datetime.date.today().isoformat()

    clauses = [
        {
            "article": "Article 1 — Objet et cadre légal",
            "content": (
                "Le présent Accord de Traitement des Données (DPA) encadre le traitement des données à caractère personnel "
                "réalisé par AVENEL pour le compte du Client (cabinet comptable/fiduciaire), dans le cadre de la "
                "Loi marocaine n° 09-08 relative à la protection des personnes physiques à l'égard du traitement des données "
                "à caractère personnel et des délibérations de la Commission Nationale de contrôle de la protection des "
                "Données à caractère Personnel (CNDP)."
            ),
        },
        {
            "article": "Article 2 — Nature et finalité du traitement",
            "content": (
                "AVENEL intervient exclusivement en qualité de sous-traitant pour assister le cabinet dans la préparation "
                "des écritures comptables mensuelles, l'extraction de pièces justificatives (factures, reçus, relevés bancaires), "
                "et le rapprochement bancaire. Les données ne sont jamais utilisées pour des finalités tierces ni exploitées "
                "pour l'entraînement de modèles d'intelligence artificielle partagés."
            ),
        },
        {
            "article": "Article 3 — Catégories de données traitées",
            "content": (
                "Les catégories de données traitées comprennent : noms et coordonnées des représentants légaux et tiers "
                "(clients, fournisseurs), numéros d'identification fiscal et douanier (ICE, IF, RC), identifiants bancaires "
                "(RIB), et montants des transactions financières."
            ),
        },
        {
            "article": "Article 4 — Sécurité, hébergement et isolation des données",
            "content": (
                "AVENEL met en œuvre l'isolation cryptographique et logique des données par le mécanisme de Row-Level Security "
                "(RLS) sur PostgreSQL, le chiffrement des données au repos (AES-256) et en transit (TLS 1.3), ainsi qu'une "
                "piste d'audit inviolable hachée par blocs cryptographiques SHA-256."
            ),
        },
        {
            "article": "Article 5 — Secret professionnel et confidentialité",
            "content": (
                "Le personnel d'AVENEL est soumis à une obligation stricte de confidentialité renforcée, tenant compte "
                "du secret professionnel comptable régi par l'Ordre des Experts-Comptables du Maroc (OEC)."
            ),
        },
    ]

    return {
        "title": "Projet — à valider par un juriste",
        "document_type": "Accord de Traitement des Données à Caractère Personnel (Loi 09-08)",
        "effective_date": effective_date,
        "needs_expert_dependencies": DPA_NEEDS_EXPERT_KEYS,
        "legal_notice": "Ce document constitue un projet préparatoire soumis à la validation d'un conseil juridique qualifié.",
        "controller": {
            "tenant_id": str(tenant_id),
            "legal_name": firm_legal_name,
            "representative": representative_name,
            "ice": firm_ice,
            "city": firm_city,
            "role": "Responsable de traitement",
        },
        "processor": {
            "legal_name": "AVENEL SARL",
            "ice": "000000000000000",
            "city": "Casablanca, Maroc",
            "role": "Sous-traitant",
        },
        "jurisdiction": "Royaume du Maroc",
        "governing_law": "Loi n° 09-08",
        "clauses": clauses,
    }
