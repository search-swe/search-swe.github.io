# Long-PDF Evidence Localization

Build an executable evidence-localization system over a single long PDF. Given a natural-language query, return the physical pages that best contain the relevant evidence.

* **Task ID**: `search-swe/task-1-4`
* **Task type**: `create`
* **Domain**: `in-document search`
* **Primary focus**: `page-level evidence localization in a long PDF`
* **Primary metric**: `Recall@5`
* **Tags**: `PDF`, `natural-language-search`, `long-document`, `localization`, `page-retrieval`

## Runtime and requirements

* **Agent time budget**: up to `120 minutes`
* **Python**: `3.12`
* **Compute**: `16` CPU cores, `64 GiB` memory, `100 GiB` storage
* **GPU required**: `no`
* **Network**: `restricted` — allowlisted OpenRouter and Jina resources only
* **Build limit**: `2,400 seconds`
* **Per-query limit**: `900 seconds`, with up to five concurrent invocations
* **Hidden-query run limit**: `1,800 seconds` shared across the complete query set

## Public input and output contract

### Inputs

* `/task/data/corpus` — one 2,043-page PDF of War and Peace.
* `/task/data/validation/queries.jsonl` — 10 public development queries, all referring to the same PDF.
* `/task/data/validation/golden_answers.jsonl` — reference physical pages and supporting excerpts.

### Outputs

The submission must provide executable `build.sh` and `run.sh` entry points under `/app`. For each query, it returns exactly five distinct ranked results. Every result contains a one-based physical PDF `page`, non-empty `evidence` text from that page, and a finite numeric `score`.

## Evaluation

The verifier rebuilds the system on the same PDF and evaluates 10 hidden queries. For each query, `Recall@5` is the fraction of all relevant evidence pages retrieved in the top five. Reward is the mean across all 10 queries, with failed or invalid queries contributing zero.

```text
reward = average(Recall@5)
score = 100 * reward
```

Page relevance is scored deterministically; no model judges answer correctness. Shared build/setup failure or a failed trajectory audit sets the final reward to `0`.
