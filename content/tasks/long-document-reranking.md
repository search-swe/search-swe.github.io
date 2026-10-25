# Long-document Reranking

Improve a fixed reranking pipeline for NarrativeQA-style long documents. Each query comes with a frozen BM25 Top-100 candidate pool, and the task focuses on reranking those candidates when relevant evidence may occur beyond the first 512 model tokens.

* **Task name**: `search-swe/long-document-reranking`
* **Domain**: `information retrieval`
* **Primary focus**: `long-document reranking`
* **Primary metric**: `Accuracy@5`
* **Tags**: `search`, `reranking`, `cross-encoder`, `long-document`, `BM25`, `NarrativeQA`

## Runtime and requirements

* **Agent time budget**: up to `120 minutes`
* **Verifier time budget**: up to `13200 seconds` (`3 hours 40 minutes`)
* **Python**: `3.12`
* **Compute**: `16` CPU cores, `16 GiB` memory, `100 GiB` storage
* **GPU required**: `no`
* **Network**: `no` — the submission uses the supplied local model offline

The verifier window covers a build of up to `1800 seconds`, two query runs of up to `3600 seconds` each, a trajectory judge of up to `3600 seconds`, and `600 seconds` for setup and cleanup. Each stage remains subject to its own time limit.

## Public input and output contract

### Inputs

* `/task/data/corpus.jsonl` — a 355-document long-document corpus.
* `/task/data/validation/queries.jsonl` — 100 public queries, each with a fixed BM25 Top-100 candidate list.
* `/task/data/validation/ground_truth.jsonl` — relevance labels for the public queries.

The candidate documents supplied with each query and the local `BAAI/bge-reranker-large` model, tokenizer, and configuration stay fixed. The submission may optimize preprocessing, document-window selection, score aggregation, caching, and inference.

### Outputs

The submission must provide executable `build.sh` and `run.sh` entry points under `/app` and return the top five reranked candidates for every query in JSONL format.

## Evaluation

The hidden split contains 100 disjoint queries. A query is a hit when at least one relevant document appears in the first five reranked candidates. `Accuracy@5` is the fraction of hidden queries that are hits.

Final reward equals `Accuracy@5` when evaluation is valid and the trajectory audit passes. Execution failures, invalid output, candidate-set or fixed-model violations, and failed trajectory audits receive a reward of `0`.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/1bd099de7b8617b863051d57b7930dd7e81d4808/tasks/long-document-reranking/instruction.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/1bd099de7b8617b863051d57b7930dd7e81d4808/tasks/long-document-reranking/task.toml)
for the complete contract at the reviewed benchmark revision.
