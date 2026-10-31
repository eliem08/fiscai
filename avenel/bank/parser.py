"""Bank statement parsers for Moroccan accounting workflows.

Supports CSV, XLSX, and PDF statement formats with strict mathematical
balance verification (opening_balance + sum(movements) == closing_balance).
Tolerance loaded from /jurisdiction/ma/invoice_mentions.yaml.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import io
import re
from typing import Any

from avenel.bank.models import ParsedStatement, ParsedTransaction
from avenel.jurisdiction.loader import get_jurisdiction_pack


def _compute_line_hash(line_index: int, date_str: str, amount: float, raw_label: str) -> str:
    """Computes a deterministic hash for idempotent transaction ingestion."""
    payload = f"{line_index}|{date_str}|{amount:.2f}|{raw_label.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_str(s: Any) -> str:
    """Normalizes string for robust header and keyword matching without accents."""
    res = str(s or "").lower().strip()
    return res.replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a")


def _parse_amount(val: Any) -> float:
    """Parses numeric string or float into a float, handling French commas and spaces."""
    if val is None or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
    # Remove any currency text
    s = re.sub(r"[^\d\.\+\-]", "", s)
    if not s or s in ("+", "-"):
        return 0.0
    return float(s)


def _parse_date(val: Any) -> datetime.date:
    """Parses date string in common Moroccan / French formats: DD/MM/YYYY, YYYY-MM-DD."""
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, datetime.date):
        return val
    s = str(val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date string: '{s}'")


def _get_balance_tolerance() -> float:
    """Loads balance tolerance from jurisdiction pack (Rule A.1/A.2)."""
    pack = get_jurisdiction_pack()
    rule = pack.get_rule("bank.statement.balance_tolerance")
    return float(rule["value"]) if rule and rule.get("value") is not None else 0.005


def verify_statement_balance(
    opening_balance: float,
    closing_balance: float,
    transactions: list[ParsedTransaction],
) -> tuple[float, float, str]:
    """Calculates computed closing balance and evaluates balance invariant.

    Returns (computed_closing, difference, balance_check).
    balance_check is 'ok' if |difference| <= tolerance, else 'break'.
    """
    tolerance = _get_balance_tolerance()
    net_movements = sum(tx.amount for tx in transactions)
    computed_closing = round(opening_balance + net_movements, 2)
    diff = round(abs(computed_closing - closing_balance), 2)
    check = "ok" if diff <= tolerance else "break"
    return computed_closing, diff, check


def parse_bank_statement_csv(content: bytes | str) -> ParsedStatement:
    """Parses a CSV bank statement.

    Expected formats:
    - Header comments or rows for opening/closing balance:
        # Solde initial: 50000.00
        # Solde final: 62450.00
      or columns:
        Date,Valeur,Libellé,Débit,Crédit,Solde
    """
    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    opening_balance: float = 0.0
    closing_balance: float = 0.0
    opening_found = False

    # 1. Look for metadata in comments or prefix rows
    data_rows: list[str] = []
    for line in lines:
        lower = line.lower()
        if "solde initial" in lower or "solde depart" in lower or "opening_balance" in lower:
            # Extract number
            nums = re.findall(r"[-+]?\d[\d\s]*[.,]?\d*", line)
            if nums:
                opening_balance = _parse_amount(nums[-1])
                opening_found = True
            continue
        if "solde final" in lower or "solde fin" in lower or "closing_balance" in lower:
            nums = re.findall(r"[-+]?\d[\d\s]*[.,]?\d*", line)
            if nums:
                closing_balance = _parse_amount(nums[-1])
            continue
        if line.startswith(("#", "//")):
            continue
        data_rows.append(line)

    if not data_rows:
        return ParsedStatement(
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            computed_closing_balance=opening_balance,
            balance_difference=0.0,
            balance_check="ok",
            transactions=[],
        )

    # Detect delimiter
    sample = "\n".join(data_rows[:5])
    delimiter = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.reader(data_rows, delimiter=delimiter)
    header = next(reader, None)
    if not header:
        raise ValueError("Empty CSV bank statement")

    col_map = {_normalize_str(col): idx for idx, col in enumerate(header)}

    def find_col(*aliases: str) -> int | None:
        for a in aliases:
            for k, idx in col_map.items():
                if a in k:
                    return idx
        return None

    date_idx = find_col("date", "operation", "date op")
    val_date_idx = find_col("valeur", "value_date")
    label_idx = find_col("libelle", "description", "motif", "label", "detail")
    ref_idx = find_col("ref", "reference", "piece")
    debit_idx = find_col("debit", "deb")
    credit_idx = find_col("credit", "cred")
    amount_idx = find_col("montant", "amount")
    solde_idx = find_col("solde", "balance")

    if date_idx is None or (amount_idx is None and debit_idx is None and credit_idx is None):
        raise ValueError("CSV missing required date or amount columns")

    transactions: list[ParsedTransaction] = []
    line_index = 1
    dates: list[datetime.date] = []

    valid_indices = [idx for idx in (date_idx, label_idx, amount_idx) if idx is not None]
    max_idx = max(valid_indices) if valid_indices else 0

    for row in reader:
        if not row or len(row) <= max_idx:
            continue

        raw_date = row[date_idx].strip()
        if not raw_date:
            continue

        try:
            booking_date = _parse_date(raw_date)
        except ValueError:
            continue

        dates.append(booking_date)

        value_date = None
        if val_date_idx is not None and val_date_idx < len(row) and row[val_date_idx].strip():
            try:
                value_date = _parse_date(row[val_date_idx])
            except ValueError:
                pass

        raw_label = row[label_idx].strip() if label_idx is not None and label_idx < len(row) else "Mouvement bancaire"
        clean_label = re.sub(r"\s+", " ", raw_label).strip()

        ext_ref = row[ref_idx].strip() if ref_idx is not None and ref_idx < len(row) else None

        # Determine signed amount (+ credit, - debit)
        if amount_idx is not None and amount_idx < len(row) and row[amount_idx].strip():
            amount = _parse_amount(row[amount_idx])
        else:
            deb_val = _parse_amount(row[debit_idx]) if debit_idx is not None and debit_idx < len(row) else 0.0
            cred_val = _parse_amount(row[credit_idx]) if credit_idx is not None and credit_idx < len(row) else 0.0
            amount = round(cred_val - deb_val, 2)

        if amount == 0.0:
            continue

        s_hash = _compute_line_hash(line_index, booking_date.isoformat(), amount, raw_label)

        tx = ParsedTransaction(
            line_index=line_index,
            booking_date=booking_date,
            value_date=value_date,
            amount=amount,
            currency="MAD",
            raw_label=raw_label,
            clean_label=clean_label,
            external_reference=ext_ref,
            source_hash=s_hash,
        )
        transactions.append(tx)

        # If opening balance was not found in headers, check solde column
        if solde_idx is not None and solde_idx < len(row):
            current_solde = _parse_amount(row[solde_idx])
            if not opening_found and line_index == 1:
                opening_balance = round(current_solde - amount, 2)
                opening_found = True
            closing_balance = current_solde

        line_index += 1

    computed_closing, diff, check = verify_statement_balance(opening_balance, closing_balance, transactions)

    period_start = min(dates) if dates else None
    period_end = max(dates) if dates else None

    return ParsedStatement(
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        computed_closing_balance=computed_closing,
        balance_difference=diff,
        balance_check=check,
        currency="MAD",
        period_start=period_start,
        period_end=period_end,
        transactions=transactions,
    )


def parse_bank_statement_xlsx(content: bytes) -> ParsedStatement:
    """Parses an Excel XLSX bank statement using openpyxl."""
    import openpyxl  # type: ignore[import-untyped]

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    ws = wb.active
    if ws is None:
        raise ValueError("Empty Excel workbook")

    rows: list[list[Any]] = []
    for row in ws.iter_rows(values_only=True):
        if any(cell is not None for cell in row):
            rows.append(list(row))

    if not rows:
        raise ValueError("No data found in Excel sheet")

    # Convert rows to CSV-like text or parse directly
    header_idx = None
    opening_balance = 0.0
    closing_balance = 0.0
    opening_found = False

    for idx, r in enumerate(rows):
        row_str = " ".join(str(c or "") for c in r).lower()
        if "solde initial" in row_str or "solde depart" in row_str:
            nums = re.findall(r"[-+]?\d[\d\s]*[.,]?\d*", row_str)
            if nums:
                opening_balance = _parse_amount(nums[-1])
                opening_found = True
        if "solde final" in row_str or "solde fin" in row_str:
            nums = re.findall(r"[-+]?\d[\d\s]*[.,]?\d*", row_str)
            if nums:
                closing_balance = _parse_amount(nums[-1])
        norm_cells = [_normalize_str(c) for c in r]
        if any("date" in c for c in norm_cells) and any("debit" in c or "credit" in c or "montant" in c for c in norm_cells):
            header_idx = idx
            break

    if header_idx is None:
        header_idx = 0

    header = [_normalize_str(c) for c in rows[header_idx]]
    col_map = {col: idx for idx, col in enumerate(header)}

    def find_col(*aliases: str) -> int | None:
        for a in aliases:
            for k, idx in col_map.items():
                if a in k:
                    return idx
        return None

    date_idx = find_col("date", "operation")
    val_date_idx = find_col("valeur", "value")
    label_idx = find_col("libelle", "description", "label")
    ref_idx = find_col("ref", "reference")
    debit_idx = find_col("debit")
    credit_idx = find_col("credit")
    amount_idx = find_col("montant", "amount")
    solde_idx = find_col("solde", "balance")

    transactions: list[ParsedTransaction] = []
    dates: list[datetime.date] = []
    line_index = 1

    for r in rows[header_idx + 1:]:
        if date_idx is None or date_idx >= len(r) or r[date_idx] is None:
            continue
        try:
            booking_date = _parse_date(r[date_idx])
        except ValueError:
            continue

        dates.append(booking_date)

        value_date = None
        if val_date_idx is not None and val_date_idx < len(r) and r[val_date_idx]:
            try:
                value_date = _parse_date(r[val_date_idx])
            except ValueError:
                pass

        raw_label = str(r[label_idx] or "").strip() if label_idx is not None and label_idx < len(r) else "Mouvement bancaire"
        clean_label = re.sub(r"\s+", " ", raw_label).strip()

        ext_ref = str(r[ref_idx] or "").strip() if ref_idx is not None and ref_idx < len(r) else None

        if amount_idx is not None and amount_idx < len(r) and r[amount_idx] is not None:
            amount = _parse_amount(r[amount_idx])
        else:
            deb_val = _parse_amount(r[debit_idx]) if debit_idx is not None and debit_idx < len(r) else 0.0
            cred_val = _parse_amount(r[credit_idx]) if credit_idx is not None and credit_idx < len(r) else 0.0
            amount = round(cred_val - deb_val, 2)

        if amount == 0.0:
            continue

        s_hash = _compute_line_hash(line_index, booking_date.isoformat(), amount, raw_label)
        tx = ParsedTransaction(
            line_index=line_index,
            booking_date=booking_date,
            value_date=value_date,
            amount=amount,
            currency="MAD",
            raw_label=raw_label,
            clean_label=clean_label,
            external_reference=ext_ref,
            source_hash=s_hash,
        )
        transactions.append(tx)

        if solde_idx is not None and solde_idx < len(r) and r[solde_idx] is not None:
            curr_solde = _parse_amount(r[solde_idx])
            if not opening_found and line_index == 1:
                opening_balance = round(curr_solde - amount, 2)
                opening_found = True
            closing_balance = curr_solde

        line_index += 1

    computed_closing, diff, check = verify_statement_balance(opening_balance, closing_balance, transactions)

    return ParsedStatement(
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        computed_closing_balance=computed_closing,
        balance_difference=diff,
        balance_check=check,
        currency="MAD",
        period_start=min(dates) if dates else None,
        period_end=max(dates) if dates else None,
        transactions=transactions,
    )


def parse_bank_statement_pdf(content: bytes) -> ParsedStatement:
    """Parses a PDF bank statement using PyMuPDF (fitz) or PyPDF layout text extraction."""
    import fitz  # type: ignore[import-untyped]

    doc = fitz.open(stream=content, filetype="pdf")
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"

    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]

    opening_balance = 0.0
    closing_balance = 0.0

    # Look for opening balance
    for line in lines:
        lower = line.lower()
        if "solde initial" in lower or "ancien solde" in lower or "solde au" in lower or "solde depart" in lower:
            nums = re.findall(r"[-+]?\d[\d\s]*[.,]?\d*", line)
            if nums:
                opening_balance = _parse_amount(nums[-1])
        if "solde final" in lower or "nouveau solde" in lower or "solde de cloture" in lower:
            nums = re.findall(r"[-+]?\d[\d\s]*[.,]?\d*", line)
            if nums:
                closing_balance = _parse_amount(nums[-1])

    # Extract transaction lines (format: Date, Libellé, Débit/Crédit, Solde)
    date_regex = re.compile(r"^(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2})\b")
    transactions: list[ParsedTransaction] = []
    dates: list[datetime.date] = []
    line_index = 1

    for line in lines:
        m = date_regex.match(line)
        if not m:
            continue
        date_str = m.group(1)
        try:
            booking_date = _parse_date(date_str)
        except ValueError:
            continue

        # Look for numbers in remainder of line
        rest = line[m.end():].strip()
        # Find amounts
        amounts_found = re.findall(r"[-+]?\d[\d\s]*[.,]\d{2}", rest)
        if not amounts_found:
            continue

        # Last number might be balance or amount
        # First amount is usually the movement
        amt_str = amounts_found[0]
        amount = _parse_amount(amt_str)

        # Check if line indicates debit (virement émis, retrait, chèque émis, carte, frais)
        lower_rest = rest.lower()
        is_debit = any(k in lower_rest for k in ("debit", "retrait", "virement emis", "paiement", "prelevement", "frais", "commission"))
        is_credit = any(k in lower_rest for k in ("credit", "virement recu", "remise", "versement", "encaissement"))

        if is_debit and amount > 0:
            amount = -amount
        elif not is_credit and "-" in amt_str:
            amount = -abs(amount)

        if amount == 0.0:
            continue

        dates.append(booking_date)
        raw_label = rest.replace(amt_str, "").strip()
        clean_label = re.sub(r"\s+", " ", raw_label).strip() or "Mouvement bancaire"

        s_hash = _compute_line_hash(line_index, booking_date.isoformat(), amount, raw_label)
        tx = ParsedTransaction(
            line_index=line_index,
            booking_date=booking_date,
            value_date=None,
            amount=amount,
            currency="MAD",
            raw_label=raw_label,
            clean_label=clean_label,
            external_reference=None,
            source_hash=s_hash,
        )
        transactions.append(tx)
        line_index += 1

    computed_closing, diff, check = verify_statement_balance(opening_balance, closing_balance, transactions)

    return ParsedStatement(
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        computed_closing_balance=computed_closing,
        balance_difference=diff,
        balance_check=check,
        currency="MAD",
        period_start=min(dates) if dates else None,
        period_end=max(dates) if dates else None,
        transactions=transactions,
    )


def parse_bank_statement(content: bytes, filename: str) -> ParsedStatement:
    """Dispatches parsing based on filename extension (CSV, XLSX, PDF)."""
    fn_lower = filename.lower()
    if fn_lower.endswith(".csv"):
        return parse_bank_statement_csv(content)
    elif fn_lower.endswith((".xlsx", ".xls")):
        return parse_bank_statement_xlsx(content)
    elif fn_lower.endswith(".pdf"):
        return parse_bank_statement_pdf(content)
    else:
        # Default try CSV
        try:
            return parse_bank_statement_csv(content)
        except (ValueError, UnicodeDecodeError, csv.Error) as err:
            raise ValueError(f"Format de relevé bancaire non pris en charge pour le fichier '{filename}'") from err
