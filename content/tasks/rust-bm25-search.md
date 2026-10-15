# Rust BM25 Search

Build a complete Rust inverted index and BM25 searcher from 8,841,823 raw
MS MARCO Passage v1 documents. Reach a fixed Pyserini retrieval-quality floor,
then improve the balance of quality, query time, and persisted index size.

* **Task name**: `search-swe/rust-bm25-search`
* **Domain**: `lexical passage retrieval`
* **Primary focus**: `Rust indexing and BM25 search efficiency`
* **Primary metric**: `Quality-gated quality/time/index-size reward`
* **Tags**: `BM25`, `Rust`, `inverted-index`, `MS-MARCO`, `CPU`

## Runtime and requirements

* **Agent time budget**: up to `180 minutes`
* **Rust**: `1.85.1`, with locked generic crates available offline
* **Compute**: `4` CPU cores, `16 GiB` container memory, `64 GiB` working storage
* **GPU required**: `no`
* **Network**: `no`
* **Compilation limit**: `600 seconds`
* **Index-build limit**: `7,200 seconds`
* **Query limit**: `120 seconds` per request, including process startup for cold queries
* **Batch limits**: `3,600 seconds` each for warmup and the measured query batch
* **Verifier budget**: `18,000 seconds` overall

Implement the dictionary, postings, term frequencies, document lengths,
serialization, BM25 scoring, and retrieval in Rust. Generic crates for text
analysis, compression, parallelism, and I/O are allowed. Existing search
engines, wrappers around them, prebuilt indexes, neural retrieval, external
data, and query-specific answer tables are prohibited. BM25 parameters and
text analysis may be tuned.

The memory cap includes child processes and page cache. The verifier requires
Linux Landlock ABI 1 or newer and seccomp filters. Candidate commands run
without grading privileges; persistent IPC, kernel keyrings, extended-attribute
operations, and io_uring are blocked. During search, only the executable,
immutable index, and required system libraries are readable.

## Public input and output contract

### Inputs

* `/task/data/corpus.jsonl.gz` — all 8,841,823 passages as gzip JSONL with `docid`, `text`, and additional `title` metadata. Index only `text`; document IDs are decimal strings from `0` through `8841822`.
* `/task/data/warmup.jsonl.gz` — 54 public DL20 queries with `query_id` and `query` fields. These are disjoint from the evaluation queries and are not a scored development subset.
* `/app/submission` — a Rust source scaffold with pinned Cargo files; retrieval is deliberately unimplemented.
* `/task/docs` — toolchain and environment documentation. An optional three-passage smoke check is available at `/task/smoke.py`; it does not estimate full evaluation quality.

MS MARCO dataset terms apply. Evaluation queries and judgments are not supplied
to the agent.

### Outputs

Submit source under `/app/submission`: `Cargo.toml`, `Cargo.lock`, `src/main.rs`,
other `.rs` files under `src/`, and optionally `README.md`. Use `bm25-search` as
both package and executable name. The source limit is 1,000 regular files,
10 MiB total, and ten directory levels. Exclude links, workspaces, custom build
scripts, Cargo overrides, vendored dependencies, binaries, indexes, and generated
data. Keep compiler outputs elsewhere with `CARGO_TARGET_DIR=/app/build`.

Only the source directory transfers to the verifier. It recompiles the source,
then builds a fresh index in an empty directory:

~~~bash
cargo build --release --offline --locked --bin bm25-search -j 4
bm25-search index --corpus /task/data/corpus.jsonl.gz --index /work/index --threads 4
bm25-search search --index /work/index --threads 4
~~~

The compiled binary may occupy at most 100 MiB. All persistent retrieval state
must be in the index, limited to 16 GiB of logical file bytes including metadata.
The index may contain no links, special files, or extended attributes and becomes
read-only before search. The working area is limited to 64 GiB and 100,000 entries.

The search command is a persistent stdin/stdout JSONL process. For each request:

~~~json
{"query_id":"example","text":"example query"}
~~~

Emit exactly one matching response, followed by a newline and a flush:

~~~json
{"query_id":"example","results":[{"doc_id":"42","score":1.2}]}
~~~

Return zero to ten unique valid IDs with finite scores in descending order and
deterministic ties. Requests are limited to 4,096 UTF-8 bytes; responses including
the newline to 65,536 bytes. Send diagnostics to stderr, emit no startup message
on stdout, and exit within five seconds of stdin EOF. Sampled cold and warm
responses must match exactly, including scores.

## Evaluation

The verifier evaluates all 6,980 standard passage development queries, withheld
from the agent. MRR@10 is the average reciprocal rank of each query's first
positively judged result in the top ten, with zero for no hit. Every query must
receive a valid response.

The quality reference is Pyserini 1.4.0 with BM25 `k1=0.9`, `b=0.4`, its default
English analyzer, and text-only indexing without stored raw text, positions, or
document vectors. The exact MRR@10 floor is `3236243/17589600` (approximately
`0.18398616227770956`); it must not be rounded to `0.18` or `0.1840`.

A fresh process first runs the 54 warmup queries, then answers all evaluation
queries with one request outstanding. The verifier measures total batch wall time and all logical
index-file bytes. It rebuilds and measures the pinned reference in the same run.
Let `M`, `T`, and `D` denote candidate MRR@10, warm batch seconds, and index bytes,
with corresponding reference values `Mref`, `Tref`, and `Dref`:

~~~text
M >= Mref = 3236243/17589600
U = ((M/Mref) * (Tref/T) * (Dref/D))^(1/3)
reward = U / (1 + U)
~~~

Quality, time, and disk have equal weights. Reference-equivalent metrics earn
`0.5`; improvements earn credit only after all quality and resource gates pass.
Missing, invalid, timed-out, over-budget, or below-reference submissions receive
`0`. Reference or environment failures invalidate the run rather than measure
the candidate's ability.

Five fresh-process startup samples, warm latency percentiles, sequential QPS,
build time, and sampled search-process RSS are reported as diagnostics. They
receive no separate bonus. Startup measurements do not evict the OS file cache;
RSS excludes children and unmapped page cache, unlike the container memory cap.
QPS reflects concurrency-one throughput.

The full contract is in the benchmark's [task instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/ebe2e7a7a5592890a81ba10c557d364ba41e9d16/tasks/rust-bm25-search/instruction.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/ebe2e7a7a5592890a81ba10c557d364ba41e9d16/tasks/rust-bm25-search/task.toml).
