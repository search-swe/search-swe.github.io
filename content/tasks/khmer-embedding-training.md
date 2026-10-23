# Khmer-to-English Embedding Training

Train a multilingual embedder and build retrieval from Khmer questions to English documents.

* **Task name**: `search-swe/khmer-embedding-training`
* **Domain**: `cross-language training`
* **Primary focus**: `Khmer-to-English Embedding Training`
* **Primary metric**: `Recall@100`
* **Tags**: `cross-language training`, `search-swe`

## Runtime and requirements

* **Agent budget**: `6 hours`
* **Compute**: `8` CPUs, `32 GiB` RAM, `100 GiB` storage; `1` GPU(s)

Offline, one A100 40 GiB. Fresh index build: 12 hours; each query invocation: 30 minutes. Preserve the supplied multilingual-E5 architecture, configuration, parameter shapes and tokenizer. The optional local generative model is development-only.

## Public input and output contract

### Inputs

`/task/data/corpus.parquet` provides `_id`, `title`, `text`; `/task/data/examples.jsonl` supplies only three question/answer examples. Models are `/task/models/multilingual-e5-large` and development-only `/task/models/Qwen3.5-9B`.

### Outputs

Save a complete offline checkpoint at `/app/submission/model/`, including `model.safetensors`, `config.json` and unchanged tokenizer files. Submit executable `/app/build.sh` and `/app/run.sh` with dependencies under `/app`.

~~~bash
/app/build.sh --corpus /task/data/corpus.parquet --index-dir /path/to/index
/app/run.sh --index-dir /path/to/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl
~~~

Build creates the initially absent index; prebuilt corpus indexes are not accepted. Retrieval sees a read-only index. Both stages run as separate non-root users with supplied scratch. Input rows contain `id`, `question`; output rows preserve input order and contain the same `id`, 100 unique zero-based Parquet row `indices` and finite descending `scores`, breaking ties by row number. Return all rows only if the corpus has fewer than 100.

## Evaluation

Recall@100 uses the source answer-token hit rule: a question succeeds when
at least one of the first 100 retrieved documents contains an accepted answer.
Recall@20 is diagnostic.

### Reward mapping

The final reward uses the raw quality described above, with fixed reference
quality `b = 0.595` and integer score anchor `a = 15` on the 0–100 scale:

```text
reward(q) = (a / 100) * q / b                             if 0 <= q <= b
            a / 100 + (1 - a / 100) * (q - b) / (1 - b)  if b < q <= 1
```

This maps raw quality 0, b and 1 to rewards 0, a / 100 and 1. Raw quality and
auxiliary diagnostics are reported separately. Harbor retains the 0–1 reward
precision; a displayed 0–100 score is rounded to one decimal place.
Correctness and trajectory-audit gates take precedence over this conversion.

### Validity and failure handling

The verifier checks local checkpoint loading, preserved architecture and
tokenizer, a successful fresh build, complete query coverage, 100 valid unique
positions per query, finite sorted scores and time limits. Hidden questions,
answer aliases, the generative model and judge credentials are unavailable
to submitted build and retrieval processes.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/khmer-embedding-training/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/khmer-embedding-training/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/khmer-embedding-training/task.toml)
for the complete contract at the synchronized benchmark revision.
