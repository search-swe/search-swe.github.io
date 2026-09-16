# Scientific-Paper Question Answering

Build an executable retrieval-augmented question answering system over 300 research-paper PDFs. For each scientific question, return a concise answer and identify the paper that supports it.

* **Task ID**: `search-swe/task-1-3`
* **Task type**: `create`
* **Domain**: `scientific question answering`
* **Primary focus**: `evidence-grounded RAG over PDFs`
* **Primary metric**: `LLMJudgeAccuracy`
* **Tags**: `PDF`, `RAG`, `scientific-documents`, `question-answering`, `evidence-attribution`

## Runtime and requirements

* **Agent time budget**: up to `120 minutes`
* **Python**: `3.12`
* **Compute**: `16` CPU cores, `64 GiB` memory, `100 GiB` storage
* **GPU required**: `no`
* **Network**: `restricted` — allowlisted OpenRouter and Jina resources only
* **Build limit**: `3,600 seconds`
* **Per-query limit**: `900 seconds`, with up to five query processes running concurrently

## Public input and output contract

### Inputs

* `/task/data/corpus` — 300 research-paper PDFs.
* `/task/data/validation/queries.jsonl` — 25 public development questions.
* `/task/data/validation/golden_answers.jsonl` — public reference answers and supporting document IDs.

### Outputs

The submission must provide executable `build.sh` and `run.sh` entry points under `/app`. Each query produces exactly one JSONL object containing its `query_id`, a non-empty `answer`, and one corpus document ID in `evidence`.

The index and any shared service must support up to five concurrent hidden-query invocations.

## Evaluation

The hidden split contains 25 held-out questions over the same PDF corpus. A question scores `1` only when the submitted evidence document matches the reference and an independent answer judge accepts the answer as semantically equivalent to the reference answer. `LLMJudgeAccuracy` is the mean of these binary outcomes:

```text
reward = mean(LLMJudgeAccuracy)
score = 100 * reward
```

Failed execution or structurally invalid output makes the entire submission invalid. A separate trajectory audit checks task and resource compliance and sets the final reward to `0` if it fails. Submission API access, answer-judge credentials, and trajectory-audit credentials are separate security domains.
