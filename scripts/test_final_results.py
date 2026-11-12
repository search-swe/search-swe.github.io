"""Current-archive edge cases: exact selection, native receipts, timing and anonymous calls."""
import copy
import csv
import tempfile
import unittest
from pathlib import Path

from import_final_results import MODELS, coding_provider, coding_session, coding_time, entry_model, selected_rows, session_usage
from import_results import export_trajectory, read


class CurrentArchiveTests(unittest.TestCase):
    def test_only_requested_models_and_complete_fixed_task_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [{'task': t, 'model': m} for t in ['one', 'two'] for m in MODELS]
            rows.append({'task': 'one', 'model': 'incomplete-other-model'})
            def save():
                with (root / 'INDEX.csv').open('w') as f:
                    writer = csv.DictWriter(f, ['task', 'model'])
                    writer.writeheader()
                    writer.writerows(rows)
            save()
            self.assertEqual(len(selected_rows(root, ['one', 'two'])), 2 * len(MODELS))
            rows.pop(0)
            save()
            with self.assertRaisesRegex(ValueError, 'complete task catalog'):
                selected_rows(root, ['one', 'two'])
            rows.append(rows[0])
            save()
            with self.assertRaises(ValueError):
                selected_rows(root, ['one', 'two'])

    def test_opus_substitution_is_limited_to_the_authorized_task_and_column(self):
        row = {'task': 'constrained-molecular-search', 'model': 'anthropic/claude-opus-5',
               'model_label': 'claude-opus-5.5-claude-code-max'}
        self.assertEqual(entry_model(row), 'anthropic/claude-opus-5.5')
        self.assertEqual(row['model'], 'anthropic/claude-opus-5')
        for override in ({'task': 'other'}, {'model_label': 'other'}):
            with self.assertRaisesRegex(ValueError, 'Unapproved'):
                entry_model({**row, **override})

    def test_receipts_include_last_response_even_without_a_ui_token_event(self):
        usage = {'input_tokens': 100, 'cached_input_tokens': 80, 'cache_write_input_tokens': 10,
                 'output_tokens': 20, 'reasoning_output_tokens': 10, 'total_tokens': 120}
        one = {'type': 'token_usage_record', 'payload': {'response_id': 'one', 'usage': usage, 'thread_token_usage': usage}}
        two = {'type': 'token_usage_record', 'payload': {'response_id': 'two', 'usage': usage,
                                                        'thread_token_usage': {k: v * 2 for k, v in usage.items()}}}
        events = [one, copy.deepcopy(one), {'type': 'event_msg', 'payload': {'type': 'token_count'}}, two]
        totals, requests, _, _ = session_usage(events)
        self.assertEqual(totals['input_tokens'], 200)
        self.assertEqual(totals['response_count'], 2)
        self.assertEqual(len(requests), 2)
        events[-1]['payload']['response_id'] = 'one'
        with self.assertRaisesRegex(ValueError, 'thread counter'):
            session_usage(events)
        events[-1]['payload']['usage'] = {**usage, 'input_tokens': 101, 'total_tokens': 121}
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            session_usage(events)

    def test_regrading_never_becomes_coding_duration(self):
        result = {'started_at': '2026-11-08T00:00:00Z', 'finished_at': '2026-11-08T01:00:00Z'}
        start, finish = '2026-11-06T00:00:00Z', '2026-11-06T00:02:00Z'
        self.assertEqual(coding_time(result, [start], [finish])[2], 120)
        self.assertIsNone(coding_time(result, [start], [])[2])
        result['agent_execution'] = {'started_at': start, 'finished_at': finish}
        self.assertEqual(coding_time(result, [], [])[2], 120)

    def test_recovered_session_directory_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recovered = root / 'agent/original-codex-sessions/2026/11/10/rollout.jsonl'
            recovered.parent.mkdir(parents=True)
            recovered.write_text('{}\n')
            self.assertEqual(coding_session(root), recovered)
            normal = root / 'agent/sessions/rollout.jsonl'
            normal.parent.mkdir(parents=True)
            normal.write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'exactly one'):
                coding_session(root)
            recovered.unlink()
            self.assertEqual(coding_session(root), normal)
            normal.unlink()
            with self.assertRaisesRegex(ValueError, 'exactly one'):
                coding_session(root)

    def test_provider_and_session_identity_follow_native_evidence(self):
        events = [{'type': 'session_meta', 'payload': {'id': 'selected', 'model_provider': 'openai'}}]
        self.assertEqual(coding_provider({'provider': 'direct'}, events, 'selected'), 'OpenAI')
        with self.assertRaisesRegex(ValueError, 'identity/provider'):
            coding_provider({'provider': 'openrouter'}, events, 'selected')
        with self.assertRaisesRegex(ValueError, 'identity/provider'):
            coding_provider({'provider': 'direct'}, events, 'another-session')
        events[0]['payload']['model_provider'] = 'openrouter'
        self.assertEqual(coding_provider({'provider': 'openrouter'}, events, 'selected'), 'OpenRouter')

    def test_empty_call_ids_do_not_join_unrelated_search_outputs(self):
        def step(i, outputs, calls=1):
            return {'step_id': i, 'source': 'agent', 'tool_calls': [
                {'tool_call_id': '', 'function_name': 'web_search_call'} for _ in range(calls)],
                'observation': {'results': [{'source_call_id': '', 'content': text} for text in outputs]}}
        raw = {'steps': [step(1, ['first']), step(2, ['second']), step(3, ['ambiguous'], 2), step(4, ['orphan'], 0)]}
        with tempfile.TemporaryDirectory() as tmp:
            export_trajectory(raw, Path(tmp))
            exported = read(Path(tmp) / 'steps-0000.json')
            self.assertEqual(exported[0]['calls'][0]['outputs'], ['first'])
            self.assertEqual(exported[1]['calls'][0]['outputs'], ['second'])
            self.assertEqual(exported[2]['calls'][0]['outputs'], [])
            self.assertEqual(exported[2]['unmatched_outputs'][0]['content'], 'ambiguous')
            self.assertEqual(exported[3]['unmatched_outputs'][0]['content'], 'orphan')


if __name__ == '__main__':
    unittest.main()
