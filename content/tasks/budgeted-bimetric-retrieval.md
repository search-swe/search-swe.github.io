# Budgeted Bimetric Retrieval

Search 250,000 passages with cheap vectors, **20 expensive distance evaluations** per query and a **two-second median** response limit. Choose which candidates deserve scarce accurate scores without seeing the expensive vectors. CPU-only retrieval earns normalized nDCG@10 gains above a frozen baseline; full credit reaches the exact expensive-search reference, and extra speed earns no bonus.

* **Task name**: `search-swe/budgeted-bimetric-retrieval`
* **Domain**: `budgeted vector retrieval`
* **Primary focus**: `Selective use of costly distance feedback`
* **Primary metric**: `baseline-normalized mean nDCG@10`
* **Tags**: `budgeted vector retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `16` CPUs, `32 GiB` RAM, `64 GiB` storage; `0` GPU(s)

Offline CPU retrieval. Development divides the 16 CPUs/32 GiB between solver (15/31) and scorer (1/1); verification shares the full allocation. Build and reloads share 3,600 seconds. Each query must meet a two-second median complete-response time across five measurements, with a three-second execution cap per measurement, including service calls and output. Storage includes fixed assets, submission, index and caches.

See the [Linux cgroup requirements](https://github.com/VectorSpaceLab/Search-SWE/blob/main/docs/evaluation/runtime.md#linux-cgroups) for the resource evidence required on cgroup v1 and v2 hosts.

## Public input and output contract

### Inputs

`/task/public/` contains `corpus.parquet`, 384-dimensional `cheap.f32`, configuration and 500 development queries/qrels. Task-local IDs are `doc0`, `doc1`, etc. The private service holds 4,096-dimensional expensive vectors; they and model weights are inaccessible.

### Outputs

Submit executable `/app/search.sh` and dependencies under `/app`:

~~~bash
/app/search.sh --data-dir /task/public --index-dir /work/runtime/index --mode build
~~~

Emit `{"op":"ready"}` and serve flushed JSONL. Queries have `op`, opaque `token`, `text`, `vector`. Send `{"op":"score","token":"...","doc_ids":["doc0"]}` for expensive L2 distances; each document costs one call, including repeats. Finish with `{"op":"result","token":"...","doc_ids":["doc0"]}`, at most ten unique ranked IDs. Zero calls and unscored final candidates are allowed. Support `--mode load` after failures. Code is read-only.

## Evaluation

Build once; each of five full passes starts a fresh load worker with cleared scratch. Prepared artifacts become read-only after construction; query-time writes use `TMPDIR`. Each measurement has a fresh query token and a separate 20-score allowance. All five results must be valid and within budget; passing queries use the mean of their five nDCG@10 values.

Mean nDCG@10 over all 3,452 queries gives Q, including failed queries as zero. Reward is `clip((Q-B)/(U-B),0,1)`: B is the strongest frozen resource-valid simple baseline, including a development-trained two-round feedback ranker, U exact full-corpus expensive-vector retrieval quality. U is a full-credit reference, not a theoretical relevance ceiling. The frozen values are `B=0.8863201879062371` and `U=0.9117533972383719`. Excess calls, query timeout or invalid output zero that query; build/reload, resource or integrity failures zero the task. Calls and speed earn no separate bonus.

The integrity audit runs independently three times. Its reported value is the mean of the three binary decisions; all three must accept for a positive task reward. Missing, failed or malformed audit evidence invalidates the measurement.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/budgeted-bimetric-retrieval/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/budgeted-bimetric-retrieval/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/budgeted-bimetric-retrieval/task.toml)
for the complete contract at the synchronized benchmark revision.
