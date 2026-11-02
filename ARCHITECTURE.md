# AVENEL — Architecture and Build Instructions

Version 2.1 · 1 November 2026 · Supersedes Version 2.0 (30 October 2026)

This file is the single source of truth for building AVENEL. It is written for an AI coding agent and the humans reviewing its work. Read Part A completely before writing any code.

---

# Part A — Instructions for the AI builder

## A.1 Your role

You are the implementing engineer for AVENEL, a service that prepares monthly bookkeeping files for Moroccan accounting firms (*fiduciaires*). You write production code, migrations, tests, and UI. You do not make accounting, tax, legal, or pricing decisions. Those come from this document, from the jurisdiction pack in `/jurisdiction/ma/`, or from a human.

## A.2 Rules you follow without exception

1. **Never invent a domain rule.** Every tax rate, threshold, account code, deadline, or legal requirement is read from `/jurisdiction/ma/*.yaml` at runtime. If you need a rule that is not there, stop, add an entry with `status: needs_expert` and `TODO(EXPERT)` in the commit message, and continue with the rule disabled. Do not guess a value.
2. **No numeric literals for tax or legal values outside `/jurisdiction/`.** CI fails on `20`, `10`, `5000`, `50000`, `75`, `100` used as rates or thresholds in application code. Use pack lookups.
3. **AI proposes, code validates, humans approve.** No code path posts, files, pays, or exports without an approval record bound to the exact content hash being exported.
4. **Tenant isolation is enforced twice.** Application authorization on every request, and PostgreSQL row-level security (forced) on every tenant table. Never disable RLS, never connect the app as a table owner, never use session-level `SET` for tenant context.
5. **Posted, approved, and audited data is immutable.** Corrections are new rows (reversals, revisions). Never write `UPDATE` or `DELETE` against audit, evidence, approved proposals, or document versions.
6. **Never edit an applied migration.** Add a new one.
7. **Tests use fixtures, not live providers.** No network calls to OCR or LLM providers in the test suite. Use recorded responses.
8. **No secrets in code, logs, fixtures, or prompts.** Logs never contain document contents, ICE/IF/RIB values, or names. Log identifiers and hashes only.
9. **Follow the design system in Part E exactly.** Do not add colors, fonts, gradients, shadows, or decorative elements that are not defined there.
10. **Write plain product copy.** French first, sentence case, no marketing language inside the product. See E.8.

## A.3 How you work

- Build in the phases of Part G, in order. Each phase ends with every exit criterion met and the full test suite green. Then stop and summarize for human review: what was built, what was tested, what is unverified, and every `TODO(EXPERT)` added.
- Before starting a phase, write a short plan in `docs/plans/phase-N.md`: files to create, migrations, tests, open questions.
- Prefer boring, explicit code. One obvious way to do each thing. No speculative abstractions, no plugin systems, no microservices.
- When the spec is ambiguous, choose the more restrictive interpretation (deny access, require review, block export) and record the question in `docs/open-questions.md`.
- When you finish a task, run: `make lint test typecheck openapi-lint rls-check`. Do not report a task done if any of these fail.

## A.4 Stop conditions

Stop and ask a human when:
- a change would weaken an invariant in Part C.4;
- a rule needs a value that is `needs_expert` in the jurisdiction pack;
- a test can only pass by changing an assertion about money, tenancy, approval, or immutability;
- a provider (OCR, LLM, storage) would receive data outside the tenant's `data_residency_policy`.

---

# Part B — Product

## B.1 What AVENEL does

A fiduciaire sends AVENEL a client company's monthly documents (supplier and customer invoices, receipts, bank statements). AVENEL returns a review-ready accounting file: every document registered and read, proposed journal entries linked to their source, bank lines matched, problems listed, and an export the firm imports into its own accounting software after an accountant approves it.

The firm pays per completed monthly file. The firm's own software remains the legal set of books (Loi 9-88). AVENEL is the preparation layer, never the *livre-journal*.

## B.2 Users

| Role | Can do |
|---|---|
| Firm owner | Everything in the tenant, including members, billing, approval policy |
| Firm manager | Assign work, manage clients and periods, approve within limits |
| Accountant | Review proposals, resolve issues, approve if registered professional |
| Firm staff | Upload documents, prepare work, cannot approve |
| Client user | Upload documents and answer requests for their own company only |
| AVENEL operator | Read-only support access, time-limited, granted by the firm, audited |

Approval requires `approval.decide` **and** a stored professional registration (expert-comptable under Loi 15-89 or comptable agréé under Loi 127-12). The registration number is recorded on every approval.

## B.3 Pilot scope

In scope: secure intake, OCR and field extraction, document classification, duplicate detection, invoice compliance checks (CGI art. 145), TVA treatment proposals, journal proposals, bank statement import (PDF and CSV/XLSX), reconciliation proposals including TVA withheld at source, issues queue, client document requests, accountant approval, export to Sage 100 and Odoo, evidence pack, usage metering.

Out of scope: filing returns, paying anything, issuing e-invoices, payroll, final posting into the firm's software, any tax advice to end clients, countries other than Morocco, a public partner API, model training on customer data.

Behind a feature flag, off by default: SIMPL-TVA *relevé des déductions* XML generation (Phase 6).

---

# Part C — System architecture

## C.1 Shape

One modular monolith plus one worker process type. One PostgreSQL database. One object store. Nothing else until measured load requires it.

```
            Firm console (Next.js)        Client portal (same app, scoped routes)
                         \                      /
                          \                    /
                       API (FastAPI, Python 3.12)
                          |            |
                 PostgreSQL 16     Object storage (S3 API, encrypted, versioned)
                   |   ^
          job queue|   |results
                   v   |
                 Workers (Python, same codebase)
                   |
       Provider adapters: OCR · LLM · malware scan · email
```

## C.2 Stack

| Concern | Choice | Reason |
|---|---|---|
| Web | Vite + React 18 SPA (ADR-001), TypeScript strict, Tailwind with Part E tokens only | Decoupled REST API, static delivery via Nginx, zero Node.js SSR runtime attack surface |
| API | FastAPI, Pydantic v2, SQLAlchemy 2 Core (no ORM magic in domain code) | Typed contracts, explicit SQL |
| Database | PostgreSQL 16 with `pgcrypto`, `citext`, `btree_gist` | RLS, exclusion constraints, `NULLS NOT DISTINCT` |
| Jobs and workflow | Procrastinate (Postgres-backed) plus the explicit state machine in Part D | Transactional enqueue, one datastore, no extra service |
| Files | S3-compatible, bucket per environment, prefix per tenant, SSE-KMS, object versioning, object lock for originals | Immutability and retention |
| OCR | Adapter. Default local engine (docTR or PaddleOCR in a container) for `MA_ONLY` tenants. External provider only when the tenant policy allows | Data residency |
| LLM | Adapter with per-tenant routing (see C.6). Structured outputs validated against JSON Schema | Replaceable, auditable |
| Auth | OIDC provider (Keycloak self-hosted or a managed IdP with EU/MA region), MFA required for approvers | Standard, auditable |
| Observability | OpenTelemetry traces, structured JSON logs, Prometheus metrics | No content in logs |
| CI | GitHub Actions: lint, typecheck, tests, migration up/down, OpenAPI lint, RLS check, secret scan, dependency scan | Release gates |

Temporal, Kafka, Kubernetes, vector databases, and separate services per domain are explicitly not used in the pilot.

## C.3 Repository layout

```
/apps/web                 Next.js console and portal
/apps/api                 FastAPI app (routes only, thin)
/avenel                   Python domain package
  /tenancy  /clients  /periods  /documents  /extraction
  /accounting  /bank  /reconciliation  /issues  /approvals
  /exports  /evidence  /billing  /workflow  /providers
/jurisdiction/ma          Versioned rule pack (YAML) + loader + schema
/db/migrations            Numbered SQL migrations, forward and down
/contracts/openapi.yaml   API contract (OpenAPI 3.1), source of truth
/tests                    unit, integration, rls, golden, e2e
/fixtures                 Synthetic invoices, statements, provider recordings
/docs                     plans, ADRs, open-questions, runbooks
AGENTS.md                 Short pointer to this file; CLAUDE.md and .cursor/rules link to it
```

Dependency rule: `routes → domain services → repositories → db`. Domain modules never import from `apps/`. Providers are only called from `/avenel/providers` through interfaces.

## C.4 Invariants

These are enforced in the database where possible and tested in CI. Breaking one is a release blocker.

1. Every tenant-owned row has `tenant_id`, and every foreign key between tenant rows includes `tenant_id`.
2. Rows that belong to a client company carry `client_entity_id`, and child rows reference parents by `(tenant_id, client_entity_id, id)` so a row can never point to another company's period, document, or proposal.
3. Every journal proposal balances in MAD (Σ debit = Σ credit) with at least two lines, checked at commit by a deferred constraint trigger.
4. No line has both a debit and a credit, and no line is zero on both sides.
5. Lines of an approved, exported, or superseded proposal cannot change.
6. Document versions, evidence records, and audit events are append-only. Audit events are hash-chained per tenant.
7. An export can only be created from an approval whose `subject_hash` equals the current hash of the proposal set.
8. The person who prepared or last edited a proposal set cannot approve it (segregation of duties), unless the firm's policy explicitly allows single-person approval for that client, which is recorded on the approval.
9. Accounting periods for one client company never overlap. Chart-of-accounts entries for the same code never overlap in effective dates.
10. Document originals are retained at least 10 years after the end of the fiscal year they belong to (Loi 9-88 art. 22; CGI art. 211). Legal hold blocks deletion indefinitely.

## C.5 Tenancy and RLS

- The API resolves the user's membership from the OIDC subject, then opens a transaction and runs `SELECT set_config('app.tenant_id', :tenant, true)` and `set_config('app.user_id', :user, true)` (transaction-local, safe with PgBouncer transaction pooling).
- The app connects as `avenel_app`: not owner, not superuser, no `BYPASSRLS`. Migrations run as `avenel_owner`.
- Every tenant table has `ENABLE` and `FORCE ROW LEVEL SECURITY` and one policy using `app.current_tenant()`. If the setting is missing, the function returns NULL and every row is hidden.
- Client-user restriction to one company is enforced in the application (membership client scopes) and tested; it is not expressed in RLS.
- `make rls-check` queries `pg_class` and fails if any table with a `tenant_id` column lacks forced RLS or a policy.

## C.6 Data residency and providers

Each tenant has `data_residency_policy`:

| Policy | OCR | LLM | Object storage |
|---|---|---|---|
| `MA_ONLY` | Local container only | Local or Morocco-hosted model only; if none configured, extraction runs OCR + rules and every field goes to review | Morocco region |
| `EU_ALLOWED` | Local or EU endpoint | EU-region endpoints with zero-retention terms | Morocco or EU |
| `GLOBAL_ALLOWED` | Any approved | Any approved with zero-retention terms | Any approved |

The provider router refuses any call that violates the policy and raises an `integration` issue. Every external call writes a `provider_calls` row: provider, region, model, purpose, document hash, token and cost usage. No call sends ICE, IF, RIB, or person names unless the policy is `EU_ALLOWED` or wider and the field is needed for the task.

Under Loi 09-08, sending documents to a provider outside Morocco is a cross-border transfer requiring a CNDP declaration and, outside adequate countries, an authorization. The firm is the controller (*responsable du traitement*), AVENEL is the processor. The product ships a CNDP dossier generator (purposes, data categories, recipients, transfers, retention) per tenant. Default policy for new tenants: `MA_ONLY`.

---

# Part D — Domain, data, workflow

## D.1 Workflow state machine

Stored in `work_requests.status`; transitions only through `avenel.workflow.transition()`, which checks the guard, writes the new status, writes an audit event, and enqueues the next job in the same transaction.

```
draft ──submit──> intake ──docs verified──> extracting ──> preparing ──> reconciling
                                                                          │
                     ┌────────────────────────────────────────────────────┘
                     v
               quality_check ──blocking issues──> needs_attention ──resolved──┐
                     │                                                         │
                     └──no blocking issues──> awaiting_approval <──────────────┘
                                                 │           │
                                          approved│           │rejected (with reason)
                                                 v           v
                                             exporting    preparing (new revision)
                                                 │
                                                 v
                                   completed | completed_with_open_items

Any non-terminal state ──cancel──> cancelled      Any state ──unrecoverable──> failed
```

| Transition | Guard |
|---|---|
| draft → intake | Period is `open`, at least one document or bank statement attached, caller has `work.submit` |
| extracting → preparing | Every document is `read`, `needs_review`, or `rejected`; none `processing` |
| quality_check → awaiting_approval | Zero open issues with severity `blocking` |
| awaiting_approval → exporting | Approval `approved`, `subject_hash` matches current proposal set hash |
| exporting → completed | Export file generated, hash stored, downloaded or delivered |

Rules:
- Waiting for a client or an approver never times out into approval. Timeouts escalate to the firm manager.
- Each job is idempotent: keyed by `(work_request_id, step, revision)`. Retries use exponential backoff with jitter, max 4 attempts, then raise an `integration` issue.
- Reprocessing never mutates history; it creates a new proposal revision.

## D.2 Issues (exceptions)

One table, typed by `code`. Severity drives the workflow.

| Severity | Effect |
|---|---|
| `blocking` | Prevents approval |
| `review` | Must be acknowledged by an accountant before approval |
| `info` | Shown, no action required |

Seed codes (the agent adds codes only through the pack in `issues.yaml`):

`DOC_UNREADABLE`, `DOC_MALWARE`, `DOC_UNSUPPORTED_TYPE`, `DUPLICATE_EXACT`, `DUPLICATE_PROBABLE`, `INVOICE_MISSING_MANDATORY_FIELD`, `ICE_INVALID_FORMAT`, `ICE_CHECK_DIGIT_MISMATCH`, `TOTALS_INCONSISTENT`, `VAT_RATE_UNKNOWN`, `VAT_NOT_DEDUCTIBLE_CASH_LIMIT`, `VAT_NOT_DEDUCTIBLE_BY_NATURE`, `VAT_ON_AUTO_ENTREPRENEUR_INVOICE`, `ACCOUNT_UNMAPPED`, `ACCOUNT_LOW_CONFIDENCE`, `FX_RATE_MISSING`, `PERIOD_MISMATCH`, `BANK_BALANCE_BREAK`, `BANK_LINE_UNMATCHED`, `MATCH_AMOUNT_DIFFERENCE`, `RAS_EXPECTED_NOT_FOUND`, `MISSING_SUPPORTING_DOCUMENT`, `INTEGRATION_FAILURE`, `RULE_NEEDS_EXPERT`.

Each issue stores `evidence_refs` pointing to document regions or bank lines, and a resolution: `fixed`, `accepted_as_is` (with reason), `waived` (blocking issues cannot be waived by staff), or `sent_to_client`.

## D.3 Database schema — migration `001_core.sql`

This replaces v1. Write it exactly, then add `002_rls.sql` and `003_append_only.sql` below. Money is `numeric(18,2)`; FX rates are `numeric(18,8)`.

```sql
-- 001_core.sql  (run as avenel_owner)
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE SCHEMA IF NOT EXISTS app;

CREATE FUNCTION app.current_tenant() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.tenant_id', true), '')::uuid
$$;

CREATE FUNCTION app.current_user_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.user_id', true), '')::uuid
$$;

CREATE FUNCTION app.touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END $$;

-- Identity and tenancy -------------------------------------------------------

CREATE TABLE tenants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  legal_name text NOT NULL,
  display_name text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','closed')),
  data_residency_policy text NOT NULL DEFAULT 'MA_ONLY'
    CHECK (data_residency_policy IN ('MA_ONLY','EU_ALLOWED','GLOBAL_ALLOWED')),
  cndp_declaration_ref text,
  settings jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  identity_subject text NOT NULL UNIQUE,
  email citext NOT NULL UNIQUE,
  full_name text NOT NULL,
  locale text NOT NULL DEFAULT 'fr-MA' CHECK (locale IN ('fr-MA','ar-MA','en')),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('invited','active','disabled')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE memberships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  user_id uuid NOT NULL REFERENCES users(id),
  role text NOT NULL CHECK (role IN ('owner','manager','accountant','staff','client_user','operator')),
  professional_title text CHECK (professional_title IN ('expert_comptable','comptable_agree')),
  professional_registration_no text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('invited','active','revoked')),
  operator_access_expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, user_id),
  CHECK ((professional_title IS NULL) = (professional_registration_no IS NULL)),
  CHECK (role <> 'operator' OR operator_access_expires_at IS NOT NULL)
);

-- Client companies, periods, chart -------------------------------------------

CREATE TABLE client_entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  legal_name text NOT NULL,
  display_name text,
  ice char(15) CHECK (ice ~ '^[0-9]{15}$'),
  if_number text CHECK (if_number ~ '^[0-9]{1,10}$'),
  rc_number text,
  rc_city text,
  tp_number text,
  legal_form text,
  vat_regime text NOT NULL DEFAULT 'encaissement' CHECK (vat_regime IN ('encaissement','debit','not_liable')),
  vat_filing_frequency text NOT NULL DEFAULT 'quarterly' CHECK (vat_filing_frequency IN ('monthly','quarterly')),
  vat_prorata numeric(5,4) CHECK (vat_prorata BETWEEN 0 AND 1),
  is_auto_entrepreneur boolean NOT NULL DEFAULT false,
  functional_currency char(3) NOT NULL DEFAULT 'MAD' CHECK (functional_currency = 'MAD'),
  export_profile_id uuid,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','archived')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, ice)
);

CREATE TABLE membership_client_scopes (
  tenant_id uuid NOT NULL,
  membership_id uuid NOT NULL REFERENCES memberships(id),
  client_entity_id uuid NOT NULL,
  PRIMARY KEY (tenant_id, membership_id, client_entity_id),
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id)
);

CREATE TABLE accounting_periods (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  period_code text NOT NULL CHECK (period_code ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
  starts_on date NOT NULL,
  ends_on date NOT NULL,
  fiscal_year_end date NOT NULL,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_review','approved','closed')),
  jurisdiction_pack_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, period_code),
  CHECK (ends_on >= starts_on),
  EXCLUDE USING gist (
    tenant_id WITH =, client_entity_id WITH =,
    daterange(starts_on, ends_on, '[]') WITH &&)
);

CREATE TABLE chart_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  account_code text NOT NULL CHECK (account_code ~ '^[0-8][0-9]{3,}$'),
  external_code text,
  label text NOT NULL,
  cgnc_class smallint GENERATED ALWAYS AS (substr(account_code,1,1)::smallint) STORED,
  is_auxiliary_parent boolean NOT NULL DEFAULT false,
  effective_from date NOT NULL DEFAULT '1900-01-01',
  effective_to date,
  source text NOT NULL DEFAULT 'firm_import' CHECK (source IN ('firm_import','cgnc_seed','manual')),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  CHECK (effective_to IS NULL OR effective_to > effective_from),
  EXCLUDE USING gist (
    tenant_id WITH =, client_entity_id WITH =, account_code WITH =,
    daterange(effective_from, effective_to, '[)') WITH &&)
);

-- Global, non-tenant: jurisdiction pack tax codes (loaded from YAML, read-only to app)
CREATE TABLE jurisdiction_tax_codes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pack_code text NOT NULL DEFAULT 'MA',
  pack_version text NOT NULL,
  code text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('vat_rate','vat_exempt_with_credit','vat_exempt_no_credit','out_of_scope','withholding')),
  rate numeric(7,4),
  effective_from date NOT NULL,
  effective_to date,
  source_ref text NOT NULL,
  status text NOT NULL CHECK (status IN ('verified','needs_expert')),
  UNIQUE (pack_code, pack_version, code, effective_from)
);

CREATE TABLE client_tax_mappings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  tax_code text NOT NULL,
  direction text NOT NULL CHECK (direction IN ('purchase','sale','fixed_asset','withholding')),
  account_id uuid NOT NULL,
  approved_by uuid REFERENCES users(id),
  approved_at timestamptz,
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, account_id) REFERENCES chart_accounts(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, tax_code, direction)
);

CREATE TABLE counterparties (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  kind text NOT NULL CHECK (kind IN ('supplier','customer','both','bank','state')),
  legal_name text NOT NULL,
  ice char(15) CHECK (ice ~ '^[0-9]{15}$'),
  if_number text,
  rc_number text,
  is_auto_entrepreneur boolean NOT NULL DEFAULT false,
  tax_compliance_certificate_valid_until date,
  default_account_id uuid,
  auxiliary_code text,
  verified_at timestamptz,
  verification_source text,
  aliases text[] NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, default_account_id) REFERENCES chart_accounts(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, client_entity_id, ice, legal_name)
);

-- Work --------------------------------------------------------------------------

CREATE TABLE work_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  accounting_period_id uuid NOT NULL,
  service_code text NOT NULL CHECK (service_code = 'monthly_bookkeeping'),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN (
    'draft','intake','extracting','preparing','reconciling','quality_check',
    'needs_attention','awaiting_approval','exporting','completed',
    'completed_with_open_items','cancelled','failed')),
  current_revision integer NOT NULL DEFAULT 1,
  assigned_to uuid REFERENCES users(id),
  requested_by uuid REFERENCES users(id),
  due_at timestamptz,
  submitted_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, accounting_period_id)
    REFERENCES accounting_periods(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, id)
);
CREATE UNIQUE INDEX work_requests_one_active_per_period
  ON work_requests (tenant_id, accounting_period_id)
  WHERE status NOT IN ('cancelled','failed');
CREATE INDEX work_requests_queue ON work_requests (tenant_id, status, due_at);

-- Documents ----------------------------------------------------------------------

CREATE TABLE documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid,
  doc_type text CHECK (doc_type IN (
    'purchase_invoice','sales_invoice','credit_note','receipt','bank_statement',
    'expense_note','customs_document','other')),
  status text NOT NULL DEFAULT 'received' CHECK (status IN (
    'received','quarantined','processing','read','needs_review','rejected')),
  original_filename text NOT NULL,
  source_channel text NOT NULL CHECK (source_channel IN ('console','portal','email','api')),
  uploaded_by uuid REFERENCES users(id),
  fiscal_year_end date,
  retain_until date,
  legal_hold boolean NOT NULL DEFAULT false,
  received_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id)
    REFERENCES work_requests(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, id)
);
CREATE INDEX documents_by_work ON documents (tenant_id, work_request_id);

CREATE TABLE document_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  document_id uuid NOT NULL,
  version_number integer NOT NULL CHECK (version_number > 0),
  object_key text NOT NULL,
  sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  mime_type text NOT NULL CHECK (mime_type IN (
    'application/pdf','image/jpeg','image/png','image/heic','image/tiff',
    'text/csv','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/xml')),
  byte_size bigint NOT NULL CHECK (byte_size > 0 AND byte_size <= 52428800),
  page_count integer,
  malware_scan text NOT NULL DEFAULT 'pending' CHECK (malware_scan IN ('pending','clean','infected','error')),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, document_id)
    REFERENCES documents(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, document_id, version_number),
  UNIQUE (tenant_id, client_entity_id, sha256),   -- exact duplicate is detected at upload
  UNIQUE (tenant_id, id)
);

CREATE TABLE extractions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  document_version_id uuid NOT NULL,
  schema_version text NOT NULL,
  engine text NOT NULL,
  engine_version text NOT NULL,
  provider_call_id uuid,
  status text NOT NULL CHECK (status IN ('succeeded','partial','failed')),
  fields jsonb NOT NULL,            -- {field: {value, confidence, page, bbox:[x0,y0,x1,y1]}}
  validation jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, document_version_id) REFERENCES document_versions(tenant_id, id),
  UNIQUE (tenant_id, id)
);

-- Accounting proposals ------------------------------------------------------------

CREATE TABLE journal_proposals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid NOT NULL,
  revision integer NOT NULL,
  journal_code text NOT NULL CHECK (journal_code ~ '^[A-Z0-9]{2,6}$'),
  entry_date date NOT NULL,
  label text NOT NULL,
  source_document_id uuid,
  source_bank_transaction_id uuid,
  status text NOT NULL DEFAULT 'proposed' CHECK (status IN (
    'proposed','edited','approved','exported','superseded','rejected')),
  supersedes_id uuid,
  reversal_of_id uuid,
  rule_refs text[] NOT NULL DEFAULT '{}',     -- jurisdiction pack keys used
  proposed_by text NOT NULL CHECK (proposed_by IN ('rules','agent','human')),
  agent_run_id uuid,
  last_edited_by uuid REFERENCES users(id),
  content_hash char(64),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id)
    REFERENCES work_requests(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, source_document_id)
    REFERENCES documents(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, id)
);
CREATE INDEX journal_proposals_by_work ON journal_proposals (tenant_id, work_request_id, revision);

CREATE TABLE journal_lines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  journal_proposal_id uuid NOT NULL,
  line_no integer NOT NULL CHECK (line_no > 0),
  account_id uuid NOT NULL,
  account_code text NOT NULL,              -- snapshot for export and audit
  counterparty_id uuid,
  label text NOT NULL,
  currency char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  debit_tx numeric(18,2) NOT NULL DEFAULT 0 CHECK (debit_tx >= 0),
  credit_tx numeric(18,2) NOT NULL DEFAULT 0 CHECK (credit_tx >= 0),
  fx_rate numeric(18,8) NOT NULL DEFAULT 1 CHECK (fx_rate > 0),
  fx_rate_date date,
  fx_source text,
  debit_mad numeric(18,2) NOT NULL DEFAULT 0 CHECK (debit_mad >= 0),
  credit_mad numeric(18,2) NOT NULL DEFAULT 0 CHECK (credit_mad >= 0),
  tax_code text,
  due_date date,
  evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  FOREIGN KEY (tenant_id, client_entity_id, journal_proposal_id)
    REFERENCES journal_proposals(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, account_id)
    REFERENCES chart_accounts(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, counterparty_id)
    REFERENCES counterparties(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, journal_proposal_id, line_no),
  CHECK ((debit_mad > 0) <> (credit_mad > 0)),
  CHECK ((debit_tx > 0) <> (credit_tx > 0)),
  CHECK ((debit_tx > 0) = (debit_mad > 0)),
  CHECK (currency = 'MAD' OR (fx_rate_date IS NOT NULL AND fx_source IS NOT NULL)),
  CHECK (currency <> 'MAD' OR fx_rate = 1)
);

CREATE FUNCTION app.assert_proposal_balanced() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_tenant uuid := coalesce(NEW.tenant_id, OLD.tenant_id);
  v_prop   uuid := coalesce(NEW.journal_proposal_id, OLD.journal_proposal_id);
  v_d numeric; v_c numeric; v_n int;
BEGIN
  SELECT coalesce(sum(debit_mad),0), coalesce(sum(credit_mad),0), count(*)
    INTO v_d, v_c, v_n
    FROM journal_lines WHERE tenant_id = v_tenant AND journal_proposal_id = v_prop;
  IF v_n = 0 THEN
    RAISE EXCEPTION 'proposal % has no lines', v_prop USING ERRCODE = '23514';
  END IF;
  IF v_n < 2 OR v_d <> v_c THEN
    RAISE EXCEPTION 'proposal % unbalanced: lines=%, debit=%, credit=%', v_prop, v_n, v_d, v_c
      USING ERRCODE = '23514';
  END IF;
  RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER journal_lines_balanced
  AFTER INSERT OR UPDATE OR DELETE ON journal_lines
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION app.assert_proposal_balanced();

CREATE FUNCTION app.forbid_frozen_line_change() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_status text;
BEGIN
  SELECT status INTO v_status FROM journal_proposals
   WHERE tenant_id = coalesce(NEW.tenant_id, OLD.tenant_id)
     AND id = coalesce(NEW.journal_proposal_id, OLD.journal_proposal_id);
  IF v_status IN ('approved','exported','superseded') THEN
    RAISE EXCEPTION 'lines of a % proposal are immutable', v_status USING ERRCODE = '42501';
  END IF;
  IF TG_OP = 'UPDATE' AND NEW.journal_proposal_id <> OLD.journal_proposal_id THEN
    RAISE EXCEPTION 'cannot move a line to another proposal' USING ERRCODE = '42501';
  END IF;
  RETURN coalesce(NEW, OLD);
END $$;

CREATE TRIGGER journal_lines_frozen
  BEFORE UPDATE OR DELETE ON journal_lines
  FOR EACH ROW EXECUTE FUNCTION app.forbid_frozen_line_change();

-- Bank ---------------------------------------------------------------------------

CREATE TABLE bank_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  bank_code char(3) NOT NULL,
  rib_last4 char(4) NOT NULL,
  rib_encrypted bytea NOT NULL,              -- pgp_sym_encrypt with KMS-managed key
  rib_sha256 char(64) NOT NULL,
  currency char(3) NOT NULL DEFAULT 'MAD',
  ledger_account_id uuid NOT NULL,           -- 5141x
  journal_code text NOT NULL,
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, ledger_account_id)
    REFERENCES chart_accounts(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, rib_sha256)
);

CREATE TABLE bank_statements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  bank_account_id uuid NOT NULL,
  document_id uuid NOT NULL,
  period_start date NOT NULL,
  period_end date NOT NULL,
  opening_balance numeric(18,2) NOT NULL,
  closing_balance numeric(18,2) NOT NULL,
  balance_check text NOT NULL CHECK (balance_check IN ('ok','break','unknown')),
  FOREIGN KEY (tenant_id, client_entity_id, bank_account_id)
    REFERENCES bank_accounts(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, document_id)
    REFERENCES documents(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id)
);

CREATE TABLE bank_transactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  bank_account_id uuid NOT NULL,
  bank_statement_id uuid NOT NULL,
  line_index integer NOT NULL,
  booking_date date NOT NULL,
  value_date date,
  amount numeric(18,2) NOT NULL CHECK (amount <> 0),  -- signed: + credit to account
  currency char(3) NOT NULL,
  description text NOT NULL,
  external_reference text,
  source_hash char(64) NOT NULL,             -- sha256(account|booking|value|amount|desc|line_index|statement)
  evidence_ref jsonb NOT NULL,
  FOREIGN KEY (tenant_id, client_entity_id, bank_account_id)
    REFERENCES bank_accounts(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, bank_statement_id)
    REFERENCES bank_statements(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, bank_account_id, source_hash)
);
CREATE UNIQUE INDEX bank_tx_ext_ref ON bank_transactions (tenant_id, bank_account_id, external_reference)
  WHERE external_reference IS NOT NULL;

ALTER TABLE journal_proposals
  ADD FOREIGN KEY (tenant_id, client_entity_id, source_bank_transaction_id)
  REFERENCES bank_transactions(tenant_id, client_entity_id, id);

CREATE TABLE reconciliation_matches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','accepted','rejected','superseded')),
  score numeric(5,4) CHECK (score BETWEEN 0 AND 1),
  reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  difference_mad numeric(18,2) NOT NULL DEFAULT 0,
  difference_kind text CHECK (difference_kind IN ('vat_withheld','bank_fee','fx','rounding','unexplained')),
  decided_by uuid REFERENCES users(id),
  decided_at timestamptz,
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id)
    REFERENCES work_requests(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id)
);

CREATE TABLE reconciliation_match_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  match_id uuid NOT NULL,
  bank_transaction_id uuid,
  journal_proposal_id uuid,
  document_id uuid,
  amount_mad numeric(18,2) NOT NULL,
  FOREIGN KEY (tenant_id, client_entity_id, match_id) REFERENCES reconciliation_matches(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, bank_transaction_id) REFERENCES bank_transactions(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, journal_proposal_id) REFERENCES journal_proposals(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, document_id) REFERENCES documents(tenant_id, client_entity_id, id),
  CHECK (num_nonnulls(bank_transaction_id, journal_proposal_id, document_id) = 1)
);
CREATE UNIQUE INDEX one_accepted_match_per_bank_line
  ON reconciliation_match_items (tenant_id, bank_transaction_id)
  WHERE bank_transaction_id IS NOT NULL;   -- enforced together with status in service + test

-- Issues, approvals, exports -------------------------------------------------------

CREATE TABLE issues (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid NOT NULL,
  code text NOT NULL,
  severity text NOT NULL CHECK (severity IN ('blocking','review','info')),
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','assigned','waiting_client','resolved','waived')),
  resolution text CHECK (resolution IN ('fixed','accepted_as_is','waived','sent_to_client')),
  resolution_note text,
  evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  subject_document_id uuid,
  subject_proposal_id uuid,
  subject_bank_transaction_id uuid,
  assigned_to uuid REFERENCES users(id),
  resolved_by uuid REFERENCES users(id),
  resolved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id) REFERENCES work_requests(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, subject_document_id) REFERENCES documents(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, subject_proposal_id) REFERENCES journal_proposals(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, subject_bank_transaction_id) REFERENCES bank_transactions(tenant_id, client_entity_id, id),
  CHECK ((status IN ('resolved','waived')) = (resolved_at IS NOT NULL)),
  CHECK (NOT (severity = 'blocking' AND resolution = 'accepted_as_is'))
);
CREATE INDEX issues_open ON issues (tenant_id, work_request_id) WHERE status NOT IN ('resolved','waived');

CREATE TABLE approvals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid NOT NULL,
  revision integer NOT NULL,
  subject_hash char(64) NOT NULL,           -- hash of ordered proposals + lines + accepted matches
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','cancelled')),
  prepared_by uuid REFERENCES users(id),
  decided_by uuid REFERENCES users(id),
  decider_professional_title text,
  decider_registration_no text,
  single_person_policy boolean NOT NULL DEFAULT false,
  reason text,
  decided_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id) REFERENCES work_requests(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, id),
  CHECK (status = 'pending' OR (decided_by IS NOT NULL AND decided_at IS NOT NULL AND reason IS NOT NULL)),
  CHECK (status <> 'approved' OR decider_registration_no IS NOT NULL),
  CHECK (single_person_policy OR decided_by IS NULL OR prepared_by IS NULL OR decided_by <> prepared_by)
);

CREATE TABLE export_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  name text NOT NULL,
  target text NOT NULL CHECK (target IN ('sage100_csv','sage100_pnm','odoo_csv')),
  encoding text NOT NULL DEFAULT 'cp1252' CHECK (encoding IN ('cp1252','utf-8')),
  config jsonb NOT NULL,                     -- delimiter, decimal, date format, column map, padding
  verified_round_trip_at timestamptz,
  UNIQUE (tenant_id, id)
);

CREATE TABLE exports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid NOT NULL,
  approval_id uuid NOT NULL,
  export_profile_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'preparing' CHECK (status IN ('preparing','ready','downloaded','failed')),
  object_key text,
  file_sha256 char(64),
  evidence_pack_key text,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id) REFERENCES work_requests(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, approval_id) REFERENCES approvals(tenant_id, id),
  FOREIGN KEY (tenant_id, export_profile_id) REFERENCES export_profiles(tenant_id, id)
);

-- Operations ---------------------------------------------------------------------

CREATE TABLE provider_calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  provider text NOT NULL,
  region text NOT NULL,
  model text,
  purpose text NOT NULL,
  input_sha256 char(64) NOT NULL,
  usage jsonb NOT NULL DEFAULT '{}'::jsonb,
  cost_mad numeric(18,6),
  status text NOT NULL CHECK (status IN ('succeeded','failed','refused_by_policy')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE agent_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  work_request_id uuid NOT NULL,
  task text NOT NULL,
  agent_version text NOT NULL,
  prompt_version text NOT NULL,
  input_refs jsonb NOT NULL,
  output jsonb,
  schema_valid boolean NOT NULL,
  provider_call_id uuid REFERENCES provider_calls(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, work_request_id) REFERENCES work_requests(tenant_id, id)
);

CREATE TABLE idempotency_keys (
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  key text NOT NULL CHECK (length(key) BETWEEN 8 AND 200),
  method text NOT NULL,
  path text NOT NULL,
  request_sha256 char(64) NOT NULL,
  status text NOT NULL CHECK (status IN ('in_progress','completed')),
  response_code integer,
  response_body jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, key)
);

CREATE TABLE usage_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid NOT NULL,
  unit text NOT NULL CHECK (unit IN ('monthly_file','extra_document','client_request')),
  quantity numeric(18,4) NOT NULL CHECK (quantity > 0),
  price_version text NOT NULL,
  billable boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id) REFERENCES work_requests(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, work_request_id, unit)
);

CREATE TABLE evidence_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  work_request_id uuid NOT NULL,
  subject_type text NOT NULL CHECK (subject_type IN ('document','extraction','proposal','line','match','issue','approval','export')),
  subject_id uuid NOT NULL,
  kind text NOT NULL,
  payload jsonb NOT NULL,
  content_sha256 char(64) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, work_request_id) REFERENCES work_requests(tenant_id, id)
);

CREATE TABLE audit_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  actor_type text NOT NULL CHECK (actor_type IN ('user','system','agent','operator')),
  actor_id text,
  action text NOT NULL,
  resource_type text NOT NULL,
  resource_id text,
  request_id text,
  data jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  prev_hash char(64),
  row_hash char(64) NOT NULL
);
CREATE INDEX audit_events_tenant_time ON audit_events (tenant_id, occurred_at DESC);

-- updated_at triggers
CREATE TRIGGER t_tenants_touch BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
CREATE TRIGGER t_users_touch BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
CREATE TRIGGER t_clients_touch BEFORE UPDATE ON client_entities FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
CREATE TRIGGER t_work_touch BEFORE UPDATE ON work_requests FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
```

```sql
-- 002_rls.sql  (run as avenel_owner)
DO $$
DECLARE t text;
BEGIN
  FOR t IN
    SELECT c.relname FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id'
    WHERE n.nspname = 'public' AND c.relkind = 'r'
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'CREATE POLICY %I ON %I USING (tenant_id = app.current_tenant()) WITH CHECK (tenant_id = app.current_tenant())',
      t || '_tenant', t);
  END LOOP;
END $$;

-- tenants: a session sees only its own tenant row
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY tenants_self ON tenants USING (id = app.current_tenant());

GRANT USAGE ON SCHEMA public, app TO avenel_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO avenel_app;
GRANT SELECT ON jurisdiction_tax_codes TO avenel_app;
REVOKE INSERT, UPDATE, DELETE ON jurisdiction_tax_codes FROM avenel_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO avenel_app;
-- DELETE is granted per table only where the domain needs it (draft lines, idempotency cleanup):
GRANT DELETE ON journal_lines, idempotency_keys TO avenel_app;
```

Membership resolution happens before tenant context exists. It runs through a `SECURITY DEFINER` function `app.resolve_membership(subject text)` owned by `avenel_owner`, returning only `(tenant_id, membership_id, role, client_scope_ids)` for that subject. No other cross-tenant read path exists.

```sql
-- 003_append_only.sql  (run as avenel_owner)
CREATE FUNCTION app.forbid_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = '42501';
END $$;

CREATE TRIGGER audit_no_mutation BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
CREATE TRIGGER evidence_no_mutation BEFORE UPDATE OR DELETE ON evidence_records
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
CREATE TRIGGER docver_no_mutation BEFORE UPDATE OR DELETE ON document_versions
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
CREATE TRIGGER extraction_no_mutation BEFORE UPDATE OR DELETE ON extractions
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
-- malware_scan result is recorded as a new evidence row, not by updating document_versions.

REVOKE UPDATE, DELETE, TRUNCATE ON audit_events, evidence_records, document_versions, extractions FROM avenel_app;

CREATE FUNCTION app.chain_audit() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_prev char(64);
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.tenant_id::text, 0));
  SELECT row_hash INTO v_prev FROM audit_events
   WHERE tenant_id = NEW.tenant_id ORDER BY id DESC LIMIT 1;
  NEW.prev_hash := v_prev;
  NEW.row_hash := encode(digest(
    coalesce(v_prev,'') || NEW.tenant_id::text || NEW.actor_type || coalesce(NEW.actor_id,'') ||
    NEW.action || NEW.resource_type || coalesce(NEW.resource_id,'') ||
    NEW.data::text || NEW.occurred_at::text, 'sha256'), 'hex');
  RETURN NEW;
END $$;

CREATE TRIGGER audit_chain BEFORE INSERT ON audit_events
  FOR EACH ROW EXECUTE FUNCTION app.chain_audit();
```

A daily job writes a signed digest of each tenant's latest `row_hash` to a separate write-once bucket. `make audit-verify` recomputes the chain.

Note on the malware result: because `document_versions` is append-only, scan status lives in `evidence_records` (`kind = 'malware_scan'`) and a view `document_versions_current` joins the latest result. Remove the `malware_scan` column from `document_versions` if you implement it this way; do not leave two sources of truth.

## D.4 Proposal set hash

`subject_hash = sha256(canonical_json(sorted proposals of the revision, each with sorted lines, plus accepted matches))`. Canonical JSON: sorted keys, no whitespace, decimals as strings with two places, dates ISO-8601. Implemented once in `avenel/approvals/hashing.py`, used by approval creation and export guard, covered by golden tests.

## D.5 Jurisdiction pack

Directory `/jurisdiction/ma/`, version string `MA-YYYY.MM.N`. Loaded at startup, validated against `pack.schema.json`, and copied into `jurisdiction_tax_codes`. Each period pins the pack version it was opened with.

Every rule entry has this shape:

```yaml
key: vat.rate.standard
value: 0.20
effective_from: 2026-01-01
effective_to: null
source: "CGI art. 99-A"
status: verified            # verified | needs_expert
note: ""
```

Seed content (status as of 30 October 2026; every `needs_expert` entry is disabled in rule evaluation and surfaces as `RULE_NEEDS_EXPERT` when hit):

| File | Contents | Status |
|---|---|---|
| `vat_rates.yaml` | 20% standard, 10% reduced from 2026-01-01; historical 7% and 14% with `effective_to`; transition steps for affected items | Rates verified; item-to-rate mapping `needs_expert` |
| `vat_deduction.yaml` | Exclusions by nature (CGI art. 106-I); cash payment limit 5,000 MAD per day per supplier and 50,000 MAD per month per supplier (art. 106-II), with admitted payment methods | Limits verified; HT vs TTC basis `needs_expert` (apply TTC, conservative) |
| `vat_filing.yaml` | Monthly if prior-year turnover ≥ 1,000,000 MAD, else quarterly; deadline expression | Threshold verified; deadline wording `needs_expert` |
| `vat_withholding.yaml` | RAS TVA (art. 117): 100% on goods/works suppliers without a valid tax compliance certificate; 75%/100% on listed services; LF 2026 extension with staged payer turnover thresholds (500 MDH from 2026-07-01, 350 MDH from 2027-01-01, 200 MDH from 2028-01-01) | Structure verified; staged thresholds and service lists `needs_expert` (primary circular not verified) |
| `invoice_mentions.yaml` | CGI art. 145-III mandatory fields, seller and buyer side | Verified |
| `identifiers.yaml` | ICE: 15 digits; check-digit rule as a *warning only*. RIB: 24 digits, mod-97 key. IF/TP/RC permissive formats | ICE key `needs_expert`; RIB verified |
| `cgnc_seed.yaml` | Classes 0–8 and seed accounts: 2xxx, 3421, 3455/34551/34552, 3456, 4411, 4415, 4417, 4455, 4456, 4481, 5141, 5161, 6111, 7111 | Verified; activity sub-accounts and RAS account `needs_expert` |
| `journals.yaml` | ACH, VTE, BQn, CAI, OD, AN | Verified as convention; firm overrides allowed |
| `retention.yaml` | 10 years after fiscal year end | Verified |
| `einvoicing.yaml` | `enabled: false`. Fields reserved: UBL XML, signature status, DGI clearance id. No dates | No decree published; all `needs_expert` |
| `issues.yaml` | Issue codes, default severity, French and English labels | Product-owned |

Do not copy e-invoicing phase dates from blogs. As of 30 October 2026 no implementing decree has been published.

## D.6 Deterministic validation (runs after every extraction and every edit)

Invoice:
- All mandatory mentions present (from pack); missing → `INVOICE_MISSING_MANDATORY_FIELD`, severity `review` for purchases (deductibility at risk), `info` for sales prepared by the client.
- Per-rate arithmetic: Σ line HT = HT per rate; HT × rate = TVA (tolerance 0.01 MAD per rate, configurable); Σ = TTC. Failure → `TOTALS_INCONSISTENT` blocking.
- Rate not in pack for the invoice date → `VAT_RATE_UNKNOWN` blocking.
- Supplier flagged auto-entrepreneur and TVA > 0 → `VAT_ON_AUTO_ENTREPRENEUR_INVOICE` review.
- Paid in cash (from bank evidence or invoice mention) above the pack limits → TVA moved to non-deductible, `VAT_NOT_DEDUCTIBLE_CASH_LIMIT` review.
- Invoice date outside the period → `PERIOD_MISMATCH` review.

Proposal:
- Balanced in MAD (database also enforces).
- Every account exists and is effective on `entry_date` for the client.
- Every non-MAD line has a rate, date, and source. FX differences on rounding are posted to an explicit rounding line, never absorbed.
- Every line has at least one evidence reference.
- No two active proposals for the same source document without a supersede link.

Bank:
- Opening + Σ movements = closing per statement; otherwise `BANK_BALANCE_BREAK` blocking.
- RIB key valid; account matches a known `bank_accounts` row.

## D.7 Reconciliation

Candidates are generated deterministically (amount, date window, counterparty, reference tokens), then scored. The LLM may write a one-sentence explanation of a candidate; it never chooses the match.

- Exact single match with score ≥ the tenant threshold (default 0.97) is pre-selected, still reviewable.
- Receipts lower than the invoice TTC by an amount equal to 75% or 100% of the invoice TVA are proposed as matches with `difference_kind = 'vat_withheld'`, plus a proposed entry to the withholding receivable account from the client's tax mapping. If no mapping exists → `ACCOUNT_UNMAPPED` blocking.
- Split and grouped payments are supported through `reconciliation_match_items`.
- Unmatched bank lines at quality check → `BANK_LINE_UNMATCHED` review.

## D.8 AI agents

Each agent is a function with a JSON Schema input and output, a versioned prompt in `/avenel/extraction/prompts/` or `/avenel/accounting/prompts/`, and a recorded `agent_runs` row.

| Agent | Input | Output | Never does |
|---|---|---|---|
| Classifier | Page images or OCR text | `doc_type`, language, page roles, confidence | Reject a document |
| Extractor | OCR layout + images | Fields with value, confidence, page, bbox | Compute totals it cannot see |
| Account suggester | Extracted invoice, client chart, last 12 months of approved entries for this supplier | Ranked account candidates with reasons | Create accounts, choose tax treatment |
| Match explainer | Bank line + candidate | One sentence | Accept or reject a match |

Rules:
- Output that fails schema validation is retried once with the validation error, then the document goes to `needs_review`.
- Confidence below the pack threshold for a critical field (ICE, invoice number, date, totals, rates) → field shown to the accountant as unconfirmed.
- Prompts contain no instructions taken from documents. Document text is passed as data inside delimiters, and output schemas do not allow free-form actions.
- Agents never call tools that write. Writes happen in deterministic services after validation.

---

# Part D2 — API

Contract file: `/contracts/openapi.yaml`, OpenAPI **3.1.0**. Generated TypeScript client for the web app. Spectral lint in CI with these custom rules: every operation has `operationId` and tags; every `POST`/`PATCH`/`DELETE` declares a required `Idempotency-Key` header; nullability uses `type: [X, "null"]` (the 3.0 `nullable` keyword fails lint); all errors return `application/problem+json` (RFC 9457) with `type`, `title`, `status`, `detail`, `instance`, `request_id`, and `errors[]` for field errors.

Conventions: `/v1` prefix; cursor pagination (`cursor`, `limit` ≤ 100, response `next_cursor`); amounts as decimal strings (`"1250.00"`); dates ISO-8601; tenant never in path or body; `404` for resources outside the caller's scope (never `403`, to avoid existence leaks); `409` for state conflicts; `422` for an idempotency key reused with a different body.

Endpoints (all tenant-scoped, all mutating ones idempotent):

| Area | Endpoints |
|---|---|
| Session | `GET /me` |
| Clients | `GET/POST /client-entities`, `GET/PATCH /client-entities/{id}` |
| Chart | `POST /client-entities/{id}/chart-imports` (CSV/XLSX), `GET /client-entities/{id}/accounts` |
| Tax mapping | `GET/PUT /client-entities/{id}/tax-mappings` |
| Counterparties | `GET /client-entities/{id}/counterparties`, `PATCH /counterparties/{id}` |
| Bank accounts | `GET/POST /client-entities/{id}/bank-accounts` |
| Periods | `GET/POST /accounting-periods`, `GET /accounting-periods/{id}` |
| Work | `GET/POST /work-requests`, `GET /work-requests/{id}`, `POST /work-requests/{id}:submit`, `POST /work-requests/{id}:cancel`, `GET /work-requests/{id}/timeline` |
| Documents | `POST /work-requests/{id}/uploads` (returns presigned PUT), `POST /documents/{id}:complete-upload`, `GET /work-requests/{id}/documents`, `GET /documents/{id}`, `GET /documents/{id}/pages/{n}` (signed image URL), `GET /documents/{id}/extraction`, `PATCH /documents/{id}/extraction` (field corrections, creates evidence) |
| Proposals | `GET /work-requests/{id}/proposals?revision=`, `GET /proposals/{id}`, `PUT /proposals/{id}/lines` (replace lines; creates an `edited` proposal superseding the old one) |
| Reconciliation | `GET /work-requests/{id}/matches`, `POST /matches/{id}:accept`, `POST /matches/{id}:reject`, `POST /work-requests/{id}/matches` (manual match) |
| Issues | `GET /work-requests/{id}/issues`, `POST /issues/{id}:assign`, `POST /issues/{id}:resolve`, `POST /issues/{id}:send-to-client` |
| Client requests | `GET /portal/requests`, `POST /portal/requests/{id}:answer` (client users) |
| Approvals | `GET /approvals?status=pending`, `POST /work-requests/{id}/approvals` (request; returns `subject_hash`), `POST /approvals/{id}:decide` (body includes `subject_hash`; mismatch → 409) |
| Exports | `POST /work-requests/{id}/exports`, `GET /exports/{id}`, `GET /exports/{id}/file`, `GET /exports/{id}/evidence-pack` |
| Audit | `GET /work-requests/{id}/audit-events` |
| Compliance | `GET /tenant/cndp-dossier` |

---

# Part E — Design system

## E.1 Direction

AVENEL is a working tool for accountants who review hundreds of lines a day. The interface is calm, dense, and exact. One thing is memorable: **every number is tied to the place it came from.** Select an amount and its region lights up on the source document beside it. Everything else stays quiet.

The brand palette is sky blue, near-white, and hot pink. Sky blue means "AVENEL did this and you can act on it." Hot pink means one thing only: **a person needs to look here.** It is never decoration.

## E.2 Color tokens

Brand colors as given, plus the minimum derived values needed for accessible text and structure. Contrast ratios are against `--paper` (#FCFFFF).

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `--sky` | `#0593C6` | Primary fills, selected states, focus ring, evidence highlight stroke, brand mark | 3.48 (non-text and large text only) |
| `--sky-ink` | `#047AA5` | Sky-colored text and links at body size | 4.82 |
| `--sky-wash` | `#E3F3F9` | Selected row background, evidence highlight fill (with 40% opacity on documents) | — |
| `--pink` | `#D83995` | "Needs a person" markers: 3px left rule on rows, 8px dot, badge outline | 4.23 (large text and markers only) |
| `--pink-ink` | `#B82A7C` | Pink text at body size (issue titles, counts waiting on you) | 5.71 |
| `--pink-wash` | `#FBE8F2` | Background of an open blocking issue panel | — |
| `--paper` | `#FCFFFF` | Page background | — |
| `--surface` | `#F2F7F9` | Side panels, table header, document viewer frame | — |
| `--line` | `#D7E3E8` | Hairlines, table borders, input borders | — |
| `--ink` | `#0A2533` | Primary text, figures | 15.76 |
| `--ink-2` | `#4A6573` | Secondary text, labels | 6.14 |
| `--ok` | `#1F7A4D` | Balanced, matched, approved (text and icons only) | 5.29 |
| `--fail` | `#B4232C` | System failures, destructive confirmations only | 6.49 |

Rules:
- Primary buttons: `--sky` fill with `--ink` text (4.52:1). Never white text on `--sky` or `--pink`; both fail contrast.
- Status is never color alone. Every colored marker has a word or icon with it.
- Pink and red are different meanings. Pink: waiting on a human (review, approval, client answer). Red: something broke or will be destroyed.
- No gradients, blur, glass, or tinted shadows in the product. The marketing site may use one flat sky-to-pink field in the hero; the console never does.
- Dark mode: not in the pilot.

## E.3 Typography

- **Readex Pro** (variable, Latin and Arabic in one family) for headings and the brand. Used at 600 weight, slightly expanded width when available. Headings are short nouns, not slogans.
- **IBM Plex Sans** with **IBM Plex Sans Arabic** for interface and body text. All figures use `font-variant-numeric: tabular-nums lining-nums`. Amounts are right-aligned, two decimals, French formatting (`12 450,00`), currency code in the column header, not repeated per cell.
- Scale (rem, base 16px): 0.8125 (table meta), 0.875 (table body, labels), 1 (body), 1.25 (panel titles), 1.75 (page titles). Line height 1.45 body, 1.2 headings. Line length ≤ 75 characters for prose.
- No all-caps labels, no letter-spaced eyebrows, no italic or colored single-word emphasis in headings.
- Arabic UI (later phase) uses `dir="rtl"` at the page level; tables keep numbers left-to-right.

## E.4 Space, shape, depth

- 4px base grid. Table rows 36px (compact) or 44px (comfortable, user setting).
- Radius by role: inputs and table cells 2px, panels 6px, status pills fully rounded. Nothing else is rounded.
- Depth by surface color and hairlines. Shadow only on floating layers (menus, dialogs): `0 8px 24px rgba(10,37,51,0.14)`.
- Icons: Lucide, 16px in tables, 20px in navigation, 1.5px stroke. No emoji. No sparkle or magic-wand icons for AI features.

## E.5 Layout

Persistent left rail (220px): firm switcher, Queue, Clients, Approvals (count in `--pink-ink` when > 0), Settings. Content is left-aligned. No centered marketing layouts inside the product.

**Queue** (home). A table, not cards: one row per client company for the selected month.

```
 Septembre 2026 ▾                                         [ Nouveau dossier ]
 ┌───────────────────────┬──────────┬───────────┬──────────┬────────┬──────────┐
 │ Société               │ Pièces   │ État      │ Anomalies│ Échéance│ Assigné  │
 ├───────────────────────┼──────────┼───────────┼──────────┼────────┼──────────┤
▌│ Atlas Distribution    │ 142      │ À valider │ 3        │ 10 oct │ S. Alami │  ← pink rule: waiting on a person
 │ Riad Menara SARL      │ 87       │ Lecture   │ —        │ 12 oct │ —        │
 └───────────────────────┴──────────┴───────────┴──────────┴────────┴──────────┘
```

**Review** (the core screen). Split view, document left, proposal right, issues as a narrow strip under the header.

```
 Atlas Distribution · Septembre 2026 · Révision 2          [ Demander la validation ]
 ▌ 3 anomalies à traiter: 1 bloquante                       (pink strip, opens list)
┌──────────────────────────────┬─────────────────────────────────────────────┐
│                              │ ACH  12/09/2026  Facture F-2026-0412        │
│   [ invoice page image ]     │ ─────────────────────────────────────────── │
│                              │ 6111  Achats de marchandises   10 000,00    │
│   ┌──────────────┐           │ 34552 TVA récupérable           2 000,00    │
│   │ TVA 2 000,00 │◀──────────│ 4411  Fournisseurs                  12 000,00│
│   └──────────────┘ sky box   │ ─────────────────────────────────────────── │
│                              │ Équilibrée ✓      Débit 12 000,00 = Crédit  │
│  ◀ page 1/2 ▶   zoom         │ Sources: page 1 (3 zones)                   │
└──────────────────────────────┴─────────────────────────────────────────────┘
```

- Focusing a line or field draws a 2px `--sky` box with `--sky-wash` fill over the source region and scrolls the document to it. This is the only animated element: the box moves to its target in 160ms ease-out, disabled under `prefers-reduced-motion`.
- Unconfirmed fields show a pink dot and the word "à confirmer". Confirming with Enter moves to the next unconfirmed field. Keyboard: J/K next/previous entry, E edit, Enter confirm, A accept match, ? shortcuts.
- Edits create a new revision; the header shows the revision number and who edited.

**Reconciliation**: two columns, bank lines left, candidates right, difference column showing the type (`TVA retenue à la source`, `frais bancaires`, `écart`).

**Approval**: a summary page, not a modal. Counts, totals per journal, open review issues acknowledged, the subject hash shortened (`a3f9…c21e`), the approver's name and registration number, and one button: "Valider le dossier". After approval, the button becomes "Télécharger l'export".

**Client portal**: one page. What is missing this month, an upload area, and answered requests. No dashboard.

## E.6 Components

Build these and only these in the pilot: Button (primary, secondary, quiet, danger), Input, Select, Combobox (accounts, with code then label), DateField, AmountField (French format, tabular), Table (sortable, sticky header, keyboard row focus), StatusPill, NeedsPersonMarker, IssueStrip, DocumentViewer (pages, zoom, bbox overlay), SplitPane, Dialog, Toast, EmptyState, Rail, FileDrop.

## E.7 Forbidden in the UI

Gradients and blur blobs in the product, glassmorphism, card grids of identical stat boxes, hero metrics, decorative illustrations, emoji, sparkle or robot icons, "AI" badges on features, confetti, skeleton shimmer longer than 300ms (show real progress instead), uppercase eyebrows, arrows appended to button text, centered page layouts, lorem ipsum, invented customer logos, testimonials, or performance numbers.

## E.8 Copy

French is the product language; English is a full translation; Arabic follows. Sentence case everywhere. Buttons say what happens. Errors say what happened and what to do, without apologizing.

Vocabulary (use exactly these terms; same word on the button and in the confirmation):

| Concept | French | English |
|---|---|---|
| Work request | Dossier mensuel | Monthly file |
| Document | Pièce | Document |
| Proposed entry | Écriture proposée | Proposed entry |
| Issue | Anomalie | Issue |
| Needs a person | À traiter | Needs review |
| Bank matching | Rapprochement | Matching |
| Approve | Valider | Approve |
| Export | Exporter | Export |
| Client request | Demande au client | Client request |

Examples:
- Empty queue: "Aucun dossier pour septembre. Créez un dossier pour commencer."
- Blocking issue: "Les totaux de cette facture ne concordent pas : HT 10 000,00 + TVA 2 000,00 ≠ TTC 12 500,00. Corrigez un montant ou rejetez la pièce."
- Export blocked: "Le dossier a changé depuis la validation. Demandez une nouvelle validation."

Never write: "intelligent", "magic", "powered by AI", "seamless", "effortless", "revolutionize", exclamation marks, or second-person cheerleading.

---

# Part F — Security, privacy, operations

- MFA required for every role that can approve or export. Session lifetime 12h, re-authentication before approval.
- Uploads: presigned PUT with content-type and size bound, max 50 MB, server-side magic-byte check, malware scan before any processing, original bytes never modified, derivatives (page images, OCR) stored under a separate prefix.
- RIB and ICE values are encrypted or hashed where they are lookup keys; display masked except on the client settings page.
- Operator access is requested by AVENEL, granted by the firm owner for ≤ 72h, scoped read-only, and every read is audited.
- Backups: daily PITR, restore tested monthly into an isolated environment; restore test is a release gate before the first live tenant.
- Retention job computes `retain_until = fiscal_year_end + 10 years` (from pack) and never deletes items on legal hold. Deletion of tenant data on contract end follows the DPA and is itself audited.
- Incident runbook in `/docs/runbooks/incident.md` includes CNDP notification steps (to be confirmed by counsel).
- DPA template and CNDP dossier generator are Phase 1 deliverables, reviewed by a Moroccan lawyer before the first pilot.

---

# Part G — Build phases

Each phase lists its exit criteria. A phase is done only when all criteria pass in CI and a human has reviewed the summary.

**Phase 0 — Skeleton**
Repo layout, Docker Compose (Postgres 16, MinIO, Keycloak, OCR container), migrations 001–003, `make` targets, CI pipeline, design tokens and fonts wired into Tailwind, AGENTS.md pointing here.
Exit: `make rls-check` passes on every table; balance trigger and append-only triggers covered by tests; CI green.

**Phase 1 — Tenancy, clients, periods**
OIDC login, membership resolution, roles, client scopes, client company CRUD, chart import (CSV/XLSX), CGNC seed, periods with overlap protection, audit events with chain verification, jurisdiction pack loader with schema validation, DPA and CNDP dossier generator.
Exit: cross-tenant tests for every endpoint (read, write, list, ID guessing) return 404; client user cannot see another company; audit chain verifies.

**Phase 2 — Intake and reading**
Upload flow, malware scan, exact duplicate detection by hash, page rendering, OCR adapter (local), classifier and extractor agents behind the provider router, extraction storage with bboxes, deterministic invoice validation (D.6), document viewer with field overlay, field correction.
Exit: on the fixture set of 300 documents, field-level accuracy report generated; residency router refuses disallowed calls; no provider call in tests.

**Phase 3 — Proposals**
Tax mappings, account suggester, rule-based entry builder for purchases, sales, credit notes, and fixed assets; FX handling; probable duplicate detection (supplier + number + amount + date window); proposal revisions; review screen with keyboard flow.
Exit: property tests (Hypothesis) show every generated proposal balances; golden tests for each invoice type; every line has evidence.

**Phase 4 — Bank and reconciliation**
PDF and CSV/XLSX statement parsing with balance check, RIB validation, candidate generation, withheld-VAT matching, split and grouped matches, reconciliation screen.
Exit: balance-break fixtures detected; withheld-VAT fixtures matched with the correct difference kind; no bank line in two accepted matches.

**Phase 5 — Approval and export**
Quality check, issue workflow, client requests in the portal, approval with subject hash and segregation of duties, Sage 100 (CSV and PNM) and Odoo CSV exporters, evidence pack (PDF summary + JSON manifest + document hashes), usage records.
Exit: export refused when the hash changed; golden export files byte-identical; round-trip import verified manually on one pilot firm's Sage and Odoo, recorded in `export_profiles.verified_round_trip_at`.

**Phase 6 — Flagged extras**
SIMPL-TVA *relevé des déductions* XML generated against the official XSD stored in the pack (not hand-written), behind a feature flag. E-invoice UBL ingestion stays disabled until a decree is published.

---

# Part H — Quality gates

Measured on a labelled set per pilot firm (≥ 300 documents, mixed scan quality, French and Arabic). These are pilot targets, revised after three months.

| Metric | Gate |
|---|---|
| ICE, invoice number, date exact match | ≥ 97% |
| HT, TVA per rate, TTC exact match after arithmetic check | ≥ 98% |
| Account suggestion accepted as first choice | ≥ 80% month 1 |
| Entries approved without edit | ≥ 50% |
| Auto-selected bank match precision | ≥ 99% |
| Bank match recall | ≥ 75% |
| Exact duplicate detection | 100% |
| Probable duplicate recall | ≥ 99% on fixtures |
| Cross-tenant leak tests | 0 failures, release blocker |

Required automated tests: unit; integration against a real Postgres; RLS suite per table; property tests for balancing, ICE and RIB checks, hash canonicalization; golden files for exports and XML; Playwright end-to-end for the full monthly file; accessibility checks (axe) on Queue, Review, Approval.

---

# Part I — Items requiring confirmation by a Moroccan professional

Every item below exists in the pack as `needs_expert` and is disabled until confirmed and signed off (name, title, date recorded in the pack entry).

1. Basis of the cash payment limits (HT or TTC) under CGI art. 106-II.
2. TVA return deadline wording for monthly and quarterly filers in 2026.
3. LF 2026 withholding: staged payer thresholds, exact service lists, and the account used for TVA withheld at source (receivable side for suppliers, payable side for payers).
4. Item-to-rate mapping for the 10% rate and transition rates.
5. ICE check-digit algorithm (currently a warning only).
6. Activity-specific CGNC sub-accounts used by each pilot firm.
7. Official SIMPL-TVA XSD version and payment method codes.
8. CNDP route for each provider and region; DPA wording; applicability of Loi 05-20.
9. OEC position on AI-assisted preparation and subcontracting under professional secrecy.
10. E-invoicing: decree, calendar, UBL profile, clearance identifiers — nothing is built until published.

---

# Part J — Definition of done for the pilot

A pilot firm can, without help from AVENEL staff:

1. create a client company, import its chart, and open September 2026;
2. upload a month of documents and bank statements from the console or let the client upload them in the portal;
3. see every document read, with each figure traceable to its place on the page;
4. review and correct proposed entries, all balanced, with TVA handled per the pack;
5. review bank matches including VAT withheld at source;
6. resolve or send to the client every issue;
7. have a registered professional approve the exact file;
8. download an export that imports cleanly into its own Sage or Odoo, plus an evidence pack;
9. see the charge for the completed file.

And the operators can show: zero cross-tenant access in tests, a verified audit chain, a successful restore test, and measured time saved against the firm's baseline for the same month.

---

# Part K — Decisions recorded during the build

The following 24 binding architectural decisions were established and recorded across the build phases (Phases 1 through 5) following human review:

1. **Role × Action Scope Matrix (C.4 / ARCHITECTURE-notes):**
   Multi-tenant authorization is scope-first: access to out-of-scope resources must return HTTP 404 (preventing enumeration attacks), while unauthorized actions on in-scope resources return HTTP 403. Forced PostgreSQL Row-Level Security (RLS) is applied on every tenant table as an independent second layer.

2. **Pack Conflation Audit & Official Authorities (A.1):**
   Domain rules must cite primary legal sources (e.g., Code Général des Impôts, Loi 9-88, Plan Comptable Général / CGNC 1989). Rules lacking definitive authority are marked `status: needs_expert` with `TODO(EXPERT)` and disabled until human expert sign-off.

3. **Keycloak JWKS Integration & Dynamic Key Rotation (C.2 / ASVS V2.8):**
   JWT authentication verifies RS256 signatures against Keycloak JWKS endpoints. Keys are cached with dynamic rotation on `kid` change; revoked keys are rejected immediately.

4. **Migration Hash Freezing (A.6):**
   Applied database migrations are immutable. A CI linter verifies SHA-256 checksums of migrations 001–008 to ensure historic migration files are never retroactively edited.

5. **RFC 9470 MFA Step-Up Challenges (Part D / Part I):**
   Critical mutations (accountant file approval, round-trip recording) require active multi-factor authentication. Requests lacking MFA return HTTP 401 with `WWW-Authenticate: Bearer error="insufficient_user_authentication"`. Re-authentication is required within 5 minutes (`auth_time < 300s`).

6. **RFC 9457 Problem Details Error Envelopes (C.4):**
   All error responses follow RFC 9457 `application/problem+json` format with standard fields (`type`, `title`, `status`, `detail`, `instance`).

7. **Universal Normalized Bounding Boxes (D.6 / Part E):**
   All document coordinate references use normalized `[x0, y0, x1, y1]` float coordinates in the range `[0.0, 1.0]`. UI overlays render with 160ms transitions.

8. **ClamAV Antivirus Scanning & Quarantine (C.3 / ASVS V12):**
   Uploaded documents must undergo ClamAV daemon malware inspection before intake. Infected files are quarantined (`status: quarantined`). If ClamAV signatures are stale (> 48h) or the scanner is down, intake is paused with user notification.

9. **Exact Duplicate Detection (D.6):**
   Exact duplicate files are detected by SHA-256 hash across `(tenant_id, client_entity_id, sha256)`. Re-submitting an identical document returns HTTP 200 with `document.resubmitted` without generating duplicate proposals.

10. **Bilingual Arabic/Latin OCR Engine (C.3 / Part H):**
    Document processing uses dual-script OCR with automatic per-page language detection, supporting French and Arabic text extraction.

11. **Test Count Invariant Baseline (Part H):**
    The automated CI quality gate fails if the pytest collection count drops below the recorded baseline, preventing accidental test deletion unless accompanied by `TESTS_REMOVED.md`.

12. **UI Verification Copy Standards (Part E):**
    User actions confirming extracted data use "Confirmer" / "Confirm", reserving "Valider" / "Validate" strictly for final legal accountant file sign-off.

13. **Zero Silent Error Rate Gate on Financial Arithmetic (D.6 / Part H):**
    Tax extraction requires strict arithmetic consistency: $HT + TVA = TTC$ within rounding tolerance. Discrepancies raise blocking issue `TOTALS_INCONSISTENT`.

14. **FX Conversion Rounding Line (D.6):**
    FX conversion residuals are posted to explicit rounding lines (`rounding_loss` / `rounding_gain` accounts resolved via `client_tax_mappings`), never to counterparty accounts. The counterparty line strictly equals invoice TTC converted at the transaction rate.

15. **Tax Account Resolution via Client Mappings (D.6):**
    Tax accounts resolve per client through `client_tax_mappings` with `approved_by`. If no approved mapping exists, no proposal line is created and blocking issue `ACCOUNT_UNMAPPED` is raised.

16. **Physical Evidence References vs Rule References (D.6):**
    `journal_lines.evidence_refs` strictly reference document page bounding boxes or bank lines. Legal citations and rule anchors are stored separately in `journal_proposals.rule_refs`. Lines containing only rule refs are rejected.

17. **Probable Duplicate Detection Heuristics (D.6):**
    Invoices from the same counterparty with either the same invoice number OR the same TTC amount within a pack-defined date window ($\pm 20$ days) raise review issue `DUPLICATE_PROBABLE`.

18. **Temporal VAT Rate Transition (D.6):**
    Rate validation is date-aware. The 14% VAT rate is accepted for invoices dated on or before 2025-12-31, but raises `VAT_RATE_UNKNOWN` for invoices dated 2026-01-01 or later per LF 2024 reform.

19. **Reconciliation Matching Uniqueness Trigger (D.3 / Migration 006):**
    `reconciliation_match_items.match_status` is synchronized with `reconciliation_matches.status` via a database trigger. A partial unique index on `(tenant_id, bank_transaction_id) WHERE match_status = 'accepted'` ensures a bank line cannot belong to two accepted matches while allowing multiple proposed candidates.

20. **Bank Journal Proposal Lifecycle (D.3 / Migration 007):**
    Every bank statement line maintains exactly one active BQ proposal. On ingestion, an unmatched line receives a suspense proposal (`5115`). Accepting a match supersedes the suspense proposal with a counterparty proposal in the same transaction. Rejecting a match restores the suspense proposal.

21. **Moroccan RIB Security & Validation (D.3 / ASVS V5):**
    Bank RIBs are validated via 24-digit modulo 97 checksum. Stored RIBs are encrypted at rest with AES-256-GCM, hashed with SHA-256 for duplicate lookup, and masked in UI and logs (`************1234`).

22. **Corporate Tax (IS) 5% Withholding Calculation (D.3):**
    The Moroccan 5% corporate income tax withholding base is HT (pre-tax amount), not TTC. Combined withholding (TVA withholding + IS withholding on HT) calculates expected net receipts deterministically.

23. **File-Level Accountant Sign-Off & Segregation of Duties (D.4 / ASVS V4):**
    Approval occurs exclusively at the monthly file level (`POST /v1/approvals/{id}:decide`), not per proposal. Segregation of duties prevents preparers from approving their own work (`decided_by != prepared_by`). The approver must possess verified professional registration (`expert_comptable` or `comptable_agree`).

24. **Deterministic Subject Hash (D.4 / Migration 008):**
    Approval binds to a canonical SHA-256 subject hash computed across all active proposals and accepted reconciliation matches, excluding volatile fields (timestamps, status, editor IDs). A hash mismatch during approval or export returns HTTP 409 `ApprovalStale`.

