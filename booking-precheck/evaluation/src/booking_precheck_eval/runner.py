from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .adapters import CliAdapter, Invocation
from .catalog import EvaluationCase, discover_cases
from .config import HarnessConfig
from .scoring import score_document_facts, score_result


@dataclass(frozen=True)
class RunRecord:
    system: str
    suite: str
    case_id: str
    stage_id: str | None
    attempt: int
    elapsed_ms: int
    invocation_error: str | None
    score: dict[str, Any] | None
    result_metrics: dict[str, int]
    result: Any | None
    facts_observed: bool
    stderr: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "suite": self.suite,
            "case_id": self.case_id,
            "stage_id": self.stage_id,
            "attempt": self.attempt,
            "elapsed_ms": self.elapsed_ms,
            "invocation_error": self.invocation_error,
            "score": self.score,
            "result_metrics": self.result_metrics,
            "result": self.result,
            "facts_observed": self.facts_observed,
            "stderr": self.stderr,
        }


def _unwrap(payload: Any) -> tuple[Any, dict[str, Any] | None]:
    if isinstance(payload, dict) and "result" in payload:
        facts = payload.get("facts") or payload.get("extracted_facts")
        return payload["result"], facts
    return payload, None


def _metrics(results: list[dict[str, Any]]) -> dict[str, int]:
    metrics = [item.get("metrics", {}) for item in results if isinstance(item, dict)]
    return {
        "duration_ms": sum(int(item.get("duration_ms", 0)) for item in metrics),
        "model_call_count": sum(int(item.get("model_call_count", 0)) for item in metrics),
        "input_tokens": sum(int(item.get("input_tokens", 0)) for item in metrics),
        "output_tokens": sum(int(item.get("output_tokens", 0)) for item in metrics),
    }


def _score_single(result: Any, case: EvaluationCase, facts: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"passed": False, "error": "expected one JSON result object"}
    score = score_result(
        result, case.expected,
        require_document_evidence=case.suite == "document",
        facts=facts,
    )
    if case.suite == "document":
        score["document_facts"] = score_document_facts(facts, case.ground_truth)
    return score


def _score_business(result: Any, case: EvaluationCase) -> dict[str, Any]:
    expected_steps = case.expected["step_expectations"]
    if not isinstance(result, list):
        return {"passed": False, "error": "expected a JSON array of business step results", "steps": []}
    step_scores = []
    for index, expected in enumerate(expected_steps):
        if index >= len(result) or not isinstance(result[index], dict):
            step_scores.append({"passed": False, "error": f"missing result for {expected['step_id']}"})
            continue
        step_score = score_result(result[index], expected, require_document_evidence=False)
        step_score["step_id"] = expected["step_id"]
        if index == 0:
            step_score["checks"]["previous_run_chain"] = result[index].get("previous_run_id") is None
        else:
            step_score["checks"]["previous_run_chain"] = (
                result[index].get("previous_run_id") == result[index - 1].get("run_id")
            )
        step_score["passed"] = step_score["passed"] and step_score["checks"]["previous_run_chain"]
        step_scores.append(step_score)
    return {
        "passed": len(result) == len(expected_steps) and all(item.get("passed", False) for item in step_scores),
        "step_count_match": len(result) == len(expected_steps),
        "steps": step_scores,
        "critical_false_clear": any(item.get("critical_false_clear", False) for item in step_scores),
    }


def _record(system_name: str, case: EvaluationCase, attempt: int, invocation: Invocation) -> RunRecord:
    if invocation.error:
        return RunRecord(
            system_name, case.suite, case.case_id, case.stage_id, attempt, invocation.elapsed_ms,
            invocation.error, None, _metrics([]), None, False, invocation.stderr,
        )
    result, facts = _unwrap(invocation.payload)
    score = _score_business(result, case) if case.suite == "business" else _score_single(result, case, facts)
    result_list = result if isinstance(result, list) else [result]
    return RunRecord(
        system_name, case.suite, case.case_id, case.stage_id, attempt, invocation.elapsed_ms,
        None, score, _metrics(result_list), result, facts is not None, invocation.stderr,
    )


def run_evaluation(
    config: HarnessConfig,
    *,
    systems: Iterable[str] | None = None,
    suites: Iterable[str] | None = None,
    case_ids: set[str] | None = None,
    repeat: int | None = None,
) -> list[RunRecord]:
    selected_systems = list(systems or config.systems)
    selected_suites = list(suites or ("rule", "document", "business"))
    attempts = repeat or config.repeat
    records: list[RunRecord] = []
    for system_name in selected_systems:
        if system_name not in config.systems:
            raise ValueError(f"unknown system: {system_name}")
        system = config.systems[system_name]
        adapter = CliAdapter(system, config.assets_dir)
        for suite in selected_suites:
            if suite not in system.suites:
                continue
            cases = discover_cases(config.assets_dir, suite)
            if case_ids:
                cases = [case for case in cases if case.case_id in case_ids or case.key in case_ids]
            for case in cases:
                for attempt in range(1, attempts + 1):
                    records.append(_record(system_name, case, attempt, adapter.invoke(case)))
    return records
