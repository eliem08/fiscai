"""Sage 100 CSV Exporter per ARCHITECTURE.md Phase 5.

Format:
- Encoding: CP1252 (Windows-1252) with clean transliteration fallback
- Delimiter: ';' (semicolon)
- Columns:
  1. Journal code (e.g. ACH, VTE, BQ)
  2. Date (format DDMMYY or DDMMYYYY per config, default DDMMYYYY)
  3. Piece number (N° Pièce)
  4. Reference (N° Facture / Pièce)
  5. General ledger account (Compte général, padded/unpadded per config)
  6. Auxiliary account / Tiers (Compte auxiliaire)
  7. Label (Libellé de la ligne)
  8. Debit amount (formatted with '.' or ',' decimal separator per config)
  9. Credit amount (formatted with '.' or ',' decimal separator per config)
"""

from __future__ import annotations

import csv
import io
from typing import Any


def format_sage100_csv(
    proposals: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> bytes:
    """Formats proposals into a byte string encoded in CP1252 for Sage 100 CSV import."""
    cfg = config or {}
    delimiter = str(cfg.get("delimiter", ";"))
    date_format = str(cfg.get("date_format", "%d%m%Y"))
    decimal_sep = str(cfg.get("decimal_separator", ","))
    account_padding = int(cfg.get("account_padding", 0))

    output = io.StringIO()
    writer = csv.writer(
        output,
        delimiter=delimiter,
        lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL,
    )

    # Sort proposals deterministically
    sorted_proposals = sorted(
        proposals,
        key=lambda p: (str(p.get("journal_code", "")), str(p.get("entry_date", "")), str(p.get("id", ""))),
    )

    for prop in sorted_proposals:
        j_code = str(prop.get("journal_code", "OD"))
        raw_date = str(prop.get("entry_date", ""))
        # Parse date YYYY-MM-DD
        if len(raw_date) >= 10 and raw_date[4] == "-" and raw_date[7] == "-":
            y, m, d = raw_date[0:4], raw_date[5:7], raw_date[8:10]
            if date_format == "%d%m%y":
                formatted_date = f"{d}{m}{y[2:4]}"
            else:
                formatted_date = f"{d}{m}{y}"
        else:
            formatted_date = raw_date.replace("-", "")

        piece_no = str(prop.get("piece_number") or prop.get("source_document_id") or prop.get("id", ""))[:35]
        ref = str(prop.get("reference") or prop.get("label", ""))[:35]

        lines = sorted(prop.get("lines", []), key=lambda l: int(l.get("line_no", 0)))
        for line in lines:
            acc_code = str(line.get("account_code", ""))
            if account_padding > 0 and len(acc_code) < account_padding:
                acc_code = acc_code.ljust(account_padding, "0")

            counterparty = str(line.get("counterparty_account_code") or line.get("counterparty_code") or "")
            label = str(line.get("label") or prop.get("label", ""))[:35]

            # Format amounts
            dr = f"{float(line.get('debit_mad', 0.0)):.2f}".replace(".", decimal_sep)
            cr = f"{float(line.get('credit_mad', 0.0)):.2f}".replace(".", decimal_sep)

            writer.writerow(
                [
                    j_code,
                    formatted_date,
                    piece_no,
                    ref,
                    acc_code,
                    counterparty,
                    label,
                    dr,
                    cr,
                ]
            )

    text_data = output.getvalue()
    # Encode with cp1252, transliterating or replacing unmappable unicode
    return text_data.encode("cp1252", errors="replace")

