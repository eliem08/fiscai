"""Tests for hash-chained audit events per ARCHITECTURE.md C.4 Invariant 6 & D.3."""

import uuid

import psycopg


def test_audit_event_hash_chaining(db_conn: psycopg.Connection):
    """Audit events are hash-chained per tenant."""
    t1_id = uuid.uuid4()
    t2_id = uuid.uuid4()

    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Tenant Chain 1'), (%s, 'Tenant Chain 2');", (t1_id, t2_id))

        # Event 1 for Tenant 1
        cur.execute(
            """INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, data)
               VALUES (%s, 'user', 'user-1', 'client.create', 'client', 'c-1', '{\"name\":\"Test\"}'::jsonb)
               RETURNING id, prev_hash, row_hash;""",
            (t1_id,),
        )
        _e1_id, e1_prev, e1_row = cur.fetchone()
        assert e1_prev is None
        assert e1_row is not None
        assert len(e1_row) == 64

        # Event 2 for Tenant 1
        cur.execute(
            """INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, data)
               VALUES (%s, 'user', 'user-1', 'client.update', 'client', 'c-1', '{\"name\":\"Updated\"}'::jsonb)
               RETURNING id, prev_hash, row_hash;""",
            (t1_id,),
        )
        _e2_id, e2_prev, e2_row = cur.fetchone()
        # Must chain directly to Event 1's row_hash!
        assert e2_prev == e1_row
        assert e2_row is not None
        assert len(e2_row) == 64
        assert e2_row != e1_row

        # Event 1 for Tenant 2 (independent chain)
        cur.execute(
            """INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, data)
               VALUES (%s, 'user', 'user-2', 'client.create', 'client', 'c-2', '{}'::jsonb)
               RETURNING id, prev_hash, row_hash;""",
            (t2_id,),
        )
        _t2_e1_id, t2_e1_prev, t2_e1_row = cur.fetchone()
        assert t2_e1_prev is None
        assert len(t2_e1_row) == 64
    db_conn.commit()


def test_audit_verify_on_seeded_data_passes(postgres_url: str):
    """Seed sample audit events and confirm verify_audit_chains passes."""
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts.verify_audit_chain import seed_sample_audit_events, verify_audit_chains

    t_id = seed_sample_audit_events(postgres_url)
    assert t_id is not None
    assert verify_audit_chains(postgres_url, fail_on_empty=True) is True


def test_audit_verify_detects_tampering_and_exits_non_zero(postgres_url: str, db_conn: psycopg.Connection):
    """Tamper one row as owner with trigger disabled: verify must detect mismatch and exit non-zero."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts.verify_audit_chain import verify_audit_chains

    t_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Tamper Test Tenant');", (t_id,))
        event_ids = []
        for i in range(3):
            cur.execute(
                """
                INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, data)
                VALUES (%s, 'user', 'u-tamper', 'action.seed', 'res', %s, %s::jsonb)
                RETURNING id;
                """,
                (t_id, str(i), f'{{"count": {i}}}'),
            )
            event_ids.append(cur.fetchone()[0])
    db_conn.commit()

    # Tamper the middle row as superuser/owner with trigger temporarily disabled
    with db_conn.cursor() as cur:
        cur.execute("ALTER TABLE audit_events DISABLE TRIGGER audit_no_mutation;")
        cur.execute(
            "UPDATE audit_events SET data = '{\"count\": 999, \"tampered\": true}'::jsonb WHERE id = %s;",
            (event_ids[1],),
        )
        cur.execute("ALTER TABLE audit_events ENABLE TRIGGER audit_no_mutation;")
    db_conn.commit()

    try:
        # 1. Direct verify function call returns False
        assert verify_audit_chains(postgres_url) is False

        # 2. CLI script exits non-zero (returncode != 0)
        proc = subprocess.run(
            [sys.executable, str(repo_root / "scripts" / "verify_audit_chain.py")],
            env={**os.environ, "DATABASE_URL": postgres_url},
            capture_output=True,
            text=True,
        )
        assert proc.returncode != 0
        assert "[AUDIT-VERIFY FAILED]" in proc.stdout or "[AUDIT-VERIFY FAILED]" in proc.stderr
    finally:
        # Clean up tampered rows so subsequent tests in shared session are not poisoned
        with db_conn.cursor() as cur:
            cur.execute("ALTER TABLE audit_events DISABLE TRIGGER audit_no_mutation;")
            cur.execute("DELETE FROM audit_events WHERE tenant_id = %s;", (t_id,))
            cur.execute("ALTER TABLE audit_events ENABLE TRIGGER audit_no_mutation;")
            cur.execute("DELETE FROM tenants WHERE id = %s;", (t_id,))
        db_conn.commit()

