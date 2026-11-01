"""Data structures for Moroccan bank statement parsing and transactions."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedTransaction:
    line_index: int
    booking_date: datetime.date
    value_date: datetime.date | None
    amount: float  # Signed: positive = credit to account, negative = debit from account
    currency: str
    raw_label: str
    clean_label: str
    external_reference: str | None = None
    source_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_index": self.line_index,
            "booking_date": self.booking_date.isoformat(),
            "value_date": self.value_date.isoformat() if self.value_date else None,
            "amount": self.amount,
            "currency": self.currency,
            "raw_label": self.raw_label,
            "clean_label": self.clean_label,
            "external_reference": self.external_reference,
            "source_hash": self.source_hash,
        }


@dataclass
class ParsedStatement:
    opening_balance: float
    closing_balance: float
    computed_closing_balance: float
    balance_difference: float
    balance_check: str  # 'ok' or 'break'
    currency: str = "MAD"
    period_start: datetime.date | None = None
    period_end: datetime.date | None = None
    transactions: list[ParsedTransaction] = field(default_factory=list)

    @property
    def has_balance_break(self) -> bool:
        return self.balance_check == "break"

