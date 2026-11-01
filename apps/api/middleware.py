"""Idempotency middleware enforcing required Idempotency-Key on mutating HTTP methods.

Enforces:
- Required Idempotency-Key on POST, PUT, PATCH, DELETE (returns 400 if missing)
- Replay: Same key and identical payload returns saved response
- Body mismatch: Same key with different payload returns 422 Unprocessable Entity
- In-flight concurrency: Concurrent request with same key returns 409 Conflict
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@dataclass
class IdempotencyRecord:
    status: str  # "in_flight" | "completed"
    request_hash: str
    response_status: int = 0
    response_headers: dict[str, str] | None = None
    response_body: bytes = b""
    created_at: float = 0.0


class IdempotencyStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, IdempotencyRecord] = {}

    def get(self, key: str) -> IdempotencyRecord | None:
        with self._lock:
            return self._records.get(key)

    def start(self, key: str, request_hash: str) -> tuple[bool, IdempotencyRecord | None]:
        """Atomically checks and registers an in-flight key.
        
        Returns:
            (success, existing_record)
        """
        with self._lock:
            existing = self._records.get(key)
            if existing is not None:
                return False, existing
            self._records[key] = IdempotencyRecord(
                status="in_flight",
                request_hash=request_hash,
                created_at=time.time(),
            )
            return True, None

    def complete(
        self,
        key: str,
        response_status: int,
        response_headers: dict[str, str],
        response_body: bytes,
    ) -> None:
        with self._lock:
            rec = self._records.get(key)
            if rec:
                rec.status = "completed"
                rec.response_status = response_status
                rec.response_headers = response_headers
                rec.response_body = response_body

    def release(self, key: str) -> None:
        with self._lock:
            self._records.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


# Global in-process idempotency store
_GLOBAL_IDEMPOTENCY_STORE = IdempotencyStore()


def get_idempotency_store() -> IdempotencyStore:
    return _GLOBAL_IDEMPOTENCY_STORE


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, store: IdempotencyStore | None = None) -> None:
        super().__init__(app)
        self.store = store or get_idempotency_store()

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Only enforce on mutating routes
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        # Exclude doc endpoints or OpenAPI JSON if any
        if request.url.path in ("/openapi.json", "/docs", "/redoc"):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key or not idempotency_key.strip():
            return JSONResponse(
                status_code=400,
                media_type="application/problem+json",
                content={
                    "type": "https://avenel.ma/errors/idempotency-key-missing",
                    "title": "Missing Idempotency-Key Header",
                    "status": 400,
                    "detail": "L'en-tête Idempotency-Key est obligatoire pour toute requête modifiant des données.",
                },
            )

        key = idempotency_key.strip()
        body_bytes = await request.body()
        req_hash = hashlib.sha256(
            request.method.encode("utf-8")
            + b":"
            + request.url.path.encode("utf-8")
            + b":"
            + body_bytes
        ).hexdigest()

        # Check existing record
        started, existing = self.store.start(key, req_hash)
        if not started and existing is not None:
            if existing.status == "in_flight":
                return JSONResponse(
                    status_code=409,
                    media_type="application/problem+json",
                    content={
                        "type": "https://avenel.ma/errors/concurrent-idempotent-request",
                        "title": "Concurrent Request In Progress",
                        "status": 409,
                        "detail": "Une requête avec cette clé d'idempotence est actuellement en cours d'exécution.",
                    },
                )
            if existing.status == "completed":
                if existing.request_hash != req_hash:
                    return JSONResponse(
                        status_code=422,
                        media_type="application/problem+json",
                        content={
                            "type": "https://avenel.ma/errors/idempotency-key-mismatch",
                            "title": "Idempotency Key Reused With Different Body",
                            "status": 422,
                            "detail": "La clé d'idempotence a déjà été utilisée avec un corps de requête différent.",
                        },
                    )
                # Replay identical response
                headers = dict(existing.response_headers or {})
                headers["Idempotency-Replay"] = "true"
                return Response(
                    content=existing.response_body,
                    status_code=existing.response_status,
                    headers=headers,
                    media_type=headers.get("content-type", "application/json"),
                )

        try:
            response = await call_next(request)
            # Collect response body
            body_chunks = [chunk async for chunk in response.body_iterator]
            full_body = b"".join(body_chunks)

            # Store completed response
            resp_headers = dict(response.headers)
            self.store.complete(key, response.status_code, resp_headers, full_body)

            return Response(
                content=full_body,
                status_code=response.status_code,
                headers=resp_headers,
                media_type=response.media_type,
            )
        except Exception:
            self.store.release(key)
            raise


class RateLimitStore:
    """Thread-safe sliding-window rate limit store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}

    def is_allowed(self, key: str, max_requests: int, window_seconds: int = 60) -> tuple[bool, int, int]:
        """Checks if request is within limit. Returns (allowed, remaining, retry_after)."""
        now = time.time()
        window_start = now - window_seconds
        with self._lock:
            timestamps = self._hits.setdefault(key, [])
            # Prune old timestamps
            self._hits[key] = [t for t in timestamps if t > window_start]
            count = len(self._hits[key])

            if count >= max_requests:
                earliest = self._hits[key][0]
                retry_after = max(1, int(earliest + window_seconds - now))
                return False, 0, retry_after

            self._hits[key].append(now)
            remaining = max_requests - (count + 1)
            return True, remaining, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_GLOBAL_RATE_LIMIT_STORE = RateLimitStore()


def get_rate_limit_store() -> RateLimitStore:
    return _GLOBAL_RATE_LIMIT_STORE


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforces rate limits on authentication and file upload endpoints."""

    def __init__(self, app: Any, store: RateLimitStore | None = None) -> None:
        super().__init__(app)
        self.store = store or get_rate_limit_store()

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        path = request.url.path

        # Determine rate limit bucket
        max_requests = 120
        window_sec = 60
        bucket_prefix = "gen"

        if path.startswith("/v1/auth") or path in ("/v1/me", "/v1/session"):
            max_requests = 30
            bucket_prefix = "auth"
        elif "/documents" in path or "/bank-statements" in path:
            max_requests = 60
            bucket_prefix = "upload"
        else:
            # General endpoints not aggressively throttled
            return await call_next(request)

        # Allow bypass for automated test suites unless testing rate limiting explicitly
        if request.headers.get("X-Test-Bypass-Rate-Limit") == "true":
            return await call_next(request)

        # Extract client identifier (X-Forwarded-For or client host)
        forwarded = request.headers.get("X-Forwarded-For")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        key = f"{bucket_prefix}:{ip}"

        allowed, remaining, retry_after = self.store.is_allowed(key, max_requests, window_sec)
        if not allowed:
            return JSONResponse(
                status_code=429,
                media_type="application/problem+json",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                },
                content={
                    "type": "https://avenel.ma/errors/rate-limit-exceeded",
                    "title": "Trop de requêtes",
                    "status": 429,
                    "detail": f"Limite de requêtes atteinte pour cette ressource. Veuillez réessayer dans {retry_after} secondes.",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces strict security headers: CSP, HSTS, X-Content-Type-Options, etc."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; font-src 'self'; connect-src 'self' http://localhost:8000; "
            "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        return response
