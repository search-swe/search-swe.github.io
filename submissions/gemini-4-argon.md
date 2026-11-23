# Community submission: gemini-4-argon (Antigravity CLI harness) — corrected

**Equal-weight mean: 34.02 / 100** (provisional) over all 47 Search-SWE tasks (21.80 → 32.61 → 34.02).
`large-scale-formula-retrieval` remains pending a maintainer rerun (counted 0); mean over the 46 resolved tasks is **34.76**.

- **Model:** gemini-4-argon, reasoning effort `high` (the Antigravity CLI harness's top setting; it rejects `max`).
- **Harness:** Antigravity CLI (`agy`) native route, Vertex AI via ADC. This is **not** the leaderboard's Codex harness, nor the companion Claude Code run.
- **Trajectories** (46/47, redacted, JSON-clean, real step counts): <https://huggingface.co/datasets/ubowang/search-swe-gemini-4-argon>

## Correction (2026-11-13 review response)
The initial run (concurrency 16) exhausted the Vertex AI per-minute token quota and terminated **20 tasks mid-solve** with 429 after 8 retries — an infrastructure failure, not model capability. Fix:
- **17** tasks truncated mid-work were **re-solved at low concurrency (4)** and now complete cleanly (e.g. `lightweight-query-retrieval` 0→84.93, `negative-constraint-retrieval` 0→100, `legal-stance-retrieval` 0→64.97).
- **3** tasks had already produced a complete, scored submission before a trailing 429, so their original valid scores are kept (`instruction-following-embedding` 100, `code-reranker-finetuning` 47.73, `narrative-clue-search` 16.70) — not replaced by a re-solve attempt, and not cherry-picked.
- `large-scale-formula-retrieval` still does not complete (a `/sys/fs/cgroup/memory.events` cgroup limit); counted as 0.

Corrected mean **21.80 → 32.61 → 34.02** (latest from the 2026-11-19 regrade rounds), comparable to the companion claude-sonnet-5-5 run (36.89) under its different harness.

## Data fixes (review)
- **Token usage:** recovered from the native `antigravity-cli.trajectory.jsonl` and uploaded to the HF dataset (`usage.json` + `usage_responses.jsonl`, revision `a3cd1787`; PR comment 7032165652): per-response input/cache-read/output for all 46 selected trials, mapped to the ATIF trajectory step_id (100% of model responses). Grand total input 84.05M · cache-read 684.18M · output 9.88M. **Cost** is still not recorded by the agy/Vertex route (derive from Vertex pricing × tokens).
- **JSON validity:** harness-redacted boolean fields appeared as bare `[REDACTED]`; quoted to valid `"[REDACTED]"` (content unchanged).
- **Step counts** corrected (7,728 total; earlier metadata recorded 0). `provenance.json` records both run batches (original concurrency 16 at commit 2b5dabe, re-solve concurrency 4 at 0.3.0 Java-fix commit a09bca1) and each task's result source.

## Regrade recoveries (2026-11-19, PR comments 7000354737 + 7013193625)
Verifier-only `search-swe regrade` (CLI 0.3.1 @ bec6079; cgroup v1/v2 fix PR#55 + query-encoder calibration fix PR#53) on the saved submissions recovered:
- `query-encoder-alignment` 0 → **47.50** (PR#53 fix)
- `constrained-molecular-search` 0 → **18.57** (PR#55 fix; integrity judge 1.0; argon trajectory JSON repaired so the integrity gate could parse)
Original→new trial IDs, rewards and redacted `regrade.json` summaries are in `review-response-2026-11-19b.json` and the HF dataset `evidence/<task>/regrade/`.
