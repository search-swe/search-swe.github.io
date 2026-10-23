# Narrative-Clue Search

Find a remembered work from a long description containing scattered clues and uncertain recollections.

* **Task name**: `search-swe/narrative-clue-search`
* **Domain**: `narrative retrieval`
* **Primary focus**: `Narrative-Clue Search`
* **Primary metric**: `QueryMeanNDCG@10`
* **Tags**: `narrative retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `8` CPUs, `32 GiB` RAM, `100 GiB` storage; `0` GPU(s)

Build: 3,600 seconds. Up to 450 requests in two calls of at most 225; each call has 2,700 seconds. Only the documented OpenRouter/Jina APIs may supplement local computation.

## Public input and output contract

### Inputs

`/task/data/corpus/records.jsonl` contains `doc_id`, `title` and article `text`. Queries contain `query_id` and `question`. Public sentence annotations also appear in `/task/data/training/sentence_labels.jsonl`. Public requests and labels are under `/task/data/validation/`.

### Outputs

Submit executable `/app/build.sh` and `/app/run.sh` and all supporting files under `/app`. The fresh verifier rebuilds the index and runs commands as a non-root user with code and inputs read-only. Honor the supplied index, output, `TMPDIR` and cache paths; the index parent is not writable.

~~~bash
/app/build.sh --corpus /task/data/corpus --index-dir /work/index
/app/run.sh --index-dir /work/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl
~~~

Return `query_id` and at most ten distinct `doc_id`/finite `score` results, ordered by nonincreasing score.

The index remains writable across repeated query calls.

## Evaluation

Compute nDCG@10 using complete original qrels, then average equally over
445 held-out questions.

Four category means based on original human uncertainty annotations and a fixed
median narrative length are diagnostics. They do not change query weights or
introduce model-generated categories.

### Reward mapping

The final reward uses the raw quality described above, with fixed reference
quality `b = 0.40178618363049623` and integer score anchor `a = 20` on the 0–100 scale:

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
that call. See [instruction.md](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/narrative-clue-search/instruction.md) and the verifier for the exact
task-specific validity checks.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/narrative-clue-search/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/narrative-clue-search/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/narrative-clue-search/task.toml)
for the complete contract at the synchronized benchmark revision.
