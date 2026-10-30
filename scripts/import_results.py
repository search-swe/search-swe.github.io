"""Export the selected local evaluation snapshot and lazy trajectory chunks.

Only INDEX.csv selections are imported. No model calls, remote fetches, or raw
job-directory serving. Large local exports are intentionally gitignored.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path

from export_trial_files import export_files, sanitize

ROOT = Path(__file__).resolve().parents[1]
NAMES = {
    "openai/gpt-6-luna": "GPT-6 Luna",
    "deepseek/deepseek-v4.1-flash-1017": "DeepSeek V4.1 Flash 1017",
    "xiaomi/mimo-v2.6-flash": "MiMo-V2.6-Flash",
    "z-ai/glm-5.3-flash": "GLM 5.3 Flash",
}
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                "output_tokens", "reasoning_output_tokens", "total_tokens", "response_count")
CHUNK_BYTES = 250_000
TEXT_CHARS = 48_000


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, data, check=False):
    if not isinstance(data, bytes):
        data = encode(data)
    if path.exists() and path.read_bytes() == data:
        return
    if check:
        raise ValueError(f"Export needs rebuilding: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def scrub(text):
    """Conservative credential-pattern redaction, also applied to downloads."""
    text = re.sub(r"\b(?:sk-(?:or-v1-)?[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,})\b",
                  "[REDACTED: credential]", text)
    text = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._-]{20,}", r"\1[REDACTED: credential]", text)
    return text


def text_value(value):
    return scrub(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))


def export_trajectory(raw, directory, check=False, scrubber=scrub, public=False):
    """Pair observations by call ID across the whole trace, never by position."""
    observations = {}
    call_ids = {c['tool_call_id'] for s in raw['steps'] for c in s.get('tool_calls', [])}
    for step in raw['steps']:
        for observation in step.get('observation', {}).get('results', []):
            observations.setdefault(observation.get('source_call_id'), []).append(observation)
    steps, index, search, download_steps = [], [], [], []
    external_count = 0
    redactions = 0

    def payload(value, searchable):
        nonlocal external_count, redactions
        original = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        safe = sanitize(value, scrubber)
        value = safe if isinstance(safe, str) else json.dumps(safe, ensure_ascii=False, indent=2)
        redactions += int(value != original)
        searchable.append(value)
        if len(value) <= TEXT_CHARS:
            return value
        parts = []
        for offset in range(0, len(value), TEXT_CHARS):
            name = f'text-{external_count:05}.json'
            external_count += 1
            write(directory / name, value[offset:offset + TEXT_CHARS], check)
            parts.append(name)
        return {'preview': value[:1200], 'chars': len(value), 'parts': parts}

    for source in raw['steps']:
        searchable = []
        step = {key: source.get(key) for key in ('step_id', 'timestamp', 'source')}
        step['model_name'] = source.get('model_name')
        metrics = source.get('metrics') or {}
        step['usage'] = {
            'input_tokens': metrics.get('prompt_tokens'),
            'cached_input_tokens': metrics.get('cached_tokens'),
            'output_tokens': metrics.get('completion_tokens'),
        }
        step['message'] = payload(source.get('message', ''), searchable)
        if source.get('reasoning_content'):
            step['reasoning'] = payload(source['reasoning_content'], searchable)
        step['calls'] = []
        for call in source.get('tool_calls', []):
            name = call['function_name']
            searchable.append(name)
            step['calls'].append({
                'id': call['tool_call_id'], 'name': name,
                'input': payload(call.get('arguments', {}), searchable),
                'outputs': [payload(o.get('content', ''), searchable)
                            for o in observations.get(call['tool_call_id'], [])],
            })
        step['unmatched_outputs'] = [
            {'id': o.get('source_call_id'), 'content': payload(o.get('content', ''), searchable)}
            for o in source.get('observation', {}).get('results', [])
            if o.get('source_call_id') not in call_ids
        ]
        # Keep the recorded structured ATIF fields for a complete text download.
        download_steps.append({k: source[k] for k in (
            'step_id', 'timestamp', 'source', 'message', 'reasoning_content',
            'tool_calls', 'observation', 'metrics', 'model_name', 'llm_call_count') if k in source})
        tools = list(dict.fromkeys(c['name'] for c in step['calls']))
        preview_value = sanitize(source.get('message') or (
            source.get('tool_calls', [{}])[0].get('arguments', '') if tools else ''), scrubber)
        preview = re.sub(r'\s+', ' ', text_value(preview_value)).strip()[:170]
        index.append({'id': step['step_id'], 'source': step['source'], 'time': step['timestamp'],
                      'preview': preview, 'tools': tools, 'calls': len(step['calls'])})
        # Full-text word index, including content externalized into large text parts.
        # Encoded images/binaries can be tens of MB and are not natural text.
        search_text = re.sub(r'[A-Za-z0-9+/=_-]{256,}', ' ', '\n'.join(searchable))
        search.append(' '.join(sorted(set(re.findall(r'[\w-]+', search_text.lower())))))
        # Some real steps contain over 1,000 parallel calls. Keep them lazy too.
        if len(encode(step)) > CHUNK_BYTES:
            groups, group, group_size = [], [], 0
            for call in step['calls']:
                call_size = len(encode(call))
                if group and (group_size + call_size > CHUNK_BYTES // 2 or len(group) >= 20):
                    groups.append(group)
                    group, group_size = [], 0
                group.append(call)
                group_size += call_size
            if group:
                groups.append(group)
            if groups:
                step['calls'] = groups[0]
                step['call_parts'] = []
                for i, calls in enumerate(groups[1:], 1):
                    name = f'calls-{step["step_id"]}-{i:04}.json'
                    write(directory / name, calls, check)
                    step['call_parts'].append(name)
        steps.append(step)

    chunk, size, number = [], 0, 0
    for pos, step in enumerate(steps):
        item_size = len(encode(step))
        if chunk and size + item_size > CHUNK_BYTES:
            write(directory / f'steps-{number:04}.json', chunk, check)
            number += 1
            chunk, size = [], 0
        index[pos]['chunk'] = f'steps-{number:04}.json'
        chunk.append(step)
        size += item_size
    if chunk:
        write(directory / f'steps-{number:04}.json', chunk, check)
    write(directory / 'search.json', search, check)
    manifest = {'schema': 2, 'steps': index, 'redacted_fields': redactions,
                'search': 'search.json', 'download': 'trajectory.json.gz'}
    write(directory / 'manifest.json', manifest, check)
    exported = {key: raw.get(key) for key in ('schema_version', 'session_id', 'final_metrics')}
    exported['agent'] = {k: raw.get('agent', {}).get(k) for k in ('name', 'version', 'model_name')}
    exported['steps'] = download_steps
    exported['export_note'] = ('Public export. Host paths normalized to documented aliases. ' if public else 'Local preview. ') + 'Credential/environment values redacted; raw agent extra fields omitted.'
    write(directory / 'trajectory.json.gz', gzip.compress(encode(sanitize(exported, scrubber)), mtime=0), check)
    return len(steps), redactions


def import_snapshot(jobs, check=False, public_output=None):
    scrubber = scrub
    if public_output is not None:
        from publication import PublicText
        public_output = Path(public_output)
        scrubber = PublicText(jobs, scrub)
    final = jobs / 'final-trajectories'
    results_path = jobs / 'traj-analysis/leaderboard-data/results.json'
    results = read(results_path)
    model_metadata_path = results_path.with_name('pricing.json')
    model_metadata_hash = digest(model_metadata_path.read_bytes())
    if model_metadata_hash != results['pricing_sha256']:
        raise ValueError('Model metadata does not match the selected analysis snapshot')
    model_metadata = read(model_metadata_path)['models']
    rows = list(csv.DictReader((final / 'INDEX.csv').open()))
    selected = {(r['task'], r['model']): r for r in rows}
    if len(selected) != len(rows):
        raise ValueError('Duplicate selected task/model')
    runs = {(r['task'], r['model']): r for r in results['runs'] if r['included_in_leaderboard']}
    tasks = results['comparison']['tasks']
    expected = {(task, m['model']) for task in tasks for m in results['models'].values()}
    if set(runs) != expected or set(selected) != expected:
        raise ValueError('Analysis and final selections must cover the same fixed task/model set')
    catalog = {t['name']: t for t in read(ROOT / 'content/tasks/catalog.json')}
    fingerprint = digest((final / 'INDEX.csv').read_bytes() + results_path.read_bytes())[:10]
    release_id = results['observed_at'][:10] + '-local-' + fingerprint
    snapshot = {'schema': 1, 'id': release_id, 'observed_at': results['observed_at'],
                'source_hashes': {'index': digest((final / 'INDEX.csv').read_bytes()),
                                  'results': digest(results_path.read_bytes()),
                                  'model_metadata': model_metadata_hash},
                'tasks': [{k: catalog[t][k] for k in ('name', 'title', 'hardware')} for t in tasks],
                'entries': [], 'trials': []}
    entries = {}
    for key, row in sorted(selected.items()):
        run = runs[key]
        pointer = read(final / row['task'] / row['model_label'] / 'FINAL_RESULT.json')
        if not pointer['valid_run'] or not pointer['publication_eligible'] or pointer['DO_NOT_USE_AS_FINAL']:
            raise ValueError(f'Ineligible final selection: {key}')
        for name in ('task', 'model', 'effort', 'primary_trajectory', 'primary_trajectory_sha256'):
            if row[name] != pointer[name]:
                raise ValueError(f'Selection mismatch: {key} {name}')
        score = float(run['score'])
        if not math.isfinite(score) or not 0 <= score <= 100 or any(
            not math.isclose(score, float(s), abs_tol=1e-8) for s in (row['score'], pointer['score'])
        ):
            raise ValueError(f'Score disagreement: {key}')
        trajectory_bytes = (final / row['primary_trajectory']).read_bytes()
        reward_bytes = (final / pointer['final_reward']).read_bytes()
        if digest(trajectory_bytes) != row['primary_trajectory_sha256'] or digest(reward_bytes) != pointer['final_reward_sha256']:
            raise ValueError(f'Final artifact hash mismatch: {key}')
        raw = json.loads(trajectory_bytes)
        meta = read(final / row['metadata'])
        entry_id = release_id + '-' + row['model_label']
        trial_id = row['task'] + '-' + row['model_label'] + '-' + digest(
            trajectory_bytes + reward_bytes + encode(run['score']))[:12]
        directory = (public_output / 'trials' if public_output else ROOT / 'data/leaderboard/traces') / trial_id
        count, redactions = export_trajectory(raw, directory, check, scrubber, public=public_output is not None)
        export_files((final / row['primary_trajectory']).parent.parent,
                     (final / pointer['final_reward']).parent, directory, scrubber, write, check)
        model_info = model_metadata.get(row['model'], {})
        released = model_info.get('release_date')
        entries[entry_id] = {'id': entry_id, 'model': row['model'], 'name': NAMES.get(row['model'], row['model']),
                             'effort': row['effort'], 'agent': 'Codex', 'agent_version': raw['agent']['version'],
                             'release_date': date.fromisoformat(released).isoformat() if released else None,
                             'release_date_source': model_info.get('page') if released else None,
                             'provider': 'OpenRouter'}
        reward = json.loads(reward_bytes)
        # Analysis/selection scores are 0–100; native verifier rewards are 0–1.
        native_reward = reward['reward'] if isinstance(reward, dict) else reward
        if not math.isclose(100 * float(native_reward), score, abs_tol=1e-7):
            raise ValueError(f'Reward disagrees with final selection: {key}')
        trial = {'id': trial_id, 'entry': entry_id, 'task': row['task'], 'score': score,
                 'valid': True, 'agent_status': meta.get('source_agent_completion_category') or meta.get('agent_completion_status') or meta.get('completion_category'),
                 'agent_seconds': run.get('agent_execution_seconds'),
                 'started_at': run.get('agent_execution_started_at'), 'finished_at': run.get('agent_execution_finished_at'),
                 'tokens': {k: run.get(k) for k in TOKEN_FIELDS}, 'steps': count,
                 'trajectory_url': f'trials/{trial_id}/manifest.json' if public_output else f'/data/leaderboard/traces/{trial_id}/manifest.json',
                 'trajectory_sha256': digest(trajectory_bytes), 'reward_sha256': digest(reward_bytes),
                 'reward': reward, 'redacted_fields': redactions,
                 'configuration': {'agent': 'Codex', 'version': raw['agent']['version'], 'model': row['model'],
                     'effort': row['effort'], 'provider': 'OpenRouter', 'resources': meta.get('resource'),
                     'agent_timeout_sec': meta.get('agent_timeout_sec'),
                     'run_mode': meta.get('run_mode'), 'verifier_commit': pointer.get('verifier_commit'),
                     'coding_commit': meta.get('coding_source_commit'),
                     'task_commit': meta.get('source_task_commit')},
                 }
        write(directory / 'evaluation.json', {'score': score, 'reward': reward, 'configuration': trial['configuration']}, check)
        snapshot['trials'].append(trial)
        if public_output:
            print(f'Prepared {len(snapshot["trials"]):3}/{len(rows)}: {trial_id}', flush=True)
    snapshot['entries'] = sorted(entries.values(), key=lambda e: e['id'])
    if public_output:
        snapshot['publication'] = {'schema': 1, 'path_aliases': {
            'BENCHMARK_ROOT': 'Benchmark checkout', 'EVAL_ROOT': 'Evaluation workspace',
            'WORKSPACE_ROOT': 'Host workspace', 'USER_HOME': 'User home directory'},
            'note': 'Paths use portable aliases. Original source hashes refer to unmodified private records; exported-file hashes are in publication.json.gz.'}
        write(public_output / 'snapshot.json', snapshot, check)
    else:
        write(ROOT / 'content/leaderboard/releases' / f'{release_id}.json', snapshot, check)
        write(ROOT / 'content/leaderboard/release.json', snapshot, check)
    print(f"{'Verified' if check else 'Exported'} {len(rows)} trials / {len(tasks)} tasks / {len(entries)} models: {release_id}")
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', required=True, type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    import_snapshot(args.jobs, args.check)


if __name__ == '__main__':
    main()
