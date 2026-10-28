# Code Context Retrieval

Find compact source-code regions that provide the context needed to understand an issue in its specified repository snapshot.

* **Task name**: `search-swe/code-context-retrieval`
* **Domain**: `repository source retrieval`
* **Primary focus**: `Issue-to-code context localization`
* **Primary metric**: `Mean physical-line F1`
* **Tags**: `code context retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `120 minutes`
* **Compute**: `16` CPUs, `32 GiB` RAM, `100 GiB` storage; no GPU
* **Build limit**: `3,600 seconds`
* **Query limit**: `180 seconds` per question, evaluated sequentially

Use only the supplied snapshots and documented model/API resources. External
repository, issue and patch lookup is prohibited. This task retrieves reading
context; it does not require generating a patch.

## Public input and output contract

### Inputs

* `/task/data/repos/<snapshot_id>/` — 51,920 eligible text files across 30 pinned snapshots from 22 repositories.
* `/task/data/validation/queries.jsonl` — ten public issues with `query_id`, `snapshot_id` and `text`.
* `/task/data/validation/ground_truth.jsonl` — public source-region labels.

The 20 evaluation issues come from 15 repositories disjoint from the seven
public-example repositories. Each query must search only its named snapshot.

### Outputs

Submit executable entry points and all dependencies under `/app`:

~~~bash
/app/build.sh --corpus /task/data/repos --index-dir /app/index
/app/run.sh --index-dir /app/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl --top-k 5
~~~

The verifier rebuilds once and runs each query separately. Public validation
files are absent; submission code is read-only and runs without grading privileges.

~~~json
{"query_id":"example","regions":[{"path":"src/example.py","start":20,"end":55}]}
~~~

Use exactly these fields. Return at most five regions containing at most 500
distinct physical lines in total. Paths are relative to the specified snapshot;
line numbers are 1-based and inclusive. Overlapping lines are deduplicated and
region order does not matter. An empty list is valid.

## Evaluation

Predicted and reference regions become sets of `(path, line)` pairs. Each
question scores `2 * intersection / (predicted_lines + reference_lines)`;
reward is mean line F1 across all 20 questions, without baseline normalization
or a subjective relevance judge.

Missing, malformed, failed or timed-out query results contribute zero for that
query. Build or integrity failures prevent the submission from scoring.

The full contract is in the benchmark's [task instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/1d73c6f9c4a90ba922b7572d9395a6f40661bbb2/tasks/code-context-retrieval/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/1d73c6f9c4a90ba922b7572d9395a6f40661bbb2/tasks/code-context-retrieval/README.md),
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/1d73c6f9c4a90ba922b7572d9395a6f40661bbb2/tasks/code-context-retrieval/task.toml).
