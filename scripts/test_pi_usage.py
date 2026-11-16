"""Pi source reconciliation must retain native tail receipts without double counting."""
import copy
import unittest
from pi_usage import pi_usage


class PiUsageTests(unittest.TestCase):
    def fixture(self):
        message = {'role': 'assistant', 'provider': 'openrouter', 'model': 'model',
                   'responseId': 'one', 'stopReason': 'stop',
                   'usage': {'input': 10, 'cacheRead': 80, 'cacheWrite': 5,
                             'output': 20, 'reasoning': 12, 'totalTokens': 115}}
        session = [{'type': 'session', 'id': 'session'},
                   {'type': 'model_change', 'provider': 'openrouter', 'modelId': 'model'},
                   {'type': 'thinking_level_change', 'thinkingLevel': 'max'},
                   {'type': 'message', 'message': copy.deepcopy(message)}]
        return [session], [{'type': 'message_end', 'message': message}]

    def test_union_deduplicates_shared_calls_and_retains_native_tail(self):
        sessions, stream = self.fixture()
        tail = copy.deepcopy(sessions[0][-1]);tail['message']['responseId'] = 'tail'
        sessions[0].append(tail)
        totals, receipts, done, note = pi_usage(sessions, stream, 'session', 'model')
        self.assertEqual(totals['total_tokens'], 230)
        self.assertEqual(totals['cached_input_tokens'], 160)
        self.assertEqual(totals['response_count'], 2)
        self.assertTrue(done)
        self.assertIn('absent from the CLI/ATIF', note)
        tail['message']['usage']['input'] += 1
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            pi_usage(sessions, stream, 'session', 'model')

    def test_zero_retry_diagnostic_does_not_require_reasoning(self):
        sessions, stream = self.fixture()
        stream.append({'type': 'message_end', 'message': {'role': 'assistant', 'provider': 'openrouter',
            'model': 'model', 'stopReason': 'error', 'usage': dict.fromkeys(
                ['input', 'output', 'cacheRead', 'cacheWrite', 'totalTokens'], 0)}})
        self.assertEqual(pi_usage(sessions, stream, 'session', 'model')[0]['response_count'], 1)

    def test_conflicts_and_wrong_effort_fail(self):
        sessions, stream = self.fixture()
        stream[0]['message']['usage']['reasoning'] = 11
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            pi_usage(sessions, stream, 'session', 'model')
        sessions, stream = self.fixture();sessions[0][2]['thinkingLevel'] = 'high'
        with self.assertRaisesRegex(ValueError, 'effort'):
            pi_usage(sessions, stream, 'session', 'model')
