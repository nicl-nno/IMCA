import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


EVIDENCE = Path(__file__).resolve().parent / 'memory_repair_evidence'
CONDITIONS = ('without-memory', 'with-imca', 'with-codebase-memory')
FINISHED = {'agent_finished', 'request_limit'}
INTERRUPTED = {'provider_or_transport_failure'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local_file(root, name):
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name or '\0' in name
            or PurePosixPath(name).is_absolute() or any(part in ('', '.', '..') for part in name.split('/'))):
        raise ValueError('Evidence path leaves its snapshot')
    root = Path(root).resolve()
    path = root.joinpath(*PurePosixPath(name).parts).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Evidence file is missing or outside its snapshot: ' + name)
    return path


def load_snapshot(root=EVIDENCE):
    root = Path(root)
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['files_sha256'].items():
        if digest(local_file(root, name)) != expected:
            raise ValueError('Evidence checksum mismatch: ' + name)
    if 'development-runs.json' not in manifest['files_sha256']:
        raise ValueError('The evidence manifest lacks the development records')
    data = json.loads((root / 'development-runs.json').read_text(encoding='utf-8'))
    for task in data['tasks']:
        prompt = task['prompt']
        if manifest['files_sha256'].get(prompt['file']) != prompt['sha256']:
            raise ValueError('The shared user prompt is not bound to its evidence manifest')
        for value in task['conditions'].values():
            patch = value.get('patch')
            if patch is not None:
                if manifest['files_sha256'].get(patch['file']) != patch['sha256']:
                    raise ValueError('A saved patch is not bound to its evidence manifest')
                if not local_file(root, patch['file']).stat().st_size:
                    raise ValueError('An advertised saved patch is empty')
    return data


def statuses(value, expected):
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError('Task test results are missing or unexpected')
    if any(status not in ('PASSED', 'FAILED') for status in value.values()):
        raise ValueError('Task tests contain indeterminate results')
    return value


def summarize(data):
    if data.get('schema') != 1 or data.get('scope') != 'development_saved_patch_validation':
        raise ValueError('Unsupported evidence scope')
    output = {'scope': data['scope'], 'independent_development_tasks': 0,
        'recorded_attempts': 0, 'saved_patches_tested': 0, 'saved_patches_passed': 0,
        'saved_patches_failed': 0, 'missing_patch_after_interruption': 0,
        'transport_interrupted_attempts': 0, 'complete_three_condition_tasks': 0, 'tasks': []}
    seen = set()
    for task in data['tasks']:
        name = task['task']
        if name in seen or task.get('held_out') is not False or set(task['conditions']) != set(CONDITIONS):
            raise ValueError('Duplicate task, mixed held-out scope or incomplete conditions')
        seen.add(name)
        required, preserved = task['required_tests'], task['preserved_tests']
        expected = set(required) | set(preserved)
        if not expected or len(expected) != len(required) + len(preserved):
            raise ValueError('Task test groups are empty, duplicate or overlapping')
        original = task.get('original_source_test_status')
        original_failures = None
        control = None
        if original is not None:
            statuses(original, expected)
            original_failures = sorted(test for test in expected if original[test] == 'FAILED')
            control = {'failing_tests': original_failures,
                'dataset_fail_to_pass_already_passing': sum(original[test] == 'PASSED' for test in required),
                'dataset_pass_to_pass_failing': sum(original[test] == 'FAILED' for test in preserved)}
        rows = {}
        for condition in CONDITIONS:
            value = task['conditions'][condition]
            runtime = value['runtime_outcome']
            if runtime not in FINISHED | INTERRUPTED:
                raise ValueError('Unknown recorded run outcome')
            if (type(value['model_request_attempts']) is not int or value['model_request_attempts'] < 0
                    or value['model_request_attempts'] > task['limits']['model_forwards']):
                raise ValueError('Invalid model request count')
            interrupted = runtime in INTERRUPTED
            if interrupted and value['eligible_for_uninterrupted_attempt_comparison']:
                raise ValueError('An interrupted attempt cannot be a complete comparison condition')
            output['recorded_attempts'] += 1
            output['transport_interrupted_attempts'] += interrupted
            patch = value['patch']
            passed = None
            fixed = newly_failed = None
            observed_repair = None
            if patch is None:
                if value['test_status'] is not None or not interrupted:
                    raise ValueError('Missing patch record has unsupported evaluation semantics')
                output['missing_patch_after_interruption'] += 1
            else:
                measured = statuses(value['test_status'], expected)
                passed = all(status == 'PASSED' for status in measured.values())
                if value['evaluator_resolved'] is not passed:
                    raise ValueError('Recorded resolution contradicts the task test outcomes')
                output['saved_patches_tested'] += 1
                output['saved_patches_passed'] += passed
                output['saved_patches_failed'] += not passed
                if original is not None:
                    fixed = [test for test in original_failures if measured[test] == 'PASSED']
                    newly_failed = sorted(test for test in expected if original[test] == 'PASSED' and measured[test] == 'FAILED')
                    observed_repair = bool(original_failures) and passed and not newly_failed
            rows[condition] = {'saved_patch_passed': passed, 'task_test_count': len(expected) if patch is not None else None,
                'runtime_outcome': runtime, 'model_request_attempts': value['model_request_attempts'],
                'active_agent_seconds': value['active_agent_seconds'], 'memory_tool_calls': value['memory_tool_calls'],
                'observed_repair': observed_repair, 'original_failures_fixed': fixed, 'newly_failing_tests': newly_failed}
        complete = all(task['conditions'][condition]['eligible_for_uninterrupted_attempt_comparison']
                       and rows[condition]['saved_patch_passed'] is not None for condition in CONDITIONS)
        output['complete_three_condition_tasks'] += complete
        output['tasks'].append({'task': name, 'test_count': len(expected), 'original_source_control': control,
                               'complete_three_condition_comparison': complete, 'conditions': rows})
    output['independent_development_tasks'] = len(seen)
    return output


def render_table(result):
    lines = ['| Task | Condition | Saved patch tests | Run outcome | Request attempts |',
             '| --- | --- | --- | --- | --- |']
    labels = {'without-memory': 'No memory', 'with-imca': 'IMCA', 'with-codebase-memory': 'Codebase-Memory'}
    outcomes = {'agent_finished': 'Finished', 'request_limit': 'Request limit', 'provider_or_transport_failure': 'Transport interruption'}
    for task in result['tasks']:
        for condition in CONDITIONS:
            row = task['conditions'][condition]
            passed = row['saved_patch_passed']
            tests = ('No patch' if passed is None else str(row['task_test_count']) + '/' + str(row['task_test_count']) if passed else 'Failed')
            lines.append('| ' + ' | '.join((task['task'], labels[condition], tests,
                outcomes[row['runtime_outcome']], str(row['model_request_attempts']))) + ' |')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, default=EVIDENCE)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--output', type=Path)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--table', action='store_true')
    args = parser.parse_args()
    result = summarize(load_snapshot(args.evidence))
    if args.check:
        expected = json.loads(local_file(args.evidence, 'expected-summary.json').read_text(encoding='utf-8'))
        if result != expected:
            raise ValueError('Recomputed analysis differs from the frozen summary')
        print(json.dumps({'status': 'frozen_summary_verified', **{key: value for key, value in result.items() if key != 'tasks'}}, indent=2))
    elif args.table:
        print(render_table(result))
    elif args.output:
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    else:
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
