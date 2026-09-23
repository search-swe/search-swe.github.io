# Query-side Encoder Alignment

Optimize a query-side retrieval system built from the compact `Qwen3-Embedding-0.6B` backbone. The document vectors are fixed in advance, so the task focuses on improving query representations without changing, re-encoding, or reordering the document collection.

* **Task ID**: `search-swe/task-2-3`
* **Task type**: `optimize`
* **Domain**: `information retrieval`
* **Primary focus**: `query encoder optimization`
* **Primary metric**: `Accuracy@1 after the runtime gate`
* **Tags**: `dense-retrieval`, `query-encoder`, `embedding`, `distillation`, `Qwen3`

## Runtime and requirements

* **Agent time budget**: up to `12 hours`
* **Python**: `3.12`
* **Compute**: `8` CPU cores, `32 GiB` memory, `100 GiB` storage
* **GPU required**: `yes`
* **Network**: `restricted` — allowlisted OpenRouter and Jina resources only

## Public input and output contract

### Inputs

* `/task/data/doc.npy` — 8,674 fixed 2,560-dimensional document vectors.
* `/task/data/corpus.jsonl` — the corpus-to-vector row mapping.
* `/task/data/validation/` — 100 public validation queries and relevance labels.
* `/task/models/Qwen3-Embedding-0.6B` — the compact query-encoder backbone.

### Outputs

The submission must contain an executable `/app/submission/run.sh`. It encodes each query, searches the supplied fixed document vectors, and returns exactly one top-ranked document per query in JSONL format.

## Evaluation

The hidden split contains 100 disjoint queries. The candidate must finish within `60%` of the fixed reference starter's measured runtime. A candidate that passes the runtime and validity gates receives:

```text
reward = clamp((candidate Accuracy@1 - 0.31) / 0.69, 0, 1)
```

The starter accuracy is diagnostic and is not subtracted from the candidate accuracy. Invalid output, modified document vectors, hidden-data access, unauthorized external retrieval, or a failed trajectory audit results in a reward of `0`.
