"""Gate the deterministic smoke results; these are not LLM benchmark scores."""
from pathlib import Path
import argparse
import json

EXPECTED = {'rule': 30, 'document': 9, 'business': 12}
ROOT = Path(__file__).resolve().parents[1]


def verify(directory: Path) -> None:
    expectations = json.loads((ROOT / 'booking-precheck/evaluation/configs/deterministic-expectations.json').read_text())
    known = expectations['known_document_failures']
    report = json.loads((directory / 'summary.json').read_text(encoding='utf-8'))
    runs = json.loads((directory / 'runs.json').read_text(encoding='utf-8'))
    assert report['total_runs'] == len(runs) == sum(EXPECTED.values()), 'Incomplete evaluation inventory'
    assert len(report['summaries']) == len(EXPECTED), 'Unexpected system/suite inventory'
    for suite, count in EXPECTED.items():
        items = [row for row in report['summaries'] if row['suite'] == suite]
        assert len(items) == 1, f'Missing or duplicated suite: {suite}'
        row = items[0]
        assert row['system'] == 'rule_baseline' and row['runs'] == count, (suite, row)
        expected_passes = count - len(known) if suite == 'document' else count
        assert row['invocation_success_rate'] == 1.0, (suite, row)
        assert row['functional_pass_rate'] == expected_passes / count, (suite, row)
        assert row['critical_false_clear_count'] == 0, (suite, row)
        assert row['model_call_count'] == row['input_tokens'] == row['output_tokens'] == 0, 'Offline smoke called a model'
    keys = set()
    for run in runs:
        key = (run['suite'], run['case_id'], run['stage_id'], run['attempt'])
        assert key not in keys, f'Duplicate case: {key}'
        keys.add(key)
        assert run['invocation_error'] is None, key
        expected_failure = known.get(f"{run['case_id']}:{run['stage_id']}") if run['suite'] == 'document' else None
        failed_checks = {name: value for name, value in run['score'].get('checks', {}).items() if value is False}
        if expected_failure:
            assert run['score']['passed'] is False, f'Known limitation changed; review expectations: {key}'
            assert failed_checks == expected_failure['failed_checks'], (key, failed_checks)
            assert run['score']['evidence_integrity']['errors'] == expected_failure['evidence_errors'], key
        else:
            assert run['score']['passed'] is True, key
        metrics = run['result_metrics']
        assert metrics['model_call_count'] == metrics['input_tokens'] == metrics['output_tokens'] == 0, key
    print('PASS: 51 invocations; 30/30 rule and 12/12 business pass; 2/9 document stages pass with 7 explicitly reviewed evidence limitations; zero model calls')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    verify(parser.parse_args().directory)
