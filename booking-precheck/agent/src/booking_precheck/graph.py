from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .assets import load_json
from .config import Settings
from .contracts import PrecheckResult
from .result import compose_result
from .rules import aggregate, evaluate_rules


class PrecheckState(TypedDict, total=False):
    facts: dict[str, Any]
    snapshot: dict[str, Any]
    policy_index: dict[str, Any]
    policy_fixture: dict[str, Any] | None
    case_id: str | None
    step_id: str | None
    previous_run_id: str | None
    trace_id: str | None
    human_confirmation: dict[str, Any] | None
    started_at: datetime
    matches: list[dict[str, Any]]
    aggregate_result: dict[str, Any]
    result: PrecheckResult


def _prepare(state: PrecheckState) -> dict[str, Any]:
    facts = dict(state["facts"])
    roles = [party.get("role") for party in facts.get("documents", {}).get("booking_request", {}).get("parties", [])]
    evaluation = {**facts.get("evaluation", {}), "has_consignee": "CONSIGNEE" in roles}
    if (state.get("policy_fixture") or {}).get("mode") == "INJECT_EQUAL_PRIORITY_CONFLICT":
        evaluation["same_priority_conflict"] = True
    facts["evaluation"] = evaluation
    return {"started_at": datetime.now(timezone.utc), "case_id": state.get("case_id") or facts.get("case_id"), "facts": facts}


def _evaluate(state: PrecheckState) -> dict[str, Any]:
    return {"matches": evaluate_rules(state["facts"], state["snapshot"], state.get("policy_fixture"))}


def _aggregate(state: PrecheckState) -> dict[str, Any]:
    return {"aggregate_result": aggregate(state["matches"], state["snapshot"])}


def _compose(state: PrecheckState) -> dict[str, Any]:
    return {"result": compose_result(
        facts=state["facts"], snapshot=state["snapshot"], matches=state["matches"],
        aggregated=state["aggregate_result"], policy_index=state["policy_index"],
        started_at=state["started_at"], case_id=state.get("case_id"), step_id=state.get("step_id"),
        previous_run_id=state.get("previous_run_id"), trace_id=state.get("trace_id"),
        human_confirmation=state.get("human_confirmation"),
    )}


def build_rule_baseline_graph():
    builder = StateGraph(PrecheckState)
    builder.add_node("prepare", _prepare)
    builder.add_node("evaluate_rules", _evaluate)
    builder.add_node("aggregate_findings", _aggregate)
    builder.add_node("compose_auditable_result", _compose)
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "evaluate_rules")
    builder.add_edge("evaluate_rules", "aggregate_findings")
    builder.add_edge("aggregate_findings", "compose_auditable_result")
    builder.add_edge("compose_auditable_result", END)
    return builder.compile()


def build_graph():
    """Backward-compatible alias for the deterministic rule baseline."""
    return build_rule_baseline_graph()


def build_studio_graph(settings: Settings | None = None):
    """Build the workflow with policy context loaded automatically for Studio."""
    resolved = settings or Settings.from_env()
    snapshot = load_json(resolved.assets_dir / "policy_snapshot.json")
    policy_index = load_json(resolved.assets_dir / "policy-documents" / "POLICY_DOCUMENT_INDEX.json")

    def load_policy_context(_: PrecheckState) -> dict[str, Any]:
        return {"snapshot": snapshot, "policy_index": policy_index}

    builder = StateGraph(PrecheckState)
    builder.add_node("load_policy_context", load_policy_context)
    builder.add_node("prepare", _prepare)
    builder.add_node("evaluate_rules", _evaluate)
    builder.add_node("aggregate_findings", _aggregate)
    builder.add_node("compose_auditable_result", _compose)
    builder.add_edge(START, "load_policy_context")
    builder.add_edge("load_policy_context", "prepare")
    builder.add_edge("prepare", "evaluate_rules")
    builder.add_edge("evaluate_rules", "aggregate_findings")
    builder.add_edge("aggregate_findings", "compose_auditable_result")
    builder.add_edge("compose_auditable_result", END)
    return builder.compile()
