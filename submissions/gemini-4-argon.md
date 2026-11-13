# Community submission: gemini-4-argon (Antigravity CLI harness) — corrected

**Equal-weight mean: 32.61 / 100** over all 47 Search-SWE tasks (corrected from an earlier 21.80).

- **Model:** gemini-4-argon, reasoning effort `high` (the Antigravity CLI harness's top setting; it rejects `max`).
- **Harness:** Antigravity CLI (`agy`) native route, Vertex AI via ADC. This is **not** the leaderboard's Codex harness, nor the companion Claude Code run.
- **Trajectories** (46/47, redacted, JSON-clean, real step counts): <https://huggingface.co/datasets/ubowang/search-swe-gemini-4-argon>

## Correction (2026-11-13 review response)
The initial run (concurrency 16) exhausted the Vertex AI per-minute token quota and terminated **20 tasks mid-solve** with 429 after 8 retries — an infrastructure failure, not model capability. Fix:
- **17** tasks truncated mid-work were **re-solved at low concurrency (4)** and now complete cleanly (e.g. `lightweight-query-retrieval` 0→84.93, `negative-constraint-retrieval` 0→100, `legal-stance-retrieval` 0→64.97).
- **3** tasks had already produced a complete, scored submission before a trailing 429, so their original valid scores are kept (`instruction-following-embedding` 100, `code-reranker-finetuning` 47.73, `narrative-clue-search` 16.70) — not replaced by a re-solve attempt, and not cherry-picked.
- `large-scale-formula-retrieval` still does not complete (a `/sys/fs/cgroup/memory.events` cgroup limit); counted as 0.

Corrected mean **21.80 → 32.61**, comparable to the companion claude-sonnet-5-5 run (30.66) under its different harness.

## Data fixes (review)
- **Token usage / cost:** not captured by the agy native route; shown as `unknown` (not 0).
- **JSON validity:** harness-redacted boolean fields appeared as bare `[REDACTED]`; quoted to valid `"[REDACTED]"` (content unchanged).
- **Step counts** corrected (7,728 total; earlier metadata recorded 0). `provenance.json` records both run batches (original concurrency 16 at commit 2b5dabe, re-solve concurrency 4 at 0.3.0 Java-fix commit a09bca1) and each task's result source.
