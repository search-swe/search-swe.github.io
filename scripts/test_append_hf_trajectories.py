"""Appending must never replace/delete old payloads or publish unrelated files."""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import append_hf_trajectories as append
from append_hf_trajectories import append_plan
from import_results import write


class AppendTests(unittest.TestCase):
    def test_payload_verification_precedes_atomic_metadata_and_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in ['README.md', 'publication.json.gz', 'releases/base/snapshot.json']:
                write(root / path, b'fixture')
            base = {'release_path': 'releases/base', 'trials': 141,
                    'files': {'releases/base/snapshot.json': {'sha256': 'old'}}}
            manifest = {**base, 'snapshot_id': 'new', 'files': {'releases/base/snapshot.json': {'sha256': 'new'}}}
            api = Mock()
            api.repo_info.return_value = SimpleNamespace(sha='parent', private=False, gated=False)
            api.create_commit.return_value = SimpleNamespace(oid='complete')
            calls = []
            api.upload_folder.side_effect = lambda *a, **kw: calls.append('upload')
            def commit(*args, **kwargs):
                self.assertEqual(kwargs['parent_commit'], 'parent')
                self.assertEqual(len(kwargs['operations']), 3)
                calls.append('commit')
                return SimpleNamespace(oid='complete')
            api.create_commit.side_effect = commit
            def verify(api, package, manifest, revision, origin, include_metadata=True):
                self.assertEqual(manifest['files']['releases/base/snapshot.json']['sha256'], 'new' if include_metadata else 'old')
                calls.append('verify-final' if include_metadata else 'verify-payload')
            with patch('sys.argv', ['append', '--base-package', str(root), '--package', str(root), '--upload']), \
                 patch.object(append, 'load_package', side_effect=[base, manifest]), \
                 patch.object(append, 'append_plan', return_value=['releases/base/trials/kimi/**']), \
                 patch.object(append, 'check_site_snapshot', return_value='hash'), \
                 patch.object(append, 'authenticated_api', return_value=api), \
                 patch.object(append, 'metadata_matches', side_effect=[False, True, True]), \
                 patch.object(append, 'verify_remote', side_effect=verify), \
                 patch.object(append, 'activate', side_effect=lambda *a: calls.append('activate')):
                append.main()
            self.assertEqual(calls, ['upload', 'verify-payload', 'commit', 'verify-final', 'activate'])

    def test_preserves_old_trials_and_rejects_changes_and_unlisted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = Path(tmp) / 'old', Path(tmp) / 'new'
            release = 'releases/base'
            write(old / release / 'snapshot.json', {'trials': [{'id': 'existing'}]})
            write(new / release / 'snapshot.json', {'trials': [{'id': 'existing'}, {'id': 'kimi'}]})
            path = release + '/trials/existing/payload'
            base = {'release_path': release, 'files': {path: {'sha256': 'unchanged'}}}
            manifest = copy.deepcopy(base)
            manifest['files'][release + '/trials/kimi/payload'] = {'sha256': 'new'}
            self.assertEqual(append_plan(old, new, base, manifest), [release + '/trials/kimi/**'])
            manifest['files'][path]['sha256'] = 'changed'
            with self.assertRaisesRegex(ValueError, 'Existing trial payload changed'):
                append_plan(old, new, base, manifest)
            manifest['files'][path] = base['files'][path]
            manifest['files'][release + '/trials/unselected/payload'] = {}
            with self.assertRaisesRegex(ValueError, 'Unexpected append file'):
                append_plan(old, new, base, manifest)
            write(new / release / 'snapshot.json', {'trials': [{'id': 'kimi'}]})
            with self.assertRaisesRegex(ValueError, 'preserve all existing'):
                append_plan(old, new, base, manifest)


if __name__ == '__main__':
    unittest.main()
