# Large-scale Formula Retrieval

Search mathematical formulas with **two CPU threads**, **34 MiB for code and index**, and a **50 ms deadline per query**. Rank formula relevance from LaTeX alone while fitting the full serving filesystem into 40 MiB. Quality is mean nDCG over judged visual-formula groups, using each query’s median-time response across five runs; at least three attempts must succeed on time.

* **Task name**: `search-swe/large-scale-formula-retrieval`
* **Domain**: `mathematical formula search`
* **Primary focus**: `Formula relevance under tight index and latency limits`
* **Primary metric**: `nDCG_prime`
* **Tags**: `mathematical formula search`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `2` CPUs, `4 GiB` RAM, `64 GiB` storage; `0` GPU(s)

Build: 3,600 seconds; service load: 120 seconds; public warmup: 30 seconds. At most two CPU execution threads. Prepared submission/models plus index: 34 MiB; the complete serving filesystem including caches and metadata: 40 MiB. Query deadline: 50 milliseconds. Development and the timed final build may use only documented OpenRouter/Jina APIs. Model weights, extra datasets and package downloads are prohibited. Loading, warmup and queries are offline.

See the [Linux cgroup requirements](https://github.com/VectorSpaceLab/Search-SWE/blob/main/docs/evaluation/runtime.md#linux-cgroups) for the resource evidence required on cgroup v1 and v2 hosts.

## Public input and output contract

### Inputs

`/task/data/formulas.tsv` provides all valid formula instances and v3 visual IDs; `posts.sqlite` provides original context. Five assessed 2021 development queries/qrels are supplied. Evaluation uses 76 assessed 2022 queries, with LaTeX alone as input.

### Outputs

Submit `/app/submission/build.sh`, `serve.sh` and their source files. Build with `--data-dir /task/data --index-dir /work/index`; regenerate corpus-derived artifacts within that build. After build workers are killed, serve a persistent JSONL `load`/`query` protocol using the relocated read-only index and supplied writable work directory.

Load replies `{"ok":true}`. Query requests contain `query_id`, `latex`; responses contain the same ID and at most 1,000 `formula_id`/finite `score` results, descending by score. Formula IDs are unsigned decimal strings. Persisted corpus state must fit the prepared-artifact limit; build scratch cannot survive as hidden service state.

## Evaluation

Map instances to visual groups, deduplicate by first rank, remove unjudged groups but retain judged grade-zero groups. nDCG prime uses original 0–3 linear gains and complete-qrels IDCG. Build once, then measure five service passes with fresh processes, empty runtime directories and the same warmup and query order. Each attempt retains the 50 ms deadline. Select each query’s median-time response, ordering failed attempts after successful ones; fewer than three valid timely responses gives zero. Reward is mean nDCG prime over all 76 queries. MAP prime and P prime@10 are diagnostics. Query failures restart the service with empty scratch. Build, any pass’s initial load/warmup, prepared-size, memory or total-storage failures zero the task. The overall verifier allows 67,800 seconds for the five-pass recovery envelope; individual stage deadlines remain unchanged. Faster compliant execution earns no separate points.

The verifier scores the available submission even if the agent reached its deadline. A confirmed memory violation during development earns zero. Missing trusted development-memory evidence invalidates the measurement.

A separate integrity audit must accept the trajectory and submission. Audit-service failures invalidate the measurement; a valid rejection gives zero reward.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/large-scale-formula-retrieval/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/large-scale-formula-retrieval/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/large-scale-formula-retrieval/task.toml)
for the complete contract at the synchronized benchmark revision.
