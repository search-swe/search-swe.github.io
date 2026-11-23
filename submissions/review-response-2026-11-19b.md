# Review response (PR #3, 2026-11-19 · round 2) — regrade of the 5 pending trials

Re: [comment 7013193625](https://github.com/search-swe/search-swe.github.io/pull/3#issuecomment-7013193625). All 5 trials regraded with **`search-swe regrade`** (verify-only on the saved submissions) using **CLI 0.3.1 @ `bec6079`** (cgroup v1/v2 fix PR#55 + query-encoder calibration fix PR#53). Dry-run showed *Missing verifier settings: none* for all 5.

## Results

| Model | Task | Original trial | New (regrade) trial | Reward | measurement_valid | integrity_judge |
|---|---|---|---|--:|:--:|:--:|
| sonnet | query-encoder-alignment | `query-encoder-alignment__7M4cETf` | `query-encoder-alignment__regrade_623a4b87f320` | **52.50** | True | None |
| argon | query-encoder-alignment | `query-encoder-alignment__yUnmYuE` | `query-encoder-alignment__regrade_08f35ada0009` | **47.50** | True | None |
| sonnet | constrained-molecular-search | `constrained-molecular-search__yfaRDio` | `constrained-molecular-search__regrade_9675d0a30749` | **22.93** | True | 1.0 |
| argon | constrained-molecular-search | `constrained-molecular-search__JeQEvXr` | `constrained-molecular-search__regrade_0268593b4ffb` | **18.57** | True | 1.0 |
| sonnet | budgeted-candidate-reranking | `budgeted-candidate-reranking__6nmMaWv` | `budgeted-candidate-reranking__regrade_3f2ed1452abf` | **29.54** | True | 1.0 |

All 5 report `status=completed`, `measurement_valid=true`. Redacted `regrade.json` + verifier `report.json`/`reward.json`/`reward-details.json` per task: `evidence/<task>/regrade/` in each HF dataset.

## Provisional means (updated)
- **claude-sonnet-5-5:** 34.65 → **36.89** (47-task; `large-scale-formula-retrieval` + `rust-bm25-search` pending, counted 0) · **38.52** over 45 resolved.
- **gemini-4-argon:** 32.61 → **34.02** (47-task; `large-scale-formula-retrieval` pending, counted 0) · **34.76** over 46 resolved.

## Judge env (per your comment)
`VERIFIER_OPENAI_API_KEY` = the deepseek-capable OpenRouter key (same as `ANSWER_JUDGE_API_KEY`), `VERIFIER_OPENAI_BASE_URL` = `https://openrouter.ai/api/v1`. The CLI maps these to `OPENAI_*` for the verifier — no manual `--verifier-env`.

## Host-specific handling (standard verifier config kept; changes documented)
1. **Argon result.json/config.json** had bare `[REDACTED]` where booleans belong (`force_build`/`delete`); repaired on a hard-linked overlay (set `true`, matching the sonnet reference). Originals untouched (verified: different inode, still redacted).
2. **cgroup tasks run the verifier container as root** → `verifier/` written root:700 → harbor `verifier.py:227` `reward.json` stat raced the root→user chown (EACCES). Re-ran those 3 with the CLI **as root** so harbor can stat them → clean `completed`. (query-encoder doesn't use that container.)
3. **Argon `constrained-molecular-search`** additionally needed its agent trajectory JSON repaired (2 structurally-bare `[REDACTED]` tokens) so the in-verifier `integrity_gate` could `json.loads` it — otherwise it crashed (`JSONDecodeError`) and scored 0.0.

## HF commits
- claude-sonnet-5-5: `e0758f61d434f416627c20b74f97e3948a3d23f7`
- gemini-4-argon: `76b0a0e6c349e57dbaab09888ab8732b0cf321c8`

## Left on your side (as you noted)
The 3 full reruns remain with you: argon `large-scale-formula-retrieval`, sonnet `rust-bm25-search`, sonnet `large-scale-formula-retrieval`. Means stay provisional until those resolve.
