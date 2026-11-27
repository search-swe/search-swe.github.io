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
from publication import REPO_ID, fingerprints, load_manifest, load_package
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


def published_base_payloads(package):
    """Use a prior upload receipt to bind the retained inventory to its published bytes."""
    receipt = read(package.with_name(package.name + '-uploaded.json'))
    base = load_manifest(package)
    if (receipt['repo_id'] != REPO_ID or receipt['snapshot_id'] != base['snapshot_id'] or
            receipt['publication_sha256'] != fingerprints(package / 'publication.json.gz')['sha256']):
        raise ValueError('Base package does not match its upload receipt')
    prefix = base['release_path'] + '/trials/'
    return base, {p: hashes for p, hashes in base['files'].items() if p.startswith(prefix)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-package', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--published-base', action='store_true', help='Reuse retained fingerprints from the base upload receipt')
    parser.add_argument('--payload-revision', help='Resume verification of a fully staged payload commit')
    parser.add_argument('--site-origin', default='https://search-swe.github.io')
    args = parser.parse_args()
    base_package, package = args.base_package.resolve(), args.package.resolve()
    if args.published_base:
        base, retained = published_base_payloads(base_package)
        manifest = load_package(package, retained=retained)
    else:
        base, manifest = load_package(base_package, check_content=False), load_package(package)
    additions = append_plan(base_package, package, base, manifest)
    source_sha = check_site_snapshot(package, manifest)
    print(f'Append {len(additions)} trials; preserve {base["trials"]} existing trials. No files will be deleted.', flush=True)
    if not args.upload:
        print('Dry run only; use --upload to publish with the existing HF login.')
        return
    api = authenticated_api()
    api.whoami()
    info = api.repo_info(REPO_ID, repo_type='dataset', expand=['sha', 'private', 'gated'])
    if info.private or info.gated:
        raise ValueError('The dataset must be public and non-gated')
    revision = info.sha
    verification = {}
    if args.published_base:
        receipt = read(base_package.with_name(base_package.name + '-uploaded.json'))
        if not metadata_matches(api, base_package, base, receipt['revision']):
            raise ValueError('Published base files differ from the upload receipt')
        verification['base_revision'] = receipt['revision']
    # Recover a successful final commit even if its response/local activation was lost.
    if not metadata_matches(api, package, manifest, revision):
        if not metadata_matches(api, base_package, base, revision):
            raise ValueError('Remote metadata differs from both base and prepared release; rebuild the append plan')
        if args.payload_revision:
            if revision != args.payload_revision:
                raise ValueError('Remote head differs from the staged payload commit')
        else:
            print('Uploading new trial directories with resumable Xet batches; committed files are skipped.', flush=True)
            api.upload_folder(repo_id=REPO_ID, folder_path=package, repo_type='dataset', revision='main',
                              allow_patterns=additions, commit_message=f'Add {len(additions)} Search-SWE trajectories: {manifest["snapshot_id"]}')
            revision = api.repo_info(REPO_ID, repo_type='dataset', expand=['sha']).sha
        print(f'Payload upload finished at {revision}; verifying every remote payload before publication.', flush=True)
        if not metadata_matches(api, base_package, base, revision):
            raise ValueError('Remote publication changed during upload; metadata was not replaced')
        staged = copy.deepcopy(manifest)
        snapshot_path = manifest['release_path'] + '/snapshot.json'
        staged['files'][snapshot_path] = base['files'][snapshot_path]
        verify_remote(api, package, staged, revision, args.site_origin, include_metadata=False, **verification)
        if check_site_snapshot(package, manifest) != source_sha:
            raise ValueError('Local snapshot changed during upload')
        from huggingface_hub import CommitOperationAdd
        commit = retry_429(lambda: api.create_commit(REPO_ID, repo_type='dataset', parent_commit=revision,
            commit_message=f'Publish Search-SWE: {manifest["snapshot_id"]}',
            operations=[CommitOperationAdd(path_in_repo=p, path_or_fileobj=package / p)
                        for p in ['README.md', 'publication.json.gz', snapshot_path]]), 'append metadata commit')
        revision = commit.oid
    print(f'Checking the complete publication at {revision} before activating the local homepage.', flush=True)
    verify_remote(api, package, manifest, revision, args.site_origin, **verification)
    if check_site_snapshot(package, manifest) != source_sha:
        raise ValueError('Local snapshot changed during upload')
    activate(package, manifest, revision, source_sha)


if __name__ == '__main__':
    main()
