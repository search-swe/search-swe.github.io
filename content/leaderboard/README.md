# Leaderboard data and publication

The current homepage contains **47 tasks (24 CPU, 23 GPU), seven leaderboard
entries, and 329 selected trials**. Mean task scores: Claude Opus 5.5 48.4108822466,
GPT-6.1 Sol 46.4303712901, GPT-6 Astra 45.9273539796,
GPT-6.1 Terra 42.5322347241, Kimi K3.1 Pro 26.5999307981,
DeepSeek V4.1 Flash 1017 21.0540612397, GPT-6 Luna 13.1030991867.
`selection.json` explicitly records the included models and the sole substitution.

Astra and DeepSeek each add 47 tasks using **Codex 0.164.0 / max**, the
benchmark default. Their 28,868 source files (59,761,934,520 bytes) passed size
and SHA-256 verification. Native response receipts reconcile with all final
thread counters: Astra uses 700,858,145 tokens ($1,339.084603 estimated),
DeepSeek uses 1,800,519,562 ($23.883737988 estimated at official peak list rates).
Astra has 47 original coding durations; DeepSeek has 46 recorded durations and
one maintainer-assigned duration. DeepSeek's regraded `spoken-query-search` uses
7200 seconds for display and aggregation; its original end timestamp remains
unknown. The assignment is recorded in `agent_time_basis` and survives reimport.
Seven earlier missing durations are also assigned 7200 seconds after review:
Luna's `agentic-search` and `scientific-paper-qa`; Terra's `visual-document-qa`;
and Kimi's `evolving-personal-memory`, `incremental-vector-search`,
`long-pdf-evidence-vectorless` and `paper-metadata-retrieval`. Six native session
spans reach the two-hour deadline window. Terra's recovered original Harbor
result records 7200.519128 seconds and `AgentTimeoutError`, with the original
session hash matching the archive. All seven models now have 47/47 reported
durations. These eight assignments change only duration and its provenance.

The reviewed exceptions remain visible in individual evidence: Astra's
`agentic-search` reached its 7,200-second deadline; final SDK reconnects were
accepted by the archived deadline-overlap review, and scoring plus all three
audits completed healthily. DeepSeek's `multilingual-vector-postprocessing`
retains a valid zero after its own `pkill` terminated Codex; its
`query-encoder-alignment` retains a healthy integrity rejection for bypassing
the required query encoder. `filtered-ann-retrieval` retains its build-timeout
zero. These are not replaced by new attempts. The incomplete DeepSeek
Claude Code/Pi cohorts are excluded from this Codex entry.

The Opus entry uses **Claude Code 2.1.309 / max / OpenRouter** for all 47 tasks,
matching the benchmark default harness version. It contains 46 actual Opus 5.5
runs and one **Opus 5** run for `constrained-molecular-search` (score 19.5839).
Five prior Opus 5.5 attempts each recorded `api_refusal_category: bio` and
`model_refusal_no_fallback`. [Anthropic's Claude Code documentation](https://code.claude.com/docs/en/model-config#automatic-model-fallback)
recommends Opus 5 for biology-flagged Opus 5.5 requests. The five-attempt limit and
benchmark attribution are evaluation decisions, not an official benchmark rule.
The leaderboard, model entry and task detail disclose this substitution; the
trial's configuration, trajectory and cost calculation retain the actual Opus 5
identity. Failed attempts are outside the selected-run accounting scope.

All 15,567 files in the 47 Opus source inventories passed byte-size and SHA-256
checks. Each selected result/reward agrees with INDEX and FINAL_RESULT. All 47
have final aggregate usage and original coding time: **912,829,589 tokens** and
**$498.74161865** at official standard API rates. Resumed Claude sessions use their
last cumulative counter; local synthetic API-error messages contribute no usage.
One interrupted response in `layout-page-search` lacks a reasoning breakdown;
its complete aggregate counters cover the usage without inventing per-call values.
JSONL parsing respects literal Unicode line separators inside JSON strings.

Provider labels preserve the API route: Astra and Sol show **OpenAI**, Kimi
shows **Moonshot AI**, and Luna, Terra and Opus show **OpenRouter**. DeepSeek
shows **DeepSeek** in task rows, with **DeepSeek via OpenRouter** in the entry
subtitle and the full route in tooltips, trial details and downloads. The operator-confirmed provider allowlist
intersects the DeepSeek 1017 endpoint list only at DeepSeek; the other routed
models may use multiple allowed upstreams. Do not infer a single upstream from
the model author. Raw native configuration remains unchanged. See the
[provider routing documentation](https://openrouter.ai/docs/guides/routing/provider-selection)
and [DeepSeek endpoint list](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash-1017/endpoints).
Scores, tokens, configurations and payloads for all 235 earlier trials are
unchanged; the seven duration assignments above update their timing summaries.

The public package is `.build/hf-trajectories-astra-deepseek/`: **133,257 files**,
approximately **4.28 GiB**, with 329 ATIF
trajectories and 337 original session JSONL exports (235 Codex, 102 Claude Code). Credentials are redacted and host paths
normalized. Large binary artifacts remain listed without content downloads.
Original benchmark records are never modified.
This is also the default package for the current importer, uploader and browser
checks; `.build/hf-trajectories-current/` remains the older 235-trial append base.

The active HF directory is **`releases/current/`**, independent of model names or
publication dates. Full commit SHAs identify immutable versions. The verified
revision is recorded in [`storage.json`](storage.json) and the private receipt
`.build/hf-trajectories-astra-deepseek-uploaded.json`. The website pins that SHA rather
than reading the mutable `main` branch.

On 2026-11-13, the then-current 235-trial corpus was moved from
`releases/2026-11-11-luna-terra-sol-0b5b811770/`. The obsolete
`releases/2026-11-09-luna-terra-a9eb7c2ac3/` was removed from `main`: its 94 trials
and all 32,467 trial payload files were already present byte-for-byte in the
current corpus. Snapshot, entry and trial identities remain unchanged; previous
commit-pinned downloads still work. The migration reuses Git trees and updates
only the dataset card and publication inventory.

The following commands document that historical migration, not the current
seven-model publication:

```bash
python scripts/normalize_hf_layout.py \
  --source-package .build/hf-trajectories-luna-terra-sol-kimi-opus \
  --package .build/hf-trajectories-current --apply
```

Without `--apply`, it checks and prepares the layout locally. The script verifies
all file hashes and anonymous JSON/gzip downloads with CORS before activating
production pages. It does not commit or push the homepage repository.

For a future model addition, update the selection/import configuration, retain
the current verified package as the base, and use a fresh output package:

```bash
python scripts/publish_final_results.py \
  --base-package .build/hf-trajectories-astra-deepseek \
  --package .build/hf-trajectories-next --upload
```

To resume that upload, use `append_hf_trajectories.py` with the same arguments.
Append preserves existing payloads and the `releases/current/` directory. Remote
metadata changes abort the append; it never removes old trials. Each successful
publication has a new pinned commit and becomes the base for the next addition.
Packages, private usage receipts and backups remain gitignored under `.build/`.
See [the publication guide](../../docs/leaderboard-publication.md).

For local preview, omit `--upload` and reuse <http://localhost:7788/leaderboard/>,
or run `python -m http.server 7788 --bind 127.0.0.1`. A preview rebuild requires
reactivating the verified HF release before deployment.

## Typography and result tables

Leaderboard pages use locally hosted Geist for UI text and Google Sans Code
for code/logs. Font sources and SIL OFL licenses are in `assets/fonts/`; no
external font service is required. Task results show repository task slugs, with 14px table text and approximately
46px desktop rows. Human-readable titles remain searchable.
Narrow screens scroll the table horizontally instead of shrinking its text.

## Data and statistics

- Final selections come only from `final-trajectories/INDEX.csv` and each
  `FINAL_RESULT.json`. Native result/reward files and source file inventories
  authenticate the selected evidence. Analysis summaries from older releases
  are not used.
- Native reward × 100 equals the selected task score. Selection scores already
  use 0–100 and must not be scaled again. Every task has equal weight; CPU and
  GPU use fixed subsets. The importer requires matching complete coverage.
- A valid zero remains a valid measurement. Agent completion is separate and
  appears in Agent. Original execution duration includes tools and waiting,
  excluding setup and verification. When Harbor lacks original execution times,
  paired Codex session events or Claude Code cost-state startTime/totalDuration
  are used. Missing original end timestamps remain missing; regrade time is never
  substituted. Eight reviewed runs use the maintainer-assigned 7200-second
  coding budget, with provenance in `agent_time_basis` and exact source trajectory
  hashes in the importer. All 329 selected trials now have a reported duration.
- Total tokens in the main leaderboard sum input (including cache) + output
  across the selected All / CPU / GPU task set, not a per-task average. Entry rows
  show Input Tokens, Output Tokens and Cached Tokens; trial summaries show the
  cached subset below Input Tokens.
  Additional reasoning counters appear in Agent. Reasoning is not added a second
  time. Verifier/task-internal API usage is excluded. Regrading uses original
  coding usage once. Missing values remain missing.
- Cost sums selected coding responses at the frozen official USD API rates in
  `official-pricing.json`, checked 2026-11-13. The OpenAI models use standard
  processing, 30-minute cache writes and per-request context tiers above 272,000
  input tokens. Kimi uses standard USD rates: input/write $2, read $0.20 and
  output $10 per million tokens, uniform across context lengths. Opus 5.5 uses
  input/read/write/output $4/$0.20/$5/$20, and the Opus 5 substitution uses
  $5/$0.50/$6.25/$25 per million tokens (5-minute writes). Cache reads/writes are subsets of input and charged once; reasoning
  is already included in output. DeepSeek uses peak list prices ($0.30/$0.006/$1.20 for input/cache read/output per million), without time-of-day discounts; these estimates are not an OpenRouter invoice. Sources and pricing assumptions remain public.
- Claude Code receipts are deduplicated by message ID across streaming blocks
  and subagent sessions. For 40 Kimi trials, recorded modelUsage counters also include
  background/compaction usage. Seven Kimi trials have no aggregate counter: the fallback
  uses deduplicated recorded responses as the final reported token totals and the
  basis for estimated cost. Unrecorded usage is not estimated. Aggregate
  remainders are priced only with a flat tariff; no extra response IDs are invented.
  Claude Code guessed costUSD values are never used.
  This reporting policy applies to generated pages and `/leaderboard/results.json`;
  the verified HF snapshot and its original accounting notes remain unchanged.
  Only affected trial pages show a short fallback explanation in Agent details;
  Kimi accounting notes do not appear on the leaderboard or model overview. The Opus model-substitution note is separate.
- `scripts/leaderboard_costs.py` matches native response usage to every selected
  task/model/effort, verifies trajectory hashes and all published token totals,
  deduplicates response IDs, and calculates with decimal arithmetic before
  display rounding. `costs.json` binds the derived amounts to the exact result,
  usage and pricing snapshots. Rebuild it when any of these inputs change;
  stale or partial cost coverage fails the page build.
- Cost metadata is maintained by the website separately from the verified HF
  trajectory release. `/leaderboard/results.json` downloads the result summary
  with costs, pricing sources and immutable HF trace URLs. The original
  `release.json`, its verified hash, and the HF files remain unchanged.
- Release Date is recorded with its source in `model-metadata.json`, not the evaluation date. The importer reads
  and fingerprints the model metadata, exporting each date and its source URL.
  Missing dates display as a dash and sort last in either direction.
- Regrading is a replacement score, not an additional independent trial.
  Original trajectory and final reward hashes remain separately visible.

The main table shows `Model (effort)` and `Agent (vVersion)` on one line. Provider
information remains in entry details. Score, Release Date, Total tokens and Cost can
be sorted in either direction using the column headers or Sort selector. Sort
state survives scope changes, search, reloads and navigation back from an entry;
ranks continue to reflect scores in the selected task scope. Old `sort=score`
and `sort=tokens` URLs retain their previous descending-score/ascending-token
meaning. Entry task tables also support both score/token/cost sort directions, and
keep Hardware and Agent centered, with the version inline as `Codex (v0.164.0)`. The main board omits metric cards and agent time. Entry rows include Provider
and Agent time, with the individual trial's Cost before the final Trajectory column; durations use
`2h 5min` / `35min`. Scores are labeled with `(%)`.
Trial summaries show six metrics: score, input tokens (with cached tokens as a
secondary line), output tokens, duration, Cost and step count.
Entry and trial pages share the main board's short pricing note. Amounts display
in USD with two decimal places; totals and sorting use unrounded values.

The leaderboard defaults to **Table**; **Pareto** compares mean task score with
**Cost**, **Tokens** or **Time** for the same All / CPU / GPU selection. Cost is
the default and uses a logarithmic axis (linear if a free model is present).
Tokens sums input and output, counting cache and reasoning only once. Time sums
reported agent durations, including tools and waiting but excluding verification.
This includes the eight maintainer-assigned 7200-second coding budgets.
Missing durations are omitted, with timed/selected task coverage shown in each
model's legend and tooltip. A model with no duration is omitted from Time.
Tokens and Time use linear axes, with time ticks in hours. Release Date is not a
Pareto option. Hover or keyboard-focus points for values, and follow points or
legend links to model results. View, x-axis (`x=cost|tokens|time`), search,
scope and sort survive reloads and the return link from an entry. Search hides
models without redefining which models are Pareto-optimal in the selected
hardware scope. Each axis recomputes dominance from unrounded values; equal points do not dominate
one another. The chart is rendered locally from the embedded summary, with no
chart library, inference calls or additional trajectory downloads.

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
`FINAL_RESULT.json` final reward pointer. The Verifier tab opens the root `reward.json` by default; nested repeated-judge
rewards remain browsable as supporting evidence. When a trial was regraded separately,
the final grading files are in a separate reevaluation directory. Old neighboring verifier rewards
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

Tools and observations are joined by nonempty recorded call IDs, including
multiple outputs and missing/unmatched observations. Empty IDs are never joined
across steps: an unambiguous anonymous call uses only its step-local observations;
ambiguous outputs remain visible as unmatched observations. The viewer preserves
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
python scripts/import_final_results.py --package .build/hf-trajectories-astra-deepseek --check
python scripts/build_leaderboard.py --check
python scripts/leaderboard_costs.py --usage .build/hf-trajectories-astra-deepseek.usage.json --check
python scripts/build_tasks.py --check
node --check leaderboard.js
node --check leaderboard-pareto.js
node scripts/test_pareto.cjs
node --check trajectory-viewer.js
node --check trial-files.js
```

With Playwright available in the Node module search path and the preview server
running, run `HF_PACKAGE=.build/hf-trajectories-astra-deepseek node scripts/test_leaderboard_browser.cjs`. Set
`LEADERBOARD_ORIGIN` to use a different local server address.
Run `HF_PACKAGE=.build/hf-trajectories-astra-deepseek node scripts/test_hf_browser.cjs` for cross-origin trajectory downloads and provider labels.
Run `node scripts/test_leaderboard_costs_browser.cjs` for cost sorting, chart/table
parity across hardware scopes, keyboard tabs, links, empty states and mobile layout.

The importer check verifies the complete prepared package and its match to the
local website snapshot; it does not modify files. Static summaries also work without
JavaScript. Browser acceptance includes desktop/mobile layouts, scope and
search persistence, direct step links, lazy long outputs, full-text search,
download links, and a retry after a failed chunk request.
