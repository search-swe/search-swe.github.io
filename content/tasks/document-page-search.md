# Document Page Search

Find supporting pages across multilingual reports containing text, charts and tables.

* **Task name**: `search-swe/document-page-search`
* **Domain**: `multilingual page retrieval`
* **Primary focus**: `Document Page Search`
* **Primary metric**: `DomainMacroNDCG@10`
* **Tags**: `multilingual page retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `8` CPUs, `32 GiB` RAM, `100 GiB` storage; `1` GPU(s)

Build: 10,800 seconds. Up to 14,500 requests in two calls of at most 7,250; each call has 2,700 seconds. Supplied page and vision encoders and the documented API allowlist are available.

## Public input and output contract

### Inputs

`/task/data/corpus/records.jsonl` supplies page IDs, domains, document IDs, image paths and Markdown transcriptions. Models are under `/task/models/page-encoder/` and `/task/models/vision-backbone/`. Requests contain `query_id`, `question`, `domain` and `language`. Public requests and labels are under `/task/data/validation/`.

### Outputs

Submit executable `/app/build.sh` and `/app/run.sh` and all supporting files under `/app`. The fresh verifier rebuilds the index and runs commands as a non-root user with code and inputs read-only. Honor the supplied index, output, `TMPDIR` and cache paths; the index parent is not writable.

~~~bash
/app/build.sh --corpus /task/data/corpus --index-dir /work/index
/app/run.sh --index-dir /work/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl
~~~

Return `query_id` and at most ten distinct `page_id`/finite `score` results in nonincreasing score order, all from the requested domain. Search the whole domain, without a supplied target document. No answer or bounding box is required.

The index remains writable across repeated query calls.

## Evaluation

Compute nDCG@10 with the original graded relevance labels and linear gains.
Average query scores within each domain, then give the eight domains equal
weight. Missing or invalid query results remain in the denominator.

### Reward mapping

The final reward uses the raw quality described above, with fixed reference
quality `b = 0.5362634643282924` and integer score anchor `a = 20` on the 0–100 scale:

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
that call. See [instruction.md](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/document-page-search/instruction.md) and the verifier for the exact
task-specific validity checks.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/document-page-search/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/document-page-search/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/document-page-search/task.toml)
for the complete contract at the synchronized benchmark revision.
