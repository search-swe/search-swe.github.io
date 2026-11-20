# Training Error Tracing

Find modified training records linked to generation errors using **one GPU**, **16 GiB host RAM** and **ten seconds per query**. Every repetition must reach macro precision@10 of 0.98 and at least 0.80 in each group. Passing earns 0.2 reward; then reduce the product of latency and GPU-memory ratios toward half the paired control’s cost for full credit.

* **Task name**: `search-swe/training-error-tracing`
* **Domain**: `training-record retrieval`
* **Primary focus**: `Efficient retrieval of modified training records`
* **Primary metric**: `Latency–memory reward after precision@10 gates`
* **Tags**: `training-record retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `4 hours`
* **Compute**: `16` CPUs, `16 GiB` RAM, `64 GiB` storage; `1` GPU(s)

Four-hour development, fixed compact Qwen2.5-7B diagnostic probe, offline submission. Preparation: 1,800 seconds; each query execution: ten seconds. A separate retrieval ranker may be trained during development, but the probe/tokenizer remain fixed and verification cannot train.

See the [Linux cgroup requirements](https://github.com/VectorSpaceLab/Search-SWE/blob/main/docs/evaluation/runtime.md#linux-cgroups) for the resource evidence required on cgroup v1 and v2 hosts.

## Public input and output contract

### Inputs

52,001 records in `/task/data/train.jsonl`, fixed probe under `/task/models/base/`, training-only token losses/alternatives and 50 public errors across five groups. Hidden evaluation has 100 errors across ten disjoint groups. Queries include actual token IDs, marked error positions and generated answer; preserve token alignment.

### Outputs

A complete starter exists under `/app/submission/`; its immutable source at `/task/starter/retriever_service.py` is also the paired efficiency control. Public quality checks use `/task/runtime/score_dev.py`. Submit `prepare.sh --data-dir /task/data --model-dir /task/models --index-dir INDEX` and `run.sh --index-dir INDEX --query QUERY_JSON --output OUTPUT_JSON --top-k 10` plus frozen artifacts. Required `submission.json` records schema version 1, method, configuration and each frozen artifact’s path, hash and generation provenance.

Return `query_id` and up to ten unique training `ids`. Each hidden request is repeated five times in shuffled orders. Recompute all query-dependent features/results after each delivery; only training-derived caches may persist. Mutable state stays inside INDEX.

## Evaluation

P@10 is returned modified-record hits divided by ten, not Average Precision and not proof of token-level causation. Every repetition must reach group-macro P@10 >=0.98 and every group >=0.80. After these gates, reward is `0.2+0.8*clip(log(C/0.9)/log(0.5/0.9),0,1)`, where `C=(T/Tcontrol)*(M/Mcontrol)`.

T aggregates per-query median times, then groups equally. M is sampled peak GPU usage over preparation/queries with a 1 GiB floor. Candidate and control each prepare once and run five independently shuffled passes in the same verifier. The primary evaluation has 9,900 seconds within an 11,400-second verifier envelope. Smaller than 10% combined-cost improvement earns only the 0.2 milestone; twofold cost reduction earns full credit. Invalid or late outputs score zero within quality denominators. A submission preparation failure or resource violation earns zero. Missing required resource evidence or a failed control invalidates the measurement.

A separate integrity audit must accept the trajectory and submission. Audit-service failures invalidate the measurement; a valid rejection gives zero reward.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/training-error-tracing/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/training-error-tracing/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/training-error-tracing/task.toml)
for the complete contract at the synchronized benchmark revision.
