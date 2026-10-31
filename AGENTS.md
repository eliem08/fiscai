# AVENEL — Agent Instructions

This repository builds **AVENEL**, a service that prepares monthly bookkeeping files for Moroccan accounting firms (*fiduciaires*).

The single source of truth for all requirements, architecture, rules, and build phases is:
👉 [ARCHITECTURE.md](ARCHITECTURE.md) (Version 2.0 · 30 October 2026)

## Mandatory Rules (Part A)
1. **Never invent a domain rule.** Read from `/jurisdiction/ma/*.yaml`. If missing, mark `status: needs_expert` with `TODO(EXPERT)` and disable.
2. **No numeric literals for tax or legal values outside `/jurisdiction/`.**
3. **AI proposes, code validates, humans approve.**
4. **Tenant isolation enforced twice:** Application authorization + forced PostgreSQL RLS on every tenant table.
5. **Posted, approved, and audited data is immutable.** Never UPDATE or DELETE audit, evidence, approved proposals, or document versions.
6. **Never edit an applied migration.**
7. **Tests use fixtures, not live providers.**
8. **No secrets in code, logs, fixtures, or prompts.**
9. **Follow Part E design system exactly.**
10. **Plain product copy (French first, sentence case).**

Build only the current phase from Part G and stop for human review at its exit criteria.
Before starting a phase, write a short plan in `docs/plans/phase-N.md`.
After completing a task, ensure `make lint test typecheck openapi-lint rls-check` passes.
