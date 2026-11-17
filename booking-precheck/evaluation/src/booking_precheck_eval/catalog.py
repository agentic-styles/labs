from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvaluationCase:
    suite: str
    case_id: str
    stage_id: str | None
    expected: dict[str, Any]
    ground_truth: dict[str, Any] | None = None

    @property
    def key(self) -> str:
        return f"{self.case_id}:{self.stage_id}" if self.stage_id else self.case_id


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _business_step(assets_dir: Path, case_id: str, stage_id: str) -> dict[str, Any] | None:
    path = assets_dir / "business-cases" / case_id / "expected.json"
    if not path.is_file():
        return None
    expected = _load(path)
    return next((item for item in expected["step_expectations"] if item["step_id"] == stage_id), None)


def _document_expected(assets_dir: Path, manifest: dict[str, Any], stage: dict[str, Any]) -> dict[str, Any]:
    case_ref = manifest["case_ref"]
    stage_id = stage["stage_id"]
    if case_ref.startswith("BA-"):
        business = _business_step(assets_dir, case_ref, stage.get("business_step_id", stage_id))
        if business:
            return business
    rule_path = assets_dir / "cases" / case_ref / "expected.json"
    if rule_path.is_file():
        return _load(rule_path)
    return {
        "expected_status": stage["expected_status"],
        "expected_reason_codes": [],
        "expected_rule_ids": [],
        "expected_routing_queues": [],
        "expected_required_facts": [],
        "expected_evidence": [],
    }


def discover_cases(assets_dir: Path, suite: str) -> list[EvaluationCase]:
    if suite == "rule":
        return [
            EvaluationCase("rule", path.parent.name, None, _load(path))
            for path in sorted((assets_dir / "cases").glob("TC-*/expected.json"))
        ]
    if suite == "business":
        return [
            EvaluationCase("business", path.parent.name, None, _load(path))
            for path in sorted((assets_dir / "business-cases").glob("BA-*/expected.json"))
        ]
    if suite == "document":
        cases: list[EvaluationCase] = []
        for manifest_path in sorted((assets_dir / "document-packs").glob("DP-*/manifest.json")):
            manifest = _load(manifest_path)
            truth = _load(manifest_path.parent / manifest.get("ground_truth_path", "ground-truth.json"))
            for stage in manifest["stages"]:
                stage_id = stage["stage_id"]
                filtered_truth = {
                    **truth,
                    "documents": [
                        item for item in truth["documents"]
                        if item.get("stage_id", "S1") == stage_id
                    ],
                }
                cases.append(EvaluationCase(
                    "document", manifest["pack_id"], stage_id,
                    _document_expected(assets_dir, manifest, stage), filtered_truth,
                ))
        return cases
    raise ValueError(f"unknown suite: {suite}")
