"""Tests for Work Request Approvals per ARCHITECTURE.md Phase 5 and D.4.

Tests:
- Quality gate enforcement (blocking issues reject approval request)
- Balance validation (unbalanced proposals reject approval request)
- Segregation of duties (preparer != decider unless single_person_policy=true)
- Professional registration requirement (OEC / Comptable Agréé)
- Hash validation and stale detection (409 on mutated proposals)
- Atomic proposal approval transition
"""

from __future__ import annotations

import datetime
import uuid
import psycopg
import pytest

from avenel.approvals.service import (
    ApprovalHashMismatchError,
    ApprovalStaleError,
    BlockingIssuesExistError,
    MissingRegistrationNumberError,
    NoProposalsError,
    SegregationOfDutiesError,
    UnacknowledgedReviewIssuesError,
    UnbalancedProposalError,
    compute_work_request_subject_hash,
    decide_work_request_approval,
    request_work_request_approval,
)
from avenel.clients.service import create_client_entity
from avenel.exports.service import (
    ExportHashMismatchError,
    create_export,
    create_or_get_default_export_profile,
)
from avenel.issues.service import acknowledge_review_issue
from avenel.periods.service import open_accounting_period
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user


@pytest.fixture
def approval_test_env(db_conn: psycopg.Connection):
    tenant_id = seed_tenant(db_conn, "Cabinet Approval Test")

    # Preparer (accountant)
    p_sub = f"prep-{uuid.uuid4()}"
    preparer_id = seed_user(db_conn, identity_subject=p_sub, email=f"{p_sub}@avenel.ma")
    seed_membership(db_conn, preparer_id, tenant_id, "accountant")

    # Decider 1: Qualified Partner (OEC)
    d1_sub = f"dec1-{uuid.uuid4()}"
    decider_oec_id = seed_user(db_conn, identity_subject=d1_sub, email=f"{d1_sub}@avenel.ma")
    seed_membership(
        db_conn,
        decider_oec_id,
        tenant_id,
        "owner",
        professional_title="expert_comptable",
        professional_registration_no="OEC-12345",
    )

    # Decider 2: Staff without registration
    d2_sub = f"dec2-{uuid.uuid4()}"
    decider_unreg_id = seed_user(db_conn, identity_subject=d2_sub, email=f"{d2_sub}@avenel.ma")
    seed_membership(db_conn, decider_unreg_id, tenant_id, "manager")

    set_rls_context(db_conn, tenant_id, preparer_id)

    client = create_client_entity(db_conn, tenant_id, "Société Maghreb Approvals SARL", actor_id=str(preparer_id))
    period = open_accounting_period(
        db_conn,
        tenant_id,
        client.id,
        actor_id=str(preparer_id),
        period_code="2026-10",
        starts_on=datetime.date(2026, 10, 1),
        ends_on=datetime.date(2026, 10, 31),
        fiscal_year_end=datetime.date(2026, 12, 31),
    )

    wr_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code, status)
            VALUES (%s, %s, %s, %s, 'monthly_bookkeeping', 'intake');
            """,
            (wr_id, tenant_id, client.id, period["id"]),
        )

    # Seed accounts
    acc_6111 = uuid.uuid4()
    acc_4411 = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label, source)
            VALUES (%s, %s, %s, '6111000', 'Achats marchandises', 'cgnc_seed'),
                   (%s, %s, %s, '4411000', 'Fournisseurs', 'cgnc_seed');
            """,
            (acc_6111, tenant_id, client.id, acc_4411, tenant_id, client.id),
        )

    db_conn.commit()

    return {
        "tenant_id": tenant_id,
        "client_id": client.id,
        "work_request_id": wr_id,
        "preparer_id": preparer_id,
        "decider_oec_id": decider_oec_id,
        "decider_unreg_id": decider_unreg_id,
        "acc_6111": acc_6111,
        "acc_4411": acc_4411,
    }


def test_approval_request_refused_on_zero_proposals(approval_test_env, db_conn):
    """Attempting to request approval with zero active proposals fails."""
    t_id = approval_test_env["tenant_id"]
    c_id = approval_test_env["client_id"]
    w_id = approval_test_env["work_request_id"]
    p_id = approval_test_env["preparer_id"]

    set_rls_context(db_conn, t_id, p_id)
    with pytest.raises(NoProposalsError):
        request_work_request_approval(db_conn, t_id, c_id, w_id, p_id)


def test_approval_request_refused_on_blocking_issues(approval_test_env, db_conn):
    """Attempting to request approval with open blocking issues fails."""
    t_id = approval_test_env["tenant_id"]
    c_id = approval_test_env["client_id"]
    w_id = approval_test_env["work_request_id"]
    p_id = approval_test_env["preparer_id"]
    acc1 = approval_test_env["acc_6111"]
    acc2 = approval_test_env["acc_4411"]

    set_rls_context(db_conn, t_id, p_id)

    # Seed proposal
    prop_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by, status)
            VALUES (%s, %s, %s, %s, 1, 'ACH', '2026-10-10', 'Achat test', 'rules', 'proposed');
            """,
            (prop_id, t_id, c_id, w_id),
        )
        cur.execute(
            """
            INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad)
            VALUES (%s, %s, %s, %s, 1, %s, '6111000', 'Achats', 'MAD', 1000.0, 0.0, 1000.0, 0.0),
                   (%s, %s, %s, %s, 2, %s, '4411000', 'Fournisseur', 'MAD', 0.0, 1000.0, 0.0, 1000.0);
            """,
            (uuid.uuid4(), t_id, c_id, prop_id, acc1, uuid.uuid4(), t_id, c_id, prop_id, acc2),
        )

        # Seed open blocking issue
        cur.execute(
            """
            INSERT INTO issues (id, tenant_id, client_entity_id, work_request_id, code, severity, status)
            VALUES (%s, %s, %s, %s, 'ACCOUNT_UNMAPPED', 'blocking', 'open');
            """,
            (uuid.uuid4(), t_id, c_id, w_id),
        )
    db_conn.commit()

    with pytest.raises(BlockingIssuesExistError):
        request_work_request_approval(db_conn, t_id, c_id, w_id, p_id)


def test_approval_request_refused_on_unbalanced_proposals(approval_test_env, db_conn):
    """Attempting to request approval with unbalanced proposal lines fails."""
    t_id = approval_test_env["tenant_id"]
    c_id = approval_test_env["client_id"]
    w_id = approval_test_env["work_request_id"]
    p_id = approval_test_env["preparer_id"]
    acc1 = approval_test_env["acc_6111"]
    acc2 = approval_test_env["acc_4411"]

    set_rls_context(db_conn, t_id, p_id)

    # Seed unbalanced proposal (Debit 1000 != Credit 900)
    prop_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by, status)
            VALUES (%s, %s, %s, %s, 1, 'ACH', '2026-10-10', 'Achat test', 'rules', 'proposed');
            """,
            (prop_id, t_id, c_id, w_id),
        )
        cur.execute(
            """
            INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad)
            VALUES (%s, %s, %s, %s, 1, %s, '6111000', 'Achats', 'MAD', 1000.0, 0.0, 1000.0, 0.0),
                   (%s, %s, %s, %s, 2, %s, '4411000', 'Fournisseur', 'MAD', 0.0, 900.0, 0.0, 900.0);
            """,
            (uuid.uuid4(), t_id, c_id, prop_id, acc1, uuid.uuid4(), t_id, c_id, prop_id, acc2),
        )
    # Calling request_work_request_approval before commit triggers UnbalancedProposalError
    with pytest.raises(UnbalancedProposalError):
        request_work_request_approval(db_conn, t_id, c_id, w_id, p_id)

    # And attempting to commit triggers database constraint check violation (app.assert_proposal_balanced)
    with pytest.raises(psycopg.errors.CheckViolation):
        db_conn.commit()
    db_conn.rollback()


def test_approval_full_flow_segregation_and_registration(approval_test_env, db_conn):
    """Full lifecycle: request -> self-approval rejected -> unreg rejected -> OEC partner approved."""
    t_id = approval_test_env["tenant_id"]
    c_id = approval_test_env["client_id"]
    w_id = approval_test_env["work_request_id"]
    prep_id = approval_test_env["preparer_id"]
    oec_id = approval_test_env["decider_oec_id"]
    unreg_id = approval_test_env["decider_unreg_id"]
    acc1 = approval_test_env["acc_6111"]
    acc2 = approval_test_env["acc_4411"]

    set_rls_context(db_conn, t_id, prep_id)

    # Seed balanced proposal
    prop_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by, status)
            VALUES (%s, %s, %s, %s, 1, 'ACH', '2026-10-10', 'Achat papeterie', 'rules', 'proposed');
            """,
            (prop_id, t_id, c_id, w_id),
        )
        cur.execute(
            """
            INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad)
            VALUES (%s, %s, %s, %s, 1, %s, '6111000', 'Achats', 'MAD', 500.0, 0.0, 500.0, 0.0),
                   (%s, %s, %s, %s, 2, %s, '4411000', 'Fournisseur', 'MAD', 0.0, 500.0, 0.0, 500.0);
            """,
            (uuid.uuid4(), t_id, c_id, prop_id, acc1, uuid.uuid4(), t_id, c_id, prop_id, acc2),
        )
    db_conn.commit()

    # 1. Request approval
    req_res = request_work_request_approval(db_conn, t_id, c_id, w_id, prep_id)
    app_id = uuid.UUID(req_res["id"])
    subject_hash = req_res["subject_hash"]
    assert req_res["status"] == "pending"
    db_conn.commit()

    # 2. Self-approval violation: preparer attempts to approve without single_person_policy
    set_rls_context(db_conn, t_id, prep_id)
    with pytest.raises(SegregationOfDutiesError):
        decide_work_request_approval(
            db_conn, t_id, app_id, prep_id, "approved", "Mon approbation", expected_subject_hash=subject_hash
        )
    db_conn.rollback()

    # 3. Decider without professional registration number rejected
    set_rls_context(db_conn, t_id, unreg_id)
    with pytest.raises(MissingRegistrationNumberError):
        decide_work_request_approval(
            db_conn, t_id, app_id, unreg_id, "approved", "Validation manager", expected_subject_hash=subject_hash
        )
    db_conn.rollback()

    # 4. Hash mismatch rejected with 409
    set_rls_context(db_conn, t_id, oec_id)
    with pytest.raises(ApprovalHashMismatchError):
        decide_work_request_approval(
            db_conn, t_id, app_id, oec_id, "approved", "Validation OEC", expected_subject_hash="wrong_hash"
        )
    db_conn.rollback()

    # 5. Stale approval rejected if proposals mutate before decision
    with db_conn.cursor() as cur:
        cur.execute(
            "UPDATE journal_lines SET debit_mad = 501.0 WHERE tenant_id = %s AND journal_proposal_id = %s AND line_no = 1;",
            (t_id, prop_id),
        )
        cur.execute(
            "UPDATE journal_lines SET credit_mad = 501.0 WHERE tenant_id = %s AND journal_proposal_id = %s AND line_no = 2;",
            (t_id, prop_id),
        )
    db_conn.commit()

    with pytest.raises(ApprovalStaleError):
        decide_work_request_approval(
            db_conn, t_id, app_id, oec_id, "approved", "Validation OEC", expected_subject_hash=subject_hash
        )
    db_conn.rollback()

    # Restore proposal so hash matches again
    with db_conn.cursor() as cur:
        cur.execute(
            "UPDATE journal_lines SET debit_mad = 500.0 WHERE tenant_id = %s AND journal_proposal_id = %s AND line_no = 1;",
            (t_id, prop_id),
        )
        cur.execute(
            "UPDATE journal_lines SET credit_mad = 500.0 WHERE tenant_id = %s AND journal_proposal_id = %s AND line_no = 2;",
            (t_id, prop_id),
        )
    db_conn.commit()

    # 6. Valid approval by OEC Partner succeeds!
    dec_res = decide_work_request_approval(
        db_conn, t_id, app_id, oec_id, "approved", "Dossier vérifié et approuvé par OEC", expected_subject_hash=subject_hash
    )
    assert dec_res["status"] == "approved"

    # Verify proposals are atomically updated to status 'approved'
    with db_conn.cursor() as cur:
        cur.execute("SELECT status FROM journal_proposals WHERE tenant_id = %s AND id = %s;", (t_id, prop_id))
        assert cur.fetchone()[0] == "approved"

        # Verify work request status is awaiting_approval (ready for export)
        cur.execute("SELECT status FROM work_requests WHERE tenant_id = %s AND id = %s;", (t_id, w_id))
        assert cur.fetchone()[0] == "awaiting_approval"

    # 7. Export generation transitions work request from exporting to completed
    prof = create_or_get_default_export_profile(db_conn, t_id, "sage100_csv")
    exp = create_export(db_conn, t_id, c_id, w_id, app_id, prof["id"])
    assert exp["status"] == "ready"
    assert exp["work_request_status"] == "completed"

    with db_conn.cursor() as cur:
        cur.execute("SELECT status FROM work_requests WHERE tenant_id = %s AND id = %s;", (t_id, w_id))
        assert cur.fetchone()[0] == "completed"


def test_unacknowledged_review_issues_blocks_approval(approval_test_env, db_conn):
    """Quality gate requires zero open blocking issues AND all review issues acknowledged."""
    t_id = approval_test_env["tenant_id"]
    c_id = approval_test_env["client_id"]
    w_id = approval_test_env["work_request_id"]
    prep_id = approval_test_env["preparer_id"]
    oec_id = approval_test_env["decider_oec_id"]
    acc1 = approval_test_env["acc_6111"]
    acc2 = approval_test_env["acc_4411"]

    set_rls_context(db_conn, t_id, prep_id)

    # Seed valid proposal
    prop_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by, status)
            VALUES (%s, %s, %s, %s, 1, 'ACH', '2026-10-15', 'Achat révisé', 'rules', 'proposed');
            """,
            (prop_id, t_id, c_id, w_id),
        )
        cur.execute(
            """
            INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad)
            VALUES (%s, %s, %s, %s, 1, %s, '6111000', 'Achats', 'MAD', 800.0, 0.0, 800.0, 0.0),
                   (%s, %s, %s, %s, 2, %s, '4411000', 'Fournisseur', 'MAD', 0.0, 800.0, 0.0, 800.0);
            """,
            (uuid.uuid4(), t_id, c_id, prop_id, acc1, uuid.uuid4(), t_id, c_id, prop_id, acc2),
        )

        # Seed unacknowledged review issue
        rev_issue_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO issues (id, tenant_id, client_entity_id, work_request_id, code, severity, status)
            VALUES (%s, %s, %s, %s, 'DUPLICATE_PROBABLE', 'review', 'open');
            """,
            (rev_issue_id, t_id, c_id, w_id),
        )
    db_conn.commit()

    # Request approval must fail with UnacknowledgedReviewIssuesError
    with pytest.raises(UnacknowledgedReviewIssuesError):
        request_work_request_approval(db_conn, t_id, c_id, w_id, prep_id)

    # Acknowledge review issue with justification note
    ack_res = acknowledge_review_issue(
        conn=db_conn,
        tenant_id=t_id,
        issue_id=rev_issue_id,
        acknowledged_by=prep_id,
        note="Fournisseur distinct confirmé par bon de livraison #441",
    )
    assert ack_res["status"] == "resolved"
    assert ack_res["resolution"] == "accepted_as_is"
    assert ack_res["resolution_note"] == "Fournisseur distinct confirmé par bon de livraison #441"
    db_conn.commit()

    # Now request approval succeeds!
    req_res = request_work_request_approval(db_conn, t_id, c_id, w_id, prep_id)
    assert req_res["status"] == "pending"

    # Decide approval succeeds!
    dec_res = decide_work_request_approval(
        db_conn, t_id, uuid.UUID(req_res["id"]), oec_id, "approved", "Dossier vérifié et acquitté", expected_subject_hash=req_res["subject_hash"]
    )
    assert dec_res["status"] == "approved"

    # Export generates completed_with_open_items because review issue was accepted_as_is!
    prof = create_or_get_default_export_profile(db_conn, t_id, "sage100_csv")
    exp_res = create_export(db_conn, t_id, c_id, w_id, uuid.UUID(req_res["id"]), prof["id"])
    assert exp_res["status"] == "ready"
    assert exp_res["work_request_status"] == "completed_with_open_items"

    with db_conn.cursor() as cur:
        cur.execute("SELECT status FROM work_requests WHERE tenant_id = %s AND id = %s;", (t_id, w_id))
        assert cur.fetchone()[0] == "completed_with_open_items"


def test_subject_hash_stable_on_approval_status_transition(approval_test_env, db_conn):
    """Subject hash calculation excludes volatile status and timestamps, remaining stable across approval."""
    t_id = approval_test_env["tenant_id"]
    c_id = approval_test_env["client_id"]
    w_id = approval_test_env["work_request_id"]
    prep_id = approval_test_env["preparer_id"]
    oec_id = approval_test_env["decider_oec_id"]
    acc1 = approval_test_env["acc_6111"]
    acc2 = approval_test_env["acc_4411"]

    set_rls_context(db_conn, t_id, prep_id)

    prop_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by, status)
            VALUES (%s, %s, %s, %s, 1, 'ACH', '2026-10-18', 'Hash test', 'rules', 'proposed');
            """,
            (prop_id, t_id, c_id, w_id),
        )
        cur.execute(
            """
            INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad)
            VALUES (%s, %s, %s, %s, 1, %s, '6111000', 'Achats', 'MAD', 250.0, 0.0, 250.0, 0.0),
                   (%s, %s, %s, %s, 2, %s, '4411000', 'Fournisseur', 'MAD', 0.0, 250.0, 0.0, 250.0);
            """,
            (uuid.uuid4(), t_id, c_id, prop_id, acc1, uuid.uuid4(), t_id, c_id, prop_id, acc2),
        )
    db_conn.commit()

    pre_approval_hash = compute_work_request_subject_hash(db_conn, t_id, c_id, w_id)
    req_res = request_work_request_approval(db_conn, t_id, c_id, w_id, prep_id)
    assert req_res["subject_hash"] == pre_approval_hash

    # Approve
    decide_work_request_approval(
        db_conn, t_id, uuid.UUID(req_res["id"]), oec_id, "approved", "Conformité vérifiée", expected_subject_hash=pre_approval_hash
    )

    # Recompute live hash on approved proposals
    post_approval_hash = compute_work_request_subject_hash(db_conn, t_id, c_id, w_id)
    assert post_approval_hash == pre_approval_hash, "Status change upon approval MUST NOT alter subject_hash!"


def test_altering_accepted_match_after_approval_refuses_export(approval_test_env, db_conn):
    """Mutating an accepted reconciliation match or its items after approval causes export refusal (Invariant #7)."""
    t_id = approval_test_env["tenant_id"]
    c_id = approval_test_env["client_id"]
    w_id = approval_test_env["work_request_id"]
    prep_id = approval_test_env["preparer_id"]
    oec_id = approval_test_env["decider_oec_id"]
    acc1 = approval_test_env["acc_6111"]
    acc2 = approval_test_env["acc_4411"]

    set_rls_context(db_conn, t_id, prep_id)

    # 1. Seed proposal
    prop_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by, status)
            VALUES (%s, %s, %s, %s, 1, 'ACH', '2026-10-20', 'Facture rapprochée', 'rules', 'proposed');
            """,
            (prop_id, t_id, c_id, w_id),
        )
        cur.execute(
            """
            INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad)
            VALUES (%s, %s, %s, %s, 1, %s, '6111000', 'Achats', 'MAD', 1500.0, 0.0, 1500.0, 0.0),
                   (%s, %s, %s, %s, 2, %s, '4411000', 'Fournisseur', 'MAD', 0.0, 1500.0, 0.0, 1500.0);
            """,
            (uuid.uuid4(), t_id, c_id, prop_id, acc1, uuid.uuid4(), t_id, c_id, prop_id, acc2),
        )

        # Seed accepted reconciliation match
        match_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO reconciliation_matches (id, tenant_id, client_entity_id, work_request_id, status, difference_kind, difference_mad)
            VALUES (%s, %s, %s, %s, 'accepted', NULL, 0.0);
            """,
            (match_id, t_id, c_id, w_id),
        )
        cur.execute(
            """
            INSERT INTO reconciliation_match_items (id, tenant_id, client_entity_id, match_id, journal_proposal_id, amount_mad)
            VALUES (%s, %s, %s, %s, %s, 1500.0);
            """,
            (uuid.uuid4(), t_id, c_id, match_id, prop_id),
        )
    db_conn.commit()

    # Request and decide approval
    req_res = request_work_request_approval(db_conn, t_id, c_id, w_id, prep_id)
    app_id = uuid.UUID(req_res["id"])
    subject_hash = req_res["subject_hash"]
    decide_work_request_approval(db_conn, t_id, app_id, oec_id, "approved", "Dossier validé", expected_subject_hash=subject_hash)
    db_conn.commit()

    # Mutate the accepted match item amount
    with db_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE reconciliation_match_items
            SET amount_mad = 1600.0
            WHERE tenant_id = %s AND match_id = %s;
            """,
            (t_id, match_id),
        )
    db_conn.commit()

    # Export MUST be refused due to hash mismatch!
    prof = create_or_get_default_export_profile(db_conn, t_id, "sage100_csv")
    with pytest.raises(ExportHashMismatchError):
        create_export(db_conn, t_id, c_id, w_id, app_id, prof["id"])


def test_single_person_policy_configured_on_client_entities(approval_test_env, db_conn):
    """single_person_policy is configured per client entity and recorded onto approvals row."""
    t_id = approval_test_env["tenant_id"]
    c_id = approval_test_env["client_id"]
    w_id = approval_test_env["work_request_id"]
    oec_id = approval_test_env["decider_oec_id"]
    acc1 = approval_test_env["acc_6111"]
    acc2 = approval_test_env["acc_4411"]

    set_rls_context(db_conn, t_id, oec_id)

    # 1. Enable single_person_policy on client_entities
    with db_conn.cursor() as cur:
        cur.execute(
            "UPDATE client_entities SET single_person_policy = true WHERE tenant_id = %s AND id = %s;",
            (t_id, c_id),
        )
        prop_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, entry_date, label, proposed_by, status)
            VALUES (%s, %s, %s, %s, 1, 'ACH', '2026-10-22', 'Single person proposal', 'rules', 'proposed');
            """,
            (prop_id, t_id, c_id, w_id),
        )
        cur.execute(
            """
            INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad)
            VALUES (%s, %s, %s, %s, 1, %s, '6111000', 'Achats', 'MAD', 300.0, 0.0, 300.0, 0.0),
                   (%s, %s, %s, %s, 2, %s, '4411000', 'Fournisseur', 'MAD', 0.0, 300.0, 0.0, 300.0);
            """,
            (uuid.uuid4(), t_id, c_id, prop_id, acc1, uuid.uuid4(), t_id, c_id, prop_id, acc2),
        )
    db_conn.commit()

    # OEC Partner prepares AND approves
    req_res = request_work_request_approval(db_conn, t_id, c_id, w_id, oec_id)
    app_id = uuid.UUID(req_res["id"])
    subject_hash = req_res["subject_hash"]

    # Verify single_person_policy was recorded on approvals row
    with db_conn.cursor() as cur:
        cur.execute("SELECT single_person_policy FROM approvals WHERE tenant_id = %s AND id = %s;", (t_id, app_id))
        assert cur.fetchone()[0] is True

    # Preparer self-approval succeeds because client entity has single_person_policy=True!
    dec_res = decide_work_request_approval(
        db_conn, t_id, app_id, oec_id, "approved", "Auto-approbation autorisée", expected_subject_hash=subject_hash
    )
    assert dec_res["status"] == "approved"

    # Verify professional registration details were copied onto approvals row
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT decider_professional_title, decider_registration_no, single_person_policy
            FROM approvals
            WHERE tenant_id = %s AND id = %s;
            """,
            (t_id, app_id),
        )
        row = cur.fetchone()
        assert row[0] == "expert_comptable"
        assert row[1] == "OEC-12345"
        assert row[2] is True
