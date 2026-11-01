param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Targets = @("help")
)

$Python = "C:\Python312\python.exe"

foreach ($Target in $Targets) {
    switch ($Target) {
        "lint" {
            Write-Host "[make] Running lint..." -ForegroundColor Cyan
            & $Python -m ruff check avenel apps scripts
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python scripts/check_no_tax_literals.py
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python scripts/check_migration_hashes.py
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python scripts/check_test_count.py
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python scripts/generate_expert_sign_off.py --check
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        "typecheck" {
            Write-Host "[make] Running typecheck..." -ForegroundColor Cyan
            & $Python -m mypy avenel apps/api scripts
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        "openapi-lint" {
            Write-Host "[make] Running openapi-lint..." -ForegroundColor Cyan
            npx @stoplight/spectral-cli lint contracts/openapi.yaml --ruleset .spectral.yaml
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        "rls-check" {
            Write-Host "[make] Running rls-check..." -ForegroundColor Cyan
            & $Python scripts/rls_check.py
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        "audit-verify" {
            Write-Host "[make] Running audit-verify..." -ForegroundColor Cyan
            & $Python scripts/verify_audit_chain.py --seed
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        "test" {
            Write-Host "[make] Running test..." -ForegroundColor Cyan
            & $Python -m pytest -v tests
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        "migrate" {
            Write-Host "[make] Running migrate..." -ForegroundColor Cyan
            & $Python avenel/infrastructure/migrations.py up
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        "migrate-down" {
            Write-Host "[make] Running migrate-down..." -ForegroundColor Cyan
            & $Python avenel/infrastructure/migrations.py down
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        "ci" {
            Write-Host "[make] Running full ci gate..." -ForegroundColor Cyan
            & $PSCommandPath lint
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $PSCommandPath typecheck
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $PSCommandPath openapi-lint
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $PSCommandPath rls-check
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $PSCommandPath audit-verify
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $PSCommandPath test
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        default {
            Write-Host "Available targets: lint, test, typecheck, openapi-lint, rls-check, audit-verify, migrate, migrate-down, ci"
        }
    }
}
