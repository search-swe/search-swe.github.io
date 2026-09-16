# Long-PDF Evidence Localization

Build an executable evidence-localization system over long PDFs. Given a natural-language query and a target PDF, return the physical pages that best contain the relevant evidence.

* **Task ID**: `search-swe/task-1-4`
* **Task type**: `create`
* **Domain**: `in-document search`
* **Primary focus**: `page-level evidence localization in long PDFs`
* **Primary metric**: `Recall@5`
* **Tags**: `PDF`, `natural-language-search`, `long-document`, `localization`, `page-retrieval`

## Runtime and requirements

* **Agent time budget**: up to `120 minutes`
* **Python**: `3.12`
* **Compute**: `16` CPU cores, `64 GiB` memory, `100 GiB` storage
* **GPU required**: `no`
* **Network**: `restricted` — allowlisted OpenRouter and Jina resources only
* **Build limit**: `2,400 seconds`
* **Hidden-query run limit**: `1,800 seconds` for the complete query set

## Public input and output contract

### Inputs

* `/task/data/corpus` — six public development PDFs.
* `/task/data/validation/queries.jsonl` — 30 public development queries.
* `/task/data/validation/ground_truth.jsonl` — public page-level relevance labels.

### Outputs

The submission must provide executable `build.sh` and `run.sh` entry points under `/app`. For each query, it returns exactly five distinct ranked results. Every result contains a one-based physical PDF `page`, non-empty `evidence` text from that page, and a finite numeric `score`.

## Evaluation

The verifier rebuilds the system on six different held-out PDFs and evaluates 30 private queries. For each query, `Recall@5` is the fraction of relevant evidence pages appearing among the five returned pages. The final quality score is the mean across hidden queries:

```text
score = 100 * average(Recall@5)
```

Page relevance is scored deterministically; no model judges answer correctness. Invalid execution or output receives zero, and a separate trajectory audit can set the final reward to `0` for noncompliance.
