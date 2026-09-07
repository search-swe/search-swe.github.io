# Sparse Retrieval Index Repair

Repair a learned sparse search index with bloated postings, inconsistent vocabulary mappings, or unsafe pruning. Restore retrieval correctness first, then reduce index size and query cost while preserving search quality.

The task uses fixed sparse representations derived from MS MARCO Passage and a frozen SPLADE encoder. The engineering focus is the consistency of vocabulary IDs, postings, and impact metadata, together with safe execution of pruned retrieval.

* **Task ID**: `search-swe/task-3-1`
* **Task type**: `repair`
* **Domain**: `learned sparse retrieval`
* **Primary focus**: `postings bloat, vocabulary compression, and safe pruning`
* **Primary metric**: `Recall@100 / NDCG@10 with correctness and cost gates`
* **Tags**: `sparse-retrieval`, `inverted-index`, `SPLADE`, `term-remapping`, `safe-pruning`

## Search-system challenge

A term remap that is not propagated to queries and postings can send a query to the wrong list. Stale impact upper bounds can cause WAND or Block-Max execution to skip relevant documents. Long postings for frequent expansion terms also increase traversal cost and tail latency.

The agent must repair the relationships among document vectors, query vectors, the term dictionary, postings, and block-level metadata. Vocabulary compression and pruning must preserve useful evidence for head-heavy, tail-heavy, mixed, and adversarial boundary queries.

The sparse scoring definition remains fixed:

~~~text
score(q, d) = Σ(t ∈ q ∩ d) q_weight(t) × d_weight(t)
~~~

## Runtime and requirements

The following environment is proposed in the draft setting and remains subject to calibration.

* **Python**: `3.12`
* **Compute**: `8` vCPU, `32 GB` RAM, `80 GB` local SSD
* **GPU required**: `no`
* **Network**: `no` — no public network, DNS, or runtime package installation
* **Dependencies**: preinstalled, pinned local packages
* **Agent time budget**: to be finalized

The sparse transformer is used during data preparation. The agent must not retrain, replace, or rerun the encoder.

## Public input and output contract

### Inputs

The planned task bundle contains starter code, a faulty inverted index, public sparse vectors, the term dictionary, postings, impact-block metadata, public queries and relevance labels, public statistics, and a public exact reference.

The draft data configuration specifies:

* 1,000,000 passages and approximately 30K–32K opaque term IDs.
* Frozen `naver/splade-cocondenser-ensembledistil` sparse representations.
* Blocks of 128 documents, first-stage candidates at Top-100, and Top-10 returned results.
* 200 public unique queries and 10,000 public requests.
* 1,000 disjoint hidden unique queries and 20,000 hidden requests, held by the verifier.

Document, query, and term IDs are randomized. Hidden vectors, relevance labels, frequency traces, and evaluator internals are unavailable to the agent.

### Outputs

Produce a loadable repaired index and reproducible build and query entry points:

~~~bash
/app/build.sh --input STARTER_INDEX --output SUBMISSION_INDEX
/app/run.sh --index SUBMISSION_INDEX --input QUERIES_JSONL --output RESULTS_JSONL
~~~

A query contains an opaque query ID, weighted term IDs, and the requested result count:

~~~json
{
  "query_id": "q_opaque_001",
  "terms": [
    {"term_id": "t_0012", "weight": 1.10},
    {"term_id": "t_8120", "weight": 0.48}
  ],
  "top_k": 10
}
~~~

Return one record per query, with unique document IDs and descending sparse scores. This abbreviated example shows the record format:

~~~json
{
  "query_id": "q_opaque_001",
  "items": [
    {"doc_id": "d_opaque_123", "score": 1.842}
  ]
}
~~~

## Evaluation

Evaluation prioritizes correctness, then retrieval quality, then efficiency. Numeric targets below are proposed draft thresholds, not finalized benchmark gates.

### Correctness first

Invalid term remaps, corrupt or duplicate postings, wrong document IDs, non-finite scores, and unsafe block skips must all be eliminated. In correctness mode with pruning disabled, Top-100 must match the exact sparse reference. Every block upper bound must remain safe.

Pruning must remain enabled for the final performance evaluation. Disabling it is only a correctness diagnostic.

### Quality safeguards

Proposed quality floors relative to the unpruned reference are:

* Mean Recall@100: at least 95% of the reference.
* Mean NDCG@10: at least 90% of the reference.
* Head-heavy and adversarial NDCG@10: at least 85% of their reference scores.
* Tail-heavy NDCG@10: at least 90% of its reference score.

### Postings and execution cost

Proposed postings-balance targets are a maximum-to-median length ratio no greater than 50, a p99-to-median ratio no greater than 12, Gini no greater than 0.70, and top-1% list postings mass no greater than 0.18. These may be replaced by relative improvement targets after data calibration.

Proposed execution and storage limits are:

* p95 latency at most 150 ms; p99 latency at most 350 ms.
* Mean postings visited at most 60% of the unpruned reference; p95 at most 70%.
* Total index size at most 75% of the unpruned index.
* Alias expansion factor at most 2.0.
* Peak temporary disk use at most twice the final index size.

The evaluator counts term fan-out, repeated postings visits, score evaluations, block skips, latency, and the bytes used by postings, dictionary, impact metadata, and aliases.

### Final comparison

After correctness and quality gates, the draft prioritizes better postings balance among submissions with a quality gap no larger than 1%. Similar balance is resolved by postings visits, p99 latency, and index size; remaining ties consider peak memory, build time, and stability.

## Constraints

* Keep the sparse encoder and mathematical score definition fixed.
* Keep remapped term IDs synchronized across documents, queries, dictionaries, postings, and impact metadata.
* Do not remove all frequent terms, return empty results, or disable pruning to evade the quality and cost objectives.
* Count alias expansion and repeated visits in query costs.
* Do not access hidden data, alter the evaluator or reference, or hardcode query-to-document answers.
* Do not falsify resource counters, postings statistics, or retrieval scores.

Global, per-term, per-document, and per-query pruning, safe inverted-index execution strategies, and limited alias splitting remain design choices for the agent.
