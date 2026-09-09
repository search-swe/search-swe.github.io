# Constrained Long-document Reranking

Improve a fixed reranking pipeline for NarrativeQA-style long documents. Each query comes with a frozen BM25 Top-100 candidate pool, and the task focuses on reranking those candidates when relevant evidence may occur beyond the first 512 model tokens.

* **Task ID**: `search-swe/task-2-1`
* **Task type**: `optimize`
* **Domain**: `information retrieval`
* **Primary focus**: `long-document reranking`
* **Primary metric**: `Accuracy@5`
* **Tags**: `search`, `reranking`, `cross-encoder`, `long-document`, `BM25`, `NarrativeQA`

## Runtime and requirements

* **Agent time budget**: up to `120 minutes`
* **Python**: `3.12`
* **Compute**: `16` CPU cores, `64 GiB` memory, `100 GiB` storage
* **GPU required**: `no`
* **Network**: `restricted` — the supplied local model only

## Public input and output contract

### Inputs

* `/task/data/corpus.jsonl` — a 355-document long-document corpus.
* `/task/data/validation/queries.jsonl` — 100 public queries, each with a fixed BM25 Top-100 candidate list.
* `/task/data/validation/ground_truth.jsonl` — relevance labels for the public queries.

The submission must use the candidate documents supplied with each query and the local `BAAI/bge-reranker-large` model. It may optimize preprocessing, document-window selection, score aggregation, and inference, but may not retrieve additional candidates or replace the model.

### Outputs

The submission must provide executable `build.sh` and `run.sh` entry points under `/app` and return the top five reranked candidates for every query in JSONL format.

## Evaluation

The hidden split contains 100 disjoint queries. A query passes when its relevant document appears in the first five reranked candidates. The task score is the average held-out `Accuracy@5`; invalid output, candidate-set violations, unauthorized retrieval, or model replacement results in a score of `0`.
