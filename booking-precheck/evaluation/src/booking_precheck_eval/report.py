from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runner import RunRecord
from .scoring import percentile


def _critical_false_clear(score: dict[str, Any] | None) -> bool:
    if not score:
        return False
    if score.get("critical_false_clear"):
        return True
    return any(item.get("critical_false_clear", False) for item in score.get("steps", []))


def _check_coverage(score: dict[str, Any] | None) -> float:
    if not score:
        return 0.0
    if "check_coverage" in score:
        return float(score["check_coverage"])
    steps = score.get("steps", [])
    values = [float(item.get("check_coverage", 0.0)) for item in steps]
    return sum(values) / len(values) if values else 0.0


def summarize(records: list[RunRecord]) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[RunRecord]] = defaultdict(list)
    for record in records:
        groups[(record.system, record.suite)].append(record)
    summaries = []
    for (system, suite), items in sorted(groups.items()):
        elapsed = [item.elapsed_ms for item in items]
        successful_invocations = [item for item in items if item.invocation_error is None]
        passed = [item for item in successful_invocations if item.score and item.score.get("passed")]
        field_scores = [
            item.score["document_facts"]["accuracy"]
            for item in successful_invocations
            if item.score and item.score.get("document_facts", {}).get("available")
        ]
        summaries.append({
            "system": system,
            "suite": suite,
            "runs": len(items),
            "invocation_success_rate": len(successful_invocations) / len(items) if items else 0.0,
            "functional_pass_rate": len(passed) / len(items) if items else 0.0,
            "functional_check_coverage": (
                round(sum(_check_coverage(item.score) for item in successful_invocations) / len(successful_invocations), 6)
                if successful_invocations else 0.0
            ),
            "critical_false_clear_count": sum(_critical_false_clear(item.score) for item in items),
            "average_latency_ms": round(sum(elapsed) / len(elapsed), 2) if elapsed else None,
            "p95_latency_ms": percentile(elapsed, 0.95),
            "model_call_count": sum(item.result_metrics["model_call_count"] for item in items),
            "input_tokens": sum(item.result_metrics["input_tokens"] for item in items),
            "output_tokens": sum(item.result_metrics["output_tokens"] for item in items),
            "field_accuracy": round(sum(field_scores) / len(field_scores), 6) if field_scores else None,
            "field_accuracy_coverage": len(field_scores) / len(items) if items else 0.0,
        })
    return {
        "schema_version": "0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_runs": len(records),
        "summaries": summaries,
    }


def write_reports(records: list[RunRecord], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "runs.json"
    summary_path = output_dir / "summary.json"
    csv_path = output_dir / "summary.csv"
    markdown_path = output_dir / "report.md"
    summary = summarize(records)
    raw_path.write_text(json.dumps([item.as_dict() for item in records], ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = [
        "system", "suite", "runs", "invocation_success_rate", "functional_pass_rate", "functional_check_coverage",
        "critical_false_clear_count", "average_latency_ms", "p95_latency_ms",
        "model_call_count", "input_tokens", "output_tokens", "field_accuracy",
        "field_accuracy_coverage",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary["summaries"])

    lines = [
        "# Booking Precheck Evaluation Report",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "| System | Suite | Runs | Invocation | Functional pass | Check coverage | Critical false clear | Avg ms | P95 ms | Calls | Tokens in/out | Field accuracy |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summary["summaries"]:
        field_accuracy = "N/A" if item["field_accuracy"] is None else f"{item['field_accuracy']:.1%}"
        lines.append(
            f"| {item['system']} | {item['suite']} | {item['runs']} "
            f"| {item['invocation_success_rate']:.1%} | {item['functional_pass_rate']:.1%} "
            f"| {item['functional_check_coverage']:.1%} | {item['critical_false_clear_count']} | {item['average_latency_ms']} "
            f"| {item['p95_latency_ms']} | {item['model_call_count']} "
            f"| {item['input_tokens']}/{item['output_tokens']} | {field_accuracy} |"
        )
    lines.extend([
        "",
        "`Field accuracy = N/A` means the system returned only `PrecheckResult`. To enable full extraction scoring, return an evaluation envelope containing both `result` and `facts`.",
        "",
    ])
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return {"runs": raw_path, "summary": summary_path, "csv": csv_path, "markdown": markdown_path}
