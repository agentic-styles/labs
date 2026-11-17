from __future__ import annotations

import json

import pytest

from booking_precheck.assets import materialize_business_steps
from booking_precheck.facts import first


@pytest.mark.parametrize("case_id", [f"BA-{index:03d}" for index in range(1, 13)])
def test_business_acceptance_case(service, case_id):
    expected = json.loads(
        (service.settings.assets_dir / "business-cases" / case_id / "expected.json").read_text(encoding="utf-8")
    )
    results = service.run_business_case(case_id)
    materialized = materialize_business_steps(service.settings.assets_dir / "business-cases" / case_id / "input.json")
    assert len(results) == len(expected["step_expectations"])
    for index, (result, step) in enumerate(zip(results, expected["step_expectations"])):
        assert result["step_id"] == step["step_id"]
        assert result["final_status"] == step["expected_status"]
        assert {item["rule_id"] for item in result["matched_rules"]} == set(step["expected_rule_ids"])
        assert set(result["reason_codes"]) == set(step["expected_reason_codes"])
        assert set(result["routing_queues"]) == set(step["expected_routing_queues"])
        assert set(result["required_facts"]) == set(step.get("expected_required_facts", []))
        assert result["next_action"] == step["expected_next_action"]
        assert result["policy_snapshot_id"] == step["policy_snapshot_id"]
        assert result["previous_run_id"] == (None if index == 0 else results[index - 1]["run_id"])
        for fact in step.get("expected_evidence", []):
            decision_match = any(item["fact_path"] == fact["fact"] and item["value"] == fact["expected_value"] for item in result["evidence"])
            input_value = first(materialized[index][1], fact["fact"])
            if fact["fact"] == "evaluation.has_consignee":
                parties = materialized[index][1]["documents"]["booking_request"]["parties"]
                input_value = any(party.get("role") == "CONSIGNEE" for party in parties)
            assert decision_match or input_value == fact["expected_value"]
