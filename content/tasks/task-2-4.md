# Agentic Search Optimization

Optimize a supplied ReAct retrieval starter over the BrowseComp-Plus corpus. Given a multi-constraint question, return exactly five distinct documents that best address its combined information need.

* **Task ID**: `search-swe/task-2-4`
* **Task type**: `optimize`
* **Domain**: `multi-constraint search`
* **Primary focus**: `agentic retrieval and document coverage`
* **Primary metric**: `Gold Recall@5`
* **Tags**: `BrowseComp-Plus`, `multi-constraint-retrieval`, `ReAct`, `agentic-search`, `BM25`

## Runtime and requirements

* **Agent time budget**: up to `120 minutes`
* **Python**: `3.12`
* **Compute**: `32` CPU cores, `128 GiB` memory, `200 GiB` storage
* **GPU required**: `no`
* **Network**: `restricted` — allowlisted OpenRouter and Jina resources only
* **Build limit**: `600 seconds`
* **Retrieval-round limit**: at most `20` search actions per query
* **Verifier execution**: one shared `15,300-second` budget includes build and scoring; hidden queries run up to five concurrently and have no individual timeout

## Public input and output contract

### Inputs

* `/task/data/corpus.jsonl` — the 100,195-document BrowseComp-Plus corpus.
* `/task/data/validation/queries.jsonl` — 20 public development questions.
* `/task/data/validation/qrels_gold.txt` — public gold document relevance labels.
* `/app/starter` — an editable ReAct loop backed by a SQLite FTS5/BM25 search service.

### Outputs

The submission must provide executable `build.sh` and `run.sh` entry points under `/app`. Each query produces one JSONL object with its `query_id` and exactly five distinct valid corpus IDs in `doc_ids`.

## Evaluation

The hidden split contains 20 held-out questions with private gold document labels. For each query, Gold Recall@5 is the fraction of its gold documents returned in the five selected IDs. Reward is the mean across hidden queries:

```text
GoldRecall@5(q) = |returned IDs intersect gold IDs| / |gold IDs|
reward = mean(GoldRecall@5)
score = 100 * reward
```

Execution and output validation are hard gates. This task uses deterministic scoring and has neither an answer judge nor a trajectory judge; the restrictions on hidden labels and unauthorized resources still apply.
