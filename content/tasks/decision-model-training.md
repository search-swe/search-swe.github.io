# Decision Model Training

Train a compact local model to make structured categorical, Boolean and ordinal decisions on previously unseen task schemas.

* **Task name**: `search-swe/decision-model-training`
* **Domain**: `structured decision prediction`
* **Primary focus**: `Offline model training and fast batch inference`
* **Primary metric**: `Mean exact decision accuracy`
* **Tags**: `decision model training`, `search-swe`

## Runtime and requirements

* **Agent budget**: `6 hours`
* **Compute**: `16` CPUs, `32 GiB` RAM, `100 GiB` storage; one A100 40 GB GPU
* **Network**: disabled; no external APIs
* **Initialization limit**: `120 seconds`
* **Inference limit**: `240 seconds` for the complete evaluation batch

Use the supplied `Qwen3-0.6B` model and examples. Batch time includes all input,
inference and output work after initialization.

## Public input and output contract

### Inputs

* `/task/data/examples.jsonl` — 80,000 examples spanning 279 configurations.
* `/task/models/Qwen3-0.6B` — the supplied local backbone.
* `/task/docs` — runtime resources and the request/answer schema.

There is no public validation split. The verifier evaluates seven held-out
datasets with 600 requests each, totaling 4,200. Requests contain `request_id`,
`state` and `questions`. Training examples are absent during verification.

### Outputs

Put executable scripts, trained weights and runtime dependencies in
`/app/submission`; only this directory transfers:

~~~bash
/app/submission/start.sh --runtime-dir /path/to/runtime
/app/submission/run.sh --runtime-dir /path/to/runtime --requests /path/to/requests.jsonl --output /path/to/results.jsonl
~~~

Initialization may start a persistent service. Submission code is read-only and
runs as an unprivileged user; write runtime state to the supplied directory.

~~~json
{"request_id":"example","answers":{"question-id":"selected-label"}}
~~~

Answer every requested question exactly once. A `choice` answer is its exact
criterion-key string; `noul` requires a JSON Boolean; `score` requires a zero-based
integer index into its criterion list. Preserve request and question IDs.

## Evaluation

Scoring compares typed answers exactly. Reward is mean accuracy over the seven
equally sized held-out datasets, equivalent to overall accuracy here. There is
no baseline subtraction or model judge.

Missing or invalid answers, failed commands, timeouts and integrity violations
set the reward to zero.

The full contract is in the benchmark's [task instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/decision-model-training/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/decision-model-training/README.md),
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/decision-model-training/task.toml).
