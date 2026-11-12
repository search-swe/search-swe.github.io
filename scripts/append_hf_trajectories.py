"""Append new model trials, verify all payloads, then atomically publish metadata.

Existing trial bytes must match the verified base package exactly. Old immutable
commit URLs remain valid. Interrupted uploads resume with the same packages.
No Git staging, commit, push or deletion is performed.
"""
import argparse
import copy
from pathlib import Path

from hf_network import authenticated_api, retry_429
from import_results import read
from publication import REPO_ID, fingerprints, load_package
from upload_hf_release import activate, check_site_snapshot, verify_remote


def append_plan(base_package, package, base, manifest):
    release = base['release_path']
    if manifest['release_path'] != release:
        raise ValueError('Append must retain the base release directory')
    before = read(base_package / release / 'snapshot.json')
    after = read(package / release / 'snapshot.json')
    old = {t['id'] for t in before['trials']}
    new = {t['id'] for t in after['trials']}
    if not old < new:
        raise ValueError('Append must preserve all existing trials and add new trials')
    prefix = release + '/trials/'
    old_files = {p: h for p, h in base['files'].items() if p.startswith(prefix)}
    for path, hashes in old_files.items():
        if manifest['files'].get(path) != hashes:
            raise ValueError(f'Existing trial payload changed: {path}')
    additions = [prefix + trial + '/**' for trial in sorted(new - old)]
    allowed = {release + '/snapshot.json', 'README.md'}
    for path in manifest['files']:
        if path not in old_files and path not in allowed and not any(
                path.startswith(pattern[:-2]) for pattern in additions):
            raise ValueError(f'Unexpected append file: {path}')
    return additions


def metadata_matches(api, package, manifest, revision):
    paths = ['README.md', 'publication.json.gz', manifest['release_path'] + '/snapshot.json']
    actual = {f.path: f for f in api.get_paths_info(REPO_ID, paths, revision=revision, repo_type='dataset')}
    for path in paths:
        want = fingerprints(package / path)
        item = actual.get(path)
        if item is None or item.size != want['bytes']:
            return False
        if (item.lfs.sha256 if item.lfs else item.blob_id) != (want['sha256'] if item.lfs else want['git_blob']):
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-package', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--site-origin', default='https://search-swe.github.io')
    args = parser.parse_args()
    base_package, package = args.base_package.resolve(), args.package.resolve()
    base, manifest = load_package(base_package), load_package(package)
    additions = append_plan(base_package, package, base, manifest)
    source_sha = check_site_snapshot(package, manifest)
    print(f'Append {len(additions)} trials; preserve {base["trials"]} existing trials. No files will be deleted.', flush=True)
    if not args.upload:
        print('Dry run only; use --upload to publish with the existing HF login.')
        return
    api = authenticated_api()
    api.whoami()
    info = api.repo_info(REPO_ID, repo_type='dataset')
    if info.private or info.gated:
        raise ValueError('The dataset must be public and non-gated')
    revision = info.sha
    # Recover a successful final commit even if its response/local activation was lost.
    if not metadata_matches(api, package, manifest, revision):
        if not metadata_matches(api, base_package, base, revision):
            raise ValueError('Remote metadata differs from both base and prepared release; rebuild the append plan')
        print('Uploading new trial directories with resumable Xet batches; committed files are skipped.', flush=True)
        # Current Hub + hf_xet stream and commit adaptive batches; reruns detect
        # already committed files and deduplicate uploaded chunks on the server.
        api.upload_folder(repo_id=REPO_ID, folder_path=package, repo_type='dataset', revision='main',
                          allow_patterns=additions, commit_message='Add Search-SWE Kimi K3.1 Pro trajectories')
        revision = api.repo_info(REPO_ID, repo_type='dataset').sha
        print(f'Payload upload finished at {revision}; verifying every remote payload before publication.', flush=True)
        if not metadata_matches(api, base_package, base, revision):
            raise ValueError('Remote publication changed during upload; metadata was not replaced')
        staged = copy.deepcopy(manifest)
        snapshot_path = manifest['release_path'] + '/snapshot.json'
        staged['files'][snapshot_path] = base['files'][snapshot_path]
        verify_remote(api, package, staged, revision, args.site_origin, include_metadata=False)
        if check_site_snapshot(package, manifest) != source_sha:
            raise ValueError('Local snapshot changed during upload')
        from huggingface_hub import CommitOperationAdd
        commit = retry_429(lambda: api.create_commit(REPO_ID, repo_type='dataset', parent_commit=revision,
            commit_message=f'Publish Search-SWE Kimi K3.1 Pro: {manifest["snapshot_id"]}',
            operations=[CommitOperationAdd(path_in_repo=p, path_or_fileobj=package / p)
                        for p in ['README.md', 'publication.json.gz', snapshot_path]]), 'append metadata commit')
        revision = commit.oid
    print(f'Checking the complete publication at {revision} before activating the local homepage.', flush=True)
    verify_remote(api, package, manifest, revision, args.site_origin)
    if check_site_snapshot(package, manifest) != source_sha:
        raise ValueError('Local snapshot changed during upload')
    activate(package, manifest, revision, source_sha)


if __name__ == '__main__':
    main()
