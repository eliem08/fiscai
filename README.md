# FiscAI PreClear

**Plateforme agentique de pré-contrôle fiscal et douanier pour le Maroc.**

FiscAI PreClear analyse les factures, documents fiscaux et dossiers import/export des PME,
importateurs, exportateurs, cabinets comptables et transitaires **avant** leur transmission aux
comptables, transitaires, flux PortNet/BADR ou processus DGI. L'application détecte les documents
manquants, les incohérences TVA et douanières, calcule un score de risque, et produit un rapport
de pré-contrôle validé par un expert humain.

> ⚠️ **Avertissement légal** — FiscAI fournit une assistance au pré-contrôle fiscal et douanier.
> Les résultats doivent être vérifiés par un comptable, un transitaire ou un expert habilité avant
> tout usage officiel. FiscAI est un outil d'aide à la décision : il ne remplace ni les comptables,
> ni les transitaires, ni les administrations fiscales ou douanières.

---

## 1. Utilisateurs cibles

- PME importatrices / exportatrices marocaines
- Cabinets comptables et fiduciaires
- Transitaires et déclarants en douane
- Directions financières préparant des dossiers DGI / ADII

## 2. Workflow principal

1. **Créer un dossier** (import, export ou fiscal/TVA)
2. **Téléverser les documents** (facture commerciale, liste de colisage, B/L, certificat d'origine…)
3. **Lancer l'analyse IA** — pipeline de 7 agents spécialisés (intake, fiscal, douane,
   réglementation, conformité, anomalies, rapport)
4. **Lire le score de risque** (fiscal /100, douanier /100, global) + checklist + questions fournisseur
5. **Traiter les alertes** (critique → faible) jusqu'à résolution
6. **Revue experte obligatoire** pour les dossiers à risque élevé/critique
7. **Générer et exporter le rapport** de pré-contrôle structuré

## 3. Stack technique

| Couche | Choix |
| --- | --- |
| UI | React 18 + TypeScript (strict), Vite 5 |
| Style | Tailwind CSS, lucide-react |
| Routage | React Router 6 (routes protégées, lazy loading) |
| État | Zustand (auth, toasts) |
| Tests unitaires/composants | Vitest + React Testing Library + jest-dom |
| Tests E2E | Playwright (Chromium) |
| Qualité | ESLint, Prettier, `tsc` strict |

## 4. Structure du projet

```
src/
  components/
    ui/        # Composants réutilisables (Modal, EmptyState, ErrorState, Skeleton, Pagination…)
    domain/    # Composants métier (RiskBadge, DossierCard, AlertCard, UploadZone, AgentCard, ReportPreview…)
    layout/    # AppLayout, Sidebar, guards (RequireAuth / RequireRole), ErrorBoundary
  pages/       # Une page = un fichier (Dashboard, Dossiers, Alerts, ExpertReview, Reports, Audit…)
  services/    # Couche service mockée (Auth, Dossier, Document, AIAnalysis, Alert, Report, ExpertReview, AuditLog, Organization) + db.ts
  lib/         # Logique métier pure et testée (riskScoring, checklist, extraction, alertRules, sqlGuard, sanitize, validation, report)
  mocks/       # Données de démonstration réalistes (seed)
  store/       # Stores Zustand
  types/       # Modèles de données typés
e2e/           # Parcours Playwright (5 journeys)
```

## 5. Lancer en local

```bash
npm install
npm run dev        # http://localhost:5173
```

Comptes de démonstration (mot de passe commun `Demo1234!`) :

| E-mail | Rôle |
| --- | --- |
| `demo@fiscai.ma` | Analyste |
| `expert@fiscai.ma` | Expert (revue experte) |
| `admin@fiscai.ma` | Admin (journal d'audit, paramètres, reset démo) |

Astuces démo : le nom des fichiers téléversés pilote l'extraction simulée —
`facture-tva-erreur.pdf` (incohérence TVA), `facture-vague.pdf` (désignation vague),
`facture-flou.pdf` (faible confiance), `dum-sans-sh.pdf` (code SH manquant),
`facture-sans-fournisseur.pdf` (identité fournisseur absente). Un dossier dont le titre contient
`[fail-analysis]` simule une panne du moteur IA.

## 6. Tests

```bash
npm run test              # tous les tests unitaires + composants (Vitest)
npm run test:unit         # logique métier + services
npm run test:components   # composants + pages
npm run test:coverage     # couverture
npm run test:e2e          # Playwright (build + preview automatiques)
npm run lint              # ESLint (0 warning toléré)
npm run typecheck         # TypeScript strict
npm run format:check      # Prettier
npm run check             # typecheck + lint + tests + build (porte qualité complète)
```

Première exécution E2E : `npx playwright install chromium`.

### Stratégie de test

- **Unitaires (`src/lib`, `src/services`)** : scoring de risque (low/medium/high/critical, liste de
  colisage, TVA, code SH, fournisseur, certificat d'origine, revue experte), extraction mockée
  (champs manquants, faible confiance, type invalide, multi-documents), checklist, génération
  d'alertes par sévérité, garde SQL lecture seule, sanitisation/anti-injection de prompt,
  validation de formulaires et de fichiers, pipeline d'agents, sections obligatoires du rapport,
  journal d'audit, isolation par organisation.
- **Composants** : badges de risque/sévérité/statut, KPI, cartes dossier/alerte/agent, zone
  d'upload (acceptation/rejet), aperçu de rapport (toutes sections), formulaire de revue experte,
  cartes tarifaires, sidebar et navigation par rôle, états vides / erreurs / chargement.
- **E2E (Playwright)** : ① analyse complète d'un dossier import (upload → analyse → scores →
  checklist → questions → rapport), ② revue experte + piste d'audit, ③ workflow d'alertes,
  ④ navigation sans erreur + garde d'authentification + 404, ⑤ validations et chemins d'erreur
  (titre manquant, fichier non supporté, analyse partielle, faible confiance, panne moteur).

## 7. Build de production

```bash
npm run build     # tsc + vite build -> dist/
npm run preview   # sert dist/ sur http://localhost:4173
```

## 8. Sécurité (hypothèses actuelles)

- **Garde d'authentification** (`RequireAuth`) et **accès par rôle** (`RequireRole` :
  viewer < analyst < expert < admin) sur les routes et la sidebar.
- **Isolation par organisation** : chaque service filtre systématiquement par `organizationId`.
- **Upload sécurisé** : liste blanche d'extensions et de types MIME, limite 10 Mo, rejet des
  fichiers vides ; validation côté composant **et** côté service.
- **Sanitisation des entrées** (`sanitizeText`, `escapeHtml`) + rendu React échappé par défaut (XSS).
- **Garde NLU-to-SQL** : lecture seule — DELETE/DROP/UPDATE/INSERT/ALTER/TRUNCATE/EXEC/MERGE
  bloqués, y compris en instructions empilées (« Mode lecture seule activé pour protéger vos données. »).
- **Couche anti-injection de prompt** : le contenu des documents est traité comme données, jamais
  comme instructions ; les motifs suspects déclenchent un avertissement.
- **Journal d'audit** : connexion, création de dossier, upload, analyse, alertes, rapport, revue
  experte, suppression de document, changement de paramètres — avec utilisateur, horodatage et
  niveau de risque.
- **Validation humaine obligatoire** : aucun dossier à risque élevé/critique n'est « validé » sans
  revue experte ; l'avertissement légal est affiché sur toutes les pages sensibles.

⚠️ Le backend étant mocké, l'authentification réelle (hachage de mots de passe, tokens signés,
rate limiting) et le stockage chiffré des documents restent à brancher (voir §10).

## 9. Ce qui est mocké

| Service | Mock actuel | À brancher plus tard |
| --- | --- | --- |
| AuthService | comptes seed + localStorage | IdP réel (Auth0/Keycloak/Supabase), MFA |
| DocumentService | métadonnées seules (aucun octet stocké) | S3/GCS + antivirus + chiffrement |
| AIAnalysisService | pipeline déterministe piloté par le nom de fichier | LLM (Claude API) + OCR/IDP réel |
| RiskScoring/Checklist/Alertes | règles métier réelles, en TypeScript pur | conservées côté serveur |
| ReportService | export texte | PDF + e-mail |
| Persistance (`db.ts`) | in-memory + localStorage | PostgreSQL + API REST |

La couche `services/` est le **seul** point de contact du UI avec les données : remplacer les mocks
par des appels HTTP ne touche ni les pages ni les composants.

## 10. Infrastructure locale (docker-compose)

Les services d'infrastructure d'AVENEL sont orchestrés via `docker-compose.yml` :
- **PostgreSQL 16** (`postgres:16-alpine`, port 5432) : base relationnelle avec RLS forcé sur 28 tables.
- **Keycloak** (`quay.io/keycloak/keycloak:26.8.1`, port 8080) : IdP OIDC pour l'authentification et les sessions.
- **MinIO** (`minio/minio:RELEASE.2024-10-13T13-34-11Z`, ports 9000/9001) : stockage objet S3 local.
- **OCR Service (STUB)** (`avenel-ocr-stub`, port 8001) : bouchon/stub de développement (`python -m http.server`). Le moteur OCR réel et le pipeline d'extraction seront branchés en Phase 2.

## 11. Checklist de déploiement

- [ ] Variables d'environnement configurées (`VITE_API_URL`, `VITE_AUTH_DOMAIN`, `ANTHROPIC_API_KEY` côté serveur, DSN Sentry)
- [ ] Authentification réelle connectée (+ hachage, sessions, MFA)
- [ ] Base de données connectée (PostgreSQL) et migrations
- [ ] Stockage de fichiers connecté (S3 compatible, scan antivirus, chiffrement au repos)
- [ ] API IA connectée (Claude API) + service OCR réel (remplacement du stub docker)
- [ ] Export e-mail / PDF des rapports
- [ ] Monitoring et error tracking activés (Sentry + uptime)
- [ ] Politique de sauvegarde définie (base + fichiers)
- [ ] Politique de confidentialité et mentions légales publiées
- [ ] Avertissement légal visible (déjà intégré dans l'UI)
- [ ] Workflow de validation experte activé avec de vrais experts habilités

## 11. Checklist démo CEED / investisseurs

1. `npm run dev`, se connecter avec `demo@fiscai.ma` / `Demo1234!`
2. (Optionnel) Admin → Paramètres → « Réinitialiser les données de démo »
3. Dashboard : KPI + dossier « Import composants électroniques — Shenzhen » en revue requise
4. Créer un dossier import, téléverser `facture-tva-erreur.pdf` **sans** liste de colisage
5. Lancer l'analyse : montrer la progression des 7 agents, puis les scores, l'alerte critique
   « liste de colisage manquante », la checklist et les questions fournisseur
6. Générer le rapport et montrer sa structure complète (synthèse → avertissement)
7. Basculer sur `expert@fiscai.ma` : dérouler la revue experte
8. Basculer sur `admin@fiscai.ma` : montrer le journal d'audit complet
9. Terminer sur la page tarifs (Starter / Pro / Enterprise)
