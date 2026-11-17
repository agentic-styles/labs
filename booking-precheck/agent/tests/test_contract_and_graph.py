from __future__ import annotations

import json

from jsonschema import Draft202012Validator, FormatChecker


def test_all_rule_case_results_follow_output_contract(service):
    schema = json.loads(
        (service.settings.assets_dir / "PRECHECK_RESULT_SCHEMA.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for index in range(1, 31):
        result = service.run_case(f"TC-{index:03d}")
        errors = sorted(validator.iter_errors(result), key=lambda error: list(error.path))
        assert not errors, f"TC-{index:03d}: {[error.message for error in errors]}"


def test_compiled_graph_exposes_teaching_nodes(service):
    nodes = set(service.graph.get_graph().nodes)
    assert {"prepare", "evaluate_rules", "aggregate_findings", "compose_auditable_result"} <= nodes


def test_studio_graph_loads_policy_context_and_runs_case(service):
    from booking_precheck.assets import load_json
    from booking_precheck.graph import build_studio_graph

    facts = load_json(service.settings.assets_dir / "cases" / "TC-014" / "input.json")
    graph = build_studio_graph(service.settings)
    state = graph.invoke({"facts": facts, "case_id": "TC-014"})
    assert state["result"]["final_status"] == "MANUAL_REVIEW"
    assert state["result"]["reason_codes"] == ["CON-GROSS-WEIGHT"]
    assert "load_policy_context" in graph.get_graph().nodes


def test_studio_output_schema_exposes_typed_precheck_result(service):
    from booking_precheck.graph import build_studio_graph

    schema = build_studio_graph(service.settings).get_output_jsonschema()
    result_schema = schema["$defs"]["PrecheckResult"]
    assert "final_status" in result_schema["properties"]
    assert "matched_rules" in result_schema["properties"]
    assert "evidence" in result_schema["properties"]
    assert "audit_context" in result_schema["properties"]
    assert "metrics" in result_schema["properties"]


def test_langgraph_version_meets_requested_floor():
    from importlib.metadata import version
    from packaging.version import Version
    assert Version(version("langgraph")) >= Version("1.2.10")
