"""Export selected trial evidence for a static, read-only file browser."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path

CODE_EXTENSIONS = {'.py', '.sh', '.md', '.toml', '.yaml', '.yml', '.rs', '.c',
                   '.h', '.cpp', '.hpp', '.js', '.ts', '.sql', '.ini', '.cfg'}
REPORT_NAMES = {'reward.json', 'reward.txt', 'evaluation.json', 'reward-details.json',
                'task-score.json', 'task-score.txt', 'test-stdout.txt',
                'jailbreak-result.json', 'jailbreak-status.json', 'run_manifest.json',
                'provenance.json'}
SECRET_KEY = re.compile(r'(?:^|_)(?:api_key|access_token|auth_token|password|secret|authorization)$', re.I)
PART_CHARS = 48_000


def sanitize(value, scrub, key=''):
    """Keep configuration structure but never export environment values."""
    if key in {'env', 'environment_variables'} and isinstance(value, dict):
        return {k: v if isinstance(v, str) and re.fullmatch(r'\$\{[A-Z0-9_]+\}', v)
                else '[REDACTED: environment value]' for k, v in value.items()}
    if SECRET_KEY.search(key):
        return value if isinstance(value, str) and re.fullmatch(r'\$\{[A-Z0-9_]+\}', value) else '[REDACTED: credential]'
    if isinstance(value, dict):
        return {k: sanitize(v, scrub, k) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v, scrub) for v in value]
    if isinstance(value, str):
        return scrub(value)
    return value


def export_files(source_trial, final_verifier, output, scrub, write, check=False):
    output = output / 'files'
    groups = {key: [] for key in ('agent', 'verifier', 'artifacts', 'config', 'lock', 'log', 'exception')}
    notes = {
        'agent': 'Agent logs accompanying the selected coding trajectory.',
        'verifier': 'Files from the final selected grading result. Earlier verifier results are not included.',
        'artifacts': 'Collected submission files. Code and small text files are readable; large indexes, checkpoints and archives are listed with their size.',
        'config': 'Harbor configuration accompanying the selected trajectory. Environment values are redacted.',
        'lock': 'Resolved Harbor configuration, including the task fingerprint and concrete execution settings. Environment values are redacted.',
        'log': 'Harbor trial lifecycle log accompanying the selected trajectory.',
        'exception': 'Recorded runtime exceptions can coexist with a valid final score, for example when a timed-out agent submission was graded.',
    }
    if final_verifier != source_trial / 'verifier':
        notes['verifier'] += ' This trial was regraded separately; these files follow the final reward pointer.'
    candidates = []
    for group, folder in [('agent', source_trial / 'agent'), ('verifier', final_verifier),
                          ('artifacts', source_trial / 'artifacts')]:
        for path in sorted(folder.rglob('*')):
            relative = path.relative_to(folder)
            if path.is_symlink() or not path.is_file() or any(part.startswith('.') for part in relative.parts):
                continue
            candidates.append((group, path, str(relative)))
    for group, name in [('config', 'config.json'), ('lock', 'lock.json'), ('log', 'trial.log'), ('exception', 'exception.txt')]:
        path = source_trial / name
        if path.is_file() and not path.is_symlink():
            candidates.append((group, path, name))
    # Prefer entry points and final reports before optional files exhaust a budget.
    priority = ['reward.json', 'evaluation.json', 'reward-details.json', 'test-stdout.txt',
                'codex.txt', 'trajectory.json', 'build.sh', 'run.sh', 'README.md']
    candidates.sort(key=lambda item: (item[0], priority.index(item[1].name) if item[1].name in priority else len(priority), item[2]))
    budgets = {group: 64 * 1024**2 if group == 'agent' else 8 * 1024**2 for group in groups}
    for group, path, name in candidates:
        size = path.stat().st_size
        entry = {'name': name, 'bytes': size, 'parts': [], 'download': None, 'source_sha256': None}
        suffix = path.suffix.lower()
        if group == 'artifacts':
            allowed = suffix in CODE_EXTENSIONS or (suffix in {'.json', '.jsonl', '.txt', '.csv', '.log'} and size <= 256 * 1024)
        elif group == 'verifier':
            allowed = path.name in REPORT_NAMES or suffix == '.log'
        else:
            allowed = suffix in CODE_EXTENSIONS | {'.txt', '.log', '.json', '.jsonl'}
        limit = 32 * 1024**2 if group == 'agent' else 2 * 1024**2
        if not allowed or size > limit or size > budgets[group]:
            entry['unavailable'] = 'Listed only: binary, large, or outside the local text export.'
            groups[group].append(entry)
            continue
        raw = path.read_bytes()
        try:
            value = raw.decode('utf-8')
            if '\x00' in value:
                raise UnicodeError('Binary file')
        except UnicodeError:
            entry['unavailable'] = 'Binary file: text preview is unavailable.'
            groups[group].append(entry)
            continue
        if suffix == '.jsonl':
            # Native session records can also contain structured environment values.
            lines = []
            for line in value.splitlines(keepends=True):
                try:
                    lines.append(json.dumps(sanitize(json.loads(line), scrub), ensure_ascii=False) + '\n')
                except json.JSONDecodeError:
                    lines.append(scrub(line))
            value = ''.join(lines)
        elif suffix == '.json':
            try:
                value = json.dumps(sanitize(json.loads(value), scrub), indent=2, ensure_ascii=False) + '\n'
            except json.JSONDecodeError:
                value = scrub(value)
        else:
            value = scrub(value)
        entry['source_sha256'] = hashlib.sha256(raw).hexdigest()
        entry['redacted'] = '[REDACTED:' in value
        entry['chars'] = len(value)
        file_id = hashlib.sha256((group + '/' + name).encode()).hexdigest()[:16]
        for offset in range(0, max(1, len(value)), PART_CHARS):
            part = f'{file_id}-{offset // PART_CHARS:04}.json'
            write(output / part, value[offset:offset + PART_CHARS], check)
            entry['parts'].append(part)
        archive = file_id + '.txt.gz'
        write(output / archive, gzip.compress(value.encode(), compresslevel=6, mtime=0), check)
        entry['download'] = archive
        budgets[group] -= size
        groups[group].append(entry)
    # Exception information can also live only in the Harbor result record.
    result_path = source_trial / 'result.json'
    exception = json.loads(result_path.read_text()).get('exception_info') if result_path.is_file() else None
    index = {'schema': 1, 'groups': groups, 'notes': notes,
             'exception': sanitize(exception, scrub),
             'regraded_separately': final_verifier != source_trial / 'verifier'}
    write(output / 'index.json', index, check)
    return index
