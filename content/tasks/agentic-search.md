# Agentic Search

Optimize a supplied ReAct retrieval starter over the BrowseComp-Plus corpus. Given a multi-constraint question, return exactly five distinct documents that best address its combined information need.

* **Task name**: `search-swe/agentic-search`
* **Domain**: `multi-constraint search`
* **Primary focus**: `agentic retrieval and document coverage`
* **Primary metric**: `Gold Recall@5`
* **Tags**: `BrowseComp-Plus`, `multi-constraint-retrieval`, `ReAct`, `agentic-search`, `BM25`

## Runtime and requirements

* **Agent time budget**: up to `120 minutes`
* **Python**: `3.12`
* **Compute**: `32` CPU cores, `16 GiB` memory, `200 GiB` storage
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

Execution and output validation are hard gates. Retrieval quality is scored deterministically, without an answer judge. A separate trajectory audit checks resource, retrieval-round and integrity constraints. A confirmed violation zeros the entire reward; missing trajectory or a failed audit invalidates the run and cannot produce positive credit. The complete verifier has a 17,100-second limit, including this audit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/561461e2619f269ffe3c8c44a541086eee17129f/tasks/agentic-search/instruction.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/561461e2619f269ffe3c8c44a541086eee17129f/tasks/agentic-search/task.toml)
for the complete contract at the reviewed benchmark revision.
