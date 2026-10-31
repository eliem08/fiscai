"""SQL Migration Runner for AVENEL (Phase 0).

Executes numbered SQL migrations forward and backward against PostgreSQL 16.
Maintains applied migration versions in `app.schema_migrations`.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "db" / "migrations"


def get_connection(db_url: str | None = None) -> psycopg.Connection:
    url = db_url or os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/avenel"
    )
    return psycopg.connect(url, autocommit=False)


def ensure_migration_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS app;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app.schema_migrations (
                version text PRIMARY KEY,
                name text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now()
            );
            """
        )
    conn.commit()


def get_applied_versions(conn: psycopg.Connection) -> set[str]:
    ensure_migration_table(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM app.schema_migrations ORDER BY version;")
        return {row[0] for row in cur.fetchall()}


def discover_migrations(direction: str = "up") -> list[tuple[str, str, Path]]:
    """Discover migrations matching pattern `<version>_<name>.<direction>.sql`."""
    pattern = re.compile(rf"^(\d{{3}})_([a-zA-Z0-9_]+)\.{direction}\.sql$")
    migrations: list[tuple[str, str, Path]] = []
    if not MIGRATIONS_DIR.exists():
        return migrations

    for p in MIGRATIONS_DIR.glob(f"*.{direction}.sql"):
        m = pattern.match(p.name)
        if m:
            version, name = m.group(1), m.group(2)
            migrations.append((version, name, p))

    migrations.sort(key=lambda x: x[0], reverse=(direction == "down"))
    return migrations


def apply_migrations(db_url: str | None = None) -> list[str]:
    """Apply all pending forward migrations."""
    applied: list[str] = []
    with get_connection(db_url) as conn:
        applied_versions = get_applied_versions(conn)
        pending = [m for m in discover_migrations("up") if m[0] not in applied_versions]

        for version, name, path in pending:
            print(f"Applying migration {version}_{name} from {path.name}...")
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO app.schema_migrations (version, name) VALUES (%s, %s);",
                    (version, name),
                )
            conn.commit()
            applied.append(f"{version}_{name}")
            print(f"Applied {version}_{name} successfully.")
    return applied


def rollback_migration(db_url: str | None = None) -> str | None:
    """Roll back the most recently applied migration. Refuses in production."""
    env = os.environ.get("ENV", os.environ.get("ENVIRONMENT", "")).lower()
    if env == "production":
        raise RuntimeError("migrate-down is forbidden when ENV=production")

    with get_connection(db_url) as conn:
        applied_versions = get_applied_versions(conn)
        if not applied_versions:
            print("No migrations to rollback.")
            return None

        latest_version = max(applied_versions)
        downs = {m[0]: m for m in discover_migrations("down")}
        if latest_version not in downs:
            raise RuntimeError(f"No down migration found for version {latest_version}")

        version, name, path = downs[latest_version]
        print(f"Rolling back migration {version}_{name}...")
        sql = path.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute("DELETE FROM app.schema_migrations WHERE version = %s;", (version,))
        conn.commit()
        print(f"Rolled back {version}_{name} successfully.")
        return f"{version}_{name}"


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "up"
    if action == "down":
        rollback_migration()
    else:
        apply_migrations()
