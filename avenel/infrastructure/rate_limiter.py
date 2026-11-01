"""Shared-store token-bucket rate limiter backed by PostgreSQL.

Provides synchronized rate-limiting across multiple FastAPI/Uvicorn workers.
"""

from __future__ import annotations

import time

import psycopg


class PostgresRateLimiter:
    """Token bucket rate limiter backed by PostgreSQL table `rate_limit_buckets`."""

    def __init__(self, db_url: str | None = None) -> None:
        self.db_url = db_url

    def acquire(
        self,
        conn: psycopg.Connection,
        bucket_key: str,
        rate_per_minute: int,
        burst_capacity: int | None = None,
    ) -> tuple[bool, int]:
        """Attempts to consume 1 token from the bucket. Returns (allowed, remaining_tokens)."""
        capacity = float(burst_capacity or rate_per_minute)
        refill_rate = float(rate_per_minute) / 60.0  # tokens per second
        now = time.time()

        with conn.cursor() as cur:
            # Lock the row for update to ensure atomicity across workers
            cur.execute(
                """
                SELECT tokens, last_refilled_at
                FROM rate_limit_buckets
                WHERE bucket_key = %s
                FOR UPDATE;
                """,
                (bucket_key,),
            )
            row = cur.fetchone()

            if row is None:
                # First request for this key
                initial_tokens = capacity - 1.0
                cur.execute(
                    """
                    INSERT INTO rate_limit_buckets (bucket_key, tokens, last_refilled_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (bucket_key) DO UPDATE
                    SET tokens = EXCLUDED.tokens, last_refilled_at = EXCLUDED.last_refilled_at;
                    """,
                    (bucket_key, initial_tokens, now),
                )
                conn.commit()
                return True, int(initial_tokens)

            current_tokens, last_refilled_at = float(row[0]), float(row[1])
            delta_time = max(0.0, now - last_refilled_at)
            refilled_tokens = min(capacity, current_tokens + (delta_time * refill_rate))

            if refilled_tokens >= 1.0:
                new_tokens = refilled_tokens - 1.0
                cur.execute(
                    """
                    UPDATE rate_limit_buckets
                    SET tokens = %s, last_refilled_at = %s
                    WHERE bucket_key = %s;
                    """,
                    (new_tokens, now, bucket_key),
                )
                conn.commit()
                return True, int(new_tokens)
            else:
                # Update refilled tokens without consuming
                cur.execute(
                    """
                    UPDATE rate_limit_buckets
                    SET tokens = %s, last_refilled_at = %s
                    WHERE bucket_key = %s;
                    """,
                    (refilled_tokens, now, bucket_key),
                )
                conn.commit()
                return False, 0
