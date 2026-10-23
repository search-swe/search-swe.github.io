# Filtered ANN Retrieval

Return exact filtered nearest neighbors from ten million tagged vectors under a 15 ms response deadline.

* **Task name**: `search-swe/filtered-ann-retrieval`
* **Domain**: `filtered vector search`
* **Primary focus**: `Filtered ANN Retrieval`
* **Primary metric**: `Mean per-query exact filtered Top-10 correctness and latency`
* **Tags**: `filtered vector search`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `8` CPUs, `16 GiB` RAM, `64 GiB` storage; `0` GPU(s)

Offline. Build: 600 seconds. Each query: 15 milliseconds including transmission and JSON response decoding. Build a valid L2 Faiss ANN index and actually use it; full-corpus brute force must not be the default. Index state must survive process termination and relocation.

## Public input and output contract

### Inputs

YFCC-10M: ten million 192-dimensional uint8 vectors in `/task/data/corpus/vectors.u8bin`, tags in `metadata.spmat`. Ten public queries and reference results are under `/task/data/validation/`; an additional small example is supplied.

### Outputs

~~~bash
/app/build.sh --vectors /task/data/corpus/vectors.u8bin --metadata /task/data/corpus/metadata.spmat --index-dir /path/to/index
/app/run.sh --index-dir /path/to/index --serve
~~~

Persist all state as regular files, including `index.faiss`. After loading, emit `{"status":"ready"}`. Requests contain string `query_id`, `vector`, `filter: {"all":[...]}` and k from 0 to 100. Return `query_id` and `results` containing integer `doc_id` values only. Return exactly min(k, matching count), ordered by original squared L2 then ID. All tags must match; boundary ties are accepted. Corpus paths and surviving build processes are unavailable at search time.

## Evaluation

Each of 25 hidden queries earns one only when its complete Top-10 is correct, timely and identical both before and after index relocation. Reward is their mean; partial recall earns no credit. Query failures remain local, while build, index, load or required audit failures zero the submission. The verifier requires the documented Landlock isolation support.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/filtered-ann-retrieval/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/filtered-ann-retrieval/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/filtered-ann-retrieval/task.toml)
for the complete contract at the synchronized benchmark revision.
