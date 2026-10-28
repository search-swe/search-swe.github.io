# Large-scale Formula Retrieval

Search the full ARQMath formula collection with a compact CPU index and a 50 ms query deadline.

* **Task name**: `search-swe/large-scale-formula-retrieval`
* **Domain**: `mathematical formula search`
* **Primary focus**: `Large-scale Formula Retrieval`
* **Primary metric**: `nDCG_prime`
* **Tags**: `mathematical formula search`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `2` CPUs, `4 GiB` RAM, `64 GiB` storage; `0` GPU(s)

Build: 3,600 seconds; service load: 120 seconds; public warmup: 30 seconds. At most two CPU execution threads. Prepared submission/models plus index: 34 MiB; the complete serving filesystem including caches and metadata: 40 MiB. Query deadline: 50 milliseconds. Only permitted pinned public HF models may be downloaded during development; serving is offline.

## Public input and output contract

### Inputs

`/task/data/public/formulas.tsv` provides all valid formula instances and v3 visual IDs; `posts.sqlite` provides original context. Five assessed 2021 development queries/qrels are supplied. Evaluation uses 76 assessed 2022 queries, with LaTeX alone as input.

### Outputs

Submit `/app/submission/build.sh`, `serve.sh`, source and optional pinned model weights. Build with `--data-dir /task/data/public --index-dir /work/index`; regenerate corpus-derived artifacts within that build. After build workers are killed, serve a persistent JSONL `load`/`query` protocol using the relocated read-only index and supplied writable work directory.

Load replies `{"ok":true}`. Query requests contain `query_id`, `latex`; responses contain the same ID and at most 1,000 `formula_id`/finite `score` results, descending by score. Formula IDs are unsigned decimal strings. Persisted corpus state must fit the prepared-artifact limit; build scratch cannot survive as hidden service state.

## Evaluation

Map instances to visual groups, deduplicate by first rank, remove unjudged groups but retain judged grade-zero groups. nDCG prime uses original 0–3 linear gains and complete-qrels IDCG. Reward is mean nDCG prime over all 76 queries, with failed/late queries zero. MAP prime and P prime@10 are diagnostics. Query failures restart the service; build, prepared-size, memory or total-storage failures zero the task. Faster compliant execution earns no separate points.

Reaching the agent deadline does not by itself invalidate the available submission; the verifier still checks its build and serving behavior. Trusted development-memory evidence is required, and a recorded development memory violation makes the score zero.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/1d73c6f9c4a90ba922b7572d9395a6f40661bbb2/tasks/large-scale-formula-retrieval/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/1d73c6f9c4a90ba922b7572d9395a6f40661bbb2/tasks/large-scale-formula-retrieval/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/1d73c6f9c4a90ba922b7572d9395a6f40661bbb2/tasks/large-scale-formula-retrieval/task.toml)
for the complete contract at the synchronized benchmark revision.
