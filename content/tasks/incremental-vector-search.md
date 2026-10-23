# Incremental Vector Search

Maintain one vector index through insertions and large-K queries while improving near-perfect recall.

* **Task name**: `search-swe/incremental-vector-search`
* **Domain**: `incremental vector indexes`
* **Primary focus**: `Incremental Vector Search`
* **Primary metric**: `Time-gated logarithmic missed-neighbor reduction over public reference`
* **Tags**: `incremental vector indexes`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `16` CPUs, `32 GiB` RAM, `32 GiB` storage; `0` GPU(s)

Offline CPU service. Build/insertion may use 16 CPUs; each query phase is confined to one CPU. Every 1,000-query stage/K cell must fit 10% of its frozen exact-scan time. Public runtime limits set build/insertion deadlines. Do not rebuild the whole index after each batch.

## Public input and output contract

### Inputs

`/task/public/{1536,3072}/initial.npy` contains 105,000 original FP32 vectors per collection. Ten 1,000-vector insertion batches grow each to 115,000. Each stage uses 1,000 queries at K=100,200,400,800,1000. Small independent development workloads and public warmups are supplied.

### Outputs

Submit `/app/submission/run.sh` and dependencies. The verifier runs it with bash as a persistent JSONL service. `build` supplies initial vectors and writable `state_dir`; `insert` supplies a temporary vector file and consecutive IDs. Reply `{"ok":true}` only when all rows are searchable. `search` supplies `vector` and `k`; return paired `ids` and finite nonnegative L2 `distances`, at most k. Preserve original L2 semantics; internal compression is allowed. Query-dependent work and caches count in query phases.

## Evaluation

Each requested neighbor has equal weight: 25,000,000 neighbor positions per collection. Let C be missed neighbors and Cbase the frozen reference missed count. Collection value is `clip(1-log(1+C)/log(1+Cbase),0,1)`; reward averages the two collections. K=1000 contributes ten times the positions of K=100. Macro recall is diagnostic. Exact boundary ties are accepted without numerical tolerance. Build/insertion failure, any cell timeout, resource violation or lost protocol zeros that collection; speed within budget adds no points.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/incremental-vector-search/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/incremental-vector-search/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/incremental-vector-search/task.toml)
for the complete contract at the synchronized benchmark revision.
