"""Odoo CSV Exporter per ARCHITECTURE.md Phase 5.

Format:
- Encoding: UTF-8
- Delimiter: ',' (comma)
- Headers:
  id,date,ref,journal_id,line_ids/account_id,line_ids/partner_id,line_ids/name,line_ids/debit,line_ids/credit
"""

from __future__ import annotations

import csv
import io
from typing import Any


def format_odoo_csv(
    proposals: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> bytes:
    """Formats proposals into a byte string encoded in UTF-8 for Odoo CSV import."""
    cfg = config or {}
    delimiter = str(cfg.get("delimiter", ","))

    output = io.StringIO()
    writer = csv.writer(
        output,
        delimiter=delimiter,
        lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL,
    )

    headers = [
        "id",
        "date",
        "ref",
        "journal_id",
        "line_ids/account_id",
        "line_ids/partner_id",
        "line_ids/name",
        "line_ids/debit",
        "line_ids/credit",
    ]
    writer.writerow(headers)

    sorted_proposals = sorted(
        proposals,
        key=lambda p: (str(p.get("journal_code", "")), str(p.get("entry_date", "")), str(p.get("id", ""))),
    )

    for prop in sorted_proposals:
        move_id = f"avenel_move_{prop.get('id', '')}"
        date_str = str(prop.get("entry_date", ""))
        ref_str = str(prop.get("reference") or prop.get("label", ""))
        journal_code = str(prop.get("journal_code", "MISC"))

        lines = sorted(prop.get("lines", []), key=lambda l: int(l.get("line_no", 0)))
        for idx, line in enumerate(lines):
            acc_code = str(line.get("account_code", ""))
            partner = str(line.get("counterparty_account_code") or line.get("counterparty_code") or "")
            name = str(line.get("label") or prop.get("label", ""))
            dr = f"{float(line.get('debit_mad', 0.0)):.2f}"
            cr = f"{float(line.get('credit_mad', 0.0)):.2f}"

            if idx == 0:
                # First line includes move header fields
                writer.writerow(
                    [
                        move_id,
                        date_str,
                        ref_str,
                        journal_code,
                        acc_code,
                        partner,
                        name,
                        dr,
                        cr,
                    ]
                )
            else:
                # Subsequent lines have empty move headers under the same move id
                writer.writerow(
                    [
                        move_id,
                        "",
                        "",
                        "",
                        acc_code,
                        partner,
                        name,
                        dr,
                        cr,
                    ]
                )

    text_data = output.getvalue()
    return text_data.encode("utf-8")

