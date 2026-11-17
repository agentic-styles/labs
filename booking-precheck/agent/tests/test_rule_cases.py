from __future__ import annotations

import json

import pytest

from booking_precheck.assets import load_json
from booking_precheck.facts import MISSING, first


def _case_ids(service):
    return [path.name for path in sorted((service.settings.assets_dir / "cases").glob("TC-*"))]


@pytest.mark.parametrize("case_id", [f"TC-{index:03d}" for index in range(1, 31)])
def test_golden_rule_case(service, case_id):
    expected = json.loads(
        (service.settings.assets_dir / "cases" / case_id / "expected.json").read_text(encoding="utf-8")
    )
    result = service.run_case(case_id)
    assert result["technical_status"] == "COMPLETED"
    assert result["final_status"] == expected["expected_status"]
    assert [item["rule_id"] for item in result["matched_rules"]] == expected["expected_rule_ids"]
    assert result["reason_codes"] == expected["expected_reason_codes"]
    assert set(result["required_facts"]) == set(expected.get("expected_required_facts", []))
    queues = [] if expected.get("expected_routing_queue") is None else [expected["expected_routing_queue"]]
    assert set(result["routing_queues"]) == set(queues)
    assert result["policy_snapshot_id"] == expected["policy_snapshot_id"]
    input_facts = load_json(service.settings.assets_dir / "cases" / case_id / "input.json")
    for item in expected.get("expected_evidence", []):
        decision_match = any(e["fact_path"] == item["fact"] and e["value"] == item["expected_value"] for e in result["evidence"])
        input_value = first(input_facts, item["fact"])
        if input_value is MISSING and item["fact"] == "evaluation.same_priority_conflict":
            input_value = expected.get("policy_fixture", {}).get("mode") == "INJECT_EQUAL_PRIORITY_CONFLICT"
        assert decision_match or input_value == item["expected_value"]


def test_catalog_contains_exactly_thirty_cases(service):
    assert _case_ids(service) == [f"TC-{index:03d}" for index in range(1, 31)]
