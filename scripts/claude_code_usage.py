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
        usage['reasoning_output_tokens'] = usage.get('output_tokens_details', {}).get('thinking_tokens')
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
    requests, states = {}, []
    for events in sessions:
        for event in events:
            if event.get('type') == 'cost-state' and event.get('sessionId') == session_id:
                states.append(event)
            if event.get('type') != 'assistant':
                continue
            message = event.get('message', {})
            if message.get('model') != model or event.get('version') != version:
                raise ValueError('Claude Code session model/version mismatch')
            key = message.get('id')
            if not key:
                raise ValueError('Claude Code response has no ID')
            usage = normalized(message['usage'])
            if key in requests and any(usage[k] < requests[key][k] for k in usage):
                raise ValueError('Conflicting Claude Code streaming usage')
            requests[key] = usage
    init = [e for e in stream if e.get('type') == 'system' and e.get('subtype') == 'init']
    if (len(init) != 1 or init[0].get('session_id') != session_id or init[0].get('model') != model
            or init[0].get('claude_code_version') != version or not requests):
        raise ValueError('Claude Code stream identity/model/version mismatch')
    results = [e for e in stream if e.get('type') == 'result']
    if len(results) > 1 or len(states) > 1:
        raise ValueError('Ambiguous Claude Code final counters')
    counters = [e['modelUsage'] for e in states + results]
    totals = Counter()
    for usage in requests.values():
        totals.update(usage)
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
    else:
        note = RECORDED_USAGE_FALLBACK_NOTE
    return (dict(totals), [{'response_id': k, 'usage': v} for k, v in requests.items()],
            remainder, start, finish, bool(results), note)
