# Sketch-and-Text Image Search

Find an artwork using a partial sketch together with a description of its complete scene.

* **Task name**: `search-swe/sketch-text-search`
* **Domain**: `sketch and text retrieval`
* **Primary focus**: `Sketch-and-Text Image Search`
* **Primary metric**: `LevelMacroRecallMRR@3`
* **Tags**: `sketch and text retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `6 hours`
* **Compute**: `8` CPUs, `32 GiB` RAM, `100 GiB` storage; `1` GPU(s)

Build: 3,600 seconds. Up to 1,260 requests in three calls of at most 420, each allowed 1,800 seconds. CLIP encoders remain fixed; scoring/fusion adaptation may use at most 30 minutes. Use supplied local resources only.

## Public input and output contract

### Inputs

Gallery records/images are under `/task/data/corpus/`, CLIP under `/task/models/clip/`, and training/validation query-label pairs under `/task/data/training/` and `/task/data/validation/`. Requests contain `query_id`, `description` and absolute `sketch_path`.

### Outputs

Submit executable `/app/build.sh` and `/app/run.sh` and all supporting files under `/app`. The fresh verifier rebuilds the index and runs commands as a non-root user with code and inputs read-only. Honor the supplied index, output, `TMPDIR` and cache paths; the index parent is not writable.

~~~bash
/app/build.sh --corpus /task/data/corpus --index-dir /work/index
/app/run.sh --index-dir /work/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl
~~~

Return `query_id` and at most ten distinct `image_id`/finite `score` results in nonincreasing score order. Process each pair independently; other requests are not context. Only the first three ranks affect quality.

The completed index is read-only during retrieval.

## Evaluation

Per-query quality is `0.5 × Recall@3 + 0.5 × MRR@3`.
Average within each of the three description levels, then give the levels
equal weight.

Up to ten results are accepted by the interface, but only the first three
affect the metric. The composite and partial-sketch input are task adaptations;
they do not reproduce the source paper's reported scores.

### Reward mapping

The final reward uses the raw quality described above, with fixed reference
quality `b = 0.32306763285024154` and integer score anchor `a = 15` on the 0–100 scale:

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
that call. See [instruction.md](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/sketch-text-search/instruction.md) and the verifier for the exact
task-specific validity checks.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/sketch-text-search/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/sketch-text-search/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/sketch-text-search/task.toml)
for the complete contract at the synchronized benchmark revision.
