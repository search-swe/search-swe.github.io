#!/usr/bin/env python3
"""Add recorded Argon usage to the existing public trajectories and leaderboard."""
import argparse
import csv
import gzip
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from append_hf_trajectories import metadata_matches, published_base_payloads
from hf_network import authenticated_api, retry_429
from import_final_results import CONTENT, default_final_dir, install_preview
from import_results import ROOT, digest, encode, read, write
from leaderboard_costs import TOKEN_FIELDS, calculate
from prepare_hf_release import finalize
from publication import REPO_ID, load_package, safe_path
from upload_hf_release import activate, check_site_snapshot, verify_remote

MODEL = 'google/gemini-4-argon'
FORMULA = 'large-scale-formula-retrieval'
BASE_PACKAGE = ROOT / '.build/hf-trajectories-pr3'
PACKAGE = ROOT / '.build/hf-trajectories-pr3-argon-usage'
VERTEX_REPO = 'ubowang/search-swe-gemini-4-argon'
VERTEX_REVISION = 'a3cd17876ca6456af39050089e242398c86864a6'
VERTEX_FILES = {
    'usage.json': '86fe59a0663690b122b29391fd3b27f80c4da811aa3e93938454beba979c06c8',
    'usage_responses.jsonl': 'f6c10261730e0bc372a7a485930b3e1b2ae937d1d1ceaf2de865a953cbfb4eca',
    'provenance_index.json': '6c52b5a1697ad26c6d7397ffca5032aa88065be58cdeebfc68276e04e27f813a',
}
FORMULA_LOG_SHA = 'd7b51a3d3d1e1f06481abd1440092b40a2f71980b70f7e7258cfb16ade38ef90'
COUNTERS = ('input_tokens', 'cache_read_tokens', 'output_tokens')
SITE_ORIGIN = 'https://search-swe.github.io'


def timestamp(value):
    return int(datetime.fromisoformat(value).timestamp())


def verified_source(path, sha):
    body = path.read_bytes()
    if digest(body) != sha:
        raise ValueError(f'Usage evidence differs from the selected source: {path.name}')
    return body


def vertex_usage(source):
    if source is None:
        from huggingface_hub import hf_hub_download
        paths = {name: Path(hf_hub_download(VERTEX_REPO, name, repo_type='dataset',
                                           revision=VERTEX_REVISION, token=False)) for name in VERTEX_FILES}
    else:
        paths = {name: source / name for name in VERTEX_FILES}
    data = {name: verified_source(paths[name], sha) for name, sha in VERTEX_FILES.items()}
    summary = json.loads(data['usage.json'])
    provenance = json.loads(data['provenance_index.json'])
    groups = defaultdict(list)
    for line in data['usage_responses.jsonl'].splitlines():
        response = json.loads(line)
        groups[response['task']].append(response)
    totals = {t['task']: t for t in summary['per_task_totals']}
    if len(totals) != 46 or groups.keys() != totals.keys() or FORMULA in groups:
        raise ValueError('Vertex usage must cover the 46 selected contributor tasks')
    for task, rows in groups.items():
        selected = totals[task]['selected_trial_id']
        original = provenance[task].get('selected_trial_id')
        if (original and selected != original) or any(r['selected_trial_id'] != selected for r in rows):
            raise ValueError(f'Vertex usage trial ID disagrees for {task}')
        for k in COUNTERS:
            if sum(r[k] for r in rows) != totals[task][k]:
                raise ValueError(f'Vertex task totals disagree for {task}')
        if (sum(totals[task][k] for k in COUNTERS) != totals[task]['total_tokens'] or
                sum(r['type'] == 'PLANNER_RESPONSE' for r in rows) != totals[task]['n_model_responses'] or
                sum(r['type'] == 'CHECKPOINT' for r in rows) != totals[task]['n_checkpoint_calls']):
            raise ValueError(f'Vertex response counts disagree for {task}')
    if (sum(map(len, groups.values())) != 6373 or
            sum(t['total_tokens'] for t in totals.values()) != summary['grand_total']['total_tokens']):
        raise ValueError('Vertex grand total disagrees with the selected summary')
    return groups


def formula_usage(archive, selected):
    with (archive / 'INDEX.csv').open() as index:
        row, = (r for r in csv.DictReader(index) if r['task'] == FORMULA and r['model'] == MODEL)
    if row['primary_trajectory_sha256'] != selected['trajectory_sha256']:
        raise ValueError('Local Formula selection differs from the published trial')
    path = safe_path(archive, row['primary_trajectory'])
    original = json.loads(verified_source(path, selected['trajectory_sha256']))
    native = verified_source(path.with_name('antigravity-cli.trajectory.jsonl'), FORMULA_LOG_SHA)
    steps = iter([s for s in original['steps'] if s['source'] == 'agent'])
    results = []
    for line in native.splitlines():
        event = json.loads(line)
        if all(event.get(k) is None for k in COUNTERS):
            continue
        step = next(steps, None) if event['type'] == 'PLANNER_RESPONSE' else None
        if event['type'] == 'PLANNER_RESPONSE' and (step is None or timestamp(step['timestamp']) != timestamp(event['created_at'])):
            raise ValueError('Native Formula response cannot be matched to the published ATIF')
        results.append({**{k: event[k] for k in (*COUNTERS, 'type', 'created_at')}, 'task': FORMULA,
                        'selected_trial_id': path.parent.parent.name, 'native_step_index': event['step_index'],
                        'atif_step_id': step['step_id'] if step else None})
    if len(results) != 97 or next(steps, None) is not None:
        raise ValueError('Formula response coverage is incomplete')
    return results


def associate(atifs, responses):
    steps = {s['step_id']: s for s in atifs if s['source'] == 'agent'}
    matched, requests, identities = {}, [], set()
    totals = Counter()
    for event in responses:
        native = event['native_step_index']
        if type(native) is not int or native < 0 or native in identities:
            raise ValueError('Missing or duplicate native event index')
        identities.add(native)
        if any(type(event[k]) is not int or event[k] < 0 for k in COUNTERS):
            raise ValueError('Invalid Argon token counter')
        step_id = event['atif_step_id']
        kind = event['type']
        if kind == 'PLANNER_RESPONSE':
            step = steps.get(step_id)
            if step is None or step_id in matched or timestamp(step['timestamp']) != timestamp(event['created_at']):
                raise ValueError(f'Usage failed to match an ATIF agent step for {event["task"]}')
        elif kind != 'CHECKPOINT' or step_id is not None:
            raise ValueError('Unexpected Argon usage event or step mapping')
        prompt = event['input_tokens'] + event['cache_read_tokens']
        completion = event['output_tokens']
        normalized = {'input_tokens': prompt, 'cached_input_tokens': event['cache_read_tokens'],
                      'cache_write_input_tokens': 0, 'output_tokens': completion,
                      'reasoning_output_tokens': None, 'total_tokens': prompt + completion}
        if step_id is not None:
            matched[step_id] = normalized
        requests.append({'response_id': f'antigravity:{event["selected_trial_id"]}:{native}', 'usage': normalized})
        totals.update({k: v for k, v in normalized.items() if v is not None})
    totals.update(response_count=len(requests))
    result = {**totals, 'reasoning_output_tokens': None}
    return matched, requests, result


def replace_file(path, body):
    # Package payloads are hard-linked from the immutable base.
    temp = path.with_suffix(path.suffix + '.tmp')
    write(temp, body)
    temp.replace(path)


def refresh_trial(directory, trial, responses, evidence):
    manifest_path = directory / 'manifest.json'
    manifest = read(manifest_path)
    path = directory / manifest['download']
    atif = json.loads(gzip.decompress(path.read_bytes()))
    if atif['agent']['name'] != 'antigravity-cli':
        raise ValueError('Expected an Antigravity CLI public trajectory')
    if any(atif['session_id'] != row['selected_trial_id'] + '__agent' for row in responses):
        raise ValueError('Argon usage belongs to another trajectory session')
    matched, requests, totals = associate(atif['steps'], responses)
    if not set(TOKEN_FIELDS) <= totals.keys():
        raise ValueError('Missing Argon trial totals')
    touched = set()
    for s in atif['steps']:
        usage = matched.get(s['step_id'])
        if usage:
            s.setdefault('metrics', {}).update(prompt_tokens=usage['input_tokens'],
                                              cached_tokens=usage['cached_input_tokens'],
                                              completion_tokens=usage['output_tokens'])
    atif['final_metrics'].update(total_prompt_tokens=totals['input_tokens'],
                                 total_cached_tokens=totals['cached_input_tokens'],
                                 total_completion_tokens=totals['output_tokens'])
    atif['final_metrics'].setdefault('extra', {}).update(
        usage_file='usage.json', recorded_model_responses=len(matched),
        recorded_compaction_calls=len(requests) - len(matched))
    replace_file(path, gzip.compress(encode(atif), mtime=0))
    touched.add(path)
    for chunk in dict.fromkeys(s['chunk'] for s in manifest['steps']):
        file = directory / chunk
        chunk_steps = read(file)
        updated = False
        for s in chunk_steps:
            usage = matched.get(s['step_id'])
            if usage:
                s['usage'].update({k: usage[k] for k in ('input_tokens', 'cached_input_tokens', 'output_tokens')})
                updated = True
        if updated:
            replace_file(file, chunk_steps)
            touched.add(file)
    manifest['usage'] = 'usage.json'
    replace_file(manifest_path, manifest)
    touched.add(manifest_path)
    usage_path = directory / manifest['usage']
    write(usage_path, {'schema': 1, 'source': evidence, 'totals': totals, 'responses': responses,
                       'note': 'Source input_tokens exclude cache reads. Recorded model calls include separate context compaction events.'})
    touched.add(usage_path)
    trial.pop('harness_reported_cost_usd', None)
    trial.update(tokens=totals, usage_evidence=True,
                 usage_note='Antigravity CLI model responses and separate context compaction calls. Per-step counters cover matched responses.')
    return touched, {'task': trial['task'], 'model': MODEL, 'effort': trial['configuration']['effort'],
                     'primary_trajectory_sha256': trial['trajectory_sha256'], 'requests': requests}


def prepare(source, archive, base_package, package):
    base, retained = published_base_payloads(base_package)
    release = base['release_path']
    snapshot = read(base_package / release / 'snapshot.json')
    trials = {t['task']: t for t in snapshot['trials'] if t['configuration']['model'] == MODEL}
    if len(trials) != 47 or set(trials) != {t['name'] for t in snapshot['tasks']} or not all(t['valid'] for t in trials.values()):
        raise ValueError('Wrong Argon task selection in the published base')
    sources = {'vertex_revision': VERTEX_REVISION, **VERTEX_FILES, 'openrouter_usage': FORMULA_LOG_SHA}
    snapshot['source_hashes'].update(argon_usage=digest(encode(sources)))
    snapshot['id'] = '2026-11-21-argon-usage-' + digest(encode(snapshot['source_hashes']))[:10]
    if (package / 'publication.json.gz').is_file():
        ids = {t['id'] for t in trials.values()}
        manifest = load_package(package, retained={p: h for p, h in retained.items() if p.split('/')[3] not in ids})
        existing = read(package / release / 'snapshot.json')
        if existing['id'] != snapshot['id']:
            raise ValueError('Prepared package differs from the selected usage evidence')
        return existing, manifest, base
    groups = vertex_usage(source)
    groups[FORMULA] = formula_usage(archive, trials[FORMULA])
    if set(groups) != set(trials):
        raise ValueError('Recorded usage covers a different set of trials')
    output = package / release / 'trials'
    shutil.copytree(base_package / release / 'trials', output, copy_function=os.link)
    counted = {}
    for task, trial in trials.items():
        evidence = ({'provider': 'OpenRouter', 'sha256': FORMULA_LOG_SHA} if task == FORMULA else
                    {'provider': 'Vertex AI', 'repository': VERTEX_REPO, 'revision': VERTEX_REVISION,
                     'file': 'usage_responses.jsonl', 'sha256': VERTEX_FILES['usage_responses.jsonl']})
        touched, counted[task] = refresh_trial(output / trial['id'], trial, groups[task], evidence)
        for path in touched:
            retained.pop(path.relative_to(package).as_posix(), None)
    usage = read(base_package.with_suffix('.usage.json'))
    usage['rows'] = [counted[row['task']] if row['model'] == MODEL else row for row in usage['rows']]
    costs = calculate(snapshot, usage, read(CONTENT / 'official-pricing.json'))
    print(f'47 Argon trials, {sum(t["tokens"]["total_tokens"] for t in trials.values()):,} tokens.', flush=True)
    print(f'Argon estimated cost: USD {sum(float(costs[t["id"]]["cost_usd"]) for t in trials.values()):.8f}.', flush=True)
    write(package.with_suffix('.usage.json'), usage)
    return snapshot, finalize(package, snapshot, release, retained=retained), base


def upload(package, snapshot, manifest, base_package, base):
    from huggingface_hub import CommitOperationAdd

    receipt = read(base_package.with_name(base_package.name + '-uploaded.json'))
    parent = receipt['revision']
    release = manifest['release_path']
    ids = {t['id'] for t in snapshot['trials'] if t['configuration']['model'] == MODEL}
    changed = {p for p, h in manifest['files'].items() if base['files'].get(p) != h}
    allowed = {'README.md', f'{release}/snapshot.json'}
    if (set(base['files']) - set(manifest['files']) or
            any(p not in allowed and not (p.startswith(f'{release}/trials/') and p.split('/')[3] in ids)
                for p in changed)):
        raise ValueError('Usage update would change unrelated payloads')
    source_sha = check_site_snapshot(package, manifest)
    api = authenticated_api()
    current = api.repo_info(REPO_ID, repo_type='dataset', expand=['sha', 'private', 'gated'])
    if current.private or current.gated or not metadata_matches(api, base_package, base, parent):
        raise ValueError('Expected an unchanged public base release')
    revision = current.sha
    if not metadata_matches(api, package, manifest, revision):
        if revision != parent:
            raise ValueError('Remote head changed since the Argon usage package was prepared')
        paths = sorted(changed | {'publication.json.gz'})
        print(f'Publishing {len(paths)} changes on {revision}.', flush=True)
        commit = retry_429(lambda: api.create_commit(
            REPO_ID, repo_type='dataset', parent_commit=revision,
            operations=[CommitOperationAdd(path_in_repo=p, path_or_fileobj=package / p) for p in paths],
            commit_message=f'Publish recorded Argon usage: {snapshot["id"]}'), 'Argon usage publication')
        revision = commit.oid
    print(f'Verifying Argon usage at {revision}.', flush=True)
    verify_remote(api, package, manifest, revision, SITE_ORIGIN, base_revision=parent, updated_trials=ids)
    if check_site_snapshot(package, manifest) != source_sha:
        raise ValueError('Local homepage snapshot changed during publication')
    activate(package, manifest, revision, source_sha)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Local copy of the verified Vertex usage export')
    parser.add_argument('--final-dir', type=Path, default=default_final_dir())
    parser.add_argument('--base-package', type=Path, default=BASE_PACKAGE)
    parser.add_argument('--package', type=Path, default=PACKAGE)
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    base_package, package = args.base_package.resolve(), args.package.resolve()
    snapshot, manifest, base = prepare(args.source, args.final_dir.resolve(), base_package, package)
    install_preview(package, snapshot, manifest)
    if args.upload:
        upload(package, snapshot, manifest, base_package, base)


if __name__ == '__main__':
    main()
