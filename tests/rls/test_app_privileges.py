"""Tests verifying avenel_app role permissions and defense-in-depth immutability.

Per Checklist Item 4:
- avenel_app is not owner of tables
- avenel_app has no BYPASSRLS
- avenel_app is not superuser
- avenel_app gets permission denied on UPDATE/DELETE of audit_events, evidence_records,
  document_versions, extractions even with mutation triggers dropped.
"""

import uuid

import psycopg
import pytest


def test_avenel_app_role_attributes(db_conn: psycopg.Connection):
    """Verify avenel_app is NOSUPERUSER, NOBYPASSRLS."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT rolname, rolsuper, rolbypassrls
            FROM pg_roles
            WHERE rolname = 'avenel_app';
            """
        )
        row = cur.fetchone()
        assert row is not None, "Role avenel_app must exist"
        _rolname, rolsuper, rolbypassrls = row
        assert rolsuper is False, "avenel_app must NEVER be superuser"
        assert rolbypassrls is False, "avenel_app must NEVER have BYPASSRLS"


def test_avenel_app_is_not_table_owner(db_conn: psycopg.Connection):
    """Verify avenel_app does not own any public tables."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT tablename, tableowner
            FROM pg_tables
            WHERE schemaname = 'public' AND tableowner = 'avenel_app';
            """
        )
        owned_tables = cur.fetchall()
        assert len(owned_tables) == 0, f"avenel_app must not own tables, found: {owned_tables}"


def test_permission_denied_on_append_only_tables_with_triggers_dropped(
    db_conn: psycopg.Connection, app_conn: psycopg.Connection
):
    """Defense-in-depth: Even with triggers dropped, avenel_app gets permission denied (table-level revoke) on UPDATE/DELETE."""
    t_id = uuid.uuid4()
    c_id = uuid.uuid4()
    p_id = uuid.uuid4()
    w_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    ev_id = uuid.uuid4()
    ext_id = uuid.uuid4()
    audit_id = None

    # 1. Insert seed data as owner
    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, legal_name) VALUES (%s, 'Tenant PrivTest');", (t_id,))
        cur.execute("INSERT INTO client_entities (id, tenant_id, legal_name) VALUES (%s, %s, 'Company PrivTest');", (c_id, t_id))
        cur.execute(
            """INSERT INTO accounting_periods (id, tenant_id, client_entity_id, period_code, starts_on, ends_on, fiscal_year_end, jurisdiction_pack_version)
               VALUES (%s, %s, %s, '2026-10', '2026-10-01', '2026-10-31', '2026-12-31', 'MA-2026.10.1');""",
            (p_id, t_id, c_id),
        )
        cur.execute(
            """INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code)
               VALUES (%s, %s, %s, %s, 'monthly_bookkeeping');""",
            (w_id, t_id, c_id, p_id),
        )
        cur.execute(
            """INSERT INTO documents (id, tenant_id, client_entity_id, work_request_id, source_channel, original_filename)
               VALUES (%s, %s, %s, %s, 'portal', 'doc.pdf');""",
            (doc_id, t_id, c_id, w_id),
        )
        cur.execute(
            """INSERT INTO document_versions (id, tenant_id, client_entity_id, document_id, version_number, object_key, sha256, mime_type, byte_size)
               VALUES (%s, %s, %s, %s, 1, 'obj/priv', repeat('b', 64), 'application/pdf', 2048);""",
            (ver_id, t_id, c_id, doc_id),
        )
        cur.execute(
            """INSERT INTO evidence_records (id, tenant_id, work_request_id, subject_type, subject_id, kind, payload, content_sha256)
               VALUES (%s, %s, %s, 'document', %s, 'malware_scan', '{"status": "clean"}'::jsonb, repeat('c', 64));""",
            (ev_id, t_id, w_id, doc_id),
        )
        cur.execute(
            """INSERT INTO extractions (id, tenant_id, document_version_id, schema_version, engine, engine_version, status, fields)
               VALUES (%s, %s, %s, 'v1', 'tesseract', '5.0', 'succeeded', '{}'::jsonb);""",
            (ext_id, t_id, ver_id),
        )
        cur.execute(
            """INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, data)
               VALUES (%s, 'system', 'sys', 'test_action', 'document', %s, '{"k":"v"}'::jsonb)
               RETURNING id;""",
            (t_id, str(doc_id)),
        )
        audit_id = cur.fetchone()[0]
    db_conn.commit()

    # 2. DROP triggers on the 4 append-only tables as owner
    try:
        with db_conn.cursor() as cur:
            cur.execute("DROP TRIGGER IF EXISTS audit_no_mutation ON audit_events;")
            cur.execute("DROP TRIGGER IF EXISTS evidence_no_mutation ON evidence_records;")
            cur.execute("DROP TRIGGER IF EXISTS docver_no_mutation ON document_versions;")
            cur.execute("DROP TRIGGER IF EXISTS extraction_no_mutation ON extractions;")
        db_conn.commit()

        # 3. As avenel_app, attempt UPDATE and DELETE on each of the 4 tables
        # Each MUST fail with psycopg.errors.InsufficientPrivilege (code 42501)
        with app_conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, true);", (str(t_id),))

            def assert_denied(query: str, params: tuple):
                cur.execute("SAVEPOINT sp_perm;")
                with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc:
                    cur.execute(query, params)
                assert "permission denied" in str(exc.value).lower()
                cur.execute("ROLLBACK TO SAVEPOINT sp_perm;")

            # Table 1: audit_events
            assert_denied("UPDATE audit_events SET action = 'tampered' WHERE id = %s;", (audit_id,))
            assert_denied("DELETE FROM audit_events WHERE id = %s;", (audit_id,))

            # Table 2: evidence_records
            assert_denied("UPDATE evidence_records SET kind = 'tampered' WHERE id = %s;", (ev_id,))
            assert_denied("DELETE FROM evidence_records WHERE id = %s;", (ev_id,))

            # Table 3: document_versions
            assert_denied("UPDATE document_versions SET byte_size = 9999 WHERE id = %s;", (ver_id,))
            assert_denied("DELETE FROM document_versions WHERE id = %s;", (ver_id,))

            # Table 4: extractions
            assert_denied("UPDATE extractions SET status = 'failed' WHERE id = %s;", (ext_id,))
            assert_denied("DELETE FROM extractions WHERE id = %s;", (ext_id,))

        app_conn.rollback()

    finally:
        # 4. Restore the mutation triggers as owner
        with db_conn.cursor() as cur:
            cur.execute(
                """
                CREATE TRIGGER audit_no_mutation BEFORE UPDATE OR DELETE ON audit_events
                  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
                CREATE TRIGGER evidence_no_mutation BEFORE UPDATE OR DELETE ON evidence_records
                  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
                CREATE TRIGGER docver_no_mutation BEFORE UPDATE OR DELETE ON document_versions
                  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
                CREATE TRIGGER extraction_no_mutation BEFORE UPDATE OR DELETE ON extractions
                  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
                """
            )
        db_conn.commit()
