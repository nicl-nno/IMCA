import argparse
from collections import Counter, defaultdict
import hashlib
import importlib
import itertools
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import sqlite3
import sys
import uuid

from memory_graph_adapter import GraphAdapter, parse_graph


METHOD = 'codebase_memory_structural_adapter'
EVIDENCE = Path(__file__).resolve().parent / 'memory_comparison_evidence'
REQUIRED_EVIDENCE = frozenset(('native-graph.json', 'queries.json', 'predictions.json',
    'native-validation.json', 'retrieval-summary.json', 'agent-pilots.json'))


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def owned_path(root, name):
    root = Path(root).resolve()
    text = str(name)
    if '\\' in text or PureWindowsPath(text).drive or '..' in PurePosixPath(text).parts:
        raise ValueError('Evidence path is not a safe relative path')
    path = (root / text).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError('Evidence path leaves its root')
    return path


def check_hashes(root, hashes):
    for name, expected in hashes.items():
        if digest(owned_path(root, name)) != expected:
            raise ValueError('Checksum mismatch: ' + name)


def verify_evidence(root):
    manifest = load(Path(root) / 'manifest.json')
    if manifest.get('schema_version') != 1:
        raise ValueError('Unknown evidence schema')
    if not REQUIRED_EVIDENCE.issubset(manifest['files_sha256']):
        raise ValueError('The evidence manifest is incomplete')
    check_hashes(root, manifest['files_sha256'])
    return manifest


def query_inputs(tasks):
    queries = []
    seen = set()
    for task in tasks:
        if task['id'] in seen:
            raise ValueError('Duplicate task identifier')
        seen.add(task['id'])
        queries.append({key: task[key] for key in ('id', 'query', 'query_text')})
    return queries


def top_ids(route):
    def score(item):
        signals = item.get('signals', {})
        return sum(value['contribution'] for value in signals.values()) if signals else item.get('score', 0.0)
    return [item['id'] for item in sorted(route['candidates'],
            key=lambda item: (-score(item), item['corpus_order']))[:5]]


def lexical_ids(engine, question):
    scores = engine.lexical.scores(question)
    order = sorted(range(len(engine.ids)), key=lambda index: (-float(scores[index]), index))
    return [engine.ids[index] for index in order[:5]]


def open_graph(nodes, edges):
    connection = sqlite3.connect(':memory:')
    connection.execute('CREATE TABLE nodes(id INTEGER,label TEXT,name TEXT,qualified_name TEXT,file_path TEXT)')
    connection.execute('CREATE TABLE edges(source_id INTEGER,type TEXT,target_id INTEGER)')
    connection.executemany('INSERT INTO nodes VALUES(?,?,?,?,?)',
        [(n['id'], n['label'], n['name'], n['qualified_name'], n['file_path']) for n in nodes.values()])
    connection.executemany('INSERT INTO edges VALUES(?,?,?)', edges)
    connection.execute('PRAGMA query_only=ON')
    return connection


def check_native_validation(rows, traces):
    by_id = {trace['id']: trace for trace in traces}
    if len(by_id) != len(traces):
        raise ValueError('Duplicate adapter trace identifier')
    seen_queries, covered = set(), set()
    mismatches = 0
    for row in rows:
        if row['query_id'] in seen_queries or not row['task_ids']:
            raise ValueError('Duplicate or empty validation query')
        seen_queries.add(row['query_id'])
        canonical, raw = row['canonical_node_ids'], row['raw_node_ids']
        if len(raw) != len(set(raw)) or sorted(raw) != sorted(canonical):
            raise ValueError('Recorded native candidate sets differ')
        mismatches += raw != canonical
        for task_id in row['task_ids']:
            if task_id in covered or task_id not in by_id:
                raise ValueError('Native validation has invalid task coverage')
            covered.add(task_id)
            if by_id[task_id]['candidate_node_ids'] != canonical:
                raise ValueError('Adapter differs from recorded native result: ' + task_id)
    if covered != set(by_id):
        raise ValueError('Native validation does not cover all tasks')
    return {'recorded_native_queries': len(rows), 'task_queries_matched': len(covered),
            'raw_order_mismatches': mismatches, 'candidate_set_mismatches': 0,
            'new_native_tool_calls': 0}


def expected_ids(expected):
    kind = expected['kind']
    if kind in ('exact_symbol', 'in_top_k'):
        return [expected['stable_id']]
    if kind == 'contains':
        return list(dict.fromkeys(expected['required']))
    if kind == 'exact_set':
        return list(dict.fromkeys(expected['stable_ids']))
    raise ValueError('Unexpected benchmark scoring rule')


def duplicate_audit(tasks):
    groups = defaultdict(list)
    for task in tasks:
        key = json.dumps({'query': task['query'], 'query_text': task['query_text']}, sort_keys=True)
        groups[key].append(task)
    repeated = []
    for group in groups.values():
        if len(group) > 1:
            expected = {json.dumps(task['expected'], sort_keys=True) for task in group}
            repeated.append({'task_ids': [task['id'] for task in group], 'operation': group[0]['query']['op'],
                             'distinct_expected_values': len(expected)})
    return {'unique_query_and_text_inputs': len(groups), 'repeated_input_groups': len(repeated),
            'tasks_in_repeated_input_groups': sum(len(row['task_ids']) for row in repeated),
            'groups_with_different_expected_values': sum(row['distinct_expected_values'] > 1 for row in repeated),
            'groups': repeated}


def score_summary(values):
    return {'n': len(values), 'passed': sum(value > 0.999 for value in values),
            'raw': sum(values) / len(values) if values else None}


def unique_input_scores(tasks, task_rows):
    by_id = {row['id']: row for row in task_rows}
    if len(by_id) != len(task_rows) or set(by_id) != {task['id'] for task in tasks}:
        raise ValueError('Distinct-input scoring has incomplete task coverage')
    groups = defaultdict(list)
    for task in tasks:
        key = json.dumps({'query': task['query'], 'query_text': task['query_text']}, sort_keys=True)
        groups[key].append(by_id[task['id']]['scores'])
    methods = list(task_rows[0]['scores']) if task_rows else []
    return {'unique_input_group_count': len(groups),
            'raw_mean_of_input_group_means': {
                method: sum(sum(row[method] for row in group) / len(group)
                            for group in groups.values()) / len(groups) for method in methods}}


def evaluate(tasks, predictions, adapter, traces):
    from code_metrics import WEIGHTS, score_expected, summarize
    methods = list(predictions)
    task_ids = [task['id'] for task in tasks]
    if len(set(task_ids)) != len(task_ids) or any(set(values) != set(task_ids) for values in predictions.values()):
        raise ValueError('Scoring does not cover the complete frozen task inventory')
    trace_by_id = {trace['id']: trace for trace in traces}
    task_rows, target_rows = [], []
    by_operation = defaultdict(lambda: defaultdict(list))
    coverage = Counter()
    unique_targets = set()
    for task in tasks:
        task_id, operation = task['id'], task['query']['op']
        wanted = expected_ids(task['expected'])
        mapped = [sid for sid in wanted if sid in adapter.sid_to_nodes]
        unique_targets.update(wanted)
        status = 'empty_expected_set' if not wanted else 'all_targets_mapped' if len(mapped) == len(wanted) else 'some_targets_mapped' if mapped else 'no_targets_mapped'
        coverage[status] += 1
        scores = {method: score_expected(task['expected'], values[task_id])['score'] for method, values in predictions.items()}
        for method, value in scores.items():
            by_operation[operation][method].append(value)
        trace = trace_by_id[task_id]
        row = {'id': task_id, 'category': task['category'], 'operation': operation,
               'expected': task['expected'], 'scores': scores, 'posthoc_target_coverage': status,
               'expected_target_count': len(wanted), 'mapped_expected_target_count': len(mapped),
               'adapter_query_status': trace['specification']['status'],
               'adapter_candidate_count': len(trace['candidate_node_ids']),
               'adapter_unmapped_top5_node_count': len(trace['unmapped_top5_nodes'])}
        task_rows.append(row)
        for sid in wanted:
            target_rows.append({'task_id': task_id, 'stable_id': sid, 'native_index_nodes': adapter.sid_to_nodes.get(sid, []),
                                'in_top5': {method: sid in values[task_id] for method, values in predictions.items()}})
    pairs = {}
    for left, right in itertools.combinations(methods, 2):
        counts = Counter('left_higher' if row['scores'][left] > row['scores'][right] else 'right_higher' if row['scores'][left] < row['scores'][right] else 'equal' for row in task_rows)
        pairs[left + '__vs__' + right] = {'left': left, 'right': right, **{key: counts[key] for key in ('left_higher', 'right_higher', 'equal')}}
    result = {'quality': {method: summarize(tasks, values) for method, values in predictions.items()},
              'by_operation': {operation: {method: score_summary(values) for method, values in grouped.items()} for operation, grouped in by_operation.items()},
              'paired_scores': pairs,
              'query_status_counts': dict(Counter(trace['specification']['status'] for trace in traces)),
              'empty_adapter_results': sum(not trace['top5'] for trace in traces),
              'tasks_with_unmapped_top5_nodes': sum(bool(trace['unmapped_top5_nodes']) for trace in traces),
              'unmapped_top5_node_occurrences': sum(len(trace['unmapped_top5_nodes']) for trace in traces),
              'posthoc_target_coverage': {'tasks_by_coverage': dict(coverage), 'target_instances': len(target_rows),
                                         'mapped_target_instances': sum(bool(row['native_index_nodes']) for row in target_rows),
                                         'unique_expected_ids': len(unique_targets),
                                         'unique_expected_ids_mapped': sum(sid in adapter.sid_to_nodes for sid in unique_targets),
                                         'tasks_requiring_more_than_five_ids': sum(len(expected_ids(task['expected'])) > 5 for task in tasks)},
              'duplicate_inputs': duplicate_audit(tasks),
              'direct_identifier_lookup_tasks': sum(task['query']['op'] == 'lookup' and not task['query'].get('bare_name') for task in tasks),
              'categories_without_weight': dict(Counter(task['category'] for task in tasks if not WEIGHTS.get(task['category'], 0))),
              'distinct_input_sensitivity': unique_input_scores(tasks, task_rows),
              'task_scores': task_rows}
    return result, target_rows



def save(path, value):
    path = Path(path)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write('\n')


def configure_artifact(root):
    python_root = (Path(root) / 'python').resolve()
    sys.path.insert(0, str(python_root))
    for name in ('code_search', 'code_structural_memory', 'code_metrics'):
        module = importlib.import_module(name)
        if Path(module.__file__).resolve().parent != python_root:
            raise ValueError('A different artifact module is already imported: ' + name)
    return importlib.import_module('code_search').CodeSearch


def reproduce(artifact_root, evidence, output):
    artifact_root, evidence, output = [Path(value).resolve() for value in (artifact_root, evidence, output)]
    manifest = verify_evidence(evidence)
    check_hashes(artifact_root, manifest['artifact_sha256'])
    if not output.is_relative_to(artifact_root / 'outputs') or output == artifact_root / 'outputs':
        raise ValueError('New results must use a new subdirectory of artifact outputs')
    output.mkdir(parents=True, exist_ok=False)
    CodeSearch = configure_artifact(artifact_root)
    graph = load(evidence / 'native-graph.json')
    nodes, edges = parse_graph(graph['nodes'], graph['edges'])
    documents = load(artifact_root / 'data/code/documents.json')
    metadata = [{key: item[key] for key in ('id', 'sourcePath', 'definitionLine')} for item in documents]
    source = artifact_root / 'data/code/source'
    adapter = GraphAdapter(nodes, edges, metadata, source)
    engine = CodeSearch(documents, load(artifact_root / 'data/code/projection.json'), source)
    queries = load(evidence / 'queries.json')
    if any(set(query) != {'id', 'query', 'query_text'} for query in queries):
        raise ValueError('Retrieval query contains fields outside the label-free interface')
    if len({query['id'] for query in queries}) != len(queries):
        raise ValueError('Duplicate query identifier')
    predictions = {'imca_fresh_source': {}, 'bm25': {}, METHOD: {}}
    traces = []
    connection = open_graph(nodes, edges)
    try:
        for query in queries:
            route = engine.route(query['query'], query['query_text'], dense_order=None)
            predictions['imca_fresh_source'][query['id']] = top_ids(route)
            predictions['bm25'][query['id']] = lexical_ids(engine, query['query_text'])
            trace = adapter.predict(query)
            sql, arguments = adapter.sql(trace['specification'])
            actual = [row[0] for row in connection.execute(sql, arguments)]
            if actual != trace['candidate_node_ids']:
                raise ValueError('Independent SQL query mismatch: ' + query['id'])
            predictions[METHOD][query['id']] = trace['top5']
            traces.append(trace)
    finally:
        connection.close()
    save(output / 'predictions.json', predictions)
    frozen_hash = digest(output / 'predictions.json')
    save(output / 'mapping.json', adapter.mapping_audit())
    save(output / 'traces.json', traces)
    if predictions != load(evidence / 'predictions.json'):
        raise ValueError('Recomputed rankings differ from the preserved experiment')
    native = check_native_validation(load(evidence / 'native-validation.json'), traces)
    tasks = load(artifact_root / 'data/code/tasks.json')
    if query_inputs(tasks) != queries:
        raise ValueError('Scoring tasks differ from frozen label-free queries')
    scores, targets = evaluate(tasks, predictions, adapter, traces)
    expected = load(evidence / 'retrieval-summary.json')
    if {key: scores[key] for key in expected} != expected:
        raise ValueError('Recomputed summary differs from the preserved experiment')
    if frozen_hash != digest(output / 'predictions.json'):
        raise ValueError('Predictions changed during scoring')
    check_hashes(artifact_root, manifest['artifact_sha256'])
    verify_evidence(evidence)
    save(output / 'target-scores.json', targets)
    result = {'status': 'all_retrieval_predictions_and_scores_reproduced',
              'scope': 'LongMemCode development retrieval on one FastAPI snapshot, not agent repair',
              'tasks': len(queries), 'rankings_saved_before_scoring': True,
              'recorded_dense_orders_used': False, 'model_calls': 0, 'native_tool_calls': 0,
              'independent_sql_queries_matched': len(traces), 'recorded_native_validation': native,
              'prediction_sha256': frozen_hash, **scores}
    save(output / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description='Recompute all 425 development-task rankings and scores offline. '
        'Uses released IMCA inputs and a frozen native graph export. No model, Docker or native-service calls. '
        'This does not rebuild Codebase-Memory or rerun agent repairs.')
    parser.add_argument('--artifact-root', type=Path, default=Path(__file__).resolve().parents[1],
                        help='IMCA repository root containing python/ and data/code/')
    parser.add_argument('--evidence', type=Path, default=EVIDENCE,
                        help='Directory containing the pinned evidence manifest and JSON inputs')
    parser.add_argument('--output', type=Path,
                        help='New subdirectory of repository outputs/; existing directories are never overwritten')
    args = parser.parse_args()
    output = args.output or args.artifact_root / 'outputs/memory-comparison' / ('retrieval-' + uuid.uuid4().hex[:12])
    result = reproduce(args.artifact_root, args.evidence, output)
    print(json.dumps({key: result[key] for key in ('status', 'tasks', 'quality', 'model_calls')}, indent=2))
    print('Saved new output to ' + str(output))


if __name__ == '__main__':
    main()

