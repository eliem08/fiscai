"""FastAPI API Application for AVENEL (routes only, thin per ARCHITECTURE.md C.3)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.middleware import (
    IdempotencyMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from apps.api.routes import (
    approvals,
    bank,
    chart,
    clients,
    compliance,
    documents,
    exports,
    issues,
    metrics,
    periods,
    proposals,
    reconciliation,
    session,
    work_requests,
)
from avenel.bank.rib import get_rib_encryption_raw_key
from avenel.documents.scanner import check_intake_health
from avenel.tenancy.jwt import MfaRequiredError


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verifies critical security preconditions at startup."""
    # Refuse startup if RIB encryption key is missing
    get_rib_encryption_raw_key()
    yield


app = FastAPI(
    title="AVENEL API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Security headers on every response
app.add_middleware(SecurityHeadersMiddleware)

# Rate limiting on authentication and upload endpoints
app.add_middleware(RateLimitMiddleware)

# Idempotency middleware enforces required Idempotency-Key on all mutating requests
app.add_middleware(IdempotencyMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(MfaRequiredError)
async def mfa_required_handler(request: Request, exc: MfaRequiredError) -> JSONResponse:
    """RFC 9470 Insufficient User Authentication handler."""
    return JSONResponse(
        status_code=401,
        headers={"WWW-Authenticate": 'Bearer error="insufficient_user_authentication"'},
        media_type="application/problem+json",
        content={
            "type": "avenel/mfa-required",
            "title": "MFA requise",
            "status": 401,
            "detail": exc.detail or "L'authentification multi-facteurs (MFA) est requise pour effectuer cette opération.",
            "instance": str(request.url.path),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """RFC 9457 Problem Details for HTTP exceptions."""
    titles = {
        400: "Requête invalide",
        401: "Non authentifié",
        403: "Accès refusé",
        404: "Ressource introuvable",
        409: "Conflit d'état",
        422: "Entité non traitable",
        500: "Erreur interne du serveur",
    }
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": titles.get(exc.status_code, "Erreur HTTP"),
            "status": exc.status_code,
            "detail": exc.detail,
            "instance": str(request.url.path),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """RFC 9457 Problem Details for validation errors."""
    errors = [
        {"field": ".".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": "Erreur de validation",
            "status": 422,
            "detail": "Les données fournies ne respectent pas le schéma requis.",
            "instance": str(request.url.path),
            "errors": errors,
        },
    )


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, Any]:
    intake = check_intake_health()
    return {
        "status": "ok",
        "service": "avenel-api",
        "intake_paused": intake.intake_paused,
        "banner_message": intake.banner_message,
    }


@app.get("/health/ready", tags=["System"])
async def readiness_check() -> dict[str, Any]:
    """Readiness probe checking database connectivity, KMS encryption key, and antivirus scanner."""
    from apps.api.deps import get_db
    from avenel.bank.rib import get_rib_encryption_raw_key

    # 1. KMS key check
    try:
        get_rib_encryption_raw_key()
        kms_status = "ok"
    except (KeyError, RuntimeError, ValueError) as ex:
        raise HTTPException(
            status_code=503,
            detail=f"Service Unavailable: KMS key uninitialized ({ex})",
        ) from ex

    # 2. Antivirus check
    intake = check_intake_health()
    clamav_status = "quarantined_fallback" if intake.intake_paused else "ok"

    # 3. Database check
    db_status = "ok"
    try:
        with next(get_db()) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1;")
    except (RuntimeError, OSError) as ex:
        raise HTTPException(
            status_code=503,
            detail=f"Service Unavailable: Database connection failed ({ex})",
        ) from ex

    return {
        "status": "ready",
        "service": "avenel-api",
        "database": db_status,
        "kms": kms_status,
        "clamav": clamav_status,
        "intake_paused": intake.intake_paused,
    }


# Include domain routers
app.include_router(session.router)
app.include_router(clients.router)
app.include_router(periods.router)
app.include_router(chart.router)
app.include_router(compliance.router)
app.include_router(work_requests.router)
app.include_router(documents.router)
app.include_router(proposals.router)
app.include_router(bank.router)
app.include_router(bank.statements_router)
app.include_router(reconciliation.router)
app.include_router(approvals.router)
app.include_router(exports.router)
app.include_router(issues.router)
app.include_router(metrics.router)
