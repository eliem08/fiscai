"""JSON Schemas and Pydantic models for Classifier and Extractor agents."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

CLASSIFIER_INPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ClassifierAgentInput",
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "page_count": {"type": "integer", "minimum": 1},
    },
    "required": ["text", "page_count"],
}

CLASSIFIER_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ClassifierAgentOutput",
    "type": "object",
    "properties": {
        "doc_type": {
            "type": "string",
            "enum": [
                "purchase_invoice",
                "sales_invoice",
                "credit_note",
                "receipt",
                "bank_statement",
                "expense_note",
                "customs_document",
                "other",
            ],
        },
        "language": {"type": "string", "enum": ["fr", "ar", "bilingual"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "page_roles": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["doc_type", "language", "confidence"],
}

EXTRACTOR_INPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ExtractorAgentInput",
    "type": "object",
    "properties": {
        "doc_type": {"type": "string"},
        "full_text": {"type": "string"},
        "lines": {"type": "array"},
        "words": {"type": "array"},
    },
    "required": ["doc_type", "full_text"],
}

EXTRACTOR_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ExtractorAgentOutput",
    "type": "object",
    "properties": {
        "fields": {"type": "object"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["fields", "confidence"],
}


class ExtractedField(BaseModel):
    value: Any = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    page: int = 1
    bbox: list[float] | None = None  # [x0, y0, x1, y1] normalized to [0.0, 1.0]


class ExtractedLineItem(BaseModel):
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    line_ht: float | None = None
    vat_rate: float | None = None
    vat_amount: float | None = None


class ExtractedTaxRate(BaseModel):
    rate: float
    base_ht: float
    tax_amount: float


class ExtractionResult(BaseModel):
    invoice_number: ExtractedField = Field(default_factory=ExtractedField)
    invoice_date: ExtractedField = Field(default_factory=ExtractedField)
    due_date: ExtractedField = Field(default_factory=ExtractedField)
    supplier_name: ExtractedField = Field(default_factory=ExtractedField)
    supplier_ice: ExtractedField = Field(default_factory=ExtractedField)
    supplier_if: ExtractedField = Field(default_factory=ExtractedField)
    supplier_rc: ExtractedField = Field(default_factory=ExtractedField)
    supplier_address: ExtractedField = Field(default_factory=ExtractedField)
    supplier_is_auto_entrepreneur: ExtractedField = Field(default_factory=ExtractedField)
    client_name: ExtractedField = Field(default_factory=ExtractedField)
    client_ice: ExtractedField = Field(default_factory=ExtractedField)
    client_if: ExtractedField = Field(default_factory=ExtractedField)
    payment_method: ExtractedField = Field(default_factory=ExtractedField)
    currency: ExtractedField = Field(default_factory=lambda: ExtractedField(value="MAD"))
    total_ht: ExtractedField = Field(default_factory=ExtractedField)
    total_vat: ExtractedField = Field(default_factory=ExtractedField)
    total_ttc: ExtractedField = Field(default_factory=ExtractedField)
    tax_breakdown: list[ExtractedTaxRate] = Field(default_factory=list)
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
