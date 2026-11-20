# Budgeted Candidate Reranking

Rerank 100 fixed BM25 candidates using a frozen local model and **2,048 weighted tokens per query**, on one GPU capped at **24 GiB**. Spend tokens where they improve the top ten: output tokens cost four times input tokens, and neither candidate expansion nor fine-tuning is allowed. Reward measures nDCG@10 improvement from the frozen baseline toward the best possible ranking of those candidates.

* **Task name**: `search-swe/budgeted-candidate-reranking`
* **Domain**: `metered reranking`
* **Primary focus**: `Token allocation within a fixed candidate pool`
* **Primary metric**: `nDCG@10 improvement normalized by fixed-candidate headroom`
* **Tags**: `metered reranking`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `16` CPUs, `32 GiB` RAM, `40 GiB` storage; `1` GPU(s)

Frozen Qwen3-1.7B, offline. One GPU with a 24 GiB total device-memory cap. Each query has 2,048 weighted tokens: input tokens plus four times output tokens. Reserve maximum output before calls. Across five measurements, median local-strategy time must be at most one second and median trusted-response time at most 90 seconds; individual execution caps are two and 120 seconds, respectively. No fine-tuning, extra models or candidate expansion.

See the [Linux cgroup requirements](https://github.com/VectorSpaceLab/Search-SWE/blob/main/docs/evaluation/runtime.md#linux-cgroups) for the resource evidence required on cgroup v1 and v2 hosts.

## Public input and output contract

### Inputs

`/task/data/public.jsonl.gz` and `public-qrels.json` contain all 43 judged DL2019 queries and fixed BM25 candidates. Evaluation uses all 54 DL2020 queries. Candidate IDs, text, ranks and BM25 scores are fixed.

### Outputs

Submit `/app/submission/run.sh`, `deployment.json` and dependencies. Deployment permits only `attention` (`sdpa` or `eager`) and `cpu_threads` (1–16). Trusted loading/warmup takes at most 600/60 seconds.

The runner receives a stdin `type: query` object with query, candidates and budgets. Send `type: count` to preview token cost or `type: generate` with `messages`, `max_new_tokens` and optional `logprob_tokens`/`candidate_ids`; read responses from stdin. Finish with `{"type":"result","ids":["candidate-id"]}` containing at most ten distinct current-pool IDs. Flush JSONL; the trusted process owns model inference and accounting.

## Evaluation

Deployment and fixed warmup run once. Each query is measured five times, each with a fresh unprivileged CPU-only strategy, cleared writable `/work` and its own 2,048-token allowance. All five rankings must be valid and within budget; passing queries use the mean of their five nDCG@10 values.

Q is mean linear-gain nDCG@10 with complete official-qrels IDCG. Reward is `clip((Q-B)/(U-B),0,1)`, using the frozen strongest simple baseline `B=0.49536006501146507` and fixed-candidate oracle `U=0.8707005096559685`. No-positive-candidate queries stay in all denominators. Budget, protocol, query or inference failures give that query zero; deployment, aggregate-resource or integrity violations zero the task. The relevance metric is deterministic; the separate integrity audit still gates reward.

The integrity audit runs independently three times. Its reported value is the mean of the three binary decisions; all three must accept for a positive task reward. Missing, failed or malformed audit evidence invalidates the measurement.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/budgeted-candidate-reranking/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/budgeted-candidate-reranking/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/budgeted-candidate-reranking/task.toml)
for the complete contract at the synchronized benchmark revision.
