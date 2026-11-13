# Review response (PR #3, 2026-11-13)

## Headline
- **gemini-4-argon: 21.80 → 32.61 (corrected).** The initial run used concurrency 16, which exhausted the Vertex AI per-minute token quota and truncated **20 tasks mid-solve** (429). Re-solved **17** at low concurrency (valid scores); kept **3** that had completed before a trailing 429. argon is now comparable to the sonnet run (30.66) — the earlier "argon underperforms" was largely a quota-truncation artifact, exactly as the review flagged.
- **claude-sonnet-5-5: 30.66 unchanged;** data already clean; completeness note corrected.

## Done
- Re-solved the 17 quota-truncated argon tasks at low concurrency (no residual 429): e.g. `lightweight-query-retrieval` 0→84.93, `negative-constraint-retrieval` 0→100, `legal-stance-retrieval` 0→64.97, `long-pdf-evidence` 0→61.11.
- Kept original valid scores for the 3 argon tasks that completed before a trailing 429 (`instruction-following-embedding` 100, `code-reranker-finetuning` 47.73, `narrative-clue-search` 16.70) — not replaced by a re-solve, not cherry-picked.
- JSON validity: quoted 441 bare `[REDACTED]` boolean fields (argon); corrected step counts (argon 7,728, was recorded 0); marked token/cost `unknown` (not 0).
- Added `provenance.json` to both datasets (run commit, CLI, model/provider/effort, per-trial IDs/status, run batches).
- Corrected completeness claims (sonnet: 45/47 have an independent reward file; argon: `large-scale-formula-retrieval` MISSING counted as 0).
- Re-uploaded both HF datasets; updated both submission docs and this PR.

## Pending (need maintainer verifier-only tooling or a gateway rerun)
- `claude-sonnet-5-5 / rust-bm25-search`: **RERUN** (confirmed ECONNRESET coding interruption). Needs the Claude-Code-via-Vertex-gateway route re-applied to the updated checkout; recommended, not yet executed.
- **Verifier-only re-eval** on preserved submissions (no re-solve): sonnet `legal-stance-retrieval`, `quantity-aware-retrieval` (`judge_succeeded=False`), plus `biomedical-graph-retrieval`, `chunqiu-temporal-retrieval`, `icsi-meeting-memory`, `code-embedding-finetuning`, `query-encoder-alignment`, `large-scale-formula-retrieval`; argon `query-encoder-alignment`.

## Corrected dispositions / confirmed no-action
- sonnet `paper-metadata-retrieval`: `judge_succeeded=True, evaluation_valid=True` → genuine 0, **retain** (review flagged REEVALUATE; evidence shows no reeval needed).
- argon `same-place-image-search`: the integrity audit returned **yes**; the 0 is a genuine **incomplete submission** (`features.py` only), not an audit misjudgment.
- Argon `effort`: `high` is the harness maximum (it rejects `max`); no rerun needed for "not max".
- Java verifier bug: separately verified **no impact** on either run.

Per-item structured records: `review-response-2026-11-13.json`.
