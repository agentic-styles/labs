from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from booking_precheck_contracts import EvaluationResponse

from .document_dataset import dataset_item_id, document_dataset_items, make_request
from .protocol import JsonlAgentClient
from .scoring import percentile, score_document_facts, score_result


DEFAULT_DATASET_NAME = "booking-precheck/day2-document-packs-v1"


def load_env_file(path: str | Path | None) -> None:
    if not path:
        return
    env_path = Path(path)
    if not env_path.is_file():
        return
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    for key, value in values.items():
        os.environ.setdefault(key, value)


def get_langfuse_client():
    try:
        from langfuse import get_client
    except ImportError as error:
        raise RuntimeError("Install the Langfuse extra: pip install -e '.[langfuse]'") from error
    return get_client()


def require_authenticated_client(client: Any) -> None:
    if not client.auth_check():
        raise RuntimeError(
            "Langfuse authentication failed. Configure LANGFUSE_PUBLIC_KEY, "
            "LANGFUSE_SECRET_KEY and LANGFUSE_BASE_URL."
        )


def sync_dataset(client: Any, assets_dir: Path, dataset_name: str = DEFAULT_DATASET_NAME) -> int:
    try:
        client.get_dataset(dataset_name)
    except Exception:
        client.create_dataset(
            name=dataset_name,
            description="Nine synthetic Booking Precheck document-pack stages for Day 2 architecture evaluation.",
            metadata={"protocol_version": "booking-precheck-eval/v1", "training_only": True},
        )
    items = document_dataset_items(assets_dir)
    for item in items:
        client.create_dataset_item(
            dataset_name=dataset_name,
            id=dataset_item_id(dataset_name, item.case.key),
            input=item.input,
            expected_output=item.expected_output,
            metadata=item.metadata,
        )
    return len(items)


def booking_precheck_evaluator(
    *, input: Any, output: Any, expected_output: Any, metadata: Any = None, **kwargs: Any,
) -> list[dict[str, Any]]:
    response = EvaluationResponse.model_validate(output)
    evaluations: list[dict[str, Any]] = [{
        "name": "technical_success",
        "value": response.technical_status == "COMPLETED",
        "comment": response.error.message if response.error else None,
    }]
    if response.technical_status != "COMPLETED" or not response.result or not response.facts:
        evaluations.extend([
            {"name": "status_correct", "value": False},
            {"name": "no_critical_false_clear", "value": not (
                expected_output["expected"].get("expected_status") == "PRECHECK_BLOCKED"
                and response.result
                and response.result.get("final_status") == "PRECHECK_PASS"
            )},
        ])
        return evaluations

    result_score = score_result(
        response.result,
        expected_output["expected"],
        require_document_evidence=True,
        facts=response.facts,
    )
    fact_score = score_document_facts(response.facts, expected_output["ground_truth"])
    evaluations.extend([
        {"name": "status_correct", "value": result_score["checks"]["status"]},
        {"name": "rule_f1", "value": result_score["rule_metrics"]["f1"]},
        {"name": "field_accuracy", "value": fact_score["accuracy"]},
        {"name": "evidence_integrity", "value": result_score["evidence_integrity"]["valid"]},
        {"name": "functional_pass", "value": result_score["passed"] and fact_score["accuracy"] == 1.0},
        {"name": "no_critical_false_clear", "value": not result_score["critical_false_clear"]},
        {"name": "model_call_count", "value": response.telemetry.model_call_count},
        {"name": "input_tokens", "value": response.telemetry.input_tokens},
        {"name": "output_tokens", "value": response.telemetry.output_tokens},
        {"name": "agent_duration_ms", "value": response.telemetry.duration_ms},
    ])
    return evaluations


def p95_latency_evaluator(*, item_results: list[Any], **kwargs: Any) -> dict[str, Any]:
    durations = []
    for item in item_results:
        try:
            durations.append(EvaluationResponse.model_validate(item.output).telemetry.duration_ms)
        except Exception:
            continue
    return {
        "name": "p95_agent_duration_ms",
        "value": percentile(durations, 0.95) or 0,
        "comment": f"Nearest-rank P95 over {len(durations)} completed experiment outputs",
    }


def run_langfuse_experiment(
    client: Any,
    *,
    assets_dir: Path,
    manifest_path: Path,
    dataset_name: str,
    run_name: str,
) -> Any:
    dataset = client.get_dataset(dataset_name)
    with JsonlAgentClient(manifest_path) as agent:
        def task(*, item: Any, **kwargs: Any) -> dict[str, Any]:
            pack_id = item.input["pack_id"]
            stage_id = item.input["stage_id"]
            request = make_request(
                assets_dir, pack_id, stage_id,
                request_id=f"langfuse-{run_name}-{pack_id}-{stage_id}",
            )
            response = agent.invoke(request)
            langfuse_trace_id = client.get_current_trace_id()
            if langfuse_trace_id:
                response = response.model_copy(update={
                    "telemetry": response.telemetry.model_copy(update={"trace_id": langfuse_trace_id}),
                })
            return response.model_dump(mode="json")

        result = dataset.run_experiment(
            name=run_name,
            description="Booking Precheck Single-Agent evaluation over nine document-pack stages.",
            task=task,
            evaluators=[booking_precheck_evaluator],
            run_evaluators=[p95_latency_evaluator],
            max_concurrency=1,
            metadata={
                "system": "booking-precheck-single-agent",
                "protocol_version": "booking-precheck-eval/v1",
            },
        )
    client.flush()
    return result
