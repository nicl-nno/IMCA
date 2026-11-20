import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

CONDITIONS = ('without-memory', 'with-imca', 'with-codebase-memory')
INTERRUPTIONS = {'provider_failure', 'provider_or_transport_failure', 'runtime_control_error', 'client_failure'}
ALLOWED_OUTCOMES = INTERRUPTIONS | {'agent_finished', 'request_limit', 'agent_time_limit'}
DEFAULT_EVIDENCE = Path(__file__).resolve().parent / 'heldout_memory_evidence'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def contained_file(directory, relative):
    if not isinstance(relative, str) or '\\' in relative:
        raise ValueError('Invalid evidence path')
    parts = PurePosixPath(relative)
    if parts.is_absolute() or not parts.parts or any(part in ('..', '.') for part in parts.parts) or ':' in relative:
        raise ValueError('Invalid evidence path')
    path = (directory / relative).resolve()
    if not path.is_relative_to(directory.resolve()) or not path.is_file():
        raise ValueError('Evidence file is missing or outside its directory')
    return path


def verify_files(directory):
    manifest = read_json(directory / 'manifest.json')
    if manifest.get('schema_version') != 1:
        raise ValueError('Unknown evidence manifest')
    for name, expected in manifest['files_sha256'].items():
        if hashlib.sha256(contained_file(directory, name).read_bytes()).hexdigest() != expected:
            raise ValueError('Evidence checksum mismatch: ' + name)
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*') if path.is_file() and path.name != 'manifest.json'}
    if actual != set(manifest['files_sha256']):
        raise ValueError('The evidence file inventory differs from its manifest')
    data = read_json(directory / 'results.json')
    policy = read_json(directory / 'protocol.json')
    for task in data['tasks']:
        if task['status'] == 'preparation_unavailable':
            if task['model_attempts'] != 0 or task['repair_outcome'] is not None:
                raise ValueError('An unavailable task cannot contain model attempts or a scored repair')
            continue
        if task['status'] != 'evaluated':
            raise ValueError('Unknown task preparation status')
        for condition, row in task['conditions'].items():
            path = row['patch']
            body = b'' if path is None else contained_file(directory, path).read_bytes()
            if len(body) != row['patch_bytes'] or hashlib.sha256(body).hexdigest() != row['patch_sha256']:
                raise ValueError('A frozen prediction differs from its recorded bytes')
    return data, policy


def counted(value, label):
    if type(value) is not int or value < 0:
        raise ValueError('Invalid nonnegative count: ' + label)
    return value


def test_groups(task):
    required, preserved = task['required_tests'], task['preserved_tests']
    for values in (required, preserved):
        if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values) or len(values) != len(set(values)):
            raise ValueError('Invalid expected test list')
    if not required or set(required) & set(preserved):
        raise ValueError('Expected test groups are empty or overlap')
    return set(required) | set(preserved)


def checked_tests(tests, expected):
    if not isinstance(tests, dict) or set(tests) != expected or any(value not in ('PASSED', 'FAILED', 'ERROR') for value in tests.values()):
        raise ValueError('Missing or indeterminate benchmark test results')
    return all(value == 'PASSED' for value in tests.values())


def summarize(data, policy):
    if data.get('schema_version') != 1 or data['benchmark'] != policy['benchmark']:
        raise ValueError('The results schema or benchmark changed')
    tasks = data['tasks']
    if len({row['task'] for row in tasks}) != len(tasks) or [row['task'] for row in tasks] != policy['planned_task_ids']:
        raise ValueError('The planned task inventory changed')
    attempts = forwards = nonempty = passing_patches = 0
    passed = dict.fromkeys(CONDITIONS, 0)
    observed = dict.fromkeys(CONDITIONS, 0)
    paired_passed = dict.fromkeys(CONDITIONS, 0)
    paired_observed = dict.fromkeys(CONDITIONS, 0)
    paired_tasks, unavailable, table, imca_only, native_only = [], [], [], [], []
    for task in tasks:
        if task['status'] == 'preparation_unavailable':
            if task['model_attempts'] != 0 or task['repair_outcome'] is not None:
                raise ValueError('An unavailable task cannot contain model attempts or a scored repair')
            unavailable.append(task['task'])
            table.append({'task': task['task'], 'status': task['status'], 'conditions': {condition: None for condition in CONDITIONS}})
            continue
        identifier = task['task']
        if task['status'] != 'evaluated' or set(task['conditions']) != set(CONDITIONS):
            raise ValueError('An evaluated task must have all three original conditions')
        expected = test_groups(task)
        original = task['original_source']['tests']
        original_passed = checked_tests(original, expected)
        if task['original_source']['outcome'] != ('resolved' if original_passed else 'unresolved'):
            raise ValueError('The original-source outcome differs from its tests')
        original_failures = {test for test, value in original.items() if value != 'PASSED'}
        row = {'task': identifier, 'status': 'evaluated', 'source_control_passed': original_passed,
            'required_test_count': len(task['required_tests']), 'preserved_test_count': len(task['preserved_tests']), 'conditions': {}}
        paired = True
        for condition in CONDITIONS:
            result = task['conditions'][condition]
            if result['runtime_outcome'] not in ALLOWED_OUTCOMES or result['cleanup_succeeded'] is not True:
                raise ValueError('Unknown runtime outcome or incomplete cleanup')
            count = counted(result['model_forward_attempts'], 'forward attempts')
            if count > policy['per_attempt_limits']['model_forwards']:
                raise ValueError('An original attempt exceeded its request allowance')
            forwards += count
            attempts += 1
            tests_passed = checked_tests(result['tests'], expected)
            empty = result['patch_bytes'] == 0
            if empty and result['patch'] is not None or not empty and not isinstance(result['patch'], str):
                raise ValueError('The patch path differs from its recorded size')
            if empty:
                if result['artifact_outcome'] != 'empty_patch' or result['tests'] != original or result['test_observation_source'] != 'original_source_control':
                    raise ValueError('An empty patch must retain the unchanged original-source observations')
                resolved = False
            else:
                counted(result['patch_bytes'], 'patch size')
                resolved = tests_passed
                if result['artifact_outcome'] != ('resolved' if resolved else 'unresolved'):
                    raise ValueError('The artifact outcome differs from the observed tests')
                nonempty += 1
                passing_patches += int(resolved)
            repair = resolved and bool(original_failures)
            interrupted = result['runtime_outcome'] in INTERRUPTIONS
            paired &= not interrupted
            passed[condition] += int(resolved)
            observed[condition] += int(repair)
            row['conditions'][condition] = {'artifact_outcome': result['artifact_outcome'], 'artifact_resolved': resolved,
                'observed_repair': repair, 'runtime_outcome': result['runtime_outcome'],
                'infrastructure_interruption': interrupted, 'model_forward_attempts': count}
        if paired:
            paired_tasks.append(identifier)
            for condition in CONDITIONS:
                paired_passed[condition] += int(row['conditions'][condition]['artifact_resolved'])
                paired_observed[condition] += int(row['conditions'][condition]['observed_repair'])
        if row['conditions']['with-imca']['observed_repair'] and not row['conditions']['with-codebase-memory']['observed_repair']:
            imca_only.append(identifier)
        if row['conditions']['with-codebase-memory']['observed_repair'] and not row['conditions']['with-imca']['observed_repair']:
            native_only.append(identifier)
        table.append(row)
    if forwards > policy['maximum_model_forward_attempts']:
        raise ValueError('The live batch exceeded its total request allowance')
    return {'schema_version': 1, 'benchmark': data['benchmark'], 'planned_tasks': len(tasks),
        'evaluated_tasks': len(tasks) - len(unavailable), 'preparation_unavailable_tasks': unavailable,
        'original_attempts': attempts, 'model_forward_attempts': forwards, 'nonempty_patches': nonempty,
        'passing_nonempty_patches': passing_patches, 'passing_artifacts': passed, 'observed_repairs_from_saved_artifacts': observed,
        'tasks_with_three_uninterrupted_attempts': paired_tasks, 'uninterrupted_paired_passing_artifacts': paired_passed,
        'uninterrupted_paired_observed_repairs': paired_observed, 'imca_only_saved_artifact_repairs': imca_only,
        'codebase_memory_only_saved_artifact_repairs': native_only, 'task_results': table}


def reproduce(directory):
    data, policy = verify_files(directory)
    result = summarize(data, policy)
    if result != read_json(directory / 'expected-summary.json'):
        raise ValueError('The recomputed summary differs from the published result')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = reproduce(args.evidence)
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output is None:
        print(text, end='')
    else:
        args.output.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()
