"""Golden export tests for Sage 100 and Odoo accounting exporters.

Asserts byte-identical golden outputs for:
- Sage 100 CSV (CP1252, semicolon-delimited, CRLF)
- Sage 100 PNM (CP1252, native PNM format, CRLF)
- Odoo CSV (UTF-8, comma-delimited, multi-line moves, CRLF)
- Evidence Pack (ZIP containing export file, manifest.json, and valid PDF summary)
"""

from __future__ import annotations

import datetime
import io
import json
import uuid
import zipfile

import psycopg
import pytest

from avenel.approvals.service import (
    decide_work_request_approval,
    request_work_request_approval,
)
from avenel.clients.service import create_client_entity
from avenel.exports.evidence_pack import (
    bundle_evidence_pack_zip,
    generate_manifest_json,
    generate_summary_pdf,
)
from avenel.exports.odoo_csv import format_odoo_csv
from avenel.exports.sage_csv import format_sage100_csv
from avenel.exports.sage_pnm import format_sage100_pnm
from avenel.exports.service import (
    create_export,
    create_or_get_default_export_profile,
    generate_export_download_token,
    get_evidence_pack_file,
    get_export_file,
    record_export_round_trip,
    verify_export_download_token,
)
from avenel.periods.service import open_accounting_period
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user


def get_sample_proposals_for_export() -> list[dict]:
    """Provides a deterministic set of proposals across ACH, VTE, and BQ journals."""
    return [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "journal_code": "ACH",
            "entry_date": "2026-09-12",
            "label": "Facture FA-2026-088 Fournisseur Maroc",
            "piece_number": "FA-2026-088",
            "reference": "FA-2026-088",
            "lines": [
                {
                    "line_no": 1,
                    "account_code": "6111000",
                    "label": "Achats de marchandises",
                    "counterparty_code": "",
                    "debit_mad": "10000.00",
                    "credit_mad": "0.00",
                },
                {
                    "line_no": 2,
                    "account_code": "3455200",
                    "label": "TVA récupérable sur charges",
                    "counterparty_code": "",
                    "debit_mad": "2000.00",
                    "credit_mad": "0.00",
                },
                {
                    "line_no": 3,
                    "account_code": "4411000",
                    "label": "Fournisseur Maroc",
                    "counterparty_code": "44110001",
                    "debit_mad": "0.00",
                    "credit_mad": "12000.00",
                },
            ],
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "journal_code": "BQ",
            "entry_date": "2026-09-15",
            "label": "Virement Fournisseur Maroc",
            "piece_number": "VIR-2026-0915",
            "reference": "VIR-2026-0915",
            "lines": [
                {
                    "line_no": 1,
                    "account_code": "4411000",
                    "label": "Règlement Fournisseur",
                    "counterparty_code": "44110001",
                    "debit_mad": "12000.00",
                    "credit_mad": "0.00",
                },
                {
                    "line_no": 2,
                    "account_code": "5141000",
                    "label": "Banque Populaire",
                    "counterparty_code": "",
                    "debit_mad": "0.00",
                    "credit_mad": "12000.00",
                },
            ],
        },
    ]


def test_golden_sage100_csv_byte_identical():
    """Asserts that Sage 100 CSV exporter produces byte-identical golden output."""
    proposals = get_sample_proposals_for_export()
    config = {
        "delimiter": ";",
        "date_format": "%d%m%Y",
        "decimal_separator": ",",
        "account_padding": 8,
    }

    actual_bytes = format_sage100_csv(proposals, config)

    # Expected CP1252 lines with CRLF
    expected_lines = [
        "ACH;12092026;FA-2026-088;FA-2026-088;61110000;;Achats de marchandises;10000,00;0,00",
        "ACH;12092026;FA-2026-088;FA-2026-088;34552000;;TVA récupérable sur charges;2000,00;0,00",
        "ACH;12092026;FA-2026-088;FA-2026-088;44110000;44110001;Fournisseur Maroc;0,00;12000,00",
        "BQ;15092026;VIR-2026-0915;VIR-2026-0915;44110000;44110001;Règlement Fournisseur;12000,00;0,00",
        "BQ;15092026;VIR-2026-0915;VIR-2026-0915;51410000;;Banque Populaire;0,00;12000,00",
    ]
    expected_text = "\r\n".join(expected_lines) + "\r\n"
    expected_bytes = expected_text.encode("cp1252")

    assert actual_bytes == expected_bytes, "Sage 100 CSV output must be byte-identical to golden reference."


def test_golden_sage100_pnm_byte_identical():
    """Asserts that Sage 100 PNM exporter produces byte-identical golden output."""
    proposals = get_sample_proposals_for_export()
    config = {
        "delimiter": ";",
        "decimal_separator": ",",
        "account_padding": 8,
    }

    actual_bytes = format_sage100_pnm(proposals, config)

    expected_lines = [
        "#FORMAT_PNM",
        "ACH;120926;FA-2026-088;FA-2026-088;61110000;;Achats de marchandises;D;10000,00;",
        "ACH;120926;FA-2026-088;FA-2026-088;34552000;;TVA récupérable sur charges;D;2000,00;",
        "ACH;120926;FA-2026-088;FA-2026-088;44110000;44110001;Fournisseur Maroc;C;12000,00;",
        "BQ;150926;VIR-2026-0915;VIR-2026-0915;44110000;44110001;Règlement Fournisseur;D;12000,00;",
        "BQ;150926;VIR-2026-0915;VIR-2026-0915;51410000;;Banque Populaire;C;12000,00;",
    ]
    expected_text = "\r\n".join(expected_lines) + "\r\n"
    expected_bytes = expected_text.encode("cp1252")

    assert actual_bytes == expected_bytes, "Sage 100 PNM output must be byte-identical to golden reference."


def test_golden_odoo_csv_byte_identical():
    """Asserts that Odoo CSV exporter produces byte-identical golden output."""
    proposals = get_sample_proposals_for_export()
    config = {
        "delimiter": ",",
    }

    actual_bytes = format_odoo_csv(proposals, config)

    expected_lines = [
        "id,date,ref,journal_id,line_ids/account_id,line_ids/partner_id,line_ids/name,line_ids/debit,line_ids/credit",
        "avenel_move_11111111-1111-1111-1111-111111111111,2026-09-12,FA-2026-088,ACH,6111000,,Achats de marchandises,10000.00,0.00",
        "avenel_move_11111111-1111-1111-1111-111111111111,,,,3455200,,TVA récupérable sur charges,2000.00,0.00",
        "avenel_move_11111111-1111-1111-1111-111111111111,,,,4411000,44110001,Fournisseur Maroc,0.00,12000.00",
        "avenel_move_22222222-2222-2222-2222-222222222222,2026-09-15,VIR-2026-0915,BQ,4411000,44110001,Règlement Fournisseur,12000.00,0.00",
        "avenel_move_22222222-2222-2222-2222-222222222222,,,,5141000,,Banque Populaire,0.00,12000.00",
    ]
    expected_text = "\r\n".join(expected_lines) + "\r\n"
    expected_bytes = expected_text.encode("utf-8")

    assert actual_bytes == expected_bytes, "Odoo CSV output must be byte-identical to golden reference."


def test_evidence_pack_zip_bundle_and_artifacts():
    """Asserts that the evidence pack generates a valid manifest, valid PDF, and well-formed ZIP."""
    proposals = get_sample_proposals_for_export()
    documents = [
        {
            "id": "doc-001",
            "original_filename": "facture_088.pdf",
            "doc_type": "purchase_invoice",
            "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "page_count": 1,
        }
    ]
    manifest_bytes = generate_manifest_json(
        tenant_id="t-001",
        client_entity_id="c-001",
        client_name="Atlas Trading SARL",
        work_request_id="wr-001",
        approval_id="app-001",
        export_id="exp-001",
        export_target="sage100_csv",
        subject_hash="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        exported_at="2026-10-01T10:00:00Z",
        approver_name="Karim Bennani",
        approver_registration_no="OEC-12345",
        documents=documents,
        proposals=proposals,
        rules_applied=["vat.rate.standard", "cgnc.rules"],
    )

    manifest_obj = json.loads(manifest_bytes.decode("utf-8"))
    assert manifest_obj["schema_version"] == "1.0"
    assert manifest_obj["subject_hash"] == "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    assert manifest_obj["summary"]["proposals_count"] == 2
    assert manifest_obj["summary"]["total_debit_mad"] == "24000.00"
    assert manifest_obj["summary"]["total_credit_mad"] == "24000.00"

    pdf_bytes = generate_summary_pdf(
        client_name="Atlas Trading SARL",
        period_code="2026-09",
        work_request_id="wr-001",
        approval_id="app-001",
        subject_hash="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        approver_name="Karim Bennani",
        approver_registration_no="OEC-12345",
        export_target="sage100_csv",
        proposals=proposals,
        documents=documents,
    )
    assert pdf_bytes.startswith(b"%PDF-"), "Generated summary must be a valid PDF document."

    export_file_bytes = format_sage100_csv(proposals)
    zip_bytes = bundle_evidence_pack_zip(
        export_filename="export_2026-09_sage100_csv.csv",
        export_file_bytes=export_file_bytes,
        manifest_bytes=manifest_bytes,
        pdf_summary_bytes=pdf_bytes,
    )

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert "export_2026-09_sage100_csv.csv" in namelist
        assert "manifest.json" in namelist
        assert "summary.pdf" in namelist

        # Verify uncompressed content
        assert zf.read("export_2026-09_sage100_csv.csv") == export_file_bytes
        assert zf.read("manifest.json") == manifest_bytes
        assert zf.read("summary.pdf") == pdf_bytes


def test_bundle_evidence_pack_zip_with_source_documents():
    """Asserts that evidence pack includes raw documents in documents/ directory when supplied."""
    proposals = get_sample_proposals_for_export()
    export_file_bytes = format_sage100_csv(proposals)
    manifest_bytes = b'{"status": "ok"}'
    pdf_bytes = b"%PDF-1.4 sample pdf"
    source_docs = [
        ("facture_achat_001.pdf", b"%PDF-1.4 source document 1"),
        ("facture_achat_002.pdf", b"%PDF-1.4 source document 2"),
    ]

    zip_bytes = bundle_evidence_pack_zip(
        export_filename="export_sage.csv",
        export_file_bytes=export_file_bytes,
        manifest_bytes=manifest_bytes,
        pdf_summary_bytes=pdf_bytes,
        source_documents=source_docs,
    )

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert "export_sage.csv" in namelist
        assert "manifest.json" in namelist
        assert "summary.pdf" in namelist
        assert "documents/facture_achat_001.pdf" in namelist
        assert "documents/facture_achat_002.pdf" in namelist
        assert zf.read("documents/facture_achat_001.pdf") == b"%PDF-1.4 source document 1"


def test_export_does_not_modify_export_profile(db_conn: psycopg.Connection):
    """create_export must never update verified_round_trip_at on export_profiles."""
    tenant_id = seed_tenant(db_conn, "Export Profile Immuta Cabinet")
    sub = f"oec-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "owner", professional_title="expert_comptable", professional_registration_no="OEC-999")
    set_rls_context(db_conn, tenant_id, user_id)

    client = create_client_entity(db_conn, tenant_id, "Société Export Test SARL", actor_id=str(user_id))
    period = open_accounting_period(
        db_conn, tenant_id, client.id, actor_id=str(user_id),
        period_code="2026-10", starts_on=datetime.date(2026, 10, 1),
        ends_on=datetime.date(2026, 10, 31), fiscal_year_end=datetime.date(2026, 12, 31)
    )

    wr_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code, status)
            VALUES (%s, %s, %s, %s, 'monthly_bookkeeping', 'awaiting_approval');
            """,
            (wr_id, tenant_id, client.id, period["id"]),
        )
        prop_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by, status)
            VALUES (%s, %s, %s, %s, 1, 'ACH', '2026-10-10', 'Test', 'rules', 'proposed');
            """,
            (prop_id, tenant_id, client.id, wr_id),
        )
        acc_id1 = uuid.uuid4()
        acc_id2 = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label, source)
            VALUES (%s, %s, %s, '6111000', 'Achats', 'cgnc_seed'),
                   (%s, %s, %s, '4411000', 'Fournisseurs', 'cgnc_seed');
            """,
            (acc_id1, tenant_id, client.id, acc_id2, tenant_id, client.id),
        )
        cur.execute(
            """
            INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad)
            VALUES (%s, %s, %s, %s, 1, %s, '6111000', 'Achats', 'MAD', 100.0, 0.0, 100.0, 0.0),
                   (%s, %s, %s, %s, 2, %s, '4411000', 'Fournisseurs', 'MAD', 0.0, 100.0, 0.0, 100.0);
            """,
            (uuid.uuid4(), tenant_id, client.id, prop_id, acc_id1, uuid.uuid4(), tenant_id, client.id, prop_id, acc_id2),
        )
    db_conn.commit()

    req = request_work_request_approval(db_conn, tenant_id, client.id, wr_id, user_id, single_person_policy=True)
    decide_work_request_approval(db_conn, tenant_id, uuid.UUID(req["id"]), user_id, "approved", "Validé", expected_subject_hash=req["subject_hash"])
    db_conn.commit()

    prof = create_or_get_default_export_profile(db_conn, tenant_id, "sage100_csv")
    assert prof["verified_round_trip_at"] is None

    # Call create_export
    exp = create_export(db_conn, tenant_id, client.id, wr_id, uuid.UUID(req["id"]), prof["id"])
    assert exp["status"] == "ready"
    db_conn.commit()

    # Profile must remain unmodified! verified_round_trip_at must STILL be None!
    with db_conn.cursor() as cur:
        cur.execute("SELECT verified_round_trip_at FROM export_profiles WHERE tenant_id = %s AND id = %s;", (tenant_id, prof["id"]))
        row = cur.fetchone()
        assert row is not None
        assert row[0] is None, "create_export must NEVER auto-stamp verified_round_trip_at on export_profiles!"


def test_manual_record_round_trip(db_conn: psycopg.Connection):
    """Recording round trips via record_export_round_trip stores rows and sets verified_round_trip_at on ok."""
    tenant_id = seed_tenant(db_conn, "Round Trip Cabinet")
    sub = f"mgr-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "manager")
    set_rls_context(db_conn, tenant_id, user_id)

    prof = create_or_get_default_export_profile(db_conn, tenant_id, "odoo_csv")
    assert prof["verified_round_trip_at"] is None

    import_time = datetime.datetime(2026, 10, 25, 14, 30, tzinfo=datetime.timezone.utc)

    # 1. Record failed test -> recorded in export_round_trips but does NOT set verified_round_trip_at
    res_fail = record_export_round_trip(
        conn=db_conn,
        tenant_id=tenant_id,
        export_profile_id=prof["id"],
        software="Odoo Enterprise",
        version="17.0",
        imported_at=import_time,
        result="failed",
        recorded_by=user_id,
        notes="Erreur d'encodage sur le séparateur décimal",
    )
    assert res_fail["result"] == "failed"
    db_conn.commit()

    with db_conn.cursor() as cur:
        cur.execute("SELECT verified_round_trip_at FROM export_profiles WHERE tenant_id = %s AND id = %s;", (tenant_id, prof["id"]))
        assert cur.fetchone()[0] is None

    # 2. Record successful test -> sets verified_round_trip_at!
    res_ok = record_export_round_trip(
        conn=db_conn,
        tenant_id=tenant_id,
        export_profile_id=prof["id"],
        software="Odoo Enterprise",
        version="17.0",
        imported_at=import_time,
        result="ok",
        recorded_by=user_id,
        notes="Importation réussie avec 45 pièces sans anomalie",
    )
    assert res_ok["result"] == "ok"
    db_conn.commit()

    with db_conn.cursor() as cur:
        cur.execute("SELECT verified_round_trip_at FROM export_profiles WHERE tenant_id = %s AND id = %s;", (tenant_id, prof["id"]))
        assert cur.fetchone()[0] is not None


def test_reexport_idempotent_no_double_billing(db_conn: psycopg.Connection):
    """Calling create_export multiple times is idempotent and inserts exactly one billable usage record."""
    tenant_id = seed_tenant(db_conn, "Idempotent Export Cabinet")
    sub = f"oec-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "owner", professional_title="expert_comptable", professional_registration_no="OEC-101")
    set_rls_context(db_conn, tenant_id, user_id)

    client = create_client_entity(db_conn, tenant_id, "Idempotent Client SARL", actor_id=str(user_id))
    period = open_accounting_period(
        db_conn, tenant_id, client.id, actor_id=str(user_id),
        period_code="2026-11", starts_on=datetime.date(2026, 11, 1),
        ends_on=datetime.date(2026, 11, 30), fiscal_year_end=datetime.date(2026, 12, 31)
    )

    wr_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code, status)
            VALUES (%s, %s, %s, %s, 'monthly_bookkeeping', 'awaiting_approval');
            """,
            (wr_id, tenant_id, client.id, period["id"]),
        )
        prop_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by, status)
            VALUES (%s, %s, %s, %s, 1, 'ACH', '2026-11-10', 'Test', 'rules', 'proposed');
            """,
            (prop_id, tenant_id, client.id, wr_id),
        )
        acc_id1 = uuid.uuid4()
        acc_id2 = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label, source)
            VALUES (%s, %s, %s, '6111000', 'Achats', 'cgnc_seed'),
                   (%s, %s, %s, '4411000', 'Fournisseurs', 'cgnc_seed');
            """,
            (acc_id1, tenant_id, client.id, acc_id2, tenant_id, client.id),
        )
        cur.execute(
            """
            INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad)
            VALUES (%s, %s, %s, %s, 1, %s, '6111000', 'Achats', 'MAD', 200.0, 0.0, 200.0, 0.0),
                   (%s, %s, %s, %s, 2, %s, '4411000', 'Fournisseurs', 'MAD', 0.0, 200.0, 0.0, 200.0);
            """,
            (uuid.uuid4(), tenant_id, client.id, prop_id, acc_id1, uuid.uuid4(), tenant_id, client.id, prop_id, acc_id2),
        )
    db_conn.commit()

    req = request_work_request_approval(db_conn, tenant_id, client.id, wr_id, user_id, single_person_policy=True)
    decide_work_request_approval(db_conn, tenant_id, uuid.UUID(req["id"]), user_id, "approved", "Validé", expected_subject_hash=req["subject_hash"])
    db_conn.commit()

    prof = create_or_get_default_export_profile(db_conn, tenant_id, "sage100_csv")

    # First export
    exp1 = create_export(db_conn, tenant_id, client.id, wr_id, uuid.UUID(req["id"]), prof["id"])
    assert exp1["status"] == "ready"
    db_conn.commit()

    # Second export on the same work request
    exp2 = create_export(db_conn, tenant_id, client.id, wr_id, uuid.UUID(req["id"]), prof["id"])
    assert exp2["status"] == "ready"
    db_conn.commit()

    # Verify exactly one usage record exists in usage_records!
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*), sum(quantity)
            FROM usage_records
            WHERE tenant_id = %s AND work_request_id = %s AND unit = 'monthly_file';
            """,
            (tenant_id, wr_id),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1, "Exactly one usage record must exist for the work request!"
        assert float(row[1]) == 1.0, "Quantity must not be double-billed!"


def test_download_token_verification_and_expiry():
    """HMAC tokens are verified and expired tokens are rejected."""
    exp_id = uuid.uuid4()
    valid_token = generate_export_download_token(exp_id, "file", expires_in_seconds=900)
    assert verify_export_download_token(valid_token, exp_id, "file") is True
    assert verify_export_download_token(valid_token, exp_id, "evidence_pack") is False
    assert verify_export_download_token(valid_token, uuid.uuid4(), "file") is False

    # Expired token
    expired_token = generate_export_download_token(exp_id, "file", expires_in_seconds=-10)
    assert verify_export_download_token(expired_token, exp_id, "file") is False


def test_download_records_audit_event(db_conn: psycopg.Connection):
    """Downloading export file or evidence pack inserts an export.downloaded event into audit_events."""
    tenant_id = seed_tenant(db_conn, "Audit Download Cabinet")
    sub = f"down-{uuid.uuid4()}"
    user_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@avenel.ma")
    seed_membership(db_conn, user_id, tenant_id, "owner", professional_title="expert_comptable", professional_registration_no="OEC-102")
    set_rls_context(db_conn, tenant_id, user_id)

    client = create_client_entity(db_conn, tenant_id, "Download Audit SARL", actor_id=str(user_id))
    period = open_accounting_period(
        db_conn, tenant_id, client.id, actor_id=str(user_id),
        period_code="2026-10", starts_on=datetime.date(2026, 10, 1),
        ends_on=datetime.date(2026, 10, 31), fiscal_year_end=datetime.date(2026, 12, 31)
    )

    wr_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code, status)
            VALUES (%s, %s, %s, %s, 'monthly_bookkeeping', 'awaiting_approval');
            """,
            (wr_id, tenant_id, client.id, period["id"]),
        )
        prop_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by, status)
            VALUES (%s, %s, %s, %s, 1, 'ACH', '2026-10-10', 'Test', 'rules', 'proposed');
            """,
            (prop_id, tenant_id, client.id, wr_id),
        )
        acc_id1 = uuid.uuid4()
        acc_id2 = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label, source)
            VALUES (%s, %s, %s, '6111000', 'Achats', 'cgnc_seed'),
                   (%s, %s, %s, '4411000', 'Fournisseurs', 'cgnc_seed');
            """,
            (acc_id1, tenant_id, client.id, acc_id2, tenant_id, client.id),
        )
        cur.execute(
            """
            INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad)
            VALUES (%s, %s, %s, %s, 1, %s, '6111000', 'Achats', 'MAD', 50.0, 0.0, 50.0, 0.0),
                   (%s, %s, %s, %s, 2, %s, '4411000', 'Fournisseurs', 'MAD', 0.0, 50.0, 0.0, 50.0);
            """,
            (uuid.uuid4(), tenant_id, client.id, prop_id, acc_id1, uuid.uuid4(), tenant_id, client.id, prop_id, acc_id2),
        )
    db_conn.commit()

    req = request_work_request_approval(db_conn, tenant_id, client.id, wr_id, user_id, single_person_policy=True)
    decide_work_request_approval(db_conn, tenant_id, uuid.UUID(req["id"]), user_id, "approved", "Validé", expected_subject_hash=req["subject_hash"])
    db_conn.commit()

    prof = create_or_get_default_export_profile(db_conn, tenant_id, "sage100_csv")
    exp = create_export(db_conn, tenant_id, client.id, wr_id, uuid.UUID(req["id"]), prof["id"])
    exp_id = uuid.UUID(exp["id"])
    db_conn.commit()

    # Call get_export_file
    get_export_file(db_conn, tenant_id, exp_id, actor_id=str(user_id))
    db_conn.commit()

    # Verify audit event was logged
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT action, resource_type, resource_id
            FROM audit_events
            WHERE tenant_id = %s AND resource_id = %s AND action = 'export.downloaded';
            """,
            (tenant_id, str(exp_id)),
        )
        event = cur.fetchone()
        assert event is not None
        assert event[0] == "export.downloaded"
        assert event[1] == "export"
        assert event[2] == str(exp_id)

