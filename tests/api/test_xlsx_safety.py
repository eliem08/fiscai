"""Tests for XLSX and CSV chart of accounts parser security.

Enforces:
- Max file size <= 10 MB
- Max uncompressed size <= 50 MB (zip bomb protection)
- Max row count <= 20,000 rows
- XXE payload rejection via defusedxml
"""

from __future__ import annotations

import io
import zipfile

import openpyxl
import pytest

from avenel.accounting.chart_import import (
    MAX_FILE_BYTES,
    MAX_ROWS,
    MAX_UNCOMPRESSED_BYTES,
    parse_csv_chart,
    parse_xlsx_chart,
)


def _create_minimal_xlsx(rows: list[tuple[str, str]]) -> bytes:
    """Helper to create a valid minimal XLSX workbook in bytes."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["code", "label"])  # Header
    for code, label in rows:
        ws.append([code, label])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def test_xlsx_valid_parse():
    """Valid XLSX parses account code and label pairs properly."""
    data = _create_minimal_xlsx([
        ("3421", "Clients"),
        ("4411", "Fournisseurs"),
        ("5141", "Banques"),
    ])
    accounts = parse_xlsx_chart(data)
    assert len(accounts) == 3
    assert accounts[0] == ("3421", "Clients")
    assert accounts[1] == ("4411", "Fournisseurs")
    assert accounts[2] == ("5141", "Banques")


def test_xlsx_file_size_limit():
    """XLSX file exceeding 10 MB is rejected."""
    oversized = b"0" * (MAX_FILE_BYTES + 1024)
    with pytest.raises(ValueError, match="taille maximale autorisée de 10 Mo"):
        parse_xlsx_chart(oversized)


def test_csv_file_size_limit():
    """CSV file exceeding 10 MB is rejected."""
    # 11 MB of valid CSV data
    oversized = b"code;label\n" + (b"3421;Clients de l'entreprise\n" * 450_000)
    assert len(oversized) > MAX_FILE_BYTES
    with pytest.raises(ValueError, match="taille maximale autorisée de 10 Mo"):
        parse_csv_chart(oversized)


def test_xlsx_row_limit():
    """XLSX file exceeding 20,000 rows is rejected."""
    rows = [("3421", f"Client {i}") for i in range(MAX_ROWS + 1)]
    data = _create_minimal_xlsx(rows)
    with pytest.raises(ValueError, match="20 000 lignes"):
        parse_xlsx_chart(data)


def test_csv_row_limit():
    """CSV file exceeding 20,000 rows is rejected."""
    lines = ["code;label"] + [f"3421;Client {i}" for i in range(MAX_ROWS + 5)]
    csv_text = "\n".join(lines)
    with pytest.raises(ValueError, match="20 000 lignes"):
        parse_csv_chart(csv_text)


def test_xlsx_zip_bomb_rejection():
    """Zip archive claiming > 50 MB uncompressed is rejected as a zip bomb."""
    valid_xlsx = _create_minimal_xlsx([("3421", "Clients")])
    in_bio = io.BytesIO(valid_xlsx)
    out_bio = io.BytesIO()

    # Add a 51 MB deflated zero stream (compresses to ~50 KB)
    big_zeros = b"\x00" * (MAX_UNCOMPRESSED_BYTES + 1024 * 1024)

    with zipfile.ZipFile(in_bio, "r") as in_zf, zipfile.ZipFile(out_bio, "w", compression=zipfile.ZIP_DEFLATED) as out_zf:
        for item in in_zf.infolist():
            out_zf.writestr(item.filename, in_zf.read(item.filename))
        out_zf.writestr("xl/large_stream.bin", big_zeros)

    zip_bomb_bytes = out_bio.getvalue()
    with pytest.raises(ValueError, match="bombe de décompression"):
        parse_xlsx_chart(zip_bomb_bytes)


def test_xlsx_xxe_payload_rejection():
    """XLSX containing XXE / DTD expansion entity payload is rejected by defusedxml."""
    valid_xlsx = _create_minimal_xlsx([("3421", "Clients")])
    in_bio = io.BytesIO(valid_xlsx)
    out_bio = io.BytesIO()

    xxe_xml = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<!DOCTYPE root [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="inlineStr"><is><t>&xxe;</t></is></c>
    </row>
  </sheetData>
</worksheet>"""

    with zipfile.ZipFile(in_bio, "r") as in_zf, zipfile.ZipFile(out_bio, "w") as out_zf:
        for item in in_zf.infolist():
            if "sheet1.xml" in item.filename:
                out_zf.writestr(item.filename, xxe_xml)
            else:
                out_zf.writestr(item.filename, in_zf.read(item.filename))

    xxe_xlsx_bytes = out_bio.getvalue()
    with pytest.raises(ValueError, match="XXE / DTD interdit"):
        parse_xlsx_chart(xxe_xlsx_bytes)
