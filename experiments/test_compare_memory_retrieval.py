import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from compare_memory_retrieval import (
    EVIDENCE, METHOD, check_hashes, check_native_validation, digest, expected_ids,
    load, owned_path, query_inputs, reproduce, save, top_ids, unique_input_scores,
    verify_evidence,
)


HERE = Path(__file__).resolve().parent
ARTIFACT = Path(os.environ.get('IMCA_ARTIFACT_ROOT', HERE.parent)).resolve()


class RetrievalUtilityTests(unittest.TestCase):
    def test_labels_are_not_part_of_query_inputs(self):
        task = {'id': 'a', 'query': {'op': 'lookup', 'name': 'x'}, 'query_text': 'find x',
                'expected': {'kind': 'exact_symbol', 'stable_id': 'answer'}, 'category': 'BugFix'}
        self.assertEqual(set(query_inputs([task])[0]), {'id', 'query', 'query_text'})

    def test_duplicate_task_ids_are_rejected(self):
        task = {'id': 'a', 'query': {}, 'query_text': ''}
        with self.assertRaises(ValueError):
            query_inputs([task, task])

    def test_score_ties_keep_original_corpus_order(self):
        route = {'candidates': [{'id': 'later', 'score': 1, 'corpus_order': 3},
                                {'id': 'earlier', 'score': 1, 'corpus_order': 1}]}
        self.assertEqual(top_ids(route), ['earlier', 'later'])

    def test_signal_contributions_take_precedence_over_display_score(self):
        route = {'candidates': [{'id': 'a', 'score': 999, 'corpus_order': 0,
                                'signals': {'x': {'contribution': 0.1}}},
                               {'id': 'b', 'score': 0, 'corpus_order': 1,
                                'signals': {'x': {'contribution': 0.2}}}]}
        self.assertEqual(top_ids(route), ['b', 'a'])

    def test_only_five_results_are_returned(self):
        route = {'candidates': [{'id': str(i), 'score': 1, 'corpus_order': i} for i in range(7)]}
        self.assertEqual(top_ids(route), ['0', '1', '2', '3', '4'])

    def test_all_expected_target_forms_are_supported(self):
        values = [({'kind': 'exact_symbol', 'stable_id': 'a'}, ['a']),
                  ({'kind': 'in_top_k', 'stable_id': 'b', 'k': 2}, ['b']),
                  ({'kind': 'contains', 'required': ['a', 'a', 'b']}, ['a', 'b']),
                  ({'kind': 'exact_set', 'stable_ids': []}, [])]
        for expected, wanted in values:
            with self.subTest(expected=expected):
                self.assertEqual(expected_ids(expected), wanted)

    def test_unknown_scoring_rule_is_rejected(self):
        with self.assertRaises(ValueError):
            expected_ids({'kind': 'unknown'})

    def test_distinct_inputs_are_weighted_equally_without_dropping_labels(self):
        tasks = [{'id': key, 'query': {'op': 'lookup', 'name': name}, 'query_text': name}
                 for key, name in [('a', 'same'), ('b', 'same'), ('c', 'other')]]
        rows = [{'id': key, 'scores': {'method': score}}
                for key, score in [('a', 1), ('b', 0), ('c', 0)]]
        result = unique_input_scores(tasks, rows)
        self.assertEqual(result['unique_input_group_count'], 2)
        self.assertEqual(result['raw_mean_of_input_group_means']['method'], 0.25)

    def test_incomplete_distinct_input_scores_are_rejected(self):
        with self.assertRaises(ValueError):
            unique_input_scores([{'id': 'a'}], [])

    def test_relative_paths_cannot_leave_their_root(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            for name in ('../outside', '/outside', 'C:/outside', 'C:outside', '..\\outside', '.'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    owned_path(temporary, name)

    def test_checksum_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            root = Path(temporary)
            save(root / 'fixture.json', {'value': 1})
            with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
                check_hashes(root, {'fixture.json': '0' * 64})

    def test_saved_records_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            path = Path(temporary) / 'fixture.json'
            save(path, {'original': True})
            before = digest(path)
            with self.assertRaises(FileExistsError):
                save(path, {})
            self.assertEqual(digest(path), before)

    def test_manifest_cannot_omit_required_evidence(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            save(Path(temporary) / 'manifest.json', {'schema_version': 1, 'files_sha256': {}})
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                verify_evidence(temporary)


class NativeValidationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'query_id': 'q1', 'task_ids': ['a', 'b'],
                      'canonical_node_ids': [1, 2], 'raw_node_ids': [2, 1]}]
        self.traces = [{'id': key, 'candidate_node_ids': [1, 2]} for key in ('a', 'b')]

    def test_raw_order_can_differ_without_changing_candidate_set(self):
        result = check_native_validation(self.rows, self.traces)
        self.assertEqual(result['raw_order_mismatches'], 1)
        self.assertEqual(result['task_queries_matched'], 2)
        self.assertEqual(result['new_native_tool_calls'], 0)

    def test_wrong_candidate_is_not_accepted_as_an_order_difference(self):
        self.rows[0]['raw_node_ids'] = [1, 3]
        with self.assertRaises(ValueError):
            check_native_validation(self.rows, self.traces)

    def test_native_duplicate_candidates_are_rejected(self):
        self.rows[0]['raw_node_ids'] = [1, 1, 2]
        with self.assertRaises(ValueError):
            check_native_validation(self.rows, self.traces)

    def test_incomplete_validation_is_rejected(self):
        self.rows[0]['task_ids'] = ['a']
        with self.assertRaises(ValueError):
            check_native_validation(self.rows, self.traces)

    def test_duplicate_task_coverage_is_rejected(self):
        row = copy.deepcopy(self.rows[0])
        row['query_id'] = 'q2'
        with self.assertRaises(ValueError):
            check_native_validation(self.rows + [row], self.traces)

    def test_duplicate_query_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            check_native_validation(self.rows * 2, self.traces)


class FrozenEvidenceTests(unittest.TestCase):
    def test_released_evidence_checksums(self):
        verify_evidence(EVIDENCE)

    @unittest.skipUnless((ARTIFACT / 'data/code/tasks.json').is_file(), 'Run inside the IMCA artifact')
    def test_all_425_rankings_and_scores_reproduce_from_released_inputs(self):
        outputs = ARTIFACT / 'outputs'
        outputs.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='memory-reproduction-test-', dir=outputs) as temporary:
            output = Path(temporary) / 'run'
            result = reproduce(ARTIFACT, EVIDENCE, output)
            self.assertEqual(result['tasks'], 425)
            self.assertEqual(result['quality']['imca_fresh_source']['passed'], 272)
            self.assertEqual(result['quality']['bm25']['passed'], 142)
            self.assertEqual(result['quality'][METHOD]['passed'], 261)
            self.assertEqual(len(result['task_scores']), 425)
            self.assertEqual(len(load(output / 'target-scores.json')), 824)
            self.assertEqual(result['distinct_input_sensitivity']['unique_input_group_count'], 328)
            self.assertEqual(result['recorded_native_validation']['raw_order_mismatches'], 61)
            self.assertEqual(load(output / 'predictions.json'), load(EVIDENCE / 'predictions.json'))
            with self.assertRaises(FileExistsError):
                reproduce(ARTIFACT, EVIDENCE, output)


if __name__ == '__main__':
    unittest.main()
