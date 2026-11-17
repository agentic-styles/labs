import json
import sys
from pathlib import Path

from booking_precheck_eval.adapters import CliAdapter
from booking_precheck_eval.catalog import EvaluationCase
from booking_precheck_eval.config import SuiteCommand, SystemConfig
from booking_precheck_eval.report import summarize, write_reports
from booking_precheck_eval.runner import RunRecord


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT.parents[1] / "assets"


def test_cli_adapter_invokes_black_box_and_parses_json():
    # The fake process does not consume assets, so check the fixture location
    # explicitly rather than silently accepting an obsolete workspace path.
    assert (ASSETS / "policy_snapshot.json").is_file()
    system = SystemConfig(
        name="fake",
        command=(sys.executable, str(ROOT / "fixtures" / "fake_system.py")),
        cwd=ROOT,
        suites={"rule": SuiteCommand(("--case", "{case_id}"), 5)},
    )
    invocation = CliAdapter(system, ASSETS).invoke(EvaluationCase("rule", "TC-001", None, {}))

    assert invocation.error is None
    assert invocation.payload["final_status"] == "PRECHECK_PASS"
    assert invocation.command[-1] == "TC-001"


def test_reports_preserve_raw_runs_and_aggregate_metrics(tmp_path):
    record = RunRecord(
        system="fake", suite="rule", case_id="TC-001", stage_id=None, attempt=1,
        elapsed_ms=25, invocation_error=None, score={"passed": True, "critical_false_clear": False},
        result_metrics={"duration_ms": 7, "model_call_count": 1, "input_tokens": 10, "output_tokens": 5},
        result={"final_status": "PRECHECK_PASS"}, facts_observed=False, stderr="",
    )

    summary = summarize([record])
    paths = write_reports([record], tmp_path)

    assert summary["summaries"][0]["functional_pass_rate"] == 1.0
    assert json.loads(paths["runs"].read_text(encoding="utf-8"))[0]["case_id"] == "TC-001"
    assert "Field accuracy" in paths["markdown"].read_text(encoding="utf-8")
