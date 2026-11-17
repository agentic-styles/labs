from booking_precheck_eval.scoring import percentile, score_document_facts, score_result


def _result(status="MANUAL_REVIEW"):
    return {
        "technical_status": "COMPLETED",
        "final_status": status,
        "reason_codes": ["R1"],
        "routing_queues": ["DG_DESK"],
        "required_facts": [],
        "policy_snapshot_id": "SNAPSHOT",
        "next_action": "ROUTE",
        "matched_rules": [{
            "rule_id": "R1",
            "policy_evidence_id": "POLICY-R1",
            "fact_evidence_ids": ["FACT-1"],
        }],
        "evidence": [{
            "evidence_id": "FACT-1",
            "evidence_type": "DOCUMENT_FIELD",
            "fact_path": "documents.booking_request.cargo.un_number",
            "value": "UN1263",
            "document_id": "DOC-1",
            "page": 1,
            "evidence_text": "UN Number UN1263",
        }, {
            "evidence_id": "POLICY-R1",
            "evidence_type": "POLICY_RULE",
            "rule_id": "R1",
            "policy_document_id": "POL-1",
            "page": 2,
            "evidence_text": "Synthetic policy rule",
        }],
    }


def test_result_score_checks_rules_evidence_and_critical_false_clear():
    expected = {
        "expected_status": "MANUAL_REVIEW",
        "expected_reason_codes": ["R1"],
        "expected_rule_ids": ["R1"],
        "expected_routing_queues": ["DG_DESK"],
        "expected_required_facts": [],
        "expected_next_action": "ROUTE",
        "policy_snapshot_id": "SNAPSHOT",
        "expected_evidence": [{
            "fact": "documents.booking_request.cargo.un_number",
            "expected_value": "UN1263",
        }],
    }

    score = score_result(_result(), expected)

    assert score["passed"] is True
    assert score["rule_metrics"] == {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    assert score["evidence_integrity"]["valid"] is True

    blocked = {**expected, "expected_status": "PRECHECK_BLOCKED"}
    false_clear = _result("PRECHECK_PASS")
    assert score_result(false_clear, blocked)["critical_false_clear"] is True


def test_document_fact_score_normalizes_values_and_reports_missing():
    facts = {"documents": {"booking_request": {"cargo": {"un_number": "UN 1263"}}}}
    truth = {"documents": [{"facts": [{
        "fact_path": "documents.booking_request.cargo.un_number",
        "expected_value": "UN1263",
        "normalization": ["UN_NUMBER_CANONICAL"],
    }, {
        "fact_path": "documents.booking_request.cargo.proper_shipping_name",
        "expected_value": "PAINT",
        "normalization": ["PSN_CANONICAL"],
    }]}]}

    score = score_document_facts(facts, truth)

    assert score["accuracy"] == 0.5
    assert score["errors"][0]["fact_path"].endswith("proper_shipping_name")
    assert score_document_facts(None, truth)["available"] is False


def test_percentile_uses_nearest_rank():
    assert percentile([10, 20, 30, 40], 0.95) == 40
    assert percentile([], 0.95) is None
