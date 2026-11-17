from __future__ import annotations

from typing import Any

from .facts import evaluate_condition, predicate_fact_paths


def evaluate_rules(facts: dict[str, Any], snapshot: dict[str, Any], policy_fixture: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    evaluation_facts = dict(facts)
    if policy_fixture and policy_fixture.get("mode") == "INJECT_EQUAL_PRIORITY_CONFLICT":
        evaluation_facts = {**facts, "evaluation": {**facts.get("evaluation", {}), "same_priority_conflict": True}}
    matches = []
    for rule in snapshot["rules"]:
        if not rule.get("enabled", True):
            continue
        if evaluate_condition(evaluation_facts, rule["condition"]):
            matches.append({**rule, "matched_fact_paths": list(dict.fromkeys(predicate_fact_paths(rule["condition"])))})
    return sorted(matches, key=lambda item: (-item["priority"], item["rule_id"]))


def aggregate(matches: list[dict[str, Any]], snapshot: dict[str, Any]) -> dict[str, Any]:
    if not matches:
        return {
            "final_status": snapshot["default_status"], "reason_codes": [], "routing_queues": [],
            "required_facts": [], "pause_automation": False,
        }
    precedence = snapshot["aggregation_policy"]["status_precedence"]
    rank = {status: len(precedence) - index for index, status in enumerate(precedence)}
    final_status = max((item["action"]["result_status"] for item in matches), key=rank.get)
    return {
        "final_status": final_status,
        "reason_codes": list(dict.fromkeys(item["action"]["reason_code"] for item in matches)),
        "routing_queues": list(dict.fromkeys(item["action"].get("routing_queue") for item in matches if item["action"].get("routing_queue"))),
        # required_facts means information the customer must still provide. Fields quoted by
        # blocking/manual rules are evidence inputs, not missing information.
        "required_facts": list(dict.fromkeys(
            path for item in matches if item["action"]["result_status"] == "REQUIRE_INFORMATION"
            for path in item["action"].get("required_fact_paths", [])
        )),
        "pause_automation": any(item["action"].get("pause_automation", False) for item in matches),
    }


def choose_next_action(aggregate_result: dict[str, Any]) -> str:
    status = aggregate_result["final_status"]
    reasons = set(aggregate_result["reason_codes"])
    queues = aggregate_result["routing_queues"]
    if status == "PRECHECK_PASS": return "FORWARD_TO_DG_DESK"
    if status == "PRECHECK_BLOCKED":
        if "DOC-SDS-FRESHNESS" in reasons: return "PAUSE_AUTOMATION_AND_REQUEST_CURRENT_SDS_EXTRACT"
        if len(reasons) > 1: return "PAUSE_AUTOMATION_AND_REPORT_ALL_FINDINGS"
        return "PAUSE_AUTOMATION"
    if status == "REQUIRE_INFORMATION":
        if len(reasons) > 1: return "REQUEST_ALL_MISSING_INFORMATION"
        if "DOC-DGD-REQUIRED" in reasons: return "REQUEST_PRELIMINARY_DGD"
        return "REQUEST_MISSING_INFORMATION"
    if reasons == {"DOC-KEY-FIELD-LOW-CONFIDENCE"}: return "PAUSE_FOR_DOCUMENT_REVIEW"
    if queues == ["DG_DESK"]: return "ROUTE_TO_DG_DESK"
    if set(queues) == {"ROUTE_DESK", "POLICY_OWNER"}: return "ROUTE_TO_ROUTE_DESK_AND_POLICY_OWNER"
    if len(queues) > 1: return "ROUTE_TO_ALL_REQUIRED_QUEUES"
    if queues: return f"ROUTE_TO_{queues[0]}"
    return "MANUAL_REVIEW"
