import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from memory_graph_adapter import GraphAdapter, parse_graph, table_rows
HERE = Path(__file__).resolve().parent


class GraphAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=HERE)
        self.root = Path(self.temporary.name)
        (self.root / 'fastapi').mkdir()
        (self.root / 'fastapi/demo.py').write_text('class A:\n    def run(self): return 1\n\ndef call():\n    return A().run()\nvalue = 1\n\nclass B: pass\n', encoding='utf-8')
        declarations = [(1, 'File', 'demo.py', 0), (2, 'Module', 'fastapi/demo.py', 1),
                        (3, 'Class', 'A', 1), (4, 'Method', 'run', 2),
                        (5, 'Function', 'call', 4), (6, 'Variable', 'value', 6), (7, 'Class', 'B', 8)]
        self.nodes = {key: {'id': key, 'label': label, 'name': name, 'qualified_name': 'native.' + str(key) + '.' + name,
                           'file_path': 'fastapi/demo.py', 'start_line': line, 'end_line': max(line, 8)}
                      for key, label, name, line in declarations}
        self.nodes[4]['qualified_name'] = 'native.A.run'
        self.edges = [(1, 'DEFINES', 3), (1, 'DEFINES', 4), (1, 'DEFINES', 5),
                      (3, 'DEFINES_METHOD', 4), (5, 'CALLS', 4), (3, 'INHERITS', 7)]
        self.ids = {1: 'file:demo.py', 2: 'fastapi `fastapi.demo`/__init__:',
                    3: 'fastapi `fastapi.demo`/A#', 4: 'fastapi `fastapi.demo`/A#run().',
                    5: 'fastapi `fastapi.demo`/call().', 6: 'fastapi `fastapi.demo`/value.',
                    7: 'fastapi `fastapi.demo`/B#'}
        self.metadata = [{'id': self.ids[key], 'sourcePath': 'fastapi/demo.py',
                          'definitionLine': None if label == 'File' else line}
                         for key, label, name, line in declarations]
        self.adapter = GraphAdapter(self.nodes, self.edges, self.metadata, self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def task(self, **query):
        return {'id': 'synthetic', 'query': query, 'query_text': 'same information'}

    def test_mapping_uses_source_location_and_kind(self):
        self.assertEqual(self.adapter.node_to_sid, self.ids)

    def test_lookup_forms(self):
        queries = [(dict(op='lookup', bare_name=True, kind='struct', name='A'), [self.ids[3]]),
                   (dict(op='lookup', bare_name=True, name='A#run'), [self.ids[4]]),
                   (dict(op='lookup', bare_name=False, name=self.ids[2]), [self.ids[2]]),
                   (dict(op='lookup', bare_name=False, name='not-in-index'), [])]
        for query, wanted in queries:
            with self.subTest(query=query):
                self.assertEqual(self.adapter.predict(self.task(**query))['top5'], wanted)

    def test_relations_keep_their_directions(self):
        queries = [(dict(op='callers', sym_stable_id=self.ids[4]), [self.ids[5]]),
                   (dict(op='callees', sym_stable_id=self.ids[5]), [self.ids[4]]),
                   (dict(op='contained_by', sym_stable_id=self.ids[3]), [self.ids[4]]),
                   (dict(op='implementors', sym_stable_id=self.ids[7]), [self.ids[3]]),
                   (dict(op='orphans', kind='function'), [self.ids[5]])]
        for query, wanted in queries:
            with self.subTest(query=query):
                self.assertEqual(self.adapter.predict(self.task(**query))['top5'], wanted)

    def test_file_anchor_uses_declared_benchmark_convention(self):
        result = self.adapter.predict(self.task(op='callers', sym_stable_id='file:demo.py'))
        self.assertIn(self.ids[3], result['top5'])
        self.assertNotIn(self.ids[6], result['top5'])

    def test_repeated_edges_do_not_repeat_candidates(self):
        adapter = GraphAdapter(self.nodes, self.edges + [(5, 'USAGE', 4)], self.metadata, self.root)
        self.assertEqual(adapter.predict(self.task(op='callers', sym_stable_id=self.ids[4]))['candidate_node_ids'], [5])

    def test_answer_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            self.adapter.predict(dict(self.task(op='orphans'), expected=self.ids[5]))
        with self.assertRaises(ValueError):
            self.adapter.predict(self.task(op='lookup', expected=self.ids[3]))
        with self.assertRaises(ValueError):
            GraphAdapter(self.nodes, self.edges, [dict(self.metadata[0], expected=True)], self.root)

    def test_task_name_does_not_change_retrieval(self):
        first = self.task(op='orphans', kind='function')
        self.assertEqual(self.adapter.predict(first)['top5'], self.adapter.predict(dict(first, id='another-target'))['top5'])

    def test_ambiguous_mapping_is_retained_as_unmapped(self):
        duplicate = dict(self.metadata[2], id='alias `fastapi.demo`/A#')
        adapter = GraphAdapter(self.nodes, self.edges, self.metadata + [duplicate], self.root)
        result = adapter.predict(self.task(op='lookup', bare_name=True, kind='struct', name='A'))
        self.assertTrue(result['top5'][0].startswith('unmapped-native:'))
        self.assertEqual(result['unmapped_top5_nodes'], [3])

    def test_decorated_start_maps_to_definition_line(self):
        (self.root / 'fastapi/decorated.py').write_text('@decorate\ndef f(): pass\n', encoding='utf-8')
        nodes = {1: {'id': 1, 'label': 'Function', 'name': 'f', 'qualified_name': 'native.f',
                     'file_path': 'fastapi/decorated.py', 'start_line': 1, 'end_line': 2}}
        metadata = [{'id': 'fastapi `fastapi.decorated`/f().', 'sourcePath': 'fastapi/decorated.py', 'definitionLine': 2}]
        self.assertEqual(GraphAdapter(nodes, [], metadata, self.root).node_to_sid[1], metadata[0]['id'])

    def test_unmapped_nodes_keep_top_five_positions(self):
        nodes = {i: {'id': i, 'label': 'Function', 'name': 'f' + str(i), 'qualified_name': 'native.' + str(i),
                     'file_path': 'fastapi/absent.py', 'start_line': i, 'end_line': i} for i in range(1, 7)}
        metadata = [{'id': 'fastapi `fastapi.absent`/f6().', 'sourcePath': 'fastapi/absent.py', 'definitionLine': 6}]
        result = GraphAdapter(nodes, [], metadata, self.root).predict(self.task(op='orphans', kind='function'))
        self.assertEqual(result['top5_node_ids'], [1, 2, 3, 4, 5])
        self.assertNotIn(metadata[0]['id'], result['top5'])

    def test_source_path_escape_is_rejected(self):
        with self.assertRaises(ValueError):
            self.adapter.predict(self.task(op='file_symbols', file_path='../outside.py'))

    def test_independent_sql_matches_all_operations(self):
        connection = sqlite3.connect(':memory:')
        connection.execute('CREATE TABLE nodes(id INTEGER,label TEXT,name TEXT,qualified_name TEXT,file_path TEXT)')
        connection.execute('CREATE TABLE edges(source_id INTEGER,type TEXT,target_id INTEGER)')
        connection.executemany('INSERT INTO nodes VALUES(?,?,?,?,?)',
                               [(n['id'], n['label'], n['name'], n['qualified_name'], n['file_path']) for n in self.nodes.values()])
        connection.executemany('INSERT INTO edges VALUES(?,?,?)', self.edges)
        queries = [self.task(op='lookup', bare_name=True, name='A#run'),
                   self.task(op='lookup', bare_name=False, name=self.ids[2]),
                   self.task(op='lookup', bare_name=False, name='absent'), self.task(op='file_symbols', file_path='demo.py'),
                   self.task(op='contained_by', sym_stable_id=self.ids[3]), self.task(op='implementors', sym_stable_id=self.ids[7]),
                   self.task(op='callers', sym_stable_id=self.ids[4]), self.task(op='callees', sym_stable_id=self.ids[5]),
                   self.task(op='orphans', kind='function')]
        for task in queries:
            with self.subTest(query=task['query']):
                specification = self.adapter.specification(task)
                sql, arguments = self.adapter.sql(specification)
                self.assertEqual([row[0] for row in connection.execute(sql, arguments)], self.adapter.matching_nodes(specification))
        connection.close()

    def test_lookup_text_is_not_sql_code(self):
        specification = self.adapter.specification(self.task(op='lookup', bare_name=True, name="x' OR 1=1"))
        sql, arguments = self.adapter.sql(specification)
        self.assertNotIn("x' OR 1=1", sql)
        self.assertIn("x' OR 1=1", arguments)


class NativeExportTests(unittest.TestCase):
    def table(self, columns, rows):
        return {'columns': list(columns), 'rows': rows, 'returned': len(rows), 'total': len(rows),
                'total_relation': 'eq', 'has_more': False, 'truncated': False}

    def test_incomplete_exports_are_rejected(self):
        for changed in ({'truncated': True}, {'total': 2}, {'has_more': True}):
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    table_rows(dict(self.table(('id',), [['1']]), **changed), ('id',))

    def test_dangling_edge_is_rejected(self):
        nodes = self.table(('node_id', 'node_labels', 'name', 'qualified_name', 'file_path', 'start_line', 'end_line'),
                           [['1', '["File"]', 'a.py', 'native.a', 'a.py', '0', '0']])
        edges = self.table(('source_id', 'relation', 'target_id'), [['1', 'CALLS', '2']])
        with self.assertRaises(ValueError):
            parse_graph(nodes, edges)


if __name__ == '__main__':
    unittest.main()
