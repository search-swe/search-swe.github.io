#!/usr/bin/env python3
"""Fetch the pinned PR #3 source files needed to publish leaderboard results."""
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import httpx
from huggingface_hub import HfApi

from hf_network import retry_429
from import_results import ROOT, write

SOURCES = {
    'claude-sonnet-5.5': ('claude-sonnet-5-5', 'e0758f61d434f416627c20b74f97e3948a3d23f7',
                         {'rust-bm25-search', 'large-scale-formula-retrieval'}),
    'gemini-4-argon': ('gemini-4-argon', '76b0a0e6c349e57dbaab09888ab8732b0cf321c8',
                      {'large-scale-formula-retrieval'}),
}
SOURCE_DIR = ROOT / '.build/pr3-publication-source'


def download(output, cache):
    api = HfApi(token=False)
    with httpx.Client(timeout=35, follow_redirects=True) as client, ThreadPoolExecutor(max_workers=8) as pool:
        for name, revision, replacements in SOURCES.values():
            repo = 'ubowang/search-swe-' + name
            info = retry_429(lambda: api.dataset_info(repo, revision=revision, files_metadata=True), repo)
            if info.sha != revision:
                raise ValueError(f'Wrong source revision for {repo}')
            files = {}
            for item in info.siblings:
                path = item.rfilename
                parts = path.split('/')
                if (path in ('results.json', 'manifest.json', 'provenance.json', 'provenance_index.json', 'regrade_index.json')
                        or (len(parts) >= 3 and parts[1] not in replacements and (
                            (parts[0] == 'trajectories' and parts[-1] in ('trajectory.json', 'reward.json', 'reward.txt'))
                            or (parts[0] == 'evidence' and parts[-1] in ('result.json', 'reward.json', 'regrade.json', 'reward-details.json'))))):
                    files[path] = (item.size, item.blob_id, item.lfs.sha256 if item.lfs else None)

            def fetch(pair):
                path, (size, blob, sha) = pair
                target = output / name / path
                if target.resolve().is_relative_to(output.resolve()) is False:
                    raise ValueError(f'Invalid source path: {path}')

                def verified(body):
                    return (len(body) == size and (hashlib.sha256(body).hexdigest() == sha if sha else
                            hashlib.sha1(f'blob {len(body)}\0'.encode() + body).hexdigest() == blob))

                options = [target, *(p / ('search-swe-' + name) / path for p in cache)]
                for candidate in options:
                    if candidate.is_file():
                        data = candidate.read_bytes()
                        if verified(data):
                            if candidate != target:
                                write(target, data)
                            return
                url = f'https://huggingface.co/datasets/{repo}/resolve/{revision}/{quote(path)}'
                def get():
                    response = client.get(url)
                    response.raise_for_status()
                    return response.content
                data = retry_429(get, f'{repo} file download')
                if not verified(data):
                    raise ValueError(f'File hash mismatch: {repo}/{path}')
                write(target, data)

            list(pool.map(fetch, files.items()))
            write(output / name / 'source-inventory.json', {'repo': repo, 'revision': revision, 'files': files})
            print(f'{repo}: verified {len(files)} files at {revision}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=SOURCE_DIR)
    parser.add_argument('--cache', type=Path, action='append', default=[])
    args = parser.parse_args()
    download(args.output, args.cache)


if __name__ == '__main__':
    main()
