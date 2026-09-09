# Domain-specific Embedder Fine-tuning

Improve a code-retrieval embedding model using supplied training data. The task starts from the fixed `BAAI/bge-base-en-v1.5` backbone and evaluates whether the submitted checkpoint can place the relevant code document at rank one on unseen queries.

* **Task ID**: `search-swe/task-2-2`
* **Task type**: `optimize`
* **Domain**: `code retrieval`
* **Primary focus**: `embedding fine-tuning`
* **Primary metric**: `held-out Accuracy@1 improvement`
* **Tags**: `code-retrieval`, `embedding`, `fine-tuning`, `representation-learning`, `BGE`

## Runtime and requirements

* **Agent time budget**: up to `12 hours`
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

The verifier compares the original backbone and the submitted checkpoint using the same embedding and exact-search procedure on 200 hidden code-retrieval queries. The score is based on the submitted model's improvement in held-out `Accuracy@1`; hidden data and external resources are unavailable during development.
