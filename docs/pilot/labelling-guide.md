# AVENEL — Guide d'Annotation des Pièces Comptables (`labels.jsonl`)

**Fichier cible :** `tests/fixtures/real/labels.jsonl` (chiffré au repos, gitignored)  
**Référence :** ARCHITECTURE.md (Part H, Phase 5b)  
**Standard :** Boîtes englobantes normalisées `[x0, y0, x1, y1]` de 0.0 à 1.0.

---

## 1. Structure du Fichier `labels.jsonl`

Chaque ligne du fichier `labels.jsonl` représente un document comptable complet au format JSON compact :

```json
{
  "document_id": "real_inv_001.pdf",
  "doc_type": "purchase_invoice",
  "language": "fr",
  "page_count": 1,
  "fields": {
    "invoice_number": {
      "value": "FA-2026-1049",
      "bbox": [0.6512, 0.1245, 0.8841, 0.1482],
      "page": 1
    },
    "invoice_date": {
      "value": "2026-10-14",
      "bbox": [0.6512, 0.1550, 0.8234, 0.1780],
      "page": 1
    },
    "counterparty_name": {
      "value": "FOURNITURES DU SOUSS SARL",
      "bbox": [0.0821, 0.0950, 0.4520, 0.1250],
      "page": 1
    },
    "counterparty_ice": {
      "value": "001827364000082",
      "bbox": [0.0821, 0.1300, 0.3200, 0.1480],
      "page": 1
    },
    "counterparty_if": {
      "value": "40291823",
      "bbox": [0.0821, 0.1520, 0.2500, 0.1700],
      "page": 1
    },
    "total_ht": {
      "value": "12500.00",
      "bbox": [0.7200, 0.7420, 0.8900, 0.7650],
      "page": 1
    },
    "total_tva": {
      "value": "2500.00",
      "bbox": [0.7200, 0.7700, 0.8900, 0.7930],
      "page": 1
    },
    "total_ttc": {
      "value": "15000.00",
      "bbox": [0.7200, 0.8100, 0.8900, 0.8350],
      "page": 1
    },
    "currency": {
      "value": "MAD",
      "bbox": [0.8950, 0.8100, 0.9400, 0.8350],
      "page": 1
    }
  },
  "vat_breakdown": [
    {
      "rate": 0.20,
      "base_ht": "12500.00",
      "vat_amount": "2500.00"
    }
  ]
}
```

---

## 2. Règles de Découpage et Bounding Boxes `[x0, y0, x1, y1]`

1. **Repère normalisé :**
   - Coin supérieur gauche de la page : `(x0, y0) = (0.0, 0.0)`
   - Coin inférieur droit de la page : `(x1, y1) = (1.0, 1.0)`
   - Les coordonnées doivent respecter l'invariant : $0.0 \le x_0 < x_1 \le 1.0$ et $0.0 \le y_0 < y_1 \le 1.0$.
2. **Encadrement strict :** La boîte englobante doit recouvrir la valeur textuelle nette, en excluant les préfixes ou intitulés de champ (ex. pour `"Date : 14/10/2026"`, la boîte n'englobe que `"14/10/2026"`).
3. **Cas bilingue Arabe / Français :**
   - Si la mention figure en arabe et en français (ex. *Facture / فاتورة*), l'annotation retient la valeur numérique ou textuelle exploitée par le système.
   - Si le montant en lettres est bilingue, l'extraction se cale sur les totaux chiffrés.

---

## 3. Normalisation des Valeurs

- **Dates :** Format ISO-8601 strict `YYYY-MM-DD`.
- **Montants :** Chaîne de caractères décimale à 2 décimales, séparateur point `.` (ex. `"15400.50"`).
- **Identifiants légaux :**
  - `counterparty_ice` : Exactement 15 chiffres numériques (aucun tiret, aucun espace).
  - `counterparty_if` : 1 à 10 chiffres numériques.
  - `counterparty_rc` : Numéro de registre du commerce avec ville (ex. `"14520 Casablanca"`).

---

## 4. Outil d'Évaluation Automatisé

L'évaluation de la performance du moteur OCR et de l'extracteur s'exécute via la commande :
```bash
python scripts/evaluate_real_set.py --dataset tests/fixtures/real/
```
Le rapport généré produit le taux de conformité exact par champ contre les seuils minimaux de la Partie H :
- ICE/IF $\ge 98.0\%$
- Date et Numéro $\ge 97.0\%$
- Montants HT / TVA / TTC $\ge 99.0\%$
- Erreurs silencieuses sur montants : **Rigoureusement 0.0%**.
