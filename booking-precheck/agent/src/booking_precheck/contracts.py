"""Typed runtime contracts exposed to LangGraph and Studio."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

TechnicalStatus = Literal["COMPLETED", "FAILED"]
FinalStatus = Literal["PRECHECK_PASS", "REQUIRE_INFORMATION", "MANUAL_REVIEW", "PRECHECK_BLOCKED"]
FindingStatus = Literal["REQUIRE_INFORMATION", "MANUAL_REVIEW", "PRECHECK_BLOCKED"]
RoutingQueue = Literal["DOCUMENT_DESK", "DG_DESK", "ROUTE_DESK", "POLICY_OWNER"]
DocumentType = Literal["BOOKING_REQUEST", "PRELIMINARY_DGD", "SDS_EXTRACT"]
EvidenceType = Literal["DOCUMENT_FIELD", "ASSERTED_ABSENCE", "POLICY_RULE", "HUMAN_CONFIRMATION"]


class MatchedRule(TypedDict):
    rule_id: str
    reason_code: str
    rule_result_status: FindingStatus
    message: str
    routing_queue: RoutingQueue | None
    pause_automation: bool
    fact_evidence_ids: list[str]
    policy_evidence_id: str


class Evidence(TypedDict):
    evidence_id: str
    evidence_type: EvidenceType
    fact_path: str | None
    value: Any
    document_id: str | None
    document_version: int | None
    document_type: DocumentType | None
    policy_document_id: str | None
    rule_id: str | None
    page: int | None
    section: str | None
    evidence_text: str
    confidence: float | None


class AuditSourceDocument(TypedDict):
    document_id: str
    document_version: int | None
    document_type: DocumentType | None


class AuditContext(TypedDict):
    fact_snapshot_ref: str
    fact_snapshot_sha256: str
    observed_fact_count: int
    source_documents: list[AuditSourceDocument]


class ResultMetrics(TypedDict):
    duration_ms: int
    model_call_count: int
    input_tokens: int
    output_tokens: int


class TechnicalError(TypedDict):
    code: str
    message: str
    failed_stage: str
    retryable: bool


class PrecheckResult(TypedDict):
    schema_version: Literal["0.1"]
    run_id: str
    trace_id: str
    technical_status: TechnicalStatus
    case_id: str | None
    step_id: str | None
    previous_run_id: str | None
    booking_reference: str
    policy_snapshot_id: str
    started_at: str
    completed_at: str
    final_status: FinalStatus | None
    reason_codes: list[str]
    routing_queues: list[RoutingQueue]
    required_facts: list[str]
    pause_automation: bool
    next_action: str | None
    matched_rules: list[MatchedRule]
    evidence: list[Evidence]
    audit_context: AuditContext
    metrics: ResultMetrics
    technical_error: TechnicalError | None

