# Phase 0 Plan — Skeleton

## 1. Goal
Establish the AVENEL system skeleton according to `ARCHITECTURE.md` (Version 2.0, 30 October 2026), complying strictly with Part A mandatory rules and meeting all Phase 0 exit criteria.

Exit Criteria for Phase 0:
1. `make rls-check` passes on every table (verifying forced RLS and tenant policy on all tables with `tenant_id`).
2. Balance trigger (`journal_lines_balanced`) and append-only triggers (`audit_no_mutation`, `evidence_no_mutation`, `docver_no_mutation`, `extraction_no_mutation`, `journal_lines_frozen`) covered by tests.
3. CI green (`lint`, `test`, `typecheck`, `openapi-lint`, `rls-check`).

---

## 2. Files to Create

### Documentation & Pointers
- `docs/plans/phase-0.md` — This build plan.
- `docs/open-questions.md` — Ambiguities recorded with the most restrictive interpretation.
- `AGENTS.md` — Canonical agent entry point pointing to `ARCHITECTURE.md`.
- `CLAUDE.md` — Link to `AGENTS.md` and `ARCHITECTURE.md`.
- `.cursor/rules` — Link to `AGENTS.md` and `ARCHITECTURE.md`.

### Architecture & Repository Layout
- Domain packages under `/avenel/`:
  - `avenel/__init__.py`
  - `avenel/tenancy/__init__.py`
  - `avenel/clients/__init__.py`
  - `avenel/periods/__init__.py`
  - `avenel/documents/__init__.py`
  - `avenel/extraction/__init__.py`
  - `avenel/accounting/__init__.py`
  - `avenel/bank/__init__.py`
  - `avenel/reconciliation/__init__.py`
  - `avenel/issues/__init__.py`
  - `avenel/approvals/__init__.py`
  - `avenel/approvals/hashing.py` (canonical hash helper outline)
  - `avenel/exports/__init__.py`
  - `avenel/evidence/__init__.py`
  - `avenel/billing/__init__.py`
  - `avenel/workflow/__init__.py`
  - `avenel/providers/__init__.py`
  - `avenel/infrastructure/` (db connection, migration runner, RLS checker)
- API application skeleton:
  - `apps/api/main.py`
  - `apps/api/config.py`
- Web console and portal:
  - `apps/web/package.json`
  - `apps/web/tailwind.config.ts` (Part E design tokens and fonts)
  - `apps/web/src/app/globals.css`
  - `apps/web/src/app/layout.tsx`
  - `apps/web/src/app/page.tsx`
- Jurisdiction pack skeleton:
  - `jurisdiction/ma/pack.schema.json`
  - `jurisdiction/ma/` YAML seed stubs with `MA-2026.10.1` versioning
- Contracts & OpenAPI:
  - `contracts/openapi.yaml` (OpenAPI 3.1.0 specification)
  - `.spectral.yaml` (Spectral lint rules per Part D2)
- Docker Compose:
  - `docker-compose.yml` (Postgres 16, MinIO, Keycloak, OCR container)
  - `docker/postgres/init-roles.sql` (bootstrap roles `avenel_owner` and `avenel_app`)
- Build & CI:
  - `Makefile` (targets: `lint`, `test`, `typecheck`, `openapi-lint`, `rls-check`, `migrate`, `migrate-down`)
  - `scripts/check_no_tax_literals.py` (Rule A.2 enforcement: fail on numeric tax literals outside `/jurisdiction/`)
  - `scripts/rls_check.py` (pg_class query implementation)
  - `.github/workflows/ci.yml` (Lint, Typecheck, Tests, Migrations Up/Down, OpenAPI Lint, RLS check, Secret Scan)

---

## 3. Database Migrations (001–003)

Forward and down migrations in `db/migrations/`:
1. `001_core.up.sql` / `001_core.down.sql`:
   - Extensions: `pgcrypto`, `citext`, `btree_gist`
   - Schema: `app`
   - Functions: `app.current_tenant()`, `app.current_user_id()`, `app.touch_updated_at()`, `app.assert_proposal_balanced()`, `app.forbid_frozen_line_change()`, `app.resolve_membership(subject text)`
   - Tables: `tenants`, `users`, `memberships`, `client_entities`, `membership_client_scopes`, `accounting_periods`, `chart_accounts`, `jurisdiction_tax_codes`, `client_tax_mappings`, `counterparties`, `work_requests`, `documents`, `document_versions`, `extractions`, `journal_proposals`, `journal_lines`, `bank_accounts`, `bank_statements`, `bank_transactions`, `reconciliation_matches`, `reconciliation_match_items`, `issues`, `approvals`, `export_profiles`, `exports`, `provider_calls`, `agent_runs`, `idempotency_keys`, `usage_records`, `evidence_records`, `audit_events`.
   - Triggers: `journal_lines_balanced` (deferred constraint trigger), `journal_lines_frozen`, updated_at triggers.
2. `002_rls.up.sql` / `002_rls.down.sql`:
   - RLS ENABLE & FORCE on all tables with `tenant_id`
   - Tenant isolation policy `*_tenant` using `app.current_tenant()`
   - Role permissions for `avenel_app` (SELECT, INSERT, UPDATE, limited DELETE per spec; REVOKE on jurisdiction_tax_codes)
3. `003_append_only.up.sql` / `003_append_only.down.sql`:
   - Function: `app.forbid_mutation()`
   - Triggers: `audit_no_mutation`, `evidence_no_mutation`, `docver_no_mutation`, `extraction_no_mutation`
   - REVOKE UPDATE, DELETE, TRUNCATE on append-only tables from `avenel_app`
   - Function: `app.chain_audit()` with advisory xact lock and sha256 hash chaining
   - Trigger: `audit_chain` on `audit_events`
   - View: `document_versions_current` for append-only malware scan reflection via `evidence_records`

---

## 4. Tests

Automated tests under `tests/`:
- `tests/conftest.py` — Postgres 16 test database fixture with migration application and teardown.
- `tests/rls/test_rls.py`:
  - `make rls-check` query test: ensures every table with `tenant_id` has forced RLS and tenant policy.
  - Multi-tenant query isolation test: session with tenant A context cannot see tenant B rows.
  - Missing tenant context (`app.current_tenant()` NULL) hides all rows.
- `tests/triggers/test_balance_trigger.py`:
  - Valid proposal with Σ debit = Σ credit (≥ 2 lines) commits successfully.
  - Unbalanced proposal fails on transaction commit with constraint error (23514).
  - Empty proposal fails.
  - Proposal line with both debit and credit or zero on both sides rejected by table check constraints.
- `tests/triggers/test_append_only.py`:
  - UPDATE and DELETE rejected on `audit_events` with 42501.
  - UPDATE and DELETE rejected on `evidence_records` with 42501.
  - UPDATE and DELETE rejected on `document_versions` with 42501.
  - UPDATE and DELETE rejected on `extractions` with 42501.
  - Frozen proposal lines (`approved`, `exported`, `superseded`) cannot be updated or deleted.
- `tests/triggers/test_audit_chain.py`:
  - Sequential inserts into `audit_events` compute matching `prev_hash` and `row_hash`.
- `tests/lint/test_tax_literals.py`:
  - Verifies that no tax/legal rate or threshold literals exist in application code outside `/jurisdiction/`.

---

## 5. Open Questions
Documented in `docs/open-questions.md`:
1. `document_versions.malware_scan`: Handled via immutable `evidence_records` (`kind = 'malware_scan'`) and `document_versions_current` view, avoiding in-place update violations of append-only constraints.
2. `app.resolve_membership`: Defined in `001_core.sql` / `002_rls.sql` as a `SECURITY DEFINER` function owned by `avenel_owner` to safely resolve membership before tenant context is set.

---

## 6. Pre-Phase 1 Conditional Review Checklist (Completed)
1. **Part I items in `/jurisdiction/ma/*.yaml`**: All 10 items marked `status: needs_expert` with `TODO(EXPERT)` and validated against schema.
2. **C.4 Invariant Database Tests (`tests/invariants/test_c4_invariants.py`)**:
   - Invariant #2: Cross-client composite FK rejection (`(tenant_id, client_entity_id, parent_id)`).
   - Invariant #8: Approvals SoD check (`prepared_by != decided_by` unless `single_person_policy=true`) and registration number requirement.
   - Invariant #9: Overlapping periods rejected by GiST exclusion constraint; overlapping chart accounts rejected by GiST exclusion constraint.
   - `UNIQUE NULLS NOT DISTINCT`: Duplicate NULL ICE values within same tenant rejected.
   - Invariant #7: Export references valid approval in same tenant.
3. **Negative Guard Tests (`tests/guards/test_negative_guards.py`)**:
   - Tax-literal linter fails on planted `0.20` in application code.
   - Spectral linter fails on planted `nullable: true` (`no-nullable` error).
   - `rls_check` fails on planted table with `tenant_id` and no RLS policy.
4. **Role Privileges & Immutability Defense-in-Depth (`tests/rls/test_app_privileges.py`)**:
   - `avenel_app` is NOSUPERUSER, NOBYPASSRLS, and owns no tables in public schema.
   - Even with mutation triggers dropped, `avenel_app` gets permission denied on UPDATE/DELETE of `audit_events`, `evidence_records`, `document_versions`, and `extractions`.
5. **Concurrent Audit Chain & `make audit-verify` (`tests/triggers/test_audit_concurrent.py`, `scripts/verify_audit_chain.py`)**:
   - 10 concurrent worker threads inserting audit events under one tenant; chain remains strictly linear without forks.
   - Target `audit-verify` added to Makefile, `make.cmd`, and `make.ps1`.
6. **Malware Scan Schema Verification (`tests/triggers/test_document_versions_malware_scan.py`)**:
   - Verified `document_versions` has no `malware_scan` column.
   - Status resolved via `evidence_records` (`kind = 'malware_scan'`) and exposed through `document_versions_current` view.
7. **Tailwind & Fonts**:
   - `theme.colors` directly overrides Tailwind default palette (no unapproved colors).
   - Self-hosted fonts (`IBM Plex Sans`, `Readex Pro`, `IBM Plex Sans Arabic`) in `public/fonts/`; zero external font CDN dependencies.
8. **Production Rollback Guard**:
   - `rollback_migration` refuses to run and raises RuntimeError when `ENV=production` or `ENVIRONMENT=production`.
   - Verified by test in `tests/integration/test_migrations.py`.
9. **Docker Image Pinning**:
   - All 4 services in `docker-compose.yml` pinned by exact multi-arch sha256 digests.

