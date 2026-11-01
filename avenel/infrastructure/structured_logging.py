"""Structured JSON logging without document content or PII per ARCHITECTURE.md C.4."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Forbidden fields that must NEVER appear in logs
FORBIDDEN_FIELDS = {
    "document_content",
    "extracted_text",
    "raw_text",
    "ocr_text",
    "page_content",
    "rib",
    "rib_raw",
    "password",
    "client_secret",
    "secret_key",
    "api_key",
    "token",
    "authorization",
}

# Patterns to mask in messages
MASK_PATTERNS = [
    (re.compile(r"\b[0-9]{24}\b"), "[REDACTED_RIB]"),  # 24-digit Moroccan RIB
    (re.compile(r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
]


def sanitize_log_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively removes sensitive keys and masks sensitive patterns in log payloads."""
    cleaned: dict[str, Any] = {}
    for k, v in data.items():
        lower_k = k.lower()
        if any(f in lower_k for f in FORBIDDEN_FIELDS):
            cleaned[k] = "[REDACTED]"
            continue

        if isinstance(v, dict):
            cleaned[k] = sanitize_log_dict(v)
        elif isinstance(v, str):
            val_str = v
            for pattern, repl in MASK_PATTERNS:
                val_str = pattern.sub(repl, val_str)
            cleaned[k] = val_str
        elif isinstance(v, list):
            cleaned[k] = [
                sanitize_log_dict(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            cleaned[k] = v
    return cleaned


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records into single-line JSON adhering to Part E and ASVS logging rules."""

    def __init__(self, service_name: str = "avenel-api") -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        for pattern, repl in MASK_PATTERNS:
            msg = pattern.sub(repl, msg)

        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": msg,
        }

        # Contextual metadata attached to the record
        if hasattr(record, "tenant_id"):
            log_entry["tenant_id"] = str(record.tenant_id)
        if hasattr(record, "actor_id"):
            log_entry["actor_id"] = str(record.actor_id)
        if hasattr(record, "action"):
            log_entry["action"] = str(record.action)
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = str(record.trace_id)

        # Extra data dict if provided
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_entry["data"] = sanitize_log_dict(record.extra_data)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def setup_structured_logging(level: int = logging.INFO, service_name: str = "avenel-api") -> None:
    """Configures the root logger with StructuredJsonFormatter."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJsonFormatter(service_name=service_name))
    root = logging.getLogger()
    root.setLevel(level)
    # Remove existing handlers to avoid duplicates
    root.handlers = [handler]
