# Architecture Notes — Role Authorization & Resource Scoping

## 1. Scope-First Authorization Rule (Part A & Part G Invariant)

To guarantee strict tenant isolation and zero information leakage across tenant and client boundaries:

### The Scope-First Invariant
1. **Out-of-Scope Resources return `404 Not Found`**:
   - Any attempt to access, list, read, or mutate a resource that belongs to another tenant returns `404 Not Found` (never `403 Forbidden` or `200 OK`).
   - For `client_user` members, any attempt to access a client entity or child resource (periods, chart of accounts, documents) outside their assigned `client_scope_ids` returns `404 Not Found`.
   - The API never reveals whether an out-of-scope resource ID exists.

2. **In-Scope Role Inabilities return `403 Forbidden`**:
   - When a resource is confirmed to exist and is within the caller's authorized scope, but the caller's role is not permitted to execute that specific action, the API returns `403 Forbidden`.
   - `operator` access is strictly read-only for support purposes. Any mutating endpoint invoked by an operator returns `403 Forbidden`.
   - `staff` members cannot modify client entities, archive companies, open/close accounting periods, or seed/import chart of accounts (`403 Forbidden`).
   - `client_user` members cannot mutate client master data, archive companies, manage accounting periods, or alter the chart of accounts even for their in-scope company (`403 Forbidden`).
   - `accountant` members cannot archive client entities (`403 Forbidden`), as archiving is reserved for firm owners and managers (`owner`, `manager`).

---

## 2. Role × Action Permission Matrix (Phase 1 Mutating Endpoints)

| Endpoint | Action | `owner` | `manager` | `accountant` | `staff` | `client_user` (in-scope) | `client_user` (out-of-scope) | `operator` |
|---|---|---|---|---|---|---|---|---|
| `POST /v1/client-entities` | Create client | ✅ 201 | ✅ 201 | ✅ 201 | ❌ 403 | ❌ 403 | N/A | ❌ 403 |
| `PUT /v1/client-entities/{id}` | Update client | ✅ 200 | ✅ 200 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |
| `PATCH /v1/client-entities/{id}` | Patch client | ✅ 200 | ✅ 200 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |
| `POST /v1/client-entities/{id}/archive` | Archive client | ✅ 200 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |
| `POST /v1/client-entities/{id}/periods` | Open period | ✅ 201 | ✅ 201 | ✅ 201 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |
| `POST /v1/client-entities/{id}/periods/{pid}/close` | Close period | ✅ 200 | ✅ 200 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |
| `POST /v1/client-entities/{id}/chart-accounts/seed-cgnc` | Seed CGNC | ✅ 200 | ✅ 200 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |
| `POST /v1/client-entities/{id}/chart-accounts/import` | Import chart | ✅ 200 | ✅ 200 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 404 | ❌ 403 |
