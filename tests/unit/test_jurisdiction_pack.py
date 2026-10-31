"""Validation tests for Moroccan jurisdiction pack rules against JSON Schema."""

import json
from pathlib import Path

import jsonschema
import yaml

PACK_DIR = Path(__file__).resolve().parent.parent.parent / "jurisdiction" / "ma"


def test_jurisdiction_pack_schema_validation():
    """All rules in jurisdiction/ma/*.yaml must validate against pack.schema.json."""
    schema_path = PACK_DIR / "pack.schema.json"
    assert schema_path.exists(), "pack.schema.json must exist"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    manifest_path = PACK_DIR / "manifest.yaml"
    assert manifest_path.exists(), "manifest.yaml must exist"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    rule_count = 0
    needs_expert_count = 0

    for filename in manifest.get("files", []):
        file_path = PACK_DIR / filename
        assert file_path.exists(), f"Pack file {filename} declared in manifest does not exist"

        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        assert isinstance(data, list), f"{filename} root must be a list of rules"

        for rule in data:
            rule_count += 1
            jsonschema.validate(instance=rule, schema=schema)
            if rule.get("status") == "needs_expert":
                needs_expert_count += 1

    assert rule_count > 0, "Jurisdiction pack must contain rules"
    assert needs_expert_count >= 10, "Every Part I item must be tagged as needs_expert"


def test_part_i_items_present_and_needs_expert():
    """Verify that all 10 Part I items from ARCHITECTURE.md are present with status: needs_expert."""
    manifest_path = PACK_DIR / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    all_rules: dict[str, dict] = {}
    for filename in manifest.get("files", []):
        file_path = PACK_DIR / filename
        rules = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        for r in rules:
            all_rules[r["key"]] = r

    expected_part_i_keys = [
        "vat.deduction.cash_limit.basis",             # 1. Cash payment limits basis (HT vs TTC)
        "vat.filing.deadline.wording",                 # 2. TVA return deadline wording
        "vat.withholding.ras_2026.thresholds",         # 3. LF 2026 withholding payer thresholds
        "vat.withholding.ras_2026.service_lists",      # 3. LF 2026 withholding service lists
        "vat.withholding.ras.accounts",               # 3. RAS ledger accounts
        "vat.rate.mapping_items",                      # 4. Item-to-rate mapping for 10%
        "identifiers.ice.check_digit_algorithm",       # 5. ICE check digit
        "cgnc.subaccounts.activity_specific",          # 6. Activity-specific CGNC sub-accounts
        "simpl_tva.xsd_version",                       # 7. SIMPL-TVA XSD version
        "simpl_tva.payment_method_codes",              # 7. SIMPL-TVA payment codes
        "compliance.cndp.provider_routes",             # 8. CNDP route
        "compliance.cndp.dpa_wording",                 # 8. DPA wording
        "compliance.cybersecurity.loi_05_20",          # 8. Loi 05-20
        "compliance.oec.ai_assisted_preparation",      # 9. OEC AI preparation position
        "compliance.oec.professional_secrecy",         # 9. OEC professional secrecy
        "einvoicing.decree_status",                    # 10. E-invoicing decree
        "einvoicing.ubl_profile",                      # 10. E-invoicing UBL profile
        "einvoicing.clearance_identifiers",            # 10. E-invoicing clearance IDs
    ]

    for key in expected_part_i_keys:
        assert key in all_rules, f"Missing Part I item in jurisdiction pack: {key}"
        assert all_rules[key]["status"] == "needs_expert", f"Rule {key} must have status: needs_expert"


def test_every_rule_has_non_empty_source():
    """Rule: every source: must be a quotable citation or 'unverified'; fails on empty source."""
    manifest_path = PACK_DIR / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    for filename in manifest.get("files", []):
        file_path = PACK_DIR / filename
        rules = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        for rule in rules:
            key = rule.get("key")
            source = rule.get("source")
            assert source is not None, f"Rule {key} in {filename} is missing 'source'"
            assert isinstance(source, str), f"Rule {key} in {filename} source must be a string"
            assert source.strip() != "", f"Rule {key} in {filename} has empty source"

    # Negative test on planted empty source
    schema_path = PACK_DIR / "pack.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    planted_empty_source_rule = {
        "key": "test.empty.source",
        "value": 123,
        "effective_from": "2026-01-01",
        "source": "",
        "status": "needs_expert",
    }
    import pytest
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=planted_empty_source_rule, schema=schema)

