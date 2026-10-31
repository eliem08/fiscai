# Rapport de Test du Pipeline Synthétique — Ingestion & Extraction

**Date d'exécution :** 2026-10-31 23:14:18Z
**Moteur OCR :** `RapidOCR / PaddleOCR ONNX PP-OCRv4 + Multilingual v3` (version `1.4.4`)
**Modèles de reconnaissance :** ONNX Latin & Arabe multilingues (ancrés par checksums SHA-256)
**Taille du corpus synthétique :** **5 documents**
**Composition du corpus :** **5 factures Français (FR)**, **0 factures Arabe (AR, synthetic, clean rendering)**, **0 factures Bilingues/Mixtes (FR/AR)**
**Perturbations appliquées aux images :** skew ±1.0°, Gaussian sensor noise (σ=6.0), JPEG quality 70

> [!IMPORTANT]
> Ce test évalue la robustesse de l'extraction sur des images synthétiques dégradées par bruit et compression.
> Conformément à la Partie H d'ARCHITECTURE.md, les portes cibles officielles ne sont validées
> que sur le corpus de test réel labellisé (tests/fixtures/real/).

## 1. Résultats Exact Match par Champ (Ensemble du Corpus)

| Champ extrait | Total | Exact Match | Échecs | Taux Exact Match | Seuil Cible Partie H |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `invoice_number` | 5 | 5 | 0 | **100.00%** | >= 97.0% |
| `invoice_date` | 5 | 5 | 0 | **100.00%** | >= 97.0% |
| `supplier_ice` | 5 | 5 | 0 | **100.00%** | >= 97.0% |
| `supplier_if` | 5 | 5 | 0 | **100.00%** | — |
| `total_ht` | 5 | 5 | 0 | **100.00%** | >= 98.0% |
| `total_vat` | 5 | 5 | 0 | **100.00%** | >= 98.0% |
| `total_ttc` | 5 | 5 | 0 | **100.00%** | >= 98.0% |

## 2. Résultats Exact Match par Langue

| Champ extrait | Français (FR - 5 docs) | Arabe (AR - 0 docs, synthetic, clean rendering) | Bilingue / Mixte (FR/AR - 0 docs) |
| :--- | :---: | :---: | :---: |
| `invoice_number` | 100.0% | 0.0% | 0.0% |
| `invoice_date` | 100.0% | 0.0% | 0.0% |
| `supplier_ice` | 100.0% | 0.0% | 0.0% |
| `supplier_if` | 100.0% | 0.0% | 0.0% |
| `total_ht` | 100.0% | 0.0% | 0.0% |
| `total_vat` | 100.0% | 0.0% | 0.0% |
| `total_ttc` | 100.0% | 0.0% | 0.0% |

## 3. Évaluation face aux Portes Cibles Partie H (Pilote)

| Porte Cible Partie H | Métrique | Cible Pilote | Résultat Obtenu | Statut |
| :--- | :--- | :---: | :---: | :---: |
| **ICE, N° Facture, Date** | Exact Match | >= 97.0% | **100.00%** | Atteint |
| **HT, TVA par taux, TTC** | Exact Match | >= 98.0% | **100.00%** | Atteint |
| **Erreurs silencieuses HT/TVA/TTC** | Silent Error Rate | 0.0% | **0.00%** | Atteint |

## 4. Taux d'Erreurs Silencieuses (Silent Error Rate)

| Champ extrait | Échecs totaux | Détectés (Caught) | Silencieux (Silent) | Taux d'erreur silencieuse |
| :--- | :---: | :---: | :---: | :---: |
| `invoice_number` | 0 | 0 | 0 | **0.00%** |
| `invoice_date` | 0 | 0 | 0 | **0.00%** |
| `supplier_ice` | 0 | 0 | 0 | **0.00%** |
| `supplier_if` | 0 | 0 | 0 | **0.00%** |
| `total_ht` | 0 | 0 | 0 | **0.00%** |
| `total_vat` | 0 | 0 | 0 | **0.00%** |
| `total_ttc` | 0 | 0 | 0 | **0.00%** |

## 5. Analyse Transparente des Échecs sous Bruit d'Image

Détail des documents ayant présenté des écarts sous les perturbations de scan :

Aucun échec constaté sur le corpus évalué.
