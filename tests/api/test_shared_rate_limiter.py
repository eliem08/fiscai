"""Integration tests for shared-store PostgreSQL rate limiting across workers (Rule ASVS & Phase 5b Item 7)."""

from __future__ import annotations

import os
import psycopg
import pytest

from avenel.infrastructure.rate_limiter import PostgresRateLimiter


@pytest.fixture
def db_url() -> str:
    return os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/avenel"
    )


def test_shared_rate_limiter_two_workers(db_url: str):
    """Verifies that two distinct worker connections share the exact same rate limit bucket in PostgreSQL."""
    limiter = PostgresRateLimiter(db_url)
    bucket_key = "test_shared_worker_bucket"

    # Setup two independent database connections representing two workers
    try:
        conn_worker_1 = psycopg.connect(db_url, autocommit=True)
        conn_worker_2 = psycopg.connect(db_url, autocommit=True)
    except Exception as ex:
        pytest.skip(f"Database not available for shared rate limiter test: {ex}")

    try:
        # Clear any existing bucket
        with conn_worker_1.cursor() as cur:
            cur.execute("DELETE FROM rate_limit_buckets WHERE bucket_key = %s;", (bucket_key,))

        # Limit: 5 requests per minute, burst capacity 5
        limit = 5

        # Worker 1 consumes 3 tokens
        for _ in range(3):
            allowed = limiter.acquire(conn_worker_1, bucket_key, rate_per_minute=limit, burst_capacity=limit)
            assert allowed is True, "Worker 1 should be allowed initial tokens"

        # Worker 2 attempts to consume 2 tokens
        for _ in range(2):
            allowed = limiter.acquire(conn_worker_2, bucket_key, rate_per_minute=limit, burst_capacity=limit)
            assert allowed is True, "Worker 2 should consume remaining tokens"

        # Total 5 consumed. Both Worker 1 and Worker 2 should now be throttled
        throttled_w1 = limiter.acquire(conn_worker_1, bucket_key, rate_per_minute=limit, burst_capacity=limit)
        assert throttled_w1 is False, "Worker 1 should be throttled after shared bucket exhaustion"

        throttled_w2 = limiter.acquire(conn_worker_2, bucket_key, rate_per_minute=limit, burst_capacity=limit)
        assert throttled_w2 is False, "Worker 2 should be throttled after shared bucket exhaustion"

    finally:
        with conn_worker_1.cursor() as cur:
            cur.execute("DELETE FROM rate_limit_buckets WHERE bucket_key = %s;", (bucket_key,))
        conn_worker_1.close()
        conn_worker_2.close()
