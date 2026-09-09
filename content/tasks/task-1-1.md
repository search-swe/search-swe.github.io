# Reasoning-intensive Query Rewriting

* **Task ID**: `search-swe/task-1-1`
* **Task type**: `create`
* **Domain**: `biology`
* **Primary focus**: `query rewriting`
* **Primary metric**: `Accuracy@3`
* **Tags**: `information-retrieval`, `query-rewriting`, `reasoning-intensive-retrieval`

Build an executable retrieval system over a 57,359-document biology corpus. The task primarily tests query rewriting and expansion: natural-language queries must be transformed to better align with relevant documents, even when they use different terminology or describe the underlying biological mechanism indirectly.

## Runtime and requirements

* **Agent time budget**: up to `120 minutes`
* **Python**: `3.12`
* **Compute**: `16` CPU cores, `32 GiB` memory, `100 GiB` storage
* **GPU required**: `no`
* **Network**: `restricted` — allowlisted resources only

## Public input and output contract

### Inputs

* `/task/data/corpus.jsonl` — 57,359 biology documents.
* `/task/data/validation/queries.jsonl` — three public development queries.
* `/task/data/validation/ground_truth.jsonl` — relevance labels for the public queries.

### Outputs

* JSONL retrieval results — top-3 ranked corpus documents for each input query.

The submission must provide executable `build.sh` and `run.sh` entry points under `/app`.

## Evaluation

A hidden query passes if at least one relevant document appears in its top three results.

**All hidden queries must pass for the submission to receive a score of `1`; otherwise the score is `0`.**

Submissions that fail the integrity or jailbreak checks also receive a score of `0`.
