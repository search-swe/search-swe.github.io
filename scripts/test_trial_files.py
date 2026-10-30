import gzip
import json
import tempfile
import unittest
from pathlib import Path

from export_trial_files import export_files
from import_results import scrub, write


class TrialFileTests(unittest.TestCase):
    def test_final_grading_provenance_redaction_and_artifact_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, final, output = root / 'trial', root / 'regrade', root / 'export'
            for folder in [source / 'agent', source / 'artifacts', source / 'verifier', final]:
                folder.mkdir(parents=True)
            (source / 'verifier/reward.json').write_text('{"reward":0}')
            (final / 'reward.json').write_text('{"reward":0.75}')
            config = {'env': {'API_KEY': 'private-value', 'REF': '${API_KEY}'}, 'other_api_key': 'private-value'}
            (source / 'config.json').write_text(json.dumps(config))
            (source / 'lock.json').write_text('{"task":{"digest":"sha256:abc"}}')
            (source / 'trial.log').write_text('<script>literal log</script>')
            (source / 'result.json').write_text('{"exception_info":{"exception_type":"AgentTimeoutError"}}')
            (source / 'agent/codex.txt').write_text('message\n' * 10000)
            session = source / 'agent/sessions/2026/10/30/rollout.jsonl'
            session.parent.mkdir(parents=True)
            session.write_text(json.dumps({'type': 'session_meta', 'env': {'API_KEY': 'private-value'}}) + '\n')
            (source / 'agent/trajectory.json').write_text('{"steps": []}')
            (source / 'artifacts/run.py').write_text('print("hello")')
            (source / 'artifacts/.env').write_text('SECRET=value')
            (source / 'artifacts/external.py').symlink_to(source / 'config.json')
            (source / 'artifacts/model.bin').write_bytes(b'\x00\xff')
            with (source / 'artifacts/large.py').open('wb') as file:
                file.truncate(3 * 1024**2)
            index = export_files(source, final, output, scrub, write)
            files = output / 'files'
            def body(entry):
                return ''.join(json.loads((files / part).read_text()) for part in entry['parts'])
            self.assertTrue(index['regraded_separately'])
            self.assertEqual(json.loads(body(index['groups']['verifier'][0]))['reward'], 0.75)
            safe = json.loads(body(index['groups']['config'][0]))
            self.assertEqual(safe['env']['API_KEY'], '[REDACTED: environment value]')
            self.assertEqual(safe['env']['REF'], '${API_KEY}')
            self.assertEqual(safe['other_api_key'], '[REDACTED: credential]')
            self.assertEqual(json.loads((source / 'config.json').read_text()), config)
            artifacts = {f['name']: f for f in index['groups']['artifacts']}
            self.assertEqual(set(artifacts), {'run.py', 'model.bin', 'large.py'})
            self.assertEqual(body(artifacts['run.py']), 'print("hello")')
            self.assertEqual(artifacts['model.bin']['parts'], [])
            self.assertEqual(artifacts['large.py']['parts'], [])
            log = index['groups']['agent'][0]
            self.assertGreater(len(log['parts']), 1)
            self.assertEqual(body(log), 'message\n' * 10000)
            self.assertEqual(gzip.decompress((files / log['download']).read_bytes()).decode(), body(log))
            agent_files = {f['name']: f for f in index['groups']['agent']}
            self.assertIn('trajectory.json', agent_files)
            self.assertEqual(json.loads(body(agent_files['sessions/2026/10/30/rollout.jsonl']))['env']['API_KEY'], '[REDACTED: environment value]')
            self.assertEqual(index['exception']['exception_type'], 'AgentTimeoutError')
            self.assertEqual(index['groups']['exception'], [])
            export_files(source, final, output, scrub, write, check=True)


if __name__ == '__main__':
    unittest.main()
