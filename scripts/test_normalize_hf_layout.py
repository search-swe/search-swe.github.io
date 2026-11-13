"""Migration preserves content identities and refuses incomplete replacements."""
import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from import_results import export_trajectory, read, write
from normalize_hf_layout import (blob_id, check_superseded, git, git_files, lfs_pointer,
                                 make_tree, relocate, verify_git_files)
from prepare_hf_release import finalize
from publication import CURRENT_RELEASE, fingerprints


class LayoutTests(unittest.TestCase):
    def test_relocation_preserves_every_payload_and_snapshot_and_can_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, package = Path(temporary) / 'source', Path(temporary) / 'current'
            release = source / 'releases/old-models'
            trial = release / 'trials/example'
            export_trajectory({'steps': [{'step_id': 1, 'source': 'user', 'message': 'hello'}]}, trial, public=True)
            write(trial / 'evaluation.json', {'score': 0})
            write(trial / 'files/index.json', {'groups': {}})
            snapshot = {'id': 'stable-id', 'observed_at': '2026-11-13', 'source_hashes': {},
                        'tasks': [], 'entries': [], 'trials': [{'id': 'example', 'steps': 1}]}
            manifest = finalize(source, snapshot, 'releases/old-models')
            write(source.with_suffix('.usage.json'), {'private': 'receipt'})
            target = relocate(source, package, manifest)
            self.assertEqual(target['snapshot_id'], 'stable-id')
            self.assertEqual(read(package.with_suffix('.usage.json')), {'private': 'receipt'})
            for path in release.rglob('*'):
                if path.is_file():
                    self.assertEqual(path.read_bytes(), (package / CURRENT_RELEASE / path.relative_to(release)).read_bytes())
            self.assertEqual(relocate(source, package, manifest), target)
            (package / CURRENT_RELEASE / 'trials/example/evaluation.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'content changed'):
                relocate(source, package, manifest)

    def test_old_configurations_need_valid_replacements(self):
        trial = {'task': 'one', 'configuration': {'model': 'model', 'agent': 'agent', 'version': '1',
                                                'effort': 'max', 'provider': 'provider'}, 'valid': True}
        old, current = {'trials': [trial]}, {'trials': [copy.deepcopy(trial)]}
        check_superseded(old, current)
        for field, value in [('valid', False), ('task', 'different')]:
            changed = copy.deepcopy(current)
            changed['trials'][0][field] = value
            with self.assertRaisesRegex(ValueError, 'absent'):
                check_superseded(old, changed)
        current['trials'][0]['configuration']['provider'] = 'other'
        with self.assertRaisesRegex(ValueError, 'absent'):
            check_superseded(old, current)

    def test_git_tree_move_reuses_regular_and_lfs_objects_and_drops_old_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / 'repo.git'
            subprocess.run(['git', 'init', '--bare', '--quiet', str(repository)], check=True)
            package = root / 'package'
            write(package / CURRENT_RELEASE / 'payload.json', b'{"unchanged":true}')
            write(package / 'publication.json.gz', b'inventory')
            hashes = fingerprints(package / CURRENT_RELEASE / 'payload.json')
            pointer = lfs_pointer(hashes)
            oid = git(repository, 'hash-object', '-w', '--stdin', data=pointer).decode().strip()
            self.assertEqual(oid, blob_id(pointer))
            corpus = make_tree(repository, {'payload.json': '100644 blob ' + oid})
            releases = make_tree(repository, {'current': '040000 tree ' + corpus})
            metadata = git(repository, 'hash-object', '-w', '--stdin', data=b'inventory').decode().strip()
            tree = make_tree(repository, {'releases': '040000 tree ' + releases,
                                         'publication.json.gz': '100644 blob ' + metadata})
            files = git_files(repository, tree)
            manifest = {'release_path': CURRENT_RELEASE, 'files': {CURRENT_RELEASE + '/payload.json': hashes}}
            verify_git_files(files, package, manifest)
            self.assertEqual(files[CURRENT_RELEASE + '/payload.json'], oid)
            self.assertEqual(len(files), 2)
            for corrupt in ({**files, CURRENT_RELEASE + '/extra.json': oid},
                            {**files, CURRENT_RELEASE + '/payload.json': '0' * 40}):
                with self.assertRaises(ValueError):
                    verify_git_files(corrupt, package, manifest)


if __name__ == '__main__':
    unittest.main()
