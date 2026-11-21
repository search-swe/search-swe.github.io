# Review response (PR #3, 2026-11-19) — regrade

Thanks for the `harbor trial regrade` pointer. All 11 flagged trials were regraded (verifier re-run on the saved original submissions; originals unmodified).

## Root cause of the "integrity judge failed" zeros
The DeepSeek trajectory/integrity judge reads `OPENAI_BASE_URL` + `OPENAI_API_KEY` directly; these were **unset in the original runs**, so the judge failed and forced reward 0. Fixed by passing them (the deepseek-capable judge key) to the verifier via `--verifier-env`.

## Recovered — false 0 → real score (sonnet)
| Task | Original | Regraded | New trial |
|---|--:|--:|---|
| chunqiu-temporal-retrieval | 0 | **55.89** | `chunqiu-temporal-retrieval__YW4RfLE` |
| legal-stance-retrieval | 0 | **48.26** | `legal-stance-retrieval__4LYgS4M` |
| quantity-aware-retrieval | 0 | **39.89** | `quantity-aware-retrieval__Pupfuqn` |
| code-embedding-finetuning | 0 | **33.50** | `code-embedding-finetuning__Lwr4Zio` |
| biomedical-graph-retrieval | 0 | **10.00** | `biomedical-graph-retrieval__HXBvLqo` |

Sonnet provisional equal-weight mean **30.66 → 34.65**.

## Confirmed valid 0 / regraded 0
- **icsi-meeting-memory** (sonnet): answer-generation now runs (72 generations, no error); **confirmed valid 0**. Trial `icsi-meeting-memory__PwvHgp3`. (Also required fixing a Docker "Nano CPUs and CPU Period" conflict in the regrade env.)
- **query-encoder-alignment** (sonnet + argon): regraded 0 — primary evaluation / baseline calibration fails (exit 1), not a judge issue. Trials `query-encoder-alignment__S4KhPjG` (sonnet), `__TLwEpq7` (argon). Flagging for your call on whether this is a valid 0.

## Pending — needs a cgroup-v2 scoring host
- **constrained-molecular-search** (sonnet + argon), **budgeted-candidate-reranking** (sonnet): the integrity judge now **confirms the submissions are legitimate**, but the deterministic grader reads cgroup-v2 limits (`/sys/fs/cgroup/cpu.max`, `memory.max`) and this scoring host is **cgroup v1**, so the grader raises FileNotFoundError → 0. These are platform-infra zeros, not valid zeros. Trials `constrained-molecular-search__Qf9eBwE` (sonnet), `__yZCNGPQ` (argon), `budgeted-candidate-reranking__GyGR2iX`.

## Original → new trial IDs (all 11 regrades)

| Task | Model | Original trial | New (regrade) trial | Reward | Disposition |
|---|---|---|---|--:|---|
| chunqiu-temporal-retrieval | sonnet | `chunqiu-temporal-retrieval__8hpmcEA` | `chunqiu-temporal-retrieval__YW4RfLE` | 55.89 | reevaluated_recovered |
| legal-stance-retrieval | sonnet | `legal-stance-retrieval__TMTDNRy` | `legal-stance-retrieval__4LYgS4M` | 48.26 | reevaluated_recovered |
| quantity-aware-retrieval | sonnet | `quantity-aware-retrieval__t2x3g7e` | `quantity-aware-retrieval__Pupfuqn` | 39.89 | reevaluated_recovered |
| code-embedding-finetuning | sonnet | `code-embedding-finetuning__mKTRabc` | `code-embedding-finetuning__Lwr4Zio` | 33.5 | reevaluated_recovered |
| biomedical-graph-retrieval | sonnet | `biomedical-graph-retrieval__yyNJfBG` | `biomedical-graph-retrieval__HXBvLqo` | 10 | reevaluated_recovered |
| icsi-meeting-memory | sonnet | `icsi-meeting-memory__kDgGC7S` | `icsi-meeting-memory__PwvHgp3` | 0 | reevaluated_valid_zero |
| query-encoder-alignment | sonnet | `query-encoder-alignment__7M4cETf` | `query-encoder-alignment__S4KhPjG` | 0 | reevaluated_zero |
| query-encoder-alignment | argon | `query-encoder-alignment__yUnmYuE` | `query-encoder-alignment__TLwEpq7` | 0 | reevaluated_zero |
| constrained-molecular-search | sonnet | `constrained-molecular-search__yfaRDio` | `constrained-molecular-search__Qf9eBwE` | pending | pending_cgroup |
| constrained-molecular-search | argon | `constrained-molecular-search__JeQEvXr` | `constrained-molecular-search__yZCNGPQ` | 0 | pending_cgroup |
| budgeted-candidate-reranking | sonnet | `budgeted-candidate-reranking__6nmMaWv` | `budgeted-candidate-reranking__GyGR2iX` | 0 | pending_cgroup |

## Scoring-environment changes needed
1. Provide `OPENAI_BASE_URL` + `OPENAI_API_KEY` to the verifier for the DeepSeek judge.
2. Score the cgroup tasks on a cgroup-v2 host (or make the grader's limit read cgroup-v1 compatible).

## Left out of my queue (your side)
argon large-scale-formula-retrieval, sonnet rust-bm25-search, sonnet large-scale-formula-retrieval.

Per-task records + rewards: `review-response-2026-11-19.json` / `regrade_index.json`. Redacted scoring + judge evidence per task: `evidence/<task>/regrade/` in each HF dataset. Argon mean 32.61 unchanged by the regrade.
