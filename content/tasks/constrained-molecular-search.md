# Constrained Molecular Search

Find 10,000 high-scoring feasible compounds in a **12.4-million-combination library**, within a **two-second median response time on one GPU**. Property constraints and docking targets change by request; true final docking scores are hidden. Reward is recall of the truly best feasible compounds, averaged equally across targets. Infeasible results waste return slots.

* **Task name**: `search-swe/constrained-molecular-search`
* **Domain**: `molecular retrieval`
* **Primary focus**: `Feasible compound retrieval across changing constraints`
* **Primary metric**: `Mean Recall@10000, equally weighted across targets`
* **Tags**: `molecular retrieval`, `search-swe`

## Runtime and requirements

* **Agent budget**: `6 hours`
* **Compute**: `16` CPUs, `32 GiB` RAM, `64 GiB` storage; `1` GPU(s)

Offline, one GPU. Preparation/loading and recovery share 3,600 seconds; every query must meet a two-second median complete-response time across five measurements, with a three-second execution cap per measurement, including GPU synchronization. Training is optional during development and forbidden in verification.

See the [Linux cgroup requirements](https://github.com/VectorSpaceLab/Search-SWE/blob/main/docs/evaluation/runtime.md#linux-cgroups) for the resource evidence required on cgroup v1 and v2 hosts.

## Public input and output contract

### Inputs

`/task/library` contains 12,446,577 combinations; `/task/models` provides encoder, probe, factorizer and APEX weights. `/task/train` contains the labeled 1M library. Public development uses a separate 347,677-candidate pool and request budget 279. Final true docking scores/property tables are evaluator-only.

### Outputs

Submit `/app/submission/retriever.py`, dependencies and frozen artifacts. Export `prepare(library_dir, model_dir, index_dir)` and `Searcher(...).search(query)`. Requests contain `query_id`, one of five docking `target` values, inclusive property-bound `constraints` and `k`. Return a plain list of at most k distinct built-in integer combination IDs. Final k is 10,000.  Submission is read-only. Deterministic property computation and query-independent indexes are permitted, but no precomputed query answer sets.

## Evaluation

Prepare once, then run five complete passes, each in a fresh Searcher process with cleared scratch. Prepared artifacts become read-only after preparation; query-time writes use `TMPDIR`. All five measurements must return valid ID lists; passing requests use mean recall across the five measurements.

Reference sets are the truly feasible top 10,000 by docking score from the whole final library, with ordinal-ID tie breaks. Recall is intersection size divided by 10,000. Average 20 main configurations within each target, then five targets equally. Reward equals this Q, without baseline subtraction. Infeasible or missing results consume slots without credit. Diagnostic tiny/empty feasible sets are excluded. Invalid or late responses zero the query; preparation/resource/integrity failures zero the task.

The integrity audit runs independently three times. Its reported value is the mean of the three binary decisions; all three must accept for a positive task reward. Missing, failed or malformed audit evidence invalidates the measurement.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/constrained-molecular-search/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/constrained-molecular-search/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/ed7544f4aeb1fe8a072edc77ece1f2f4a742bfda/tasks/constrained-molecular-search/task.toml)
for the complete contract at the synchronized benchmark revision.
