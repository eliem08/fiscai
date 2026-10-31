"""Integration test verifying complete migrations forward and rollback cycle."""

from avenel.infrastructure.migrations import (
    apply_migrations,
    get_applied_versions,
    get_connection,
    rollback_migration,
)


def test_migrations_forward_and_rollback_cycle(postgres_url: str):
    """Ensure all migrations can be applied, rolled back down, and re-applied cleanly."""
    # 1. Rollback down to clean state
    with get_connection(postgres_url) as conn:
        applied = get_applied_versions(conn)

    for _ in range(len(applied)):
        rb = rollback_migration(postgres_url)
        assert rb is not None

    with get_connection(postgres_url) as conn:
        assert len(get_applied_versions(conn)) == 0

    # 2. Apply up
    applied_up = apply_migrations(postgres_url)
    assert len(applied_up) == 5
    assert applied_up == ["001_core", "002_rls", "003_append_only", "004_fx_rates", "005_rounding_directions"]

    with get_connection(postgres_url) as conn:
        assert get_applied_versions(conn) == {"001", "002", "003", "004", "005"}


def test_migrate_down_refuses_in_production(postgres_url: str, monkeypatch):
    """Ensure rollback_migration refuses immediately when ENV=production or ENVIRONMENT=production."""
    import pytest

    monkeypatch.setenv("ENV", "production")
    with pytest.raises(RuntimeError) as exc_info:
        rollback_migration(postgres_url)
    assert "migrate-down is forbidden when ENV=production" in str(exc_info.value)

    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(RuntimeError) as exc_info:
        rollback_migration(postgres_url)
    assert "migrate-down is forbidden when ENV=production" in str(exc_info.value)

