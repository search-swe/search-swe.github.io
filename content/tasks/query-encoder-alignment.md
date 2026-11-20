# Query-side Encoder Alignment

Align a **0.6B query encoder** to fixed document vectors on one GPU, using at most **60% of the measured 4B reference runtime**. Improve top-one accuracy above a separately measured 0.6B ridge baseline without changing the document space. Reward normalizes that accuracy gain; runtime is a gate, measured over five fresh processes, whose candidate outputs must match exactly.

* **Task name**: `search-swe/query-encoder-alignment`
* **Domain**: `query encoder optimization`
* **Primary focus**: `Query adaptation to a frozen document space`
* **Primary metric**: `Accuracy@1 error reduction above frozen 0.6B ridge, after runtime gate`
* **Tags**: `query encoder optimization`, `search-swe`

## Runtime and requirements

* **Agent budget**: `6 hours`
* **Compute**: `8` CPUs, `32 GiB` RAM, `100 GiB` storage; `1` GPU(s)

Use Qwen3-Embedding-0.6B as the basis. Development has allowlisted egress, but external retrieval, reranking, embedding, generation and answer services are prohibited. Final inference is offline. Each reference and candidate invocation has a 1,800-second limit. The overall verifier budget is 32,100 seconds, including up to 20,400 seconds for task-specific verification and 11,100 seconds for the integrity audit.

Final query inference must use the supplied `Qwen3-Embedding-0.6B` encoder or a legitimately adapted derivative, and its outputs must contribute to candidate selection or ranking. Development-only use, loading unused weights or discarding encoder outputs does not satisfy this requirement. Lexical, structural and corpus-copy features may supplement the required encoder, but cannot replace it.

## Public input and output contract

### Inputs

8,674 fixed document vectors in `/task/data/doc.npy` and corresponding corpus rows; 100 public query/label pairs under `/task/data/validation/`. `/app/quality_reference` supplies fixed 0.6B centered-ridge quality baseline. The 4B starter/model may provide public-input teacher signals and timing comparisons, but is inaccessible to final inference.

### Outputs

Submit all custom runtime files under `/app/submission`, including:

~~~bash
/app/submission/run.sh --doc-vectors /task/data/doc.npy --queries /path/to/queries.jsonl --output /path/to/results.jsonl --top-k 1
~~~

Preserve vector bytes and row order. Return one valid `doc_id`/finite `score` result per `query_id`, in input order. Exclude same-ID documents and full-text matches after NFKC, whitespace collapse and casefold. Ties follow corpus order. All five fresh-process candidate runs must produce byte-identical output. Use supplied scratch and leave no background processes.

## Evaluation

A0 is the measured hidden Accuracy@1 of the fixed 0.6B centered-ridge baseline, fit only on public corpus text/vector pairs. Reward is `clip((Accuracy@1-A0)/(1-A0),0,1)` provided candidate runtime is at most 60% of the separate measured 4B time reference.

Timing includes startup, imports, loading, encoding, retrieval, filtering, output and exit. The verifier fits the pinned quality baseline on public pairs, measures it on the same hidden queries and hardware as the candidate, and runs five time-reference and candidate pairs. The median wall times determine the runtime gate. All candidate outputs must be byte-identical and the time reference must remain deterministic. The 4B accuracy is diagnostic.

Candidate format or vector-integrity violations, candidate invocation timeouts, and a completed integrity rejection earn zero. Reference failure, A0=1, and integrity-audit timeouts or service failures invalidate the measurement.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/bec6079118beb85e1b46ad6d9de6b96e6b22ea4e/tasks/query-encoder-alignment/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/bec6079118beb85e1b46ad6d9de6b96e6b22ea4e/tasks/query-encoder-alignment/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/bec6079118beb85e1b46ad6d9de6b96e6b22ea4e/tasks/query-encoder-alignment/task.toml)
for the complete contract at the synchronized benchmark revision.
