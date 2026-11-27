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
        self.assertEqual(build.stats(trials), {'score': 30, 'tokens': None, 'cost': None, 'seconds': None})

    def test_all_is_task_weighted_not_mean_of_hardware_means(self):
        self.assertEqual(build.mean([0, 0, 90]), 30)
        self.assertNotEqual(build.mean([0, 0, 90]), build.mean([0, 90]))

    def test_token_overview_is_total_while_score_and_time_are_means(self):
        trials = [{'score': score, 'tokens': {'total_tokens': tokens}, 'agent_seconds': seconds}
                  for score, tokens, seconds in [(0, 12, 5), (90, 30, 10)]]
        self.assertEqual(build.stats(trials), {'score': 45, 'tokens': 42, 'cost': None, 'seconds': 7.5})
        self.assertIsNone(build.total([12, None]))


@unittest.skipUnless((build.ROOT / 'content/leaderboard/release.json').exists(), 'Run local importer first')
class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads((build.ROOT / 'content/leaderboard/release.json').read_text())

    def test_fixed_coverage_tokens_and_expected_analysis_means(self):
        snapshot = self.snapshot
        expected = {'openai/gpt-6-luna': 13.103099186708066,
                    'openai/gpt-6.1-terra': 42.53223472405557,
                    'gpt-6.1-sol': 46.4303712900911,
                    'kimi-k3.1-pro': 26.599930798089026,
                    'anthropic/claude-opus-5.5': 48.41088224661941,
                    'gpt-6-astra': 45.927353979642724,
                    'deepseek/deepseek-v4.1-flash-1017': 21.054061239674596, 'kimi-k3': 25.371920241505414,
                    'xiaomi/mimo-v2.6-flash': 15.272761996392159, 'xiaomi/mimo-v2.6-pro': 18.630222644023586,
                    'step-5-preview': 19.47455964531325,
                    'z-ai/glm-5.3': 18.35926991146622, 'z-ai/glm-5.3-flash': 16.356435223177584,
                    'anthropic/claude-sonnet-5.5': 38.42, 'google/gemini-4-argon': 34.02,
                    'anthropic/claude-fable-5.2': 52.72524302040524}
        self.assertEqual(len(snapshot['tasks']), 47)
        self.assertEqual(len(snapshot['trials']), 846)
        self.assertEqual({entry['model'] for entry in snapshot['entries']}, set(expected))
        for entry in snapshot['entries']:
            trials = [t for t in snapshot['trials'] if t['entry'] == entry['id']]
            self.assertEqual({t['task'] for t in trials}, {t['name'] for t in snapshot['tasks']})
            model = entry['model']
            wanted = expected[model]
            if model.startswith('deepseek/'):
                wanted = {'Claude Code': 27.592737573013743, 'Pi': 18.43878164582429}.get(entry['agent'], wanted)
            places = 2 if model in {'anthropic/claude-sonnet-5.5', 'google/gemini-4-argon'} else 10
            self.assertAlmostEqual(build.stats(trials)['score'], wanted, places=places)
            totals = [t['tokens']['total_tokens'] for t in trials]
            self.assertEqual(build.stats(trials)['tokens'], None if None in totals else sum(totals))
            for trial in trials:
                usage = trial['tokens']
                self.assertEqual(usage['input_tokens'] + usage['output_tokens'], usage['total_tokens'])
                self.assertLessEqual(usage['cached_input_tokens'], usage['input_tokens'])

    def test_argon_usage_includes_all_tasks_and_original_formula(self):
        trials = [t for t in self.snapshot['trials'] if t['configuration']['model'] == 'google/gemini-4-argon']
        self.assertEqual(len(trials), 47)
        self.assertEqual(sum(t['tokens']['total_tokens'] for t in trials), 791_340_865)
        self.assertEqual(sum(t['tokens']['response_count'] for t in trials), 6_470)
        self.assertTrue(all(t['usage_evidence'] and t['tokens']['reasoning_output_tokens'] is None for t in trials))
        formula = next(t for t in trials if t['task'] == 'large-scale-formula-retrieval')
        self.assertEqual(formula['tokens']['total_tokens'], 13_226_203)
        self.assertEqual(formula['tokens']['response_count'], 97)

    def test_fable_direct_result_and_fallback_attribution(self):
        model = 'anthropic/claude-fable-5.2'
        entry = next(e for e in self.snapshot['entries'] if e['model'] == model)
        self.assertEqual((entry['provider'], entry['agent'], entry['agent_version'], entry['effort']),
                         ('Anthropic', 'Claude Code', '2.1.309', 'max'))
        trials = [t for t in self.snapshot['trials'] if t['entry'] == entry['id']]
        self.assertTrue(all(t['agent_seconds'] is not None and t['configuration']['provider'] == 'Anthropic'
                            for t in trials))
        fallback, = [t for t in trials if t.get('model_substitution')]
        self.assertEqual(fallback['task'], 'constrained-molecular-search')
        self.assertAlmostEqual(fallback['score'], 17.6659)
        self.assertEqual(fallback['configuration']['model'], 'anthropic/claude-opus-5')
        self.assertEqual(fallback['configuration']['fallback_from'], model)
        self.assertEqual(fallback['model_substitution']['refusal_attempts'], 1)
        self.assertTrue(all(t['configuration']['model'] == model for t in trials if t is not fallback))
        self.assertIn('For Claude Fable 5.2,', build.substitution_note([fallback]))
        self.assertIn('switched automatically to Opus 5', build.substitution_note([fallback]))
        self.assertIn('switched from Claude Fable 5.2 to Claude Opus 5', build.substitution_note([fallback], detailed=True))
        reviewed = next(t for t in trials if t['task'] == 'training-error-tracing')
        self.assertEqual(reviewed['score'], 100)
        self.assertEqual(reviewed['reward']['reward'], 0)
        self.assertEqual(reviewed['qualification']['judge_verdict'], 'yes')

    def test_generated_routes_and_no_script_injection(self):
        pages = build.generate()
        self.assertEqual(len(pages), 867)  # 866 pages plus the cost-enriched download.
        for trial in self.snapshot['trials']:
            self.assertIn(build.ROOT / f'leaderboard/trials/{trial["id"]}/index.html', pages)
        rendered = build.page('<script>', '<p>test</p>', 'trial', {'message': '</script><script>alert(1)'}, self.snapshot)
        self.assertIn('&lt;script&gt;', rendered)
        self.assertNotIn('</script><script>alert(1)', rendered)

    def test_pr3_entries_preserve_routes_and_local_selected_rewards(self):
        expected = {
            'anthropic/claude-sonnet-5.5': ('Claude Code', '2.1.309', 'max', {
                'rust-bm25-search': 72.246176919, 'large-scale-formula-retrieval': 0}),
            'google/gemini-4-argon': ('Antigravity CLI', '1.5.2', 'high', {
                'large-scale-formula-retrieval': 0}),
        }
        for model, (agent, version, effort, reruns) in expected.items():
            entry = next(e for e in self.snapshot['entries'] if e['model'] == model)
            self.assertEqual((entry['agent'], entry['agent_version'], entry['effort'], entry['provider']),
                             (agent, version, effort, 'Vertex AI'))
            trials = [t for t in self.snapshot['trials'] if t['entry'] == entry['id']]
            for trial in trials:
                task = trial['task']
                self.assertEqual(trial['configuration']['provider'], 'OpenRouter' if task in reruns else 'Vertex AI')
                if task in reruns:
                    self.assertTrue(trial['valid'])
                    self.assertAlmostEqual(trial['score'], reruns[task])

    def test_step5_original_timing_usage_and_transport_flags(self):
        trials = [t for t in self.snapshot['trials'] if t['configuration']['model'] == 'step-5-preview']
        self.assertEqual(len(trials), 47)
        self.assertEqual(sum(t['tokens']['total_tokens'] for t in trials), 800569286)
        self.assertEqual(sum('Final aggregate counter unavailable' in t['usage_note'] for t in trials), 13)
        for trial in trials:
            self.assertEqual(trial['configuration']['provider'], 'StepFun')
            self.assertEqual(trial['configuration']['version'], '2.1.309')
            self.assertEqual(trial['configuration']['effort'], 'max')
            self.assertIsNotNone(trial['agent_seconds'])
        by_task = {t['task']: t for t in trials}
        self.assertAlmostEqual(by_task['evolving-personal-memory']['agent_seconds'], 7201.643989)
        self.assertAlmostEqual(by_task['instruction-following-embedding']['agent_seconds'], 7201.056449)
        self.assertEqual({t['task'] for t in trials if t['qualification'].get('qualification_flag') == 'API_TRANSPORT_DEGRADATION_RECORDED'},
                         {'code-reranker-finetuning', 'query-encoder-alignment', 'sparse-retrieval-pruning'})

    def test_glm_provider_timing_and_image_failure_notices(self):
        entries = {e['model']: e for e in self.snapshot['entries'] if e['model'].startswith('z-ai/glm-5.3')}
        self.assertEqual(set(entries), {'z-ai/glm-5.3', 'z-ai/glm-5.3-flash'})
        for model, entry in entries.items():
            self.assertEqual(entry['provider'], 'Z.ai')
            self.assertEqual(entry['provider_route'], 'TokenPlus (SiliconFlow)')
            trials = [t for t in self.snapshot['trials'] if t['entry'] == entry['id']]
            self.assertEqual(len(trials), 47)
            self.assertTrue(all(t['agent_seconds'] > 0 for t in trials))
            self.assertTrue(all(t['configuration']['request_model'] == model + '?provider=z-ai' for t in trials))
        failures = [t for t in self.snapshot['trials'] if build.image_input_failed(t)]
        self.assertEqual(len(failures), 5)
        self.assertEqual({t['task'] for t in failures}, {'composed-image-search', 'layout-page-search',
                         'same-place-image-search', 'sketch-text-search', 'visual-document-qa'})
        self.assertTrue(all(t['entry'] == entries['z-ai/glm-5.3']['id'] and t['score'] == 0 for t in failures))
        resumed = next(t for t in self.snapshot['trials'] if t['entry'] == entries['z-ai/glm-5.3']['id']
                       and t['task'] == 'budgeted-bimetric-retrieval')
        self.assertEqual(resumed['tokens']['total_tokens'], 6464221)
        self.assertIn('final invocation', resumed['usage_note'])
        page = build.generate()
        for t in failures:
            self.assertIn('Claude Code stopped after its Read tool tried to pass an image',
                          page[build.ROOT / f'leaderboard/trials/{t["id"]}/index.html'])
        for model, entry in entries.items():
            html = page[build.ROOT / f'leaderboard/entries/{entry["id"]}/index.html']
            self.assertEqual(html.count('class="fineprint image-input-status"'), 5 if model == 'z-ai/glm-5.3' else 0)
            self.assertEqual(html.count('>Z.ai</td>'), 47)

    def test_opus_fallback_keeps_actual_model_and_discloses_substitution(self):
        trials = [t for t in self.snapshot['trials'] if
                  t.get('model_substitution', {}).get('requested_model') == 'anthropic/claude-opus-5.5']
        self.assertEqual(len(trials), 1)
        trial = trials[0]
        self.assertEqual(trial['task'], 'constrained-molecular-search')
        self.assertEqual(trial['configuration']['model'], 'anthropic/claude-opus-5')
        self.assertEqual(trial['configuration']['provider'], 'OpenRouter')
        entry = next(e for e in self.snapshot['entries'] if e['id'] == trial['entry'])
        self.assertEqual(entry['model'], 'anthropic/claude-opus-5.5')
        self.assertEqual(trial['model_substitution']['refusal_category'], 'bio')
        self.assertEqual(len(trial['model_substitution']['refusal_evidence']), 5)
        pages = build.generate()
        self.assertIn('uses Opus 5 after five biology-safety refusals', pages[build.ROOT / 'leaderboard/index.html'])
        detail = pages[build.ROOT / f'leaderboard/trials/{trial["id"]}/index.html']
        self.assertIn('This result uses Claude Opus 5', detail)
        self.assertIn('Anthropic’s recommended fallback', detail)


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
