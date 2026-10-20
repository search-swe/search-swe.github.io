# Join-aware Table Retrieval

Retrieve the tables and column-level joins needed to answer a question from a catalog of relational schemas.

* **Task name**: `search-swe/join-aware-table-retrieval`
* **Domain**: `relational catalog search`
* **Primary focus**: `Complete table-and-join plan coverage`
* **Primary metric**: `Complete plan coverage at 5 tables and 6 joins`
* **Tags**: `table and join retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `120 minutes`
* **Compute**: `16` CPUs, `32 GiB` RAM, `100 GiB` storage; no GPU
* **Build limit**: `1,200 seconds`; persisted index at most `8 GiB`
* **Search startup limit**: `30 seconds`
* **Query limit**: `20 seconds` per request, including API calls

Optional OpenRouter/Jina resources are restricted to the documented allowlist.
Only `/app/submission` transfers; global installations and development processes
do not. The verifier rebuilds a fresh index and runs without grading privileges.

## Public input and output contract

### Inputs

* `/task/data/catalog.json` — 1,056 tables in 206 groups, 935 public relationships and 2,926 sample rows.
* `/task/data/validation/queries.jsonl` — ten public questions.
* `/task/data/validation/labels.jsonl` — acceptable table-and-join plans.

There are at most three sample rows per table; full databases and executable
SQL are not supplied. Ten evaluation questions are withheld from the agent.
Queries do not identify the target database.

### Outputs

Submit these scripts and their dependencies:

~~~bash
bash /app/submission/build.sh --corpus /task/data/catalog.json --index-dir /work/index
bash /app/submission/search.sh --index-dir /work/index
~~~

Search is a persistent stdin/stdout JSONL process. Emit `{"ready":true}` within
the startup deadline, then respond to requests such as:

~~~json
{"query_id":"example","question":"Which tables answer this question?"}
~~~

Return exactly `query_id`, `table_ids` and `joins`. Supply exactly five distinct
known table IDs and zero to six distinct joins. Each join has exactly
`left_table`, `left_column`, `right_table`, and `right_column`; it must be a
supplied catalog relationship whose endpoints are in the returned tables.

Each response must be newline-terminated, flushed and at most 65,536 bytes.
Send diagnostics to stderr. Query IDs are opaque and must be preserved.

## Evaluation

A question earns one only when the returned candidates contain all tables and
joins of at least one single acceptable plan. Extra valid candidates are allowed;
the whole candidate set need not be connected. Join direction and result order
do not affect grading. There is no partial-plan credit.

Reward is mean complete-plan coverage over ten questions. Invalid or late
responses score zero for the affected question; the process can be restarted for
later questions. Build failure or index-limit violations yield zero overall.
A synthetic warmup is unscored; failure triggers restart rather than automatic
loss of a scored question.

The full contract is in the benchmark's [task instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/join-aware-table-retrieval/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/join-aware-table-retrieval/README.md),
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/dab2e1e04904ff2731bf81849c65c639631c9499/tasks/join-aware-table-retrieval/task.toml).
