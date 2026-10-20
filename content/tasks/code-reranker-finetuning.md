# Code Reranker Fine-tuning

Fine-tune a fixed BGE reranker to improve top-five code retrieval over shared BM25 and local embedding candidates.

* **Task name**: `search-swe/code-reranker-finetuning`
* **Domain**: `code retrieval`
* **Primary focus**: `Fixed-backbone cross-encoder fine-tuning`
* **Primary metric**: `Accuracy@5 gain normalized by candidate headroom`
* **Tags**: `reranker training`, `search-swe`

## Runtime and requirements

* **Agent budget**: `6 hours`
* **Compute**: `8` CPUs, `32 GiB` RAM, `100 GiB` storage; one GPU
* **Network**: disabled in both task phases; no task API keys
* **Verifier budget**: `10,800 seconds`
* **Phase limits**: `2,700 seconds` for first-stage retrieval; `7,200 seconds` for both rerankers

Only the weights of `BAAI/bge-reranker-base` may change. Preserve its architecture,
parameter names and shapes, configuration and tokenizer. Do not modify the frozen
embedding model or candidate policy, blend first-stage scores into logits, or
use outside training queries, labels, models or services.

## Public input and output contract

### Inputs

* `/task/data/corpus.jsonl` — 8,765 code documents with `_id`, `title` and `text`.
* `/task/data/train.jsonl` — 5,000 queries, each with one positive and an empty negative array.
* `/task/models/bge-reranker-base` — the supplied reranker backbone.
* `/task/models/bge-base-en-v1.5` — the frozen local embedding model for candidate mining.
* `/app/starter/train.sh` and `/app/starter/train.py` — editable training and export starter.

There is no public validation split; a local training holdout is allowed.
Evaluation uses 200 questions withheld from the agent.

### Outputs

Save a complete checkpoint under `/app/output/model`, including `config.json`,
`model.safetensors` and the original tokenizer files. Only this directory
transfers; submitted training scripts are not executed.

The verifier loads weights offline with remote code disabled and safetensors
required. Both rerankers use the tokenizer from the trusted backbone; the four
required submitted tokenizer files must still match byte for byte. Additional
submitted tokenizer metadata cannot change inference.

## Evaluation

The fixed first stage combines BM25 Top-200 and local BGE Top-200 using
equal-weight reciprocal rank fusion with `k=60`. Keep the entire deduplicated
union of 200–400 candidates. Both rerankers score the same full question/document
pairs with joint 512-token truncation and batch size 16; equal logits preserve
RRF order. The full contract fixes tokenization, pooling and branch tie-breaking.

Accuracy@5 is one when any relevant document appears among the first five
reranked candidates. Let `B` be baseline mean Accuracy@5, `S` the submitted mean,
and `C` the fraction of questions with a relevant document anywhere in the
fixed candidate union:

~~~text
reward = clamp((S - B) / (C - B), 0, 1), when C > B
reward = 0, otherwise
~~~

All 200 questions remain in every denominator, including first-stage misses.
`B` and `C` are recomputed in each evaluation, not taken from historical trials.
Invalid checkpoints, loading failures or phase timeouts yield zero. Scoring and
checkpoint checks are deterministic; there is no trajectory judge.

The full contract is in the benchmark's [task instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/code-reranker-finetuning/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/code-reranker-finetuning/README.md),
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/code-reranker-finetuning/task.toml).
