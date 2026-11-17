from __future__ import annotations

from copy import deepcopy
from typing import Any

from booking_precheck.agent_graph import build_single_agent_graph
from booking_precheck.agent_contracts import ExtractedFactEvidence
from booking_precheck.agent_tools import submit_decision_evidence, submit_extracted_facts
from booking_precheck.assets import load_json
from booking_precheck.extractors import extract_document_pack
from jsonschema import Draft202012Validator
import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, ValidationError


class ScriptedModel(BaseChatModel):
    responses: list[Any]
    requests: list[list[BaseMessage]] = Field(default_factory=list)
    bound_tool_names: list[str] = Field(default_factory=list)
    cursor: int = 0

    @property
    def _llm_type(self):
        return "scripted-tool-chat-model"

    def bind_tools(self, tools, **kwargs):
        self.bound_tool_names = [item.name for item in tools]
        return self

    def _generate(
        self, messages: list[BaseMessage], stop=None,
        run_manager: CallbackManagerForLLMRun | None = None, **kwargs,
    ) -> ChatResult:
        self.requests.append(deepcopy(messages))
        if self.cursor >= len(self.responses):
            raise AssertionError("Agent made more model calls than scripted")
        response = self.responses[self.cursor]
        self.cursor += 1
        if isinstance(response, Exception):
            raise response
        return ChatResult(generations=[ChatGeneration(message=response)])


def _turn(content="", tool_call=None, input_tokens=0, output_tokens=0):
    return AIMessage(
        content=content,
        tool_calls=[] if tool_call is None else [tool_call],
        usage_metadata={"input_tokens": input_tokens, "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens},
    )


def _extracted_documents(settings):
    facts = extract_document_pack(settings.assets_dir / "document-packs" / "DP-003")["documents"]
    documents = deepcopy(facts)
    for document in documents.values():
        if not document:
            continue
        metadata = document.pop("metadata")
        document["metadata"] = {"issued_at": metadata.get("issued_at"), "language": metadata.get("language", "en")}
    return documents


def test_extraction_evidence_requires_value_and_accepts_indexed_paths():
    common = {
        "fact_path": "documents.booking_request.parties[1].role",
        "document_type": "BOOKING_REQUEST",
        "page": 1,
        "evidence_text": "Consignee SYNTHETIC JEBEL ALI TRADING LLC",
        "confidence": 1.0,
    }

    with pytest.raises(ValidationError):
        ExtractedFactEvidence.model_validate(common)
    assert ExtractedFactEvidence.model_validate({**common, "value": "CONSIGNEE"}).value == "CONSIGNEE"


def test_single_agent_uses_real_tool_loop_and_preserves_deterministic_decision(service):
    documents = _extracted_documents(service.settings)
    evidence = [
        {
            "fact_path": "documents.booking_request.cargo.un_number",
            "value": "UN1263",
            "document_type": "BOOKING_REQUEST",
            "page": 1,
            "evidence_text": "UN Number UN1263",
            "confidence": 0.98,
        },
        {
            "fact_path": "documents.dgd.declaration.un_number",
            "value": "UN1866",
            "document_type": "PRELIMINARY_DGD",
            "page": 1,
            "evidence_text": "UN Number UN1866",
            "confidence": 0.97,
        },
    ]
    model = ScriptedModel(responses=[
        _turn(tool_call={"id": "call-1", "name": "submit_extracted_facts",
                         "args": {"documents": documents}, "type": "tool_call"},
              input_tokens=100, output_tokens=40),
        _turn(tool_call={"id": "call-2", "name": "run_precheck_rules", "args": {}, "type": "tool_call"},
              input_tokens=80, output_tokens=10),
        _turn(tool_call={"id": "call-3", "name": "submit_decision_evidence",
                         "args": {"evidence": evidence}, "type": "tool_call"},
              input_tokens=70, output_tokens=10),
        _turn(tool_call={"id": "call-4", "name": "lookup_policy_evidence",
                         "args": {"rule_ids": ["CON-BOOKING-DGD-UN"]}, "type": "tool_call"},
              input_tokens=60, output_tokens=10),
        _turn("UN numbers conflict; route to DG Desk.", input_tokens=50, output_tokens=20),
    ])

    graph = build_single_agent_graph(service.settings, model)
    output = graph.invoke({"document_pack_id": "DP-003"})
    result = output["result"]

    assert result["technical_status"] == "COMPLETED"
    assert result["final_status"] == "MANUAL_REVIEW"
    assert result["reason_codes"] == ["CON-BOOKING-DGD-UN"]
    assert result["metrics"] == {"duration_ms": result["metrics"]["duration_ms"], "model_call_count": 5, "input_tokens": 360, "output_tokens": 90}
    assert len(model.requests) == 5
    assert set(model.bound_tool_names) == {
        "submit_extracted_facts", "run_precheck_rules", "submit_decision_evidence",
        "lookup_policy_evidence", "request_human_confirmation",
    }
    assert any(isinstance(message, ToolMessage) for message in model.requests[1])
    un_evidence = next(item for item in result["evidence"] if item["fact_path"] == "documents.booking_request.cargo.un_number")
    assert un_evidence["page"] == 1
    assert un_evidence["evidence_text"] == "UN Number UN1263"


def test_single_agent_model_failure_never_becomes_business_pass(service):
    model = ScriptedModel(responses=[RuntimeError("provider unavailable")])
    graph = build_single_agent_graph(service.settings, model)

    result = graph.invoke({"document_pack_id": "DP-001"})["result"]

    assert result["technical_status"] == "FAILED"
    assert result["final_status"] is None
    assert result["technical_error"]["code"] == "AGENT_RUNTIME_FAILED"
    schema = load_json(service.settings.assets_dir / "PRECHECK_RESULT_SCHEMA.json")
    assert list(Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).iter_errors(result)) == []


def test_precheck_agent_has_no_direct_node_initialization_guard(service):
    model = ScriptedModel(responses=[_turn("done")])
    graph = build_single_agent_graph(service.settings, model)
    agent_node = graph.get_graph().nodes["precheck_agent"].data

    update = agent_node.invoke({"messages": [], "document_pack_id": "DP-003"})

    assert update["messages"][0].content == "done"
    assert model.requests == [[]]


def test_single_agent_accepts_unverified_incomplete_evidence(service):
    documents = _extracted_documents(service.settings)
    bad_evidence = {
        "evidence": [{
            "fact_path": "documents.booking_request.cargo.un_number",
            "value": "UN1263",
            "document_type": "BOOKING_REQUEST",
            "page": 1,
            "evidence_text": "THIS TEXT DOES NOT EXIST",
            "confidence": 0.99,
        }],
    }
    model = ScriptedModel(responses=[
        _turn(tool_call={"id": "call-1", "name": "submit_extracted_facts",
                         "args": {"documents": documents}, "type": "tool_call"}),
        _turn(tool_call={"id": "call-2", "name": "run_precheck_rules", "args": {}, "type": "tool_call"}),
        _turn(tool_call={"id": "call-3", "name": "submit_decision_evidence",
                         "args": bad_evidence, "type": "tool_call"}),
        _turn(tool_call={"id": "call-4", "name": "lookup_policy_evidence",
                         "args": {"rule_ids": ["CON-BOOKING-DGD-UN"]}, "type": "tool_call"}),
        _turn("done"),
    ])

    result = build_single_agent_graph(service.settings, model).invoke({"document_pack_id": "DP-003"})["result"]

    assert result["technical_status"] == "COMPLETED"
    asserted = next(
        item for item in result["evidence"]
        if item["fact_path"] == "documents.booking_request.cargo.un_number"
    )
    assert asserted["evidence_text"] == "THIS TEXT DOES NOT EXIST"
    assert len(model.requests) == 5


def test_single_agent_does_not_repair_invalid_provider_tool_call(service):
    malformed = AIMessage(
        content="",
        additional_kwargs={"tool_calls": [{
            "id": "bad-call", "type": "function",
            "function": {"name": "submit_extracted_facts", "arguments": "{bad json"},
        }]},
        invalid_tool_calls=[{
            "id": "bad-call", "name": "submit_extracted_facts", "args": "{bad json",
            "error": "invalid JSON", "type": "invalid_tool_call",
        }],
        usage_metadata={"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
    )
    model = ScriptedModel(responses=[malformed])

    result = build_single_agent_graph(service.settings, model).invoke({"document_pack_id": "DP-003"})["result"]

    assert result["technical_status"] == "FAILED"
    assert "Agent stopped before producing serializable state" in result["technical_error"]["message"]
    assert result["metrics"]["model_call_count"] == 1
    assert len(model.requests) == 1


def test_fact_and_decision_evidence_tools_have_separate_unbounded_schemas():
    fact_properties = submit_extracted_facts.tool_call_schema.model_json_schema()["properties"]
    evidence_schema = submit_decision_evidence.tool_call_schema.model_json_schema()["properties"]["evidence"]

    assert set(fact_properties) == {"documents"}
    assert "maxItems" not in evidence_schema


def test_fact_submission_preserves_rule_input_confidence_metadata(service):
    documents = _extracted_documents(service.settings)
    documents["dgd"]["metadata"]["extraction_confidence"] = 0.72
    documents["dgd"]["metadata"]["field_confidences"] = {"un_number": 0.72}
    model = ScriptedModel(responses=[
        _turn(tool_call={"id": "call-1", "name": "submit_extracted_facts",
                         "args": {"documents": documents}, "type": "tool_call"}),
        _turn(tool_call={"id": "call-2", "name": "run_precheck_rules", "args": {}, "type": "tool_call"}),
        RuntimeError("stop after inspecting rule inputs"),
    ])

    graph = build_single_agent_graph(service.settings, model)
    result = graph.invoke({"document_pack_id": "DP-003"})["result"]

    assert result["technical_status"] == "FAILED"
    rule_result = next(
        message for message in model.requests[2] if isinstance(message, ToolMessage)
        and message.name == "run_precheck_rules"
    )
    assert "DOC-KEY-FIELD-LOW-CONFIDENCE" in rule_result.content


def test_single_agent_studio_contract_hides_internal_state(service):
    graph = build_single_agent_graph(service.settings, ScriptedModel(responses=[]))
    input_schema = graph.get_input_jsonschema()
    output_schema = graph.get_output_jsonschema()

    assert set(input_schema["properties"]) == {
        "document_pack_id", "stage_id", "source_documents", "submitted_at",
        "case_id", "step_id", "previous_run_id", "trace_id",
    }
    assert output_schema["properties"]["result"] == {"$ref": "#/$defs/PrecheckResult"}
