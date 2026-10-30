"""Publication contracts: portable text, complete evidence, fixed revisions and integrity."""
import copy
import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import build_leaderboard as build
from export_trial_files import export_files
from import_results import encode, export_trajectory, read, scrub, write
from leaderboard_storage import resolve_snapshot
from publication import PublicText, REPO_ID, fingerprints, load_package
from prepare_hf_release import finalize, referenced_files
from upload_hf_release import verify_remote


class PublicTextTests(unittest.TestCase):
    def setUp(self):
        self.public = PublicText('/data/Search-SWE-Workspace/Search-SWE/run-eval-release/Search-SWE/jobs', scrub)

    def test_host_paths_portable_container_commands_preserved(self):
        text = 'file:///data/Search-SWE-Workspace/Search-SWE/run-eval-release/Search-SWE/tasks/demo /root/Search-SWE/env/lib.py /root/.codex/config /home/alice/private /app/run.sh /tests/test.py /tmp/log /data/train.json'
        value = self.public(text)
        self.assertNotIn('file://', value)
        self.assertNotIn('Search-SWE-Workspace', value)
        self.assertNotIn('/root/', value)
        self.assertNotIn('/home/alice', value)
        self.assertIn('${BENCHMARK_ROOT}/tasks/demo', value)
        self.assertIn('/app/run.sh /tests/test.py /tmp/log /data/train.json', value)
        nested = r'"output":"one\n/root/.cache/torch\n/home/oai/share/.cache"'
        self.assertNotIn('/root/', self.public(nested))
        self.assertNotIn('/home/', self.public(nested))

    def test_paths_split_after_sanitizing_and_download_matches_viewer(self):
        message = 'x' * 47990 + '/data/Search-SWE-Workspace/Search-SWE/run-eval-release/Search-SWE/jobs/demo/' + 'y' * 50000
        raw = {'steps': [{'step_id': 1, 'source': 'agent', 'message': message,
                         'tool_calls': [{'tool_call_id': 'a', 'function_name': 'exec',
                                         'arguments': {'env': {'API_KEY': 'short-private-secret'}, 'cmd': '/app/run.sh'}}]}]}
        original = copy.deepcopy(raw)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            export_trajectory(raw, folder, scrubber=self.public, public=True)
            step = read(folder / 'steps-0000.json')[0]
            restored = ''.join(read(folder / part) for part in step['message']['parts'])
            downloaded = json.loads(gzip.decompress((folder / 'trajectory.json.gz').read_bytes()))
            self.assertEqual(restored, self.public(message))
            self.assertEqual(restored, downloaded['steps'][0]['message'])
            self.assertNotIn('short-private-secret', step['calls'][0]['input'])
            self.assertNotIn('short-private-secret', json.dumps(downloaded))
            self.assertEqual(raw, original)

    def test_file_browser_and_archives_have_identical_portable_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            (source / 'verifier').mkdir(parents=True)
            (source / 'config.json').write_text(json.dumps({'path': '/root/Search-SWE/jobs/test', 'env': {'TOKEN': 'secret'}}))
            result = export_files(source, source / 'verifier', root / 'public', self.public, write)
            file = result['groups']['config'][0]
            folder = root / 'public/files'
            preview = ''.join(read(folder / p) for p in file['parts'])
            download = gzip.decompress((folder / file['download']).read_bytes()).decode()
            self.assertEqual(preview, download)
            self.assertNotIn('/root/Search-SWE', download)
            self.assertNotIn('secret', download)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = read(build.ROOT / 'content/leaderboard/release.json')
        self.source_hash = fingerprints(build.ROOT / 'content/leaderboard/release.json')['sha256']
        self.config = {'provider': 'huggingface', 'repo_id': REPO_ID, 'revision': 'a' * 40,
                       'release_path': 'releases/test', 'snapshot_id': self.snapshot['id'],
                       'source_hashes': self.snapshot['source_hashes'], 'site_snapshot_sha256': self.source_hash}

    def test_every_production_trace_and_download_uses_same_immutable_commit(self):
        pages = build.generate(self.config, production=True)
        self.assertEqual(len(pages), 2 + len(self.snapshot['entries']) + len(self.snapshot['trials']))
        prefix = f'https://huggingface.co/datasets/{REPO_ID}/resolve/{"a" * 40}/releases/test/'
        for html in pages.values():
            self.assertNotIn('/data/leaderboard/traces/', html)
            self.assertNotIn('Local preview', html)
            self.assertIn(prefix, html)
        trial = self.snapshot['trials'][0]
        html = pages[build.ROOT / f'leaderboard/trials/{trial["id"]}/index.html']
        for file in ['manifest.json', 'trajectory.json.gz', 'evaluation.json']:
            self.assertIn(prefix + f'trials/{trial["id"]}/{file}', html)

    def test_no_production_fallback_to_local_or_mutable_remote_data(self):
        for provider in ['local', 'preview']:
            with self.assertRaises(ValueError):
                resolve_snapshot(self.snapshot, {'provider': provider}, production=True)
        for revision in ['main', 'latest', 'a' * 7]:
            with self.assertRaises(ValueError):
                resolve_snapshot(self.snapshot, {**self.config, 'revision': revision}, True, self.source_hash)
        with self.assertRaises(ValueError):
            resolve_snapshot(self.snapshot, self.config, True, 'changed-local-snapshot')


class PackageTests(unittest.TestCase):
    def test_finalizing_again_preserves_the_publication_inventory_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = {'id': 'test', 'observed_at': '2026-10-31', 'source_hashes': {},
                        'tasks': [], 'entries': [], 'trials': [],
                        'publication': {'note': 'Exported-file hashes are in publication.json.gz.'}}
            finalize(root, snapshot, 'releases/test')
            before = (root / 'publication.json.gz').read_bytes()
            finalize(root, snapshot, 'releases/test')
            self.assertEqual((root / 'publication.json.gz').read_bytes(), before)
            self.assertNotIn('.gz.gz', read(root / 'releases/test/snapshot.json')['publication']['note'])

    def fixture(self, root):
        release = root / 'releases/test'
        directory = release / 'trials/demo'
        export_trajectory({'steps': [{'step_id': 1, 'source': 'user', 'message': 'hello'}]}, directory, public=True)
        write(directory / 'evaluation.json', {'score': 0})
        write(directory / 'files/index.json', {'groups': {}})
        snapshot = {'trials': [{'id': 'demo', 'steps': 1}]}
        write(release / 'snapshot.json', snapshot)
        (root / 'README.md').write_text('Public data\n')
        files = {p.relative_to(root).as_posix(): fingerprints(p) for p in root.rglob('*') if p.is_file()}
        manifest = {'schema': 1, 'repo_id': REPO_ID, 'release_path': 'releases/test', 'files': files}
        write(root / 'publication.json.gz', gzip.compress(encode(manifest), mtime=0))
        return manifest, snapshot

    def test_missing_refs_unlisted_files_and_changed_downloads_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, snapshot = self.fixture(root)
            referenced_files(root / 'releases/test', snapshot)
            load_package(root)
            (root / 'unlisted.txt').write_text('do not upload')
            with self.assertRaises(ValueError):
                load_package(root)
            (root / 'unlisted.txt').unlink()
            (root / 'releases/test/trials/demo/steps-0000.json').unlink()
            with self.assertRaises(ValueError):
                referenced_files(root / 'releases/test', snapshot)
            with self.assertRaises(ValueError):
                load_package(root)

    def test_remote_git_lfs_bytes_and_cors_are_checked_before_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _ = self.fixture(root)
            expected = {**manifest['files'], 'publication.json.gz': fingerprints(root / 'publication.json.gz')}
            remote = [SimpleNamespace(path=p, size=f['bytes'], blob_id=f['git_blob'],
                                     lfs=SimpleNamespace(sha256=f['sha256']) if p.endswith('.gz') else None)
                      for p, f in expected.items()]
            api = SimpleNamespace(list_repo_tree=lambda *a, **kw: remote, get_paths_info=lambda *a, **kw: [])
            class Response:
                headers = {'Access-Control-Allow-Origin': '*'}
                def __init__(self, request, **kw):
                    self.path = root / request.full_url.split('/' + 'a' * 40 + '/')[1]
                    self.assert_no_auth = 'Authorization' not in request.headers
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self): return self.path.read_bytes()
            with patch('upload_hf_release.urlopen', Response):
                verify_remote(api, root, manifest, 'a' * 40, 'https://search-swe.github.io')
                Response.headers = {}
                with self.assertRaisesRegex(ValueError, 'CORS'):
                    verify_remote(api, root, manifest, 'a' * 40, 'https://search-swe.github.io')
                remote[0].blob_id = 'wrong'
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    verify_remote(api, root, manifest, 'a' * 40, 'https://search-swe.github.io')


if __name__ == '__main__':
    unittest.main()
