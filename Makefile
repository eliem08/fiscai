.PHONY: lint test typecheck openapi-lint rls-check audit-verify migrate migrate-down ci

PYTHON ?= python

lint:
	$(PYTHON) -m ruff check avenel apps scripts
	$(PYTHON) scripts/check_no_tax_literals.py
	$(PYTHON) scripts/check_migration_hashes.py
	$(PYTHON) scripts/check_test_count.py
	$(PYTHON) scripts/generate_expert_sign_off.py --check

test:
	$(PYTHON) -m pytest -v tests

typecheck:
	$(PYTHON) -m mypy avenel apps/api scripts

openapi-lint:
	npx @stoplight/spectral-cli lint contracts/openapi.yaml --ruleset .spectral.yaml

rls-check:
	$(PYTHON) scripts/rls_check.py

audit-verify:
	$(PYTHON) scripts/verify_audit_chain.py --seed

migrate:
	$(PYTHON) avenel/infrastructure/migrations.py up

migrate-down:
	$(PYTHON) avenel/infrastructure/migrations.py down

ci: lint typecheck openapi-lint rls-check audit-verify test

