# Multilingual Vector Postprocessing

Improve cross-language retrieval by applying one frozen language-aware function to existing vectors.

* **Task name**: `search-swe/multilingual-vector-postprocessing`
* **Domain**: `multilingual vector transforms`
* **Primary focus**: `Multilingual Vector Postprocessing`
* **Primary metric**: `clip((Q-B)/(U-B),0,1), with B and U frozen before agent evaluation`
* **Tags**: `multilingual vector transforms`, `search-swe`

## Runtime and requirements

* **Agent budget**: `6 hours`
* **Compute**: `16` CPUs, `16 GiB` RAM, `100 GiB` storage; `1` GPU(s)

Offline A100 40 GB. Preparation: 1,800 seconds; each complete query operation: 0.5 seconds. All learning/statistics must finish during development. Maintain 1,024 dimensions and apply the same function to documents and queries, independent of batch/order/history.

## Public input and output contract

### Inputs

Frozen multilingual-E5 vectors only: two million training and 200,000 probe vectors in ten languages. Full candidate pools contain 4,880 Belebele and 1,440 XQuAD documents; development has 1,830/1,308 queries. No raw text or encoder checkpoint is supplied.

### Outputs

Submit `/app/submission/transform.py`, frozen weights and dependencies. Implement `load(submission_dir)` and `transform(vectors, languages, state)`. Inputs are read-only FP32 B-by-1024 arrays, B=1–128. Return same-shaped finite real values with nonzero norms. No IDs or phase flag are given. The verifier normalizes results and performs complete-pool cosine ranking; no interaction reranker or verification-time learning is allowed.

## Evaluation

Evaluate 7,170 Belebele and 5,832 XQuAD held-out queries. Binary nDCG@20 averages queries within language, languages within dataset and both datasets equally. With `B=0.9127469497437668`, `U=0.9353486724891793`, reward is `clip((Q-B)/(U-B),0,1)`. U is the fixed quality reference from the original task calibration, not a claim that it was recalibrated under the new 16 GiB memory cap. Query errors/timeouts zero that query; preparation, resource, frozen-function or integrity violations zero the task. Extra speed gives no bonus.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/561461e2619f269ffe3c8c44a541086eee17129f/tasks/multilingual-vector-postprocessing/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/561461e2619f269ffe3c8c44a541086eee17129f/tasks/multilingual-vector-postprocessing/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/561461e2619f269ffe3c8c44a541086eee17129f/tasks/multilingual-vector-postprocessing/task.toml)
for the complete contract at the synchronized benchmark revision.
