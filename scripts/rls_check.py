"""RLS Check script per ARCHITECTURE.md Section C.5.

Queries `pg_class` and fails if any table with a `tenant_id` column lacks forced RLS or a policy.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import psycopg

from avenel.infrastructure.migrations import apply_migrations

RLS_CHECK_QUERY = """
SELECT
    c.relname AS table_name,
    c.relrowsecurity AS rls_enabled,
    c.relforcerowsecurity AS rls_forced,
    COALESCE(pol.policy_count, 0) AS policy_count
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id'
LEFT JOIN (
    SELECT polrelid, count(*) AS policy_count
    FROM pg_policy
    GROUP BY polrelid
) pol ON pol.polrelid = c.oid
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND (
    NOT c.relrowsecurity
    OR NOT c.relforcerowsecurity
    OR COALESCE(pol.policy_count, 0) = 0
  )
ORDER BY c.relname;
"""

VERIFY_ALL_TENANT_TABLES_QUERY = """
SELECT
    c.relname AS table_name,
    c.relrowsecurity AS rls_enabled,
    c.relforcerowsecurity AS rls_forced,
    COALESCE(pol.policy_count, 0) AS policy_count
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id'
LEFT JOIN (
    SELECT polrelid, count(*) AS policy_count
    FROM pg_policy
    GROUP BY polrelid
) pol ON pol.polrelid = c.oid
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY c.relname;
"""


def _run_query_on_url(url: str) -> bool:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(VERIFY_ALL_TENANT_TABLES_QUERY)
        all_tables = cur.fetchall()
        if not all_tables:
            print("WARNING: No tables with tenant_id found in database.")
            return False

        print(f"Found {len(all_tables)} tables with tenant_id:")
        for t_name, enabled, forced, pol_count in all_tables:
            print(f"  - {t_name}: rls_enabled={enabled}, rls_forced={forced}, policies={pol_count}")

        cur.execute(RLS_CHECK_QUERY)
        violations = cur.fetchall()

        if violations:
            print("\n[RLS-CHECK FAILED] Tables violating forced RLS or missing policies:")
            for row in violations:
                print(f"  FAILED: {row[0]} (enabled={row[1]}, forced={row[2]}, policies={row[3]})")
            return False

        print(f"\n[RLS-CHECK PASSED] All {len(all_tables)} tables with tenant_id have forced RLS and tenant policy.")
        return True


def check_rls(db_url: str | None = None) -> bool:
    url = db_url or os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/avenel"
    )
    try:
        return _run_query_on_url(url)
    except Exception:
        if db_url:
            raise
        # If default connection fails, launch a transient local cluster
        pg_bin = r"C:\Program Files\PostgreSQL\16\bin"
        port = 5441
        temp_dir = os.path.join(tempfile.gettempdir(), "avenel_rls_pgdata")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

        initdb_cmd = os.path.join(pg_bin, "initdb.exe") if os.name == "nt" else "initdb"
        postgres_cmd = os.path.join(pg_bin, "postgres.exe") if os.name == "nt" else "postgres"

        subprocess.run(
            [initdb_cmd, "-D", temp_dir, "-U", "postgres", "-A", "trust", "--no-locale", "-E", "UTF8"],
            capture_output=True,
            text=True,
            check=True,
        )
        proc = subprocess.Popen(
            [postgres_cmd, "-D", temp_dir, "-p", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)

        transient_url = f"postgresql://postgres:@localhost:{port}/postgres"
        try:
            init_sql = Path(__file__).resolve().parent.parent / "docker" / "postgres" / "init-roles.sql"
            if init_sql.exists():
                with psycopg.connect(transient_url, autocommit=True) as conn, conn.cursor() as cur:
                    cur.execute(init_sql.read_text(encoding="utf-8"))
            apply_migrations(transient_url)
            return _run_query_on_url(transient_url)
        finally:
            proc.terminate()
            proc.wait()
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    passed = check_rls()
    sys.exit(0 if passed else 1)
