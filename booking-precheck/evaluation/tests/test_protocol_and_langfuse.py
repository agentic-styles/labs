import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from booking_precheck_eval.document_dataset import document_dataset_items, make_request
from booking_precheck_eval.langfuse_eval import (
    booking_precheck_evaluator,
    load_env_file,
    p95_latency_evaluator,
    sync_dataset,
)
from booking_precheck_eval.protocol import JsonlAgentClient


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT.parents[1] / "assets"


def test_env_file_uses_last_duplicate_without_overwriting_process_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LANGFUSE_PUBLIC_KEY=\nLANGFUSE_PUBLIC_KEY=pk-final\n", encoding="utf-8")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)

    load_env_file(env_file)

    assert os.environ["LANGFUSE_PUBLIC_KEY"] == "pk-final"


def test_document_dataset_contains_only_nine_public_inputs():
    items = document_dataset_items(ASSETS)

    assert len(items) == 9
    assert set(items[0].input) == {"pack_id", "stage_id"}
    assert "expected" not in items[0].input
    assert "ground_truth" not in items[0].input
    assert "ground_truth" in items[0].expected_output


def test_request_contains_documents_but_no_ground_truth():
    request = make_request(ASSETS, "DP-003", "S1", request_id="request-1")
    payload = request.model_dump(mode="json")

    assert request.request_id == "request-1"
    assert len(request.documents) == 3
    assert all(Path(document.path).is_file() for document in request.documents)
    assert "ground_truth" not in json.dumps(payload).lower()
    assert "expected" not in json.dumps(payload).lower()


def test_jsonl_protocol_client_validates_response(tmp_path):
    manifest = tmp_path / "agent.json"
    manifest.write_text(json.dumps({
        "protocol_version": "booking-precheck-eval/v1",
        "transport": "stdio-jsonl",
        "command": [sys.executable, str(ROOT / "fixtures" / "fake_jsonl_agent.py")],
        "cwd": str(ROOT),
        "case_timeout_seconds": 5,
        "capabilities": {"returns_facts": True},
    }), encoding="utf-8")
    first_request = make_request(ASSETS, "DP-001", "S1", request_id="protocol-test-1")
    second_request = make_request(ASSETS, "DP-001", "S1", request_id="protocol-test-2")

    with JsonlAgentClient(manifest) as client:
        first_response = client.invoke(first_request)
        second_response = client.invoke(second_request)

    assert first_response.request_id == "protocol-test-1"
    assert second_response.request_id == "protocol-test-2"
    assert first_response.technical_status == "COMPLETED"
    assert second_response.telemetry.trace_id == "trace-1"


def test_langfuse_evaluator_scores_protocol_response():
    item = next(item for item in document_dataset_items(ASSETS) if item.case.key == "DP-001:S1")
    facts = {
        document_type: {}
        for document_type in ("booking_request", "dgd", "sds")
    }
    output = {
        "protocol_version": "booking-precheck-eval/v1",
        "request_id": "x",
        "technical_status": "COMPLETED",
        "result": {
            "technical_status": "COMPLETED",
            "final_status": item.expected_output["expected"]["expected_status"],
            "reason_codes": [], "routing_queues": [], "required_facts": [],
            "matched_rules": [], "evidence": [],
        },
        "facts": {"documents": facts},
        "telemetry": {
            "duration_ms": 10, "model_call_count": 1,
            "input_tokens": 5, "output_tokens": 2,
        },
    }

    evaluations = booking_precheck_evaluator(
        input=item.input, output=output, expected_output=item.expected_output,
    )

    scores = {evaluation["name"]: evaluation["value"] for evaluation in evaluations}
    assert scores["technical_success"] is True
    assert scores["status_correct"] is True
    assert scores["field_accuracy"] < 1.0
    assert scores["functional_pass"] is False


def test_p95_run_evaluator_reads_protocol_telemetry():
    items = [
        SimpleNamespace(output={
            "protocol_version": "booking-precheck-eval/v1", "request_id": str(value),
            "technical_status": "FAILED", "result": None, "facts": None,
            "telemetry": {"duration_ms": value, "model_call_count": 0, "input_tokens": 0, "output_tokens": 0},
            "error": {"code": "X", "stage": "test", "retryable": False, "message": "failed"},
        })
        for value in (10, 20, 30, 40)
    ]

    assert p95_latency_evaluator(item_results=items)["value"] == 40


class FakeLangfuse:
    def __init__(self):
        self.datasets = []
        self.items = []

    def get_dataset(self, name):
        raise RuntimeError("not found")

    def create_dataset(self, **kwargs):
        self.datasets.append(kwargs)

    def create_dataset_item(self, **kwargs):
        self.items.append(kwargs)


def test_sync_dataset_upserts_nine_stable_items():
    client = FakeLangfuse()

    count = sync_dataset(client, ASSETS, "course/test")

    assert count == 9
    assert len(client.datasets) == 1
    assert len(client.items) == 9
    assert len({item["id"] for item in client.items}) == 9
