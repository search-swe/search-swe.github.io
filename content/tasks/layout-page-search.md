# Layout Page Search

Return a compact set of pages supporting a question within its specified document.

* **Task name**: `search-swe/layout-page-search`
* **Domain**: `document evidence pages`
* **Primary focus**: `Layout Page Search`
* **Primary metric**: `EvidencePageSetF1`
* **Tags**: `document evidence pages`, `search-swe`

## Runtime and requirements

* **Agent budget**: `6 hours`
* **Compute**: `8` CPUs, `32 GiB` RAM, `100 GiB` storage; `1` GPU(s)

Build: 3,600 seconds. Up to 600 requests in two calls, each allowed 2,700 seconds. Encoders remain fixed; an optional component may have at most five million trainable parameters and 45 minutes of training. At most 40 pages per request may undergo query-dependent token, region or learned pairwise scoring. No external APIs or data.

## Public input and output contract

### Inputs

Page records, rendered images and extracted Markdown are in `/task/data/corpus/`; local page/vision models are in `/task/models/`. Requests provide `query_id`, `doc_id`, `question`, `domain` and `language`. Public requests and labels are under `/task/data/validation/`.

### Outputs

Submit executable `/app/build.sh` and `/app/run.sh` and all supporting files under `/app`. The fresh verifier rebuilds the index and runs commands as a non-root user with code and inputs read-only. Honor the supplied index, output, `TMPDIR` and cache paths; the index parent is not writable.

~~~bash
/app/build.sh --corpus /task/data/corpus --index-dir /work/index
/app/run.sh --index-dir /work/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl
~~~

Return `query_id` and at most ten distinct `page_id`/finite `score` results from the specified document, in nonincreasing score order. No answer or bounding box is required.

The index remains writable across repeated query calls.

## Evaluation

For each question, compute set F1 between the returned pages and the complete
original evidence-page set. Quality is mean F1 over 515 held-out questions.
 Domain means are diagnostic.

The set metric penalizes both missing evidence and extra pages. Returning the
complete annotated evidence set achieves full per-query credit. It does not
measure answer accuracy or bounding-box localization.

### Reward mapping

The final reward uses the raw quality described above, with fixed reference
quality `b = 0.5734305608092015` and integer score anchor `a = 20` on the 0–100 scale:

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
that call. See [instruction.md](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/layout-page-search/instruction.md) and the verifier for the exact
task-specific validity checks.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/layout-page-search/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/layout-page-search/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/layout-page-search/task.toml)
for the complete contract at the synchronized benchmark revision.
