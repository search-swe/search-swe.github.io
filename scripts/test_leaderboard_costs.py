"""Financial arithmetic, request coverage, and snapshot binding contracts."""
import copy
import json
import unittest
from decimal import Decimal

import leaderboard_costs as costs
import build_leaderboard as build


def tokens(inp=12015, cached=0, written=12012, output=239):
    return {'input_tokens': inp, 'cached_input_tokens': cached,
            'cache_write_input_tokens': written, 'output_tokens': output,
            'reasoning_output_tokens': 144, 'total_tokens': inp + output}


class CostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prices = json.loads((costs.CONTENT / 'official-pricing.json').read_text())
        cls.luna = cls.prices['models']['openai/gpt-6-luna']

    def test_cache_write_and_reasoning_are_not_double_counted(self):
        self.assertEqual(costs.request_cost(tokens(), self.luna), Decimal('0.0016213'))
        self.assertEqual(costs.request_cost(tokens(137255, 136252, 1000, 3582), self.luna), Decimal('0.00327882'))
        usage = tokens()
        usage['reasoning_output_tokens'] = 999  # Preserve anomalous auxiliary counters; output is the billed total.
        self.assertEqual(costs.request_cost(usage, self.luna), Decimal('0.0016213'))

    def test_long_context_boundary_uses_each_request_not_trial_total(self):
        self.assertEqual(costs.request_cost(tokens(272000, 0, 0, 1000), self.luna), Decimal('0.0277'))
        self.assertEqual(costs.request_cost(tokens(272001, 0, 0, 1000), self.luna), Decimal('0.0551502'))
        two_calls = 2 * costs.request_cost(tokens(200000, 0, 0, 1000), self.luna)
        self.assertEqual(two_calls, Decimal('0.041'))
        self.assertNotEqual(two_calls, costs.request_cost(tokens(400000, 0, 0, 2000), self.luna))

    def test_missing_and_overlapping_usage_cannot_be_published_as_zero(self):
        for usage in [tokens(10, 9, 2), {k: v for k, v in tokens().items() if k != 'cached_input_tokens'},
                      {**tokens(), 'total_tokens': 1}]:
            with self.assertRaises(ValueError):
                costs.request_cost(usage, self.luna)

    def test_selected_model_long_context_rates(self):
        usage = tokens(1000000, 800000, 0, 100000)
        expected = {'openai/gpt-6-luna': '0.131', 'openai/gpt-6.1-terra': '1.23', 'gpt-6.1-sol': '2.46',
                    'kimi-k3.1-pro': '1.56', 'deepseek/deepseek-v4.1-flash-1017': '0.0924'}
        for model, value in expected.items():
            self.assertEqual(costs.request_cost(usage, self.prices['models'][model]), Decimal(value))

    def fixture(self):
        usage = tokens()
        trial = {'id': 'trial', 'task': 'task', 'configuration': {'model': 'openai/gpt-6-luna', 'effort': 'max'},
                 'trajectory_sha256': 'hash', 'tokens': {**usage, 'response_count': 1}}
        row = {'task': 'task', 'model': 'openai/gpt-6-luna', 'effort': 'max', 'primary_trajectory_sha256': 'hash',
               'requests': [{'response_id': 'one', 'usage': usage}]}
        return {'id': 'snapshot', 'trials': [trial]}, {'rows': [row]}

    def test_repeated_request_is_counted_once_but_conflicts_fail(self):
        snapshot, usage = self.fixture()
        usage['rows'][0]['requests'] *= 2
        result = costs.calculate(snapshot, usage, self.prices)
        self.assertEqual(Decimal(result['trial']['cost_usd']), Decimal('0.0016213'))
        self.assertEqual(result['trial']['response_count'], 1)
        usage['rows'][0]['requests'][1] = {'response_id': 'one', 'usage': tokens(output=300)}
        with self.assertRaises(ValueError):
            costs.calculate(snapshot, usage, self.prices)

    def test_only_explicitly_withdrawn_models_are_excluded_from_usage(self):
        snapshot, usage = self.fixture()
        snapshot['selection'] = {'excluded_models': ['z-ai/glm-5.3-flash']}
        withdrawn = copy.deepcopy(usage['rows'][0])
        withdrawn['model'] = 'z-ai/glm-5.3-flash'
        usage['rows'].append(withdrawn)
        self.assertEqual(set(costs.calculate(snapshot, usage, self.prices)), {'trial'})
        usage['rows'][-1]['model'] = 'unexpected-model'
        with self.assertRaises(ValueError):
            costs.calculate(snapshot, usage, self.prices)

    def test_changed_trajectory_missing_selection_or_partial_usage_fail(self):
        snapshot, source = self.fixture()
        for mutation in ('trajectory', 'selection', 'tokens'):
            usage = copy.deepcopy(source)
            if mutation == 'trajectory':
                usage['rows'][0]['primary_trajectory_sha256'] = 'different'
            elif mutation == 'selection':
                usage['rows'] = []
            else:
                usage['rows'][0]['requests'][0]['usage'] = tokens(output=300)
            with self.assertRaises(ValueError):
                costs.calculate(snapshot, usage, self.prices)

    def test_cost_supplement_is_bound_to_snapshot_and_price_table(self):
        snapshot, usage = self.fixture()
        supplement = {'snapshot_id': 'snapshot', 'snapshot_sha256': 's', 'pricing_sha256': 'p',
                      'usage_sha256': 'u', 'trials': costs.calculate(snapshot, usage, self.prices)}
        enriched = costs.apply_costs(snapshot, supplement, self.prices, 's', 'p')
        self.assertEqual(enriched['trials'][0]['cost_usd'], 0.0016213)
        self.assertNotIn('cost_usd', snapshot['trials'][0])
        for source, pricing in [('changed', 'p'), ('s', 'changed')]:
            with self.assertRaises(ValueError):
                costs.apply_costs(snapshot, supplement, self.prices, source, pricing)

    def test_valid_zero_scores_and_free_calls_still_count_toward_total_cost(self):
        trials = [{'score': 0, 'cost_usd': cost, 'tokens': {'total_tokens': 12}, 'agent_seconds': 1}
                  for cost in [1.25, 0, 2.5]]
        self.assertEqual(build.stats(trials)['cost'], 3.75)
        trials[0]['cost_usd'] = None
        self.assertIsNone(build.stats(trials)['cost'])


if __name__ == '__main__':
    unittest.main()
