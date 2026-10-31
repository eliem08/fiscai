"""Chart of accounts importer from CSV and XLSX formats.

Enforces:
- File size limit: <= 10 MB
- Uncompressed size limit: <= 50 MB (zip bomb protection)
- Row count limit: <= 20,000 rows
- XXE protection via defusedxml
- Parser implementation using openpyxl and defusedxml
"""

from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
import zipfile

import defusedxml.common  # type: ignore[import-untyped]
import defusedxml.ElementTree as DefusedET  # type: ignore[import-untyped]
import openpyxl  # type: ignore[import-untyped]

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_ROWS = 20_000
MAX_COMPRESSION_RATIO = 100.0

ACCOUNT_CODE_REGEX = re.compile(r"^[0-8][0-9]{3,}$")
HEADER_KEYWORDS = {
    "code", "compte", "numero", "numéro", "account", "account_code",
    "label", "libelle", "libellé", "intitule", "intitulé",
}


def parse_csv_chart(content: str | bytes) -> list[tuple[str, str]]:
    """Parses chart of accounts from CSV string or bytes."""
    if isinstance(content, bytes):
        if len(content) > MAX_FILE_BYTES:
            raise ValueError(f"Le fichier dépasse la taille maximale autorisée de {MAX_FILE_BYTES // (1024 * 1024)} Mo.")
        text = content.decode("utf-8-sig", errors="replace")
    else:
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError(f"Le fichier dépasse la taille maximale autorisée de {MAX_FILE_BYTES // (1024 * 1024)} Mo.")
        text = content

    sample = text[:2048]
    delimiter = ";" if ";" in sample else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)

    accounts: list[tuple[str, str]] = []
    row_count = 0
    for row in reader:
        row_count += 1
        if row_count > MAX_ROWS:
            raise ValueError("Le fichier dépasse le nombre maximal autorisé de 20 000 lignes.")

        if not row or len(row) < 2:
            continue
        raw_code = str(row[0]).strip()
        raw_label = str(row[1]).strip()

        if raw_code.lower() in HEADER_KEYWORDS or raw_label.lower() in HEADER_KEYWORDS:
            continue

        clean_code = raw_code.replace(" ", "").replace(".", "")
        if not ACCOUNT_CODE_REGEX.match(clean_code):
            continue
        if not raw_label:
            continue

        accounts.append((clean_code, raw_label))

    return accounts


def inspect_xlsx_safety(content: bytes) -> None:
    """Preflights XLSX zip archive for zip bomb and XXE payloads using defusedxml."""
    if len(content) > MAX_FILE_BYTES:
        raise ValueError(f"Le fichier dépasse la taille maximale autorisée de {MAX_FILE_BYTES // (1024 * 1024)} Mo.")

    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except Exception as e:
        raise ValueError(f"Fichier XLSX invalide ou archive zip corrompue: {e}") from e

    with zf:
        infolist = zf.infolist()
        total_uncompressed = sum(info.file_size for info in infolist)
        if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
            raise ValueError(
                "La taille décompressée dépasse la limite de sécurité de 50 Mo (suspicion de bombe de décompression)."
            )

        for info in infolist:
            # Check suspicious compression ratio
            if info.compress_size > 0 and info.file_size > 1024 * 1024:
                ratio = info.file_size / info.compress_size
                if ratio > MAX_COMPRESSION_RATIO:
                    raise ValueError(
                        f"Ratio de compression suspect ({ratio:.1f}:1) détecté dans {info.filename} "
                        "(suspicion de bombe de décompression)."
                    )

            # Inspect all XML files for XXE / DTD expansion via defusedxml
            if info.filename.endswith((".xml", ".rels")):
                xml_data = zf.read(info.filename)
                try:
                    DefusedET.fromstring(xml_data)
                except (
                    defusedxml.common.DTDForbidden,
                    defusedxml.common.EntitiesForbidden,
                    defusedxml.common.DefusedXmlException,
                ) as e:
                    raise ValueError(
                        f"Contenu XML non sécurisé détecté dans {info.filename} (XXE / DTD interdit): {e}"
                    ) from e
                except ET.ParseError:
                    # Non-fatal if a non-core part has parsing quirks; openpyxl validates structure
                    continue


def parse_xlsx_chart(content: bytes) -> list[tuple[str, str]]:
    """Parses chart of accounts from XLSX binary data using openpyxl + defusedxml."""
    # 1. Security preflight: zip bomb + XXE checks
    inspect_xlsx_safety(content)

    # 2. Parse with openpyxl
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as e:
        raise ValueError(f"Impossible de lire le classeur XLSX: {e}") from e

    ws = wb.active
    if ws is None:
        return []

    accounts: list[tuple[str, str]] = []
    row_count = 0

    try:
        for row in ws.iter_rows(values_only=True):
            row_count += 1
            if row_count > MAX_ROWS:
                raise ValueError("Le fichier dépasse le nombre maximal autorisé de 20 000 lignes.")

            if not row or len(row) < 2:
                continue

            raw_code = str(row[0]).strip() if row[0] is not None else ""
            raw_label = str(row[1]).strip() if row[1] is not None else ""

            if not raw_code or not raw_label:
                continue

            if raw_code.lower() in HEADER_KEYWORDS or raw_label.lower() in HEADER_KEYWORDS:
                continue

            clean_code = raw_code.replace(" ", "").replace(".", "")
            if not ACCOUNT_CODE_REGEX.match(clean_code):
                continue

            accounts.append((clean_code, raw_label))
    finally:
        wb.close()

    return accounts
