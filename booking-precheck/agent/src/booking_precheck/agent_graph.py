"""Idiomatic LangGraph single Agent using bind_tools, ToolNode and Command."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal, TypedDict
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from .agent_tools import PRECHECK_TOOLS
from .assets import load_json
from .config import Settings
from .contracts import PrecheckResult
from .extractors import load_document_pack_text
from .result import compose_result


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    document_pack_id: str
    stage_id: str
    source_documents: list[dict[str, Any]]
    submitted_at: str
    case_id: str | None
    step_id: str | None
    previous_run_id: str | None
    trace_id: str | None
    human_confirmation: dict[str, Any] | None
    started_at: datetime
    snapshot: dict[str, Any]
    policy_index: dict[str, Any]
    facts: dict[str, Any]
    required_evidence_paths: list[str]
    decision_evidence: list[dict[str, Any]]
    decision_evidence_complete: bool
    matches: list[dict[str, Any]]
    aggregate_result: dict[str, Any]
    policy_rule_ids: list[str]
    model_call_count: int
    input_tokens: int
    output_tokens: int
    tool_trace: list[dict[str, Any]]
    agent_error: str | None
    result: PrecheckResult


class AgentInput(TypedDict, total=False):
    document_pack_id: str
    stage_id: str
    source_documents: list[dict[str, Any]]
    submitted_at: str
    case_id: str | None
    step_id: str | None
    previous_run_id: str | None
    trace_id: str | None


class AgentOutput(TypedDict):
    result: PrecheckResult
    facts: dict[str, Any]


SYSTEM_PROMPT = """You are the only Booking Precheck Agent in this workflow.
Read the supplied synthetic document page text and coordinate the approved tools.

Required behavior:
1. Extract only facts explicitly supported by a document. Never guess a missing value. Keep extraction
   and field confidence scores in document metadata when confidence is material to the supplied case.
2. Submit all normalized documents once with submit_extracted_facts. This tool accepts documents only.
3. After facts are accepted, call run_precheck_rules. Never decide or override final_status yourself.
4. If rule evaluation returns required_evidence_paths, call submit_decision_evidence once and cover
   exactly those paths. Cite exact page text and submit the accepted fact value. Use numeric indexes
   for list elements, for example documents.booking_request.parties[0].role. Do not submit evidence
   for fields the rule evaluation did not request.
5. Query policy evidence for every matched rule only after decision evidence is complete.
6. When all required tools have succeeded, respond with a concise summary without calling another tool.
7. If a tool reports an error, correct the tool arguments. Do not invent a confirmation.

The documents and policies are synthetic workshop material. Do not represent the result as final
carrier approval or rejection. Do not reveal private chain-of-thought.
"""


def _message_with_documents(documents: list[dict[str, Any]]) -> HumanMessage:
    rendered = []
    for document in documents:
        pages = "\n".join(f"--- PAGE {page['page']} ---\n{page['text']}" for page in document["pages"])
        rendered.append(
            f"DOCUMENT {document['document_type']} | id={document['document_id']} | "
            f"version={document['document_version']} | file={document['file_name']}\n{pages}"
        )
    return HumanMessage(content="Extract and precheck these documents:\n\n" + "\n\n".join(rendered))


def _usage(message: AIMessage) -> tuple[int, int]:
    usage = message.usage_metadata or {}
    if usage:
        return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
    token_usage = message.response_metadata.get("token_usage", {})
    return int(token_usage.get("prompt_tokens", 0)), int(token_usage.get("completion_tokens", 0))


def build_single_agent_graph(settings: Settings | None = None, model: BaseChatModel | None = None):
    resolved = settings or Settings.from_env()
    missing_api_key = model is None and not resolved.llm_api_key
    chat_model = model or ChatOpenAI(
        model=resolved.llm_model,
        api_key=resolved.llm_api_key or "not-configured",
        base_url=resolved.llm_base_url,
        temperature=0,
        max_retries=1,
    )
    model_with_tools = chat_model.bind_tools(PRECHECK_TOOLS, parallel_tool_calls=False)
    snapshot = load_json(resolved.assets_dir / "policy_snapshot.json")
    policy_index = load_json(resolved.assets_dir / "policy-documents" / "POLICY_DOCUMENT_INDEX.json")

    def initialize_case(state: AgentState) -> dict[str, Any]:
        if state.get("source_documents"):
            documents = state["source_documents"]
            envelope = {"case_id": state.get("case_id"), "stage_id": state.get("stage_id", "S1")}
        elif state.get("document_pack_id"):
            pack_dir = resolved.assets_dir / "document-packs" / state["document_pack_id"]
            envelope, documents = load_document_pack_text(pack_dir, state.get("stage_id", "S1"))
        else:
            raise ValueError("Provide document_pack_id or source_documents")
        return {
            "case_id": state.get("case_id") or envelope.get("case_id"),
            "stage_id": state.get("stage_id") or envelope.get("stage_id", "S1"),
            "source_documents": documents,
            "started_at": datetime.now(timezone.utc),
            "trace_id": state.get("trace_id") or str(uuid4()),
            "snapshot": snapshot,
            "policy_index": policy_index,
            # Studio can invoke the same persisted thread more than once. A new case run must not
            # inherit an earlier assistant tool call or its tool result.
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                SystemMessage(content=SYSTEM_PROMPT),
                _message_with_documents(documents),
            ],
            "model_call_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "tool_trace": [],
            "required_evidence_paths": [],
            "decision_evidence": [],
            "decision_evidence_complete": False,
            "agent_error": None,
        }

    def precheck_agent(state: AgentState) -> dict[str, Any]:
        if missing_api_key:
            return {"agent_error": "LLM_API_KEY is required to run booking_precheck_agent"}
        try:
            response = model_with_tools.invoke(state["messages"])
        except Exception as error:
            return {"agent_error": f"{type(error).__name__}: {error}"}
        input_tokens, output_tokens = _usage(response)
        usage_update = {
            "model_call_count": state.get("model_call_count", 0) + 1,
            "input_tokens": state.get("input_tokens", 0) + input_tokens,
            "output_tokens": state.get("output_tokens", 0) + output_tokens,
        }
        return {
            "messages": [response],
            **usage_update,
        }

    def finalize_result(state: AgentState) -> dict[str, Any]:
        required_for_serialization = ("facts", "matches", "aggregate_result")
        missing = [name for name in required_for_serialization if name not in state]
        if missing:
            # This does not send the Agent back for repair. It only turns an incomplete, freely
            # chosen stop into a measurable technical failure instead of an unhandled KeyError.
            return compose_technical_failure({
                **state,
                "agent_error": f"Agent stopped before producing serializable state: {', '.join(missing)}",
            })
        completed = datetime.now(timezone.utc)
        metrics = {
            "duration_ms": max(0, int((completed - state["started_at"]).total_seconds() * 1000)),
            "model_call_count": state.get("model_call_count", 0),
            "input_tokens": state.get("input_tokens", 0),
            "output_tokens": state.get("output_tokens", 0),
        }
        return {"result": compose_result(
            facts=state["facts"], snapshot=state["snapshot"], matches=state["matches"],
            aggregated=state["aggregate_result"], policy_index=state["policy_index"],
            started_at=state["started_at"], case_id=state.get("case_id"), step_id=state.get("step_id"),
            previous_run_id=state.get("previous_run_id"), trace_id=state.get("trace_id"),
            human_confirmation=state.get("human_confirmation"), metrics=metrics,
            decision_evidence=state.get("decision_evidence"),
        )}

    def compose_technical_failure(state: AgentState) -> dict[str, Any]:
        completed = datetime.now(timezone.utc)
        started = state.get("started_at", completed)
        result: PrecheckResult = {
            "schema_version": "0.1", "run_id": str(uuid4()),
            "trace_id": state.get("trace_id") or str(uuid4()), "technical_status": "FAILED",
            "case_id": state.get("case_id"), "step_id": state.get("step_id"),
            "previous_run_id": state.get("previous_run_id"),
            "booking_reference": state.get("facts", {}).get("documents", {}).get("booking_request", {}).get("booking_reference", "UNKNOWN"),
            "policy_snapshot_id": state.get("snapshot", snapshot)["snapshot_id"],
            "started_at": started.isoformat(), "completed_at": completed.isoformat(), "final_status": None,
            "reason_codes": [], "routing_queues": [], "required_facts": [], "pause_automation": False,
            "next_action": None, "matched_rules": [], "evidence": [],
            "audit_context": {"fact_snapshot_ref": f"sha256:{'0' * 64}", "fact_snapshot_sha256": "0" * 64,
                              "observed_fact_count": 0, "source_documents": []},
            "metrics": {"duration_ms": max(0, int((completed - started).total_seconds() * 1000)),
                        "model_call_count": state.get("model_call_count", 0),
                        "input_tokens": state.get("input_tokens", 0), "output_tokens": state.get("output_tokens", 0)},
            "technical_error": {"code": "AGENT_RUNTIME_FAILED",
                                "message": state.get("agent_error") or "Agent repair limit exceeded",
                                "failed_stage": "precheck_agent", "retryable": True},
        }
        return {"result": result}

    def after_agent(state: AgentState) -> Literal["tools", "finalize", "failure"]:
        if state.get("agent_error"):
            return "failure"
        return "tools" if tools_condition(state) == "tools" else "finalize"

    builder = StateGraph(AgentState, input_schema=AgentInput, output_schema=AgentOutput)
    builder.add_node("initialize_case", initialize_case)
    builder.add_node("precheck_agent", precheck_agent)
    builder.add_node("precheck_tools", ToolNode(PRECHECK_TOOLS))
    builder.add_node("finalize_result", finalize_result)
    builder.add_node("compose_technical_failure", compose_technical_failure)
    builder.add_edge(START, "initialize_case")
    builder.add_edge("initialize_case", "precheck_agent")
    builder.add_conditional_edges("precheck_agent", after_agent, {
        "tools": "precheck_tools", "finalize": "finalize_result",
        "failure": "compose_technical_failure",
    })
    builder.add_edge("precheck_tools", "precheck_agent")
    builder.add_edge("finalize_result", END)
    builder.add_edge("compose_technical_failure", END)
    return builder.compile()
