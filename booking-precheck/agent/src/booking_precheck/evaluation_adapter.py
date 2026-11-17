from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import pdfplumber
from booking_precheck_contracts import EvaluationError, EvaluationRequest, EvaluationResponse, EvaluationTelemetry

from .agent_graph import build_single_agent_graph
from .assets import load_json
from .config import Settings


def _source_documents(request: EvaluationRequest) -> list[dict[str, Any]]:
    documents = []
    for reference in request.documents:
        path = Path(reference.path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Input document does not exist: {path}")
        with pdfplumber.open(path) as pdf:
            pages = [
                {"page": index, "text": page.extract_text() or ""}
                for index, page in enumerate(pdf.pages, start=1)
            ]
        documents.append({
            "document_id": reference.document_id,
            "document_type": reference.document_type,
            "document_version": reference.document_version,
            "file_name": path.name,
            "pages": pages,
        })
    return documents


class SingleAgentEvaluationAdapter:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self.graph = build_single_agent_graph(self.settings)

    def run(self, request: EvaluationRequest) -> EvaluationResponse:
        started = time.perf_counter()
        try:
            snapshot = load_json(self.settings.assets_dir / "policy_snapshot.json")
            if request.policy.snapshot_id != snapshot["snapshot_id"]:
                raise ValueError(
                    f"Unauthorized policy snapshot: {request.policy.snapshot_id}; "
                    f"expected {snapshot['snapshot_id']}"
                )
            state = self.graph.invoke({
                "document_pack_id": request.case.pack_id,
                "stage_id": request.case.stage_id,
                "source_documents": _source_documents(request),
                "trace_id": request.request_id,
            })
            result = state["result"]
            metrics = result.get("metrics", {})
            if result.get("technical_status") != "COMPLETED" or not state.get("facts"):
                technical = result.get("technical_error") or {}
                return EvaluationResponse(
                    request_id=request.request_id,
                    technical_status="FAILED",
                    result=result,
                    facts=state.get("facts"),
                    telemetry=EvaluationTelemetry(
                        duration_ms=int(metrics.get("duration_ms", (time.perf_counter() - started) * 1000)),
                        model_call_count=int(metrics.get("model_call_count", 0)),
                        input_tokens=int(metrics.get("input_tokens", 0)),
                        output_tokens=int(metrics.get("output_tokens", 0)),
                        trace_id=result.get("trace_id"),
                    ),
                    error=EvaluationError(
                        code=technical.get("code", "AGENT_EVALUATION_FAILED"),
                        stage=technical.get("failed_stage", "single_agent"),
                        retryable=bool(technical.get("retryable", False)),
                        message=technical.get("message", "Single-Agent evaluation did not complete"),
                    ),
                )
            return EvaluationResponse(
                request_id=request.request_id,
                technical_status="COMPLETED",
                result=result,
                facts=state["facts"],
                telemetry=EvaluationTelemetry(
                    duration_ms=int(metrics.get("duration_ms", (time.perf_counter() - started) * 1000)),
                    model_call_count=int(metrics.get("model_call_count", 0)),
                    input_tokens=int(metrics.get("input_tokens", 0)),
                    output_tokens=int(metrics.get("output_tokens", 0)),
                    trace_id=result.get("trace_id"),
                ),
            )
        except Exception as error:
            return EvaluationResponse(
                request_id=request.request_id,
                technical_status="FAILED",
                telemetry=EvaluationTelemetry(
                    duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
                    model_call_count=0,
                    input_tokens=0,
                    output_tokens=0,
                ),
                error=EvaluationError(
                    code="ADAPTER_RUNTIME_FAILED",
                    stage="evaluation_adapter",
                    retryable=False,
                    message=f"{type(error).__name__}: {error}",
                ),
            )


def serve() -> None:
    adapter: SingleAgentEvaluationAdapter | None = None
    for line in sys.stdin:
        if not line.strip():
            continue
        request_id = "unknown"
        try:
            raw = json.loads(line)
            request_id = str(raw.get("request_id", request_id)) if isinstance(raw, dict) else request_id
            request = EvaluationRequest.model_validate(raw)
            adapter = adapter or SingleAgentEvaluationAdapter()
            response = adapter.run(request)
        except Exception as error:
            response = EvaluationResponse(
                request_id=request_id,
                technical_status="FAILED",
                telemetry=EvaluationTelemetry(
                    duration_ms=0, model_call_count=0, input_tokens=0, output_tokens=0,
                ),
                error=EvaluationError(
                    code="INVALID_EVALUATION_REQUEST",
                    stage="protocol",
                    retryable=False,
                    message=f"{type(error).__name__}: {error}",
                ),
            )
        sys.stdout.write(response.model_dump_json() + "\n")
        sys.stdout.flush()


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
