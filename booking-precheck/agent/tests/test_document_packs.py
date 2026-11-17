from __future__ import annotations

import json

import pytest

from booking_precheck.extractors import extract_document_pack
from booking_precheck.facts import MISSING, first


PACK_STAGES = [(f"DP-{index:03d}", "S1") for index in range(1, 8)] + [("DP-008", "S1"), ("DP-008", "S2")]


def test_fact_path_resolves_numeric_list_indexes():
    facts = {"documents": {"booking_request": {"parties": [
        {"role": "SHIPPER", "name": "A"},
        {"role": "CONSIGNEE", "name": "B"},
    ]}}}

    assert first(facts, "documents.booking_request.parties[1].role") == "CONSIGNEE"
    assert first(facts, "documents.booking_request.parties[2].role") is MISSING


def _extracted_value(facts, path):
    if path == "documents.booking_request.parties.consignee":
        return next((p["name"] for p in facts["documents"]["booking_request"]["parties"] if p["role"] == "CONSIGNEE"), None)
    return first(facts, path)


@pytest.mark.parametrize(("pack_id", "stage_id"), PACK_STAGES)
def test_pdf_pack_extracts_ground_truth_and_reaches_expected_status(service, pack_id, stage_id):
    pack_dir = service.settings.assets_dir / "document-packs" / pack_id
    manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    ground_truth = json.loads((pack_dir / "ground-truth.json").read_text(encoding="utf-8"))
    stage = next(item for item in manifest["stages"] if item["stage_id"] == stage_id)
    facts = extract_document_pack(pack_dir, stage_id)
    for document in [item for item in ground_truth["documents"] if item.get("stage_id", "S1") == stage_id]:
        for fact in document["facts"]:
            assert _extracted_value(facts, fact["fact_path"]) == fact["expected_value"], fact["fact_path"]
    result = service.run_document_pack(pack_id, stage_id)
    assert result["final_status"] == stage["expected_status"]
