"""Jurisdiction pack loader and schema validator.

Loads Moroccan legal and tax rules from /jurisdiction/ma/ per Rule A.1.
Enforces:
- Schema validation against pack.schema.json
- Non-empty source citations
- Status tracking ('verified' vs 'needs_expert')
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]
import yaml  # type: ignore[import-untyped]

PACK_DIR = Path(__file__).resolve().parent.parent.parent / "jurisdiction" / "ma"


class JurisdictionPackLoader:
    def __init__(self, pack_dir: Path = PACK_DIR) -> None:
        self.pack_dir = pack_dir
        self.manifest: dict[str, Any] = {}
        self.rules: dict[str, dict[str, Any]] = {}
        self._load_pack()

    def _load_pack(self) -> None:
        schema_path = self.pack_dir / "pack.schema.json"
        if not schema_path.exists():
            raise FileNotFoundError(f"Pack schema not found at {schema_path}")

        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        manifest_path = self.pack_dir / "manifest.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found at {manifest_path}")

        self.manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        file_list = self.manifest.get("files", [])

        loaded_rules: dict[str, dict[str, Any]] = {}
        for filename in file_list:
            file_path = self.pack_dir / filename
            if not file_path.exists():
                raise FileNotFoundError(f"Jurisdiction file listed in manifest not found: {file_path}")

            content = yaml.safe_load(file_path.read_text(encoding="utf-8"))
            if not isinstance(content, list):
                raise TypeError(f"Jurisdiction file {filename} must contain a list of rules")

            for rule in content:
                jsonschema.validate(instance=rule, schema=schema)
                key = rule["key"]
                # Enforce rule citation non-emptiness
                source = rule.get("source", "")
                if not source or not str(source).strip():
                    raise ValueError(f"Rule {key} has missing or empty source citation")

                loaded_rules[key] = rule

        self.rules = loaded_rules

    @property
    def pack_version(self) -> str:
        return str(self.manifest.get("pack_version", "MA-2026.10.1"))

    def get_rule(self, key: str) -> dict[str, Any] | None:
        return self.rules.get(key)

    def is_rule_active(self, key: str) -> bool:
        rule = self.get_rule(key)
        if not rule:
            return False
        return rule.get("status") == "verified"

    def get_value(self, key: str, default: Any = None) -> Any:
        rule = self.get_rule(key)
        if not rule or rule.get("status") != "verified":
            return default
        return rule.get("value", default)


# Global singleton instance
_GLOBAL_PACK: JurisdictionPackLoader | None = None


def get_jurisdiction_pack() -> JurisdictionPackLoader:
    global _GLOBAL_PACK
    if _GLOBAL_PACK is None:
        _GLOBAL_PACK = JurisdictionPackLoader()
    return _GLOBAL_PACK


def get_cgnc_seed_accounts() -> list[dict[str, str]]:
    """Loads standard Moroccan CGNC seed accounts from /jurisdiction/ma/cgnc_seed.yaml."""
    pack = get_jurisdiction_pack()
    val = pack.get_value("cgnc.seed.accounts", [])
    if not isinstance(val, list):
        return []
    return [dict(a) for a in val]


def get_identifier_regex(identifier_type: str) -> re.Pattern[str]:
    """Loads identifier validation regex pattern from /jurisdiction/ma/identifiers.yaml."""
    pack = get_jurisdiction_pack()
    pattern_str = pack.get_value(f"identifiers.{identifier_type}.format")
    if not pattern_str or not isinstance(pattern_str, str):
        raise ValueError(f"Pattern for identifier '{identifier_type}' not found or invalid in jurisdiction pack")
    return re.compile(pattern_str)

