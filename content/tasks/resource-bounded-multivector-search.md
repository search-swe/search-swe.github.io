# Resource-bounded Multivector Search

Accelerate full-corpus ColBERT retrieval while retaining at least 99% exact MaxSim Recall@100.

* **Task name**: `search-swe/resource-bounded-multivector-search`
* **Domain**: `MaxSim search efficiency`
* **Primary focus**: `Resource-bounded Multivector Search`
* **Primary metric**: `Normalized relative query-time improvement at Recall@100 >= 0.99`
* **Tags**: `MaxSim search efficiency`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `8` CPUs, `16 GiB` RAM, `32 GiB` storage; `0` GPU(s)

Offline CPU service; all index preparation must finish inside the two-hour agent phase. No fresh offline build follows. Load: 120 seconds; five-query public warmup: 30 seconds; complete hidden workload: 600 seconds. Eight CPUs shared by all processes.

## Public input and output contract

### Inputs

522,931 Quora documents with 8,140,769 fixed 128-dimensional token vectors under `/task/data/public/corpus/`. Five thousand development queries have exact top-100 truth. A frozen public OPQ/IVF/PQ baseline index is available; 10,000 test queries arrive individually.

### Outputs

Submit `/app/run.sh`, dependencies and prepared custom `/app/index` artifacts; record the build/self-check in `/app/README.md`. Serve persistent JSONL. `load` supplies corpus, index and writable work directory; reply `{"ok":true}`. Queries provide `query_id` and 32-by-128 token vectors. Return at most 100 unique string `doc_id`/finite `score` results in descending score order, ties by corpus row. Submission and index are read-only during verification.

## Evaluation

Exact MaxSim sums each query token’s maximum dot product over document tokens. Mean Recall@100 must be >=0.99, with all 10,000 responses completed. A fresh trusted baseline run gives TB_current; normalize candidate time as `Tnorm=T*TB/TB_current` using frozen TB and faster reference TU. Reward is `clip((TB-Tnorm)/(TB-TU),0,1)`. Raw T must also fit 600 seconds. Loading, incomplete workload, resource or quality-gate failure gives zero. Higher recall beyond the floor adds no bonus; baseline failure is an invalid measurement.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/resource-bounded-multivector-search/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/resource-bounded-multivector-search/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/resource-bounded-multivector-search/task.toml)
for the complete contract at the synchronized benchmark revision.
