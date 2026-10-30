"""Contracts that matter for result integrity and lazy trajectory reading."""
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_leaderboard as build
import import_results as importer


class TrajectoryTests(unittest.TestCase):
    def test_per_step_usage_preserves_recorded_counts_and_missing_values(self):
        raw = {'steps': [
            {'step_id': 1, 'source': 'user', 'message': 'Task'},
            {'step_id': 2, 'source': 'agent', 'model_name': 'test/model', 'message': 'Working',
             'metrics': {'prompt_tokens': 1000, 'cached_tokens': 800, 'completion_tokens': 40,
                         'cost_usd': 0.2, 'extra': {'reasoning_output_tokens': 30}}},
            {'step_id': 3, 'source': 'agent', 'message': '',
             'metrics': {'prompt_tokens': 1100, 'completion_tokens': 0}},
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            importer.export_trajectory(raw, path)
            steps = json.loads((path / 'steps-0000.json').read_text())
            self.assertEqual(steps[1]['model_name'], 'test/model')
            self.assertEqual(steps[1]['usage'], {'input_tokens': 1000, 'cached_input_tokens': 800, 'output_tokens': 40})
            self.assertIsNone(steps[0]['usage']['input_tokens'])
            self.assertIsNone(steps[2]['usage']['cached_input_tokens'])
            self.assertEqual(steps[2]['usage']['output_tokens'], 0)
            self.assertNotIn('cost_usd', steps[1])

    def test_call_ids_not_output_order_and_missing_outputs(self):
        raw = {'steps': [
            {'step_id': 1, 'source': 'agent', 'message': '<script>alert(1)</script>',
             'tool_calls': [
                 {'tool_call_id': 'a', 'function_name': 'exec', 'arguments': {'cmd': 'one'}},
                 {'tool_call_id': 'b', 'function_name': 'exec', 'arguments': {'cmd': 'two'}},
                 {'tool_call_id': 'c', 'function_name': 'exec', 'arguments': {'cmd': 'three'}},
             ]},
            {'step_id': 2, 'source': 'agent', 'message': '', 'observation': {'results': [
                {'source_call_id': 'b', 'content': 'second'},
                {'source_call_id': 'a', 'content': 'first'},
                {'source_call_id': 'b', 'content': 'second again'},
                {'source_call_id': 'unknown', 'content': 'unmatched'},
            ]}},
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            importer.export_trajectory(raw, path)
            steps = json.loads((path / 'steps-0000.json').read_text())
            self.assertEqual(steps[0]['calls'][0]['outputs'], ['first'])
            self.assertEqual(steps[0]['calls'][1]['outputs'], ['second', 'second again'])
            self.assertEqual(steps[0]['calls'][2]['outputs'], [])
            self.assertEqual(steps[1]['unmatched_outputs'][0]['content'], 'unmatched')
            self.assertEqual(steps[0]['message'], '<script>alert(1)</script>')
            importer.export_trajectory(raw, path, check=True)

    def test_long_output_is_complete_searchable_and_redacted_in_download(self):
        secret = 'sk-or-v1-' + 'x' * 40
        body = 'start ' + 'padding ' * 15000 + 'uniquetailword ' + secret
        raw = {'steps': [{'step_id': 1, 'source': 'user', 'message': body}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            count, redacted = importer.export_trajectory(raw, path)
            value = json.loads((path / 'steps-0000.json').read_text())[0]['message']
            restored = ''.join(json.loads((path / p).read_text()) for p in value['parts'])
            self.assertEqual(restored, importer.scrub(body))
            self.assertNotIn(secret, restored)
            self.assertEqual((count, redacted), (1, 1))
            self.assertIn('uniquetailword', json.loads((path / 'search.json').read_text())[0])
            downloaded = json.loads(gzip.decompress((path / 'trajectory.json.gz').read_bytes()))
            self.assertEqual(downloaded['steps'][0]['message'], restored)
            importer.export_trajectory(raw, path, check=True)

    def test_changed_export_fails_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'a.json'
            importer.write(path, {'value': 1})
            with self.assertRaises(ValueError):
                importer.write(path, {'value': 2}, check=True)

    def test_many_calls_are_split_without_losing_observations(self):
        calls = [{'tool_call_id': str(i), 'function_name': 'exec', 'arguments': {'cmd': 'x' * 3000}} for i in range(130)]
        raw = {'steps': [{'step_id': 1, 'source': 'agent', 'message': '', 'tool_calls': calls,
                         'observation': {'results': [{'source_call_id': str(i), 'content': f'output {i}'} for i in range(130)]}}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            importer.export_trajectory(raw, path)
            step = json.loads((path / 'steps-0000.json').read_text())[0]
            self.assertLessEqual(len(step['calls']), 20)
            restored = step['calls'] + [c for part in step['call_parts'] for c in json.loads((path / part).read_text())]
            self.assertEqual(len(restored), 130)
            self.assertEqual(restored[-1]['outputs'], ['output 129'])
            self.assertLess((path / 'steps-0000.json').stat().st_size, importer.CHUNK_BYTES)


class ScoreTests(unittest.TestCase):
    def test_valid_zero_and_missing_usage(self):
        trials = [{'score': score, 'tokens': {'total_tokens': tokens}, 'agent_seconds': seconds}
                  for score, tokens, seconds in [(0, 12, 5), (90, None, None), (0, 10, 6)]]
        self.assertEqual(build.stats(trials), {'score': 30, 'tokens': None, 'seconds': None})

    def test_all_is_task_weighted_not_mean_of_hardware_means(self):
        self.assertEqual(build.mean([0, 0, 90]), 30)
        self.assertNotEqual(build.mean([0, 0, 90]), build.mean([0, 90]))

    def test_token_overview_is_total_while_score_and_time_are_means(self):
        trials = [{'score': score, 'tokens': {'total_tokens': tokens}, 'agent_seconds': seconds}
                  for score, tokens, seconds in [(0, 12, 5), (90, 30, 10)]]
        self.assertEqual(build.stats(trials), {'score': 45, 'tokens': 42, 'seconds': 7.5})
        self.assertIsNone(build.total([12, None]))


@unittest.skipUnless((build.ROOT / 'content/leaderboard/release.json').exists(), 'Run local importer first')
class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads((build.ROOT / 'content/leaderboard/release.json').read_text())

    def test_fixed_coverage_tokens_and_expected_analysis_means(self):
        snapshot = self.snapshot
        expected = {'openai/gpt-6-luna': 16.386433628958837,
                    'deepseek/deepseek-v4.1-flash-1017': 15.471256969875635,
                    'xiaomi/mimo-v2.6-flash': 4.747514872689746,
                    'z-ai/glm-5.3-flash': 1.3106598667289633}
        self.assertEqual(len(snapshot['tasks']), 47)
        self.assertEqual(len(snapshot['trials']), 188)
        for entry in snapshot['entries']:
            trials = [t for t in snapshot['trials'] if t['entry'] == entry['id']]
            self.assertEqual({t['task'] for t in trials}, {t['name'] for t in snapshot['tasks']})
            self.assertAlmostEqual(build.stats(trials)['score'], expected[entry['model']], places=10)
            self.assertEqual(build.stats(trials)['tokens'], sum(t['tokens']['total_tokens'] for t in trials))
            for trial in trials:
                usage = trial['tokens']
                self.assertEqual(usage['input_tokens'] + usage['output_tokens'], usage['total_tokens'])
                self.assertLessEqual(usage['cached_input_tokens'], usage['input_tokens'])

    def test_generated_routes_and_no_script_injection(self):
        pages = build.generate()
        self.assertEqual(len(pages), 194)
        for trial in self.snapshot['trials']:
            self.assertIn(build.ROOT / f'leaderboard/trials/{trial["id"]}/index.html', pages)
        rendered = build.page('<script>', '<p>test</p>', 'trial', {'message': '</script><script>alert(1)'}, self.snapshot)
        self.assertIn('&lt;script&gt;', rendered)
        self.assertNotIn('</script><script>alert(1)', rendered)


class PageRemovalTests(unittest.TestCase):
    def test_obsolete_generated_routes_are_removed_without_touching_manual_pages(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(build, 'ROOT', Path(tmp)):
            stale = build.ROOT / 'leaderboard/trials/withdrawn/index.html'
            manual = build.ROOT / 'leaderboard/manual/index.html'
            kept = build.ROOT / 'leaderboard/index.html'
            for path, text in [(stale, build.MARKER), (manual, 'Manual page')]:
                path.parent.mkdir(parents=True)
                path.write_text(text)
            pages = {kept: build.MARKER + 'Current leaderboard'}
            with self.assertRaisesRegex(ValueError, 'rebuilding/removing'):
                build.write_pages(pages, check=True)
            self.assertTrue(stale.exists())
            self.assertEqual(build.write_pages(pages), (1, 1))
            self.assertFalse(stale.exists())
            self.assertEqual(manual.read_text(), 'Manual page')
            self.assertEqual(build.write_pages(pages, check=True), (0, 0))


if __name__ == '__main__':
    unittest.main()
