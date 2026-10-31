"""Proposal set canonical hash implementation per ARCHITECTURE.md Section D.4.

subject_hash = sha256(canonical_json(sorted proposals of the revision, each with sorted lines, plus accepted matches))
Canonical JSON: sorted keys, no whitespace, decimals as strings with two places, dates ISO-8601.
"""

from __future__ import annotations

import decimal
import hashlib
import json
from datetime import date, datetime
from typing import Any


def decimal_serializer(obj: Any) -> Any:
    if isinstance(obj, decimal.Decimal):
        return f"{obj:.2f}"
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable in canonical JSON")


def canonical_json(data: Any) -> str:
    """Serialize data to canonical JSON (sorted keys, no whitespace, decimals as 2-place strings)."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        default=decimal_serializer,
        ensure_ascii=True,
    )


def compute_proposal_set_hash(
    proposals: list[dict[str, Any]],
    accepted_matches: list[dict[str, Any]],
) -> str:
    """Compute deterministic SHA-256 hash of proposals, lines, and accepted matches.

    Proposals and their lines must be deterministically sorted before hashing.
    """
    sorted_proposals = []
    for prop in sorted(proposals, key=lambda p: str(p.get("id", ""))):
        prop_copy = dict(prop)
        lines = prop_copy.get("lines", [])
        sorted_lines = sorted(lines, key=lambda line_item: int(line_item.get("line_no", 0)))
        prop_copy["lines"] = sorted_lines
        sorted_proposals.append(prop_copy)

    sorted_matches = sorted(
        accepted_matches, key=lambda m: str(m.get("id", ""))
    )

    canonical_payload = {
        "accepted_matches": sorted_matches,
        "proposals": sorted_proposals,
    }

    raw_json = canonical_json(canonical_payload)
    return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
