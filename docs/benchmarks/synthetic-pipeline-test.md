# Rapport de Test du Pipeline Synthétique — Ingestion & Extraction

**Date d'exécution :** 2026-10-31 17:28:49Z
**Moteur OCR :** `RapidOCR / PaddleOCR ONNX PP-OCRv4 + Multilingual v3` (version `1.4.4`)
**Modèles de reconnaissance :** ONNX Latin & Arabe multilingues (ancrés par checksums SHA-256)
**Taille du corpus synthétique :** **45 documents**
**Composition du corpus :** **30 factures Français (FR)**, **10 factures Arabe (AR)**, **5 factures Bilingues/Mixtes (FR/AR)**
**Perturbations appliquées aux images :** skew ±1.0°, Gaussian sensor noise (σ=6.0), JPEG quality 70

> [!IMPORTANT]
> Ce test évalue la robustesse de l'extraction sur des images synthétiques dégradées par bruit et compression.
> Conformément à la Partie H d'ARCHITECTURE.md, les portes cibles officielles ne sont validées
> que sur le corpus de test réel labellisé (tests/fixtures/real/).

## 1. Résultats Exact Match par Champ (Ensemble du Corpus)

| Champ extrait | Total | Exact Match | Échecs | Taux Exact Match | Seuil Cible Partie H |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `invoice_number` | 45 | 44 | 1 | **97.78%** | >= 97.0% |
| `invoice_date` | 45 | 45 | 0 | **100.00%** | >= 97.0% |
| `supplier_ice` | 45 | 45 | 0 | **100.00%** | >= 97.0% |
| `supplier_if` | 45 | 45 | 0 | **100.00%** | — |
| `total_ht` | 45 | 45 | 0 | **100.00%** | >= 98.0% |
| `total_vat` | 45 | 45 | 0 | **100.00%** | >= 98.0% |
| `total_ttc` | 45 | 44 | 1 | **97.78%** | >= 98.0% |

## 2. Résultats Exact Match par Langue

| Champ extrait | Français (FR - 30 docs) | Arabe (AR - 10 docs) | Bilingue / Mixte (FR/AR - 5 docs) |
| :--- | :---: | :---: | :---: |
| `invoice_number` | 100.0% | 100.0% | 80.0% |
| `invoice_date` | 100.0% | 100.0% | 100.0% |
| `supplier_ice` | 100.0% | 100.0% | 100.0% |
| `supplier_if` | 100.0% | 100.0% | 100.0% |
| `total_ht` | 100.0% | 100.0% | 100.0% |
| `total_vat` | 100.0% | 100.0% | 100.0% |
| `total_ttc` | 100.0% | 100.0% | 80.0% |

## 3. Évaluation face aux Portes Cibles Partie H (Pilote)

| Porte Cible Partie H | Métrique | Cible Pilote | Résultat Obtenu | Statut |
| :--- | :--- | :---: | :---: | :---: |
| **ICE, N° Facture, Date** | Exact Match | >= 97.0% | **97.78%** | Atteint |
| **HT, TVA par taux, TTC** | Exact Match | >= 98.0% | **97.78%** | Non atteint |

## 4. Analyse Transparente des Échecs sous Bruit d'Image

Détail des documents ayant présenté des écarts sous les perturbations de scan :

- **Document `mixed_inv_001`** (Langue: `mixed`, Catégorie: `bilingual_mixed`) :
  - `invoice_number` : attendu `FAC-MIX-6001`, extrait `xFAC-MIX-6001`
- **Document `mixed_inv_002`** (Langue: `mixed`, Catégorie: `bilingual_mixed`) :
  - `total_ttc` : attendu `7672.68`, extrait `17672.68`
