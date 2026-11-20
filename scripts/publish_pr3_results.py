#!/usr/bin/env python3
"""Prepare and append the reviewed Sonnet and Argon PR #3 results."""
import argparse
import copy
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from append_hf_trajectories import append_plan, published_base_payloads
from download_pr3_results import SOURCE_DIR
from export_trial_files import export_files
from import_final_results import CONTENT, DEFAULT_FINAL, coding_time, install_preview, verified_bytes
from import_results import ROOT, TOKEN_FIELDS, digest, encode, export_trajectory, read, scrub, write
from leaderboard_costs import calculate
from prepare_hf_release import finalize
from publication import CURRENT_RELEASE, PublicText, fingerprints, load_package, safe_path

BASE = ROOT / '.build/hf-trajectories-glm53-tokenplus'
PACKAGE = ROOT / '.build/hf-trajectories-pr3'
MODELS = {
    'anthropic/claude-sonnet-5.5': ('Claude Sonnet 5.5', 'Claude Code', '2.1.309', 'max',
                                  {'claude-sonnet-5-5', 'anthropic/claude-sonnet-5.5'}),
    'google/gemini-4-argon': ('Gemini 4 Argon', 'Antigravity CLI', '1.5.2', 'high',
                            {'gemini/gemini-4-argon', 'google/gemini-4-argon'}),
}
REPORTED_REWARDS = {
    ('claude-sonnet-5-5', 'incremental-vector-search'),
    ('gemini-4-argon', 'rust-bm25-search'),
}


def recorded_usage(raw):
    metrics = raw.get('final_metrics') or {}
    inp = metrics.get('total_prompt_tokens')
    out = metrics.get('total_completion_tokens')
    cost = metrics.get('total_cost_usd')
    values = dict.fromkeys(TOKEN_FIELDS)
    if inp is None or out is None:
        if inp is not None or out is not None or cost is not None:
            raise ValueError('Partial ATIF usage summary')
        return values, None, 'Antigravity did not export token or cost counters.'
    values.update(input_tokens=inp, output_tokens=out, total_tokens=inp + out,
                  cached_input_tokens=metrics.get('total_cached_tokens'),
                  cache_write_input_tokens=(metrics.get('extra') or {}).get('total_cache_creation_input_tokens'))
    if (any(v is not None and (type(v) is not int or v < 0) for v in values.values()) or
            sum(values[k] or 0 for k in ('cached_input_tokens', 'cache_write_input_tokens')) > inp or
            cost is not None and (not math.isfinite(cost) or cost < 0)):
        raise ValueError('Invalid exported ATIF usage summary')
    return values, cost, 'Claude Code ATIF counters and harness-reported USD estimate for the original coding run.'


def original_time(raw, provenance):
    start, finish = provenance.get('coding_started'), provenance.get('coding_finished')
    if start and finish:
        basis = 'Contributor provenance for the original Harbor coding interval.'
    else:
        stamps = sorted((datetime.fromisoformat(s['timestamp']), s['timestamp']) for s in raw['steps'] if s.get('timestamp'))
        if len(stamps) < 2:
            raise ValueError('Missing timestamps for a coding-time estimate')
        start, finish = stamps[0][1], stamps[-1][1]
        basis = 'Estimated from the first and last recorded trajectory timestamps.'
    seconds = (datetime.fromisoformat(finish) - datetime.fromisoformat(start)).total_seconds()
    if seconds < 0:
        raise ValueError('Negative original coding interval')
    return start, finish, seconds, basis


def community_trial(root, task, entry, model_info, results, provenance, regrades, output, public):
    path = root / 'trajectories' / task / 'trajectory.json'
    reported = results[task]['score']
    original = provenance[task]
    evidence = root / 'evidence' / task
    regrade = regrades.get(f'{task}|{root.name}')
    qualification = {}
    reward_path = next((p for p in (evidence / 'regrade/reward.json', path.with_name('reward.json'),
                                   path.with_name('reward.txt'), evidence / 'reward.json') if p.is_file()), None)
    if reward_path is None:
        if (root.name, task) not in REPORTED_REWARDS:
            raise ValueError(f'Missing community reward: {root.name}/{task}')
        reward = {'reward': reported / 100}
        qualification['score_source'] = 'Contributor results.json'
        reward_bytes = encode(reward)
    else:
        reward = read(reward_path)
        reward_bytes = reward_path.read_bytes()
    score = float(reward['reward'] if isinstance(reward, dict) else reward) * 100
    if not math.isclose(score, reported, abs_tol=0.005001):
        raise ValueError(f'Community reward disagrees with results.json: {root.name}/{task}')
    if regrade:
        if regrade.get('original_trial_id') != original.get('selected_trial_id'):
            raise ValueError(f'Regrade source trial disagrees with the selected original: {root.name}/{task}')
        qualification.update(original_trial_id=regrade['original_trial_id'], regrade_trial_id=regrade.get('new_trial_id') or regrade.get('regrade_trial_dir'))
    summary = evidence / 'regrade/regrade.json'
    verifier_revision = None
    if summary.is_file():
        record = read(summary)
        if record.get('status') != 'completed' or record.get('measurement_valid') is not True or not math.isclose(record['rewards']['reward'] * 100, score, abs_tol=1e-7):
            raise ValueError(f'Invalid regrade summary: {root.name}/{task}')
        verifier_revision = record['verifier_revision']
    raw = read(path)
    timing = original_time(raw, original)
    files = {'verifier': {}}
    if reward_path:
        files['verifier'][reward_path.name] = reward_path
    for p in (summary, (reward_path.parent if reward_path else evidence) / 'reward-details.json'):
        if p.is_file():
            files['verifier'][p.name] = p
    config = {'provider': 'Vertex AI', 'run_mode': 'regrade' if regrade else 'native',
              'verifier_commit': verifier_revision, 'source_repository': model_info['repo_id'],
              'source_revision': model_info['revision']}
    return export_trial(path, raw, reward, reward_bytes, score, timing, original.get('exception_type'),
                        task, entry, config, qualification, output, public, files=files)


def local_trial(final, row, entry, evidence, output, public):
    if any(row[k] != v for k, v in evidence.items()):
        raise ValueError('Selected local PR #3 run changed')
    metadata = safe_path(final, row['metadata'])
    pointer = read(metadata)
    root = metadata.parent
    trial = safe_path(root, pointer['selected_native_trial'])
    manifest_path = safe_path(final, row['file_manifest'])
    if digest(manifest_path.read_bytes()) != row['file_manifest_sha256'] or pointer['status'] != 'valid':
        raise ValueError('Invalid selected local PR #3 trial')
    for item in read(manifest_path)['files']:
        verified_bytes(safe_path(root / pointer['output'], item['relative']), item)
    path = safe_path(final, row['primary_trajectory'])
    if digest(path.read_bytes()) != row['primary_trajectory_sha256'] or pointer['provider'] != 'openrouter':
        raise ValueError('Local PR #3 trajectory or provider differs')
    reward_path = safe_path(root, pointer['selected_reward'])
    reward = read(reward_path)
    score = float(reward['reward'] if isinstance(reward, dict) else reward) * 100
    result = read(safe_path(root, pointer['selected_result']))
    if not (result.get('verifier') or {}).get('finished_at') or not math.isclose(score, float(row['score']), abs_tol=1e-7) or not math.isclose(result['verifier_result']['rewards']['reward'] * 100, score, abs_tol=1e-7):
        raise ValueError('Local PR #3 score differs or verification is unfinished')
    status = (result.get('exception_info') or {}).get('exception_type')
    config = {'provider': 'OpenRouter', 'run_mode': 'native', 'task_commit': pointer['source_revision'],
              'verifier_commit': pointer['source_revision']}
    qualification = {'source': 'Maintainer rerun for PR #3'}
    return export_trial(path, read(path), reward, reward_path.read_bytes(), score, coding_time(result, [], []),
                        status, row['task'], entry, config, qualification, output, public,
                        trial_dir=trial, verifier_dir=reward_path.parent)


def export_trial(path, raw, reward, reward_bytes, score, timing, status, task, entry, config,
                 qualification, output, public, files=None, trial_dir=None, verifier_dir=None):
    agent = raw['agent']
    model = entry['model']
    expected = (entry['agent'].lower().replace(' ', '-'), entry['agent_version'])
    if ((agent['name'], agent['version']) != expected or agent['model_name'] not in MODELS[model][4]
            or not 0 <= score <= 100 or timing[2] is None):
        raise ValueError(f'Wrong harness, model, score or duration for {model}/{task}')
    source_hash = digest(path.read_bytes())
    reward_hash = digest(reward_bytes)
    trial_id = f'{task}-{model.split("/")[-1]}-{expected[0]}-{entry["effort"]}-{digest((source_hash + reward_hash).encode())[:12]}'
    destination = output / trial_id
    steps, redactions = export_trajectory(raw, destination, scrubber=public, public=True)
    if files is not None:
        # The contributor ships ATIF plus selected verifier evidence, with no Harbor run directory.
        index = export_files(destination, destination / 'verifier', destination, public, write, extra_files=files)
        index['regraded_separately'] = config['run_mode'] == 'regrade'
        write(destination / 'files/index.json', index)
    else:
        export_files(trial_dir, verifier_dir, destination, public, write)
    tokens, cost, note = recorded_usage(raw)
    config.update(agent=entry['agent'], version=entry['agent_version'], model=model, effort=entry['effort'])
    result = {'id': trial_id, 'entry': entry['id'], 'task': task, 'score': score, 'valid': True,
              'agent_status': status or ('completed' if trial_dir else 'No exception recorded'),
              'agent_seconds': timing[2], 'started_at': timing[0], 'finished_at': timing[1],
              'agent_time_basis': timing[3], 'tokens': tokens, 'usage_note': note,
              'harness_reported_cost_usd': cost, 'steps': steps, 'configuration': config,
              'qualification': qualification, 'trajectory_url': f'trials/{trial_id}/manifest.json',
              'trajectory_sha256': source_hash, 'reward_sha256': reward_hash, 'reward': reward,
              'redacted_fields': redactions}
    write(destination / 'evaluation.json', {k: result[k] for k in ('score', 'reward', 'configuration', 'qualification')})
    usage = {'task': task, 'model': model, 'effort': entry['effort'], 'primary_trajectory_sha256': source_hash,
             'requests': [], 'usage_basis': 'exported_harness_summary', 'tokens': tokens, 'cost_usd': cost}
    return result, usage


def prepare(source, final, base_package, package):
    evidence_path = CONTENT / 'community-source-evidence.json'
    evidence = read(evidence_path)['pr3']
    policy = read(CONTENT / 'selection.json')
    metadata = read(CONTENT / 'model-metadata.json')
    if not set(MODELS) <= set(policy['community_models']):
        raise ValueError('Select both PR #3 models for the leaderboard')
    index = final / 'INDEX.csv'
    archive = read(final / 'MANIFEST.json')
    if archive['index_sha256'] != digest(index.read_bytes()):
        raise ValueError('Local final archive index differs from its manifest')
    with index.open() as handle:
        local_rows = {(r['task'], r['model_label']): r for r in csv.DictReader(handle)}
    base, retained = published_base_payloads(base_package)
    release = base['release_path']
    if release != CURRENT_RELEASE:
        raise ValueError('Expected the current release layout')
    base_snapshot = base_package / release / 'snapshot.json'
    snapshot = copy.deepcopy(read(base_snapshot))
    if any(e['model'] in MODELS for e in snapshot['entries']):
        raise ValueError('Base already includes a PR #3 model')
    inventories = {}
    for model, info in evidence['models'].items():
        root = source / info['repo_id'].split('search-swe-', 1)[1]
        inventory = read(root / 'source-inventory.json')
        if (inventory['repo'], inventory['revision']) != (info['repo_id'], info['revision']):
            raise ValueError('Source inventory does not match the pinned contributor revision')
        for relative, (size, blob, sha) in inventory['files'].items():
            checked = fingerprints(safe_path(root, relative))
            if checked['bytes'] != size or (checked['sha256'] != sha if sha else checked['git_blob'] != blob):
                raise ValueError(f'Contributor file differs from its pinned inventory: {relative}')
        inventories[model] = (root, inventory)
    sources = {**snapshot['source_hashes'], 'index': archive['index_sha256'],
               'archive': digest((final / 'MANIFEST.json').read_bytes()),
               'community_source_evidence': digest(evidence_path.read_bytes()),
               'model_metadata': digest(encode(metadata)), 'selection': digest(encode(policy)),
               'base_snapshot': digest(base_snapshot.read_bytes()),
               'pr3_source': digest(encode({m: inv for m, (_, inv) in inventories.items()}))}
    snapshot.update(id=policy['updated_at'] + '-selected-' + digest(encode(sources))[:10],
                    observed_at=archive['at'], source_hashes=sources, selection=policy)
    if (package / 'publication.json.gz').exists():
        manifest = load_package(package, retained=retained)
        if manifest['source_hashes'] != sources:
            raise ValueError('Prepared package differs from the selected evidence')
        return read(package / release / 'snapshot.json'), manifest
    partial = package / release / 'snapshot.json'
    if partial.is_file():
        completed = read(partial)
        if completed['source_hashes'] != sources or completed['trials'][:len(snapshot['trials'])] != snapshot['trials'] or len(completed['trials']) != len(snapshot['trials']) + 94:
            raise ValueError('Incomplete package differs from the selected evidence')
        calculate(completed, read(package.with_suffix('.usage.json')), read(CONTENT / 'official-pricing.json'))
        manifest = finalize(package, completed, release, retained=retained)
        append_plan(base_package, package, base, manifest)
        return completed, manifest
    if package.exists():
        raise ValueError('Incomplete output exists. Use a fresh package directory.')
    output = package / release / 'trials'
    shutil.copytree(base_package / release / 'trials', output, copy_function=os.link)
    public = PublicText(final.parent, scrub)
    usage = read(base_package.with_suffix('.usage.json'))
    tasks = {t['name'] for t in snapshot['tasks']}
    for model, (root, _) in inventories.items():
        info = evidence['models'][model]
        name, agent, version, effort, _ = MODELS[model]
        entry = {'id': snapshot['id'] + '-' + model.split('/')[-1] + '-' + effort,
                 'model': model, 'name': name, 'agent': agent, 'agent_version': version, 'effort': effort,
                 'provider': 'Vertex AI', 'release_date': metadata['models'][model]['release_date'],
                 'release_date_source': metadata['models'][model]['source'],
                 'provider_note': f'{len(info["local_trials"])} maintainer rerun{"s" if len(info["local_trials"]) != 1 else ""} via OpenRouter.'}
        snapshot['entries'].append(entry)
        official = read(root / 'results.json')
        results = official['tasks']
        replacements = info['local_trials']
        if set(results) != tasks or set(official['pending_tasks']) != set(replacements):
            raise ValueError('PR #3 selections must cover all tasks with exactly the specified local reruns')
        provenance = read(root / 'provenance_index.json')
        regrades = read(root / 'regrade_index.json')
        for task in sorted(tasks):
            if task in replacements:
                accepted = replacements[task]
                trial, counted = local_trial(final, local_rows[(task, accepted['model_label'])], entry, accepted, output, public)
            else:
                trial, counted = community_trial(root, task, entry, info, results, provenance, regrades, output, public)
            snapshot['trials'].append(trial)
            usage['rows'].append(counted)
            print(f'Prepared {name}: {task}', flush=True)
    calculate(snapshot, usage, read(CONTENT / 'official-pricing.json'))
    write(package.with_suffix('.usage.json'), usage)
    manifest = finalize(package, snapshot, release, retained=retained)
    append_plan(base_package, package, base, manifest)
    return snapshot, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE_DIR)
    parser.add_argument('--final-dir', type=Path, default=DEFAULT_FINAL)
    parser.add_argument('--base-package', type=Path, default=BASE)
    parser.add_argument('--package', type=Path, default=PACKAGE)
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    package, base = args.package.resolve(), args.base_package.resolve()
    snapshot, manifest = prepare(args.source.resolve(), args.final_dir.resolve(), base, package)
    install_preview(package, snapshot, manifest)
    if args.upload:
        subprocess.run([sys.executable, str(ROOT / 'scripts/append_hf_trajectories.py'),
                        '--base-package', str(base), '--package', str(package), '--published-base', '--upload'], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
