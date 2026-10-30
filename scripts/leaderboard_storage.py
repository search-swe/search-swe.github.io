"""Resolve static page assets against local exports or a verified HF commit."""
from __future__ import annotations

import copy
import re
from urllib.parse import urljoin, urlsplit

from publication import REPO_ID


def resolve_snapshot(snapshot, storage=None, production=False, source_sha256=None):
    storage = storage or {'provider': 'local'}
    provider = storage.get('provider')
    if provider == 'local':
        if production:
            raise ValueError('Production build requires a verified Hugging Face revision. Run upload_hf_release.py --upload first.')
        return snapshot
    if provider not in {'huggingface', 'preview'} or (production and provider != 'huggingface'):
        raise ValueError('Unsupported data provider for this build')
    if storage.get('snapshot_id') != snapshot['id'] or storage.get('source_hashes') != snapshot['source_hashes']:
        raise ValueError('Storage configuration and local result snapshot do not match')
    if provider == 'huggingface':
        if storage.get('repo_id') != REPO_ID or not re.fullmatch(r'[0-9a-f]{40}', storage.get('revision', '')):
            raise ValueError('Hugging Face data must use search-swe/trajectories and a full immutable commit SHA')
        if storage.get('site_snapshot_sha256') != source_sha256:
            raise ValueError('Local snapshot changed after upload verification; prepare and verify a matching release')
        if not re.fullmatch(r'releases/[A-Za-z0-9._-]+', storage.get('release_path', '')):
            raise ValueError('Invalid public release path')
        base = f'https://huggingface.co/datasets/{REPO_ID}/resolve/{storage["revision"]}/{storage["release_path"]}/'
    else:
        base = storage['data_base_url'].rstrip('/') + '/'
        parsed = urlsplit(base)
        if not (base.startswith('/') and not base.startswith('//')) and not (
            parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1'}
        ):
            raise ValueError('Preview data must come from a local server')
    snapshot = copy.deepcopy(snapshot)
    snapshot['data_source'] = {'provider': provider, 'base_url': base}
    snapshot['download_url'] = urljoin(base, 'snapshot.json')
    for trial in snapshot['trials']:
        trial['trajectory_url'] = urljoin(base, f'trials/{trial["id"]}/manifest.json')
    return snapshot
