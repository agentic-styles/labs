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
    assets = ROOT / 'booking-precheck/assets'
    expected_keys = {('rule', path.name, None, 1) for path in (assets / 'cases').glob('TC-*')}
    expected_keys |= {('business', path.name, None, 1) for path in (assets / 'business-cases').glob('BA-*')}
    for path in (assets / 'document-packs').glob('DP-*/manifest.json'):
        manifest = json.loads(path.read_text())
        expected_keys |= {('document', manifest['pack_id'], stage['stage_id'], 1) for stage in manifest['stages']}
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
        assert run['system'] == 'rule_baseline', 'Unexpected system in raw evaluation'
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
            assert all(run['score']['checks'][check] is True for check in ('technical_completed', 'status', 'reason_codes', 'rules', 'routing_queues', 'required_facts', 'policy_snapshot')), key
        else:
            assert run['score']['passed'] is True, key
        metrics = run['result_metrics']
        assert metrics['model_call_count'] == metrics['input_tokens'] == metrics['output_tokens'] == 0, key
    assert keys == expected_keys, 'Case IDs or stages differ from the frozen inventory'
    assert {suite: sum(run['suite'] == suite for run in runs) for suite in EXPECTED} == EXPECTED, 'Raw suite counts differ from summary'
    print('PASS: 51 invocations; 30/30 rule and 12/12 business pass; 2/9 document stages pass with 7 explicitly reviewed evidence limitations; zero model calls')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    verify(parser.parse_args().directory)
