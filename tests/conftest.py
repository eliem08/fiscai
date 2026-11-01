"""Pytest configuration and database fixtures for AVENEL test suite.

Connects to existing PostgreSQL 16 (via DATABASE_URL or default 5432) or launches
a transient local Postgres 16 instance.
Applies migrations 001_core, 002_rls, and 003_append_only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Generator
from pathlib import Path

import psycopg
import pytest

from avenel.infrastructure.migrations import apply_migrations

PG_BIN = r"C:\Program Files\PostgreSQL\16\bin"
DEFAULT_TEST_PORT = 5439

# Ensure RIB encryption key is available for integration tests
os.environ.setdefault("AVENEL_KMS_KEY", "avenel-test-kms-key-fixture-32chars-min-ok")


def is_postgres_reachable(url: str) -> bool:
    try:
        with psycopg.connect(url, connect_timeout=1) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1;")
            return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def postgres_url() -> Generator[str, None, None]:
    env_url = os.environ.get("DATABASE_URL")
    if env_url and is_postgres_reachable(env_url):
        print(f"\nUsing existing PostgreSQL at: {env_url}")
        _bootstrap_roles(env_url)
        apply_migrations(env_url)
        yield env_url
        return

    # Launch transient local cluster
    print(f"\nLaunching transient PostgreSQL 16 cluster on port {DEFAULT_TEST_PORT}...")
    temp_dir = os.path.join(tempfile.gettempdir(), "avenel_pytest_pgdata")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)

    initdb_path = os.path.join(PG_BIN, "initdb.exe") if os.name == "nt" else "initdb"
    postgres_path = os.path.join(PG_BIN, "postgres.exe") if os.name == "nt" else "postgres"

    res = subprocess.run(
        [initdb_path, "-D", temp_dir, "-U", "postgres", "-A", "trust", "--no-locale", "-E", "UTF8"],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"initdb failed: {res.stderr}")

    proc = subprocess.Popen(
        [postgres_path, "-D", temp_dir, "-p", str(DEFAULT_TEST_PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)

    cluster_url = f"postgresql://postgres:@localhost:{DEFAULT_TEST_PORT}/postgres"
    os.environ["DATABASE_URL"] = cluster_url

    try:
        _bootstrap_roles(cluster_url)
        apply_migrations(cluster_url)
        yield cluster_url
    finally:
        proc.terminate()
        proc.wait()
        shutil.rmtree(temp_dir, ignore_errors=True)


def _bootstrap_roles(db_url: str) -> None:
    init_sql_path = Path(__file__).resolve().parent.parent / "docker" / "postgres" / "init-roles.sql"
    if init_sql_path.exists():
        sql = init_sql_path.read_text(encoding="utf-8")
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)


@pytest.fixture
def db_conn(postgres_url: str) -> Generator[psycopg.Connection, None, None]:
    """Superuser/owner connection for tests."""
    with psycopg.connect(postgres_url, autocommit=False) as conn:
        yield conn
        conn.rollback()


@pytest.fixture
def app_conn(postgres_url: str) -> Generator[psycopg.Connection, None, None]:
    """Application role connection ('avenel_app', subject to RLS)."""
    # Parse url to connect as avenel_app
    info = psycopg.conninfo.conninfo_to_dict(postgres_url)
    info["user"] = "avenel_app"
    info["password"] = os.environ.get("AVENEL_APP_PASSWORD", "avenel_app_secret")
    app_url = psycopg.conninfo.make_conninfo(**info)
    with psycopg.connect(app_url, autocommit=False) as conn:
        yield conn
        conn.rollback()
