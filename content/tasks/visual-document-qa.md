# Visual-Document Question Answering

Answer questions from long documents containing text, charts and tables, including unanswerable requests.

* **Task name**: `search-swe/visual-document-qa`
* **Domain**: `visual document QA`
* **Primary focus**: `Visual-Document Question Answering`
* **Primary metric**: `SourceMacroAnswerAccuracy`
* **Tags**: `visual document QA`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `8` CPUs, `32 GiB` RAM, `100 GiB` storage; `0` GPU(s)

Build: 14,400 seconds. Up to 2,500 requests in two calls of at most 1,250, each allowed 10,800 seconds. No GPU; only documented external resources are permitted.

## Public input and output contract

### Inputs

`/task/data/corpus/records.jsonl` maps documents to original PDFs, extracted page text and page counts. Requests have `query_id`, `doc_id` and `question`; PDFs may be rendered directly. Public requests and labels are under `/task/data/validation/`.

### Outputs

Submit executable `/app/build.sh` and `/app/run.sh` and all supporting files under `/app`. The fresh verifier rebuilds the index and runs commands as a non-root user with code and inputs read-only. Honor the supplied index, output, `TMPDIR` and cache paths; the index parent is not writable.

~~~bash
/app/build.sh --corpus /task/data/corpus --index-dir /work/index
/app/run.sh --index-dir /work/index --queries /path/to/queries.jsonl --output /path/to/results.jsonl
~~~

Return `query_id`, an `answer` string and supporting 1-based `pages`. Give the final answer and units directly; say when information is absent, using an empty page list when no evidence exists.

The index remains writable across repeated query calls.

## Evaluation

MMLongBench-Doc integer and float answers use the source answer-extraction
prompt and numeric comparators. Text, list and unanswerable answers use a
binary semantic judgment of the question, reference and full submitted answer.
Equivalent wording receives credit; incorrect entities or comparisons, missing
list items and unsupported claims do not. Each semantic judgment records a reason.
FinRAGBench-V retains its original binary answer judge. Trusted model calls use
`google/gemini-2.5-flash` through OpenRouter.

Average answers within each source, then give the two sources equal weight.

Evidence-page precision, recall and F1 are diagnostics, not part of the primary
answer score. Out-of-range source page references are excluded only from citation
diagnostics and do not remove the corresponding answer question.

### Reward mapping

The final reward uses the raw quality described above, with fixed reference
quality `b = 0.4350989780543772` and integer score anchor `a = 20` on the 0–100 scale:

```text
reward(q) = (a / 100) * q / b                             if 0 <= q <= b
            a / 100 + (1 - a / 100) * (q - b) / (1 - b)  if b < q <= 1
```

This maps raw quality 0, b and 1 to rewards 0, a / 100 and 1. Raw quality and
auxiliary diagnostics are reported separately. Harbor retains the 0–1 reward
precision; a displayed 0–100 score is rounded to one decimal place.
Correctness and trajectory-audit gates take precedence over this conversion.

### Validity and failure handling

The verifier checks execution, output structure, document/page validity and
stage limits. Completed valid rows survive query-call timeout; missing or invalid
rows receive zero. Other query-command failures invalidate that call.
Trusted answer-extraction or judge transport failures invalidate the measurement
rather than establishing a low baseline or model score.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/1d73c6f9c4a90ba922b7572d9395a6f40661bbb2/tasks/visual-document-qa/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/1d73c6f9c4a90ba922b7572d9395a6f40661bbb2/tasks/visual-document-qa/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/1d73c6f9c4a90ba922b7572d9395a6f40661bbb2/tasks/visual-document-qa/task.toml)
for the complete contract at the synchronized benchmark revision.
