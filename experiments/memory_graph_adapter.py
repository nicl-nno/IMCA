import ast
from collections import Counter, defaultdict
import json
from pathlib import Path, PureWindowsPath
import re


_DESCRIPTOR_NAME = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?=[#.:()]|$)")
_METHOD_SUFFIX = re.compile(r"\([^()]*\)\.$")
_PARAMETER_SUFFIX = re.compile(r"\.\([A-Za-z_][A-Za-z0-9_]*\)$")


def display_name(stable_id):
    tail = stable_id.rsplit('/', 1)[-1]
    names = _DESCRIPTOR_NAME.findall(tail)
    return names[-1] if names else tail


def symbol_kind(stable_id):
    if stable_id.startswith('file:'):
        return 'file'
    tail = stable_id.rsplit('/', 1)[-1].strip()
    if _PARAMETER_SUFFIX.search(tail) or (tail.startswith('(') and tail.endswith(')')):
        return 'parameter'
    if _METHOD_SUFFIX.search(tail):
        return 'function'
    if tail.endswith('#'):
        return 'struct'
    if tail.endswith(':'):
        return 'module'
    if tail.endswith('.'):
        return 'term'
    return 'symbol'


LABEL_KINDS = {'File': 'file', 'Module': 'module', 'Class': 'struct', 'Struct': 'struct',
               'Function': 'function', 'Method': 'function', 'Variable': 'term',
               'Field': 'term', 'Constant': 'term'}
RETURN_LABELS = ('File', 'Class', 'Struct', 'Function', 'Method', 'Variable', 'Field', 'Constant')
CALLER_LABELS = ('File', 'Class', 'Struct', 'Function', 'Method')
CALLEE_LABELS = ('Class', 'Struct', 'Function', 'Method')
REFERENCE_EDGES = ('CALLS', 'CALL_REFERENCE', 'USAGE')
IMPLEMENTATION_EDGES = ('INHERITS', 'IMPLEMENTS', 'OVERRIDE')
CONTAINMENT_EDGES = ('DEFINES', 'DEFINES_METHOD')
QUERY_KEYS = frozenset(('op', 'name', 'bare_name', 'kind', 'file_path', 'sym_stable_id'))


def table_rows(value, columns):
    if (value.get('columns') != list(columns) or value.get('has_more') or value.get('truncated')
            or value.get('total_relation') != 'eq' or value.get('returned') != value.get('total')
            or len(value.get('rows', [])) != value.get('total')):
        raise ValueError('Native graph export is incomplete or has an unexpected schema')
    if any(len(row) != len(columns) for row in value['rows']):
        raise ValueError('Native graph row has an unexpected width')
    return [dict(zip(columns, row, strict=True)) for row in value['rows']]


def parse_graph(nodes_payload, edges_payload):
    columns = ('node_id', 'node_labels', 'name', 'qualified_name', 'file_path', 'start_line', 'end_line')
    nodes = {}
    for row in table_rows(nodes_payload, columns):
        key = int(row.pop('node_id'))
        labels = json.loads(row.pop('node_labels'))
        if key in nodes or not isinstance(labels, list) or len(labels) != 1:
            raise ValueError('Native node identity or label is ambiguous')
        nodes[key] = {**row, 'id': key, 'label': labels[0], 'start_line': int(row['start_line']),
                      'end_line': int(row['end_line'])}
    edges = []
    for row in table_rows(edges_payload, ('source_id', 'relation', 'target_id')):
        source, target = int(row['source_id']), int(row['target_id'])
        if source not in nodes or target not in nodes:
            raise ValueError('Native graph contains a dangling exported edge')
        edges.append((source, row['relation'], target))
    if len({node['qualified_name'] for node in nodes.values()}) != len(nodes):
        raise ValueError('Native qualified names are not unique')
    return nodes, edges


def labels_for_kind(kind):
    if not kind or kind == 'symbol':
        return RETURN_LABELS
    kind = 'struct' if kind == 'class' else kind
    return tuple(label for label, mapped in LABEL_KINDS.items() if mapped == kind)


def source_path(value):
    value = str(value).replace('\\', '/')
    parts = Path(value).parts
    if '..' in parts or Path(value).is_absolute() or PureWindowsPath(value).drive:
        raise ValueError('Source path leaves the indexed repository')
    return value.removeprefix('./')


def benchmark_file(value):
    value = source_path(value)
    return value if value.startswith('fastapi/') else 'fastapi/' + value


def native_descriptor(value):
    return value.replace('().', '.').replace('#', '.').rstrip('.')


class GraphAdapter:
    def __init__(self, nodes, edges, metadata, root):
        self.nodes, self.edges = nodes, list(edges)
        self.root = Path(root).resolve()
        self.documents = {}
        by_file = defaultdict(list)
        for item in metadata:
            if set(item) != {'id', 'sourcePath', 'definitionLine'} or item['id'] in self.documents:
                raise ValueError('Only unique source-location metadata may enter identifier mapping')
            self.documents[item['id']] = dict(item)
            by_file[source_path(item['sourcePath'])].append(item)
        declarations = {}
        self.node_to_sid = {}
        self.sid_to_nodes = defaultdict(list)
        self.mapping_rows = []
        for key, node in sorted(nodes.items()):
            path = source_path(node['file_path'])
            kind = LABEL_KINDS.get(node['label'])
            lines = {node['start_line']}
            if kind in ('struct', 'function') and path:
                if path not in declarations:
                    source = (self.root / path).resolve()
                    if not source.is_relative_to(self.root):
                        raise ValueError('Native declaration path leaves the source root')
                    declarations[path] = []
                    if source.is_file():
                        tree = ast.parse(source.read_text(encoding='utf-8'))
                        for declaration in ast.walk(tree):
                            if isinstance(declaration, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                                start = min([declaration.lineno] + [d.lineno for d in declaration.decorator_list])
                                declarations[path].append((declaration.name, start, declaration.lineno))
                lines.update(line for name, start, line in declarations[path]
                             if name == node['name'] and start == node['start_line'])
            candidates = []
            for item in by_file.get(path, []):
                sid = item['id']
                if symbol_kind(sid) != kind:
                    continue
                if kind == 'file' or (item['definitionLine'] in lines and
                                      (kind == 'module' or display_name(sid) == node['name'])):
                    candidates.append(sid)
            if len(candidates) == 1:
                self.node_to_sid[key] = candidates[0]
                self.sid_to_nodes[candidates[0]].append(key)
            self.mapping_rows.append({'node_id': key, 'label': node['label'], 'file_path': path,
                                      'start_line': node['start_line'], 'name': node['name'],
                                      'status': 'mapped' if len(candidates) == 1 else 'ambiguous' if candidates else 'unmapped',
                                      'candidate_stable_ids': candidates})
        self.incoming = defaultdict(list)
        self.outgoing = defaultdict(list)
        for source, relation, target in self.edges:
            self.outgoing[source].append((relation, target))
            self.incoming[target].append((relation, source))

    def mapping_audit(self):
        return {'native_nodes': len(self.nodes), 'native_edges': len(self.edges),
                'status_counts': dict(Counter(row['status'] for row in self.mapping_rows)),
                'mapped_document_ids': len(set(self.node_to_sid.values())),
                'status_by_label': {label: dict(Counter(row['status'] for row in self.mapping_rows if row['label'] == label))
                                    for label in sorted({node['label'] for node in self.nodes.values()})},
                'rows': self.mapping_rows}

    def specification(self, task):
        if set(task) != {'id', 'query', 'query_text'} or not set(task['query']).issubset(QUERY_KEYS):
            raise ValueError('Only the frozen label-free query interface is accepted')
        query = task['query']
        operation = query.get('op')
        specification = {'operation': operation, 'labels': (), 'status': 'supported', 'mode': 'empty'}
        if operation == 'lookup':
            labels = labels_for_kind(query.get('kind'))
            if not query.get('bare_name'):
                ids = tuple(self.sid_to_nodes.get(query.get('name', ''), ()))
                specification.update(mode='ids', ids=ids, labels=tuple(LABEL_KINDS),
                                     status='supported' if ids else 'query_anchor_not_mapped')
            else:
                name = str(query.get('name', '')).strip()
                specification.update(mode='name', name=name, descriptor=native_descriptor(name), labels=labels,
                                     status='supported' if labels else 'unsupported_symbol_kind')
        elif operation == 'file_symbols':
            specification.update(mode='file', file=benchmark_file(query.get('file_path', '')), labels=RETURN_LABELS)
        elif operation in ('callers', 'callees', 'implementors', 'contained_by'):
            sid = query.get('sym_stable_id', '')
            ids = tuple(self.sid_to_nodes.get(sid, ()))
            if operation == 'callers' and sid.startswith('file:'):
                specification.update(mode='file', file=benchmark_file(sid.removeprefix('file:')), labels=CALLER_LABELS)
            else:
                labels = CALLER_LABELS if operation == 'callers' else CALLEE_LABELS if operation == 'callees' else RETURN_LABELS
                relations = REFERENCE_EDGES + IMPLEMENTATION_EDGES if operation == 'callers' else REFERENCE_EDGES if operation == 'callees' else IMPLEMENTATION_EDGES if operation == 'implementors' else CONTAINMENT_EDGES
                specification.update(mode='incoming' if operation in ('callers', 'implementors') else 'outgoing',
                                     ids=ids, labels=labels, relations=relations,
                                     status='supported' if ids else 'query_anchor_not_mapped')
        elif operation == 'orphans':
            labels = labels_for_kind(query.get('kind', 'function'))
            specification.update(mode='orphans', labels=labels,
                                 status='supported' if labels else 'unsupported_symbol_kind')
        else:
            specification.update(status='unsupported_operation')
        return specification

    def matching_nodes(self, specification):
        mode, labels = specification['mode'], specification['labels']
        selected = []
        for key, node in self.nodes.items():
            if node['label'] not in labels:
                continue
            if mode == 'ids':
                matched = key in specification['ids']
            elif mode == 'name':
                descriptor = specification['descriptor']
                matched = (node['name'] == specification['name'] if '.' not in descriptor
                           else node['qualified_name'].endswith('.' + descriptor))
            elif mode == 'file':
                matched = node['file_path'] == specification['file']
            elif mode == 'incoming':
                matched = any(relation in specification['relations'] and other in specification['ids']
                              for relation, other in self.outgoing[key])
            elif mode == 'outgoing':
                matched = any(relation in specification['relations'] and other in specification['ids']
                              for relation, other in self.incoming[key])
            elif mode == 'orphans':
                matched = not any(relation == 'CALLS' for relation, other in self.incoming[key])
            else:
                matched = False
            if matched:
                selected.append(key)
        return sorted(selected, key=lambda key: self.nodes[key]['qualified_name'])

    def sql(self, specification):
        mode = specification['mode']
        labels = specification['labels']
        if not labels or mode == 'empty':
            return 'SELECT id FROM nodes WHERE 0', []
        arguments = list(labels)
        where = ['n.label IN (' + ','.join('?' for _ in labels) + ')']
        join = ''
        if mode == 'ids':
            ids = specification['ids']
            where.append('n.id IN (' + ','.join('?' for _ in ids) + ')' if ids else '0')
            arguments.extend(ids)
        elif mode == 'name':
            descriptor = specification['descriptor']
            if '.' not in descriptor:
                where.append('n.name = ?')
                arguments.append(specification['name'])
            else:
                suffix = '.' + descriptor
                where.append('substr(n.qualified_name, -?) = ?')
                arguments.extend((len(suffix), suffix))
        elif mode == 'file':
            where.append('n.file_path = ?')
            arguments.append(specification['file'])
        elif mode in ('incoming', 'outgoing'):
            join = ' JOIN edges r ON ' + ('r.source_id=n.id' if mode == 'incoming' else 'r.target_id=n.id')
            anchor = 'r.target_id' if mode == 'incoming' else 'r.source_id'
            ids = specification['ids']
            where.append(anchor + ' IN (' + ','.join('?' for _ in ids) + ')' if ids else '0')
            arguments.extend(ids)
            relations = specification['relations']
            where.append('r.type IN (' + ','.join('?' for _ in relations) + ')')
            arguments.extend(relations)
        elif mode == 'orphans':
            where.append("NOT EXISTS (SELECT 1 FROM edges e WHERE e.target_id=n.id AND e.type='CALLS')")
        else:
            raise ValueError('Unsupported query specification')
        return 'SELECT DISTINCT n.id FROM nodes n' + join + ' WHERE ' + ' AND '.join(where) + ' ORDER BY n.qualified_name COLLATE BINARY', arguments

    def predict(self, task):
        specification = self.specification(task)
        candidates = self.matching_nodes(specification)
        selected = candidates[:5]
        returned = [self.node_to_sid.get(key, 'unmapped-native:' + self.nodes[key]['qualified_name']) for key in selected]
        return {'id': task['id'], 'specification': specification, 'candidate_node_ids': candidates,
                'top5_node_ids': selected, 'top5': returned, 'unmapped_top5_nodes': [key for key in selected if key not in self.node_to_sid]}
