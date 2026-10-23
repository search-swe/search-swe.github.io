# Spoken-Query Document Search

Retrieve documents from noisy speech-recognition hypotheses without access to clean questions or audio.

* **Task name**: `search-swe/spoken-query-search`
* **Domain**: `speech uncertainty retrieval`
* **Primary focus**: `Spoken-Query Document Search`
* **Primary metric**: `SpokenMacroNDCG@10`
* **Tags**: `speech uncertainty retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `8` CPUs, `32 GiB` RAM, `100 GiB` storage; `1` GPU(s)

Build: 10,800 seconds. Up to 4,600 requests in four calls of at most 1,200, each allowed 1,350 seconds. Use at most five retrieval formulations and 50 further query-document reranking pairs per request. The recognizer is fixed; follow the documented model/API allowlist.

## Public input and output contract

### Inputs

Corpus JSONL files under `/task/data/corpus/` include IDs, domain, language, title and text. Local encoder: `/task/models/encoder/`. Requests have `query_id`, `domain`, `language`, `one_best` and scored `hypotheses`, including word confidence and spans. Public requests and labels are under `/task/data/validation/`.

### Outputs

Submit executable `/app/build.sh` and `/app/run.sh` and all supporting files under `/app`. The fresh verifier rebuilds the index and runs commands as a non-root user with code and inputs read-only. Honor the supplied index, output, `TMPDIR` and cache paths; the index parent is not writable.

~~~bash
/app/build.sh --corpus /task/data/corpus --index-dir /work/index
/app/run.sh --index-dir /work/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl
~~~

Return `query_id` and at most ten distinct `doc_id`/finite `score` results from the requested domain, in nonincreasing score order. Requests must be processed independently.

The completed index is read-only during retrieval.

## Evaluation

Compute original graded nDCG@10, average within each collection and acoustic
condition, then give the six collections and four conditions equal weight.


The split separates question families, but it is not an independently verified
speaker-disjoint benchmark. Per-condition and per-collection scores are reported
to show the effect of recognition noise.

### Reward mapping

The final reward uses the raw quality described above, with fixed reference
quality `b = 0.4530094614433184` and integer score anchor `a = 15` on the 0–100 scale:

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
that call. See [instruction.md](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/spoken-query-search/instruction.md) and the verifier for the exact
task-specific validity checks.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/spoken-query-search/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/spoken-query-search/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/spoken-query-search/task.toml)
for the complete contract at the synchronized benchmark revision.
