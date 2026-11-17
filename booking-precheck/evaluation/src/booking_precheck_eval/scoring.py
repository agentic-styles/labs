from __future__ import annotations

import math
import re
from datetime import date
from typing import Any


MISSING = object()


def resolve(data: Any, path: str) -> Any:
    if path == "documents.booking_request.parties.consignee":
        parties = resolve(data, "documents.booking_request.parties")
        if isinstance(parties, list):
            return next((item.get("name") for item in parties if item.get("role") == "CONSIGNEE"), MISSING)
    value = data
    for name, indexes in re.findall(r"([^.\[\]]+)((?:\[\d+\])*)", path):
        if not isinstance(value, dict) or name not in value:
            return MISSING
        value = value[name]
        for index in re.findall(r"\[(\d+)\]", indexes):
            position = int(index)
            if not isinstance(value, list) or position >= len(value):
                return MISSING
            value = value[position]
    return value


def _normalize(value: Any, operations: list[str]) -> Any:
    if value is MISSING:
        return value
    result = value
    for operation in operations:
        if operation == "TRIM" and isinstance(result, str):
            result = result.strip()
        elif operation == "UPPERCASE" and isinstance(result, str):
            result = result.upper()
        elif operation == "COLLAPSE_WHITESPACE" and isinstance(result, str):
            result = " ".join(result.split())
        elif operation == "UN_NUMBER_CANONICAL" and isinstance(result, str):
            result = "UN" + re.sub(r"\D", "", result.upper().removeprefix("UN"))
        elif operation == "PSN_CANONICAL" and isinstance(result, str):
            result = " ".join(result.split()).upper()
        elif operation == "UNIT_TO_KG":
            if isinstance(result, dict) and "value" in result:
                unit = str(result.get("unit", "KG")).upper()
                result = float(result["value"]) * (1000 if unit in {"T", "TON", "TONNE"} else 1)
        elif operation == "DATE_TO_ISO" and result is not None:
            result = date.fromisoformat(str(result)[:10]).isoformat()
    return result


def _set_metrics(expected: set[str], actual: set[str]) -> dict[str, float]:
    if not actual:
        precision = 1.0 if not expected else 0.0
    else:
        precision = len(expected & actual) / len(actual)
    recall = 1.0 if not expected else len(expected & actual) / len(expected)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1}


def _expected_queues(expected: dict[str, Any]) -> set[str]:
    if "expected_routing_queues" in expected:
        return set(expected["expected_routing_queues"])
    queue = expected.get("expected_routing_queue")
    return set() if queue is None else {queue}


def _evidence_match(result: dict[str, Any], item: dict[str, Any]) -> bool:
    for actual in result.get("evidence", []):
        if actual.get("fact_path") != item["fact"] or actual.get("value") != item.get("expected_value"):
            continue
        if item.get("source_document_id") and actual.get("document_id") != item["source_document_id"]:
            continue
        return True
    if item["fact"].endswith(".metadata.document_version"):
        return any(
            source.get("document_version") == item.get("expected_value")
            and (
                not item.get("source_document_id")
                or source.get("document_id") == item.get("source_document_id")
            )
            for source in result.get("audit_context", {}).get("source_documents", [])
        )
    return False


def _expected_evidence_check(
    result: dict[str, Any], expected_evidence: list[dict[str, Any]], facts: dict[str, Any] | None,
) -> bool | None:
    if all(_evidence_match(result, item) for item in expected_evidence):
        return True
    if facts is None:
        return None
    for item in expected_evidence:
        actual = resolve(facts, item["fact"])
        if item["fact"] == "evaluation.has_consignee" and actual is MISSING:
            parties = resolve(facts, "documents.booking_request.parties")
            actual = isinstance(parties, list) and any(party.get("role") == "CONSIGNEE" for party in parties)
        if (None if actual is MISSING else actual) != item.get("expected_value"):
            return False
    return True


def _evidence_integrity(result: dict[str, Any], *, require_document_evidence: bool) -> dict[str, Any]:
    evidence = result.get("evidence", [])
    by_id = {item.get("evidence_id"): item for item in evidence}
    errors: list[str] = []
    for match in result.get("matched_rules", []):
        policy = by_id.get(match.get("policy_evidence_id"))
        if not policy or policy.get("evidence_type") != "POLICY_RULE" or policy.get("rule_id") != match.get("rule_id"):
            errors.append(f"{match.get('rule_id')}: invalid policy evidence")
        elif not policy.get("policy_document_id") or not policy.get("page") or not policy.get("evidence_text"):
            errors.append(f"{match.get('rule_id')}: incomplete policy evidence")
        for evidence_id in match.get("fact_evidence_ids", []):
            fact = by_id.get(evidence_id)
            if not fact:
                errors.append(f"{match.get('rule_id')}: missing fact evidence {evidence_id}")
            elif require_document_evidence and fact.get("evidence_type") == "DOCUMENT_FIELD" and (
                not fact.get("document_id") or not fact.get("page") or not fact.get("evidence_text")
            ):
                errors.append(f"{match.get('rule_id')}: incomplete document evidence {evidence_id}")
    return {"valid": not errors, "errors": errors}


def score_result(
    result: dict[str, Any], expected: dict[str, Any], *, require_document_evidence: bool = True,
    facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expected_rules = set(expected.get("expected_rule_ids", []))
    actual_rules = {item.get("rule_id") for item in result.get("matched_rules", [])}
    expected_reasons = set(expected.get("expected_reason_codes", []))
    expected_evidence = expected.get("expected_evidence", [])
    checks = {
        "technical_completed": result.get("technical_status") == "COMPLETED",
        "status": result.get("final_status") == expected.get("expected_status"),
        "reason_codes": set(result.get("reason_codes", [])) == expected_reasons,
        "rules": actual_rules == expected_rules,
        "routing_queues": set(result.get("routing_queues", [])) == _expected_queues(expected),
        "required_facts": set(result.get("required_facts", [])) == set(expected.get("expected_required_facts", [])),
        "policy_snapshot": (
            "policy_snapshot_id" not in expected
            or result.get("policy_snapshot_id") == expected.get("policy_snapshot_id")
        ),
        "expected_evidence": _expected_evidence_check(result, expected_evidence, facts),
    }
    if "expected_next_action" in expected:
        checks["next_action"] = result.get("next_action") == expected.get("expected_next_action")
    integrity = _evidence_integrity(result, require_document_evidence=require_document_evidence)
    checks["evidence_integrity"] = integrity["valid"]
    evaluated_checks = [value for value in checks.values() if value is not None]
    return {
        "passed": all(evaluated_checks),
        "checks": checks,
        "check_coverage": len(evaluated_checks) / len(checks),
        "rule_metrics": _set_metrics(expected_rules, actual_rules),
        "evidence_integrity": integrity,
        "critical_false_clear": (
            expected.get("expected_status") == "PRECHECK_BLOCKED"
            and result.get("final_status") == "PRECHECK_PASS"
        ),
    }


def score_document_facts(facts: dict[str, Any] | None, truth: dict[str, Any] | None) -> dict[str, Any]:
    if facts is None or truth is None:
        return {"available": False, "correct": 0, "total": 0, "accuracy": None, "errors": []}
    errors = []
    total = 0
    correct = 0
    for document in truth.get("documents", []):
        for item in document.get("facts", []):
            total += 1
            actual = resolve(facts, item["fact_path"])
            expected = item.get("expected_value")
            operations = item.get("normalization", [])
            if _normalize(actual, operations) == _normalize(expected, operations):
                correct += 1
            else:
                errors.append({
                    "fact_path": item["fact_path"],
                    "expected": expected,
                    "actual": None if actual is MISSING else actual,
                })
    return {
        "available": True,
        "correct": correct,
        "total": total,
        "accuracy": 1.0 if total == 0 else correct / total,
        "errors": errors,
    }


def percentile(values: list[int], percentile_value: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]
