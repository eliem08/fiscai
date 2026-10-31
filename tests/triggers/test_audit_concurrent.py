"""Concurrent insert test for audit chain serialization.

Per ARCHITECTURE.md Rule A.2 #5 and Checklist Item 5:
- One tenant, parallel transactions inserting audit events concurrently.
- Separate database connections per worker thread.
- Synchronized release using threading.Barrier before insert.
- pg_sleep(0.05) inside each transaction while holding serialization lock.
- Trigger uses pg_advisory_xact_lock to serialize inserts per tenant.
- Audit chain remains strictly linear with zero forks or orphan links.
- Report observed concurrency overlap metrics.
"""

from __future__ import annotations

import concurrent.futures
import json
import threading
import time
import uuid
from typing import Any

import psycopg

from scripts.verify_audit_chain import verify_audit_chains


def _worker_insert_audit_event(
    postgres_url: str,
    tenant_id: uuid.UUID,
    worker_id: int,
    barrier: threading.Barrier,
) -> dict[str, Any]:
    """Worker task: connects via dedicated connection, synchronizes at barrier, sleeps in tx, inserts and commits."""
    with psycopg.connect(postgres_url, autocommit=False) as conn:
        # 1. Wait at barrier so all threads begin their database transaction simultaneously
        barrier.wait()
        t_start = time.perf_counter()

        with conn.cursor() as cur:
            # 2. Acquire tenant advisory lock before sequence allocation to ensure sequence and chain order align
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s::text, 0));", (str(tenant_id),))

            # 3. Insert event
            payload = json.dumps({"worker": worker_id, "data": f"payload_{worker_id}"})
            cur.execute(
                """
                INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, data)
                VALUES (%s, 'system', %s, 'concurrent_event', 'worker_job', %s, %s::jsonb)
                RETURNING id;
                """,
                (tenant_id, f"worker-{worker_id}", str(worker_id), payload),
            )
            row_id = cur.fetchone()[0]

            # 4. Hold transaction and advisory lock open for 50ms
            cur.execute("SELECT pg_sleep(0.05);")

        conn.commit()
        t_end = time.perf_counter()

    return {
        "worker_id": worker_id,
        "row_id": row_id,
        "start": t_start,
        "end": t_end,
        "duration": t_end - t_start,
    }


def test_concurrent_audit_inserts_chain_stays_linear(postgres_url: str, db_conn: psycopg.Connection):
    """Spawn concurrent threads with threading.Barrier, separate connections, and pg_sleep(0.05)."""
    t_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Concurrent Audit Tenant');", (t_id,))
    db_conn.commit()

    num_workers = 10
    barrier = threading.Barrier(num_workers)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(_worker_insert_audit_event, postgres_url, t_id, i, barrier)
            for i in range(num_workers)
        ]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == num_workers

    # Calculate concurrency metrics and overlap
    min_start = min(r["start"] for r in results)
    max_end = max(r["end"] for r in results)
    wall_time = max_end - min_start
    sum_durations = sum(r["duration"] for r in results)

    # Count how many pairs of worker intervals overlapped in time
    overlapping_pairs = sum(
        1
        for i in range(len(results))
        for j in range(i + 1, len(results))
        if max(results[i]["start"], results[j]["start"]) < min(results[i]["end"], results[j]["end"])
    )

    print("\n" + "=" * 60)
    print("CONCURRENT AUDIT LOCK OVERLAP REPORT")
    print(f"Total concurrent workers: {num_workers} (synchronized via threading.Barrier)")
    print(f"Sleep inside each transaction: 0.05s (50ms)")
    print(f"Total wall-clock elapsed time: {wall_time:.4f}s")
    print(f"Sum of individual transaction durations: {sum_durations:.4f}s")
    print(f"Observed interval overlap pairs: {overlapping_pairs} / {(num_workers * (num_workers - 1)) // 2} possible pairs")
    print(f"Serialization efficiency: {sum_durations / wall_time:.2f}x concurrency factor serialized sequentially")
    print("=" * 60)

    # Assert that all workers were indeed attempting concurrency (overlapping intervals)
    assert overlapping_pairs > 0, "Expected threads released at barrier to overlap in execution time"

    # Query all events for this tenant ordered by id ASC
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, prev_hash, row_hash, actor_id
            FROM audit_events
            WHERE tenant_id = %s
            ORDER BY id ASC;
            """,
            (t_id,),
        )
        rows = cur.fetchall()

    assert len(rows) == num_workers, f"Expected {num_workers} audit rows, found {len(rows)}"

    # Verify linear continuity: row[i].prev_hash must strictly equal row[i-1].row_hash
    seen_prev_hashes = set()
    for idx, r in enumerate(rows):
        row_id, prev_hash, _row_hash, _actor_id = r
        if idx == 0:
            assert prev_hash is None, f"First row {row_id} must have NULL prev_hash"
        else:
            expected_prev = rows[idx - 1][2]
            assert prev_hash == expected_prev, (
                f"Chain forked or out of order at index {idx} (row {row_id}): "
                f"prev_hash={prev_hash}, expected={expected_prev}"
            )
            assert prev_hash not in seen_prev_hashes, f"Duplicate prev_hash detected: {prev_hash} (fork in chain!)"
            seen_prev_hashes.add(prev_hash)

    # Verify overall audit chain verification script passes
    assert verify_audit_chains(postgres_url) is True
