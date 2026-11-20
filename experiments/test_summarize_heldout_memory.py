import ast
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tokenize
import unittest

import summarize_heldout_memory as analysis


class HeldoutSummaryTests(unittest.TestCase):
    def inputs(self):
        folder = analysis.DEFAULT_EVIDENCE
        return analysis.read_json(folder / 'results.json'), analysis.read_json(folder / 'protocol.json')

    def task(self, data, prefix='pytest'):
        return next(row for row in data['tasks'] if row['task'].startswith(prefix))

    def test_published_summary_and_patch_checksums_reproduce(self):
        result = analysis.reproduce(analysis.DEFAULT_EVIDENCE)
        self.assertEqual(result['planned_tasks'], 5)
        self.assertEqual(result['evaluated_tasks'], 3)
        self.assertEqual(result['original_attempts'], 9)
        self.assertEqual(result['model_forward_attempts'], 151)
        self.assertEqual(result['passing_nonempty_patches'], 8)
        self.assertEqual(result['uninterrupted_paired_observed_repairs'], {'without-memory': 1, 'with-imca': 2, 'with-codebase-memory': 2})
        self.assertEqual(result['imca_only_saved_artifact_repairs'], [])
        self.assertEqual(result['codebase_memory_only_saved_artifact_repairs'], [])

    def test_interrupted_passing_patch_stays_outside_paired_subset(self):
        data, policy = self.inputs()
        result = analysis.summarize(data, policy)
        self.assertNotIn('astropy__astropy-8872', result['tasks_with_three_uninterrupted_attempts'])
        self.assertEqual(result['passing_artifacts']['without-memory'], 2)
        self.assertEqual(result['uninterrupted_paired_passing_artifacts']['without-memory'], 1)

    def test_already_passing_source_does_not_count_as_a_repair(self):
        data, policy = self.inputs()
        task = self.task(data)
        original = task['original_source']
        original['tests'] = dict.fromkeys(original['tests'], 'PASSED')
        original['outcome'] = 'resolved'
        task['conditions']['without-memory']['tests'] = copy.deepcopy(original['tests'])
        result = analysis.summarize(data, policy)
        self.assertEqual(result['observed_repairs_from_saved_artifacts']['with-imca'], 2)
        self.assertEqual(result['passing_artifacts']['with-imca'], 3)

    def test_new_preserved_failure_is_an_unresolved_patch(self):
        data, policy = self.inputs()
        task = self.task(data)
        row = task['conditions']['with-imca']
        row['tests'][task['preserved_tests'][0]] = 'FAILED'
        row['artifact_outcome'] = 'unresolved'
        result = analysis.summarize(data, policy)
        self.assertEqual(result['passing_artifacts']['with-imca'], 2)
        self.assertEqual(result['codebase_memory_only_saved_artifact_repairs'], [task['task']])

    def test_false_success_claim_is_rejected(self):
        data, policy = self.inputs()
        task = self.task(data)
        task['conditions']['with-imca']['tests'][task['required_tests'][0]] = 'FAILED'
        with self.assertRaisesRegex(ValueError, 'artifact outcome'):
            analysis.summarize(data, policy)

    def test_missing_or_skipped_test_is_not_a_failed_repair(self):
        for status in (None, 'SKIPPED'):
            data, policy = self.inputs()
            task = self.task(data)
            tests = task['conditions']['with-imca']['tests']
            if status is None:
                del tests[task['required_tests'][0]]
            else:
                tests[task['required_tests'][0]] = status
            with self.assertRaisesRegex(ValueError, 'indeterminate'):
                analysis.summarize(data, policy)

    def test_unavailable_task_cannot_be_scored_or_hidden(self):
        data, policy = self.inputs()
        task = next(row for row in data['tasks'] if row['status'] == 'preparation_unavailable')
        task['repair_outcome'] = False
        with self.assertRaisesRegex(ValueError, 'unavailable task'):
            analysis.summarize(data, policy)
        data, policy = self.inputs()
        data['tasks'].pop()
        with self.assertRaisesRegex(ValueError, 'inventory'):
            analysis.summarize(data, policy)

    def test_model_request_allowance_is_enforced(self):
        data, policy = self.inputs()
        self.task(data)['conditions']['with-imca']['model_forward_attempts'] = 21
        with self.assertRaisesRegex(ValueError, 'request allowance'):
            analysis.summarize(data, policy)

    def test_missing_condition_or_changed_original_status_is_rejected(self):
        data, policy = self.inputs()
        del self.task(data)['conditions']['with-codebase-memory']
        with self.assertRaisesRegex(ValueError, 'all three'):
            analysis.summarize(data, policy)
        data, policy = self.inputs()
        self.task(data)['original_source']['outcome'] = 'resolved'
        with self.assertRaisesRegex(ValueError, 'original-source outcome'):
            analysis.summarize(data, policy)

    def test_modified_patch_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'evidence'
            shutil.copytree(analysis.DEFAULT_EVIDENCE, folder)
            patch = next((folder / 'patches').glob('*.diff'))
            patch.write_bytes(patch.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                analysis.verify_files(folder)

    def test_manifest_paths_cannot_escape_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            for name in ('../outside.txt', '/outside.txt', 'Z:/outside.txt', '..\\outside.txt'):
                with self.assertRaises(ValueError):
                    analysis.contained_file(Path(temporary), name)

    def test_cli_runs_without_project_imports_or_current_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run([sys.executable, '-I', '-B', str(Path(analysis.__file__))],
                cwd=temporary, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), analysis.read_json(analysis.DEFAULT_EVIDENCE / 'expected-summary.json'))

    def test_analysis_python_has_no_comments_or_docstrings(self):
        for path in (Path(analysis.__file__), Path(__file__)):
            source = path.read_text(encoding='utf-8')
            self.assertFalse(any(token.type == tokenize.COMMENT for token in tokenize.generate_tokens(io.StringIO(source).readline)))
            self.assertFalse(any(ast.get_docstring(node) for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))))


if __name__ == '__main__':
    unittest.main()
