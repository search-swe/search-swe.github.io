# Memory-constrained Dense Retrieval

Build an executable dense-vector search engine over 1.5 million precomputed NaturalQuestions document vectors. The task tests how an agent balances retrieval quality, memory usage, index size, and query latency when the raw vector collection is substantially larger than available memory.

* **Task ID**: `search-swe/task-1-2`
* **Task type**: `create`
* **Domain**: `information retrieval`
* **Primary focus**: `memory-constrained vector search`
* **Primary metric**: `Accuracy@3`
* **Tags**: `dense-retrieval`, `vector-search`, `NaturalQuestions`, `ANN`, `indexing`, `memory-constrained`

## Runtime and requirements

* **Agent time budget**: up to `120 minutes`
* **Python**: `3.12`
* **Compute**: `16` CPU cores, `2 GiB` memory, `100 GiB` storage
* **GPU required**: `no`
* **Network**: `no`
* **Build limit**: `120 seconds`, including index construction and service startup
* **Per-query limit**: `0.5 seconds` per invocation, measured from process start to exit

## Public input and output contract

### Inputs

* `/task/data/vectors.f32` — 1,500,000 normalized float32 vectors with dimension 1,024.
* `/task/data/metadata.jsonl` — document metadata aligned with the vector rows.
* `/task/data/vector_config.json` — vector collection configuration.
* `/task/data/validation/` — 20 public development queries and relevance labels.

### Outputs

The submission must provide executable `build.sh` and `run.sh` entry points under `/app` and return the top three corpus documents for each query in JSONL format.

## Evaluation

The verifier evaluates 20 hidden queries. A query scores `1` only if its invocation succeeds within `0.5 seconds`, its output is valid, and a relevant document appears in the top three results; otherwise it scores `0`. Reward is the mean of these per-query scores. Build or overall evaluation failure, or a failed trajectory audit, sets the final reward to `0`.

The implementation may use exact or approximate search, quantization, memory mapping, block-wise computation, or other indexing strategies, but must use the supplied vectors and operate without external retrieval resources.
