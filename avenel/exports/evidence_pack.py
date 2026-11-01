"""Evidence Pack generator per ARCHITECTURE.md Phase 5 and D.4.

Bundles into a ZIP archive:
1. The accounting export file (Sage 100 CSV/PNM or Odoo CSV)
2. manifest.json: canonical metadata, subject_hash, document sha256 hashes, rules applied
3. summary.pdf: PDF summary of approved entries and cryptographic proof
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # type: ignore[import-untyped]


def generate_manifest_json(
    tenant_id: str,
    client_entity_id: str,
    client_name: str,
    work_request_id: str,
    approval_id: str,
    export_id: str,
    export_target: str,
    subject_hash: str,
    exported_at: str,
    approver_name: str,
    approver_registration_no: str,
    documents: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    rules_applied: list[str],
) -> bytes:
    """Generates the canonical manifest.json for the evidence pack."""
    doc_entries = [
        {
            "document_id": str(d.get("id", "")),
            "original_filename": str(d.get("original_filename", "")),
            "doc_type": str(d.get("doc_type", "")),
            "sha256": str(d.get("sha256", "")),
            "page_count": d.get("page_count", 1),
        }
        for d in sorted(documents, key=lambda x: str(x.get("id", "")))
    ]

    total_debit = sum(
        float(l.get("debit_mad", 0.0))
        for p in proposals
        for l in p.get("lines", [])
    )
    total_credit = sum(
        float(l.get("credit_mad", 0.0))
        for p in proposals
        for l in p.get("lines", [])
    )

    manifest_payload = {
        "schema_version": "1.0",
        "jurisdiction": "MA",
        "service": "AVENEL - Dossier de preuves comptable",
        "tenant_id": tenant_id,
        "client_entity_id": client_entity_id,
        "client_name": client_name,
        "work_request_id": work_request_id,
        "approval_id": approval_id,
        "export_id": export_id,
        "export_target": export_target,
        "exported_at": exported_at,
        "subject_hash": subject_hash,
        "approver": {
            "name": approver_name,
            "registration_number": approver_registration_no,
        },
        "summary": {
            "proposals_count": len(proposals),
            "documents_count": len(doc_entries),
            "total_debit_mad": f"{total_debit:.2f}",
            "total_credit_mad": f"{total_credit:.2f}",
        },
        "rules_applied": sorted(set(rules_applied)),
        "documents": doc_entries,
    }

    raw = json.dumps(manifest_payload, indent=2, ensure_ascii=False)
    return raw.encode("utf-8")


def generate_summary_pdf(
    client_name: str,
    period_code: str,
    work_request_id: str,
    approval_id: str,
    subject_hash: str,
    approver_name: str,
    approver_registration_no: str,
    export_target: str,
    proposals: list[dict[str, Any]],
    documents: list[dict[str, Any]],
) -> bytes:
    """Generates a PDF summary of the approved bookkeeping file."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0B132B"),
    )
    subtitle_style = ParagraphStyle(
        "SubTitleStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#4A5568"),
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1A202C"),
    )
    bold_style = ParagraphStyle(
        "BoldStyle",
        parent=body_style,
        fontName="Helvetica-Bold",
    )
    code_style = ParagraphStyle(
        "CodeStyle",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#2D3748"),
    )

    story: list[Any] = []

    # Title & Header
    story.append(Paragraph("Récapitulatif du dossier mensuel", title_style))
    story.append(Paragraph("Dossier mensuel préparé selon les normes comptables marocaines (CGNC)", subtitle_style))
    story.append(Spacer(1, 14))

    # Meta table
    total_debit = sum(
        float(l.get("debit_mad", 0.0))
        for p in proposals
        for l in p.get("lines", [])
    )
    total_credit = sum(
        float(l.get("credit_mad", 0.0))
        for p in proposals
        for l in p.get("lines", [])
    )

    meta_data = [
        [Paragraph("Client / Société :", bold_style), Paragraph(client_name, body_style)],
        [Paragraph("Période comptable :", bold_style), Paragraph(period_code, body_style)],
        [Paragraph("Format d'export :", bold_style), Paragraph(export_target, body_style)],
        [Paragraph("Validé par :", bold_style), Paragraph(f"{approver_name} (N° Ordre : {approver_registration_no})", body_style)],
        [Paragraph("Identifiant dossier :", bold_style), Paragraph(str(work_request_id), code_style)],
        [Paragraph("Identifiant validation :", bold_style), Paragraph(str(approval_id), code_style)],
        [Paragraph("Empreinte SHA-256 (subject_hash) :", bold_style), Paragraph(subject_hash, code_style)],
        [Paragraph("Totaux validés :", bold_style), Paragraph(f"Débit : {total_debit:.2f} MAD  |  Crédit : {total_credit:.2f} MAD", bold_style)],
    ]

    meta_table = Table(meta_data, colWidths=[160, 360])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 16))

    # Documents summary table
    story.append(Paragraph("Pièces justificatives intégrées", bold_style))
    story.append(Spacer(1, 6))

    doc_rows = [
        [
            Paragraph("Document", bold_style),
            Paragraph("Type", bold_style),
            Paragraph("Empreinte SHA-256 (32 premiers car.)", bold_style),
        ]
    ]
    for d in documents[:20]:  # limit rows for compact display
        sha = str(d.get("sha256", ""))[:32] + "..."
        doc_rows.append(
            [
                Paragraph(str(d.get("original_filename", d.get("id", "")))[:25], body_style),
                Paragraph(str(d.get("doc_type", "")), body_style),
                Paragraph(sha, code_style),
            ]
        )

    doc_table = Table(doc_rows, colWidths=[180, 140, 200])
    doc_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(doc_table)
    story.append(Spacer(1, 16))

    # Proposals summary table
    story.append(Paragraph("Synthèse des écritures comptables", bold_style))
    story.append(Spacer(1, 6))

    prop_rows = [
        [
            Paragraph("Journal", bold_style),
            Paragraph("Date", bold_style),
            Paragraph("Libellé", bold_style),
            Paragraph("Lignes", bold_style),
        ]
    ]
    for p in proposals[:25]:
        lines_count = len(p.get("lines", []))
        prop_rows.append(
            [
                Paragraph(str(p.get("journal_code", "")), body_style),
                Paragraph(str(p.get("entry_date", "")), body_style),
                Paragraph(str(p.get("label", ""))[:30], body_style),
                Paragraph(str(lines_count), body_style),
            ]
        )

    prop_table = Table(prop_rows, colWidths=[70, 80, 310, 60])
    prop_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(prop_table)

    doc.build(story)
    return buf.getvalue()


def bundle_evidence_pack_zip(
    export_filename: str,
    export_file_bytes: bytes,
    manifest_bytes: bytes,
    pdf_summary_bytes: bytes,
    source_documents: list[tuple[str, bytes]] | None = None,
) -> bytes:
    """Bundles the export file, manifest.json, summary.pdf, and optional source documents into a ZIP archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(export_filename, export_file_bytes)
        zf.writestr("manifest.json", manifest_bytes)
        zf.writestr("summary.pdf", pdf_summary_bytes)
        if source_documents:
            for doc_name, doc_bytes in source_documents:
                zf.writestr(f"documents/{doc_name}", doc_bytes)
    return buf.getvalue()
