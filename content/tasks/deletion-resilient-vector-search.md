# Deletion-resilient Vector Search

Maintain graph search quality and reclaim memory as repeated deletions remove 80% of two vector collections.

* **Task name**: `search-swe/deletion-resilient-vector-search`
* **Domain**: `dynamic vector indexes`
* **Primary focus**: `Deletion-resilient Vector Search`
* **Primary metric**: `normalized log-error reduction * (0.8 + 0.2 memory efficiency)`
* **Tags**: `dynamic vector indexes`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `16` CPUs, `32 GiB` RAM, `100 GiB` storage; `0` GPU(s)

Offline CPU workload. Build/delete may use 16 CPUs; queries use one logical CPU. Each of 100 stage query phases must finish within 20% of its frozen full-scan time. Per-collection build/delete limits are in `/task/tools/runtime_limits.py`. Full graph rebuilding after each deletion batch is prohibited.

## Public input and output contract

### Inputs

`/task/data/public/{sift,gist}/` contains one million original FP32 vectors, dimension 128 or 960, configuration, ten calibration queries and public deletion blocks. Final workloads use 5,000 SIFT and 1,000 GIST queries with separate deletion orders.

### Outputs

Submit executable `/app/run.sh` and dependencies under `/app`, without prebuilt corpus indexes. Serve persistent JSONL `build`, `delete`, `query` requests. Build supplies vectors, dimensions, calibration and writable `work_dir`; reply `{"ok":true}`. Delete supplies 8,000 live IDs per stage; reply when repair is complete. Query replies contain matching integer `query_id` and up to ten `results` with integer `id` and finite nonnegative squared-L2 `distance`. Optional edge/distance counters are diagnostic. Generated state stays in `work_dir`; query-dependent cache maintenance belongs in query time.

## Evaluation

For each collection, R is mean Recall@10 across all queries and 100 stages. Let N be the number of true-neighbor positions, C=N(1-R), and Cbase the fixed tombstone-HNSW missed-hit count. `G=clip(1-log(1+C)/log(1+Cbase),0,1)`. Frozen baseline recalls are 0.988931 (SIFT) and 0.886659 (GIST).

With B0 the fixed full-corpus HNSW RSS, Bmean its mean rebuilt-live RSS, and Mmean candidate mean query-phase peak RSS, `E=clip((B0-Mmean)/(B0-Bmean),0,1)`. Collection reward is `G*(0.8+0.2*E)`; final reward averages the two. Memory alone earns no credit. A failed stage, deadline/resource violation or incomplete collection zeros that collection; invalid individual responses contribute zero recall.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/561461e2619f269ffe3c8c44a541086eee17129f/tasks/deletion-resilient-vector-search/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/561461e2619f269ffe3c8c44a541086eee17129f/tasks/deletion-resilient-vector-search/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/561461e2619f269ffe3c8c44a541086eee17129f/tasks/deletion-resilient-vector-search/task.toml)
for the complete contract at the synchronized benchmark revision.
