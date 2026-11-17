from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pdfplumber


ROOT = Path(os.environ.get("BOOKING_PRECHECK_MATERIALS_ROOT", Path(__file__).resolve().parents[1] / "assets")).resolve()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def contains_evidence(page_text: str, evidence_text: str) -> bool:
    return " ".join(evidence_text.split()) in " ".join(page_text.split())


def validate_manifest(path: Path, data: dict):
    errors = []
    required = {"schema_version", "pack_id", "case_ref", "canonical_fixture_path", "ground_truth_path", "stages"}
    if missing := required - data.keys():
        errors.append(f"{path}: missing keys {sorted(missing)}")
    if data.get("schema_version") != "0.1" or not re.fullmatch(r"DP-[0-9]{3}", data.get("pack_id", "")):
        errors.append(f"{path}: invalid schema version or pack ID")
    if not re.fullmatch(r"(TC|BA)-[0-9]{3}", data.get("case_ref", "")):
        errors.append(f"{path}: invalid case_ref")
    for stage in data.get("stages", []):
        if len(stage.get("documents", [])) != 3:
            errors.append(f"{path}: {stage.get('stage_id')} must declare exactly three document types")
        if {item.get("document_type") for item in stage.get("documents", [])} != {
            "BOOKING_REQUEST", "PRELIMINARY_DGD", "SDS_EXTRACT"
        }:
            errors.append(f"{path}: {stage.get('stage_id')} has invalid document type inventory")
    return errors


def validate_truth(path: Path, data: dict):
    errors = []
    required = {"schema_version", "pack_id", "case_ref", "documents"}
    if missing := required - data.keys():
        errors.append(f"{path}: missing keys {sorted(missing)}")
    for document in data.get("documents", []):
        if missing := {
            "document_id", "document_type", "document_version", "source_path",
            "text_layer_required", "facts"
        } - document.keys():
            errors.append(f"{path}: document truth missing keys {sorted(missing)}")
        if document.get("text_layer_required") is not True:
            errors.append(f"{path}: text_layer_required must be true")
        for fact in document.get("facts", []):
            if missing := {"fact_path", "expected_value", "evidence"} - fact.keys():
                errors.append(f"{path}: fact truth missing keys {sorted(missing)}")
            if not {"page", "evidence_text"} <= fact.get("evidence", {}).keys():
                errors.append(f"{path}: evidence requires page and evidence_text")
    return errors


def collect_keys(value):
    keys = set()
    if isinstance(value, dict):
        keys.update(value.keys())
        for item in value.values():
            keys.update(collect_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(collect_keys(item))
    return keys


def validate_rule_actions(snapshot: dict, path: Path):
    errors = []
    for rule in snapshot.get("rules", []):
        action = rule.get("action", {})
        required = {"result_status", "reason_code", "message_template", "routing_queue", "pause_automation"}
        if missing := required - action.keys():
            errors.append(f"{path}: {rule.get('rule_id')} action missing {sorted(missing)}")
            continue
        should_pause = action["result_status"] == "PRECHECK_BLOCKED"
        if action["pause_automation"] is not should_pause:
            errors.append(
                f"{path}: {rule['rule_id']} pause_automation must be {should_pause} "
                f"for {action['result_status']}"
            )
    return errors


def main():
    errors = []
    snapshot = load(ROOT / "policy_snapshot.json")
    rule_ids = {rule["rule_id"] for rule in snapshot["rules"]}
    rules_by_id = {rule["rule_id"]: rule for rule in snapshot["rules"]}
    errors.extend(validate_rule_actions(snapshot, ROOT / "policy_snapshot.json"))
    pdf_paths = set()
    evidence_count = 0
    stage_count = 0
    policy_evidence_count = 0
    page_counts = {}

    variant_path = ROOT / "policy-variants" / "PV-001-ibc-block.json"
    variant = load(variant_path)
    if variant["base_snapshot_id"] != snapshot["snapshot_id"]:
        errors.append(f"{variant_path}: base snapshot ID differs from policy_snapshot.json")
    variant_actions = {}
    for override in variant["rule_overrides"]:
        if override["rule_id"] not in rule_ids:
            errors.append(f"{variant_path}: unknown rule {override['rule_id']}")
        variant_actions[override["rule_id"]] = override["action"]
        should_pause = override["action"]["result_status"] == "PRECHECK_BLOCKED"
        if override["action"]["pause_automation"] is not should_pause:
            errors.append(f"{variant_path}: invalid pause_automation for {override['rule_id']}")

    for expected_path in sorted((ROOT / "cases").glob("TC-*/expected.json")):
        expected = load(expected_path)
        if "expected_routing_queue" not in expected:
            errors.append(f"{expected_path}: missing expected_routing_queue")
            continue
        queues = {
            rules_by_id[rule_id]["action"]["routing_queue"]
            for rule_id in expected["expected_rule_ids"]
            if rule_id in rules_by_id and rules_by_id[rule_id]["action"]["routing_queue"] is not None
        }
        expected_queue = expected["expected_routing_queue"]
        if queues != ({expected_queue} if expected_queue is not None else set()):
            errors.append(f"{expected_path}: routing queue differs from expected rules: {sorted(queues)}")

    for expected_path in sorted((ROOT / "business-cases").glob("BA-*/expected.json")):
        expected = load(expected_path)
        for step in expected["step_expectations"]:
            if "expected_routing_queues" not in step:
                errors.append(f"{expected_path}: {step['step_id']} missing expected_routing_queues")
                continue
            actions = {
                rule_id: (
                    variant_actions[rule_id]
                    if step["policy_snapshot_id"] == variant["snapshot_id"] and rule_id in variant_actions
                    else rules_by_id[rule_id]["action"]
                )
                for rule_id in step["expected_rule_ids"]
                if rule_id in rules_by_id
            }
            queues = {action["routing_queue"] for action in actions.values() if action["routing_queue"] is not None}
            if queues != set(step["expected_routing_queues"]):
                errors.append(
                    f"{expected_path}: {step['step_id']} routing queues differ: "
                    f"rules={sorted(queues)}, expected={sorted(step['expected_routing_queues'])}"
                )

    ba12_input_path = ROOT / "business-cases" / "BA-012" / "input.json"
    ba12_input = load(ba12_input_path)
    ba12_variant = ba12_input["steps"][1]["policy_variant"]
    referenced_variant = (ba12_input_path.parent / ba12_variant["variant_path"]).resolve()
    if referenced_variant != variant_path.resolve() or ba12_variant["variant_id"] != variant["variant_id"]:
        errors.append(f"{ba12_input_path}: Policy Variant reference does not resolve to PV-001")

    deprecated = {"manual_queue", "expected_manual_queue", "expected_manual_queues", "stop_processing"}
    for json_path in sorted(ROOT.rglob("*.json")):
        used = collect_keys(load(json_path)) & deprecated
        if used:
            errors.append(f"{json_path}: deprecated keys remain {sorted(used)}")

    for pack_dir in sorted((ROOT / "document-packs").glob("DP-*")):
        manifest_path = pack_dir / "manifest.json"
        truth_path = pack_dir / "ground-truth.json"
        manifest = load(manifest_path)
        truth = load(truth_path)
        stage_count += len(manifest["stages"])
        errors.extend(validate_manifest(manifest_path, manifest))
        errors.extend(validate_truth(truth_path, truth))

        truth_by_key = {(item.get("stage_id", "S1"), item["document_type"]): item for item in truth["documents"]}
        for stage in manifest["stages"]:
            for document in stage["documents"]:
                key = (stage["stage_id"], document["document_type"])
                if not document["present"]:
                    if document.get("source_path") is not None or document.get("pdf_path") is not None:
                        errors.append(f"{manifest_path}: absent {key} has a source or PDF path")
                    continue
                for field in ("source_path", "pdf_path"):
                    target = pack_dir / document[field]
                    if not target.exists():
                        errors.append(f"{manifest_path}: missing {field} {target}")
                if key not in truth_by_key:
                    errors.append(f"{truth_path}: missing truth for {key}")

        for document in truth["documents"]:
            pdf_path = pack_dir / document["source_path"]
            pdf_paths.add(pdf_path.resolve())
            if not pdf_path.exists():
                continue
            with pdfplumber.open(pdf_path) as pdf:
                page_texts = [page.extract_text() or "" for page in pdf.pages]
            page_counts[str(pdf_path.relative_to(ROOT))] = len(page_texts)
            if len(page_texts) != document.get("expected_page_count"):
                errors.append(
                    f"{truth_path}: {document['source_path']} expected "
                    f"{document.get('expected_page_count')} pages, got {len(page_texts)}"
                )
            for fact in document["facts"]:
                evidence_count += 1
                evidence = fact["evidence"]
                page = evidence["page"]
                if page < 1 or page > len(page_texts) or not contains_evidence(page_texts[page - 1], evidence["evidence_text"]):
                    errors.append(
                        f"{truth_path}: evidence missing on page {page}: "
                        f"{evidence['evidence_text']!r}"
                    )

    policy_index_path = ROOT / "policy-documents" / "POLICY_DOCUMENT_INDEX.json"
    policy_index = load(policy_index_path)
    policy_page_counts = load(ROOT / "policy-documents" / "EXPECTED_PAGE_COUNTS.json")["documents"]
    indexed_rules = set()
    for document in policy_index["documents"]:
        pdf_path = ROOT / document["pdf_path"]
        source_path = ROOT / document["source_path"]
        pdf_paths.add(pdf_path.resolve())
        if not source_path.exists() or not pdf_path.exists():
            errors.append(f"{policy_index_path}: missing source or PDF for {document['policy_document_id']}")
            continue
        with pdfplumber.open(pdf_path) as pdf:
            page_texts = [page.extract_text() or "" for page in pdf.pages]
        page_counts[str(pdf_path.relative_to(ROOT))] = len(page_texts)
        expected_pages = policy_page_counts.get(document["policy_document_id"])
        if len(page_texts) != expected_pages:
            errors.append(
                f"{policy_index_path}: {document['policy_document_id']} expected {expected_pages} pages, "
                f"got {len(page_texts)}"
            )
        for evidence in document["rule_evidence"]:
            policy_evidence_count += 1
            indexed_rules.add(evidence["rule_id"])
            page = evidence["page"]
            if page < 1 or page > len(page_texts) or not contains_evidence(page_texts[page - 1], evidence["evidence_text"]):
                errors.append(
                    f"{policy_index_path}: policy evidence missing for {evidence['rule_id']} "
                    f"on page {page}"
                )
    if indexed_rules != rule_ids:
        errors.append(
            f"Policy coverage differs: missing={sorted(rule_ids - indexed_rules)}, "
            f"extra={sorted(indexed_rules - rule_ids)}"
        )

    actual_pdfs = {path.resolve() for path in ROOT.rglob("*.pdf")}
    if pdf_paths != actual_pdfs:
        errors.append(
            f"PDF inventory differs: unindexed={sorted(map(str, actual_pdfs - pdf_paths))}, "
            f"missing={sorted(map(str, pdf_paths - actual_pdfs))}"
        )

    print(json.dumps({
        "document_packs": len(list((ROOT / "document-packs").glob("DP-*"))),
        "document_pack_stages": stage_count,
        "pdf_files": len(actual_pdfs),
        "policy_documents": len(policy_index["documents"]),
        "field_evidence_facts": evidence_count,
        "policy_evidence_fragments": policy_evidence_count,
        "policy_rules_indexed": len(indexed_rules),
        "policy_variants": 1,
        "pdf_page_counts": page_counts,
        "errors": errors,
    }, indent=2, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
