# Memory-constrained Dense Retrieval

Search 1.5 million vectors within 512 MiB of memory and a 64 MiB deployable index workspace.

* **Task name**: `search-swe/memory-constrained-dense-retrieval`
* **Domain**: `compact vector retrieval`
* **Primary focus**: `Memory-constrained Dense Retrieval`
* **Primary metric**: `Accuracy@3`
* **Tags**: `compact vector retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `16` CPUs, `0.5 GiB` RAM, `100 GiB` storage; `0` GPU(s)

Offline; 16 CPUs for construction, one logical CPU shared by every online process. Build: 150 seconds; each invocation: 0.5 seconds including cold service startup and protected output capture. The 512 MiB cgroup includes descendants, runtime overhead and file cache. The `/task/index` 64 MiB tmpfs also consumes this memory.

## Public input and output contract

### Inputs

`/task/data/vectors.f32` contains 1,500,000 normalized 1,024-dimensional FP32 vectors. Matching metadata/configuration and 20 public development queries with relevance labels are supplied under `/task/data/`.

### Outputs

Submit executable `/app/build.sh` and `/app/run.sh` under `/app`. Build accepts `--vectors`, `--metadata`, `--config`, `--index-dir`; run accepts `--index-dir`, `--query-vectors`, `--query-metadata`, `--query-config`, `--output`, `--top-k 3`.

Derive all corpus-dependent state during the measured build. All final generated artifacts, executables, caches and temporary files must fit inside the supplied 64 MiB workspace; result JSONL is the exception. After build, all submission processes and shared IPC state are cleared. The first query must reload/start the service within its own deadline. Return matching `query_id` and exactly three unique valid `doc_id`/finite `score` results, descending by score with corpus-order ties. The original corpus remains readable for genuine retrieval.

## Evaluation

A is mean latency-gated Accuracy@3 over 20 hidden queries: each requires valid captured output within 0.5 seconds and a relevant top-three hit. Require `A>=0.95`; otherwise reward is zero. After this gate, reward is `A*min(1,0.030/L95)`.

L95 is the 19th sorted end-to-end duration. Failed launches/timeouts contribute 0.5 seconds; other durations include output capture and are capped at 0.5. There is one sequential pass, no hidden warmup, and no OS cache flush. Build failure, invalid/oversized index, final OOM, resource or integrity failure zeros the task.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/memory-constrained-dense-retrieval/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/memory-constrained-dense-retrieval/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/memory-constrained-dense-retrieval/task.toml)
for the complete contract at the synchronized benchmark revision.
