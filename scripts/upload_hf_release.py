"""Check a prepared release; upload only with --upload, then pin and build the site."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from import_results import ROOT, read, write
from publication import DEFAULT_PACKAGE, REPO_ID, fingerprints, load_package


def check_site_snapshot(package, manifest):
    """Do not attach an uploaded release to a different local leaderboard."""
    source = ROOT / 'content/leaderboard/release.json'
    local = read(source)
    exported = read(package / manifest['release_path'] / 'snapshot.json')
    def comparable(snapshot):
        value = copy.deepcopy(snapshot)
        value.pop('publication', None)
        for trial in value['trials']:
            trial.pop('trajectory_url', None)
            trial.pop('redacted_fields', None)
        return value
    if comparable(local) != comparable(exported):
        raise ValueError('Prepared release differs from the local leaderboard. Rebuild the matching package before upload.')
    return hashlib.sha256(source.read_bytes()).hexdigest()


def verify_remote(api, package, manifest, revision, site_origin):
    """Verify every file at a fixed commit, then exercise anonymous browser reads."""
    expected = dict(manifest['files'])
    expected['publication.json.gz'] = fingerprints(package / 'publication.json.gz')
    remote = {}
    for item in api.list_repo_tree(REPO_ID, path_in_repo=manifest['release_path'],
                                   recursive=True, revision=revision, repo_type='dataset'):
        if hasattr(item, 'blob_id'):
            remote[item.path] = item
    for item in api.get_paths_info(REPO_ID, ['README.md', 'publication.json.gz'], revision=revision, repo_type='dataset'):
        remote[item.path] = item
    for path, hashes in expected.items():
        item = remote.get(path)
        if item is None or item.size != hashes['bytes']:
            raise ValueError(f'Missing or incomplete remote file: {path}')
        if item.lfs:
            actual = item.lfs.sha256
            wanted = hashes['sha256']
        else:
            actual, wanted = item.blob_id, hashes['git_blob']
        if actual != wanted:
            raise ValueError(f'Remote content hash mismatch: {path}')
    release = manifest['release_path']
    snapshot = read(package / release / 'snapshot.json')
    trial = snapshot['trials'][0]
    trial_dir = f'{release}/trials/{trial["id"]}'
    first = read(package / trial_dir / 'manifest.json')['steps'][0]['chunk']
    samples = [f'{release}/snapshot.json', f'{trial_dir}/manifest.json',
               f'{trial_dir}/{first}', f'{trial_dir}/files/index.json', f'{trial_dir}/trajectory.json.gz']
    # Include a larger plain JSON file to exercise the redirected/CDN path as well.
    samples.append(max((p for p in expected if p.endswith('.json')), key=lambda p: expected[p]['bytes']))
    for path in dict.fromkeys(samples):
        url = f'https://huggingface.co/datasets/{REPO_ID}/resolve/{revision}/{path}'
        request = Request(url, headers={'Origin': site_origin})
        with urlopen(request, timeout=120) as response:
            if response.headers.get('Access-Control-Allow-Origin') not in {'*', site_origin}:
                raise ValueError(f'Anonymous browser CORS check failed: {path}')
            body = response.read()
        if hashlib.sha256(body).hexdigest() != expected[path]['sha256']:
            raise ValueError(f'Anonymous download hash mismatch: {path}')
        if path.endswith('.json'):
            json.loads(body)
    print(f'Verified all {len(expected):,} remote files and anonymous JSON/gzip downloads with CORS.')


def activate(package, manifest, revision, site_snapshot_sha256):
    from build_leaderboard import generate, write_pages
    config = {'provider': 'huggingface', 'repo_id': REPO_ID, 'revision': revision,
              'release_path': manifest['release_path'], 'snapshot_id': manifest['snapshot_id'],
              'source_hashes': manifest['source_hashes'], 'site_snapshot_sha256': site_snapshot_sha256,
              'publication_sha256': fingerprints(package / 'publication.json.gz')['sha256']}
    # Resolve/validate all pages before changing the website's data configuration.
    pages = generate(config, production=True)
    write(ROOT / 'content/leaderboard/storage.json', config)
    write_pages(pages)
    receipt = package.with_name(package.name + '-uploaded.json')
    write(receipt, config)
    print(f'Pinned HF revision: {revision}\nReceipt: {receipt}')
    print(f'Generated {len(pages)} production pages. No Git commit, push, or website deployment was performed.')
    print('Next check: python scripts/build_leaderboard.py --production --check')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=DEFAULT_PACKAGE)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--upload', action='store_true', help='Upload to HF, verify, then update local website URLs')
    action.add_argument('--verify-revision', help='Verify an already uploaded full commit SHA, then update local website URLs')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--site-origin', default='https://search-swe.github.io')
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('--workers must be positive')
    if args.verify_revision and not re.fullmatch(r'[0-9a-f]{40}', args.verify_revision):
        parser.error('--verify-revision requires a full commit SHA')
    package = args.package.absolute()
    print(f'Checking public package: {package}', flush=True)
    manifest = load_package(package)
    source_sha = check_site_snapshot(package, manifest)
    print(f'Checked {len(manifest["files"]):,} files / {manifest["trials"]} trials / {manifest["total_bytes"] / 1024**3:.2f} GiB.')
    if not args.upload and not args.verify_revision:
        print(f'Dry run only. Target: https://huggingface.co/datasets/{REPO_ID}')
        print('Run the same command with --upload to publish. No network requests or writes were made.')
        return
    from huggingface_hub import HfApi
    anonymous = HfApi(token=False)
    info = anonymous.repo_info(REPO_ID, repo_type='dataset')
    if info.private or info.gated:
        raise ValueError('The website requires a public, non-gated dataset')
    revision = args.verify_revision
    if args.upload:
        api = HfApi()  # Uses hf auth login or HF_TOKEN; never embed a token in site files.
        api.whoami()  # Fail before starting if authentication is missing or invalid.
        print('Uploading resumably. If interrupted, repeat this command with the same package.')
        api.upload_large_folder(REPO_ID, package, repo_type='dataset', revision='main',
                                num_workers=args.workers,
                                allow_patterns=['README.md', manifest['release_path'] + '/**'])
        # Publish the inventory last. Existing releases are never deleted.
        commit = api.upload_file(path_or_fileobj=package / 'publication.json.gz',
                                 path_in_repo='publication.json.gz', repo_id=REPO_ID, repo_type='dataset',
                                 commit_message=f'Complete Search-SWE release {manifest["snapshot_id"]}')
        revision = commit.oid
        print(f'Upload complete: {revision}. Verifying before changing website URLs…')
    verify_remote(anonymous, package, manifest, revision, args.site_origin)
    # Recheck in case local result files were edited during the upload.
    if check_site_snapshot(package, manifest) != source_sha:
        raise ValueError('Local snapshot changed during upload; website configuration was not updated')
    activate(package, manifest, revision, source_sha)


if __name__ == '__main__':
    main()
