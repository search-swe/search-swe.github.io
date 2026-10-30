"""Portable public text and integrity checks shared by preparation and upload."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

REPO_ID = 'search-swe/trajectories'
DEFAULT_PACKAGE = Path(__file__).resolve().parents[1] / '.build/hf-trajectories'
PATH_BOUNDARY = r'(?:(?<![\w/])|(?<=\\n)|(?<=\\r)|(?<=\\t))'
PRIVATE_ROOT = re.compile(r'/data/Search-SWE-Workspace|/root/Search-SWE|' + PATH_BOUNDARY + r'(?:/home/[^/\s]+/|/root/)')
CREDENTIAL = re.compile(r'\b(?:sk-(?:or-v1-)?[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,})\b')


class PublicText:
    """Normalize host paths before chunking. Container paths such as /app stay intact."""
    def __init__(self, jobs, scrub):
        self.scrub = scrub
        jobs = Path(jobs).absolute()
        roots = {
            str(jobs.parent): '${BENCHMARK_ROOT}',
            str(jobs.parent.parent): '${EVAL_ROOT}',
            '/data/Search-SWE-Workspace/Search-SWE': '${WORKSPACE_ROOT}',
            '/data/Search-SWE-Workspace': '${WORKSPACE_ROOT}',
            '/root/Search-SWE': '${WORKSPACE_ROOT}',
        }
        self.roots = sorted(roots.items(), key=lambda item: -len(item[0]))

    def __call__(self, text):
        text = self.scrub(text)
        for root, alias in self.roots:
            text = text.replace('file://' + root, alias).replace(root, alias)
        # Home directories in traceback/config paths are machine-specific too.
        if '/root' in text:
            text = re.sub(PATH_BOUNDARY + r'(?:file://)?/root(?=/|[\s\"\x27]|$)', '${USER_HOME}', text)
        if '/home/' in text:
            text = re.sub(PATH_BOUNDARY + r'(?:file://)?/home/[^/\s\"\x27]+', '${USER_HOME}', text)
        return text


def safe_path(root, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts or '\\' in relative:
        raise ValueError(f'Unsafe package path: {relative}')
    target = root / path
    if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Package path escapes its root: {relative}')
    return target


def fingerprints(path):
    """Both hashes let upload verification handle regular Git and LFS/Xet files."""
    size = path.stat().st_size
    sha = hashlib.sha256()
    git = hashlib.sha1(f'blob {size}\0'.encode())
    with path.open('rb') as source:
        while block := source.read(1024 * 1024):
            sha.update(block)
            git.update(block)
    return {'bytes': size, 'sha256': sha.hexdigest(), 'git_blob': git.hexdigest()}


def check_text(path):
    data = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    text = data.decode('utf-8')
    has_path = any(marker in text for marker in ('/data/Search-SWE-Workspace', '/root/', '/home/'))
    has_token = any(marker in text for marker in ('sk-', 'hf_', 'ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_'))
    if (has_path and PRIVATE_ROOT.search(text)) or (has_token and CREDENTIAL.search(text)):
        # Never print matched credential values in a report or error.
        raise ValueError(f'Private path or credential pattern remains in {path.name}')
    if path.suffix == '.json':
        json.loads(text)


def load_package(package, check_content=True):
    """Verify exactly the manifest's files; never upload unlisted local files."""
    package = Path(package)
    manifest_path = package / 'publication.json.gz'
    manifest = json.loads(gzip.decompress(manifest_path.read_bytes()))
    if manifest.get('schema') != 1 or manifest.get('repo_id') != REPO_ID:
        raise ValueError('Unexpected publication schema or dataset repository')
    if not re.fullmatch(r'releases/[A-Za-z0-9._-]+', manifest.get('release_path', '')):
        raise ValueError('Invalid publication release path')
    for path in package.rglob('*'):
        if path.is_symlink():
            raise ValueError(f'Symlinks are not allowed in a public package: {path.relative_to(package)}')
    allowed = set(manifest['files']) | {'publication.json.gz'}
    actual = {p.relative_to(package).as_posix() for p in package.rglob('*')
              if p.is_file() and not p.relative_to(package).as_posix().startswith('.cache/')}
    if actual != allowed:
        raise ValueError(f'Package file set changed: {len(allowed - actual)} missing, {len(actual - allowed)} unlisted')
    for count, (relative, expected) in enumerate(manifest['files'].items(), 1):
        path = safe_path(package, relative)
        if fingerprints(path) != expected:
            raise ValueError(f'Package content changed: {relative}')
        if check_content:
            check_text(path)
        if count % 10000 == 0:
            print(f'Verified {count:,} / {len(manifest["files"]):,} public files', flush=True)
    return manifest
