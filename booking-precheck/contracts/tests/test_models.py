import pytest
from pydantic import ValidationError

from booking_precheck_contracts import EvaluationRequest, EvaluationResponse


def test_request_rejects_non_document_pack_cases():
    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate({
            "request_id": "x",
            "case": {"pack_id": "TC-001", "stage_id": "S1"},
            "policy": {"snapshot_id": "SNAPSHOT"},
            "documents": [{
                "document_id": "DOC-1", "document_type": "BOOKING_REQUEST",
                "document_version": 1, "path": "/tmp/doc.pdf",
            }],
        })


def test_completed_response_requires_result_and_facts():
    with pytest.raises(ValidationError):
        EvaluationResponse.model_validate({
            "request_id": "x", "technical_status": "COMPLETED", "result": {},
            "telemetry": {"duration_ms": 1, "model_call_count": 0, "input_tokens": 0, "output_tokens": 0},
        })
