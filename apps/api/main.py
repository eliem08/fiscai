"""FastAPI API Application for AVENEL (routes only, thin per ARCHITECTURE.md C.3)."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.middleware import IdempotencyMiddleware
from apps.api.routes import chart, clients, compliance, periods, session
from avenel.tenancy.jwt import MfaRequiredError

app = FastAPI(
    title="AVENEL API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

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
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "avenel-api"}


# Include Phase 1 domain routers
app.include_router(session.router)
app.include_router(clients.router)
app.include_router(periods.router)
app.include_router(chart.router)
app.include_router(compliance.router)
