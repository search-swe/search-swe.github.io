"""Community receipt reconciliation and CLI-only publication contracts."""
import copy
import unittest

from import_hy4_results import community_usage, repaired_trajectory, usage_row
from leaderboard_costs import calculate


class Hy4Tests(unittest.TestCase):
    def fixture(self):
        receipt = {'input_tokens': 10, 'cache_read_input_tokens': 80, 'cache_creation_input_tokens': 0,
                   'output_tokens': 5, 'output_tokens_details': {'thinking_tokens': 0}}
        assistant = {'type': 'assistant', 'version': '2.1.309',
                     'message': {'id': 'response', 'model': 'hy4', 'usage': receipt}}
        final = {'hy4': {'inputTokens': 12, 'cacheReadInputTokens': 100, 'cacheCreationInputTokens': 0,
                         'outputTokens': 8, 'thinkingTokens': 0}}
        state = {'type': 'cost-state', 'sessionId': 'main', 'modelUsage': final}
        stream = [{'type': 'system', 'subtype': 'init', 'session_id': 'main', 'model': 'hy4',
                   'claude_code_version': '2.1.309'},
                  {'type': 'result', 'session_id': 'main', 'modelUsage': copy.deepcopy(final)}]
        return assistant, state, stream

    def test_streaming_duplicates_and_background_remainder_count_once(self):
        assistant, state, stream = self.fixture()
        tokens, requests, remainder, aggregate_only, *_ = community_usage(
            [[assistant, copy.deepcopy(assistant), state]], stream, 'main')
        self.assertEqual(tokens['total_tokens'], 120)
        self.assertEqual(tokens['response_count'], 1)
        self.assertEqual(len(requests), 1)
        self.assertEqual(remainder['total_tokens'], 25)
        self.assertFalse(aggregate_only)

    def test_cli_only_uses_model_usage_without_inventing_receipts(self):
        _, _, stream = self.fixture()
        tokens, requests, remainder, aggregate_only, *_ = community_usage([], stream, 'main')
        self.assertEqual(tokens['total_tokens'], 120)
        self.assertEqual(tokens['response_count'], 0)
        self.assertEqual(requests, [])
        self.assertEqual(remainder['total_tokens'], 120)
        self.assertTrue(aggregate_only)

    def test_source_identity_and_counter_disagreements_fail(self):
        assistant, state, stream = self.fixture()
        for mutation in ('version', 'model', 'counter', 'session', 'effort'):
            a, s, cli = copy.deepcopy((assistant, state, stream))
            events = [a, s]
            if mutation == 'version': a['version'] = 'unknown'
            elif mutation == 'model': a['message']['model'] = 'other'
            elif mutation == 'counter': cli[-1]['modelUsage']['hy4']['outputTokens'] += 1
            elif mutation == 'session': cli[0]['session_id'] = 'other'
            else: events.append({'type': 'api-request', 'params': {'output_config': {'effort': 'max'}}})
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                community_usage([events], cli, 'main')

    def test_cli_derivative_repairs_totals_preserves_missing_step_usage_and_source(self):
        _, _, stream = self.fixture()
        tokens = community_usage([], stream, 'main')[0]
        raw = {'agent': {'version': 'unknown'}, 'final_metrics': {'total_completion_tokens': 0},
               'steps': [{'source': 'agent', 'metrics': {'prompt_tokens': 90, 'completion_tokens': 0}}]}
        repaired = repaired_trajectory(raw, tokens, cli_only=True)
        self.assertEqual(repaired['agent']['version'], '2.1.309')
        self.assertEqual(repaired['final_metrics']['total_completion_tokens'], 8)
        self.assertIsNone(repaired['steps'][0]['metrics']['completion_tokens'])
        self.assertEqual(repaired['steps'][0]['metrics']['prompt_tokens'], 90)
        self.assertEqual(raw['agent']['version'], 'unknown')
        self.assertEqual(raw['steps'][0]['metrics']['completion_tokens'], 0)

    def test_aggregate_only_cost_requires_explicit_basis_and_flat_rates(self):
        _, _, stream = self.fixture()
        tokens, requests, remainder, *_ = community_usage([], stream, 'main')
        row = usage_row('task', 'hash', tokens, requests, remainder, aggregate_only=True)
        snapshot = {'trials': [{'id': 'trial', 'task': 'task', 'configuration': {'model': 'tencent/hy4', 'effort': 'high'},
                                'trajectory_sha256': 'hash', 'tokens': tokens}]}
        model = {'rates': {'input': '0.834', 'cached_input': '0.042', 'cache_write_input': '0.834', 'output': '2.501'}}
        prices = {'models': {'tencent/hy4': model}}
        self.assertEqual(calculate(snapshot, {'rows': [row]}, prices)['trial']['cost_usd'], '0.000034216')
        for change in ('basis', 'counter', 'tier'):
            selected, tariff = copy.deepcopy(row), copy.deepcopy(prices)
            if change == 'basis': selected.pop('usage_basis')
            elif change == 'counter': selected.pop('aggregate_remainder')
            else: tariff['models']['tencent/hy4']['long_context'] = {'above_input_tokens': 100}
            with self.subTest(change=change), self.assertRaises(ValueError):
                calculate(snapshot, {'rows': [selected]}, tariff)


if __name__ == '__main__':
    unittest.main()
