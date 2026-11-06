import ast
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import tokenize
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from summarize_memory_repair_checks import EVIDENCE, load_snapshot, local_file, render_table, summarize


class RepairEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = load_snapshot()

    def test_frozen_evidence_reproduces_two_tasks_five_patches_and_no_complete_pair(self):
        value = summarize(self.snapshot)
        self.assertEqual(value['independent_development_tasks'], 2)
        self.assertEqual(value['recorded_attempts'], 6)
        self.assertEqual(value['saved_patches_tested'], 5)
        self.assertEqual(value['saved_patches_passed'], 5)
        self.assertEqual(value['saved_patches_failed'], 0)
        self.assertEqual(value['complete_three_condition_tasks'], 0)
        self.assertEqual(value, json.loads((EVIDENCE / 'expected-summary.json').read_text()))

    def test_interrupted_empty_attempt_is_unknown_rather_than_a_failed_patch(self):
        value = summarize(self.snapshot)
        requests = next(row for row in value['tasks'] if row['task'] == 'psf__requests-1724')
        self.assertIsNone(requests['conditions']['without-memory']['saved_patch_passed'])
        self.assertEqual(value['missing_patch_after_interruption'], 1)
        self.assertEqual(value['transport_interrupted_attempts'], 2)
        self.assertIn('| psf__requests-1724 | No memory | No patch |', render_table(value))

    def test_patch_from_interrupted_run_can_pass_tests_without_completing_comparison(self):
        django = summarize(self.snapshot)['tasks'][0]
        self.assertTrue(django['conditions']['with-imca']['saved_patch_passed'])
        self.assertFalse(django['complete_three_condition_comparison'])
        self.assertIsNone(django['conditions']['with-imca']['observed_repair'])

    def test_original_source_failure_and_dataset_label_mismatch_are_recomputed(self):
        requests = summarize(self.snapshot)['tasks'][1]
        control = requests['original_source_control']
        self.assertEqual(len(control['failing_tests']), 1)
        self.assertEqual(control['dataset_fail_to_pass_already_passing'], 6)
        self.assertEqual(control['dataset_pass_to_pass_failing'], 1)
        for condition in ('with-imca', 'with-codebase-memory'):
            self.assertTrue(requests['conditions'][condition]['observed_repair'])
            self.assertEqual(requests['conditions'][condition]['newly_failing_tests'], [])

    def test_already_passing_original_source_cannot_count_as_a_repair(self):
        data = deepcopy(self.snapshot)
        original = data['tasks'][1]['original_source_test_status']
        data['tasks'][1]['original_source_test_status'] = {test: 'PASSED' for test in original}
        requests = summarize(data)['tasks'][1]
        self.assertFalse(requests['conditions']['with-imca']['observed_repair'])

    def test_missing_or_skipped_task_tests_are_validation_errors(self):
        for replacement in ('missing', 'SKIPPED'):
            data = deepcopy(self.snapshot)
            status = data['tasks'][0]['conditions']['with-imca']['test_status']
            test = next(iter(status))
            if replacement == 'missing':
                del status[test]
            else:
                status[test] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                summarize(data)

    def test_contradictory_resolution_and_interruption_flags_are_rejected(self):
        data = deepcopy(self.snapshot)
        data['tasks'][0]['conditions']['with-imca']['evaluator_resolved'] = False
        with self.assertRaises(ValueError):
            summarize(data)
        data = deepcopy(self.snapshot)
        data['tasks'][0]['conditions']['with-imca']['eligible_for_uninterrupted_attempt_comparison'] = True
        with self.assertRaises(ValueError):
            summarize(data)

    def test_repeated_task_and_held_out_results_cannot_be_pooled_as_development_tasks(self):
        for mode in ('duplicate', 'held-out'):
            data = deepcopy(self.snapshot)
            if mode == 'duplicate':
                data['tasks'].append(deepcopy(data['tasks'][0]))
            else:
                data['tasks'][0]['held_out'] = True
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                summarize(data)

    def test_modified_patch_bytes_fail_integrity_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'evidence'
            shutil.copytree(EVIDENCE, root)
            patch = next((root / 'patches').glob('*.diff'))
            patch.write_bytes(patch.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                load_snapshot(root)

    def test_evidence_paths_cannot_read_outside_the_snapshot(self):
        for name in ('../outside', '/absolute', 'C:/private', 'folder\\file'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                local_file(EVIDENCE, name)

    def test_new_python_has_no_comments_or_docstrings(self):
        for name in ('summarize_memory_repair_checks.py', Path(__file__).name):
            text = (Path(__file__).parent / name).read_text()
            self.assertFalse(any(token.type == tokenize.COMMENT for token in tokenize.generate_tokens(io.StringIO(text).readline)))
            self.assertFalse(any(ast.get_docstring(node) for node in ast.walk(ast.parse(text))
                if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))))


if __name__ == '__main__':
    unittest.main()
