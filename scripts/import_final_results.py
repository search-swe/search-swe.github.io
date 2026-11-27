"""Prepare the selected models directly from the current final archive.

No evaluation jobs are changed and no network requests are made. Publication is
a separate, explicit step in publish_final_results.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

from export_trial_files import export_files, load_session_event, sanitize
from import_results import ROOT, NAMES, TOKEN_FIELDS, digest, encode, export_trajectory, read, scrub, write
from leaderboard_costs import calculate
from prepare_hf_release import finalize, referenced_files
from publication import CURRENT_RELEASE, DEFAULT_PACKAGE, PublicText, load_package, safe_path
from claude_code_usage import claude_usage, normalized
from pi_usage import pi_usage


def default_final_dir():
    archive = Path('Search-SWE/jobs/final-trajectories')
    for parent in ROOT.parents:
        candidate = parent / 'run-eval-release' / archive
        if (candidate / 'INDEX.csv').is_file():
            return candidate
    return ROOT.parent / archive


TOKENPLUS_MODELS = ('z-ai/glm-5.3', 'z-ai/glm-5.3-flash')
FABLE_MODEL = 'anthropic/claude-fable-5.2'
FABLE_REQUEST = 'claude-fable-5-2'
FABLE_SETTING = 'claude-fable-5.2-claude-code-direct-max'
OPUS_FALLBACK = 'anthropic/claude-opus-5'
FABLE_REVIEWED_SCORE = 'judge_timed_out_at_900s_with_yes_verdict_in_process_log'
TOKENPLUS_SETTINGS = {
    'z-ai/glm-5.3?provider=z-ai': 'glm53-tokenplus-zai-official-claude-code-max',
    'z-ai/glm-5.3-flash?provider=z-ai': 'glm53-flash-tokenplus-zai-official-claude-code-max',
}
GLM_IMAGE_ERRORS = frozenset({'composed-image-search', 'layout-page-search', 'same-place-image-search',
                             'sketch-text-search', 'visual-document-qa'})
GLM_RESUMED_USAGE_SHA256 = '64aa8c420fffef818c50720d760d76cc0bee22cc91eb3c33340acbfbf80d1721'
MODELS = ('openai/gpt-6-luna', 'openai/gpt-6.1-terra', 'gpt-6.1-sol', 'kimi-k3.1-pro',
          'anthropic/claude-opus-5.5', 'gpt-6-astra', 'deepseek/deepseek-v4.1-flash-1017', 'kimi-k3',
          'xiaomi/mimo-v2.6-flash', 'xiaomi/mimo-v2.6-pro', 'step-5-preview', *TOKENPLUS_MODELS, FABLE_MODEL)
DEFAULT_FINAL = default_final_dir()
CONTENT = ROOT / 'content/leaderboard'
COMMUNITY_MODELS = ('tencent/hy4', 'anthropic/claude-sonnet-5.5', 'google/gemini-4-argon')
AGENT_TIME_BUDGET_ASSIGNMENTS = {
    'd3f3eb57779186e628427437bba10ee3a085739d7745e555bd2d709a40dac54d': 'spoken-query-search',
    'd047ea53a65844db9d17be5eb00c580bab4909fa888fd35e396d72d85b07ac77': 'agentic-search',
    '494754ffb91d8f70e07c6b64a438de79c2afe48a65412bbbc68f213cea3b8692': 'scientific-paper-qa',
    'a817d496cb32b56606961dc410cdb77bb53922a294931751c6bd424cc8a7e428': 'visual-document-qa',
    '7520c7cb474837fccbd554b696625c79a9f699c74ed4277b178980365d065692': 'evolving-personal-memory',
    'a697b8a84f15c325bd97f8978d2fa52735db4cd6bf6c12116ba37e3eaaf7063c': 'incremental-vector-search',
    '6ef74415d53b1b913f4c19cd76262feac8302fbe73e9fe88e86783e81ce0b972': 'long-pdf-evidence-vectorless',
    'f5a3cdc50c401e7f0c341e6730f407b2743012b4f72ee2193083ce75aba29ac8': 'paper-metadata-retrieval',
}


def entry_model(row):
    if row['model'] == FABLE_REQUEST:
        if row.get('model_label') != FABLE_SETTING:
            raise ValueError('Unselected Fable configuration')
        return FABLE_MODEL
    if row['model'] in TOKENPLUS_SETTINGS:
        return row['model'].removesuffix('?provider=z-ai')
    if row['model'] == 'anthropic/claude-opus-5':
        if (row['task'] != 'constrained-molecular-search' or
                row.get('model_label') != 'claude-opus-5.5-claude-code-max'):
            raise ValueError('Unapproved Opus model substitution')
        return 'anthropic/claude-opus-5.5'
    return row['model']


DEEPSEEK_SETTINGS = ('deepseek-v4.1-flash-1017-codex-max',
                     'deepseek-v4.1-flash-1017-claude-code-max',
                     'deepseek-v4.1-flash-1017-pi-max')


def setting_key(row):
    model = entry_model(row)
    return row['model_label'] if model.startswith('deepseek/') else model


def selected_rows(final, tasks):
    with (final / 'INDEX.csv').open() as source:
        rows = [r for r in csv.DictReader(source)
                if (r['model'] in (*MODELS, OPUS_FALLBACK) and r['model'] not in (*TOKENPLUS_MODELS, FABLE_MODEL)
                    or (r['model'] in TOKENPLUS_SETTINGS and TOKENPLUS_SETTINGS[r['model']] == r['model_label'])
                    or (r['model'] == FABLE_REQUEST and r['model_label'] == FABLE_SETTING))
                and (not r['model'].startswith('deepseek/') or r.get('model_label') in DEEPSEEK_SETTINGS)]
    keys = [(r['task'], setting_key(r)) for r in rows]
    settings = [m for m in MODELS if not m.startswith('deepseek/')] + list(DEEPSEEK_SETTINGS)
    if len(keys) != len(set(keys)) or set(keys) != {(t, m) for t in tasks for m in settings}:
        raise ValueError('Selected settings must each cover exactly the complete task catalog')
    return sorted(rows, key=lambda r: (r['task'], r['model_label']))


def verified_bytes(path, expected):
    data = path.read_bytes()
    if len(data) != expected['bytes'] or digest(data) != expected['sha256']:
        raise ValueError(f'Archived source changed: {path.name}')
    return data


def original_claude_source(pointer, row, trajectory, jobs=None):
    """Bind a verifier-only regrade to its reviewed original coding evidence."""
    evidence = [e for e in read(CONTENT / 'coding-source-evidence.json')['trials']
                if e['task'] == row['task'] and e['setting'] == row['model_label']
                and e['trajectory_sha256'] == digest(trajectory)]
    if len(evidence) != 1:
        raise ValueError('Missing verified original coding source')
    evidence = evidence[0]
    step5_source = (row.get('model') == 'step-5-preview' and
                    evidence.get('purpose') == 'step5_verified_original_coding')
    fable_source = (row.get('model') == FABLE_REQUEST and pointer.get('mode') == 'regrade' and
                    evidence.get('purpose') == 'fable_verified_original_coding')
    if not (step5_source or fable_source) and (pointer.get('actual_agent') != 'nop' or not pointer.get('no_new_coding')):
        raise ValueError('Original coding supplements require an explicit NoP regrade')
    root = (Path(pointer['coding_source_original_trial']).resolve() if pointer.get('coding_source_original_trial')
            else safe_path(jobs or DEFAULT_FINAL.parent, evidence['source_trial_relative_path']))
    if digest((root / 'agent/trajectory.json').read_bytes()) != digest(trajectory):
        raise ValueError('Original coding trajectory differs from the selected regrade')
    files = evidence['files']
    for relative, expected in files.items():
        verified_bytes(safe_path(root, relative), expected)
    result = json.loads(verified_bytes(root / 'result.json', files['result.json']))
    if (result['id'] != evidence['source_trial_id'] or
            (pointer.get('coding_source_UUID') and result['id'] != pointer['coding_source_UUID'])):
        raise ValueError('Original coding UUID differs from the reviewed source')
    return root, files, result


def fable_usage(sessions, stream, session_id, actual_model):
    """Verify the direct max session and account for the refused request separately."""
    requests = [e['params'] for events in sessions for e in events if e.get('type') == 'api-request']
    if (not requests or {p['model'] for p in requests} != {FABLE_REQUEST, actual_model} or
            any(p.get('output_config', {}).get('effort') != 'max' for p in requests)):
        raise ValueError('Fable request models or thinking effort differ from the archive')
    if actual_model == FABLE_REQUEST:
        return claude_usage(sessions, stream, session_id, actual_model, '2.1.309'), None

    fallback = [e for e in stream if e.get('type') == 'system' and e.get('subtype') == 'model_refusal_fallback']
    if len(fallback) != 1 or any(fallback[0].get(k) != v for k, v in {
            'session_id': session_id, 'original_model': FABLE_REQUEST, 'fallback_model': actual_model,
            'scope': 'session', 'trigger': 'refusal', 'api_refusal_category': 'bio'}.items()):
        raise ValueError('Missing native Fable biology-safety fallback')
    initial_usage = []
    for event in [*stream, *(e for events in sessions for e in events if e.get('type') == 'cost-state')]:
        if event.get('type') == 'system' and event.get('subtype') == 'init':
            if event.get('model') != FABLE_REQUEST:
                raise ValueError('Unexpected initial model for the Fable fallback')
            event['model'] = actual_model
        if event.get('type') in {'result', 'cost-state'}:
            usage = event['modelUsage']
            if set(usage) != {FABLE_REQUEST, actual_model}:
                raise ValueError('Fable fallback requires counters for both models')
            initial_usage.append(normalized(usage.pop(FABLE_REQUEST), aggregate=True))
    if len(initial_usage) != 2 or initial_usage[0] != initial_usage[1] or initial_usage[0]['output_tokens']:
        raise ValueError('Fable refusal usage differs between the CLI and session counters')
    result = claude_usage(sessions, stream, session_id, actual_model, '2.1.309')
    result[0].update({key: result[0][key] + value for key, value in initial_usage[0].items()})
    return result, initial_usage[0]


def fable_reviewed_reward(pointer, source, root, reward_path, result_bytes, reward, score):
    """Bind the reviewed score to the primary metric and the frozen judge verdict."""
    review = json.loads(source(safe_path(root, pointer['qualification_archive'])))
    judge_path = safe_path(reward_path.parent, Path(review['judge_log_path']).name)
    judge = source(judge_path)
    events = [json.loads(line) for line in judge.split(b'\n') if line.startswith(b'{')]
    answers = [e['item']['text'] for e in events if e.get('type') == 'item.completed'
               and e['item'].get('type') == 'agent_message']
    gate = json.loads(source(reward_path.parent / 'reward-details.json'))['final_gate']
    primary = reward['tracing_improvement']
    if (review['kind'] != 'fable_judge_failure_regrade_final' or review['status'] != 'valid' or
            review['diagnosis'] != 'verified_regrade_manual_judge_timeout_confirmed' or
            review['manual_judge_timeout_confirmed'] is not True or review['coding_api_calls'] != 0 or
            review['primary_reward_key'] != 'tracing_improvement' or
            review['native_result_sha256'] != digest(result_bytes) or review['judge_log_sha256'] != digest(judge) or
            reward['reward'] != 0 or reward['jailbreak_judge'] != 0 or
            gate['primary_valid'] is not True or review['score'] != score or
            not math.isclose(score, primary * 100, abs_tol=1e-7) or
            events[-1]['type'] != 'turn.completed' or not answers or
            re.findall(r'"score"\s*:\s*"(yes|no)"', answers[-1]) != ['yes']):
        raise ValueError('Reviewed Fable score lacks its final primary and judge evidence')
    return {'native_reward': 0, 'reviewed_reward': primary, 'judge_verdict': 'yes',
            'judge_log_sha256': digest(judge),
            'review_note': 'The final judge process recorded a yes verdict at the timeout boundary. '
                           'The reviewed score uses the verified primary result.'}


def coding_session(trial_root):
    # Some recovered native exports retain the original-codex-sessions name.
    sessions = sorted(p for name in ('sessions', 'original-codex-sessions')
                      for p in (trial_root / 'agent' / name).rglob('*.jsonl'))
    if len(sessions) != 1:
        raise ValueError('Expected exactly one original coding session per selected trial')
    return sessions[0]


def coding_provider(pointer, events, session_id):
    metadata = [e['payload'] for e in events if e.get('type') == 'session_meta']
    expected, label = {'openrouter': ('openrouter', 'OpenRouter'),
                       'direct': ('openai', 'OpenAI')}[pointer['provider']]
    if (len(metadata) != 1 or metadata[0].get('model_provider') != expected or
            metadata[0].get('id') != session_id):
        raise ValueError('Coding session identity/provider differs from the selected trajectory')
    return label


def session_usage(events):
    """Count explicit response receipts once, including a receipt after the last UI counter."""
    requests, starts, finishes = {}, [], []
    last_thread = None
    for event in events:
        payload = event.get('payload', {})
        if event.get('type') == 'token_usage_record':
            response = payload.get('response_id')
            usage = payload.get('usage', {})
            if (not response or any(type(usage.get(k)) is not int or usage[k] < 0 for k in TOKEN_FIELDS[:-1]) or
                    usage['total_tokens'] != usage['input_tokens'] + usage['output_tokens'] or
                    usage['cached_input_tokens'] + usage['cache_write_input_tokens'] > usage['input_tokens']):
                raise ValueError('Invalid native response usage')
            if response in requests and requests[response] != usage:
                raise ValueError('Conflicting repeated response usage')
            requests[response] = usage
            last_thread = payload.get('thread_token_usage')
        elif event.get('type') == 'event_msg':
            if payload.get('type') == 'task_started':
                starts.append(event['timestamp'])
            elif payload.get('type') == 'task_complete':
                finishes.append(event['timestamp'])
    if not requests:
        raise ValueError('No per-response coding usage in the selected session')
    totals = Counter()
    for usage in requests.values():
        totals.update({k: usage[k] for k in TOKEN_FIELDS[:-1]})
    if last_thread is None or any(totals[k] != last_thread.get(k) for k in TOKEN_FIELDS[:-1]):
        raise ValueError('Response receipts disagree with the final native thread counter')
    totals['response_count'] = len(requests)
    return dict(totals), [{'response_id': k, 'usage': v} for k, v in requests.items()], starts, finishes


def coding_time(result, starts, finishes):
    execution = result.get('agent_execution') or {}
    start, finish = execution.get('started_at'), execution.get('finished_at')
    basis = 'Harbor agent_execution'
    if not start or not finish:
        start = starts[0] if len(starts) == 1 else None
        finish = finishes[0] if len(finishes) == 1 else None
        basis = 'Native coding session task_started/task_complete'
    if not start or not finish:
        return start, finish, None, 'Original coding end time unavailable; regrade duration is excluded.'
    seconds = (datetime.fromisoformat(finish) - datetime.fromisoformat(start)).total_seconds()
    if seconds < 0 or not math.isfinite(seconds):
        raise ValueError('Invalid original coding duration')
    return start, finish, seconds, basis


def apply_agent_time_override(trial):
    # Maintainer-approved assignments are bound to the reviewed trajectories.
    # Preserve timestamps, termination status and any already recorded duration.
    if (AGENT_TIME_BUDGET_ASSIGNMENTS.get(trial['trajectory_sha256']) == trial['task'] and
            trial['agent_seconds'] is None):
        trial['agent_seconds'] = 7200
        trial['agent_time_basis'] = ('7200-second task budget assigned by the benchmark maintainer; '
                                   'original coding end timestamp unavailable; regrade duration excluded.')
        if trial['task'] == 'visual-document-qa':
            trial['agent_time_basis'] = ('7200-second task budget assigned by the benchmark maintainer; '
                                        'original Harbor AgentTimeoutError confirms 7200.519128 seconds; '
                                        'selected regrade has no coding timing; regrade duration excluded.')


def prepare(final, package, base_package=None, published_base=False):
    final, package = final.resolve(), package.resolve()
    if published_base and base_package is None:
        raise ValueError('A verified base package is required')
    catalog = read(ROOT / 'content/tasks/catalog.json')
    rows = selected_rows(final, {t['name'] for t in catalog})
    if len(catalog) != 47:
        raise ValueError('This publication expects 47 tasks')
    policy = read(CONTENT / 'selection.json')
    community_models = policy.get('community_models', [])
    if (len(set(community_models)) != len(community_models) or any(m not in COMMUNITY_MODELS for m in community_models) or
            policy.get('included_models') != list(MODELS) + community_models or
            policy.get('included_settings') != list(DEEPSEEK_SETTINGS)):
        raise ValueError('Website selection must explicitly contain the selected models')
    if community_models and not base_package:
        raise ValueError('Community results must be retained from a verified --base-package')
    metadata = read(CONTENT / 'model-metadata.json')
    archive = read(final / 'MANIFEST.json')
    if archive['index_sha256'] != digest((final / 'INDEX.csv').read_bytes()):
        raise ValueError('Archive manifest and index differ')
    settings = {(s['task'], s['model'], s['model_label']): s for s in archive['settings']}
    source_hashes = {'index': archive['index_sha256'], 'archive': digest((final / 'MANIFEST.json').read_bytes()),
                     'model_metadata': digest(encode(metadata)), 'selection': digest(encode(policy)),
                     'coding_time_evidence': digest((CONTENT / 'coding-time-evidence.json').read_bytes()),
                     'coding_source_evidence': digest((CONTENT / 'coding-source-evidence.json').read_bytes())}
    if community_models:
        source_hashes['community_source_evidence'] = digest((CONTENT / 'community-source-evidence.json').read_bytes())
    release_id = policy['updated_at'] + '-selected-' + digest(encode(source_hashes))[:10]
    # Appending retains the physical corpus directory. Immutable commit URLs keep
    # the previously published snapshot available without duplicating its remote payloads.
    retained_files = None
    if published_base:
        from append_hf_trajectories import published_base_payloads
        base_manifest, retained_files = published_base_payloads(base_package)
    elif base_package:
        base_manifest = load_package(base_package, check_content=False)
    release_path = base_manifest['release_path'] if base_package else CURRENT_RELEASE
    if (package / 'publication.json.gz').exists():
        manifest = load_package(package, retained=retained_files)
        if manifest['source_hashes'] != source_hashes or manifest['release_path'] != release_path:
            raise ValueError('Package has different source records; use a new --package directory')
        snapshot = read(package / manifest['release_path'] / 'snapshot.json')
        referenced_files(package / manifest['release_path'], snapshot,
                         (p.removeprefix(release_path + '/') for p in (retained_files or {})))
        return snapshot, manifest
    # Retrying an interrupted export is safe only in this exact release directory.
    if package.exists() and any(p.name != 'releases' for p in package.iterdir()):
        raise ValueError('Unrecognized incomplete package; use a new --package directory')
    if (package / 'releases').exists() and any(p.name != Path(release_path).name for p in (package / 'releases').iterdir()):
        raise ValueError('Incomplete package belongs to another source snapshot')
    public = PublicText(final.parent, scrub)
    snapshot = {'schema': 1, 'id': release_id, 'observed_at': archive['at'], 'source_hashes': source_hashes,
                'selection': policy, 'tasks': [{k: t[k] for k in ('name', 'title', 'hardware')} for t in catalog],
                'entries': [], 'trials': [], 'publication': {'schema': 1,
                    'path_aliases': {'BENCHMARK_ROOT': 'Benchmark checkout', 'EVAL_ROOT': 'Evaluation workspace',
                                    'WORKSPACE_ROOT': 'Host workspace', 'USER_HOME': 'User home directory'},
                    'note': 'Sanitized public text; source hashes identify the unmodified private archive.'}}
    entries, usage_rows = {}, []
    previous = {}
    if base_package:
        base_snapshot = read(base_package / release_path / 'snapshot.json')
        base_usage = read(base_package.with_suffix('.usage.json'))
        previous = {(t['task'], t['configuration'].get('fallback_from', t['configuration']['model']),
                     t['configuration']['agent']): t for t in base_snapshot['trials']}
        entries.update({e['id']: e for e in base_snapshot['entries']})
        usage_rows.extend(base_usage['rows'])
        # Reuse immutable payloads, including their original redaction/export
        # format. Re-importing old trials would change published evidence bytes.
        if published_base:
            def link_file(source, target):
                if not Path(target).exists():
                    os.link(source, target)
                elif not os.path.samefile(source, target):
                    raise ValueError('Retained package payload differs from the verified base')
                return target
        else:
            link_file = shutil.copy2
        shutil.copytree(base_package / release_path / 'trials', package / release_path / 'trials',
                        copy_function=link_file, dirs_exist_ok=True)
    for number, row in enumerate(rows, 1):
        harness = 'Pi' if row['model_label'].endswith('-pi-max') else ('Claude Code' if '-claude-code-' in row['model_label'] else 'Codex')
        tokenplus = row['model'] in TOKENPLUS_SETTINGS
        fable = row['model'] == FABLE_REQUEST
        model = entry_model(row)
        coding_model = model if tokenplus or fable else row['model']
        old = previous.get((row['task'], coding_model, harness))
        if old:
            if (old['trajectory_sha256'] != row['primary_trajectory_sha256'] or
                    not math.isclose(old['score'], float(row['score']), abs_tol=1e-8)):
                raise ValueError('Previously published selection changed; cannot append')
            apply_agent_time_override(old)
            snapshot['trials'].append(old)
            continue
        root = safe_path(final, row['task'] + '/' + row['model_label'])
        pointer = read(safe_path(final, row['metadata']))
        if pointer.get('status') != 'valid' or pointer.get('DO_NOT_USE_AS_FINAL'):
            raise ValueError(f'Invalid final selection: {row["task"]} / {row["model"]}')
        for key in ('task', 'model', 'effort', 'primary_trajectory_sha256'):
            if pointer[key] != row[key]:
                raise ValueError(f'Selection mismatch: {row["task"]} / {key}')
        manifest_data = safe_path(final, row['file_manifest']).read_bytes()
        if digest(manifest_data) != row['file_manifest_sha256']:
            raise ValueError('Source file inventory changed')
        inventory = {f['relative']: f for f in json.loads(manifest_data)['files']}
        output = safe_path(root, pointer['output'])
        trial_root = safe_path(root, pointer['selected_native_trial'])

        def source(path):
            return verified_bytes(path, inventory[path.relative_to(output).as_posix()])

        trajectory_path = safe_path(final, row['primary_trajectory'])
        if trajectory_path != safe_path(root, pointer['primary_trajectory']) or trajectory_path != trial_root / 'agent/trajectory.json':
            raise ValueError('Primary trajectory does not follow the selected native trial')
        trajectory = source(trajectory_path)
        if digest(trajectory) != row['primary_trajectory_sha256']:
            raise ValueError('Primary trajectory hash changed')
        reward_path = safe_path(root, pointer['selected_reward'])
        reward_bytes = source(reward_path)
        reward = json.loads(reward_bytes)
        native = reward['reward'] if isinstance(reward, dict) else reward
        score = float(row['score'])
        reviewed = (fable and row['task'] == 'training-error-tracing' and
                    pointer.get('qualification_flag') == FABLE_REVIEWED_SCORE)
        if (not math.isfinite(score) or not 0 <= score <= 100 or
                not math.isclose(score, float(pointer['score']), abs_tol=1e-8) or
                (not reviewed and not math.isclose(score, 100 * float(native), abs_tol=1e-7))):
            raise ValueError('Selected score disagrees with the final native reward')
        result_bytes = source(safe_path(root, pointer['selected_result']))
        result = json.loads(result_bytes)
        review_evidence = fable_reviewed_reward(pointer, source, root, reward_path, result_bytes, reward, score) if reviewed else {}
        if result['task_name'].removeprefix('search-swe/') != row['task']:
            raise ValueError('Native result refers to another task')
        adjudicated_image = (tokenplus and coding_model == 'z-ai/glm-5.3' and row['task'] in GLM_IMAGE_ERRORS)
        frozen_regrade = tokenplus and pointer.get('mode') == 'frozen_submission_regrade'
        if adjudicated_image:
            if (score != 0 or result.get('verifier_result') is not None
                    or (result.get('exception_info') or {}).get('exception_type') != 'UnknownApiError'
                    or pointer.get('selected_reward_kind') != 'explicit_user_adjudication'
                    or pointer.get('qualification_flag') != 'user_adjudicated_image_input_failure_zero'
                    or reward.get('diagnosis') != pointer['qualification_flag']
                    or reward.get('decision_type') != 'explicit_user_adjudication'
                    or reward.get('original_native_outputs_modified') is not False
                    or reward.get('task') != row['task'] or reward.get('model_id') != row['model']
                    or Path(reward.get('native_trial') or '').name != result['trial_name']):
                raise ValueError('Invalid archived image-input zero adjudication')
        else:
            if frozen_regrade:
                if (row['task'] != 'scientific-paper-qa'
                        or pointer.get('qualification_flag') != 'VERIFIED_FROZEN_SUBMISSION_REGRADE'
                        or result.get('record_type') != 'qualified_frozen_submission_regrade'
                        or result.get('valid') is not True or not result.get('regrade_verified_at')):
                    raise ValueError('Missing qualified frozen-submission scoring evidence')
            elif not (result.get('verifier') or {}).get('finished_at'):
                raise ValueError('Native verification has not completed for the selected task')
            native_result_reward = result['verifier_result']['rewards']['reward']
            if not math.isclose(float(native_result_reward), float(native), abs_tol=1e-9):
                raise ValueError('Native result and selected reward differ')
        raw = json.loads(trajectory)
        selected = settings[(row['task'], row['model'], row['model_label'])]['selection']
        fable_fallback = fable and raw['agent']['model_name'] == 'claude-opus-5'
        if fable_fallback:
            if (row['task'] != 'constrained-molecular-search' or
                    selected.get('actual_model_id') != 'claude-opus-5' or
                    selected.get('actual_model_substitution') is not True or
                    selected.get('model_fallback_kind') != 'model_refusal_fallback' or
                    pointer.get('qualification_flag') != 'OFFICIAL_MODEL_REFUSAL_FALLBACK_OPUS5_ACCEPTED'):
                raise ValueError('Fable fallback lacks explicit archive approval')
            coding_model = OPUS_FALLBACK
        request_model = raw['agent']['model_name'] if fable_fallback else row['model'] if fable else coding_model
        if raw['agent']['model_name'] != ('openrouter/' + coding_model if harness == 'Pi' else request_model):
            raise ValueError('Selected trajectory model differs')
        extra_usage = None
        fallback_usage = None
        extra_agent_files = {}
        extra_source_hashes = {}
        coding_result = result
        usage_note = 'Per-response native coding receipts, deduplicated by response ID.'
        if harness == 'Claude Code':
            agent = 'Claude Code'
            coding_root, coding_read = trial_root, source
            step5_original = row['model'] == 'step-5-preview' and any(
                e['task'] == row['task'] and e['setting'] == row['model_label']
                for e in read(CONTENT / 'coding-source-evidence.json')['trials'])
            fable_original = fable and not (trial_root / 'agent/claude-code.txt').is_file()
            if step5_original or fable_original or (pointer.get('no_new_coding') and not any((trial_root / 'agent/sessions').rglob('*.jsonl'))):
                coding_root, coding_inventory, coding_result = original_claude_source(pointer, row, trajectory, final.parent)
                def coding_read(path):
                    return verified_bytes(path, coding_inventory[path.relative_to(coding_root).as_posix()])
                exported_originals = {'result.json', 'config.json', 'agent/harness.json'} if step5_original else set(coding_inventory)
                extra_agent_files = {'original-coding/' + relative: coding_root / relative
                                     for relative in coding_inventory if relative in exported_originals}
                extra_source_hashes = {'original-coding/' + relative: expected
                                       for relative, expected in coding_inventory.items()}
            provider = 'OpenRouter' if pointer.get('provider') == 'openrouter' else metadata['models'][model if fable else coding_model]['provider']
            if (raw['agent']['name'] != 'claude-code' or raw['agent']['version'] != '2.1.309' or
                    (provider == 'OpenRouter' and (pointer.get('provider') != 'openrouter' or row['effort'] != 'max')) or
                    (row['model'].startswith('kimi-') and provider != 'Moonshot AI')):
                raise ValueError('Claude Code provider or harness differs from the confirmed configuration')
            if provider == 'OpenRouter':
                coding_config = json.loads(coding_read(coding_root / 'config.json'))['agent']
                if (coding_config['name'] != 'scripts.evaluation.harbor_agents:ManagedOpenRouterClaudeCode' or
                        coding_config['model_name'] != row['model'] or
                        coding_config['kwargs'].get('version') != '2.1.309' or
                        coding_config['kwargs'].get('reasoning_effort') != 'max'):
                    raise ValueError('Claude Code configuration differs from the selected model/provider/effort')
            elif row['model'] == 'step-5-preview' or tokenplus:
                coding_config = json.loads(coding_read(coding_root / 'config.json'))['agent']
                expected_provider, allowed_host = ('Z.ai', 'api.tokenplus.cn') if tokenplus else ('StepFun', 'api.stepfun.com')
                if (provider != expected_provider or pointer.get('provider') != 'native' or row['effort'] != 'max' or
                        coding_config.get('import_path') != 'scripts.evaluation.native_agents:NativeAgent' or
                        coding_config.get('model_name') != row['model'] or
                        coding_config.get('kwargs', {}).get('version') != '2.1.309' or
                        coding_config.get('kwargs', {}).get('reasoning_effort') != 'max' or
                        allowed_host not in coding_config.get('extra_allowed_hosts', [])):
                    raise ValueError('Native coding model/provider/version/effort differs')
                if frozen_regrade:
                    original = safe_path(trial_root, result['original_native_result'])
                    coding_result = json.loads(source(original))
                    if (coding_result['id'] != result['id'] or result['id'] != pointer['native_UUID']
                            or coding_result['config']['agent']['model_name'] != row['model']):
                        raise ValueError('Frozen-submission regrade original coding identity differs')
                    extra_agent_files['original-coding/result.json'] = original
                    extra_source_hashes['original-coding/result.json'] = inventory[original.relative_to(output).as_posix()]
            elif fable:
                if (provider != 'Anthropic' or pointer.get('provider') != 'direct' or row['effort'] != 'max' or
                        selected.get('provider') != 'direct' or selected.get('agent') != 'claude-code' or
                        selected.get('agent_version') != '2.1.309' or selected.get('reasoning_effort') != 'max'):
                    raise ValueError('Fable provider or harness differs from the confirmed configuration')
                if fable_original or pointer.get('mode') != 'regrade':
                    coding_config = json.loads(coding_read(coding_root / 'config.json'))['agent']
                    if (coding_config.get('name') != 'scripts.evaluation.harbor_agents:ManagedClaudeCode' or
                            coding_config.get('model_name') != FABLE_REQUEST or
                            coding_config.get('kwargs', {}).get('version') != '2.1.309' or
                            coding_config.get('kwargs', {}).get('reasoning_effort') != 'max' or
                            'api.anthropic.com' not in coding_config.get('extra_allowed_hosts', [])):
                        raise ValueError('Fable native request is not the selected direct Claude Code max configuration')
            harness_path = coding_root / 'agent/harness.json'
            if harness_path.exists():
                harness = json.loads(coding_read(harness_path))
                if harness['actual_version'] != '2.1.309' or harness['requested_version'] != '2.1.309':
                    raise ValueError('Claude Code installed harness version differs')
            session_paths = sorted(((trial_root if fable else coding_root) / 'agent/sessions').rglob('*.jsonl'))
            if not any(p.stem == raw['session_id'] for p in session_paths):
                raise ValueError('Original Claude Code main session missing')
            if fable:
                sessions = [[load_session_event(line) for line in source(p).split(b'\n') if line.strip()] for p in session_paths]
            else:
                sessions = [[json.loads(line) for line in coding_read(p).splitlines() if line.strip()] for p in session_paths]
            stream = []
            for line in coding_read(coding_root / 'agent/claude-code.txt').splitlines():
                try:
                    stream.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # CLI progress lines are not JSON events.
            glm_resumed = (tokenplus and coding_model == 'z-ai/glm-5.3' and row['task'] == 'budgeted-bimetric-retrieval'
                           and row['primary_trajectory_sha256'] == GLM_RESUMED_USAGE_SHA256)
            if fable:
                usage, fallback_usage = fable_usage(sessions, stream, raw['session_id'], request_model)
            else:
                usage = claude_usage(sessions, stream, raw['session_id'], coding_model, raw['agent']['version'],
                                    request_model=row['model'] if tokenplus else None, receipts_only=glm_resumed)
            tokens, requests, extra_usage, start, finish, completed, usage_note = usage
            if fallback_usage:
                usage_note += ' Includes the recorded Fable prompt usage before the session switched to Opus 5.'
            if glm_resumed and (tokens['input_tokens'] != raw['final_metrics']['total_prompt_tokens']
                                or tokens['output_tokens'] != raw['final_metrics']['total_completion_tokens']
                                or tokens['cached_input_tokens'] != raw['final_metrics']['total_cached_tokens']):
                raise ValueError('GLM resumed usage differs from the archived complete receipts')
            starts, finishes = [start] if start else [], [finish] if finish else []
            start, finish, seconds, time_basis = coding_time(coding_result, starts, finishes)
            if extra_agent_files:
                time_basis += '; original coding reused for verifier-only regrade; source UUID and trajectory SHA-256 verified.'
            if time_basis.startswith('Native coding session'):
                time_basis = 'Original Claude Code cost-state startTime/totalDuration; regrade duration excluded.'
        elif harness == 'Pi':
            agent, provider = 'Pi', 'OpenRouter'
            coding_config = json.loads(source(trial_root / 'config.json'))['agent']
            harness_info = json.loads(source(trial_root / 'agent/harness.json'))
            if (raw['agent']['version'] != '1.4.0' or raw['agent']['name'] != 'pi'
                    or raw['agent']['model_name'] != 'openrouter/' + row['model']
                    or pointer.get('provider') != 'openrouter'
                    or coding_config['name'] != 'scripts.evaluation.harbor_agents:ManagedPi'
                    or harness_info['actual_version'] != '1.4.0'):
                raise ValueError('Pi harness/provider/model differs from the selected configuration')
            session_paths = sorted((trial_root / 'agent/pi/sessions').rglob('*.jsonl'))
            sessions = [[json.loads(line) for line in source(p).splitlines() if line.strip()] for p in session_paths]
            stream = []
            for line in source(trial_root / 'agent/pi.txt').splitlines():
                try:
                    stream.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            tokens, requests, completed, usage_note = pi_usage(sessions, stream, raw['session_id'], row['model'])
            start, finish, seconds, time_basis = coding_time(result, [], [])
        else:
            agent = 'Codex'
            if raw['agent']['name'] != 'codex' or raw['agent']['version'] != '0.164.0' or row['effort'] != 'max':
                raise ValueError('Codex harness or effort differs from the selected configuration')
            events = [json.loads(line) for line in source(coding_session(trial_root)).splitlines() if line.strip()]
            provider = coding_provider(pointer, events, raw['session_id'])
            tokens, requests, starts, finishes = session_usage(events)
            completed = bool(finishes)
            start, finish, seconds, time_basis = coding_time(result, starts, finishes)
        if seconds is None:
            evidence = [e for e in read(CONTENT / 'coding-time-evidence.json')['trials']
                        if e['task'] == row['task'] and e['setting'] == row['model_label']
                        and e['trajectory_sha256'] == row['primary_trajectory_sha256']]
            if len(evidence) != 1:
                raise ValueError('Missing verified original coding timing')
            evidence = evidence[0]
            if not any(digest(source(p)) == evidence['session_sha256'] for p in session_paths):
                raise ValueError('Recovered timing is bound to a different coding session')
            start, finish, seconds, _ = coding_time({'agent_execution': evidence}, [], [])
            time_basis = evidence['basis'] + ' Source result SHA-256: ' + evidence['source_result_sha256']
            if evidence.get('source_result_bytes') is not None:
                original_result = Path(pointer['coding_source_original_trial']) / 'result.json'
                expected = {'bytes': evidence['source_result_bytes'], 'sha256': evidence['source_result_sha256']}
                coding_result = json.loads(verified_bytes(original_result, expected))
                if coding_result['id'] != evidence['source_trial_id'] or coding_result['id'] != pointer['coding_source_UUID']:
                    raise ValueError('Recovered coding timing belongs to another trial')
                extra_agent_files['original-coding/result.json'] = original_result
                extra_source_hashes['original-coding/result.json'] = expected
        entry_id = release_id + '-' + row['model_label']
        trial_id = row['task'] + '-' + row['model_label'] + '-' + digest(trajectory + reward_bytes)[:12]
        destination = package / release_path / 'trials' / trial_id
        count, redactions = export_trajectory(raw, destination, scrubber=public, public=True)
        files = export_files(trial_root, reward_path.parent, destination, public, write,
                             extra_agent_files=extra_agent_files)
        folders = {'agent': trial_root / 'agent', 'verifier': reward_path.parent, 'artifacts': trial_root / 'artifacts'}
        for group, items in files['groups'].items():
            for item in items:
                path = folders.get(group, trial_root) / item['name']
                expected = (extra_source_hashes[item['name']] if group == 'agent' and item['name'] in extra_source_hashes
                            else inventory[path.relative_to(output).as_posix()])
                if item['bytes'] != expected['bytes'] or (item['source_sha256'] and item['source_sha256'] != expected['sha256']):
                    raise ValueError(f'Exported evidence differs from source inventory: {group}/{item["name"]}')
        info = metadata['models'][model]
        if info.get('inference_provider'):
            if provider != 'OpenRouter':
                raise ValueError('Inferred upstream provider must retain its OpenRouter routing provenance')
            provider = info['inference_provider'] + ' (via OpenRouter)'
        entry = {'id': entry_id, 'model': model, 'name': NAMES[model], 'effort': row['effort'],
                 'agent': agent, 'agent_version': raw['agent']['version'], 'provider': provider,
                 'release_date': info['release_date'], 'release_date_source': info['source']}
        if tokenplus:
            entry['provider_route'] = 'TokenPlus (SiliconFlow)'
        if entry_id in entries and entries[entry_id] != entry:
            raise ValueError('Mixed agent configurations in one model entry')
        entries[entry_id] = entry
        qualification = {k: selected.get(k) or pointer.get(k) for k in
                         ('qualification_flag', 'judge_semantic_quality_flag', 'qualification_limitations')}
        qualification.update(review_evidence)
        if pointer.get('source_profile_and_coding_qualification_provenance'):
            qualification['coding_source_provenance'] = pointer['source_profile_and_coding_qualification_provenance']
        qualification = sanitize({k: v for k, v in qualification.items() if v}, public)
        exception = (coding_result.get('exception_info') or {}).get('exception_type')
        fm = raw.get('final_metrics', {})
        if agent == 'Codex' and any(tokens[k] != fm.get(f) for k, f in [('input_tokens', 'total_prompt_tokens'), ('output_tokens', 'total_completion_tokens')]):
            usage_note += ' The ATIF summary lags the final receipt; totals include that recorded response.'
        config = {'agent': agent, 'version': raw['agent']['version'], 'model': coding_model,
                  'effort': row['effort'], 'provider': provider,
                  'run_mode': 'regrade' if extra_agent_files else pointer.get('mode') or 'native',
                  'task_commit': pointer.get('source_revision'), 'verifier_commit': pointer.get('source_revision')}
        if tokenplus:
            config.update(provider_route=entry['provider_route'], request_model=row['model'])
        if fable:
            config['request_model'] = FABLE_REQUEST
        if fable_fallback:
            config['fallback_from'] = FABLE_MODEL
        if frozen_regrade:
            config.update(run_mode='frozen_submission_regrade', verifier_commit=result['grader_revision'])
        if extra_agent_files:
            config.update(coding_source_trial_id=coding_result['id'], grading_trial_id=result['id'])
        trial = {'id': trial_id, 'entry': entry_id, 'task': row['task'], 'score': score, 'valid': True,
                 'agent_status': exception or ('completed' if completed else 'Completion not recorded in the archived session'),
                 'agent_seconds': seconds, 'started_at': start, 'finished_at': finish, 'agent_time_basis': time_basis,
                 'tokens': tokens, 'usage_note': usage_note, 'steps': count, 'configuration': config,
                 'qualification': qualification, 'trajectory_url': f'trials/{trial_id}/manifest.json',
                 'trajectory_sha256': digest(trajectory), 'reward_sha256': digest(reward_bytes),
                 'reward': sanitize(reward, public), 'redacted_fields': redactions}
        apply_agent_time_override(trial)
        if model != coding_model:
            if not fable_fallback and (not pointer.get('actual_model_substitution') or pointer.get('requested_scoreboard_model') != model):
                raise ValueError('Model substitution lacks explicit archive provenance')
            substitution = next(s for s in policy['model_substitutions'] if
                                s['task'] == row['task'] and s['actual_model'] == coding_model and s['requested_model'] == model)
            trial['model_substitution'] = substitution
        write(destination / 'evaluation.json', {k: trial[k] for k in ('score', 'reward', 'configuration', 'qualification')})
        snapshot['trials'].append(trial)
        usage_rows.append({'task': row['task'], 'model': coding_model, 'effort': row['effort'],
                           **({'agent': agent} if row['model'].startswith('deepseek/') else {}),
                           'primary_trajectory_sha256': digest(trajectory), 'requests': requests})
        if extra_usage is not None:
            usage_rows[-1]['aggregate_remainder'] = extra_usage
        if fallback_usage is not None:
            usage_rows[-1].update(fallback_from=FABLE_MODEL, fallback_from_usage=fallback_usage)
        print(f'Prepared {number:3}/{len(rows)}: {row["task"]} / {row["model_label"]}', flush=True)
    retained = [t for t in previous.values() if t['configuration']['model'] in community_models]
    if {(t['task'], t['configuration']['model']) for t in retained} != {
            (t['name'], m) for t in catalog for m in community_models}:
        raise ValueError('Verified base package must cover every selected community model and task')
    snapshot['trials'].extend(retained)
    snapshot['entries'] = sorted(entries.values(), key=lambda e: e['id'])
    # Freeze usage outside the upload package, so source receipts are never uploaded accidentally.
    usage = {'schema': 1, 'rows': usage_rows}
    write(package.with_suffix('.usage.json'), usage)
    calculate(snapshot, usage, read(CONTENT / 'official-pricing.json'))
    manifest = finalize(package, snapshot, release_path, retained=retained_files)
    return snapshot, manifest


def install_preview(package, snapshot, manifest):
    from build_leaderboard import generate, write_pages
    source = encode(snapshot)
    price_source = (CONTENT / 'official-pricing.json').read_bytes()
    usage_source = package.with_suffix('.usage.json').read_bytes()
    costs = calculate(snapshot, json.loads(usage_source), json.loads(price_source))
    supplement = {'schema': 1, 'snapshot_id': snapshot['id'], 'snapshot_sha256': digest(source),
                  'pricing_sha256': digest(price_source), 'usage_sha256': digest(usage_source), 'trials': costs}
    backup = package.with_suffix('.previous-site.json')
    if not backup.exists():
        write(backup, {name: read(CONTENT / name) for name in ('release.json', 'costs.json', 'storage.json')})
    write(CONTENT / 'release.json', source)
    write(CONTENT / 'releases' / (snapshot['id'] + '.json'), source)
    write(CONTENT / 'costs.json', (json.dumps(supplement, indent=2, sort_keys=True) + '\n').encode())
    write(CONTENT / 'storage.json', {'provider': 'preview', 'snapshot_id': snapshot['id'],
        'source_hashes': snapshot['source_hashes'],
        'data_base_url': '/' + package.relative_to(ROOT).as_posix() + '/' + manifest['release_path']})
    pages = generate()
    for old in (CONTENT / 'releases').glob('*.json'):
        if old.stem != snapshot['id']:
            old.unlink()
    changed, removed = write_pages(pages)
    print(f'Homepage preview ready: {changed} files generated, {removed} obsolete pages removed. HF unchanged.')
    for entry in snapshot['entries']:
        trials = [t for t in snapshot['trials'] if t['entry'] == entry['id']]
        print(f'{entry["name"]}: {len(trials)}/47 tasks, mean score {sum(t["score"] for t in trials)/len(trials):.8f}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--final-dir', type=Path, default=DEFAULT_FINAL)
    parser.add_argument('--package', type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument('--base-package', type=Path, help='Retain this verified package release directory for append')
    parser.add_argument('--check', action='store_true', help='Validate the prepared public package without writing')
    args = parser.parse_args()
    package = args.package.resolve()
    if args.check:
        manifest = load_package(package)
        referenced_files(package / manifest['release_path'], read(package / manifest['release_path'] / 'snapshot.json'))
        from upload_hf_release import check_site_snapshot
        check_site_snapshot(package, manifest)
        print('Public package and homepage snapshot verified; no network requests or writes.')
    else:
        snapshot, manifest = prepare(args.final_dir, package, args.base_package)
        install_preview(package, snapshot, manifest)


if __name__ == '__main__':
    main()
