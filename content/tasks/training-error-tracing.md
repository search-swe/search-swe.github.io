# Training Error Tracing

Retrieve modified training records associated with erroneous generated answers while reducing latency and GPU memory.

* **Task name**: `search-swe/training-error-tracing`
* **Domain**: `training-record retrieval`
* **Primary focus**: `Training Error Tracing`
* **Primary metric**: `quality-gated paired query-latency and GPU-memory cost`
* **Tags**: `training-record retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `4 hours`
* **Compute**: `16` CPUs, `16 GiB` RAM, `64 GiB` storage; `1` GPU(s)

Four-hour development, fixed compact Qwen2.5-7B diagnostic probe, offline submission. Preparation: 1,800 seconds; each query execution: ten seconds. A separate retrieval ranker may be trained during development, but the probe/tokenizer remain fixed and verification cannot train.

## Public input and output contract

### Inputs

52,001 records in `/task/data/train.jsonl`, fixed probe under `/task/models/base/`, training-only token losses/alternatives and 50 public errors across five groups. Hidden evaluation has 100 errors across ten disjoint groups. Queries include actual token IDs, marked error positions and generated answer; preserve token alignment.

### Outputs

A complete starter exists under `/app/submission/`. Submit `prepare.sh --data-dir /task/data --model-dir /task/models --index-dir INDEX` and `run.sh --index-dir INDEX --query QUERY_JSON --output OUTPUT_JSON --top-k 10` plus frozen artifacts. Required `submission.json` records schema version 1, method, configuration and each frozen artifact’s path, hash and generation provenance.

Return `query_id` and up to ten unique training `ids`. Each hidden request is repeated three times in shuffled orders. Recompute all query-dependent features/results after each delivery; only training-derived caches may persist. Mutable state stays inside INDEX.

## Evaluation

P@10 is returned modified-record hits divided by ten, not Average Precision and not proof of token-level causation. Every repetition must reach group-macro P@10 >=0.98 and every group >=0.80. After these gates, reward is `0.2+0.8*clip(log(C/0.9)/log(0.5/0.9),0,1)`, where `C=(T/Tcontrol)*(M/Mcontrol)`.

T aggregates per-query median times, then groups equally. M is sampled peak GPU usage over preparation/queries with a 1 GiB floor. The control is rerun in the same verifier. Smaller than 10% combined-cost improvement earns only the 0.2 milestone; twofold cost reduction earns full credit. Invalid/late outputs score zero within quality denominators; preparation/resource failure zeros the task. Failed control is an infrastructure error.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/561461e2619f269ffe3c8c44a541086eee17129f/tasks/training-error-tracing/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/561461e2619f269ffe3c8c44a541086eee17129f/tasks/training-error-tracing/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/561461e2619f269ffe3c8c44a541086eee17129f/tasks/training-error-tracing/task.toml)
for the complete contract at the synchronized benchmark revision.
