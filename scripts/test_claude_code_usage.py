"""Claude receipts, cache normalization, subagents and missing completion counters."""
import copy
import unittest

from claude_code_usage import claude_usage
from leaderboard_costs import calculate


class ClaudeUsageTests(unittest.TestCase):
    def fixture(self):
        def receipt(key, output):
            return {'type': 'assistant', 'version': '2.1.309', 'message': {
                'id': key, 'model': 'kimi-k3.1-pro', 'usage': {'input_tokens': 10,
                'cache_read_input_tokens': 80, 'cache_creation_input_tokens': 10,
                'output_tokens': output, 'output_tokens_details': {'thinking_tokens': output // 2}}}}
        sessions = [[receipt('one', 2), receipt('one', 20)], [receipt('two', 10)]]
        stream = [{'type': 'system', 'subtype': 'init', 'session_id': 'main',
                   'model': 'kimi-k3.1-pro', 'claude_code_version': '2.1.309'}]
        return sessions, stream

    def read(self, sessions, stream):
        return claude_usage(sessions, stream, 'main', 'kimi-k3.1-pro', '2.1.309')

    def test_streaming_subagents_and_cache_buckets_count_once(self):
        sessions, stream = self.fixture()
        totals, requests, remainder, start, finish, done, note = self.read(sessions, stream)
        self.assertEqual(totals['input_tokens'], 200)
        self.assertEqual(totals['output_tokens'], 30)
        self.assertEqual(totals['cached_input_tokens'], 160)
        self.assertEqual(totals['response_count'], 2)
        self.assertEqual(len(requests), 2)
        self.assertIsNone(remainder)
        self.assertIsNone(finish)
        self.assertFalse(done)
        self.assertIn('final reported token totals', note)

    def test_background_remainder_is_included_without_fabricating_receipts(self):
        sessions, stream = self.fixture()
        counter = {'kimi-k3.1-pro': {'inputTokens': 30, 'cacheReadInputTokens': 160,
            'cacheCreationInputTokens': 20, 'outputTokens': 40, 'thinkingTokens': 20}}
        sessions[0].append({'type': 'cost-state', 'sessionId': 'main', 'modelUsage': counter,
                            'startTime': 100000, 'totalDuration': 5000})
        stream.append({'type': 'result', 'modelUsage': counter})
        totals, requests, remainder, start, finish, done, note = self.read(sessions, stream)
        self.assertEqual(totals['total_tokens'], 250)
        self.assertEqual(totals['response_count'], 2)
        self.assertEqual(remainder['total_tokens'], 20)
        self.assertTrue(done)
        self.assertTrue(finish.startswith('1970-01-01T00:01:45'))
        trial = {'id': 'trial', 'task': 'task', 'configuration': {'model': 'kimi-k3.1-pro', 'effort': 'max'},
                 'trajectory_sha256': 'hash', 'tokens': totals}
        row = {'task': 'task', 'model': 'kimi-k3.1-pro', 'effort': 'max', 'primary_trajectory_sha256': 'hash',
               'requests': requests, 'aggregate_remainder': remainder}
        price = {'rates': {'input': '2', 'cached_input': '.2', 'cache_write_input': '2', 'output': '10'}}
        priced = calculate({'trials': [trial]}, {'rows': [row]}, {'models': {'kimi-k3.1-pro': price}})
        self.assertEqual(priced['trial'], {'cost_usd': '0.000532', 'response_count': 2})
        price['long_context'] = {'above_input_tokens': 272000, 'rates': price['rates']}
        with self.assertRaisesRegex(ValueError, 'per-request context tiers'):
            calculate({'trials': [trial]}, {'rows': [row]}, {'models': {'kimi-k3.1-pro': price}})
        stream[-1] = copy.deepcopy(stream[-1])
        stream[-1]['modelUsage']['kimi-k3.1-pro']['outputTokens'] += 1
        with self.assertRaisesRegex(ValueError, 'counters disagree'):
            self.read(sessions, stream)

    def test_wrong_model_and_regressing_stream_usage_fail(self):
        sessions, stream = self.fixture()
        sessions[1][0]['message']['model'] = 'other'
        with self.assertRaisesRegex(ValueError, 'model/version'):
            self.read(sessions, stream)
        sessions, stream = self.fixture()
        sessions[0].reverse()
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.read(sessions, stream)


if __name__ == '__main__':
    unittest.main()
