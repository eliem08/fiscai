"""Review effort tracking and internal operational metrics per Phase 5b.

Tracks:
- Active human review time per user per monthly file
- Fields corrected in DocumentViewer
- Accounting entries edited or confirmed
- Issues resolved (accepted_as_is or fixed)
- Cost per accepted file from provider_calls and usage_records
"""

from __future__ import annotations

import uuid
from typing import Any

import psycopg

from avenel.tenancy.auth import require_tenant_context


def record_review_effort(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    work_request_id: uuid.UUID,
    user_id: uuid.UUID,
    active_review_seconds: int = 0,
    fields_corrected: int = 0,
    entries_edited: int = 0,
    issues_resolved: int = 0,
) -> dict[str, Any]:
    """Upserts review effort metrics for a user on a given monthly file."""
    require_tenant_context(conn)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO review_effort_metrics (
                tenant_id, work_request_id, user_id,
                active_review_seconds, fields_corrected,
                entries_edited, issues_resolved, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (tenant_id, work_request_id, user_id)
            DO UPDATE SET
                active_review_seconds = review_effort_metrics.active_review_seconds + EXCLUDED.active_review_seconds,
                fields_corrected = review_effort_metrics.fields_corrected + EXCLUDED.fields_corrected,
                entries_edited = review_effort_metrics.entries_edited + EXCLUDED.entries_edited,
                issues_resolved = review_effort_metrics.issues_resolved + EXCLUDED.issues_resolved,
                updated_at = now()
            RETURNING id, tenant_id, work_request_id, user_id, active_review_seconds, fields_corrected, entries_edited, issues_resolved;
            """,
            (
                tenant_id,
                work_request_id,
                user_id,
                max(0, active_review_seconds),
                max(0, fields_corrected),
                max(0, entries_edited),
                max(0, issues_resolved),
            ),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError("Failed to record review effort metrics")

        return {
            "id": str(row[0]),
            "tenant_id": str(row[1]),
            "work_request_id": str(row[2]),
            "user_id": str(row[3]),
            "active_review_seconds": row[4],
            "fields_corrected": row[5],
            "entries_edited": row[6],
            "issues_resolved": row[7],
        }


def get_internal_metrics_summary(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
) -> dict[str, Any]:
    """Retrieves full review effort and cost metrics across all monthly files for owner and operator roles."""
    require_tenant_context(conn)

    with conn.cursor() as cur:
        # 1. Fetch review effort per file and user (counts and field keys only, never field values or identifiers)
        cur.execute(
            """
            SELECT
                r.work_request_id,
                w.status AS work_request_status,
                ce.name AS client_name,
                p.period_name,
                u.id AS user_id,
                u.full_name AS user_name,
                u.email AS user_email,
                r.active_review_seconds,
                r.fields_corrected,
                r.entries_edited,
                r.issues_resolved,
                r.updated_at
            FROM review_effort_metrics r
            JOIN work_requests w ON w.tenant_id = r.tenant_id AND w.id = r.work_request_id
            JOIN client_entities ce ON ce.tenant_id = w.tenant_id AND ce.id = w.client_entity_id
            JOIN accounting_periods p ON p.tenant_id = w.tenant_id AND p.id = w.period_id
            JOIN users u ON u.id = r.user_id
            WHERE r.tenant_id = %s
            ORDER BY r.updated_at DESC;
            """,
            (tenant_id,),
        )
        effort_rows = cur.fetchall()

        # 2. Fetch provider costs per tenant
        cur.execute(
            """
            SELECT
                COALESCE(sum(cost_mad), 0.0) AS total_provider_cost_mad,
                count(*) AS total_provider_calls,
                count(*) FILTER (WHERE status = 'succeeded') AS succeeded_calls,
                count(*) FILTER (WHERE status = 'refused_by_policy') AS refused_calls
            FROM provider_calls
            WHERE tenant_id = %s;
            """,
            (tenant_id,),
        )
        prow = cur.fetchone()
        provider_cost_mad = float(prow[0]) if prow else 0.0
        provider_calls_count = prow[1] if prow else 0

        # 3. Fetch usage billing records (e.g. accepted monthly files)
        cur.execute(
            """
            SELECT
                work_request_id,
                unit,
                quantity,
                billable,
                price_version,
                created_at
            FROM usage_records
            WHERE tenant_id = %s
            ORDER BY created_at DESC;
            """,
            (tenant_id,),
        )
        usage_rows = cur.fetchall()

    files_map: dict[str, dict[str, Any]] = {}
    total_seconds = 0
    total_corrected = 0
    total_edited = 0
    total_resolved = 0

    for row in effort_rows:
        wr_id = str(row[0])
        total_seconds += row[7]
        total_corrected += row[8]
        total_edited += row[9]
        total_resolved += row[10]

        if wr_id not in files_map:
            files_map[wr_id] = {
                "work_request_id": wr_id,
                "status": row[1],
                "client_name": row[2],
                "period_name": row[3],
                "users": [],
                "file_review_seconds": 0,
                "file_fields_corrected": 0,
                "file_entries_edited": 0,
                "file_issues_resolved": 0,
                "provider_cost_mad": 0.0,
                "provider_cost_per_accepted_file_mad": 0.0,
                "cost_per_accepted_file_mad": 0.0,
                "compute_cost": {
                    "status": "not_computed_yet",
                    "label_fr": "Coût calcul serveur (estimé)",
                    "label_en": "Compute cost (estimated)",
                    "amount_mad": None,
                },
                "reviewer_cost": {
                    "status": "not_computed_yet",
                    "label_fr": "Coût réviseur humain",
                    "label_en": "Reviewer cost",
                    "amount_mad": None,
                },
                "billable_units": 0,
            }

        files_map[wr_id]["users"].append({
            "user_id": str(row[4]),
            "user_name": row[5],
            "user_email": row[6],
            "active_review_seconds": row[7],
            "fields_corrected": row[8],
            "entries_edited": row[9],
            "issues_resolved": row[10],
        })
        files_map[wr_id]["file_review_seconds"] += row[7]
        files_map[wr_id]["file_fields_corrected"] += row[8]
        files_map[wr_id]["file_entries_edited"] += row[9]
        files_map[wr_id]["file_issues_resolved"] += row[10]

    # Map usage records to files
    accepted_files_count = 0
    for urow in usage_rows:
        wr_id = str(urow[0])
        if urow[1] == "monthly_file" and urow[3]:  # billable
            accepted_files_count += 1
        if wr_id in files_map:
            files_map[wr_id]["billable_units"] += float(urow[2])

    # Allocate provider cost evenly across active files or per file
    files_count = len(files_map) or 1
    per_file_provider_cost = provider_cost_mad / files_count
    for f in files_map.values():
        f["provider_cost_mad"] = round(per_file_provider_cost, 4)
        f["provider_cost_per_accepted_file_mad"] = round(per_file_provider_cost, 4)
        f["cost_per_accepted_file_mad"] = round(per_file_provider_cost, 4)

    provider_cost_per_file = round(provider_cost_mad / max(1, accepted_files_count), 4)
    return {
        "summary": {
            "total_active_review_seconds": total_seconds,
            "total_active_review_minutes": round(total_seconds / 60.0, 1),
            "total_fields_corrected": total_corrected,
            "total_entries_edited": total_edited,
            "total_issues_resolved": total_resolved,
            "total_provider_calls": provider_calls_count,
            "total_provider_cost_mad": round(provider_cost_mad, 4),
            "accepted_files_count": accepted_files_count,
            "provider_cost_label_fr": "Coût fournisseurs par dossier validé",
            "provider_cost_label_en": "Provider cost per accepted file",
            "provider_cost_per_accepted_file_mad": provider_cost_per_file,
            "average_cost_per_file_mad": provider_cost_per_file,
            "compute_cost": {
                "status": "not_computed_yet",
                "label_fr": "Coût calcul serveur (estimé)",
                "label_en": "Compute cost (estimated)",
                "amount_mad": None,
            },
            "reviewer_cost": {
                "status": "not_computed_yet",
                "label_fr": "Coût réviseur humain",
                "label_en": "Reviewer cost",
                "amount_mad": None,
            },
        },
        "files": list(files_map.values()),
    }

