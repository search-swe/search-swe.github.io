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
        key = (row['task'], row['model'], row['effort'])
        if key in rows:
            raise ValueError(f'Duplicate usage selection: {key}')
        rows[key] = row
    expected = {(t['task'], t['configuration']['model'], t['configuration']['effort'])
                for t in snapshot['trials']}
    if set(rows) != expected:
        raise ValueError('Usage and selected trials do not cover the same task/model set')
    costs, all_ids = {}, set()
    for trial in snapshot['trials']:
        config = trial['configuration']
        row = rows[(trial['task'], config['model'], config['effort'])]
        if row.get('primary_trajectory_sha256') != trial['trajectory_sha256']:
            raise ValueError(f'Coding trajectory changed: {trial["id"]}')
        unique = {}
        for request in row['requests']:
            key = request['response_id']
            if not key or (key in unique and unique[key] != request['usage']):
                raise ValueError('Missing response ID or conflicting repeated usage')
            unique[key] = request['usage']
        if not unique or all_ids.intersection(unique):
            raise ValueError('Missing requests or a response assigned to multiple trials')
        all_ids.update(unique)
        totals, cost = Counter(), Decimal(0)
        for tokens in unique.values():
            cost += request_cost(tokens, prices['models'][config['model']])
            totals.update({key: tokens[key] for key in TOKEN_FIELDS})
        if row.get('aggregate_remainder') is not None:
            model = prices['models'][config['model']]
            if model.get('long_context'):
                raise ValueError('Aggregate usage cannot be priced with per-request context tiers')
            remainder = row['aggregate_remainder']
            cost += request_cost(remainder, model)
            totals.update({key: remainder[key] for key in TOKEN_FIELDS})
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
        cost = Decimal(item['cost_usd'])
        if not cost.is_finite() or cost < 0 or item['response_count'] != trial['tokens']['response_count']:
            raise ValueError(f'Invalid cost coverage: {trial["id"]}')
        trial['cost_usd'] = float(cost)
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
        total = sum(Decimal(costs[t['id']]['cost_usd']) for t in snapshot['trials'] if t['entry'] == entry['id'])
        print(f'{entry["name"]}: ${total:.2f} (unrounded: {total})')
    print(f'{len(costs)} selected trials priced; cost supplement {"verified" if args.check else "written"}.')


if __name__ == '__main__':
    main()
