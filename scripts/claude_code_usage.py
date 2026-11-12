"""Read Claude Code receipts and final counters without using its model price guesses."""
from collections import Counter
from datetime import datetime, timezone

from import_results import TOKEN_FIELDS


RECORDED_USAGE_FALLBACK_NOTE = (
    'Claude Code main/subagent response receipts, deduplicated by message ID; input includes cache reads and writes.'
    ' Final aggregate counter unavailable: deduplicated recorded responses are used as the final reported'
    ' token totals and the basis for estimated cost. Unrecorded usage is not estimated.'
)


def normalized(usage, aggregate=False):
    names = (('inputTokens', 'cacheReadInputTokens', 'cacheCreationInputTokens', 'outputTokens', 'thinkingTokens')
             if aggregate else ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens',
                                'output_tokens', 'reasoning_output_tokens'))
    if not aggregate:
        usage = dict(usage)
        usage['reasoning_output_tokens'] = (usage.get('output_tokens_details') or {}).get('thinking_tokens')
        if usage.get('output_tokens') == 0:
            usage['reasoning_output_tokens'] = 0
    values = [usage.get(k) for k in names]
    if any(type(n) is not int or n < 0 for n in values):
        raise ValueError('Missing or invalid Claude Code token count')
    uncached, cached, written, output, thinking = values
    if thinking > output:
        raise ValueError('Reasoning tokens exceed output tokens')
    inp = uncached + cached + written
    return dict(zip(TOKEN_FIELDS[:-1], (inp, cached, written, output, thinking, inp + output)))


def claude_usage(sessions, stream, session_id, model, version):
    """Deduplicate streaming blocks across main/subagent sessions; reconcile final totals.

    Final modelUsage includes compaction/background calls absent from the transcript.
    Their aggregate remainder can only be priced with a flat (not per-request tiered)
    model tariff. Missing final counters fall back to deduplicated recorded usage.
    """
    requests, states, partial = {}, [], {}
    for events in sessions:
        for event in events:
            if event.get('type') == 'cost-state' and event.get('sessionId') == session_id:
                states.append(event)
            if event.get('type') != 'assistant':
                continue
            message = event.get('message', {})
            if message.get('model') == '<synthetic>':
                # Claude Code emits local connection-error messages, not model calls.
                if any(message.get('usage', {}).get(k) != 0 for k in
                       ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')):
                    raise ValueError('Synthetic Claude Code message has nonzero or missing usage')
                continue
            if message.get('model') != model or event.get('version') != version:
                raise ValueError('Claude Code session model/version mismatch')
            key = message.get('id')
            if not key:
                raise ValueError('Claude Code response has no ID')
            raw_usage = message['usage']
            if raw_usage.get('output_tokens', 0) > 0 and not raw_usage.get('output_tokens_details'):
                # An interrupted response can lack its reasoning breakdown. Keep
                # its known buckets for reconciliation; never invent that count.
                partial[key] = raw_usage
                continue
            usage = normalized(raw_usage)
            if key in requests and any(usage[k] < requests[key][k] for k in usage):
                raise ValueError('Conflicting Claude Code streaming usage')
            requests[key] = usage
    init = [e for e in stream if e.get('type') == 'system' and e.get('subtype') == 'init']
    if (not init or any(e.get('session_id') != session_id or e.get('model') != model
            or e.get('claude_code_version') != version for e in init) or not requests):
        raise ValueError('Claude Code stream identity/model/version mismatch')
    results = [e for e in stream if e.get('type') == 'result']
    if len(states) > 1 or len(results) > len(init):
        raise ValueError('Ambiguous Claude Code final counters')
    # A resumed session writes several cumulative results. Verify monotonicity
    # and reconcile its last result with the final saved state, without summing.
    previous = None
    for result in results:
        if result.get('session_id', session_id) != session_id or set(result['modelUsage']) != {model}:
            raise ValueError('Unexpected session/model in Claude Code result')
        current = normalized(result['modelUsage'][model], aggregate=True)
        if previous and any(current[k] < previous[k] for k in current):
            raise ValueError('Regressing Claude Code resumed counters')
        previous = current
    counters = [e['modelUsage'] for e in states + results[-1:]]
    totals = Counter()
    for usage in requests.values():
        totals.update(usage)
    incomplete = {k: v for k, v in partial.items() if k not in requests}
    if incomplete and not counters:
        raise ValueError('Incomplete Claude Code receipt requires a final aggregate counter')
    remainder = None
    if counters:
        if any(set(c) != {model} for c in counters):
            raise ValueError('Unexpected model in Claude Code final counters')
        complete = [normalized(c[model], aggregate=True) for c in counters]
        if any(c != complete[0] for c in complete):
            raise ValueError('Claude Code terminal and saved counters disagree')
        remainder = {k: complete[0][k] - totals[k] for k in TOKEN_FIELDS[:-1]}
        if any(v < 0 for v in remainder.values()):
            raise ValueError('Claude Code aggregate is smaller than recorded receipts')
        known_partial = Counter()
        for usage in incomplete.values():
            # Zero is used only to validate the known non-reasoning buckets;
            # this temporary value is never exported or counted as a receipt.
            known = normalized({**usage, 'output_tokens_details': {'thinking_tokens': 0}})
            known_partial.update(known)
        if any(known_partial[k] > remainder[k] for k in known_partial):
            raise ValueError('Claude Code aggregate does not cover partial receipts')
        totals.update(remainder)
    totals['response_count'] = len(requests)
    start = finish = None
    if states:
        state = states[0]
        start = datetime.fromtimestamp(state['startTime'] / 1000, timezone.utc).isoformat()
        finish = datetime.fromtimestamp((state['startTime'] + state['totalDuration']) / 1000, timezone.utc).isoformat()
    note = 'Claude Code main/subagent response receipts, deduplicated by message ID; input includes cache reads and writes.'
    if counters:
        note += ' Final modelUsage counters include background/compaction usage; recorded response count excludes calls without individual receipts.'
        if incomplete:
            note += ' An interrupted response lacks its reasoning breakdown; final counters include its usage, and the response count excludes this partial receipt.'
    else:
        note = RECORDED_USAGE_FALLBACK_NOTE
    return (dict(totals), [{'response_id': k, 'usage': v} for k, v in requests.items()],
            remainder, start, finish, bool(results), note)
