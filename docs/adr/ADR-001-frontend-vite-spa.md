# ADR-001: Frontend Architecture — Vite + React 18 SPA over Next.js 15 App Router

**Status:** Accepted  
**Date:** 1 November 2026  
**Deciders:** AVENEL Architecture Team  
**Consulted:** Security, DevOps, Domain Experts  

---

## Context

In `ARCHITECTURE.md` Version 2.0 (Section C.2), the web layer was specified as:
> `Next.js 15 App Router, TypeScript strict, Tailwind with the tokens in Part E only`

During Phase 1–5b implementation, evaluation of operational constraints in Moroccan sovereign hosting environments (N+ONE Datacenter, Inwi Cloud) *(unverified — confirm with provider)* and enterprise accounting firm network perimeters led to a re-evaluation of the frontend deployment topology.

## Decision

We adopt a **Vite + React 18 Single Page Application (SPA)** architecture, compiled to static assets and served by an unprivileged Nginx reverse proxy (`docker/Dockerfile.web` and `docker/nginx.conf`), communicating exclusively with the backend via typed OpenAPI 3.1 REST contracts (`apps/api/`).

## Rationale

### 1. Data Residency & Sovereign Datacenter Hardening
Moroccan sovereign infrastructure (N+ONE, Inwi) *(unverified — confirm with provider)* requires minimal attack surfaces and strictly auditable runtime environments. A static SPA eliminates the requirement for a Node.js server runtime in production:
- No Node.js process running with elevated privileges or listening on production ports.
- Memory footprint is reduced from ~300MB (Node SSR) to <20MB (Nginx static delivery).
- Immune to server-side template injection or SSR-specific Node vulnerabilities.

### 2. Strict Boundary Enforcement & PostgreSQL RLS
In Next.js App Router, the line between Server Components, Server Actions, and Client Components frequently blurs data access boundaries. In contrast:
- In the Vite SPA model, the frontend is strictly treated as untrusted.
- Every read and write must transit through the FastAPI gateway, where application RBAC and forced PostgreSQL Row-Level Security (RLS) are enforced twice (Part A Rule 4).
- No database credentials or internal backend secrets ever exist in frontend bundles or build steps.

### 3. Hardened Security Headers from the Edge
Serving static assets via Nginx (`docker/nginx.conf`) and the API via FastAPI allows HTTP security headers to be applied at the protocol level:
- `Content-Security-Policy` (CSP), `Strict-Transport-Security` (HSTS), `X-Content-Type-Options`, and `X-Frame-Options` are injected directly into HTTP response headers, eliminating reliance on client-side `<meta>` tags.
- Immutable static caching (`Cache-Control: public, max-age=31536000, immutable`) on hashed chunks.

### 4. Deterministic Performance & Fast Developer Feedback
Vite provides sub-second hot module replacement (HMR), tree-shaking, and lightweight test orchestration via Vitest and Playwright without the overhead of Next.js route compilation.

---

## Consequences

- **Positive:** Simpler Docker containerization, faster CI build times, zero Node.js backend runtime maintenance, strict decoupled API contracts.
- **Negative:** Search engine optimization (SEO) is not natively server-rendered; however, AVENEL is an authenticated B2B SaaS portal and internal console for accounting firms, where public indexing is not required.

