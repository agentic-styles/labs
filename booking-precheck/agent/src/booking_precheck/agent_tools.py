"""Standard LangGraph tools for the Day 1 single Agent."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command, interrupt

from .agent_contracts import ExtractedDocuments, ExtractedFactEvidence
from .facts import MISSING, first
from .rules import aggregate, evaluate_rules


def _source_by_type(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["document_type"]: item for item in state["source_documents"]}


DOCUMENT_KEYS = {"BOOKING_REQUEST": "booking_request", "PRELIMINARY_DGD": "dgd", "SDS_EXTRACT": "sds"}


def _attach_document_metadata(
    documents: dict[str, Any], source_by_type: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    for document_type, key in DOCUMENT_KEYS.items():
        document = documents.get(key)
        if not isinstance(document, dict):
            continue
        source = source_by_type.get(document_type, {})
        submitted_metadata = document.get("metadata") or {}
        field_confidences = submitted_metadata.get("field_confidences", {})
        document["metadata"] = {
            "document_id": source.get("document_id", f"UNKNOWN-{document_type}"),
            "document_version": source.get("document_version", 1),
            "document_type": document_type,
            "file_name": source.get("file_name", "unknown.pdf"),
            "mime_type": "application/pdf",
            "issued_at": submitted_metadata.get("issued_at"),
            "language": submitted_metadata.get("language", "en"),
            "synthetic": True,
            "extraction_confidence": submitted_metadata.get(
                "extraction_confidence", min(field_confidences.values(), default=0.5)
            ),
            "field_confidences": field_confidences,
        }
    return documents


def _required_decision_evidence_paths(facts: dict[str, Any], matches: list[dict[str, Any]]) -> list[str]:
    paths = []
    for match in matches:
        for path in match["matched_fact_paths"]:
            value = first(facts, path)
            if (
                path.startswith("documents.")
                and ".metadata." not in path
                and value is not MISSING
                and value is not None
                and not isinstance(value, (dict, list))
            ):
                paths.append(path)
    return list(dict.fromkeys(paths))


def _attach_evidence_metadata(
    evidence: list[dict[str, Any]],
    source_by_type: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_evidence = []
    for item in evidence:
        source = source_by_type.get(item["document_type"], {})
        normalized_evidence.append({
            **item,
            "document_id": source.get("document_id"),
            "document_version": source.get("document_version"),
        })
    return normalized_evidence


def _tool_command(runtime: ToolRuntime, tool_name: str, payload: dict[str, Any], **updates: Any) -> Command:
    trace = [*runtime.state.get("tool_trace", []), {"tool": tool_name, "status": "OK"}]
    return Command(update={
        **updates,
        "tool_trace": trace,
        "messages": [ToolMessage(
            content=json.dumps(payload, ensure_ascii=False, default=str),
            tool_call_id=runtime.tool_call_id or "unknown",
        )],
    })


@tool
def submit_extracted_facts(
    documents: ExtractedDocuments,
    runtime: ToolRuntime,
) -> Command:
    """Submit structured facts extracted from the supplied PDFs."""
    document_values = _attach_document_metadata(
        documents.model_dump(exclude_none=True), _source_by_type(runtime.state),
    )
    snapshot = runtime.state["snapshot"]
    facts = {
        "schema_version": "0.2",
        "fixture_type": "AGENT_EXTRACTED_CASE",
        "case_id": runtime.state.get("case_id"),
        "submitted_at": runtime.state.get("submitted_at", "2026-08-10T09:00:00+08:00"),
        "policy_context": {
            "snapshot_id": snapshot["snapshot_id"],
            "carrier_code": snapshot["carrier_code"],
            "route_id": "CNSHA-AEJEA-TRAIN-ME1",
            "training_only": True,
        },
        "documents": document_values,
    }
    return _tool_command(
        runtime, "submit_extracted_facts",
        {"ok": True, "accepted_documents": sorted(document_values), "next": "run_precheck_rules"},
        facts=facts,
    )


@tool
def run_precheck_rules(runtime: ToolRuntime) -> Command:
    """Run the authorized deterministic policy snapshot against accepted facts."""
    facts = runtime.state["facts"]
    roles = [party.get("role") for party in facts.get("documents", {}).get("booking_request", {}).get("parties", [])]
    facts = {**facts, "evaluation": {**facts.get("evaluation", {}), "has_consignee": "CONSIGNEE" in roles}}
    matches = evaluate_rules(facts, runtime.state["snapshot"])
    aggregate_result = aggregate(matches, runtime.state["snapshot"])
    required_evidence_paths = _required_decision_evidence_paths(facts, matches)
    next_tool = "submit_decision_evidence" if required_evidence_paths else "lookup_policy_evidence"
    return _tool_command(
        runtime, "run_precheck_rules",
        {"ok": True, "final_status": aggregate_result["final_status"],
         "matched_rule_ids": [item["rule_id"] for item in matches],
         "reason_codes": aggregate_result["reason_codes"],
         "required_evidence_paths": required_evidence_paths, "next": next_tool},
        facts=facts, matches=matches, aggregate_result=aggregate_result,
        required_evidence_paths=required_evidence_paths,
        decision_evidence=[],
        decision_evidence_complete=not required_evidence_paths,
    )


@tool
def submit_decision_evidence(
    evidence: list[ExtractedFactEvidence], runtime: ToolRuntime,
) -> Command:
    """Submit exact page evidence only for the fact paths requested by the rule evaluation."""
    normalized = _attach_evidence_metadata(
        [item.model_dump() for item in evidence], _source_by_type(runtime.state),
    )
    return _tool_command(
        runtime, "submit_decision_evidence",
        {"ok": True, "accepted_evidence": len(normalized), "next": "lookup_policy_evidence"},
        decision_evidence=normalized, decision_evidence_complete=True,
    )


@tool
def lookup_policy_evidence(rule_ids: list[str], runtime: ToolRuntime) -> Command:
    """Retrieve frozen policy evidence for the requested rule IDs."""
    requested = set(rule_ids)
    evidence = [
        {**item, "policy_document_id": document["policy_document_id"]}
        for document in runtime.state["policy_index"]["documents"]
        for item in document["rule_evidence"]
        if item["rule_id"] in requested
    ]
    return _tool_command(
        runtime, "lookup_policy_evidence",
        {"ok": True, "policy_evidence": evidence, "next": "respond_without_tool_calls"},
        policy_rule_ids=sorted(requested),
    )


@tool
def request_human_confirmation(
    fact_path: str, question: str, evidence_text: str, runtime: ToolRuntime,
) -> Command:
    """Pause when a material field cannot be established from document evidence."""
    confirmation = interrupt({"type": "BOOKING_FACT_CONFIRMATION", "fact_path": fact_path,
                              "question": question, "evidence_text": evidence_text})
    return _tool_command(
        runtime, "request_human_confirmation",
        {"ok": True, "human_confirmation": confirmation, "next": "continue_precheck"},
        human_confirmation=confirmation,
    )


PRECHECK_TOOLS: list[BaseTool] = [
    submit_extracted_facts, run_precheck_rules, submit_decision_evidence,
    lookup_policy_evidence, request_human_confirmation,
]
