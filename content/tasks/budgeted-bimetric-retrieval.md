# Budgeted Bimetric Retrieval

Search 250,000 NQ passages using cheap vectors and at most 20 expensive distance evaluations per question.

* **Task name**: `search-swe/budgeted-bimetric-retrieval`
* **Domain**: `budgeted vector retrieval`
* **Primary focus**: `Budgeted Bimetric Retrieval`
* **Primary metric**: `baseline-normalized mean nDCG@10`
* **Tags**: `budgeted vector retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `16` CPUs, `32 GiB` RAM, `64 GiB` storage; `0` GPU(s)

Offline CPU retrieval. Development divides the 16 CPUs/32 GiB between solver (15/31) and scorer (1/1); verification shares the full allocation. Build and reloads share 3,600 seconds. Each query has two seconds, including service calls and output. Storage includes fixed assets, submission, index and caches.

## Public input and output contract

### Inputs

`/task/public/` contains `corpus.parquet`, 384-dimensional `cheap.f32`, configuration and 500 development queries/qrels. Task-local IDs are `doc0`, `doc1`, etc. The private service holds 4,096-dimensional expensive vectors; they and model weights are inaccessible.

### Outputs

Submit executable `/app/search.sh` and dependencies under `/app`:

~~~bash
/app/search.sh --data-dir /task/public --index-dir /work/runtime/index --mode build
~~~

Emit `{"op":"ready"}` and serve flushed JSONL. Queries have `op`, opaque `token`, `text`, `vector`. Send `{"op":"score","token":"...","doc_ids":["doc0"]}` for expensive L2 distances; each document costs one call, including repeats. Finish with `{"op":"result","token":"...","doc_ids":["doc0"]}`, at most ten unique ranked IDs. Zero calls and unscored final candidates are allowed. Support `--mode load` after failures. Code is read-only; runtime state uses the supplied working/index directory.

## Evaluation

Mean nDCG@10 over all 3,452 queries gives Q, including failed queries as zero. Reward is `clip((Q-B)/(U-B),0,1)`: B is the strongest frozen resource-valid simple baseline, U exact full-corpus expensive-vector retrieval quality. U is a full-credit reference, not a theoretical relevance ceiling. The frozen values are `B=0.8460412084949013` and `U=0.9117533972383719`. Excess calls, query timeout or invalid output zero that query; build/reload, resource or integrity failures zero the task. Calls and speed earn no separate bonus.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/budgeted-bimetric-retrieval/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/budgeted-bimetric-retrieval/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/budgeted-bimetric-retrieval/task.toml)
for the complete contract at the synchronized benchmark revision.
