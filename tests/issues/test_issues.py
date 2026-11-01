"""Tests for Issue Workflow and Client Portal Requests per ARCHITECTURE.md Phase 5."""

from __future__ import annotations

import datetime
import uuid
import psycopg
import pytest

from avenel.clients.service import create_client_entity
from avenel.issues.service import (
    IssueError,
    acknowledge_review_issue,
    answer_portal_request,
    assign_issue,
    list_portal_requests,
    list_work_request_issues,
    resolve_issue,
    send_issue_to_client,
)
from avenel.periods.service import open_accounting_period
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user


@pytest.fixture
def issues_test_env(db_conn: psycopg.Connection):
    tenant_id = seed_tenant(db_conn, "Cabinet Issues Test")

    accountant_sub = f"acc-{uuid.uuid4()}"
    accountant_id = seed_user(db_conn, identity_subject=accountant_sub, email=f"{accountant_sub}@avenel.ma")
    seed_membership(db_conn, accountant_id, tenant_id, "accountant")

    client_user_sub = f"client-{uuid.uuid4()}"
    client_user_id = seed_user(db_conn, identity_subject=client_user_sub, email=f"{client_user_sub}@client.ma")
    seed_membership(db_conn, client_user_id, tenant_id, "client_user")

    set_rls_context(db_conn, tenant_id, accountant_id)

    client = create_client_entity(db_conn, tenant_id, "Société Beta SARL", actor_id=str(accountant_id))
    period = open_accounting_period(
        db_conn,
        tenant_id,
        client.id,
        actor_id=str(accountant_id),
        period_code="2026-11",
        starts_on=datetime.date(2026, 11, 1),
        ends_on=datetime.date(2026, 11, 30),
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
    db_conn.commit()

    return {
        "tenant_id": tenant_id,
        "client_id": client.id,
        "work_request_id": wr_id,
        "accountant_id": accountant_id,
        "client_user_id": client_user_id,
    }


def test_issue_lifecycle_assign_resolve_and_rules(issues_test_env, db_conn):
    """Tests assign, blocking resolution restriction, and resolution."""
    t_id = issues_test_env["tenant_id"]
    c_id = issues_test_env["client_id"]
    w_id = issues_test_env["work_request_id"]
    acc_id = issues_test_env["accountant_id"]

    set_rls_context(db_conn, t_id, acc_id)

    # 1. Create a blocking issue and a review issue
    issue_block_id = uuid.uuid4()
    issue_rev_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO issues (id, tenant_id, client_entity_id, work_request_id, code, severity, status)
            VALUES (%s, %s, %s, %s, 'ACCOUNT_UNMAPPED', 'blocking', 'open'),
                   (%s, %s, %s, %s, 'DUPLICATE_PROBABLE', 'review', 'open');
            """,
            (issue_block_id, t_id, c_id, w_id, issue_rev_id, t_id, c_id, w_id),
        )
    db_conn.commit()

    issues = list_work_request_issues(db_conn, t_id, c_id, w_id)
    assert len(issues) == 2
    assert issues[0]["severity"] == "blocking"

    # 2. Assign issue
    assigned = assign_issue(db_conn, t_id, issue_block_id, acc_id)
    assert assigned["status"] == "assigned"
    assert assigned["assigned_to"] == str(acc_id)
    db_conn.commit()

    # 3. Blocking issue CANNOT be accepted_as_is
    with pytest.raises(IssueError):
        resolve_issue(db_conn, t_id, issue_block_id, acc_id, resolution="accepted_as_is")
    db_conn.rollback()

    # 4. Blocking issue resolved with 'fixed'
    res = resolve_issue(db_conn, t_id, issue_block_id, acc_id, resolution="fixed", resolution_note="Compte configuré")
    assert res["status"] == "resolved"
    assert res["resolution"] == "fixed"
    db_conn.commit()

    # 5. Review issue waived
    res2 = resolve_issue(db_conn, t_id, issue_rev_id, acc_id, resolution="waived", resolution_note="Faux positif vérifié")
    assert res2["status"] == "waived"
    assert res2["resolution"] == "waived"
    db_conn.commit()


def test_issue_portal_request_and_client_answer(issues_test_env, db_conn):
    """Tests cabinet sending issue to client portal, listing, and client answering."""
    t_id = issues_test_env["tenant_id"]
    c_id = issues_test_env["client_id"]
    w_id = issues_test_env["work_request_id"]
    acc_id = issues_test_env["accountant_id"]
    client_uid = issues_test_env["client_user_id"]

    set_rls_context(db_conn, t_id, acc_id)

    # 1. Seed open issue
    issue_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO issues (id, tenant_id, client_entity_id, work_request_id, code, severity, status)
            VALUES (%s, %s, %s, %s, 'MISSING_INVOICE', 'review', 'open');
            """,
            (issue_id, t_id, c_id, w_id),
        )
    db_conn.commit()

    # 2. Cabinet sends issue to client
    send_res = send_issue_to_client(
        db_conn,
        t_id,
        issue_id,
        actor_id=str(acc_id),
        client_prompt="Merci de fournir la facture correspondant au virement de 5000 MAD.",
    )
    assert send_res["status"] == "waiting_client"
    assert send_res["resolution"] == "sent_to_client"
    db_conn.commit()

    # 3. Client user checks portal requests
    set_rls_context(db_conn, t_id, client_uid)
    portal_requests = list_portal_requests(db_conn, t_id, c_id)
    assert len(portal_requests) == 1
    req = portal_requests[0]
    assert req["id"] == str(issue_id)
    assert "Merci de fournir la facture" in req["prompt"]

    # 4. Client user answers in portal
    ans_res = answer_portal_request(
        db_conn,
        t_id,
        issue_id,
        client_user_id=client_uid,
        answer_text="Voici la facture demandée, scan joint.",
        attached_document_id=uuid.uuid4(),
    )
    assert ans_res["status"] == "open"
    assert ans_res["answered"] is True
    db_conn.commit()

    # 5. Cabinet views updated issue with evidence
    set_rls_context(db_conn, t_id, acc_id)
    issues = list_work_request_issues(db_conn, t_id, c_id, w_id)
    assert len(issues) == 1
    assert issues[0]["status"] == "open"
    evidence = issues[0]["evidence_refs"]
    assert len(evidence) == 2
    assert evidence[0]["type"] == "client_request"
    assert evidence[1]["type"] == "client_response"
    assert "Voici la facture demandée" in evidence[1]["response"]


def test_acknowledge_review_issue_workflow(issues_test_env, db_conn):
    """Review issue acknowledgement requires non-empty note and rejects blocking issues."""
    t_id = issues_test_env["tenant_id"]
    c_id = issues_test_env["client_id"]
    w_id = issues_test_env["work_request_id"]
    acc_id = issues_test_env["accountant_id"]

    set_rls_context(db_conn, t_id, acc_id)

    rev_issue_id = uuid.uuid4()
    blk_issue_id = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO issues (id, tenant_id, client_entity_id, work_request_id, code, severity, status)
            VALUES (%s, %s, %s, %s, 'DUPLICATE_PROBABLE', 'review', 'open'),
                   (%s, %s, %s, %s, 'ACCOUNT_UNMAPPED', 'blocking', 'open');
            """,
            (rev_issue_id, t_id, c_id, w_id, blk_issue_id, t_id, c_id, w_id),
        )
    db_conn.commit()

    # 1. Reject empty note
    with pytest.raises(ValueError):
        acknowledge_review_issue(db_conn, t_id, rev_issue_id, acc_id, note="   ")

    # 2. Reject blocking issue acknowledgement
    with pytest.raises(IssueError) as exc_info:
        acknowledge_review_issue(db_conn, t_id, blk_issue_id, acc_id, note="Acceptation forcée")
    assert "Une anomalie bloquante ne peut pas être acquittée" in str(exc_info.value)

    # 3. Successful review issue acknowledgement
    ack_res = acknowledge_review_issue(
        conn=db_conn,
        tenant_id=t_id,
        issue_id=rev_issue_id,
        acknowledged_by=acc_id,
        note="Écart de date justifié par le bon de réception du transitaire",
    )
    assert ack_res["status"] == "resolved"
    assert ack_res["resolution"] == "accepted_as_is"
    assert ack_res["resolution_note"] == "Écart de date justifié par le bon de réception du transitaire"


