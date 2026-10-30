"""Prepare a self-contained public HF release. This command never uses the network."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from import_results import ROOT, digest, encode, import_snapshot, read, write
from publication import DEFAULT_PACKAGE, REPO_ID, check_text, fingerprints, load_package, safe_path


def referenced_files(release, snapshot):
    """Follow every reader/download reference, including long text and parallel calls."""
    expected = {'snapshot.json'}

    def add(base, relative):
        path = safe_path(release, (base / relative).as_posix())
        if not path.is_file():
            raise ValueError(f'Missing published reference: {path.relative_to(release)}')
        expected.add(path.relative_to(release).as_posix())
        return path

    def payload(base, value):
        if isinstance(value, dict):
            for part in value.get('parts', []):
                add(base, part)

    def calls(base, items):
        for call in items:
            payload(base, call['input'])
            for output in call['outputs']:
                payload(base, output)

    for trial in snapshot['trials']:
        base = Path('trials') / trial['id']
        manifest = read(add(base, 'manifest.json'))
        add(base, 'evaluation.json')
        add(base, manifest['download'])
        add(base, manifest['search'])
        ids = []
        for chunk in dict.fromkeys(s['chunk'] for s in manifest['steps']):
            for step in read(add(base, chunk)):
                ids.append(step['step_id'])
                payload(base, step['message'])
                payload(base, step.get('reasoning'))
                for output in step['unmatched_outputs']:
                    payload(base, output['content'])
                calls(base, step['calls'])
                for part in step.get('call_parts', []):
                    calls(base, read(add(base, part)))
        if ids != [s['id'] for s in manifest['steps']] or len(ids) != trial['steps']:
            raise ValueError(f'Trajectory step coverage mismatch: {trial["id"]}')
        files = read(add(base, 'files/index.json'))
        for group in files['groups'].values():
            for file in group:
                for part in file['parts']:
                    add(base / 'files', part)
                if file['download']:
                    add(base / 'files', file['download'])
    actual = {p.relative_to(release).as_posix() for p in release.rglob('*') if p.is_file()}
    if actual != expected:
        raise ValueError(f'Release has {len(actual - expected)} unreferenced files or {len(expected - actual)} missing files')
    return expected


def dataset_card(snapshot, release_path):
    return f'''---
license: cc-by-nc-sa-4.0
language:
- en
tags:
- search-swe
- agent-trajectories
- benchmark
---

# Search-SWE trajectories

Public evaluation evidence for [Search-SWE](https://search-swe.github.io/leaderboard/).
This release contains {len(snapshot['trials'])} selected trials, {len(snapshot['tasks'])} tasks,
and {len(snapshot['entries'])} model configurations. Observation date: {snapshot['observed_at'][:10]}.

## Files

- `{release_path}/snapshot.json`: scores, token counts, original agent durations,
  model metadata, task catalog and per-trial provenance.
- `{release_path}/trials/<trial-id>/manifest.json`: ordered step index.
- `steps-*.json`, `calls-*.json`, `text-*.json`, `search.json`: lazy reader data.
- `trajectory.json.gz`: public ATIF text download for each trial.
- `evaluation.json`: selected final reward and evaluation configuration.
- `files/index.json`: Agent, Verifier, Artifacts, Config, Lock, Log and Exception trees.
  Referenced JSON parts hold text; `.txt.gz` files provide complete exported text downloads.
- `publication.json.gz`: inventory, byte sizes, SHA-256 and Git blob hashes of every release file.

Snapshot trajectory paths are relative to `{release_path}/`. References inside
each trial are relative to its directory; file-browser references are relative to
`files/`. Use `/datasets/{REPO_ID}/resolve/<commit-sha>/<path>` URLs to read data.
The website pins a full commit SHA after upload and verification. It never uses
`main` or a temporary signed CDN URL as its saved data version.

## Interpretation

Task scores are native reward × 100, on a 0–100 percent scale. Model scores use
equal task weights. A valid zero is included. Agent termination is separate from
score validity. Only the final selected trial per model and task is published;
regrading replaces verification and does not count agent usage a second time.

Input tokens include cached input. Total tokens = input + output; cached and
reasoning counters are not added again. Missing values remain null. Agent time
includes original tool execution and waiting, excluding separate verification.
Provider billing is not inferred from these token counts.

## Public text transformations

Credential patterns and structured credential/environment values are redacted.
Host paths are replaced before text is split into chunks, consistently in previews
and downloads: `${{BENCHMARK_ROOT}}` denotes the benchmark checkout,
`${{EVAL_ROOT}}` the evaluation workspace, `${{WORKSPACE_ROOT}}` its host workspace,
and `${{USER_HOME}}` a user home directory. These are provenance aliases, not links
to files in this dataset. Container paths such as `/app`, `/tests`, `/logs` and
`/tmp` are preserved because they explain the recorded commands.

Source SHA-256 values identify unmodified original records. Exported-file hashes
in `publication.json.gz` identify the transformed public bytes; these hashes are
intentionally different. Raw environment values, unselected attempts, hidden files,
symlinks, large checkpoints/indexes and binary artifacts are not uploaded.
Large/binary artifacts can appear as names and sizes with no content download.
File previews use the same text as their corresponding compressed downloads.

## License

This repository retains its existing CC BY-NC-SA 4.0 license. Third-party materials
and code retain their own license notices where applicable.
'''


def prepare(jobs, output):
    output = Path(output).absolute()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output is not empty. Use --check for a prepared package, or choose a new --output directory.')
    # Derive only the directory name here; the importer validates all source hashes.
    jobs = Path(jobs)
    results = jobs / 'traj-analysis/leaderboard-data/results.json'
    selected = jobs / 'final-trajectories/INDEX.csv'
    release_id = read(results)['observed_at'][:10] + '-' + digest(selected.read_bytes() + results.read_bytes())[:10]
    release_path = f'releases/{release_id}'
    snapshot = import_snapshot(jobs, public_output=output / release_path)
    return finalize(output, snapshot, release_path)


def finalize(output, snapshot, release_path):
    snapshot['publication']['note'] = snapshot['publication']['note'].replace('publication.json.', 'publication.json.gz.')
    write(output / release_path / 'snapshot.json', snapshot)
    referenced_files(output / release_path, snapshot)
    write(output / 'README.md', dataset_card(snapshot, release_path).encode())
    files = {}
    for path in sorted(output.rglob('*')):
        if path.is_file() and path.name != 'publication.json.gz':
            check_text(path)
            files[path.relative_to(output).as_posix()] = fingerprints(path)
            if len(files) % 10000 == 0:
                print(f'Checked and hashed {len(files):,} public files', flush=True)
    manifest = {'schema': 1, 'repo_id': REPO_ID, 'release_path': release_path,
                'snapshot_id': snapshot['id'], 'source_hashes': snapshot['source_hashes'],
                'trials': len(snapshot['trials']), 'tasks': len(snapshot['tasks']),
                'entries': len(snapshot['entries']), 'files': files,
                'total_bytes': sum(f['bytes'] for f in files.values())}
    write(output / 'publication.json.gz', gzip.compress(encode(manifest), mtime=0))
    print(f'Public package: {output}\n{len(files):,} files, {manifest["total_bytes"] / 1024**3:.2f} GiB; all references and content checks passed.')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=Path)
    parser.add_argument('--output', type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument('--check', action='store_true', help='Verify the prepared package without rebuilding or uploading')
    args = parser.parse_args()
    if args.check:
        manifest = load_package(args.output)
        release = args.output / manifest['release_path']
        referenced_files(release, read(release / 'snapshot.json'))
        print(f'Public package verified: {len(manifest["files"]):,} files / {manifest["trials"]} trials.')
    elif args.jobs:
        prepare(args.jobs, args.output)
    else:
        parser.error('--jobs is required when preparing a new package')


if __name__ == '__main__':
    main()
