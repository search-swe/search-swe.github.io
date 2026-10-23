# Financial-Report Evidence Retrieval

Locate original report passages supporting financial questions across a collection of annual reports.

* **Task name**: `search-swe/financial-report-qa`
* **Domain**: `financial evidence retrieval`
* **Primary focus**: `Financial-Report Evidence Retrieval`
* **Primary metric**: `EvidenceRecall@5`
* **Tags**: `financial evidence retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `8` CPUs, `32 GiB` RAM, `100 GiB` storage; `0` GPU(s)

Build: 1,800 seconds. Up to 8,000 requests in two calls of at most 4,000, each allowed 3,600 seconds. Only documented OpenRouter/Jina resources are available; no GPU.

## Public input and output contract

### Inputs

`/task/data/corpus/reports.jsonl` contains all 885 reports with `document_id` and full `text`. Queries have `query_id` and `question`, without a target report ID. Public requests and labels are under `/task/data/validation/`.

### Outputs

Submit executable `/app/build.sh` and `/app/run.sh` and all supporting files under `/app`. The fresh verifier rebuilds the index and runs commands as a non-root user with code and inputs read-only. Honor the supplied index, output, `TMPDIR` and cache paths; the index parent is not writable.

~~~bash
/app/build.sh --corpus /task/data/corpus --index-dir /work/index
/app/run.sh --index-dir /work/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl
~~~

Return exactly `query_id` and `spans`. Supply at most five ranked objects containing exactly `document_id`, `start`, `end`. Offsets count original Unicode characters, with inclusive start and exclusive end; each nonempty span is at most 512 characters. Empty results are permitted.

The index remains writable across repeated query calls.

## Evaluation

For each question, EvidenceRecall@5 is the number of covered reference
evidence units divided by the number of required units. Average these recalls
equally over the 4,236 held-out questions.

A fact is covered when the union of returned spans in the correct report
completely covers at least one verified location for that fact. Partial overlap
is insufficient. Multiple hits on the same fact do not add credit. Several
facts can fit in one span, and adjacent spans can jointly cover a fact.

Evidence locations are aligned to complete FinQA support text and table
context, with checks on numeric values and formatting. They are not inferred
by searching for the expected final answer number.

### Reward mapping

The final reward uses the raw quality described above, with fixed reference
quality `b = 0.6831800740440966` and integer score anchor `a = 20` on the 0–100 scale:

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
query IDs, span count, report IDs, Unicode offsets and the 512-character limit.
Duplicate output rows invalidate their query. Repeated evidence spans do not
increase recall. Completed valid JSONL rows remain usable after a query timeout;
missing or invalid query results score zero. A non-timeout query-command failure
invalidates that call.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/financial-report-qa/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/financial-report-qa/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/financial-report-qa/task.toml)
for the complete contract at the synchronized benchmark revision.
