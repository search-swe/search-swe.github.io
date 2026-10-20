# Negative-Constraint Retrieval

Retrieve one passage that satisfies the requested subjects while excluding forbidden content anywhere in the passage.

* **Task name**: `search-swe/negative-constraint-retrieval`
* **Domain**: `constraint-aware passage retrieval`
* **Primary focus**: `Positive requirements and explicit exclusions`
* **Primary metric**: `Accuracy@1`
* **Tags**: `negative constraints`, `search-swe`

## Runtime and requirements

* **Agent budget**: `120 minutes`
* **Compute**: `4` CPUs, `32 GiB` RAM, `100 GiB` storage; no GPU
* **Build limit**: `1,800 seconds`
* **Query limit**: `8 seconds` per question, evaluated sequentially

The query allowance is three base seconds plus five fixed network-allowance
seconds, including all API work; it is not renewed per API call or pooled across
queries. Optional OpenRouter/Jina services must follow the documented allowlist.

## Public input and output contract

### Inputs

* `/task/data/corpus.jsonl` — 8,011 original and augmented passages.
* `/task/data/validation/queries.jsonl` — ten public questions.
* `/task/data/validation/ground_truth.jsonl` — their matching document IDs.

Ten evaluation questions use subjects disjoint from the public examples. Each
question has one correct passage. A relevant fragment does not make a passage
compliant if forbidden content occurs elsewhere. Apply the instructions to the
supplied text as written, including their treatment of preferences and exceptions.

### Outputs

Submit executable entry points and dependencies under `/app`:

~~~bash
/app/build.sh --corpus /task/data/corpus.jsonl --index-dir /app/index
/app/run.sh --index-dir /app/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl --top-k 1
~~~

The verifier rebuilds once and invokes queries separately. Future questions are
not available in advance. Honor supplied index, query and output paths.

~~~json
{"query_id":"example","results":[{"doc_id":"document-id","score":0.123}]}
~~~

Return exactly one known document ID and a finite numeric score for each query.
An empty result is invalid.

## Evaluation

Accuracy@1 is one when the returned passage is the question's correct compliant
document. Reward is mean Accuracy@1 across all ten questions, with no additional
quality threshold or bonus.

A per-question timeout contributes zero and remains in the denominator. A build
failure, non-timeout execution failure, invalid output, integrity violation or
failed mandatory trajectory compliance audit sets the overall reward to zero.

The full contract is in the benchmark's [task instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/negative-constraint-retrieval/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/negative-constraint-retrieval/README.md),
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/negative-constraint-retrieval/task.toml).
