from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from booking_precheck_contracts import (
    CaseReference,
    DocumentReference,
    EvaluationRequest,
    PolicyReference,
)

from .catalog import EvaluationCase, discover_cases


@dataclass(frozen=True)
class DocumentDatasetItem:
    case: EvaluationCase
    input: dict[str, Any]
    expected_output: dict[str, Any]
    metadata: dict[str, Any]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def document_dataset_items(assets_dir: Path) -> list[DocumentDatasetItem]:
    items = []
    for case in discover_cases(assets_dir, "document"):
        items.append(DocumentDatasetItem(
            case=case,
            input={"pack_id": case.case_id, "stage_id": case.stage_id},
            expected_output={
                "case_key": case.key,
                "expected": case.expected,
                "ground_truth": case.ground_truth,
            },
            metadata={
                "suite": "BOOKING_PRECHECK_DOCUMENT",
                "training_only": True,
                "document_count": len(case.ground_truth.get("documents", [])) if case.ground_truth else 0,
            },
        ))
    return items


def make_request(assets_dir: Path, pack_id: str, stage_id: str, *, request_id: str | None = None) -> EvaluationRequest:
    pack_dir = assets_dir / "document-packs" / pack_id
    manifest = _load(pack_dir / "manifest.json")
    truth = _load(pack_dir / manifest.get("ground_truth_path", "ground-truth.json"))
    snapshot = _load(assets_dir / "policy_snapshot.json")
    stage = next(item for item in manifest["stages"] if item["stage_id"] == stage_id)
    truth_documents = {
        item["document_type"]: item
        for item in truth["documents"]
        if item.get("stage_id", "S1") == stage_id
    }
    documents = []
    for item in stage["documents"]:
        if not item.get("present"):
            continue
        document_truth = truth_documents[item["document_type"]]
        documents.append(DocumentReference(
            document_id=document_truth["document_id"],
            document_type=item["document_type"],
            document_version=int(item.get("document_version", document_truth["document_version"])),
            path=str((pack_dir / item["pdf_path"]).resolve()),
        ))
    return EvaluationRequest(
        request_id=request_id or f"{pack_id}-{stage_id}-{uuid4()}",
        case=CaseReference(pack_id=pack_id, stage_id=stage_id),
        policy=PolicyReference(snapshot_id=snapshot["snapshot_id"]),
        documents=documents,
    )


def dataset_item_id(dataset_name: str, case_key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"langfuse:{dataset_name}:{case_key}"))
