"""Publish the reviewed 43-task Hy4 export plus four selected local trials.

Source records stay unchanged. Final counters repair derived ATIF summaries;
CLI-only transcripts never acquire invented per-response output counts.
Upload uses the existing append pipeline and does not stage or commit Git files.
"""
from __future__ import annotations

import argparse
import copy
import csv
import gzip
import json
import math
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from claude_code_usage import claude_usage, normalized
from append_hf_trajectories import append_plan
from export_trial_files import export_files
from import_final_results import DEFAULT_FINAL, coding_time, install_preview, verified_bytes
from import_results import ROOT, TOKEN_FIELDS, digest, encode, export_trajectory, read, scrub, write
from leaderboard_costs import calculate
from prepare_hf_release import finalize
from publication import CURRENT_RELEASE, REPO_ID, PublicText, load_package, safe_path

CONTENT = ROOT / 'content/leaderboard'
MODEL = 'tencent/hy4'
VERSION = '2.1.309'
SETTING = 'hy4-claude-code-openrouter-high'
BASE_PACKAGE = ROOT / '.build/hf-trajectories-mimo'
PACKAGE = ROOT / '.build/hf-trajectories-hy4'
COMMUNITY = ROOT / '.build/hy4-review-20261117/unpacked/search-swe-hy4-claude-code'


def community_usage(sessions, stream, session_id):
    """Prefer final counters; keep individual receipts only when actually available."""
    requests, states = {}, []
    for events in sessions:
        for event in events:
            if event.get('type') == 'cost-state' and event.get('sessionId') == session_id:
                states.append(event)
            if event.get('type') == 'api-request':
                effort = (event.get('params', {}).get('output_config') or {}).get('effort')
                if effort != 'high':
                    raise ValueError('Community request effort differs from high')
            if event.get('type') != 'assistant':
                continue
            message = event['message']
            if message.get('model') == '<synthetic>':
                if any(message['usage'].get(k) != 0 for k in
                       ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')):
                    raise ValueError('Synthetic message has nonzero or missing usage')
                continue
            if message.get('model') != 'hy4' or event.get('version') != VERSION:
                raise ValueError('Community native model/version differs')
            key = message.get('id')
            if not key:
                raise ValueError('Community response has no message ID')
            usage = normalized(message['usage'])
            if key in requests and any(usage[k] < requests[key][k] for k in usage):
                raise ValueError('Regressing community response counters')
            requests[key] = usage
    if len(states) > 1:
        raise ValueError('Ambiguous community final counters')
    inits = [e for e in stream if e.get('type') == 'system' and e.get('subtype') == 'init']
    if stream and (not inits or any(e.get('session_id') != session_id or e.get('model') != 'hy4'
            or e.get('claude_code_version') != VERSION for e in inits)):
        raise ValueError('Community CLI identity/model/version differs')
    results = [e for e in stream if e.get('type') == 'result']
    if any(e.get('session_id') != session_id for e in results):
        raise ValueError('Community CLI final session differs')
    counters = [e['modelUsage'] for e in states + results[-1:]]
    previous = None
    for result in results:
        if set(result['modelUsage']) != {'hy4'}:
            raise ValueError('Unexpected community CLI model')
        current = normalized(result['modelUsage']['hy4'], aggregate=True)
        if previous and any(current[k] < previous[k] for k in current):
            raise ValueError('Regressing community CLI final counters')
        previous = current
    totals = Counter()
    for usage in requests.values():
        totals.update(usage)
    remainder = None
    if counters:
        if any(set(c) != {'hy4'} for c in counters):
            raise ValueError('Unexpected community final model')
        final = [normalized(c['hy4'], aggregate=True) for c in counters]
        if any(c != final[0] for c in final):
            raise ValueError('Community CLI and saved final counters disagree')
        remainder = {k: final[0][k] - totals[k] for k in TOKEN_FIELDS[:-1]}
        if any(n < 0 for n in remainder.values()):
            raise ValueError('Community final counters are smaller than recorded responses')
        totals.update(remainder)
    if not requests and (sessions or not counters):
        raise ValueError('No usable community coding usage')
    totals['response_count'] = len(requests)
    note = ('Claude Code final modelUsage counters; recorded main/subagent responses deduplicated by message ID. '
            'Unitemized background/compaction usage is included once. Reasoning is included in output; '
            'the endpoint does not meter it separately.')
    if not requests:
        note += (' Native session JSONL was not collected. The complete CLI transcript supplies final totals; '
                 'per-response output usage remains unknown and the recorded complete-response count is zero.')
    return (dict(totals), [{'response_id': k, 'usage': v} for k, v in requests.items()],
            remainder, not requests, states[0] if states else None, bool(results), note)


def repaired_trajectory(raw, tokens, cli_only=False):
    """Repair the public derivative while retaining the source transcript unchanged."""
    raw = copy.deepcopy(raw)
    raw['agent']['version'] = VERSION
    raw['final_metrics'].update(total_prompt_tokens=tokens['input_tokens'],
                                total_completion_tokens=tokens['output_tokens'],
                                total_cached_tokens=tokens['cached_input_tokens'])
    raw['final_metrics'].setdefault('extra', {}).update(
        total_cache_creation_input_tokens=tokens['cache_write_input_tokens'],
        total_cache_read_input_tokens=tokens['cached_input_tokens'])
    if cli_only:
        for step in raw['steps']:
            if step.get('source') == 'agent' and step.get('metrics'):
                step['metrics']['completion_tokens'] = None
                step['metrics'].pop('cost_usd', None)
    raw['export_note'] = ('Derived harness version and final token totals reconciled with preserved native/CLI evidence. '
                          'Per-step counts are not allocated from final totals.')
    return raw


def community_inventory(root, evidence):
    for name, field in [('index.json', 'index_sha256'), ('manifest.json', 'manifest_sha256')]:
        if digest((root / name).read_bytes()) != evidence[field]:
            raise ValueError(f'Reviewed community source changed: {name}')
    inventory = {f['path']: f for f in read(root / 'manifest.json')}
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != set(inventory) | {'manifest.json', 'SHA256SUMS'}:
        raise ValueError('Community source file set changed')
    for relative, expected in inventory.items():
        verified_bytes(safe_path(root, relative), expected)
    return read(root / 'index.json')


def local_rows(final, evidence):
    archive = read(final / 'MANIFEST.json')
    if archive['index_sha256'] != digest((final / 'INDEX.csv').read_bytes()):
        raise ValueError('Local final archive index changed without its manifest')
    with (final / 'INDEX.csv').open() as source:
        rows = [r for r in csv.DictReader(source) if r['model'] == MODEL and r['model_label'] == SETTING]
    if len(rows) != 4 or {r['task'] for r in rows} != set(evidence['local_trials']):
        raise ValueError('Expected exactly the four reviewed local Hy4 trials')
    for row in rows:
        expected = evidence['local_trials'][row['task']]
        if row['primary_trajectory_sha256'] != expected['trajectory_sha256'] or row['effort'] != 'high':
            raise ValueError('Reviewed local Hy4 selection changed')
        data = safe_path(final, row['file_manifest']).read_bytes()
        if digest(data) != row['file_manifest_sha256'] or digest(data) != expected['file_manifest_sha256']:
            raise ValueError('Reviewed local Hy4 file manifest changed')
        root = safe_path(final, row['task'] + '/' + row['model_label'])
        pointer = read(safe_path(final, row['metadata']))
        if (pointer.get('status') != 'valid' or pointer.get('DO_NOT_USE_AS_FINAL') or
                any(pointer[k] != row[k] for k in ('task', 'model', 'effort', 'primary_trajectory_sha256'))):
            raise ValueError('Invalid local Hy4 final pointer')
        output = safe_path(root, pointer['output'])
        for item in json.loads(data)['files']:
            verified_bytes(safe_path(output, item['relative']), item)
    return rows


def usage_row(task, trajectory_sha, tokens, requests, remainder, aggregate_only=False):
    row = {'task': task, 'model': MODEL, 'effort': 'high',
           'primary_trajectory_sha256': trajectory_sha, 'requests': requests}
    if remainder is not None:
        row['aggregate_remainder'] = remainder
    if aggregate_only:
        row['usage_basis'] = 'final_model_usage_only'
    return row


def trial_record(task, entry, trajectory, reward, reward_bytes, tokens, seconds, start, finish,
                 time_basis, status, note, configuration, steps, redactions, trial_id):
    value = reward['reward'] if isinstance(reward, dict) else reward
    score = 100 * float(value)
    if not math.isfinite(score) or not 0 <= score <= 100 or not math.isfinite(seconds) or seconds < 0:
        raise ValueError('Invalid Hy4 score or original coding duration')
    return {'id': trial_id, 'entry': entry, 'task': task, 'score': score, 'valid': True,
            'agent_status': status, 'agent_seconds': seconds, 'started_at': start, 'finished_at': finish,
            'agent_time_basis': time_basis, 'tokens': tokens, 'usage_note': note, 'steps': steps,
            'configuration': configuration, 'qualification': {},
            'trajectory_url': f'trials/{trial_id}/manifest.json', 'trajectory_sha256': digest(trajectory),
            'reward_sha256': digest(reward_bytes), 'reward': reward, 'redacted_fields': redactions}


def import_community(root, row, entry, destination, public):
    task = row['task']
    source = root / 'tasks' / task
    trajectory = (source / 'trajectory.json').read_bytes()
    raw = read(source / 'trajectory.json')
    if raw['agent']['name'] != 'claude-code' or raw['agent']['model_name'] != 'hy4':
        raise ValueError('Community ATIF model/harness differs')
    if row['reasoning_effort'] != 'high' or row['status'] != 'valid' or not row['reward_consistent']:
        raise ValueError('Invalid community final selection')
    session_paths = sorted((source / 'harness/claude-code-session').rglob('*.jsonl'))
    if session_paths and not any(p.stem == raw['session_id'] for p in session_paths):
        raise ValueError('Community ATIF has no corresponding main session')
    sessions = [[json.loads(line) for line in p.read_bytes().splitlines() if line.strip()]
                for p in session_paths]
    cli = source / 'harness/claude-code-cli-output.json'
    stream = read(cli) if cli.exists() else []
    tokens, requests, remainder, aggregate_only, state, completed, note = community_usage(sessions, stream, raw['session_id'])
    reward_path = source / 'verifier/final/reward.json'
    if not reward_path.exists():
        reward_path = source / 'verifier/final/reward.txt'
    reward_bytes = reward_path.read_bytes()
    reward = read(reward_path)
    value = reward['reward'] if isinstance(reward, dict) else reward
    if not math.isclose(float(value), row['reward'], abs_tol=1e-9):
        raise ValueError('Community selected reward differs from source index')
    trial_id = task + '-hy4-claude-code-high-' + digest(trajectory + reward_bytes)[:12]
    destination = destination / trial_id
    steps, redactions = export_trajectory(repaired_trajectory(raw, tokens, aggregate_only), destination,
                                           scrubber=public, public=True)
    files = export_files(source, reward_path.parent, destination, public, write, extra_files={
        'agent': {'trajectory.source.json': source / 'trajectory.json',
                  **{p.relative_to(source / 'harness').as_posix(): p for p in (source / 'harness').rglob('*') if p.is_file()}},
        'config': {p.name: p for p in (source / 'config').iterdir() if p.is_file()},
        'log': {p.name: p for p in (source / 'results').iterdir() if p.is_file()},
        'verifier': {'evaluation-summary.json': source / 'verifier/evaluation-summary.json'}})
    files['notes']['agent'] = 'Preserved community Claude Code transcript, recorded native sessions where available, and original ATIF source.'
    files['notes']['config'] = 'Community runner configuration and original task settings. Environment values are redacted.'
    files['notes']['log'] = 'Original community solve-run result records.'
    files['regraded_separately'] = row['scoring'] not in {'solve run', 're-solve (endpoint B)'}
    files['notes']['verifier'] = 'Final selected reward, judge records and scoring-run summary.'
    # The source package lists some artifacts whose binary/large contents were not exported.
    for item in read(source / 'artifacts/listing.json')['files']:
        name = 'files/' + item['path']
        if not item.get('included'):
            files['groups']['artifacts'].append({'name': name, 'bytes': item['bytes'], 'parts': [],
                'download': None, 'source_sha256': None, 'unavailable': 'Listed only in the community source export.'})
    write(destination / 'files/index.json', files)
    run = read(source / 'harness/claude-code-run.json')
    seconds = run['execution_time']
    if abs(seconds - row['agent_wall_seconds']) > .11:
        raise ValueError('Community original coding duration differs')
    start = finish = None
    if state:
        start = datetime.fromtimestamp(state['startTime'] / 1000, timezone.utc).isoformat()
        finish = datetime.fromtimestamp((state['startTime'] + state['totalDuration']) / 1000, timezone.utc).isoformat()
    config = {'agent': 'Claude Code', 'version': VERSION, 'model': MODEL, 'effort': 'high', 'provider': 'Tencent',
              'run_mode': 'regrade' if files['regraded_separately'] else 'native', 'task_commit': '2b5dabe',
              'verifier_commit': '7cd1262' if task == 'query-encoder-alignment' else '2b5dabe'}
    status = 'completed' if run['success'] else ('AgentTimeoutError' if run.get('failure_kind') == 'timeout' else
              run.get('failure_kind') or 'Agent exited before recording completion')
    trial = trial_record(task, entry, trajectory, reward, reward_bytes, tokens, seconds, start, finish,
        'Original community runner agent execution_time; separate verification excluded. Timestamps, when available, are the recorded harness session bounds.',
        status, note, config, steps, redactions, trial_id)
    write(destination / 'evaluation.json', {k: trial[k] for k in ('score', 'reward', 'configuration', 'qualification')})
    return trial, usage_row(task, digest(trajectory), tokens, requests, remainder, aggregate_only)


def import_local(final, row, entry, destination, public):
    root = safe_path(final, row['task'] + '/' + row['model_label'])
    pointer = read(safe_path(final, row['metadata']))
    source = safe_path(root, pointer['selected_native_trial'])
    trajectory = safe_path(final, row['primary_trajectory']).read_bytes()
    raw = read(source / 'agent/trajectory.json')
    if digest(trajectory) != row['primary_trajectory_sha256']:
        raise ValueError('Local trajectory hash differs')
    if any(raw['agent'][k] != v for k, v in {'name': 'claude-code', 'version': VERSION, 'model_name': MODEL}.items()):
        raise ValueError('Local Claude Code model/version differs')
    agent_config = read(source / 'config.json')['agent']
    if (agent_config['kwargs'].get('reasoning_effort') != 'high' or
            agent_config['model_name'] != MODEL or pointer.get('provider') != 'openrouter'):
        raise ValueError('Local Claude Code configuration differs')
    session_paths = sorted((source / 'agent/sessions').rglob('*.jsonl'))
    sessions = [[json.loads(line) for line in p.read_bytes().splitlines() if line.strip()] for p in session_paths]
    if not any(p.stem == raw['session_id'] for p in session_paths):
        raise ValueError('Local Claude Code main session missing')
    stream = []
    for line in (source / 'agent/claude-code.txt').read_bytes().splitlines():
        try:
            stream.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    tokens, requests, remainder, start, finish, completed, note = claude_usage(sessions, stream, raw['session_id'], MODEL, VERSION)
    result = read(safe_path(root, pointer['selected_result']))
    start, finish, seconds, basis = coding_time(result, [start] if start else [], [finish] if finish else [])
    if seconds is None:
        raise ValueError('Missing local Hy4 original coding time')
    reward_path = safe_path(root, pointer['selected_reward'])
    reward_bytes, reward = reward_path.read_bytes(), read(reward_path)
    value = reward['reward'] if isinstance(reward, dict) else reward
    if (not math.isclose(float(value), result['verifier_result']['rewards']['reward'], abs_tol=1e-9) or
            not math.isclose(float(value) * 100, float(row['score']), abs_tol=1e-7) or
            not result.get('verifier', {}).get('finished_at')):
        raise ValueError('Local Hy4 final reward is inconsistent or unfinished')
    trial_id = row['task'] + '-hy4-claude-code-high-' + digest(trajectory + reward_bytes)[:12]
    destination = destination / trial_id
    steps, redactions = export_trajectory(repaired_trajectory(raw, tokens), destination, scrubber=public, public=True)
    export_files(source, reward_path.parent, destination, public, write)
    config = {'agent': 'Claude Code', 'version': VERSION, 'model': MODEL, 'effort': 'high', 'provider': 'Tencent',
              'run_mode': pointer.get('mode') or 'native', 'task_commit': pointer.get('source_revision'),
              'verifier_commit': pointer.get('source_revision')}
    status = (result.get('exception_info') or {}).get('exception_type') or ('completed' if completed else 'Completion not recorded')
    trial = trial_record(row['task'], entry, trajectory, reward, reward_bytes, tokens, seconds, start, finish,
                         basis, status, note, config, steps, redactions, trial_id)
    write(destination / 'evaluation.json', {k: trial[k] for k in ('score', 'reward', 'configuration', 'qualification')})
    return trial, usage_row(row['task'], digest(trajectory), tokens, requests, remainder)


def prepare(community, final, base_package, package):
    evidence = read(CONTENT / 'community-source-evidence.json')['hy4']
    rows = community_inventory(community, evidence)
    local = local_rows(final, evidence)
    tasks = {t['name'] for t in read(ROOT / 'content/tasks/catalog.json')}
    names = [r['task'] for r in rows + local]
    if len(names) != 47 or len(set(names)) != 47 or set(names) != tasks:
        raise ValueError('Community and local Hy4 selections must cover all 47 tasks exactly once')
    policy = read(CONTENT / 'selection.json')
    if MODEL not in policy['included_models'] or policy.get('community_models') != [MODEL]:
        raise ValueError('Hy4 community publication is not explicitly selected')
    # finalize hashes and scans every copied payload. Compare those fingerprints
    # with the sealed base inventory below, avoiding a redundant full-corpus pass.
    base = json.loads(gzip.decompress((base_package / 'publication.json.gz').read_bytes()))
    if base.get('schema') != 1 or base.get('repo_id') != REPO_ID or base.get('release_path') != CURRENT_RELEASE:
        raise ValueError('Unexpected base publication')
    release = base['release_path']
    before = read(base_package / release / 'snapshot.json')
    if any(t['configuration']['model'] == MODEL for t in before['trials']):
        raise ValueError('Base package already contains Hy4')
    sources = {**before['source_hashes'], 'community_source_evidence': digest((CONTENT / 'community-source-evidence.json').read_bytes()),
               'selection': digest(encode(policy)), 'model_metadata': digest(encode(read(CONTENT / 'model-metadata.json'))),
               'base_snapshot': digest((base_package / release / 'snapshot.json').read_bytes())}
    if (package / 'publication.json.gz').exists():
        manifest = load_package(package)
        if manifest['source_hashes'] != sources:
            raise ValueError('Prepared Hy4 package has different source evidence')
        return read(package / release / 'snapshot.json'), manifest
    if package.exists() and any(p.name != 'releases' for p in package.iterdir()):
        raise ValueError('Unrecognized incomplete package')
    snapshot = copy.deepcopy(before)
    snapshot.update(id=policy['updated_at'] + '-selected-' + digest(encode(sources))[:10],
                    observed_at=evidence['accepted_at'], source_hashes=sources, selection=policy)
    info = read(CONTENT / 'model-metadata.json')['models'][MODEL]
    entry = {'id': snapshot['id'] + '-hy4-claude-code-high', 'model': MODEL, 'name': 'Hy4', 'effort': 'high',
             'agent': 'Claude Code', 'agent_version': VERSION, 'provider': 'Tencent',
             'release_date': info['release_date'], 'release_date_source': info['source']}
    snapshot['entries'].append(entry)
    snapshot['entries'].sort(key=lambda e: e['id'])
    usage = copy.deepcopy(read(base_package.with_suffix('.usage.json')))
    # Hard links reuse immutable base payloads without duplicating ten GB locally.
    def link_base(source, target):
        if Path(target).exists():
            if not os.path.samefile(source, target):
                raise ValueError('Incomplete package contains a different base payload')
        else:
            os.link(source, target)
        return target
    shutil.copytree(base_package / release / 'trials', package / release / 'trials', copy_function=link_base, dirs_exist_ok=True)
    public = PublicText(final.parent, scrub)
    for row in sorted(rows, key=lambda r: r['task']):
        trial, counted = import_community(community, row, entry['id'], package / release / 'trials', public)
        snapshot['trials'].append(trial); usage['rows'].append(counted)
        print(f'Prepared community: {row["task"]}', flush=True)
    for row in sorted(local, key=lambda r: r['task']):
        trial, counted = import_local(final, row, entry['id'], package / release / 'trials', public)
        snapshot['trials'].append(trial); usage['rows'].append(counted)
        print(f'Prepared local: {row["task"]}', flush=True)
    calculate(snapshot, usage, read(CONTENT / 'official-pricing.json'))
    write(package.with_suffix('.usage.json'), usage)
    manifest = finalize(package, snapshot, release)
    append_plan(base_package, package, base, manifest)
    return snapshot, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--community-dir', type=Path, default=COMMUNITY)
    parser.add_argument('--final-dir', type=Path, default=DEFAULT_FINAL)
    parser.add_argument('--base-package', type=Path, default=BASE_PACKAGE)
    parser.add_argument('--package', type=Path, default=PACKAGE)
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    package, base_package = args.package.resolve(), args.base_package.resolve()
    snapshot, manifest = prepare(args.community_dir.resolve(), args.final_dir.resolve(), base_package, package)
    install_preview(package, snapshot, manifest)
    if not args.upload:
        print('Prepared and verified locally. Use --upload to publish; no network requests or Git staging performed.')
        return
    command = [sys.executable, str(ROOT / 'scripts/append_hf_trajectories.py'),
               '--base-package', str(base_package), '--package', str(package)]
    command.append('--upload')
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
