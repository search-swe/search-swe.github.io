# ICSI Meeting Memory

Compress meeting history into a small readable memory, then retrieve notes and answer questions from those notes alone.

* **Task name**: `search-swe/icsi-meeting-memory`
* **Domain**: `compact meeting memory`
* **Primary focus**: `ICSI Meeting Memory`
* **Primary metric**: `EvidenceGroundedAnswerAccuracy`
* **Tags**: `compact meeting memory`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `8` CPUs, `8 GiB` RAM, `8 GiB` storage; `0` GPU(s)

No local model or GPU. Build: 300 seconds; all searches together: 150 seconds; all answers together: 1,800 seconds. Jina is allowed for preparation/search, while permitted generation is restricted to answering. Evaluation uses restricted API transports, not provider credentials in submitted processes.

## Public input and output contract

### Inputs

`/task/data/history.jsonl` covers 67 meetings. Five public questions, reference answers and evidence are under `/task/data/validation/`; 143 evaluation questions are withheld.

### Outputs

Deliver exactly four regular files: `/app/memory.json`, `build.sh`, `run.sh`, `answer.sh`. Memory must be readable JSON of at most 183,981 bytes; do not compress or encode dialogue. Scripts must be self-contained and corpus-independent.

~~~bash
/app/build.sh --memory /app/memory.json --output /path/to/index
/app/run.sh --index /path/to/index --question "$question" --output /path/to/memories.json
/app/answer.sh --question "$question" --memories /path/to/memories.json --output /path/to/answer.txt
~~~

Search returns at most ten strings from the indexed memory. Answer returns nonempty plain text of at most 2,000 characters, using at most two generation calls with at most 2,000 output tokens each. Build, search and answer have separate read boundaries: original transcripts do not transfer, search sees only the index, and answer sees only the current question and recalled notes.

## Evaluation

For each question, credit requires both an evidence hit and a correct answer.
A hit means that the retrieved notes faithfully preserve at least one relevant
reference fact, including valid summaries or paraphrases. Topic overlap alone
does not count. The answer judge checks the reference answer and required facts.
Evidence is judged without the answer, and the answer is judged without the
retrieved notes.

EvidenceGroundedAnswerAccuracy is the mean of these joint binary outcomes over
143 held-out questions.
Evidence and answer accuracy are also reported separately. Semantic grading
remains subject to model variability.

### Reward mapping

The final reward uses the raw quality described above, with fixed reference
quality `b = 0.06293706293706294` and integer score anchor `a = 20` on the 0–100 scale:

```text
reward(q) = (a / 100) * q / b                             if 0 <= q <= b
            a / 100 + (1 - a / 100) * (q - b) / (1 - b)  if b < q <= 1
```

This maps raw quality 0, b and 1 to rewards 0, a / 100 and 1. Raw quality and
auxiliary diagnostics are reported separately. Harbor retains the 0–1 reward
precision; a displayed 0–100 score is rounded to one decimal place.
Correctness and trajectory-audit gates take precedence over this conversion.

### Validity and failure handling

The four files, executable permissions, JSON syntax and size, index build,
script completion and output formats must satisfy the contract. A failed
submitted process or invalid output invalidates the submission. Empty retrieval
is an evidence miss. A malformed judge response or model-service failure
invalidates the measurement rather than establishing model quality.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/icsi-meeting-memory/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/icsi-meeting-memory/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/icsi-meeting-memory/task.toml)
for the complete contract at the synchronized benchmark revision.
