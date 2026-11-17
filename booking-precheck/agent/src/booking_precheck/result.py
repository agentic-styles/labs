from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .contracts import PrecheckResult
from .facts import MISSING, first
from .rules import choose_next_action


def _policy_lookup(policy_index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for document in policy_index["documents"]:
        for evidence in document["rule_evidence"]:
            result[evidence["rule_id"]] = {**evidence, "policy_document_id": document["policy_document_id"]}
    return result


def compose_result(
    facts: dict[str, Any], snapshot: dict[str, Any], matches: list[dict[str, Any]], aggregated: dict[str, Any],
    policy_index: dict[str, Any], started_at: datetime, case_id: str | None, step_id: str | None,
    previous_run_id: str | None, trace_id: str | None, human_confirmation: dict[str, Any] | None = None,
    metrics: dict[str, int] | None = None,
    decision_evidence: list[dict[str, Any]] | None = None,
) -> PrecheckResult:
    policy_by_rule = _policy_lookup(policy_index)
    evidence: list[dict[str, Any]] = []
    evidence_by_key: dict[tuple[str, str], str] = {}
    submitted_by_path = {item["fact_path"]: item for item in decision_evidence or []}

    def add_fact_evidence(path: str, rule_id: str) -> str:
        key = (path, rule_id)
        if key in evidence_by_key:
            return evidence_by_key[key]
        value = first(facts, path)
        absent = value is MISSING or value is None
        root = path.split(".")[1] if path.startswith("documents.") and len(path.split(".")) > 1 else None
        document = facts.get("documents", {}).get(root) if root else None
        metadata = document.get("metadata", {}) if isinstance(document, dict) else {}
        submitted = submitted_by_path.get(path, {})
        evidence_id = f"FACT-{len(evidence)+1:03d}"
        evidence.append({
            "evidence_id": evidence_id, "evidence_type": "ASSERTED_ABSENCE" if absent else "DOCUMENT_FIELD",
            "fact_path": path, "value": None if absent else value,
            "document_id": submitted.get("document_id", metadata.get("document_id")),
            "document_version": submitted.get("document_version", metadata.get("document_version")),
            "document_type": submitted.get("document_type", metadata.get("document_type")),
            "policy_document_id": None, "rule_id": rule_id,
            "page": submitted.get("page"), "section": None,
            "evidence_text": submitted.get("evidence_text", f"{path} is absent" if absent else f"{path} = {value}"),
            "confidence": submitted.get("confidence", metadata.get("field_confidences", {}).get(path.rsplit(".", 1)[-1], metadata.get("extraction_confidence"))),
        })
        evidence_by_key[key] = evidence_id
        return evidence_id

    matched_rules = []
    for match in matches:
        fact_ids = [add_fact_evidence(path, match["rule_id"]) for path in match["matched_fact_paths"]]
        policy = policy_by_rule.get(match["rule_id"], {})
        policy_id = f"POLICY-{match['rule_id']}"
        evidence.append({
            "evidence_id": policy_id, "evidence_type": "POLICY_RULE", "fact_path": None, "value": None,
            "document_id": None, "document_version": None, "document_type": None,
            "policy_document_id": policy.get("policy_document_id"), "rule_id": match["rule_id"],
            "page": policy.get("page"), "section": "Rule evidence",
            "evidence_text": policy.get("evidence_text", match["source"]["evidence_excerpt"]), "confidence": None,
        })
        action = match["action"]
        matched_rules.append({
            "rule_id": match["rule_id"], "reason_code": action["reason_code"],
            "rule_result_status": action["result_status"], "message": action["message_template"],
            "routing_queue": action.get("routing_queue"), "pause_automation": action.get("pause_automation", False),
            "fact_evidence_ids": fact_ids, "policy_evidence_id": policy_id,
        })

    if human_confirmation:
        evidence.append({
            "evidence_id": f"HUMAN-{len(evidence)+1:03d}", "evidence_type": "HUMAN_CONFIRMATION",
            "fact_path": human_confirmation["fact_path"], "value": human_confirmation["confirmed_value"],
            "document_id": human_confirmation.get("source_document_id"), "document_version": None,
            "document_type": None, "policy_document_id": None, "rule_id": None, "page": None,
            "section": "Human confirmation", "evidence_text": human_confirmation.get("note", "Human-confirmed value"),
            "confidence": 1.0,
        })

    def atomic_facts(value: Any, path: str = ""):
        if isinstance(value, dict) and value:
            for key, child in value.items():
                yield from atomic_facts(child, f"{path}.{key}" if path else key)
        elif path and (path.startswith("documents.") or path.startswith("evaluation.") or path == "submitted_at"):
            # Arrays stay intact: party lists and subsidiary risks are single domain facts,
            # while nested objects are represented only by their atomic leaves.
            yield path, value

    observed_facts = dict(atomic_facts(facts))
    source_documents = []
    for document in facts.get("documents", {}).values():
        if not isinstance(document, dict):
            continue
        metadata = document.get("metadata", {})
        if metadata.get("document_id"):
            source_documents.append({
                "document_id": metadata["document_id"],
                "document_version": metadata.get("document_version"),
                "document_type": metadata.get("document_type"),
            })
    fact_snapshot_sha256 = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    booking_reference = first(facts, "documents.booking_request.booking_reference")
    if booking_reference is MISSING or booking_reference is None:
        booking_reference = "UNKNOWN"
    completed = datetime.now(timezone.utc)
    run_id = str(uuid4())
    return {
        "schema_version": "0.1", "run_id": run_id, "trace_id": trace_id or str(uuid4()),
        "technical_status": "COMPLETED", "case_id": case_id, "step_id": step_id,
        "previous_run_id": previous_run_id,
        "booking_reference": booking_reference,
        "policy_snapshot_id": snapshot["snapshot_id"], "started_at": started_at.isoformat(),
        "completed_at": completed.isoformat(), **aggregated, "next_action": choose_next_action(aggregated),
        "matched_rules": matched_rules, "evidence": evidence,
        "audit_context": {
            "fact_snapshot_ref": f"sha256:{fact_snapshot_sha256}",
            "fact_snapshot_sha256": fact_snapshot_sha256,
            "observed_fact_count": len(observed_facts),
            "source_documents": source_documents,
        },
        "metrics": metrics or {"duration_ms": max(0, int((completed-started_at).total_seconds()*1000)), "model_call_count": 0, "input_tokens": 0, "output_tokens": 0},
        "technical_error": None,
    }
