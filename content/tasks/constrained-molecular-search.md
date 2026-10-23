# Constrained Molecular Search

Recover the best feasible 10,000 compounds from a 12.4-million-combination library under changing property constraints.

* **Task name**: `search-swe/constrained-molecular-search`
* **Domain**: `molecular retrieval`
* **Primary focus**: `Constrained Molecular Search`
* **Primary metric**: `Macro mean Recall@10000; public proportional-budget Recall@279`
* **Tags**: `molecular retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `6 hours`
* **Compute**: `16` CPUs, `32 GiB` RAM, `64 GiB` storage; `1` GPU(s)

Offline, one A100 40 GB. Preparation/loading and recovery share 3,600 seconds; every complete response has a two-second deadline including GPU synchronization. Training is optional during development and forbidden in verification.

## Public input and output contract

### Inputs

`/task/library` contains 12,446,577 combinations; `/task/models` provides encoder, probe, factorizer and APEX weights. `/task/train` contains the labeled 1M library. Public development uses a separate 347,677-candidate pool and request budget 279. Final true docking scores/property tables are evaluator-only.

### Outputs

Submit `/app/submission/retriever.py`, dependencies and frozen artifacts. Export `prepare(library_dir, model_dir, index_dir)` and `Searcher(...).search(query)`. Requests contain `query_id`, one of five docking `target` values, inclusive property-bound `constraints` and `k`. Return a plain list of at most k distinct built-in integer combination IDs. Final k is 10,000. Honor supplied writable index/scratch paths; submission is read-only. Deterministic property computation and query-independent indexes are permitted, but no precomputed query answer sets.

## Evaluation

Reference sets are the truly feasible top 10,000 by docking score from the whole final library, with ordinal-ID tie breaks. Recall is intersection size divided by 10,000. Average 20 main configurations within each target, then five targets equally. Reward equals this Q, without baseline subtraction. Infeasible or missing results consume slots without credit. Diagnostic tiny/empty feasible sets are excluded. Invalid or late responses zero the query; preparation/resource/integrity failures zero the task.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/constrained-molecular-search/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/constrained-molecular-search/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/constrained-molecular-search/task.toml)
for the complete contract at the synchronized benchmark revision.
