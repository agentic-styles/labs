from pathlib import Path

from booking_precheck_eval.catalog import discover_cases


ASSETS = Path(__file__).resolve().parents[2] / "assets"


def test_catalog_discovers_all_published_cases():
    assert len(discover_cases(ASSETS, "rule")) == 30
    assert len(discover_cases(ASSETS, "document")) == 9
    assert len(discover_cases(ASSETS, "business")) == 12


def test_document_catalog_filters_multistage_ground_truth():
    cases = {case.key: case for case in discover_cases(ASSETS, "document")}

    assert {case.stage_id for case in cases.values() if case.case_id == "DP-008"} == {"S1", "S2"}
    assert {item["stage_id"] for item in cases["DP-008:S2"].ground_truth["documents"]} == {"S2"}
    assert cases["DP-008:S1"].expected["expected_status"] == "REQUIRE_INFORMATION"
    assert cases["DP-008:S2"].expected["expected_status"] == "PRECHECK_PASS"
