"""Reconcile Pi CLI events and native sessions by provider response ID."""
from collections import Counter


def pi_usage(sessions, stream, session_id, model):
    headers = [e for s in sessions for e in s if e.get('type') == 'session']
    changes = [e for s in sessions for e in s if e.get('type') == 'model_change']
    efforts = [e.get('thinkingLevel') for s in sessions for e in s
               if e.get('type') == 'thinking_level_change']
    if (len(headers) != 1 or headers[0].get('id') != session_id or not changes or
            any(e.get('provider') != 'openrouter' or e.get('modelId') != model for e in changes)
            or not efforts or set(efforts) != {'max'}):
        raise ValueError('Pi native identity/provider/model/effort mismatch')
    requests, cli_ids = {}, set()
    last = None
    for events, native in [(stream, False)] + [(s, True) for s in sessions]:
        for e in events:
            if e.get('type') != ('message' if native else 'message_end'):
                continue
            m = e.get('message', {})
            if m.get('role') != 'assistant':
                continue
            if m.get('provider') != 'openrouter' or m.get('model') != model:
                raise ValueError('Pi response model/provider mismatch')
            last = m
            u = m.get('usage', {})
            if all(u.get(k) == 0 for k in ('input', 'cacheRead', 'cacheWrite', 'output', 'totalTokens')):
                continue  # Explicit zero-usage retry diagnostics stay in the raw logs.
            keys = ('input', 'cacheRead', 'cacheWrite', 'output', 'reasoning', 'totalTokens')
            if (any(type(u.get(k)) is not int or u[k] < 0 for k in keys)
                    or u['totalTokens'] != sum(u[k] for k in keys[:4]) or u['reasoning'] > u['output']):
                raise ValueError('Missing or inconsistent Pi response usage')
            rid = m.get('responseId')
            usage = {'input_tokens': u['input'] + u['cacheRead'] + u['cacheWrite'],
                     'cached_input_tokens': u['cacheRead'], 'cache_write_input_tokens': u['cacheWrite'],
                     'output_tokens': u['output'], 'reasoning_output_tokens': u['reasoning'],
                     'total_tokens': u['totalTokens']}
            if not rid or (rid in requests and requests[rid] != usage):
                raise ValueError('Missing Pi response ID or conflicting repeated usage')
            requests[rid] = usage
            if not native:
                cli_ids.add(rid)
            last = m
    if not requests:
        raise ValueError('No recorded Pi model responses')
    totals = Counter()
    for usage in requests.values():
        totals.update(usage)
    totals['response_count'] = len(requests)
    note = ('Pi CLI and native session receipts, deduplicated by provider response ID; '
            'input includes cache reads and writes, and reasoning is included in output.')
    if requests.keys() - cli_ids:
        note += ' Native sessions contain responses absent from the CLI/ATIF summary; totals include their recorded usage.'
    return dict(totals), [{'response_id': k, 'usage': v} for k, v in requests.items()], last.get('stopReason') == 'stop', note
