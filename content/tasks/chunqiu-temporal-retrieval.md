# ChunQiu Temporal Retrieval

Retrieve Classical Chinese annal records for reign dates and temporal constraints while distinguishing events from later commentary.

* **Task name**: `search-swe/chunqiu-temporal-retrieval`
* **Domain**: `Classical Chinese historical retrieval`
* **Primary focus**: `Reign-date interpretation and event retrieval`
* **Primary metric**: `Mean binary nDCG@10`
* **Tags**: `temporal retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `6 hours`
* **Compute**: `16` CPUs, `32 GiB` RAM, `100 GiB` storage; one A100 40 GB GPU
* **Build limit**: `1,200 seconds`
* **Query limit**: `120 seconds` for the entire evaluation batch

Use the supplied data and local `Qwen3-Embedding-0.6B` model. Optional APIs must
follow the documented OpenRouter/Jina allowlist. External datasets, additional
model weights and answer lookup are prohibited. Batch time includes startup,
input loading, inference, API calls and output writing.

## Public input and output contract

### Inputs

* `/task/data/corpus.jsonl` — 18,662 records with `doc_id` and `text`.
* `/task/data/examples.jsonl` — 6,617 labeled examples with `query_id`, `text` and `relevant_doc_ids`.
* `/task/data/dated_examples.jsonl` — 19,452 dated associations with `doc_id`, `time_text`, `reign`, `year` and `month`.
* `/task/models/Qwen3-Embedding-0.6B` — supplied local embedding weights.

There is no separate public validation split. Training examples are not mounted
in the verifier; evaluation contains 778 questions.

### Outputs

Submit executable scripts and dependencies under `/app`:

~~~bash
/app/build.sh --corpus /task/data/corpus.jsonl --index-dir /app/index
/app/run.sh --index-dir /app/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl --top-k 10
~~~

Build must finish initialization before queries arrive; a service may remain
running. The verifier uses an unprivileged user and read-only submission code,
with writable runtime state in the supplied index directory.

~~~json
{"query_id":"example","results":[{"doc_id":"document-id","score":0.123}]}
~~~

Return at most ten distinct known IDs per query, sorted by finite descending
scores, with ties following corpus order. Empty results are valid. Every query
must appear exactly once; output row order is unrestricted.

## Evaluation

Reward is mean binary nDCG@10 over all 778 questions, without baseline
subtraction. The ideal ranking contains up to ten relevant documents.

A timed-out or failed batch, malformed or missing output, or a failed mandatory
trajectory compliance audit yields zero overall; there is no partial batch credit.

The full contract is in the benchmark's [task instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/chunqiu-temporal-retrieval/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/chunqiu-temporal-retrieval/README.md),
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/chunqiu-temporal-retrieval/task.toml).
