from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PROTOCOL = Literal["booking-precheck-eval/v1"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseReference(ContractModel):
    pack_id: str = Field(pattern=r"^DP-[0-9]{3}$")
    stage_id: str = Field(pattern=r"^S[0-9]+$")


class PolicyReference(ContractModel):
    snapshot_id: str = Field(min_length=1)


class DocumentReference(ContractModel):
    document_id: str = Field(min_length=1)
    document_type: Literal["BOOKING_REQUEST", "PRELIMINARY_DGD", "SDS_EXTRACT"]
    document_version: int = Field(ge=1)
    path: str = Field(min_length=1)


class EvaluationRequest(ContractModel):
    protocol_version: PROTOCOL = "booking-precheck-eval/v1"
    request_id: str = Field(min_length=1)
    case: CaseReference
    policy: PolicyReference
    documents: list[DocumentReference] = Field(min_length=1)


class EvaluationTelemetry(ContractModel):
    duration_ms: int = Field(ge=0)
    model_call_count: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    trace_id: str | None = None


class EvaluationError(ContractModel):
    code: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    retryable: bool
    message: str = Field(min_length=1)


class EvaluationResponse(ContractModel):
    protocol_version: PROTOCOL = "booking-precheck-eval/v1"
    request_id: str = Field(min_length=1)
    technical_status: Literal["COMPLETED", "FAILED"]
    result: dict[str, Any] | None = None
    facts: dict[str, Any] | None = None
    telemetry: EvaluationTelemetry
    error: EvaluationError | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "EvaluationResponse":
        if self.technical_status == "COMPLETED" and (self.result is None or self.facts is None):
            raise ValueError("COMPLETED responses require both result and facts")
        if self.technical_status == "FAILED" and self.error is None:
            raise ValueError("FAILED responses require error")
        return self


class AgentManifest(ContractModel):
    protocol_version: PROTOCOL = "booking-precheck-eval/v1"
    transport: Literal["stdio-jsonl"] = "stdio-jsonl"
    command: list[str] = Field(min_length=1)
    cwd: str = "."
    startup_timeout_seconds: float = Field(default=30, gt=0)
    case_timeout_seconds: float = Field(default=180, gt=0)
    env_file: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    capabilities: dict[str, bool] = Field(default_factory=dict)
