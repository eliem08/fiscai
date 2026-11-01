"""Sage 100 PNM Exporter per ARCHITECTURE.md Phase 5.

Format:
- Encoding: CP1252 (Windows-1252)
- Header: #FORMAT_PNM
- Delimiter: ';'
- Fields per line:
  CodeJournal;Date(DDMMYY);NoPiece;RefFacture;CompteGen;CompteTiers;Libelle;Sens(D/C);Montant;DateEcheance
"""

from __future__ import annotations

from typing import Any


def format_sage100_pnm(
    proposals: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> bytes:
    """Formats proposals into a byte string encoded in CP1252 for Sage 100 PNM import."""
    cfg = config or {}
    delimiter = str(cfg.get("delimiter", ";"))
    decimal_sep = str(cfg.get("decimal_separator", ","))
    account_padding = int(cfg.get("account_padding", 0))

    lines_out: list[str] = ["#FORMAT_PNM"]

    sorted_proposals = sorted(
        proposals,
        key=lambda p: (str(p.get("journal_code", "")), str(p.get("entry_date", "")), str(p.get("id", ""))),
    )

    for prop in sorted_proposals:
        j_code = str(prop.get("journal_code", "OD"))
        raw_date = str(prop.get("entry_date", ""))
        if len(raw_date) >= 10 and raw_date[4] == "-" and raw_date[7] == "-":
            y, m, d = raw_date[0:4], raw_date[5:7], raw_date[8:10]
            formatted_date = f"{d}{m}{y[2:4]}"
        else:
            formatted_date = raw_date.replace("-", "")[:6]

        piece_no = str(prop.get("piece_number") or prop.get("source_document_id") or prop.get("id", ""))[:35]
        ref = str(prop.get("reference") or prop.get("label", ""))[:35]

        prop_lines = sorted(prop.get("lines", []), key=lambda l: int(l.get("line_no", 0)))
        for line in prop_lines:
            acc_code = str(line.get("account_code", ""))
            if account_padding > 0 and len(acc_code) < account_padding:
                acc_code = acc_code.ljust(account_padding, "0")

            counterparty = str(line.get("counterparty_account_code") or line.get("counterparty_code") or "")
            label = str(line.get("label") or prop.get("label", ""))[:35]

            debit = float(line.get("debit_mad", 0.0))
            credit = float(line.get("credit_mad", 0.0))

            if debit > 0:
                sens = "D"
                amount_str = f"{debit:.2f}".replace(".", decimal_sep)
            else:
                sens = "C"
                amount_str = f"{credit:.2f}".replace(".", decimal_sep)

            due_date = ""

            record_fields = [
                j_code,
                formatted_date,
                piece_no,
                ref,
                acc_code,
                counterparty,
                label,
                sens,
                amount_str,
                due_date,
            ]
            lines_out.append(delimiter.join(record_fields))

    text_data = "\r\n".join(lines_out) + "\r\n"
    return text_data.encode("cp1252", errors="replace")

