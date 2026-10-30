"""Prepare/check a task withdrawal offline; change HF only with --apply."""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import re
import shutil
from pathlib import Path

from import_results import ROOT, read, write
from prepare_hf_release import finalize, referenced_files
from publication import DEFAULT_PACKAGE, REPO_ID, check_text, fingerprints, load_package, safe_path
from upload_hf_release import activate, check_site_snapshot, verify_remote

DEFAULT_PLAN = ROOT / '.build/hf-task-removal-2026-10-31.json'
PRUNED_PACKAGE = ROOT / '.build/hf-trajectories-47'


def retained_snapshot(previous, current, removed):
    """A withdrawal may only remove whole tasks; retained evidence must be identical."""
    old_tasks = {t['name']: t for t in previous['tasks']}
    tasks = {t['name']: t for t in current['tasks']}
    if not removed or set(old_tasks) - set(tasks) != set(removed) or set(tasks) - set(old_tasks):
        raise ValueError('Task difference does not match the removal record')
    if any(t != old_tasks[name] for name, t in tasks.items()):
        raise ValueError('Retained task metadata changed')

    def models(snapshot):
        return {e['model']: {k: v for k, v in e.items() if k != 'id'} for e in snapshot['entries']}

    if models(previous) != models(current):
        raise ValueError('Model configurations changed')
    old_trials = {t['id']: t for t in previous['trials'] if t['task'] not in removed}
    new_trials = {t['id']: t for t in current['trials']}
    if len(new_trials) != len(current['trials']) or old_trials.keys() != new_trials.keys():
        raise ValueError('Retained trial selection changed')
    old_entries = {e['id']: e['model'] for e in previous['entries']}
    new_entries = {e['id']: e['model'] for e in current['entries']}
    result = copy.deepcopy(current)
    for trial in result['trials']:
        old = old_trials[trial['id']]
        ignored = {'entry', 'trajectory_url', 'redacted_fields'}
        if ({k: v for k, v in old.items() if k not in ignored} !=
                {k: v for k, v in trial.items() if k not in ignored} or
                old_entries[old['entry']] != new_entries[trial['entry']]):
            raise ValueError(f'Retained trial evidence changed: {trial["id"]}')
        trial['trajectory_url'] = f'trials/{trial["id"]}/manifest.json'
        trial['redacted_fields'] = old['redacted_fields']
    result['publication'] = copy.deepcopy(previous['publication'])
    return result


def deletion_paths(previous, removed, release_path):
    return sorted(f'{release_path}/trials/{t["id"]}/' for t in previous['trials'] if t['task'] in removed)


def validate_delta(base, updated, directories):
    """Reject changed retained payloads, unexpected additions, and broad deletions."""
    release = base['release_path']
    if updated['release_path'] != release:
        raise ValueError('Withdrawal must retain the existing release directory')
    for directory in directories:
        relative = directory.removeprefix(release + '/trials/')
        if not directory.startswith(release + '/trials/') or not re.fullmatch(r'[a-z0-9][a-z0-9.-]*/', relative):
            raise ValueError('Deletion must name one exact trial directory')
        if not any(p.startswith(directory) for p in base['files']):
            raise ValueError(f'Deleted directory is absent from the base inventory: {directory}')
    deleted = {p for p in base['files'] if any(p.startswith(d) for d in directories)}
    if set(updated['files']) != set(base['files']) - deleted:
        raise ValueError('File removals differ from the exact withdrawn trial directories')
    metadata = {'README.md', release + '/snapshot.json'}
    for path, hashes in updated['files'].items():
        if path not in metadata and hashes != base['files'][path]:
            raise ValueError(f'Retained payload changed: {path}')
    return deleted


def prepare(jobs, base_package, package, plan_path):
    storage = read(ROOT / 'content/leaderboard/storage.json')
    if storage.get('provider') != 'huggingface' or not re.fullmatch(r'[0-9a-f]{40}', storage.get('revision', '')):
        raise ValueError('Preparation requires the currently verified HF storage configuration')
    # The pinned inventory authenticates already-sanitized bytes; do not rescan their text.
    base = load_package(base_package, check_content=False)
    base_hash = fingerprints(base_package / 'publication.json.gz')['sha256']
    if (base_hash != storage['publication_sha256'] or base['snapshot_id'] != storage['snapshot_id'] or
            base['release_path'] != storage['release_path'] or base['source_hashes'] != storage['source_hashes']):
        raise ValueError('Base package does not match the verified website release')
    record = read(jobs / 'release/REMOVED_TASKS.json')
    if record.get('status') != 'withdrawn_from_current_benchmark' or not record.get('all_models_and_attempts_excluded'):
        raise ValueError('Expected an explicit whole-task withdrawal record')
    current = read(ROOT / 'content/leaderboard/release.json')
    if (len(current['tasks']), len(current['trials'])) != (record['current_tasks'], record['current_valid_results']):
        raise ValueError('Import the current jobs snapshot before preparing this update')
    for key, relative in [('index', 'final-trajectories/INDEX.csv'),
                          ('results', 'traj-analysis/leaderboard-data/results.json'),
                          ('model_metadata', 'traj-analysis/leaderboard-data/pricing.json')]:
        if current['source_hashes'][key] != fingerprints(jobs / relative)['sha256']:
            raise ValueError('Local results do not match the current jobs snapshot')
    release = base['release_path']
    previous = read(base_package / release / 'snapshot.json')
    public = retained_snapshot(previous, current, record['tasks'])
    directories = deletion_paths(previous, record['tasks'], release)
    if package.exists() and any(package.iterdir()):
        # A fully exported package can be rechecked after interruption before plan creation.
        updated = load_package(package, check_content=False)
        if read(package / release / 'snapshot.json') != public:
            raise ValueError('Existing package belongs to a different update; choose an empty --package directory')
        check_text(package / release / 'snapshot.json')
        check_text(package / 'README.md')
        referenced_files(package / release, public)
    else:
        for relative in base['files']:
            if relative in {'README.md', release + '/snapshot.json'} or any(relative.startswith(d) for d in directories):
                continue
            target = safe_path(package, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(safe_path(base_package, relative), target)
        updated = finalize(package, public, release)
    deleted = validate_delta(base, updated, directories)
    check_site_snapshot(package, updated)
    plan = {'schema': 1, 'repo_id': REPO_ID, 'base_revision': storage['revision'],
            'base_package': str(base_package), 'package': str(package),
            'base_publication_sha256': base_hash,
            'publication_sha256': fingerprints(package / 'publication.json.gz')['sha256'],
            'removed_tasks': sorted(record['tasks']), 'delete_directories': directories,
            'deleted_files': len(deleted), 'deleted_bytes': sum(base['files'][p]['bytes'] for p in deleted),
            'update_files': ['README.md', release + '/snapshot.json', 'publication.json.gz']}
    write(plan_path, plan)
    print(f'Prepared withdrawal plan: {plan_path}')
    return plan


def check_plan(plan):
    if plan.get('schema') != 1 or plan.get('repo_id') != REPO_ID or not re.fullmatch(r'[0-9a-f]{40}', plan.get('base_revision', '')):
        raise ValueError('Unexpected withdrawal plan or target')
    package, base_package = Path(plan['package']), Path(plan['base_package'])
    for folder, field in [(package, 'publication_sha256'), (base_package, 'base_publication_sha256')]:
        if fingerprints(folder / 'publication.json.gz')['sha256'] != plan[field]:
            raise ValueError('Publication inventory changed after preparation')
    base = json.loads(gzip.decompress((base_package / 'publication.json.gz').read_bytes()))
    updated = load_package(package)
    release = updated['release_path']
    previous = read(base_package / release / 'snapshot.json')
    if fingerprints(base_package / release / 'snapshot.json') != base['files'][release + '/snapshot.json']:
        raise ValueError('Base snapshot changed after preparation')
    expected = retained_snapshot(previous, read(ROOT / 'content/leaderboard/release.json'), plan['removed_tasks'])
    public = read(package / release / 'snapshot.json')
    if public != expected or deletion_paths(previous, plan['removed_tasks'], release) != plan['delete_directories']:
        raise ValueError('Prepared withdrawal differs from the reviewed task set')
    deleted = validate_delta(base, updated, plan['delete_directories'])
    if len(deleted) != plan['deleted_files'] or sum(base['files'][p]['bytes'] for p in deleted) != plan['deleted_bytes']:
        raise ValueError('Deletion totals changed')
    if plan['update_files'] != ['README.md', release + '/snapshot.json', 'publication.json.gz']:
        raise ValueError('Only the dataset card, snapshot and publication inventory may be updated')
    referenced_files(package / release, public)
    return package, updated, check_site_snapshot(package, updated)


def verify_applied(api, package, plan, revision):
    """Also recognizes a successful commit when a previous run lost its response."""
    items = {i.path: i for i in api.get_paths_info(REPO_ID, plan['update_files'],
             revision=revision, repo_type='dataset')}
    for path in plan['update_files']:
        item = items.get(path)
        wanted = fingerprints(package / path)
        if item is None or not hasattr(item, 'blob_id') or item.size != wanted['bytes'] or (
            item.lfs.sha256 != wanted['sha256'] if item.lfs else item.blob_id != wanted['git_blob']
        ):
            raise ValueError('HF main changed without matching this update; no automatic deletion will be attempted')
    if api.get_paths_info(REPO_ID, [d.rstrip('/') for d in plan['delete_directories']],
                          revision=revision, repo_type='dataset'):
        raise ValueError('Withdrawn trial directories still exist remotely')


def apply(plan, package, manifest, source_hash, plan_path, site_origin):
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi
    anonymous = HfApi(token=False)
    info = anonymous.repo_info(REPO_ID, repo_type='dataset', revision='main',
                               expand=['sha', 'private', 'gated'], timeout=30)
    if info.private or info.gated:
        raise ValueError('The website requires a public, non-gated dataset')
    revision = info.sha
    if revision == plan['base_revision']:
        api = HfApi()
        api.whoami()
        operations = [CommitOperationDelete(path_in_repo=d, is_folder=True) for d in plan['delete_directories']]
        operations += [CommitOperationAdd(path_in_repo=p, path_or_fileobj=package / p) for p in plan['update_files']]
        commit = api.create_commit(REPO_ID, repo_type='dataset', revision='main',
            parent_commit=plan['base_revision'], operations=operations,
            commit_message=f'Withdraw two tasks; publish {manifest["tasks"]} tasks and {manifest["trials"]} trials')
        revision = commit.oid
        write(plan_path.with_suffix('.applied.json'), {'revision': revision, 'publication_sha256': plan['publication_sha256']})
        print(f'HF update committed: {revision}. Verifying before activating the website…', flush=True)
    else:
        print('HF main differs from the base; checking whether this exact update already succeeded.', flush=True)
    verify_applied(anonymous, package, plan, revision)
    verify_remote(anonymous, package, manifest, revision, site_origin)
    if check_site_snapshot(package, manifest) != source_hash:
        raise ValueError('Local snapshot changed during publication; website configuration was not updated')
    activate(package, manifest, revision, source_hash)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--prepare', action='store_true', help='Prepare the local withdrawal package without accessing HF')
    action.add_argument('--apply', action='store_true', help='Delete the exact retired directories and update HF metadata, then verify and pin the website')
    parser.add_argument('--jobs', type=Path)
    parser.add_argument('--base-package', type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument('--package', type=Path, default=PRUNED_PACKAGE)
    parser.add_argument('--plan', type=Path, default=DEFAULT_PLAN)
    parser.add_argument('--site-origin', default='https://search-swe.github.io')
    args = parser.parse_args()
    if args.prepare:
        if not args.jobs:
            parser.error('--prepare requires --jobs')
        prepare(args.jobs.absolute(), args.base_package.absolute(), args.package.absolute(), args.plan)
        return
    plan = read(args.plan)
    package, manifest, source_hash = check_plan(plan)
    print(f'Target: {REPO_ID}\nBase commit: {plan["base_revision"]}')
    print(f'Remove {len(plan["delete_directories"])} trial directories / {plan["deleted_files"]:,} files / {plan["deleted_bytes"] / 1024**2:.2f} MiB:')
    for directory in plan['delete_directories']:
        print('  ' + directory)
    print(f'Keep {manifest["tasks"]} tasks / {manifest["trials"]} trials unchanged. Update only: ' + ', '.join(plan['update_files']))
    if not args.apply:
        print('Offline check only: no HF requests or changes. Run with --apply to execute this exact plan.')
        return
    apply(plan, package, manifest, source_hash, args.plan, args.site_origin)


if __name__ == '__main__':
    main()
