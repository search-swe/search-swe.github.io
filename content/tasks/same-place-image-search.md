# Same-Place Image Search

Find photographs of the same physical place despite changes in viewpoint, scale and occlusion.

* **Task name**: `search-swe/same-place-image-search`
* **Domain**: `landmark retrieval`
* **Primary focus**: `Same-Place Image Search`
* **Primary metric**: `HardPlaceMacroNDCG@5`
* **Tags**: `landmark retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `8` CPUs, `32 GiB` RAM, `100 GiB` storage; `1` GPU(s)

Build: 3,600 seconds. Up to 140 requests in two calls of at most 70, each allowed 2,700 seconds. Keep the supplied CLIP encoder fixed. Additional pixel-based geometric verification may inspect at most 20 candidates per request. No external APIs.

## Public input and output contract

### Inputs

Gallery images and `records.jsonl` are under `/task/data/corpus/`; CLIP is under `/task/models/clip/`. Requests contain `query_id`, absolute query `image_path` and `exclude_image_ids`. Public requests and labels are under `/task/data/validation/`.

### Outputs

Submit executable `/app/build.sh` and `/app/run.sh` and all supporting files under `/app`. The fresh verifier rebuilds the index and runs commands as a non-root user with code and inputs read-only. Honor the supplied index, output, `TMPDIR` and cache paths; the index parent is not writable.

~~~bash
/app/build.sh --corpus /task/data/corpus --index-dir /work/index
/app/run.sh --index-dir /work/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl
~~~

Return `query_id` and at most five distinct eligible `image_id`/finite `score` pairs in nonincreasing order. Respect every exclusion and process requests independently.

The completed index is read-only during retrieval.

## Evaluation

Compute binary nDCG@5 against the original Hard positives after removing
excluded images. Average within Oxford and Paris, then give the two sources
equal weight.

This task uses the source Hard relevance protocol with a task-specific top-five
metric. Invalid or excluded returned IDs invalidate that query.

### Reward mapping

The final reward uses the raw quality described above, with fixed reference
quality `b = 0.5364309790092764` and integer score anchor `a = 15` on the 0–100 scale:

```text
reward(q) = (a / 100) * q / b                             if 0 <= q <= b
            a / 100 + (1 - a / 100) * (q - b) / (1 - b)  if b < q <= 1
```

This maps raw quality 0, b and 1 to rewards 0, a / 100 and 1. Raw quality and
auxiliary diagnostics are reported separately. Harbor retains the 0–1 reward
precision; a displayed 0–100 score is rounded to one decimal place.
Correctness and trajectory-audit gates take precedence over this conversion.

### Validity and failure handling

The verifier checks successful index construction, executable behavior,
query coverage, IDs, duplicate handling, finite scores and stage limits.
Completed valid JSONL rows remain usable after a query timeout; missing or
invalid rows score zero. A non-timeout query-command failure invalidates
that call. See [instruction.md](https://github.com/VectorSpaceLab/Search-SWE/blob/1d73c6f9c4a90ba922b7572d9395a6f40661bbb2/tasks/same-place-image-search/instruction.md) and the verifier for the exact
task-specific validity checks.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/1d73c6f9c4a90ba922b7572d9395a6f40661bbb2/tasks/same-place-image-search/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/1d73c6f9c4a90ba922b7572d9395a6f40661bbb2/tasks/same-place-image-search/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/1d73c6f9c4a90ba922b7572d9395a6f40661bbb2/tasks/same-place-image-search/task.toml)
for the complete contract at the synchronized benchmark revision.
