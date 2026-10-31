"""CNDP declaration dossier generator under Moroccan Law 09-08 requirements."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

CNDP_NEEDS_EXPERT_KEYS = [
    "compliance.cndp.provider_routes",
    "compliance.cndp.dpa_wording",
    "compliance.cybersecurity.loi_05_20",
    "compliance.oec.ai_assisted_preparation",
    "compliance.oec.professional_secrecy",
]


def generate_cndp_dossier(
    tenant_id: uuid.UUID,
    firm_legal_name: str,
    representative_name: str,
    firm_ice: str | None = None,
    firm_email: str | None = None,
) -> dict[str, Any]:
    """Generates the CNDP Declaration Dossier (Déclaration Préalable de Traitement) for accounting preparation.
    
    Titled strictly as a project to be validated by legal counsel.
    Includes explicit references to needs_expert jurisdiction keys.
    Does not use the word 'conforme'.
    """
    generation_date = datetime.date.today().isoformat()

    return {
        "title": "Projet — à valider par un juriste",
        "dossier_type": "Dossier de Déclaration Préalable auprès de la CNDP",
        "governing_statute": "Loi marocaine n° 09-08 promulguée par le Dahir n° 1-09-15 du 18 février 2009",
        "generated_at": generation_date,
        "needs_expert_dependencies": CNDP_NEEDS_EXPERT_KEYS,
        "legal_notice": "Ce document constitue un projet préparatoire soumis à la validation d'un conseil juridique qualifié.",
        "responsible_entity": {
            "tenant_id": str(tenant_id),
            "legal_name": firm_legal_name,
            "representative": representative_name,
            "ice": firm_ice,
            "contact_email": firm_email,
            "profession": "Expert-comptable / Comptable agréé / Fiduciaire",
        },
        "purpose_of_processing": {
            "primary": "Gestion comptable, fiscale et financière des entreprises clientes",
            "secondary": "Préparation automatisée des liasses et journaux comptables mensuels",
            "exempt_from_transfer_abroad": True,
            "hosting_jurisdiction": "Maroc / Cloud souverain certifié",
        },
        "data_subjects": [
            "Dirigeants et représentants légaux des clients",
            "Tiers personnes physiques (fournisseurs, prestataires, clients particuliers)",
            "Salariés identifiés sur bordereaux de charges",
        ],
        "categories_of_data": [
            "Données d'identification (Nom, Prénom, ICE, CIN)",
            "Données financières (Numéro de facture, montant HT, TVA, TTC, RIB)",
            "Données professionnelles (Raison sociale, fonction)",
        ],
        "subcontractor": {
            "name": "AVENEL SARL",
            "service": "Plateforme d'assistance agentique à la pré-comptabilisation",
            "security_guarantees": [
                "Strict isolation des bases par Row-Level Security (RLS)",
                "Chiffrement intégral TLS 1.3 et AES-256",
                "Non-utilisation des données pour réentraînement d'IA",
                "Journalisation d'audit inviolable hachée par blocs cryptographiques",
            ],
        },
        "declaration_checklist": {
            "formulaire_cndp_signe": True,
            "accord_dpa_annexe": True,
            "mesures_securite_documentees": True,
            "registre_traitements_tenu": True,
        },
    }
