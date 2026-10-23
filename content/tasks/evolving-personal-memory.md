# Evolving Personal Memory

Answer questions from a person’s conversation history as it stood at a specified session.

* **Task name**: `search-swe/evolving-personal-memory`
* **Domain**: `conversation memory`
* **Primary focus**: `Evolving Personal Memory`
* **Primary metric**: `FAMA`
* **Tags**: `conversation memory`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `8` CPUs, `32 GiB` RAM, `100 GiB` storage; `0` GPU(s)

Build and each search call: 1,800 seconds; up to 300 questions per search call. Answers: 600 seconds each, at most eight concurrent processes and a shared 7,200-second answer phase. Follow the documented API allowlist.

## Public input and output contract

### Inputs

`/task/data/corpus/records.jsonl` contains 27,614 conversation records with person, session, date and text. Five public questions and criteria are under `/task/data/validation/`; 595 questions are held out.

### Outputs

Submit `/app/build.sh`, `/app/search.sh`, `/app/answer.sh` and supporting answer code under `/app/answer/`.

~~~bash
/app/build.sh --corpus /task/data/corpus --index-dir /work/index
/app/search.sh --index-dir /work/index --queries /path/to/queries.jsonl --output /path/to/retrievals.jsonl
/app/answer.sh --input /path/to/request.json --output /path/to/answer.json
~~~

Search receives `query_id`, `persona_id`, `cutoff_session`, `question`; return exactly `query_id` and up to 350 unique `record_ids` belonging to that person and no later than the cutoff. The verifier supplies their complete original text to an isolated answer process. Return exactly `query_id` and a nonempty `answer`. Answer code may read only the current request, reusable code and its own scratch; it cannot access corpus, index, other requests or stored conversation facts. Build/search use the supplied writable index; all stages run unprivileged with read-only code.

## Evaluation

Three independent judge configurations vote on each deduplicated criterion.
MPA measures passed memory criteria, FAA measures passed forgetting criteria,
and lambda is the fraction of criteria that concern forgetting.

```text
FAMA = max(0, MPA - lambda * (1 - FAA))
```

Final quality is mean FAMA over 595 held-out questions. Retrieval IDs assemble the answer request and are not a
separate retrieval-quality metric. Record IDs are not appended to judged answer
text.

### Reward mapping

The final reward uses the raw quality described above, with fixed reference
quality `b = 0.3712215103709065` and integer score anchor `a = 20` on the 0–100 scale:

```text
reward(q) = (a / 100) * q / b                             if 0 <= q <= b
            a / 100 + (1 - a / 100) * (q - b) / (1 - b)  if b < q <= 1
```

This maps raw quality 0, b and 1 to rewards 0, a / 100 and 1. Raw quality and
auxiliary diagnostics are reported separately. Harbor retains the 0–1 reward
precision; a displayed 0–100 score is rounded to one decimal place.
Correctness and trajectory-audit gates take precedence over this conversion.

### Validity and failure handling

Executable behavior, eligible record IDs, answer format, query coverage and
stage limits are checked. Build and search stop before answer execution.
Each answer process tree and workspace are removed before its role is reused.
Transport or malformed-response failures in trusted judging invalidate the
measurement and must not be interpreted as model quality.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/evolving-personal-memory/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/evolving-personal-memory/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/evolving-personal-memory/task.toml)
for the complete contract at the synchronized benchmark revision.
