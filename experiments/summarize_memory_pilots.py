import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from compare_memory_retrieval import EVIDENCE, load, save, verify_evidence


def response_values(raw):
    content = raw.decode('utf-8')
    if content.lstrip().startswith('{'):
        return [json.loads(content)]
    values = []
    pending = []
    for line in [*content.splitlines(), '']:
        if line.startswith('data:'):
            pending.append(line[5:].lstrip(' '))
        elif not line and pending:
            data = '\n'.join(pending)
            pending = []
            if data.strip() != '[DONE]':
                values.append(json.loads(data))
    if not values:
        raise ValueError('The recorded response has no completion events')
    return values


def response_metadata(raw):
    finishes = []
    text_characters = reasoning_characters = tool_fragments = 0
    usage = None
    for value in response_values(raw):
        if isinstance(value.get('usage'), dict):
            usage = value['usage']
        for choice in value.get('choices', []):
            if choice.get('index', 0) != 0:
                raise ValueError('Unexpected multiple-choice model response')
            if choice.get('finish_reason'):
                finishes.append(choice['finish_reason'])
            delta = choice.get('delta', choice.get('message', {}))
            text_characters += len(delta.get('content') or '')
            reasoning_characters += len(delta.get('reasoning_content') or '')
            tool_fragments += len(delta.get('tool_calls') or [])
    return {'finish_reasons': finishes, 'visible_text_characters': text_characters,
            'reasoning_characters': reasoning_characters, 'tool_call_fragments': tool_fragments, 'usage': usage}


def step_warning(request):
    for message in request.get('messages', []):
        if message.get('role') != 'assistant' or not isinstance(message.get('content'), str):
            continue
        text = message['content']
        if ('CRITICAL - MAXIMUM STEPS REACHED' in text
                and 'Tools are disabled until next user input' in text):
            return True
    return False


def terminal_diagnosis(metadata, warning, timed_out):
    if timed_out:
        return 'agent_wall_time_limit'
    if 'length' in metadata['finish_reasons']:
        usage = metadata.get('usage') or {}
        reasoning = usage.get('completion_tokens_details', {}).get('reasoning_tokens')
        if (metadata['visible_text_characters'] == 0 and metadata['tool_call_fragments'] == 0
                and type(reasoning) is int and reasoning > 0 and reasoning == usage.get('completion_tokens')):
            return 'provider_output_limit_reasoning_only'
        return 'provider_output_length_limit'
    if warning and metadata['finish_reasons'] == ['stop']:
        return 'client_step_limit_summary'
    return 'no_specific_limit_proven_by_terminal_evidence'



def usage_totals(calls):
    result = {}
    for name in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
        values = [(call.get('usage') or {}).get(name) for call in calls]
        known = [value for value in values if type(value) is int and value >= 0]
        result[name] = sum(known) if len(known) == len(calls) else None
        result['known_' + name] = sum(known)
    result['calls_without_reported_usage'] = sum(call.get('usage') is None for call in calls)
    result['financial_cost_estimated'] = False
    return result


def attempt_summary(row):
    calls = row['calls']
    if not calls or [call['number'] for call in calls] != list(range(1, len(calls) + 1)):
        raise ValueError('Model request numbers are incomplete')
    if len(calls) > row['limits']['max_forwards']:
        raise ValueError('The recorded attempt exceeded its request cap')
    evaluation = row['evaluation']
    if evaluation is not None:
        if evaluation['tests_executed'] and not row['patch_bytes']:
            raise ValueError('An empty patch cannot have executed repair tests')
        if evaluation['resolved'] and not evaluation['tests_executed']:
            raise ValueError('A resolved result requires executed tests')
    statuses = Counter(str(call['http_status']) if call['http_status'] is not None else 'no_status' for call in calls)
    terminal = row['terminal']
    if row['execution_outcome'] == 'provider_or_transport_failure':
        cause = 'connection_interrupted'
    elif row['execution_outcome'] == 'provider_failure':
        cause = 'provider_interrupted'
    elif terminal is None:
        cause = 'no_terminal_response_recorded'
    else:
        cause = terminal_diagnosis(terminal, row['last_request_contains_client_step_warning'],
                                  row['wall_time_limit_reached'])
    outcome = ('not_evaluated' if evaluation is None else 'resolved' if evaluation['resolved']
               else 'empty_patch' if not row['patch_bytes'] else 'unresolved_patch' if evaluation['tests_executed']
               else 'evaluation_not_executed')
    return {'attempt_id': row['attempt_id'], 'condition': row['condition'],
            'forward_attempts': len(calls), 'http_status_counts': dict(statuses),
            'patch_bytes': row['patch_bytes'], 'evaluation_outcome': outcome,
            'tests_executed': evaluation['tests_executed'] if evaluation else False,
            'terminal_condition': cause, 'task_tool_calls': row['task_tool_calls'],
            'memory_tool_calls': row['memory_tool_calls'],
            'provider_usage': usage_totals(calls)}


def summarize(records):
    grouped = defaultdict(list)
    seen = set()
    for row in records['attempts']:
        if row['attempt_id'] in seen:
            raise ValueError('An agent attempt was counted twice')
        seen.add(row['attempt_id'])
        grouped[(row['track'], row['instance_id'])].append(attempt_summary(row))
    blocks = [{'track': key[0], 'instance_id': key[1], 'independent_tasks': 1,
               'agent_attempts': len(rows), 'forward_attempts': sum(row['forward_attempts'] for row in rows),
               'attempts': rows} for key, rows in grouped.items()]
    return {'scope': 'Development attempts in separate memory tracks; not an estimate of comparative repair performance',
            'independent_tasks': len({key[1] for key in grouped}), 'agent_attempts': len(seen),
            'recorded_model_forwards': sum(row['forward_attempts'] for block in blocks for row in block['attempts']),
            'blocks': blocks, 'memory_benefit_established': False,
            'model_calls_during_summary': 0}


def main():
    parser = argparse.ArgumentParser(description='Summarize all seven retained pilot attempts offline. '
        'Uses per-request metadata, not raw model conversations. Does not rerun repairs or execute benchmark tests. '
        'Missing usage remains unknown, and the two development tasks stay in separate tracks.')
    parser.add_argument('--evidence', type=Path, default=EVIDENCE)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    verify_evidence(args.evidence)
    result = summarize(load(args.evidence / 'agent-pilots.json'))
    if args.output:
        root = Path(__file__).resolve().parents[1] / 'outputs'
        output = args.output.resolve()
        if output == root or not output.is_relative_to(root):
            raise ValueError('New summary must be inside repository outputs')
        output.parent.mkdir(parents=True, exist_ok=True)
        save(output, result)
    verify_evidence(args.evidence)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

