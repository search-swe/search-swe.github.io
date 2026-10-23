# Budgeted Candidate Reranking

Allocate a small local-model token budget to rerank a fixed pool of 100 BM25 passages.

* **Task name**: `search-swe/budgeted-candidate-reranking`
* **Domain**: `metered reranking`
* **Primary focus**: `Budgeted Candidate Reranking`
* **Primary metric**: `nDCG@10 improvement normalized by fixed-candidate headroom`
* **Tags**: `metered reranking`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `16` CPUs, `32 GiB` RAM, `40 GiB` storage; `1` GPU(s)

Frozen Qwen3-1.7B, offline. One A100 40 GB with 24 GiB total device-memory cap. Each query has 2,048 weighted tokens: input tokens plus four times output tokens. Reserve maximum output before calls. Strategy work has one cumulative second; trusted response waits have 90 seconds. No fine-tuning, extra models or candidate expansion.

## Public input and output contract

### Inputs

`/task/data/public.jsonl.gz` and `public-qrels.json` contain all 43 judged DL2019 queries and fixed BM25 candidates. Evaluation uses all 54 DL2020 queries. Candidate IDs, text, ranks and BM25 scores are fixed.

### Outputs

Submit `/app/submission/run.sh`, `deployment.json` and dependencies. Deployment permits only `attention` (`sdpa` or `eager`) and `cpu_threads` (1–16). Trusted loading/warmup takes at most 600/60 seconds. Each query launches a fresh unprivileged CPU-only strategy with writable `/work`.

The runner receives a stdin `type: query` object with query, candidates and budgets. Send `type: count` to preview token cost or `type: generate` with `messages`, `max_new_tokens` and optional `logprob_tokens`/`candidate_ids`; read responses from stdin. Finish with `{"type":"result","ids":["candidate-id"]}` containing at most ten distinct current-pool IDs. Flush JSONL; the trusted process owns model inference and accounting.

## Evaluation

Q is mean linear-gain nDCG@10 with complete official-qrels IDCG. Reward is `clip((Q-B)/(U-B),0,1)`, using the frozen strongest simple baseline `B=0.49536006501146507` and fixed-candidate oracle `U=0.8707005096559685`. No-positive-candidate queries stay in all denominators. Budget, protocol, query or inference failures give that query zero; deployment, aggregate-resource or integrity violations zero the task. The relevance metric is deterministic; the separate integrity audit still gates reward.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/budgeted-candidate-reranking/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/budgeted-candidate-reranking/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/budgeted-candidate-reranking/task.toml)
for the complete contract at the synchronized benchmark revision.
