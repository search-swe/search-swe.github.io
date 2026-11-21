"""Price selected coding requests using a frozen official model price table.

The small cost supplement is bound to the existing verified result snapshot.
It does not change the immutable Hugging Face trajectory release.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / 'content/leaderboard'
TOKEN_FIELDS = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens',
                'output_tokens', 'reasoning_output_tokens', 'total_tokens')


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def request_cost(usage, model):
    for key in TOKEN_FIELDS:
        if key == 'reasoning_output_tokens' and key in usage and usage[key] is None:
            continue  # Optional breakdown of output, which is already priced in full.
        if type(usage.get(key)) is not int or usage[key] < 0:
            raise ValueError(f'Missing or invalid token count: {key}')
    inp, cached, written = (usage[k] for k in TOKEN_FIELDS[:3])
    output = usage['output_tokens']
    if cached + written > inp or usage['total_tokens'] != inp + output:
        raise ValueError('Overlapping cache buckets or inconsistent total tokens')
    rates = model['rates']
    tier = model.get('long_context')
    if tier and inp > tier['above_input_tokens']:
        rates = tier['rates']
    counts = {'input': inp - cached - written, 'cached_input': cached,
              'cache_write_input': written, 'output': output}
    result = Decimal(0)
    for key, count in counts.items():
        rate = Decimal(rates[key])
        if not rate.is_finite() or rate < 0:
            raise ValueError(f'Invalid price: {key}')
        result += count * rate / 1_000_000
    return result


def calculate(snapshot, usage, prices):
    """Join by selected task/model/effort and verify provenance and all totals."""
    rows = {}
    excluded = set(snapshot.get('selection', {}).get('excluded_models', []))
    for row in usage['rows']:
        if row['model'] in excluded:
            continue
        key = (row['task'], row['model'], row['effort'], row.get('agent', 'Codex' if row['model'].startswith('deepseek/') else ''))
        if key in rows:
            raise ValueError(f'Duplicate usage selection: {key}')
        rows[key] = row
    def trial_key(t):
        c = t['configuration']
        return (t['task'], c['model'], c['effort'], c.get('agent', 'Codex') if c['model'].startswith('deepseek/') else '')
    expected = {trial_key(t)
                for t in snapshot['trials']}
    if set(rows) != expected:
        raise ValueError('Usage and selected trials do not cover the same task/model set')
    costs, all_ids = {}, set()
    for trial in snapshot['trials']:
        config = trial['configuration']
        row = rows[trial_key(trial)]
        if row.get('primary_trajectory_sha256') != trial['trajectory_sha256']:
            raise ValueError(f'Coding trajectory changed: {trial["id"]}')
        if row.get('usage_basis') == 'exported_harness_summary':
            if (row['requests'] or row.get('aggregate_remainder') is not None or
                    row['tokens'] != trial['tokens'] or row['cost_usd'] != trial.get('harness_reported_cost_usd')):
                raise ValueError(f'Exported harness summary differs: {trial["id"]}')
            value = row['cost_usd']
            costs[trial['id']] = {'cost_usd': None if value is None else str(value),
                                  'response_count': trial['tokens']['response_count']}
            continue
        unique = {}
        for request in row['requests']:
            key = request['response_id']
            if not key or (key in unique and unique[key] != request['usage']):
                raise ValueError('Missing response ID or conflicting repeated usage')
            unique[key] = request['usage']
        aggregate_only = row.get('usage_basis') == 'final_model_usage_only'
        if (aggregate_only and (unique or row.get('aggregate_remainder') is None)):
            raise ValueError('Aggregate-only usage must contain final counters and no individual receipts')
        if (not unique and not aggregate_only) or all_ids.intersection(unique):
            raise ValueError('Missing requests or a response assigned to multiple trials')
        all_ids.update(unique)
        totals, cost = Counter(), Decimal(0)
        measured = list(unique.values())
        model = prices['models'][config['model']]
        remainder = row.get('aggregate_remainder')
        if remainder is not None:
            if model.get('long_context'):
                raise ValueError('Aggregate usage cannot be priced with per-request context tiers')
            measured.append(remainder)
        for tokens in measured:
            cost += request_cost(tokens, model)
            totals.update({key: tokens[key] for key in TOKEN_FIELDS if tokens[key] is not None})
        if any(tokens['reasoning_output_tokens'] is None for tokens in measured):
            totals['reasoning_output_tokens'] = None
        totals['response_count'] = len(unique)
        if any(totals[k] != trial['tokens'].get(k) for k in (*TOKEN_FIELDS, 'response_count')):
            raise ValueError(f'Usage disagrees with selected trial totals: {trial["id"]}')
        costs[trial['id']] = {'cost_usd': format(cost, 'f'), 'response_count': len(unique)}
    return costs


def apply_costs(snapshot, supplement, prices, snapshot_sha256, pricing_sha256):
    if (supplement['snapshot_id'] != snapshot['id'] or
            supplement['snapshot_sha256'] != snapshot_sha256 or
            supplement['pricing_sha256'] != pricing_sha256):
        raise ValueError('Cost supplement is stale; rerun scripts/leaderboard_costs.py')
    if set(supplement['trials']) != {t['id'] for t in snapshot['trials']}:
        raise ValueError('Cost supplement must cover exactly the selected trials')
    snapshot = copy.deepcopy(snapshot)
    for trial in snapshot['trials']:
        item = supplement['trials'][trial['id']]
        raw = item['cost_usd']
        cost = Decimal(raw) if raw is not None else None
        if (item['response_count'] != trial['tokens']['response_count'] or
                (cost is None and ('harness_reported_cost_usd' not in trial or trial['harness_reported_cost_usd'] is not None)) or
                (cost is not None and (not cost.is_finite() or cost < 0))):
            raise ValueError(f'Invalid cost coverage: {trial["id"]}')
        trial['cost_usd'] = float(cost) if cost is not None else None
    snapshot['cost_methodology'] = {'type': 'estimated', **prices,
                                  'usage_sha256': supplement['usage_sha256'],
                                  'pricing_sha256': pricing_sha256}
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--usage', type=Path, required=True, help='Selected leaderboard-data/usage.json')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    source = (CONTENT / 'release.json').read_bytes()
    price_source = (CONTENT / 'official-pricing.json').read_bytes()
    usage_source = args.usage.read_bytes()
    snapshot, prices = json.loads(source), json.loads(price_source)
    costs = calculate(snapshot, json.loads(usage_source), prices)
    supplement = {'schema': 1, 'snapshot_id': snapshot['id'],
                  'snapshot_sha256': sha256(source), 'pricing_sha256': sha256(price_source),
                  'usage_sha256': sha256(usage_source), 'trials': costs}
    rendered = json.dumps(supplement, indent=2, sort_keys=True) + '\n'
    destination = CONTENT / 'costs.json'
    if args.check:
        if not destination.exists() or destination.read_text() != rendered:
            raise ValueError('Cost supplement needs rebuilding')
    else:
        destination.write_text(rendered)
    for entry in snapshot['entries']:
        values = [costs[t['id']]['cost_usd'] for t in snapshot['trials'] if t['entry'] == entry['id']]
        if None in values:
            print(f'{entry["name"]}: cost unavailable')
            continue
        total = sum(Decimal(value) for value in values)
        print(f'{entry["name"]}: ${total:.2f} (unrounded: {total})')
    print(f'{len(costs)} selected trials priced; cost supplement {"verified" if args.check else "written"}.')


if __name__ == '__main__':
    main()
