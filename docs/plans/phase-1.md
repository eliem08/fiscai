# Phase 1 Plan — Tenancy, Clients, Periods

## 1. Goal
Implement Phase 1 according to `ARCHITECTURE.md` (Version 2.0, 30 October 2026, Part G) and Part A mandatory rules.

### Phase 1 Deliverables
1. **OIDC Authentication & Membership Resolution**:
   - Real Keycloak RS256 JWT validation against JWKS (`iss`, `aud`, `exp`, `nbf`, signature).
   - MFA claim (`acr`/`amr`) enforcement for memberships with `professional_registration_no`.
   - Temporary operator access with duration $\le 72$h granted by owner; expired access returns 404.
   - Setting PostgreSQL session context: `app.tenant_id` and `app.user_id` per DB spec functions `app.current_tenant()` and `app.current_user_id()`.
   - Client scope enforcement: `client_user` restricted strictly to assigned `client_scope_ids` (mutations and compliance routes return 404).

2. **Client Company Lifecycle (Archive, No Deletion)**:
   - Endpoints: `GET /v1/client-entities`, `POST /v1/client-entities`, `GET /v1/client-entities/{id}`, `PUT /v1/client-entities/{id}`, `PATCH /v1/client-entities/{id}`, `POST /v1/client-entities/{id}/archive`.
   - Deletion completely removed; archived clients have `status='archived'` and are strictly read-only (mutations reject with 409 Conflict).
   - Audit logging: Hash-chained audit event `client.archive` emitted (no `client.delete`).

3. **Chart of Accounts (CGNC Seed & Secure CSV/XLSX Import)**:
   - Built-in standard CGNC seed (classes 0–8) loaded from `/jurisdiction/ma/cgnc_seed.yaml`.
   - Identifier regexes (ICE, IF, RIB, RC) loaded from `/jurisdiction/ma/identifiers.yaml`.
   - Tax-literal and pattern linter forbidding hardcoded regexes and account code seeds in application code.
   - Hardened parser using `openpyxl` + `defusedxml`:
     - Max file size: 10 MB
     - Max uncompressed size: 50 MB (zip bomb protection)
     - Max row count: 20,000 rows
     - XXE / DTD expansion protection via `defusedxml.ElementTree`

4. **Accounting Periods with Overlap Protection**:
   - Table `accounting_periods` operations with period code validation (`YYYY-MM`).
   - GiST exclusion constraint enforcement preventing overlapping date ranges for the same client.
   - Endpoints: `GET /v1/client-entities/{id}/periods`, `POST /v1/client-entities/{id}/periods`.
   - Cross-tenant requests return 404; overlapping periods return 409 Conflict.

5. **Idempotency Protection**:
   - Middleware enforcing required `Idempotency-Key` header on every mutating route (`POST`, `PUT`, `PATCH`, `DELETE`).
   - Identical replay returns cached response and headers without re-execution.
   - Reused key with different payload returns 422 Unprocessable Entity.
   - Concurrent in-flight request with same key returns 409 Conflict.

6. **CNDP Dossier & DPA Compliance Documents**:
   - Titled strictly `"Projet — à valider par un juriste"`.
   - Explicitly list `needs_expert_dependencies` keys.
   - Strictly avoid the forbidden term `"conforme"`.
   - Endpoints: `GET /v1/compliance/dpa`, `GET /v1/compliance/cndp-dossier`.

7. **Four-Quadrant Security Matrix**:
   - Every Phase 1 endpoint tested across:
     1. Same-tenant positive (200 / 201 with expected rows)
     2. Cross-tenant isolation (404, never 403 or 200)
     3. `client_user` out-of-scope isolation (404, never 403 or 200)
     4. Unauthenticated request (401)

---

## 2. Phase 1 Exit Criteria
Per `ARCHITECTURE.md` Part G:
- **Cross-tenant tests for every endpoint (read, write, list, ID guessing) return 404 (never 403 or 200).**
- **Client user cannot see another company or perform unauthorized mutations (404).**
- **Audit chain verifies (`audit-verify` passes on seeded data).**
- **Full CI gate passes (`make lint test typecheck openapi-lint rls-check audit-verify`).**

---

## 3. Implementation Steps

1. **Domain Models & Services (`avenel/`)**:
   - `avenel/tenancy/auth.py`: Token verification, membership resolution, and DB session context setup.
   - `avenel/clients/service.py`: Client entity CRUD, validation (ICE regex, IF, RC).
   - `avenel/periods/service.py`: Period opening, closing, and overlap validation.
   - `avenel/accounting/cgnc.py`: Standard CGNC seed data and chart loader.
   - `avenel/accounting/chart_import.py`: CSV and XLSX parser for chart accounts.
   - `avenel/jurisdiction/loader.py`: Pack loader and validator.
   - `avenel/compliance/dpa.py`: DPA generator for Moroccan accounting firms.
   - `avenel/compliance/cndp.py`: CNDP declaration dossier generator.

2. **API Routes (`apps/api/`)**:
   - Update `contracts/openapi.yaml` with Phase 1 endpoints and schemas.
   - Implement route handlers in `apps/api/routes/`:
     - `auth.py`: `/v1/me`
     - `clients.py`: `/v1/client-entities` (CRUD)
     - `periods.py`: `/v1/client-entities/{id}/periods`
     - `chart.py`: `/v1/client-entities/{id}/chart-accounts`
     - `compliance.py`: `/v1/compliance/dpa`, `/v1/compliance/cndp-dossier`
   - Wire dependencies into `apps/api/main.py`.

3. **Tests (`tests/`)**:
   - `tests/api/test_cross_tenant_isolation.py`:
     - Read, write, list, ID guessing for every endpoint returns 404.
   - `tests/api/test_client_user_scoping.py`:
     - `client_user` can only see their scoped client company.
   - `tests/api/test_chart_import.py`:
     - CGNC seed test, CSV import test, XLSX import test, duplicate rejection.
   - `tests/api/test_periods.py`:
     - Period creation and GiST overlap rejection (409 Conflict).
   - `tests/api/test_compliance.py`:
     - DPA and CNDP dossier generation tests.
