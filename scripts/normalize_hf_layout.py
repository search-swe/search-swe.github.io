#!/usr/bin/env python3
"""Move the verified corpus to releases/current and retire superseded releases.

Dry run by default. --apply publishes one fast-forward Git commit, verifies every
remote file and anonymous downloads, then activates the local homepage. Git tree
reuse preserves all trial bytes without downloading or uploading them again.
"""
import argparse
import copy
import gzip
import hashlib
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from hf_network import authenticated_api
from import_results import ROOT, encode, read, write
from prepare_hf_release import dataset_card, referenced_files
from publication import REPO_ID, CURRENT_RELEASE, fingerprints, load_package
from upload_hf_release import activate, check_site_snapshot, verify_remote


def git(directory, *args, data=None):
    return subprocess.check_output(['git', '--git-dir=' + str(directory), *args], input=data)


def lfs_pointer(hashes):
    return (f'version https://git-lfs.github.com/spec/v1\noid sha256:{hashes["sha256"]}\n'
            f'size {hashes["bytes"]}\n').encode()


def blob_id(data):
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()


def git_files(directory, revision):
    result = {}
    for line in git(directory, 'ls-tree', '-rz', revision).split(b'\0'):
        if not line:
            continue
        metadata, path = line.decode().split('\t', 1)
        mode, kind, oid = metadata.split()
        if mode != '100644' or kind != 'blob':
            raise ValueError('Unexpected non-regular repository file')
        result[path] = oid
    return result


def verify_git_files(files, package, manifest):
    expected = {**manifest['files'], 'publication.json.gz': fingerprints(package / 'publication.json.gz')}
    prefix = manifest['release_path'] + '/'
    if {p for p in files if p.startswith(prefix)} != {p for p in expected if p.startswith(prefix)}:
        raise ValueError('Git release contains missing or unlisted files')
    for path, hashes in expected.items():
        if files.get(path) not in {hashes['git_blob'], blob_id(lfs_pointer(hashes))}:
            raise ValueError(f'Git content differs from verified package: {path}')


def relocate(source, package, manifest):
    """Change only inventory paths and the dataset card; payloads are immutable."""
    if source.resolve() == package.resolve() or manifest['release_path'] == CURRENT_RELEASE:
        raise ValueError('Use separate source and destination packages for migration')
    target = copy.deepcopy(manifest)
    prefix = manifest['release_path'] + '/'
    if any(p != 'README.md' and not p.startswith(prefix) for p in manifest['files']):
        raise ValueError('Unexpected file outside the source release')
    target['release_path'] = CURRENT_RELEASE
    target['files'] = {(CURRENT_RELEASE + '/' + p[len(prefix):] if p.startswith(prefix) else p): h
                       for p, h in manifest['files'].items()}
    if (package / 'publication.json.gz').exists():
        existing = load_package(package, check_content=False)
        # README can change with documentation; payloads and snapshot cannot.
        for path, hashes in target['files'].items():
            if path != 'README.md' and existing['files'].get(path) != hashes:
                raise ValueError('Destination package contains different payloads')
        if existing['release_path'] != CURRENT_RELEASE or existing['snapshot_id'] != manifest['snapshot_id']:
            raise ValueError('Destination package belongs to another snapshot')
        return existing
    destination = package / CURRENT_RELEASE
    if package.exists() and any(package.iterdir()):
        raise ValueError('Use an empty destination package')
    shutil.copytree(source / manifest['release_path'], destination, copy_function=shutil.copyfile)
    snapshot = read(destination / 'snapshot.json')
    referenced_files(destination, snapshot)
    write(package / 'README.md', dataset_card(snapshot, CURRENT_RELEASE).encode())
    target['files']['README.md'] = fingerprints(package / 'README.md')
    target['total_bytes'] = sum(h['bytes'] for h in target['files'].values())
    write(package / 'publication.json.gz', gzip.compress(encode(target), mtime=0))
    # Keep the private receipt next to the migrated package for future appends.
    usage = source.with_suffix('.usage.json')
    if usage.exists():
        shutil.copyfile(usage, package.with_suffix('.usage.json'))
    return load_package(package, check_content=False)


def trial_key(trial):
    config = trial['configuration']
    return (trial['task'], config['model'], config['agent'], config['version'], config['effort'], config['provider'])


def check_superseded(previous, current):
    old = {trial_key(t) for t in previous['trials']}
    new = {trial_key(t) for t in current['trials'] if t['valid']}
    if not old or not old <= new:
        raise ValueError('Old release has configurations absent from the current valid selection')


def tree_entries(directory, revision):
    return {line.split('\t', 1)[1]: line.split('\t', 1)[0]
            for line in git(directory, 'ls-tree', revision).decode().splitlines()}


def make_tree(directory, entries):
    data = ''.join(f'{metadata}\t{name}\n' for name, metadata in sorted(entries.items())).encode()
    return git(directory, 'mktree', '--missing', data=data).decode().strip()


def push(directory, commit):
    # Credentials go only to Git's helper pipe, never command arguments or logs.
    with tempfile.TemporaryDirectory(prefix='hf-layout-auth-') as temporary:
        helper = Path(temporary) / 'credential.py'
        helper.write_text("import sys\nfrom huggingface_hub import get_token\n"
                          "fields = dict(line.rstrip('\\n').split('=', 1) for line in sys.stdin if '=' in line)\n"
                          "if sys.argv[-1] == 'get' and fields.get('host') == 'huggingface.co':\n"
                          "    print('username=hf_user')\n    print('password=' + get_token())\n")
        subprocess.run(['git', '--git-dir=' + str(directory), '-c', 'credential.helper=', '-c',
                        'credential.helper=!' + shlex.join([sys.executable, str(helper)]),
                        'push', 'origin', commit + ':refs/heads/main'], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-package', type=Path, required=True)
    parser.add_argument('--package', type=Path, default=ROOT / '.build/hf-trajectories-current')
    parser.add_argument('--git-dir', type=Path, default=ROOT / '.build/hf-layout.git')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    source, package, directory = args.source_package.resolve(), args.package.resolve(), args.git_dir.resolve()
    storage = read(ROOT / 'content/leaderboard/storage.json')
    # Only relocate an already published, verified package. Rehash every byte;
    # there is no need to repeat text redaction when no payload bytes change.
    if fingerprints(source / 'publication.json.gz')['sha256'] != storage['publication_sha256']:
        if not (package / 'publication.json.gz').exists() or fingerprints(package / 'publication.json.gz')['sha256'] != storage['publication_sha256']:
            raise ValueError('Source is not the verified homepage publication')
    before = load_package(source, check_content=False)
    manifest = relocate(source, package, before)
    source_sha = check_site_snapshot(package, manifest)
    api = authenticated_api()
    info = api.repo_info(REPO_ID, repo_type='dataset')
    if info.private or info.gated:
        raise ValueError('The dataset must remain public and non-gated')
    if not directory.exists():
        subprocess.run(['git', 'clone', '--bare', '--depth=1', '--filter=blob:none',
                        'https://huggingface.co/datasets/' + REPO_ID, str(directory)], check=True)
    git(directory, 'fetch', '--depth=1', '--filter=blob:none', 'origin', info.sha)
    files = git_files(directory, info.sha)
    releases = tree_entries(directory, info.sha + ':releases')
    if set(releases) == {'current'}:
        verify_git_files(files, package, manifest)
        revision = info.sha
        print('This exact normalized publication already exists; finishing verification.', flush=True)
    else:
        if info.sha != storage['revision'] or 'current' in releases:
            raise ValueError('Remote changed or target directory already exists; review before migration')
        verify_git_files(files, source, before)
        snapshot = read(package / CURRENT_RELEASE / 'snapshot.json')
        old_name = before['release_path'].split('/')[1]
        for name in releases:
            if name == old_name:
                continue
            filename = api.hf_hub_download(REPO_ID, f'releases/{name}/snapshot.json', repo_type='dataset', revision=info.sha)
            previous = read(Path(filename))
            check_superseded(previous, snapshot)
            count = sum(p.startswith(f'releases/{name}/') for p in files)
            print(f'Retire releases/{name}: {len(previous["trials"])} superseded trials, {count:,} files.', flush=True)
        print(f'Move {before["release_path"]} to {CURRENT_RELEASE}: {manifest["trials"]} trials; all payload bytes preserved.', flush=True)
        if not args.apply:
            print('Dry run complete. Use --apply to publish and verify this layout.')
            return
        from huggingface_hub import CommitOperationAdd
        operations = [CommitOperationAdd(path_in_repo=p, path_or_fileobj=package / p)
                      for p in ('README.md', 'publication.json.gz')]
        api.preupload_lfs_files(REPO_ID, operations, repo_type='dataset', revision='main', free_memory=False)
        root = tree_entries(directory, info.sha)
        release_tree = make_tree(directory, {'current': releases[old_name]})
        root['releases'] = '040000 tree ' + release_tree
        for operation in operations:
            path = operation.path_in_repo
            data = lfs_pointer(fingerprints(package / path)) if operation._upload_mode == 'lfs' else (package / path).read_bytes()
            oid = git(directory, 'hash-object', '-w', '--stdin', data=data).decode().strip()
            root[path] = '100644 blob ' + oid
        tree = make_tree(directory, root)
        proposed = git_files(directory, tree)
        verify_git_files(proposed, package, manifest)
        expected = set(manifest['files']) | {'publication.json.gz'} | {p for p in files if not p.startswith('releases/')}
        if set(proposed) != expected:
            raise ValueError('Migration has unexpected additions or deletions')
        for name in ('name', 'email'):
            value = subprocess.check_output(['git', '-C', str(ROOT), 'config', 'user.' + name]).decode().strip()
            git(directory, 'config', 'user.' + name, value)
        revision = git(directory, 'commit-tree', tree, '-p', info.sha,
                       data=b'Normalize trajectories under releases/current and retire superseded releases\n').decode().strip()
        write(ROOT / '.build/hf-layout-migration.json', {'parent': info.sha, 'revision': revision,
              'old_directories': list(releases), 'release_path': CURRENT_RELEASE,
              'publication_sha256': fingerprints(package / 'publication.json.gz')['sha256']})
        if check_site_snapshot(package, manifest) != source_sha:
            raise ValueError('Homepage snapshot changed during preparation')
        push(directory, revision)  # Ordinary fast-forward; concurrent updates reject the push.
    if args.apply:
        verify_remote(api, package, manifest, revision, 'https://search-swe.github.io')
        if check_site_snapshot(package, manifest) != source_sha:
            raise ValueError('Homepage changed during remote verification')
        activate(package, manifest, revision, source_sha)


if __name__ == '__main__':
    main()
