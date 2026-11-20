# Memory-constrained Dense Retrieval

Search 1.5 million vectors with **one query CPU**, **512 MiB RAM** and a **64 MiB index workspace**, including runtime caches. First reach at least 95% top-three hit rate under the 0.5-second query deadline, then reduce P95 latency toward 30 ms. Reward combines accuracy and latency; compression and startup costs must both fit the limits.

* **Task name**: `search-swe/memory-constrained-dense-retrieval`
* **Domain**: `compact vector retrieval`
* **Primary focus**: `Compression and low-latency CPU retrieval`
* **Primary metric**: `Accuracy@3 × P95-latency factor, after a 95% accuracy gate`
* **Tags**: `compact vector retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `16` CPUs, `0.5 GiB` RAM, `100 GiB` storage; `0` GPU(s)

Offline; 16 CPUs for construction, one logical CPU shared by every online process. Build: 150 seconds; each invocation: 0.5 seconds including cold service startup and protected output capture. The 512 MiB cgroup includes descendants, runtime overhead and file cache. The `/task/index` 64 MiB tmpfs also consumes this memory.

See the [Linux cgroup requirements](https://github.com/VectorSpaceLab/Search-SWE/blob/main/docs/evaluation/runtime.md#linux-cgroups) for the resource evidence required on cgroup v1 and v2 hosts.

## Public input and output contract

### Inputs

`/task/data/vectors.f32` contains 1,500,000 normalized 1,024-dimensional FP32 vectors. Matching metadata/configuration and 20 public development queries with relevance labels are supplied under `/task/data/`.

### Outputs

Submit executable `/app/build.sh` and `/app/run.sh` under `/app`. Build accepts `--vectors`, `--metadata`, `--config`, `--index-dir`; run accepts `--index-dir`, `--query-vectors`, `--query-metadata`, `--query-config`, `--output`, `--top-k 3`.

Derive all corpus-dependent state during the measured build. All final generated artifacts, executables, caches and temporary files must fit inside the supplied 64 MiB workspace; result JSONL is the exception. After build, all submission processes and shared IPC state are cleared. The first query must reload/start the service within its own deadline. Return matching `query_id` and exactly three unique valid `doc_id`/finite `score` results, descending by score with corpus-order ties. The original corpus remains readable for genuine retrieval.

## Evaluation

A is mean latency-gated Accuracy@3 over 20 hidden queries: each requires valid captured output within 0.5 seconds and a relevant top-three hit. Require `A>=0.95`; otherwise reward is zero. After this gate, reward is `A*min(1,0.030/L95)`.

L95 is the 19th sorted end-to-end duration. Failed launches/timeouts contribute 0.5 seconds; other durations include output capture and are capped at 0.5. Five independent rounds each rebuild from an empty workspace, clear processes and IPC state, and query the same 20 items without warmup. Select the round with the median P95 and use both its accuracy and latency; do not pool the rounds. Query-result caches do not carry between rounds, and the OS file cache is not flushed. A failed build, invalid or oversized index, confirmed OOM, or submission resource violation earns zero. Missing required resource evidence invalidates the measurement.

A separate integrity audit must accept the trajectory and submission. Audit-service failures invalidate the measurement; a valid rejection gives zero reward.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/bec6079118beb85e1b46ad6d9de6b96e6b22ea4e/tasks/memory-constrained-dense-retrieval/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/bec6079118beb85e1b46ad6d9de6b96e6b22ea4e/tasks/memory-constrained-dense-retrieval/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/bec6079118beb85e1b46ad6d9de6b96e6b22ea4e/tasks/memory-constrained-dense-retrieval/task.toml)
for the complete contract at the synchronized benchmark revision.
