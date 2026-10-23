# Code Embedding Fine-tuning

Improve a code-retrieval embedding model using supplied training data. The task starts from the fixed `BAAI/bge-base-en-v1.5` backbone and evaluates whether the submitted checkpoint can place the relevant code document at rank one on unseen queries.

* **Task name**: `search-swe/code-embedding-finetuning`
* **Domain**: `code retrieval`
* **Primary focus**: `embedding fine-tuning`
* **Primary metric**: `held-out Accuracy@1 improvement`
* **Tags**: `code-retrieval`, `embedding`, `fine-tuning`, `representation-learning`, `BGE`

## Runtime and requirements

* **Agent time budget**: up to `6 hours`
* **Python**: `3.12`
* **Compute**: `8` CPU cores, `32 GiB` memory, `100 GiB` storage
* **GPU required**: `yes`
* **Network**: `no`

## Public input and output contract

### Inputs

* `/task/data/corpus.jsonl` — the code document corpus.
* `/task/data/train.jsonl` — 5,000 supervised code-retrieval training examples.
* `/task/data/validation/` — 10 public validation queries and relevance labels.
* `/task/models/bge-base-en-v1.5` — the supplied backbone model.

### Outputs

The submission must contain a self-contained offline checkpoint at `/app/submission/model`. It must preserve the backbone architecture, parameter names, parameter shapes, and parameter count, and must be loadable locally by the standard Transformers interfaces.

## Evaluation

The verifier compares the original backbone and the submitted checkpoint using the same embedding and exact-search procedure on 200 hidden code-retrieval queries. The base reward is the nonnegative absolute improvement in held-out `Accuracy@1`, measured on the 0–1 accuracy scale:

```text
max(0, submitted Accuracy@1 - original-backbone Accuracy@1)
```

Final reward equals this gain when evaluation is valid and the trajectory audit passes. Invalid evaluation, timeouts, or a failed audit receive a reward of `0`.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/561461e2619f269ffe3c8c44a541086eee17129f/tasks/code-embedding-finetuning/instruction.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/561461e2619f269ffe3c8c44a541086eee17129f/tasks/code-embedding-finetuning/task.toml)
for the complete contract at the reviewed benchmark revision.
