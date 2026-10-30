import copy
import json
import unittest

from compare_memory_retrieval import EVIDENCE, load
from summarize_memory_pilots import (
    attempt_summary, response_metadata, response_values, step_warning, summarize,
    terminal_diagnosis, usage_totals,
)


class ResponseTests(unittest.TestCase):
    def metadata(self, finish='stop', content='done', reasoning='', usage=None):
        response = {'choices': [{'index': 0, 'finish_reason': finish,
                    'message': {'content': content, 'reasoning_content': reasoning}}], 'usage': usage}
        return response_metadata(json.dumps(response).encode())

    def test_json_response_and_stream_have_the_same_metadata(self):
        response = {'choices': [{'index': 0, 'finish_reason': 'stop', 'delta': {'content': 'done'}}]}
        plain = json.dumps(response).encode()
        stream = b'data: ' + plain + b'\n\ndata: [DONE]\n\n'
        self.assertEqual(response_metadata(plain), response_metadata(stream))

    def test_stream_without_a_final_blank_line_is_supported(self):
        response = {'choices': [{'index': 0, 'finish_reason': 'stop', 'delta': {}}]}
        self.assertEqual(response_values(b'data: ' + json.dumps(response).encode()), [response])

    def test_empty_response_is_rejected(self):
        with self.assertRaises(ValueError):
            response_values(b'')

    def test_other_response_choices_are_rejected(self):
        with self.assertRaises(ValueError):
            response_metadata(b'{"choices":[{"index":1,"message":{}}]}')

    def test_normal_exit_is_not_a_repair_success(self):
        self.assertEqual(terminal_diagnosis(self.metadata(), False, False),
                         'no_specific_limit_proven_by_terminal_evidence')

    def test_step_warning_requires_the_client_marker_and_assistant_role(self):
        text = 'CRITICAL - MAXIMUM STEPS REACHED. Tools are disabled until next user input'
        self.assertTrue(step_warning({'messages': [{'role': 'assistant', 'content': text}]}))
        self.assertFalse(step_warning({'messages': [{'role': 'user', 'content': text}]}))
        self.assertFalse(step_warning({'messages': [{'role': 'assistant', 'content': 'MAXIMUM STEPS REACHED'}]}))

    def test_step_limit_is_separate_from_output_limit(self):
        self.assertEqual(terminal_diagnosis(self.metadata(), True, False), 'client_step_limit_summary')
        self.assertEqual(terminal_diagnosis(self.metadata(finish='length'), True, False),
                         'provider_output_length_limit')

    def test_reasoning_only_limit_requires_provider_usage_evidence(self):
        usage = {'completion_tokens': 2048, 'completion_tokens_details': {'reasoning_tokens': 2048}}
        meta = self.metadata(finish='length', content='', reasoning='hidden', usage=usage)
        self.assertEqual(terminal_diagnosis(meta, False, False), 'provider_output_limit_reasoning_only')
        meta['usage'] = None
        self.assertEqual(terminal_diagnosis(meta, False, False), 'provider_output_length_limit')

    def test_visible_output_is_not_reasoning_only(self):
        usage = {'completion_tokens': 2048, 'completion_tokens_details': {'reasoning_tokens': 2048}}
        self.assertEqual(terminal_diagnosis(self.metadata(finish='length', usage=usage), False, False),
                         'provider_output_length_limit')

    def test_wall_time_limit_is_not_a_normal_completion(self):
        self.assertEqual(terminal_diagnosis(self.metadata(), True, True), 'agent_wall_time_limit')


class UsageAndAttemptTests(unittest.TestCase):
    def setUp(self):
        self.records = load(EVIDENCE / 'agent-pilots.json')

    def test_missing_usage_is_unknown_not_zero(self):
        result = usage_totals([{'usage': {'prompt_tokens': 7, 'completion_tokens': 3, 'total_tokens': 10}},
                               {'usage': None}])
        self.assertIsNone(result['prompt_tokens'])
        self.assertEqual(result['known_prompt_tokens'], 7)
        self.assertEqual(result['calls_without_reported_usage'], 1)
        self.assertFalse(result['financial_cost_estimated'])

    def test_partial_usage_fields_do_not_create_a_complete_total(self):
        result = usage_totals([{'usage': {'prompt_tokens': 7}}])
        self.assertEqual(result['prompt_tokens'], 7)
        self.assertIsNone(result['completion_tokens'])

    def test_all_seven_attempts_and_both_tasks_are_retained(self):
        result = summarize(self.records)
        self.assertEqual(result['agent_attempts'], 7)
        self.assertEqual(result['independent_tasks'], 2)
        self.assertEqual(result['recorded_model_forwards'], 50)
        self.assertEqual([row['agent_attempts'] for row in result['blocks']], [4, 3])
        self.assertFalse(result['memory_benefit_established'])

    def test_duplicate_attempts_are_rejected(self):
        records = copy.deepcopy(self.records)
        records['attempts'].append(records['attempts'][0])
        with self.assertRaises(ValueError):
            summarize(records)

    def test_missing_request_accounting_is_rejected(self):
        row = copy.deepcopy(self.records['attempts'][0])
        row['calls'].pop(0)
        with self.assertRaises(ValueError):
            attempt_summary(row)

    def test_more_than_authorized_requests_is_rejected(self):
        row = copy.deepcopy(self.records['attempts'][0])
        row['limits']['max_forwards'] = 1
        with self.assertRaises(ValueError):
            attempt_summary(row)

    def test_empty_patch_cannot_be_reported_as_tested(self):
        row = copy.deepcopy(self.records['attempts'][-1])
        row['evaluation']['tests_executed'] = True
        with self.assertRaises(ValueError):
            attempt_summary(row)

    def test_resolved_requires_executed_tests(self):
        row = copy.deepcopy(self.records['attempts'][0])
        row['evaluation']['tests_executed'] = False
        with self.assertRaises(ValueError):
            attempt_summary(row)

    def test_flask_baseline_is_resolved_but_memory_failures_are_not(self):
        rows = summarize(self.records)['blocks'][0]['attempts']
        self.assertEqual(rows[0]['evaluation_outcome'], 'resolved')
        self.assertTrue(rows[0]['tests_executed'])
        self.assertEqual(rows[1]['terminal_condition'], 'connection_interrupted')
        self.assertEqual(rows[2]['terminal_condition'], 'provider_interrupted')
        self.assertEqual(rows[2]['evaluation_outcome'], 'not_evaluated')
        self.assertIsNone(rows[1]['provider_usage']['prompt_tokens'])

    def test_sphinx_stops_are_identified_without_claiming_test_failure(self):
        rows = summarize(self.records)['blocks'][1]['attempts']
        by_condition = {row['condition']: row for row in rows}
        self.assertEqual(by_condition['without-memory']['terminal_condition'], 'client_step_limit_summary')
        self.assertEqual(by_condition['with-codebase-memory']['terminal_condition'], 'client_step_limit_summary')
        self.assertEqual(by_condition['with-imca']['terminal_condition'], 'provider_output_limit_reasoning_only')
        self.assertTrue(all(row['evaluation_outcome'] == 'empty_patch' for row in rows))
        self.assertTrue(all(not row['tests_executed'] for row in rows))
        self.assertEqual({key: row['memory_tool_calls'] for key, row in by_condition.items()},
                         {'without-memory': 0, 'with-codebase-memory': 2, 'with-imca': 1})


if __name__ == '__main__':
    unittest.main()
