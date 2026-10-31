# Rapport de Test du Pipeline Synthétique — Ingestion & Extraction

**Date d'exécution :** 2026-10-31 19:26:37Z
**Moteur OCR :** `RapidOCR / PaddleOCR ONNX PP-OCRv4 + Multilingual v3` (version `1.4.4`)
**Modèles de reconnaissance :** ONNX Latin & Arabe multilingues (ancrés par checksums SHA-256)
**Taille du corpus synthétique :** **60 documents**
**Composition du corpus :** **30 factures Français (FR)**, **10 factures Arabe (AR, synthetic, clean rendering)**, **20 factures Bilingues/Mixtes (FR/AR)**
**Perturbations appliquées aux images :** skew ±1.0°, Gaussian sensor noise (σ=6.0), JPEG quality 70

> [!IMPORTANT]
> Ce test évalue la robustesse de l'extraction sur des images synthétiques dégradées par bruit et compression.
> Conformément à la Partie H d'ARCHITECTURE.md, les portes cibles officielles ne sont validées
> que sur le corpus de test réel labellisé (tests/fixtures/real/).

## 1. Résultats Exact Match par Champ (Ensemble du Corpus)

| Champ extrait | Total | Exact Match | Échecs | Taux Exact Match | Seuil Cible Partie H |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `invoice_number` | 60 | 58 | 2 | **96.67%** | >= 97.0% |
| `invoice_date` | 60 | 55 | 5 | **91.67%** | >= 97.0% |
| `supplier_ice` | 60 | 60 | 0 | **100.00%** | >= 97.0% |
| `supplier_if` | 60 | 59 | 1 | **98.33%** | — |
| `total_ht` | 60 | 60 | 0 | **100.00%** | >= 98.0% |
| `total_vat` | 60 | 60 | 0 | **100.00%** | >= 98.0% |
| `total_ttc` | 60 | 60 | 0 | **100.00%** | >= 98.0% |

## 2. Résultats Exact Match par Langue

| Champ extrait | Français (FR - 30 docs) | Arabe (AR - 10 docs, synthetic, clean rendering) | Bilingue / Mixte (FR/AR - 20 docs) |
| :--- | :---: | :---: | :---: |
| `invoice_number` | 100.0% | 100.0% | 90.0% |
| `invoice_date` | 100.0% | 90.0% | 80.0% |
| `supplier_ice` | 100.0% | 100.0% | 100.0% |
| `supplier_if` | 100.0% | 100.0% | 95.0% |
| `total_ht` | 100.0% | 100.0% | 100.0% |
| `total_vat` | 100.0% | 100.0% | 100.0% |
| `total_ttc` | 100.0% | 100.0% | 100.0% |

## 3. Évaluation face aux Portes Cibles Partie H (Pilote)

| Porte Cible Partie H | Métrique | Cible Pilote | Résultat Obtenu | Statut |
| :--- | :--- | :---: | :---: | :---: |
| **ICE, N° Facture, Date** | Exact Match | >= 97.0% | **88.33%** | Non atteint |
| **HT, TVA par taux, TTC** | Exact Match | >= 98.0% | **100.00%** | Atteint |
| **Erreurs silencieuses HT/TVA/TTC** | Silent Error Rate | 0.0% | **0.00%** | Atteint |

## 4. Taux d'Erreurs Silencieuses (Silent Error Rate)

| Champ extrait | Échecs totaux | Détectés (Caught) | Silencieux (Silent) | Taux d'erreur silencieuse |
| :--- | :---: | :---: | :---: | :---: |
| `invoice_number` | 2 | 2 | 0 | **0.00%** |
| `invoice_date` | 5 | 5 | 0 | **0.00%** |
| `supplier_ice` | 0 | 0 | 0 | **0.00%** |
| `supplier_if` | 1 | 1 | 0 | **0.00%** |
| `total_ht` | 0 | 0 | 0 | **0.00%** |
| `total_vat` | 0 | 0 | 0 | **0.00%** |
| `total_ttc` | 0 | 0 | 0 | **0.00%** |

## 5. Analyse Transparente des Échecs sous Bruit d'Image

Détail des documents ayant présenté des écarts sous les perturbations de scan :

- **Document `ar_inv_009`** (Langue: `ar`, Catégorie: `arabic_commercial`) :
  - `invoice_date` : attendu `2026-10-10`, extrait `None`
- **Document `mixed_inv_001`** (Langue: `mixed`, Catégorie: `bilingual_mixed`) :
  - `invoice_number` : attendu `FAC-MIX-6001`, extrait `xFAC-MIX-6001`
- **Document `mixed_inv_011`** (Langue: `mixed`, Catégorie: `bilingual_mixed`) :
  - `invoice_date` : attendu `2026-12-12`, extrait `None`
- **Document `mixed_inv_013`** (Langue: `mixed`, Catégorie: `bilingual_mixed`) :
  - `invoice_date` : attendu `2026-02-14`, extrait `None`
- **Document `mixed_inv_014`** (Langue: `mixed`, Catégorie: `bilingual_mixed`) :
  - `invoice_date` : attendu `2026-03-15`, extrait `None`
  - `supplier_if` : attendu `78901234`, extrait `1`
- **Document `mixed_inv_015`** (Langue: `mixed`, Catégorie: `bilingual_mixed`) :
  - `invoice_number` : attendu `FAC-MIX-6015`, extrait `UFAC-MIX-6015`
- **Document `mixed_inv_020`** (Langue: `mixed`, Catégorie: `bilingual_mixed`) :
  - `invoice_date` : attendu `2026-09-21`, extrait `None`
