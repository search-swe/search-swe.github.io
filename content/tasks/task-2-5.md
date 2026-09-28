# Sparse Retrieval Postings Pruning

Optimize a Python-only sparse retrieval system over one million documents with
opaque, unweighted term IDs. Preserve retrieval quality while reducing query
latency against the corrected, unpruned starter.

* **Task ID**: `search-swe/task-2-5`
* **Task type**: `optimize`
* **Domain**: `learned sparse retrieval`
* **Primary focus**: `sparse retrieval and postings pruning`
* **Primary metric**: `Quality-gated linear latency reward`
* **Tags**: `sparse-retrieval`, `inverted-index`, `IDF`, `candidate-pruning`

## Runtime and requirements

* **Agent time budget**: up to `120 minutes`
* **Python**: `3.12`
* **Compute**: `1` CPU core, `32 GiB` memory, `80 GiB` storage
* **GPU required**: `no`
* **Network**: `no`
* **Candidate limits**: `3,600 seconds` for build and `900 seconds` for search

All indexing, retrieval, scoring, pruning, and ranking logic must be Python.
The submission must be single-process and single-threaded, with no native code,
parallel query execution, runtime downloads, or external services.

## Public input and output contract

### Inputs

* `/task/data/corpus.jsonl` — the full one-million-document corpus.
* `/task/data/validation/queries.jsonl` — 200 public queries.
* `/task/data/validation/qrels.tsv` — public relevance judgments.
* `/task/data/validation/stats.json` — term and document-frequency statistics.
* `/task/data/validation/reference_top100.jsonl` — public regression rankings.

### Outputs

Provide executable `/app/build.sh` and `/app/run.sh` files. The verifier runs:

~~~bash
/app/build.sh --corpus /task/data/corpus.jsonl --index-dir /path/to/index
/app/run.sh --index-dir /app/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl
~~~

Write one JSONL object per input query, in input order:

~~~json
{"query_id":"query-id","results":[{"doc_id":"document-id","score":0.123}]}
~~~

Return at most 100 unique corpus document IDs per query. Scores must be finite,
ordered descending, with ascending document ID as the tie-breaker.

## Evaluation

The hidden split contains 1,000 queries. Results must satisfy both gates:

~~~text
NDCG@10 >= 0.89
qrels Recall@100 >= 0.99
~~~

For a valid submission, let the latency ratio be candidate wall time divided by
the corrected-starter wall time measured by the verifier:

* ratio at or below `0.25`: reward `1`;
* ratio between `0.25` and `0.35`: reward `(0.35 - ratio) / 0.10`;
* ratio at or above `0.35`: reward `0`.

Quality, execution, output, integrity, and trajectory-audit failures receive a
reward of `0`. Hidden queries, hidden judgments, and external evaluation data
are unavailable.
