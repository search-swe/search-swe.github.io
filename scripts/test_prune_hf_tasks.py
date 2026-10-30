"""Withdrawal safety: unchanged retained evidence, exact deletions and retry behavior."""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import prune_hf_tasks as prune
from import_results import write
from publication import fingerprints


class WithdrawalTests(unittest.TestCase):
    def snapshots(self):
        old = {'id': 'old', 'tasks': [{'name': 'keep'}, {'name': 'retire'}],
               'entries': [{'id': 'old-model', 'model': 'model'}], 'publication': {'schema': 1},
               'trials': [{'id': task + '-trial', 'task': task, 'entry': 'old-model',
                           'score': 10, 'tokens': {'total_tokens': 30},
                           'trajectory_url': 'old-url', 'redacted_fields': 2}
                          for task in ['keep', 'retire']]}
        new = copy.deepcopy(old)
        new['id'] = 'new'
        new['tasks'] = new['tasks'][:1]
        new['trials'] = new['trials'][:1]
        new['entries'][0]['id'] = 'new-model'
        new['trials'][0].update(entry='new-model', trajectory_url='local-url', redacted_fields=0)
        new.pop('publication')
        return old, new

    def test_retained_scores_usage_selection_and_models_cannot_change(self):
        old, new = self.snapshots()
        public = prune.retained_snapshot(old, new, ['retire'])
        self.assertEqual(public['trials'][0]['redacted_fields'], 2)
        self.assertEqual(new['trials'][0]['redacted_fields'], 0)
        for key, value in [('score', 11), ('tokens', {'total_tokens': 31}), ('id', 'another-trial')]:
            changed = copy.deepcopy(new)
            changed['trials'][0][key] = value
            with self.assertRaises(ValueError):
                prune.retained_snapshot(old, changed, ['retire'])
        with self.assertRaises(ValueError):
            prune.retained_snapshot(old, new, ['keep'])

    def test_only_exact_trial_directories_can_be_deleted(self):
        release = 'releases/test'
        paths = [release + '/trials/retire-v4.1/manifest.json', release + '/trials/retire-v4.1-longer/manifest.json',
                 release + '/trials/keep/manifest.json', release + '/snapshot.json', 'README.md']
        base = {'release_path': release, 'files': {p: {'sha256': p} for p in paths}}
        updated = copy.deepcopy(base)
        del updated['files'][paths[0]]
        self.assertEqual(prune.validate_delta(base, updated, [release + '/trials/retire-v4.1/']), {paths[0]})
        for directory in [release + '/', release + '/trials/', release + '/trials/../', release + '/trials/retire']:
            with self.assertRaises(ValueError):
                prune.validate_delta(base, updated, [directory])
        updated['files'][paths[2]]['sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'Retained payload changed'):
                prune.validate_delta(base, updated, [release + '/trials/retire-v4.1/'])

    def test_retry_requires_matching_metadata_and_absent_retired_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp)
            write(package / 'snapshot.json', {'tasks': 47})
            hashes = fingerprints(package / 'snapshot.json')
            file = SimpleNamespace(path='snapshot.json', size=hashes['bytes'], blob_id=hashes['git_blob'], lfs=None)
            plan = {'update_files': ['snapshot.json'], 'delete_directories': ['releases/test/trials/retire/']}
            api = Mock()
            api.get_paths_info.side_effect = [[file], []]
            prune.verify_applied(api, package, plan, 'a' * 40)
            api.get_paths_info.side_effect = [[file], [SimpleNamespace(path='releases/test/trials/retire')]]
            with self.assertRaisesRegex(ValueError, 'still exist'):
                prune.verify_applied(api, package, plan, 'a' * 40)
            file.blob_id = 'different-update'
            api.get_paths_info.side_effect = [[file]]
            with self.assertRaisesRegex(ValueError, 'no automatic deletion'):
                prune.verify_applied(api, package, plan, 'a' * 40)

    def test_atomic_commit_is_guarded_and_retry_never_deletes_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp)
            plan = {'base_revision': 'a' * 40, 'delete_directories': ['releases/test/trials/retire/'],
                    'update_files': ['README.md', 'publication.json.gz'], 'publication_sha256': 'hash'}
            anonymous, authenticated = Mock(), Mock()
            anonymous.repo_info.return_value = SimpleNamespace(sha='a' * 40, private=False, gated=False)
            authenticated.create_commit.return_value = SimpleNamespace(oid='b' * 40)
            fake_hub = SimpleNamespace(HfApi=Mock(side_effect=[anonymous, authenticated]),
                CommitOperationAdd=lambda **kw: SimpleNamespace(kind='add', **kw),
                CommitOperationDelete=lambda **kw: SimpleNamespace(kind='delete', **kw))
            with patch.dict('sys.modules', huggingface_hub=fake_hub), \
                 patch.object(prune, 'verify_applied') as verified, \
                 patch.object(prune, 'verify_remote'), \
                 patch.object(prune, 'check_site_snapshot', return_value='source'), \
                 patch.object(prune, 'activate') as activate:
                prune.apply(plan, package, {'tasks': 47, 'trials': 188}, 'source', package / 'plan.json', 'https://site')
                kwargs = authenticated.create_commit.call_args.kwargs
                self.assertEqual(kwargs['parent_commit'], 'a' * 40)
                self.assertEqual([o.kind for o in kwargs['operations']], ['delete', 'add', 'add'])
                self.assertEqual(kwargs['operations'][0].path_in_repo, plan['delete_directories'][0])
                self.assertTrue(kwargs['operations'][0].is_folder)
                activate.assert_called_once()
                anonymous.repo_info.return_value.sha = 'b' * 40
                fake_hub.HfApi.side_effect = [anonymous]
                prune.apply(plan, package, {'tasks': 47, 'trials': 188}, 'source', package / 'plan.json', 'https://site')
                self.assertEqual(authenticated.create_commit.call_count, 1)
                verified.side_effect = ValueError('Unrelated remote update')
                fake_hub.HfApi.side_effect = [anonymous]
                with self.assertRaisesRegex(ValueError, 'Unrelated'):
                    prune.apply(plan, package, {}, 'source', package / 'plan.json', 'https://site')
                self.assertEqual(activate.call_count, 2)

    def test_default_command_performs_only_an_offline_check(self):
        plan = {'base_revision': 'a' * 40, 'delete_directories': [], 'deleted_files': 0,
                'deleted_bytes': 0, 'update_files': []}
        with patch('sys.argv', ['prune_hf_tasks.py']), patch.object(prune, 'read', return_value=plan), \
             patch.object(prune, 'check_plan', return_value=(Path('/tmp'), {'tasks': 47, 'trials': 188}, 'hash')), \
             patch.object(prune, 'apply') as apply:
            prune.main()
            apply.assert_not_called()


if __name__ == '__main__':
    unittest.main()
