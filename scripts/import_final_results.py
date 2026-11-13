"""Prepare the selected models directly from the current final archive.

No evaluation jobs are changed and no network requests are made. Publication is
a separate, explicit step in publish_final_results.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

from export_trial_files import export_files, sanitize
from import_results import ROOT, NAMES, TOKEN_FIELDS, digest, encode, export_trajectory, read, scrub, write
from leaderboard_costs import calculate
from prepare_hf_release import finalize, referenced_files
from publication import CURRENT_RELEASE, DEFAULT_PACKAGE, PublicText, load_package, safe_path
from claude_code_usage import claude_usage

MODELS = ('openai/gpt-6-luna', 'openai/gpt-6.1-terra', 'gpt-6.1-sol', 'kimi-k3.1-pro',
          'anthropic/claude-opus-5.5', 'gpt-6-astra', 'deepseek/deepseek-v4.1-flash-1017')
DEFAULT_FINAL = Path('/data/Search-SWE-Workspace/Search-SWE/run-eval-release/Search-SWE/jobs/final-trajectories')
CONTENT = ROOT / 'content/leaderboard'
AGENT_TIME_BUDGET_ASSIGNMENTS = {
    'd3f3eb57779186e628427437bba10ee3a085739d7745e555bd2d709a40dac54d': 'spoken-query-search',
    'd047ea53a65844db9d17be5eb00c580bab4909fa888fd35e396d72d85b07ac77': 'agentic-search',
    '494754ffb91d8f70e07c6b64a438de79c2afe48a65412bbbc68f213cea3b8692': 'scientific-paper-qa',
    'a817d496cb32b56606961dc410cdb77bb53922a294931751c6bd424cc8a7e428': 'visual-document-qa',
    '7520c7cb474837fccbd554b696625c79a9f699c74ed4277b178980365d065692': 'evolving-personal-memory',
    'a697b8a84f15c325bd97f8978d2fa52735db4cd6bf6c12116ba37e3eaaf7063c': 'incremental-vector-search',
    '6ef74415d53b1b913f4c19cd76262feac8302fbe73e9fe88e86783e81ce0b972': 'long-pdf-evidence-vectorless',
    'f5a3cdc50c401e7f0c341e6730f407b2743012b4f72ee2193083ce75aba29ac8': 'paper-metadata-retrieval',
}


def entry_model(row):
    if row['model'] == 'anthropic/claude-opus-5':
        if (row['task'] != 'constrained-molecular-search' or
                row.get('model_label') != 'claude-opus-5.5-claude-code-max'):
            raise ValueError('Unapproved Opus model substitution')
        return 'anthropic/claude-opus-5.5'
    return row['model']


def selected_rows(final, tasks):
    with (final / 'INDEX.csv').open() as source:
        rows = [r for r in csv.DictReader(source)
                if r['model'] in (*MODELS, 'anthropic/claude-opus-5')
                and (r['model'] != 'deepseek/deepseek-v4.1-flash-1017'
                     or r.get('model_label') == 'deepseek-v4.1-flash-1017-codex-max')]
    keys = [(r['task'], entry_model(r)) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != {(t, m) for t in tasks for m in MODELS}:
        raise ValueError('Selected models must each cover exactly the complete task catalog')
    return sorted(rows, key=lambda r: (r['task'], r['model']))


def verified_bytes(path, expected):
    data = path.read_bytes()
    if len(data) != expected['bytes'] or digest(data) != expected['sha256']:
        raise ValueError(f'Archived source changed: {path.name}')
    return data


def coding_session(trial_root):
    # Some recovered native exports retain the original-codex-sessions name.
    sessions = sorted(p for name in ('sessions', 'original-codex-sessions')
                      for p in (trial_root / 'agent' / name).rglob('*.jsonl'))
    if len(sessions) != 1:
        raise ValueError('Expected exactly one original coding session per selected trial')
    return sessions[0]


def coding_provider(pointer, events, session_id):
    metadata = [e['payload'] for e in events if e.get('type') == 'session_meta']
    expected, label = {'openrouter': ('openrouter', 'OpenRouter'),
                       'direct': ('openai', 'OpenAI')}[pointer['provider']]
    if (len(metadata) != 1 or metadata[0].get('model_provider') != expected or
            metadata[0].get('id') != session_id):
        raise ValueError('Coding session identity/provider differs from the selected trajectory')
    return label


def session_usage(events):
    """Count explicit response receipts once, including a receipt after the last UI counter."""
    requests, starts, finishes = {}, [], []
    last_thread = None
    for event in events:
        payload = event.get('payload', {})
        if event.get('type') == 'token_usage_record':
            response = payload.get('response_id')
            usage = payload.get('usage', {})
            if (not response or any(type(usage.get(k)) is not int or usage[k] < 0 for k in TOKEN_FIELDS[:-1]) or
                    usage['total_tokens'] != usage['input_tokens'] + usage['output_tokens'] or
                    usage['cached_input_tokens'] + usage['cache_write_input_tokens'] > usage['input_tokens']):
                raise ValueError('Invalid native response usage')
            if response in requests and requests[response] != usage:
                raise ValueError('Conflicting repeated response usage')
            requests[response] = usage
            last_thread = payload.get('thread_token_usage')
        elif event.get('type') == 'event_msg':
            if payload.get('type') == 'task_started':
                starts.append(event['timestamp'])
            elif payload.get('type') == 'task_complete':
                finishes.append(event['timestamp'])
    if not requests:
        raise ValueError('No per-response coding usage in the selected session')
    totals = Counter()
    for usage in requests.values():
        totals.update({k: usage[k] for k in TOKEN_FIELDS[:-1]})
    if last_thread is None or any(totals[k] != last_thread.get(k) for k in TOKEN_FIELDS[:-1]):
        raise ValueError('Response receipts disagree with the final native thread counter')
    totals['response_count'] = len(requests)
    return dict(totals), [{'response_id': k, 'usage': v} for k, v in requests.items()], starts, finishes


def coding_time(result, starts, finishes):
    execution = result.get('agent_execution') or {}
    start, finish = execution.get('started_at'), execution.get('finished_at')
    basis = 'Harbor agent_execution'
    if not start or not finish:
        start = starts[0] if len(starts) == 1 else None
        finish = finishes[0] if len(finishes) == 1 else None
        basis = 'Native coding session task_started/task_complete'
    if not start or not finish:
        return start, finish, None, 'Original coding end time unavailable; regrade duration is excluded.'
    seconds = (datetime.fromisoformat(finish) - datetime.fromisoformat(start)).total_seconds()
    if seconds < 0 or not math.isfinite(seconds):
        raise ValueError('Invalid original coding duration')
    return start, finish, seconds, basis


def apply_agent_time_override(trial):
    # Maintainer-approved assignments are bound to the reviewed trajectories.
    # Preserve timestamps, termination status and any already recorded duration.
    if (AGENT_TIME_BUDGET_ASSIGNMENTS.get(trial['trajectory_sha256']) == trial['task'] and
            trial['agent_seconds'] is None):
        trial['agent_seconds'] = 7200
        trial['agent_time_basis'] = ('7200-second task budget assigned by the benchmark maintainer; '
                                   'original coding end timestamp unavailable; regrade duration excluded.')
        if trial['task'] == 'visual-document-qa':
            trial['agent_time_basis'] = ('7200-second task budget assigned by the benchmark maintainer; '
                                        'original Harbor AgentTimeoutError confirms 7200.519128 seconds; '
                                        'selected regrade has no coding timing; regrade duration excluded.')


def prepare(final, package, base_package=None):
    final, package = final.resolve(), package.resolve()
    catalog = read(ROOT / 'content/tasks/catalog.json')
    rows = selected_rows(final, {t['name'] for t in catalog})
    if len(catalog) != 47:
        raise ValueError('This publication expects 47 tasks')
    policy = read(CONTENT / 'selection.json')
    if policy.get('included_models') != list(MODELS):
        raise ValueError('Website selection must explicitly contain the selected models')
    metadata = read(CONTENT / 'model-metadata.json')
    archive = read(final / 'MANIFEST.json')
    if archive['index_sha256'] != digest((final / 'INDEX.csv').read_bytes()):
        raise ValueError('Archive manifest and index differ')
    settings = {(s['task'], s['model'], s['model_label']): s for s in archive['settings']}
    source_hashes = {'index': archive['index_sha256'], 'archive': digest((final / 'MANIFEST.json').read_bytes()),
                     'model_metadata': digest(encode(metadata)), 'selection': digest(encode(policy))}
    release_id = policy['updated_at'] + '-selected-' + digest(encode(source_hashes))[:10]
    # Appending retains the physical corpus directory. Immutable commit URLs keep
    # the previously published snapshot available without duplicating its remote payloads.
    release_path = load_package(base_package)['release_path'] if base_package else CURRENT_RELEASE
    if (package / 'publication.json.gz').exists():
        manifest = load_package(package)
        if manifest['source_hashes'] != source_hashes or manifest['release_path'] != release_path:
            raise ValueError('Package has different source records; use a new --package directory')
        snapshot = read(package / manifest['release_path'] / 'snapshot.json')
        referenced_files(package / manifest['release_path'], snapshot)
        return snapshot, manifest
    # Retrying an interrupted export is safe only in this exact release directory.
    if package.exists() and any(p.name != 'releases' for p in package.iterdir()):
        raise ValueError('Unrecognized incomplete package; use a new --package directory')
    if (package / 'releases').exists() and any(p.name != Path(release_path).name for p in (package / 'releases').iterdir()):
        raise ValueError('Incomplete package belongs to another source snapshot')
    public = PublicText(final.parent, scrub)
    snapshot = {'schema': 1, 'id': release_id, 'observed_at': archive['at'], 'source_hashes': source_hashes,
                'selection': policy, 'tasks': [{k: t[k] for k in ('name', 'title', 'hardware')} for t in catalog],
                'entries': [], 'trials': [], 'publication': {'schema': 1,
                    'path_aliases': {'BENCHMARK_ROOT': 'Benchmark checkout', 'EVAL_ROOT': 'Evaluation workspace',
                                    'WORKSPACE_ROOT': 'Host workspace', 'USER_HOME': 'User home directory'},
                    'note': 'Sanitized public text; source hashes identify the unmodified private archive.'}}
    entries, usage_rows = {}, []
    previous = {}
    if base_package:
        base_snapshot = read(base_package / release_path / 'snapshot.json')
        base_usage = read(base_package.with_suffix('.usage.json'))
        previous = {(t['task'], t['configuration']['model']): t for t in base_snapshot['trials']}
        entries.update({e['id']: e for e in base_snapshot['entries']})
        usage_rows.extend(base_usage['rows'])
        # Reuse immutable payloads, including their original redaction/export
        # format. Re-importing old trials would change published evidence bytes.
        shutil.copytree(base_package / release_path / 'trials', package / release_path / 'trials', dirs_exist_ok=True)
    for number, row in enumerate(rows, 1):
        old = previous.get((row['task'], row['model']))
        if old:
            if (old['trajectory_sha256'] != row['primary_trajectory_sha256'] or
                    not math.isclose(old['score'], float(row['score']), abs_tol=1e-8)):
                raise ValueError('Previously published selection changed; cannot append')
            apply_agent_time_override(old)
            snapshot['trials'].append(old)
            continue
        root = safe_path(final, row['task'] + '/' + row['model_label'])
        pointer = read(safe_path(final, row['metadata']))
        if pointer.get('status') != 'valid' or pointer.get('DO_NOT_USE_AS_FINAL'):
            raise ValueError(f'Invalid final selection: {row["task"]} / {row["model"]}')
        for key in ('task', 'model', 'effort', 'primary_trajectory_sha256'):
            if pointer[key] != row[key]:
                raise ValueError(f'Selection mismatch: {row["task"]} / {key}')
        manifest_data = safe_path(final, row['file_manifest']).read_bytes()
        if digest(manifest_data) != row['file_manifest_sha256']:
            raise ValueError('Source file inventory changed')
        inventory = {f['relative']: f for f in json.loads(manifest_data)['files']}
        output = safe_path(root, pointer['output'])
        trial_root = safe_path(root, pointer['selected_native_trial'])

        def source(path):
            return verified_bytes(path, inventory[path.relative_to(output).as_posix()])

        trajectory_path = safe_path(final, row['primary_trajectory'])
        if trajectory_path != safe_path(root, pointer['primary_trajectory']) or trajectory_path != trial_root / 'agent/trajectory.json':
            raise ValueError('Primary trajectory does not follow the selected native trial')
        trajectory = source(trajectory_path)
        if digest(trajectory) != row['primary_trajectory_sha256']:
            raise ValueError('Primary trajectory hash changed')
        reward_path = safe_path(root, pointer['selected_reward'])
        reward_bytes = source(reward_path)
        reward = json.loads(reward_bytes)
        native = reward['reward'] if isinstance(reward, dict) else reward
        score = float(row['score'])
        if (not math.isfinite(score) or not 0 <= score <= 100 or
                not math.isclose(score, float(pointer['score']), abs_tol=1e-8) or
                not math.isclose(score, 100 * float(native), abs_tol=1e-7)):
            raise ValueError('Selected score disagrees with the final native reward')
        result = json.loads(source(safe_path(root, pointer['selected_result'])))
        if result['task_name'].removeprefix('search-swe/') != row['task'] or not (result.get('verifier') or {}).get('finished_at'):
            raise ValueError('Native verification has not completed for the selected task')
        native_result_reward = result['verifier_result']['rewards']['reward']
        if not math.isclose(float(native_result_reward), float(native), abs_tol=1e-9):
            raise ValueError('Native result and selected reward differ')
        raw = json.loads(trajectory)
        if raw['agent']['model_name'] != row['model']:
            raise ValueError('Selected trajectory model differs')
        extra_usage = None
        usage_note = 'Per-response native coding receipts, deduplicated by response ID.'
        if row['model'] == 'kimi-k3.1-pro' or row['model'].startswith('anthropic/claude-opus-5'):
            agent = 'Claude Code'
            provider = 'OpenRouter' if row['model'].startswith('anthropic/') else metadata['models'][row['model']]['provider']
            if (raw['agent']['name'] != 'claude-code' or raw['agent']['version'] != '2.1.309' or
                    (provider == 'OpenRouter' and (pointer.get('provider') != 'openrouter' or row['effort'] != 'max')) or
                    (row['model'] == 'kimi-k3.1-pro' and provider != 'Moonshot AI')):
                raise ValueError('Claude Code provider or harness differs from the confirmed configuration')
            if provider == 'OpenRouter':
                coding_config = json.loads(source(trial_root / 'config.json'))['agent']
                if (coding_config['name'] != 'scripts.evaluation.harbor_agents:ManagedOpenRouterClaudeCode' or
                        coding_config['model_name'] != row['model'] or
                        coding_config['kwargs'].get('version') != '2.1.309' or
                        coding_config['kwargs'].get('reasoning_effort') != 'max'):
                    raise ValueError('Opus coding configuration differs from the selected model/provider/effort')
            harness_path = trial_root / 'agent/harness.json'
            if harness_path.exists():
                harness = json.loads(source(harness_path))
                if harness['actual_version'] != '2.1.309' or harness['requested_version'] != '2.1.309':
                    raise ValueError('Claude Code installed harness version differs')
            session_paths = sorted((trial_root / 'agent/sessions').rglob('*.jsonl'))
            if not any(p.stem == raw['session_id'] for p in session_paths):
                raise ValueError('Original Claude Code main session missing')
            sessions = [[json.loads(line) for line in source(p).splitlines() if line.strip()] for p in session_paths]
            stream = []
            for line in source(trial_root / 'agent/claude-code.txt').splitlines():
                try:
                    stream.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # CLI progress lines are not JSON events.
            tokens, requests, extra_usage, start, finish, completed, usage_note = claude_usage(
                sessions, stream, raw['session_id'], row['model'], raw['agent']['version'])
            starts, finishes = [start] if start else [], [finish] if finish else []
            start, finish, seconds, time_basis = coding_time(result, starts, finishes)
            if time_basis.startswith('Native coding session'):
                time_basis = 'Original Claude Code cost-state startTime/totalDuration; regrade duration excluded.'
        else:
            agent = 'Codex'
            if raw['agent']['name'] != 'codex' or raw['agent']['version'] != '0.164.0' or row['effort'] != 'max':
                raise ValueError('Codex harness or effort differs from the selected configuration')
            events = [json.loads(line) for line in source(coding_session(trial_root)).splitlines() if line.strip()]
            provider = coding_provider(pointer, events, raw['session_id'])
            tokens, requests, starts, finishes = session_usage(events)
            completed = bool(finishes)
            start, finish, seconds, time_basis = coding_time(result, starts, finishes)
        entry_id = release_id + '-' + row['model_label']
        trial_id = row['task'] + '-' + row['model_label'] + '-' + digest(trajectory + reward_bytes)[:12]
        destination = package / release_path / 'trials' / trial_id
        count, redactions = export_trajectory(raw, destination, scrubber=public, public=True)
        files = export_files(trial_root, reward_path.parent, destination, public, write)
        folders = {'agent': trial_root / 'agent', 'verifier': reward_path.parent, 'artifacts': trial_root / 'artifacts'}
        for group, items in files['groups'].items():
            for item in items:
                path = folders.get(group, trial_root) / item['name']
                expected = inventory[path.relative_to(output).as_posix()]
                if item['bytes'] != expected['bytes'] or (item['source_sha256'] and item['source_sha256'] != expected['sha256']):
                    raise ValueError(f'Exported evidence differs from source inventory: {group}/{item["name"]}')
        model = entry_model(row)
        info = metadata['models'][model]
        if model == 'deepseek/deepseek-v4.1-flash-1017':
            if provider != 'OpenRouter':
                raise ValueError('DeepSeek selection must retain its OpenRouter routing provenance')
            provider = 'DeepSeek (via OpenRouter)'
        entry = {'id': entry_id, 'model': model, 'name': NAMES[model], 'effort': row['effort'],
                 'agent': agent, 'agent_version': raw['agent']['version'], 'provider': provider,
                 'release_date': info['release_date'], 'release_date_source': info['source']}
        if entry_id in entries and entries[entry_id] != entry:
            raise ValueError('Mixed agent configurations in one model entry')
        entries[entry_id] = entry
        selected = settings[(row['task'], row['model'], row['model_label'])]['selection']
        qualification = {k: selected.get(k) or pointer.get(k) for k in
                         ('qualification_flag', 'judge_semantic_quality_flag', 'qualification_limitations')}
        qualification = sanitize({k: v for k, v in qualification.items() if v}, public)
        exception = (result.get('exception_info') or {}).get('exception_type')
        fm = raw.get('final_metrics', {})
        if agent == 'Codex' and any(tokens[k] != fm.get(f) for k, f in [('input_tokens', 'total_prompt_tokens'), ('output_tokens', 'total_completion_tokens')]):
            usage_note += ' The ATIF summary lags the final receipt; totals include that recorded response.'
        config = {'agent': agent, 'version': raw['agent']['version'], 'model': row['model'],
                  'effort': row['effort'], 'provider': provider, 'run_mode': pointer.get('mode') or 'native',
                  'task_commit': pointer.get('source_revision'), 'verifier_commit': pointer.get('source_revision')}
        trial = {'id': trial_id, 'entry': entry_id, 'task': row['task'], 'score': score, 'valid': True,
                 'agent_status': exception or ('completed' if completed else 'Completion not recorded in the archived session'),
                 'agent_seconds': seconds, 'started_at': start, 'finished_at': finish, 'agent_time_basis': time_basis,
                 'tokens': tokens, 'usage_note': usage_note, 'steps': count, 'configuration': config,
                 'qualification': qualification, 'trajectory_url': f'trials/{trial_id}/manifest.json',
                 'trajectory_sha256': digest(trajectory), 'reward_sha256': digest(reward_bytes),
                 'reward': sanitize(reward, public), 'redacted_fields': redactions}
        apply_agent_time_override(trial)
        if model != row['model']:
            if not pointer.get('actual_model_substitution') or pointer.get('requested_scoreboard_model') != model:
                raise ValueError('Model substitution lacks explicit archive provenance')
            substitution = next(s for s in policy['model_substitutions'] if
                                s['task'] == row['task'] and s['actual_model'] == row['model'] and s['requested_model'] == model)
            trial['model_substitution'] = substitution
        write(destination / 'evaluation.json', {k: trial[k] for k in ('score', 'reward', 'configuration', 'qualification')})
        snapshot['trials'].append(trial)
        usage_rows.append({'task': row['task'], 'model': row['model'], 'effort': row['effort'],
                           'primary_trajectory_sha256': digest(trajectory), 'requests': requests})
        if extra_usage is not None:
            usage_rows[-1]['aggregate_remainder'] = extra_usage
        print(f'Prepared {number:3}/{len(rows)}: {row["task"]} / {row["model_label"]}', flush=True)
    snapshot['entries'] = sorted(entries.values(), key=lambda e: e['id'])
    # Freeze usage outside the upload package, so source receipts are never uploaded accidentally.
    usage = {'schema': 1, 'rows': usage_rows}
    write(package.with_suffix('.usage.json'), usage)
    calculate(snapshot, usage, read(CONTENT / 'official-pricing.json'))
    manifest = finalize(package, snapshot, release_path)
    return snapshot, manifest


def install_preview(package, snapshot, manifest):
    from build_leaderboard import generate, write_pages
    source = encode(snapshot)
    price_source = (CONTENT / 'official-pricing.json').read_bytes()
    usage_source = package.with_suffix('.usage.json').read_bytes()
    costs = calculate(snapshot, json.loads(usage_source), json.loads(price_source))
    supplement = {'schema': 1, 'snapshot_id': snapshot['id'], 'snapshot_sha256': digest(source),
                  'pricing_sha256': digest(price_source), 'usage_sha256': digest(usage_source), 'trials': costs}
    backup = package.with_suffix('.previous-site.json')
    if not backup.exists():
        write(backup, {name: read(CONTENT / name) for name in ('release.json', 'costs.json', 'storage.json')})
    write(CONTENT / 'release.json', source)
    write(CONTENT / 'releases' / (snapshot['id'] + '.json'), source)
    write(CONTENT / 'costs.json', (json.dumps(supplement, indent=2, sort_keys=True) + '\n').encode())
    write(CONTENT / 'storage.json', {'provider': 'preview', 'snapshot_id': snapshot['id'],
        'source_hashes': snapshot['source_hashes'],
        'data_base_url': '/' + package.relative_to(ROOT).as_posix() + '/' + manifest['release_path']})
    pages = generate()
    for old in (CONTENT / 'releases').glob('*.json'):
        if old.stem != snapshot['id']:
            old.unlink()
    changed, removed = write_pages(pages)
    print(f'Homepage preview ready: {changed} files generated, {removed} obsolete pages removed. HF unchanged.')
    for entry in snapshot['entries']:
        trials = [t for t in snapshot['trials'] if t['entry'] == entry['id']]
        print(f'{entry["name"]}: {len(trials)}/47 tasks, mean score {sum(t["score"] for t in trials)/len(trials):.8f}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--final-dir', type=Path, default=DEFAULT_FINAL)
    parser.add_argument('--package', type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument('--base-package', type=Path, help='Retain this verified package release directory for append')
    parser.add_argument('--check', action='store_true', help='Validate the prepared public package without writing')
    args = parser.parse_args()
    package = args.package.resolve()
    if args.check:
        manifest = load_package(package)
        referenced_files(package / manifest['release_path'], read(package / manifest['release_path'] / 'snapshot.json'))
        from upload_hf_release import check_site_snapshot
        check_site_snapshot(package, manifest)
        print('Public package and homepage snapshot verified; no network requests or writes.')
    else:
        snapshot, manifest = prepare(args.final_dir, package, args.base_package)
        install_preview(package, snapshot, manifest)


if __name__ == '__main__':
    main()
