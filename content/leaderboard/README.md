# Leaderboard data and publication

The homepage now links to `/leaderboard/`, with static model entries and 188
trial pages. Local previews read exported trajectories. Production pages read the same public
files from an immutable Hugging Face commit. Neither mode calls inference APIs or
modifies evaluation jobs. See [the publication guide](../../docs/leaderboard-publication.md)
for the prepared upload script, path normalization and production checks.

The current selection has 47 tasks (24 CPU, 23 GPU) and four models. The
2026-10-31 withdrawal removes two tasks and their eight trials from scores,
token totals, task pages and trial routes. `scripts/prune_hf_tasks.py` checks the
prepared HF update offline; `--apply` deletes only those trial directories and
updates the dataset metadata in one guarded commit. It then verifies the result
and pins the local site to the new HF revision. Before execution, the local site
previews the prepared public package. See the publication guide for the command.

From the homepage repository root:

```bash
python scripts/import_results.py --jobs /data/Search-SWE-Workspace/Search-SWE/run-eval-release/Search-SWE/jobs
python scripts/build_leaderboard.py
python scripts/build_tasks.py
python -m http.server 7788 --bind 127.0.0.1
```

Open <http://localhost:7788/leaderboard/>. If the existing homepage server already
uses port 7788, reuse it. Serve the repository at the domain root; deep links
are real directories and refresh without a routing fallback.

`release.json` is the current compact snapshot. `releases/<id>.json` stores
imported snapshots; withdrawn selections must also be removed from these public
JSON files. The release ID includes a hash of the selected index
and analysis results. HTML is generated into `leaderboard/`; obsolete generated
entry, snapshot and trial pages are removed when the selection changes.
Large exports in `data/leaderboard/traces/` are ignored by Git; a fresh checkout
needs the importer to read trajectories. The importer leaves original records
and older exports untouched. Public packages are prepared separately in `.build/hf-trajectories/`; source
exports and public packages are both excluded from Git.

## Typography and result tables

Leaderboard pages use locally hosted Geist for UI text and Google Sans Code
for code/logs. Font sources and SIL OFL licenses are in `assets/fonts/`; no
external font service is required. Task results show repository task slugs, with 14px table text and approximately
46px desktop rows. Human-readable titles remain searchable.
Narrow screens scroll the table horizontally instead of shrinking its text.

## Data and statistics

- Final selections come only from `final-trajectories/INDEX.csv` and each
  `FINAL_RESULT.json`. Analysis comes from
  `traj-analysis/leaderboard-data/results.json`. Every selected trajectory and
  final reward is verified against its recorded SHA-256.
- Native reward × 100 equals the selected task score. Analysis scores already
  use 0–100 and must not be scaled again. Every task has equal weight; CPU and
  GPU use fixed subsets. The importer requires matching complete coverage.
- A valid zero remains a valid measurement. Agent completion is separate and
  appears in Agent. Original execution duration includes tool work and
  waiting, excluding setup and independent verification.
- Total tokens in the main leaderboard sum input (including cache) + output
  across the selected All / CPU / GPU task set, not a per-task average. Entry rows
  and trial summaries show Input Tokens, Output Tokens and Cached Tokens separately.
  Additional reasoning counters appear in Agent. Reasoning is not added a second
  time. Verifier/task-internal API usage is excluded. Regrading uses original
  coding usage once. Missing values remain missing.
- Dollar estimates are deliberately absent. Reported cache usage does not
  establish cache lifetime, actual provider routing, or paid cost.
- Release Date is the model release date recorded in the analysis snapshot’s
  `leaderboard-data/pricing.json`, not the evaluation date. The importer verifies
  that file against `results.json`’s hash and exports each date and its source URL.
  Missing dates display as a dash and sort last in either direction.
- Regrading is a replacement score, not an additional independent trial.
  Original trajectory and final reward hashes remain separately visible.

The main table shows `Model (effort)` and `Agent (vVersion)` on one line. Provider
information remains in entry details. Score, Release Date and Total tokens can
be sorted in either direction using the column headers or Sort selector. Sort
state survives scope changes, search, reloads and navigation back from an entry;
ranks continue to reflect scores in the selected task scope. Old `sort=score`
and `sort=tokens` URLs retain their previous descending-score/ascending-token
meaning. Entry task tables also support both score/token sort directions, and
keep Hardware and Agent centered, with the version inline as `Codex (v0.164.0)`. The main board omits metric cards and agent time. Entry rows include Provider
and Agent time; durations use `2h 5min` / `35min`. Scores are labeled with `(%)`.
Trial summaries show score, three token counters, duration and step count.

## Viewer and export boundaries

The leaderboard fetches no trajectories. A trial shows a continuous timeline,
loading steps in batches as the reader scrolls down and keeping loaded steps
above. Long messages initially show six lines, with Show more / Show less
controls; short messages remain fully visible. Tools show compact summaries and expand to reveal input/output. Setup
context and recorded reasoning are collapsed initially. Step links still jump
directly to the relevant position; earlier steps can be prepended. The timeline
uses the full reading width without a step sidebar. Long text and exceptionally
large groups of parallel tool calls are split further. Downloads contain the
text export in compressed ATIF JSON, not the complete jobs directory.

Each step has a compact metadata row: step number, time since the preceding
recorded step, time since the first recorded step, agent, model, and recorded
input/cache/output tokens. Timing is calculated against the complete original
step index, so direct links and filters do not reset it. Time differences include
tools and waiting; they are not isolated model latency. Hover over times for
their meaning and the original timestamp, and over token counts for exact values.
Missing counts stay missing (`—`); cached tokens are included in input and
reasoning is not added to output again. Per-step ATIF usage is preserved as
recorded and is not used to replace the separately deduplicated run totals.
Unverified ATIF dollar estimates are not shown in the step metadata.

## Trial evidence tabs

| Tab | Content |
| --- | --- |
| Trajectory | Continuous structured coding conversation and tool calls. |
| Agent | Directory tree of native agent logs, session recordings and trajectory JSON; coding time/usage below the browser. |
| Verifier | Final score, native reward, evaluation reports and verifier logs. |
| Artifacts | Collected submission files, code previews, trajectory/report downloads and provenance. |
| Config | Saved Harbor configuration and the compact evaluation settings summary. |
| Lock | Resolved Harbor configuration and task fingerprints. |
| Log | Harbor trial lifecycle log. |
| Exception | Saved exception text and/or structured exception information; an explicit empty state when none was recorded. |

Agent, Verifier and Artifacts use a directory tree with collapsible folders,
compact single-child paths, and search that preserves matching ancestors.
Selecting a file opens it in a fixed-height preview with wrap, copy and download
controls. JSON is colored without interpreting file content as HTML.

Files are exported by `scripts/export_trial_files.py` during import and indexed
in each trial's `files/index.json`. Their text is fetched only after opening the
relevant tab and selecting a file. Large text is loaded in parts, and available
text exports can be downloaded as gzip. File bodies are inserted as text.

Agent/artifact/config/lock/log/exception sources are the Harbor directory
accompanying the selected trajectory. Verifier sources **always** follow the
`FINAL_RESULT.json` final reward pointer: in 33 current trials the final grading
files are in a separate reevaluation directory. Old neighboring verifier rewards
must not replace these final results. Config/Lock can describe the retained
Harbor run rather than a subsequent separate scoring pass; the Verifier note
identifies separately regraded trials. Exceptions do not imply invalid scores.

The file catalog includes binaries and large artifacts with their original
sizes, without copying indexes, databases, model weights or archives. Previews
cover source code and small artifact text, final reports and verifier logs,
plus the saved agent logs/configuration/lock/lifecycle/exception files. Text
limits are 2 MiB per file and 8 MiB per section, except Agent (32 MiB per file
and 64 MiB per section); small
artifact data files use a 256 KiB limit. Files outside this text export remain
listed with a reason and have no download link. Hidden files and symlinks are excluded. Native session JSONL files are included
under their original directory paths. Environment values and credential
fields in JSON and JSONL are redacted; variable references remain visible. The original
files are unchanged. Exported source hashes refer to original bytes, before
redaction or JSON formatting.

Old `?tab=evaluation` and `?tab=configuration` links map to Verifier and Config;
`?tab=agent-logs` also opens Agent.

Tools and observations are joined by their recorded call IDs, including
multiple outputs and missing/unmatched observations. The viewer preserves
the recorded order. Nested agent commands remain as recorded; it does not
invent child sessions or reconstruct missing hierarchy. Embedded image/binary
payloads are preserved as text, without an image renderer in this prototype.

Search loads a per-trial word index only when requested. It matches all query
words across messages, recorded reasoning, tool inputs and outputs, including
unopened chunks. It is word matching, not phrase/substring search. Long encoded
binary strings are excluded from the search index, but preserved in the reader
and download. No output is silently truncated; long text has a load-more button.

Trajectory content is inserted as text, never HTML. The exporter selects fields,
omits environment dictionaries and native configuration extras, and redacts
recognizable credential patterns consistently in chunks, search and downloads.
This automated pass is not a full public-release review. Source logs are
unchanged; exported JSON contains no local host source paths in its metadata.

## Verification

```bash
python -m unittest discover -s scripts -p 'test_*.py'
python scripts/import_results.py --jobs /data/Search-SWE-Workspace/Search-SWE/run-eval-release/Search-SWE/jobs --check
python scripts/build_leaderboard.py --check
python scripts/build_tasks.py --check
node --check leaderboard.js
node --check trajectory-viewer.js
node --check trial-files.js
```

With Playwright available in the Node module search path and the preview server
running, run `node scripts/test_leaderboard_browser.cjs`. Set
`LEADERBOARD_ORIGIN` to use a different local server address.

The importer check verifies deterministic exports against the current local
source snapshot; it does not modify files. Static summaries also work without
JavaScript. Browser acceptance includes desktop/mobile layouts, scope and
search persistence, direct step links, lazy long outputs, full-text search,
download links, and a retry after a failed chunk request.
