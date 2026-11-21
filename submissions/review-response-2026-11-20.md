# Review response (PR #3, 2026-11-20) — Argon token usage

Re: [comment 7032165652](https://github.com/search-swe/search-swe.github.io/pull/3#issuecomment-7032165652). Token usage recovered from each selected trial's native `antigravity-cli.trajectory.jsonl` (saved runs; no re-run) and uploaded to the Argon HF dataset.

**Uploaded:** `ubowang/search-swe-gemini-4-argon` revision `a3cd17876ca6456af39050089e242398c86864a6` → `usage.json` + `usage_responses.jsonl`.

## Coverage
- **46 / 46** selected Vertex AI trials have **complete per-response** usage. None aggregate-only; none missing or partial.
- `large-scale-formula-retrieval` excluded (pending your rerun; you said you'll handle its usage).
- Selected trials span 3 batches: `argon-full-20261111-005939` (28), `argon-rerun-429-20261113-055829` (17), `argon-rerun-bounded` (1).

## Files
- **`usage.json`** — per-task totals (input / cache-read / output), grand total, semantics, coverage, cost note.
- **`usage_responses.jsonl`** — one record per model response (**6,373** total). Schema: `task, selected_trial_id, type, native_step_index, atif_step_id, created_at, input_tokens, cache_read_tokens, output_tokens`.

## Matching to the trajectory viewer
- `atif_step_id` maps each response to `trajectories/<task>/trajectory.json` step_id — **6,335/6,335 PLANNER_RESPONSE matched (100%)** by exact-second timestamp + order. `CHECKPOINT` → `atif_step_id=null`.
- `native_step_index` + `created_at` are also included (the native event index/timestamp you mentioned).

## Counter semantics
- `input_tokens` is **fresh (non-cached)** prompt tokens and **excludes** `cache_read_tokens` (reported separately). Full prompt = input + cache_read; billable per call = input + cache_read + output (cache reads normally discounted).
- Only `PLANNER_RESPONSE` and `CHECKPOINT` events carry tokens (verified: 0 token-bearing events outside those two types across all 46 trials).
- **CHECKPOINT = agy context-compaction call** (model re-reads context, writes a summary). It is a real model call, included as its own record; it is **not** a cumulative running total and does not double-count PLANNER_RESPONSE tokens.

## Cost
Not recorded by the agy native route (Vertex AI via ADC) — no cost field in `harness.json` or the native trajectory, and Vertex billing isn't returned per call. Derive from Vertex Gemini pricing × the token counts (USD).

## Grand total (46 trials)
input **84,052,615** · cache-read **684,181,727** · output **9,880,320** · total **778,114,662**.
