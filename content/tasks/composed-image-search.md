# Composed Image Search

Find gallery photographs matching a reference image plus a requested change.

* **Task name**: `search-swe/composed-image-search`
* **Domain**: `composed image retrieval`
* **Primary focus**: `Composed Image Search`
* **Primary metric**: `ComposedSourceQuality`
* **Tags**: `composed image retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `8` CPUs, `32 GiB` RAM, `100 GiB` storage; `1` GPU(s)

Build: 3,600 seconds. Up to 4,400 requests in two calls of at most 2,200, each allowed 14,400 seconds. Additional query-dependent visual inspection is limited to 100 candidate images per request. Use the supplied CLIP and only documented API resources.

## Public input and output contract

### Inputs

`/task/data/corpus/records.jsonl` maps image IDs to gallery paths. Local CLIP weights are at `/task/models/clip/`. Requests contain `query_id`, `reference_image_id`, `modification` and optional-content `shared_concept`. Public requests and labels are under `/task/data/validation/`.

### Outputs

Submit executable `/app/build.sh` and `/app/run.sh` and all supporting files under `/app`. The fresh verifier rebuilds the index and runs commands as a non-root user with code and inputs read-only. Honor the supplied index, output, `TMPDIR` and cache paths; the index parent is not writable.

~~~bash
/app/build.sh --corpus /task/data/corpus --index-dir /work/index
/app/run.sh --index-dir /work/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl
~~~

Return `query_id` and `results`, containing at most 50 distinct `image_id`/finite `score` pairs in nonincreasing score order. Exclude the reference image.

The index remains writable across repeated query calls.

## Evaluation

For CIRCO, quality is the mean of AP@5, AP@10, AP@25 and AP@50.
For CIRR, it is the mean of Recall@1, Recall@5, Recall@10 and Recall@50.
Queries are averaged within each source, then the two source scores receive
equal weight.

The source metrics retain their original positive labels. The shared gallery
and equal weighting of the two sources are this task's adaptation; unlabeled
alternatives are not treated as newly certified negatives.

### Reward mapping

The final reward uses the raw quality described above, with fixed reference
quality `b = 0.26812065144613684` and integer score anchor `a = 20` on the 0–100 scale:

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
that call. See [instruction.md](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/composed-image-search/instruction.md) and the verifier for the exact
task-specific validity checks.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/composed-image-search/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/composed-image-search/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/composed-image-search/task.toml)
for the complete contract at the synchronized benchmark revision.
