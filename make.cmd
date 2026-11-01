@echo off
setlocal

set PYTHON=C:\Python312\python.exe

if "%~1"=="" goto help

:loop
if "%~1"=="" goto end
set TARGET=%~1

if "%TARGET%"=="lint" (
    echo [make] Running lint...
    %PYTHON% -m ruff check avenel apps scripts
    if errorlevel 1 exit /b 1
    %PYTHON% scripts\check_no_tax_literals.py
    if errorlevel 1 exit /b 1
    %PYTHON% scripts\check_migration_hashes.py
    if errorlevel 1 exit /b 1
    %PYTHON% scripts\check_test_count.py
    if errorlevel 1 exit /b 1
    %PYTHON% scripts\generate_expert_sign_off.py --check
    if errorlevel 1 exit /b 1
) else if "%TARGET%"=="typecheck" (
    echo [make] Running typecheck...
    %PYTHON% -m mypy avenel apps/api scripts
    if errorlevel 1 exit /b 1
) else if "%TARGET%"=="openapi-lint" (
    echo [make] Running openapi-lint...
    call npx @stoplight/spectral-cli lint contracts/openapi.yaml --ruleset .spectral.yaml
    if errorlevel 1 exit /b 1
) else if "%TARGET%"=="rls-check" (
    echo [make] Running rls-check...
    %PYTHON% scripts\rls_check.py
    if errorlevel 1 exit /b 1
) else if "%TARGET%"=="audit-verify" (
    echo [make] Running audit-verify...
    %PYTHON% scripts\verify_audit_chain.py --seed
    if errorlevel 1 exit /b 1
) else if "%TARGET%"=="test" (
    echo [make] Running test...
    %PYTHON% -m pytest -v tests
    if errorlevel 1 exit /b 1
) else if "%TARGET%"=="migrate" (
    echo [make] Running migrate...
    %PYTHON% avenel\infrastructure\migrations.py up
    if errorlevel 1 exit /b 1
) else if "%TARGET%"=="migrate-down" (
    echo [make] Running migrate-down...
    %PYTHON% avenel\infrastructure\migrations.py down
    if errorlevel 1 exit /b 1
) else if "%TARGET%"=="ci" (
    echo [make] Running full ci gate...
    call %0 lint
    if errorlevel 1 exit /b 1
    call %0 typecheck
    if errorlevel 1 exit /b 1
    call %0 openapi-lint
    if errorlevel 1 exit /b 1
    call %0 rls-check
    if errorlevel 1 exit /b 1
    call %0 audit-verify
    if errorlevel 1 exit /b 1
    call %0 test
    if errorlevel 1 exit /b 1
) else (
    echo Unknown target: %TARGET%
    exit /b 1
)

shift
goto loop

:help
echo Available targets: lint, test, typecheck, openapi-lint, rls-check, audit-verify, migrate, migrate-down, ci
exit /b 0

:end
exit /b 0
