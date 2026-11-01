"""Export Service per ARCHITECTURE.md Phase 5 and D.4.

Enforces:
- Invariant #7: Export refused when proposal hash changed between approval and export.
- Formatters for Sage 100 CSV, Sage 100 PNM, and Odoo CSV.
- Evidence pack generation (PDF summary + JSON manifest + document hashes + optional source documents).
- Usage records metering (monthly_file billable event, ON CONFLICT DO NOTHING).
- Manual round-trip verification via export_round_trips (never auto-stamped on export).
- Work request transitions: awaiting_approval -> exporting -> completed / completed_with_open_items.
- Signed download URLs expiring in 15 minutes and export.downloaded audit events.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any

import psycopg

from avenel.approvals.service import (
    compute_work_request_subject_hash,
    get_work_request_canonical_proposals_and_matches,
)
from avenel.exports.evidence_pack import (
    bundle_evidence_pack_zip,
    generate_manifest_json,
    generate_summary_pdf,
)
from avenel.exports.metering import record_export_usage
from avenel.exports.odoo_csv import format_odoo_csv
from avenel.exports.sage_csv import format_sage100_csv
from avenel.exports.sage_pnm import format_sage100_pnm
from avenel.infrastructure.storage import get_storage
from avenel.tenancy.auth import require_tenant_context


class ExportError(Exception):
    """Base exception for export errors."""


class ExportApprovalRequiredError(ExportError):
    """Raised when attempting to export without an approved approval."""


class ExportHashMismatchError(ExportError):
    """Raised when proposal hash changed between approval and export (Invariant #7)."""


DOWNLOAD_TOKEN_SECRET = os.environ.get("EXPORT_DOWNLOAD_SECRET", "avenel-export-download-signing-key-2026")


def generate_export_download_token(
    export_id: uuid.UUID,
    kind: str,
    expires_in_seconds: int = 900,  # 15 minutes
    secret_key: str | None = None,
) -> str:
    """Generates an HMAC-SHA256 signed download token expiring in 15 minutes."""
    secret = (secret_key or DOWNLOAD_TOKEN_SECRET).encode()
    expires_at = int(time.time()) + expires_in_seconds
    msg = f"{export_id}:{kind}:{expires_at}".encode()
    sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()
    return f"{expires_at}.{sig}"


def verify_export_download_token(
    token: str,
    export_id: uuid.UUID,
    kind: str,
    secret_key: str | None = None,
) -> bool:
    """Verifies that the download token signature is valid and within the 15-minute window."""
    try:
        parts = token.split(".", 1)
        if len(parts) != 2:
            return False
        expires_at_str, sig = parts
        expires_at = int(expires_at_str)
        if time.time() > expires_at:
            return False
        secret = (secret_key or DOWNLOAD_TOKEN_SECRET).encode()
        msg = f"{export_id}:{kind}:{expires_at}".encode()
        expected_sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected_sig)
    except (ValueError, TypeError):
        return False


def generate_signed_download_urls(
    export_id: uuid.UUID,
    expires_in_seconds: int = 900,
) -> dict[str, str]:
    """Generates signed download URLs for accounting file and evidence pack, expiring in 15 minutes."""
    file_token = generate_export_download_token(export_id, "file", expires_in_seconds)
    pack_token = generate_export_download_token(export_id, "evidence_pack", expires_in_seconds)
    return {
        "file_download_url": f"/v1/exports/{export_id}/file?token={file_token}",
        "evidence_pack_download_url": f"/v1/exports/{export_id}/evidence-pack?token={pack_token}",
    }


def record_export_round_trip(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    export_profile_id: uuid.UUID,
    software: str,
    version: str,
    imported_at: datetime.datetime,
    result: str,
    recorded_by: uuid.UUID,
    notes: str | None = None,
    screenshot_document_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Records an external software round-trip test in export_round_trips, updating verified_round_trip_at on success."""
    require_tenant_context(conn)

    if result not in ("ok", "failed"):
        raise ValueError(f"Résultat de round-trip invalide : {result}")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM export_profiles WHERE tenant_id = %s AND id = %s;",
            (tenant_id, export_profile_id),
        )
        if not cur.fetchone():
            raise ExportError(f"Profil d'exportation {export_profile_id} introuvable.")

        trip_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO export_round_trips (
                id, tenant_id, export_profile_id, software, version,
                imported_at, result, notes, screenshot_document_id,
                recorded_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, recorded_at;
            """,
            (
                trip_id,
                tenant_id,
                export_profile_id,
                software,
                version,
                imported_at,
                result,
                notes,
                screenshot_document_id,
                recorded_by,
            ),
        )
        row = cur.fetchone()
        assert row is not None

        if result == "ok":
            cur.execute(
                """
                UPDATE export_profiles
                SET verified_round_trip_at = %s
                WHERE tenant_id = %s AND id = %s;
                """,
                (imported_at, tenant_id, export_profile_id),
            )

        return {
            "id": str(row[0]),
            "export_profile_id": str(export_profile_id),
            "software": software,
            "version": version,
            "imported_at": imported_at.isoformat(),
            "result": result,
            "notes": notes,
            "screenshot_document_id": str(screenshot_document_id) if screenshot_document_id else None,
            "recorded_at": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
        }


def create_or_get_default_export_profile(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    target: str,
    name: str | None = None,
) -> dict[str, Any]:
    """Ensures a default export profile exists for the specified target."""
    require_tenant_context(conn)

    if target not in ("sage100_csv", "sage100_pnm", "odoo_csv"):
        raise ValueError(f"Cible d'exportation non supportée : {target}")

    encoding = "utf-8" if target == "odoo_csv" else "cp1252"
    profile_name = name or f"Profil standard {target}"

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, target, encoding, config, verified_round_trip_at
            FROM export_profiles
            WHERE tenant_id = %s AND target = %s
            ORDER BY name ASC
            LIMIT 1;
            """,
            (tenant_id, target),
        )
        row = cur.fetchone()
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "target": row[2],
                "encoding": row[3],
                "config": row[4] if isinstance(row[4], dict) else json.loads(row[4]),
                "verified_round_trip_at": row[5],
            }

        prof_id = uuid.uuid4()
        config = {
            "delimiter": ";" if "sage" in target else ",",
            "date_format": "%d%m%Y",
            "decimal_separator": "," if "sage" in target else ".",
            "account_padding": 8 if "sage" in target else 0,
        }
        cur.execute(
            """
            INSERT INTO export_profiles (id, tenant_id, name, target, encoding, config)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, name, target, encoding, config, verified_round_trip_at;
            """,
            (prof_id, tenant_id, profile_name, target, encoding, json.dumps(config)),
        )
        r = cur.fetchone()
        assert r is not None
        return {
            "id": r[0],
            "name": r[1],
            "target": r[2],
            "encoding": r[3],
            "config": r[4] if isinstance(r[4], dict) else json.loads(r[4]),
            "verified_round_trip_at": r[5],
        }


def create_export(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    work_request_id: uuid.UUID,
    approval_id: uuid.UUID,
    export_profile_id: uuid.UUID,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Generates accounting export and evidence pack, enforcing Invariant #7."""
    require_tenant_context(conn)

    with conn.cursor() as cur:
        # 1. Fetch and validate approval
        cur.execute(
            """
            SELECT a.id, a.revision, a.subject_hash, a.status,
                   u.full_name, a.decider_registration_no, a.decided_at,
                   ce.legal_name, ap.period_code
            FROM approvals a
            JOIN client_entities ce ON ce.id = a.client_entity_id AND ce.tenant_id = a.tenant_id
            JOIN work_requests wr ON wr.id = a.work_request_id AND wr.tenant_id = a.tenant_id
            JOIN accounting_periods ap ON ap.id = wr.accounting_period_id AND ap.tenant_id = wr.tenant_id
            LEFT JOIN users u ON u.id = a.decided_by
            WHERE a.tenant_id = %s AND a.id = %s AND a.client_entity_id = %s AND a.work_request_id = %s;
            """,
            (tenant_id, approval_id, client_entity_id, work_request_id),
        )
        app_row = cur.fetchone()
        if not app_row:
            raise ExportApprovalRequiredError("Validation introuvable pour ce dossier.")

        (
            _,
            _app_rev,
            stored_hash,
            app_status,
            approver_name,
            approver_reg_no,
            _decided_at,
            client_name,
            period_code,
        ) = app_row

        if app_status != "approved":
            raise ExportApprovalRequiredError(
                f"L'exportation requiert un dossier validé (statut actuel : {app_status})."
            )

        # Transition work request status: awaiting_approval -> exporting
        cur.execute(
            """
            UPDATE work_requests
            SET status = 'exporting', updated_at = now()
            WHERE tenant_id = %s AND id = %s;
            """,
            (tenant_id, work_request_id),
        )

        # 2. Invariant #7: Verify proposal hash has not changed between approval and export!
        current_hash = compute_work_request_subject_hash(
            conn, tenant_id, client_entity_id, work_request_id
        )
        if current_hash != stored_hash:
            raise ExportHashMismatchError(
                "Le dossier a changé depuis la validation. Demandez une nouvelle validation."
            )

        # 3. Fetch export profile
        cur.execute(
            """
            SELECT id, target, encoding, config
            FROM export_profiles
            WHERE tenant_id = %s AND id = %s;
            """,
            (tenant_id, export_profile_id),
        )
        prof_row = cur.fetchone()
        if not prof_row:
            raise ExportError(f"Profil d'exportation {export_profile_id} introuvable.")

        _, target, _encoding, cfg_raw = prof_row
        config = cfg_raw if isinstance(cfg_raw, dict) else json.loads(cfg_raw)

        # 4. Fetch canonical proposals and lines
        proposals, _matches = get_work_request_canonical_proposals_and_matches(
            conn, tenant_id, client_entity_id, work_request_id
        )

        # 5. Fetch rules applied across proposals
        cur.execute(
            """
            SELECT DISTINCT unnest(rule_refs)
            FROM journal_proposals
            WHERE tenant_id = %s AND client_entity_id = %s AND work_request_id = %s
              AND status = 'approved';
            """,
            (tenant_id, client_entity_id, work_request_id),
        )
        rule_rows = cur.fetchall()
        rules_applied = [r[0] for r in rule_rows if r[0]]

        # 6. Fetch documents attached to this work request
        cur.execute(
            """
            SELECT d.id, d.original_filename, d.doc_type, dv.sha256, dv.page_count
            FROM documents d
            LEFT JOIN document_versions dv ON dv.document_id = d.id AND dv.tenant_id = d.tenant_id
            WHERE d.tenant_id = %s AND d.client_entity_id = %s AND d.work_request_id = %s
            ORDER BY dv.created_at ASC NULLS LAST, d.id ASC;
            """,
            (tenant_id, client_entity_id, work_request_id),
        )
        doc_rows = cur.fetchall()
        documents = [
            {
                "id": str(dr[0]),
                "original_filename": str(dr[1] or ""),
                "doc_type": str(dr[2] or ""),
                "sha256": str(dr[3] or ""),
                "page_count": dr[4] or 1,
            }
            for dr in doc_rows
        ]

    # 7. Format export file
    export_id = uuid.uuid4()
    if target == "sage100_csv":
        export_bytes = format_sage100_csv(proposals, config)
        ext = "csv"
        mime = "text/csv; charset=windows-1252"
    elif target == "sage100_pnm":
        export_bytes = format_sage100_pnm(proposals, config)
        ext = "pnm"
        mime = "text/plain; charset=windows-1252"
    elif target == "odoo_csv":
        export_bytes = format_odoo_csv(proposals, config)
        ext = "csv"
        mime = "text/csv; charset=utf-8"
    else:
        raise ExportError(f"Cible non supportée : {target}")

    file_sha256 = hashlib.sha256(export_bytes).hexdigest()
    export_filename = f"export_{period_code}_{target}.{ext}"
    exported_at_iso = datetime.datetime.now(datetime.UTC).isoformat()

    # 8. Generate Evidence Pack (manifest.json, summary.pdf, evidence_pack.zip)
    manifest_bytes = generate_manifest_json(
        tenant_id=str(tenant_id),
        client_entity_id=str(client_entity_id),
        client_name=client_name,
        work_request_id=str(work_request_id),
        approval_id=str(approval_id),
        export_id=str(export_id),
        export_target=target,
        subject_hash=stored_hash,
        exported_at=exported_at_iso,
        approver_name=approver_name or "Expert-Comptable",
        approver_registration_no=approver_reg_no or "",
        documents=documents,
        proposals=proposals,
        rules_applied=rules_applied,
    )

    pdf_bytes = generate_summary_pdf(
        client_name=client_name,
        period_code=period_code,
        work_request_id=str(work_request_id),
        approval_id=str(approval_id),
        subject_hash=stored_hash,
        approver_name=approver_name or "Expert-Comptable",
        approver_registration_no=approver_reg_no or "",
        export_target=target,
        proposals=proposals,
        documents=documents,
    )

    # Check include_source_documents option (default true)
    include_source_docs = bool(config.get("include_source_documents", True))
    source_documents: list[tuple[str, bytes]] = []
    if include_source_docs:
        storage = get_storage()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.original_filename, dv.object_key
                FROM documents d
                JOIN document_versions dv ON dv.document_id = d.id AND dv.tenant_id = d.tenant_id
                WHERE d.tenant_id = %s AND d.client_entity_id = %s AND d.work_request_id = %s
                ORDER BY dv.created_at ASC NULLS LAST;
                """,
                (tenant_id, client_entity_id, work_request_id),
            )
            for doc_fn, obj_k in cur.fetchall():
                if obj_k and storage.object_exists(obj_k):
                    source_documents.append((doc_fn or "document", storage.get_object(obj_k)))

    evidence_pack_bytes = bundle_evidence_pack_zip(
        export_filename=export_filename,
        export_file_bytes=export_bytes,
        manifest_bytes=manifest_bytes,
        pdf_summary_bytes=pdf_bytes,
        source_documents=source_documents if source_documents else None,
    )

    # 9. Store objects in S3 / storage
    object_key = f"exports/{tenant_id}/{export_id}/{export_filename}"
    evidence_pack_key = f"exports/{tenant_id}/{export_id}/evidence_pack_{period_code}.zip"

    storage = get_storage()
    storage.put_object(object_key, export_bytes, mime)
    storage.put_object(evidence_pack_key, evidence_pack_bytes, "application/zip")

    # 10. Insert exports record and transition work request status
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO exports (
                id, tenant_id, client_entity_id, work_request_id,
                approval_id, export_profile_id, status, object_key,
                file_sha256, evidence_pack_key
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'ready', %s, %s, %s)
            RETURNING id, status, created_at;
            """,
            (
                export_id,
                tenant_id,
                client_entity_id,
                work_request_id,
                approval_id,
                export_profile_id,
                object_key,
                file_sha256,
                evidence_pack_key,
            ),
        )
        exp_row = cur.fetchone()

        # Check if any review issue was resolved with resolution 'accepted_as_is'
        cur.execute(
            """
            SELECT 1 FROM issues
            WHERE tenant_id = %s AND client_entity_id = %s AND work_request_id = %s
              AND resolution = 'accepted_as_is'
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, work_request_id),
        )
        has_open_items = cur.fetchone() is not None
        final_wr_status = "completed_with_open_items" if has_open_items else "completed"

        # Transition work request status: exporting -> completed or completed_with_open_items
        cur.execute(
            """
            UPDATE work_requests
            SET status = %s, completed_at = now(), updated_at = now()
            WHERE tenant_id = %s AND id = %s;
            """,
            (final_wr_status, tenant_id, work_request_id),
        )

    # 11. Record billable usage record (idempotent ON CONFLICT DO NOTHING)
    record_export_usage(
        conn=conn,
        tenant_id=tenant_id,
        client_entity_id=client_entity_id,
        work_request_id=work_request_id,
    )

    download_urls = generate_signed_download_urls(export_id, expires_in_seconds=900)

    assert exp_row is not None
    return {
        "id": str(exp_row[0]),
        "status": exp_row[1],
        "created_at": exp_row[2].isoformat() if hasattr(exp_row[2], "isoformat") else str(exp_row[2]),
        "file_sha256": file_sha256,
        "object_key": object_key,
        "evidence_pack_key": evidence_pack_key,
        "filename": export_filename,
        "subject_hash": stored_hash,
        "work_request_status": final_wr_status,
        "file_download_url": download_urls["file_download_url"],
        "evidence_pack_download_url": download_urls["evidence_pack_download_url"],
    }


def get_export_file(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    export_id: uuid.UUID,
    actor_id: str | None = None,
) -> tuple[bytes, str, str]:
    """Retrieves the accounting export file content and records export.downloaded audit event."""
    require_tenant_context(conn)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.object_key, ep.target
            FROM exports e
            JOIN export_profiles ep ON ep.id = e.export_profile_id AND ep.tenant_id = e.tenant_id
            WHERE e.tenant_id = %s AND e.id = %s AND e.status = 'ready';
            """,
            (tenant_id, export_id),
        )
        row = cur.fetchone()
        if not row:
            raise ExportError(f"Fichier d'export {export_id} introuvable ou non prêt.")

        obj_key, target = row

        ext = "pnm" if target == "sage100_pnm" else "csv"
        mime = "text/csv; charset=windows-1252" if target == "sage100_csv" else ("text/csv; charset=utf-8" if target == "odoo_csv" else "text/plain; charset=windows-1252")
        filename = f"export_{export_id}.{ext}"

        # Record export.downloaded audit event
        cur.execute(
            """
            INSERT INTO audit_events (
                tenant_id, actor_type, actor_id, action, resource_type, resource_id, data
            )
            VALUES (%s, 'user', %s, 'export.downloaded', 'export', %s, %s::jsonb);
            """,
            (tenant_id, actor_id or "system", str(export_id), json.dumps({"kind": "file", "filename": filename})),
        )

    content = get_storage().get_object(obj_key)
    return content, filename, mime


def get_evidence_pack_file(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    export_id: uuid.UUID,
    actor_id: str | None = None,
) -> tuple[bytes, str, str]:
    """Retrieves the evidence pack ZIP archive and records export.downloaded audit event."""
    require_tenant_context(conn)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT evidence_pack_key
            FROM exports
            WHERE tenant_id = %s AND id = %s AND status = 'ready';
            """,
            (tenant_id, export_id),
        )
        row = cur.fetchone()
        if not row or not row[0]:
            raise ExportError(f"Dossier de preuves pour l'export {export_id} introuvable.")

        pack_key = row[0]
        filename = f"evidence_pack_{export_id}.zip"

        # Record export.downloaded audit event
        cur.execute(
            """
            INSERT INTO audit_events (
                tenant_id, actor_type, actor_id, action, resource_type, resource_id, data
            )
            VALUES (%s, 'user', %s, 'export.downloaded', 'export', %s, %s::jsonb);
            """,
            (tenant_id, actor_id or "system", str(export_id), json.dumps({"kind": "evidence_pack", "filename": filename})),
        )

    content = get_storage().get_object(pack_key)
    return content, filename, "application/zip"
