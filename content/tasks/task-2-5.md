# Sparse Retrieval Postings Pruning

Optimize a Python-only sparse retrieval system over a large corpus of opaque,
unweighted term IDs. Preserve retrieval quality while reducing search wall time
relative to a corrected, unpruned starter baseline.

* **Task ID**: `search-swe/task-2-5`
* **Task type**: `optimize`
* **Domain**: `learned sparse retrieval`
* **Primary focus**: `candidate generation, sparse scoring, and safe query-time pruning`
* **Primary metric**: `NDCG@10, Recall@100, and starter-relative wall time`
* **Tags**: `sparse-retrieval`, `inverted-index`, `IDF`, `candidate-pruning`, `single-threaded`

## Search-system challenge

The corpus contains one million documents represented as sets of opaque term
IDs. Queries use the same representation. The lexical form and numeric-looking
part of an ID do not encode relevance, so the solution must build its retrieval
state from the supplied corpus rather than relying on term naming patterns.

The baseline performs unpruned binary/IDF-overlap retrieval. The agent may
replace the physical index and query algorithm, but it must preserve the input
and output contracts and must not use hidden query mappings, hidden relevance
judgments, or external evaluation data.

## Runtime and requirements

The formal verifier runs the candidate and the corrected starter in the same
resource-controlled environment. The submission path is offline after the
inputs have been provided.

* **Language**: all submission logic must be Python.
* **Process model**: single-process and single-threaded; no multiprocessing, worker pools, threading, joblib, Ray, or parallel query execution.
* **Network**: no runtime network access, package installation, remote models, credentials, or external services.
* **Agent time budget**: up to 120 minutes.

The `build.sh` and `run.sh` files may be thin Bash wrappers, but indexing,
retrieval, scoring, pruning, and ranking logic must remain in Python. Native
submission source code and native executables are not allowed.

## Input and output contract

The verifier invokes the candidate with:

~~~bash
/app/build.sh \
  --corpus /task/data/corpus.jsonl \
  --index-dir /path/to/index

/app/run.sh \
  --index-dir /app/index \
  --queries /path/to/queries.jsonl \
  --output /path/to/results.jsonl
~~~

The corpus and queries are JSONL. A document has the form:

~~~json
{"doc_id":"document-id","terms":["term-id", "term-id"]}
~~~

A query has the form:

~~~json
{"query_id":"query-id","terms":["term-id", "term-id"]}
~~~

Terms within a row are unique opaque strings. The candidate must process every
query exactly once, preserve input order, and write one output object per
query:

~~~json
{"query_id":"query-id","results":[{"doc_id":"document-id","score":0.123}]}
~~~

Results may contain at most 100 unique corpus document IDs. Scores must be
finite numeric values, ordered by descending score, with opaque document IDs in
ascending lexicographic order as the tie-breaker. Returning fewer than 100
results is valid but may reduce Recall@100.

## Available validation data

The agent can use the public validation files:

* `/task/data/corpus.jsonl` — the full corpus;
* `/task/data/validation/queries.jsonl` — validation queries;
* `/task/data/validation/qrels.tsv` — validation relevance judgments;
* `/task/data/validation/stats.json` — validation term and document-frequency statistics;
* `/task/data/validation/reference_top100.jsonl` — validation regression rankings.

The formal hidden query split and hidden relevance judgments are owned by the
verifier and are unavailable to the agent.

## Corrected starter baseline

The verifier-owned starter is the latency baseline. It retains every corpus
term and every posting, applies no DF, prefix, or other posting-list pruning by
default, and performs unpruned binary/IDF-overlap search over the unweighted
set-valued inputs.

The candidate may use a different index layout and a different retrieval
algorithm. Any pruning must be derived from the supplied corpus and query
inputs and must not depend on hidden evaluator state.

## Evaluation and reward

The verifier rebuilds the candidate from the full corpus and evaluates it on a
private query split. It checks build success, executable behavior, output
validity, retrieval integrity, retrieval quality, and external process wall
time.

The hidden results must satisfy all of the following:

~~~text
NDCG@10 >= 0.89
qrels Recall@100 >= 0.99
candidate wall time <= 0.30 * corrected-starter wall time
~~~

The reward is binary:

* all quality, latency, build, run, output, and trajectory checks pass: reward `1`;
* any one of those conditions fails: reward `0`.

The verifier measures candidate and starter wall time externally under the same
workload and resource allocation. Submission-reported lookup counters and
internal timing are diagnostic only; they do not replace verifier wall-time
measurement.

## Constraints

* Do not use hidden queries, hidden qrels, hidden references, or query-document answer mappings.
* Do not access external datasets or services containing evaluation answers.
* Do not modify the evaluator, reference data, or resource counters.
* Keep `build.sh` and `run.sh` executable and write persistent artifacts only beneath the supplied index directory.
* Keep the search path deterministic and preserve the required output order.
* Keep the corrected starter as the no-pruning baseline; starter pruning flags, if present, are for explicit local experiments only.
