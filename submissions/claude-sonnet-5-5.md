# Community submission: claude-sonnet-5-5 (Claude Code harness)

**Equal-weight mean: 36.89 / 100** (provisional) over all 47 Search-SWE tasks (11 tasks scored 0, 4 perfect 100s).
Two tasks — `large-scale-formula-retrieval` and `rust-bm25-search` — remain pending maintainer reruns and are counted 0; the mean over the 45 resolved tasks is **38.52**.
Updated by the 2026-11-19 regrade rounds (PR comments 7000354737 + 7013193625): verifier-only `search-swe regrade` recovered 8 false/ pending zeros.

## Configuration
- **Model:** claude-sonnet-5-5, reasoning effort `max`.
- **Harness:** Claude Code (Harbor native agent route), served from Vertex AI through a host-side auth gateway. Google credentials never entered task containers.
- **Pipeline:** official `search-swe` CLI → Harbor with the separate per-task verifier. Equal task weight; score = native reward × 100.
- **Hardware:** single node, 8× NVIDIA H100 80GB HBM3, 208 vCPU, 1842 GiB RAM, NVIDIA driver 570.195.03, Docker 29.9.3. GPU tasks used a Container Device Interface (CDI) GPU request.

## Trajectories
Complete ATIF trajectories for all 47 tasks (45 have an independent verifier reward file; `incremental-vector-search` and `large-scale-formula-retrieval` lack one — see the dataset notes):
<https://huggingface.co/datasets/ubowang/search-swe-claude-sonnet-5-5>

Host paths are replaced with documented aliases; the Vertex project ID, gateway host/URL/port, and credential patterns are redacted.

## Notes for maintainers
- This run uses the **Claude Code** harness, not the **Codex** harness behind the current leaderboard entries (GPT-6 Luna, GPT-6.1 Terra), so it is not a strict apples-to-apples comparison.
- Harness is labeled **Claude Code** (not the Codex harness of current leaderboard entries); inclusion on the published board is at the maintainers' discretion via their publication pipeline.
- The Jina API outage on 2026-11-08/09 (UTC 21:22 → 01:15) did not affect this run; all scoring finished by 2026-11-08 14:17 UTC.

## Per-task scores

| task | score |
|---|---:|
| filtered-ann-retrieval | 100.00 |
| incremental-vector-search | 100.00 |
| instruction-following-embedding | 100.00 |
| sparse-retrieval-pruning | 100.00 |
| lightweight-query-retrieval | 87.64 |
| same-place-image-search | 81.76 |
| negative-constraint-retrieval | 80.00 |
| sketch-text-search | 59.48 |
| decision-model-training | 58.40 |
| chunqiu-temporal-retrieval | 55.89 |
| query-encoder-alignment | 52.50 |
| code-reranker-finetuning | 52.27 |
| visual-document-qa | 50.52 |
| join-aware-table-retrieval | 50.00 |
| reasoning-query-rewriting | 50.00 |
| composed-image-search | 48.94 |
| legal-stance-retrieval | 48.26 |
| spoken-query-search | 43.76 |
| narrative-clue-search | 41.27 |
| long-document-reranking | 40.00 |
| quantity-aware-retrieval | 39.89 |
| layout-page-search | 37.48 |
| khmer-embedding-training | 36.83 |
| code-embedding-finetuning | 33.50 |
| document-page-search | 32.67 |
| protein-text-bidirectional-retrieval | 32.58 |
| video-moment-search | 31.26 |
| agentic-search-vectorless | 29.92 |
| budgeted-candidate-reranking | 29.54 |
| code-context-retrieval | 26.93 |
| agentic-search | 25.58 |
| constrained-molecular-search | 22.93 |
| financial-report-qa | 19.21 |
| methodology-inspiration-retrieval | 15.31 |
| biomedical-graph-retrieval | 10.00 |
| multilingual-vector-postprocessing | 9.28 |
| budgeted-bimetric-retrieval | 0.00 |
| evolving-personal-memory | 0.00 |
| icsi-meeting-memory | 0.00 |
| large-scale-formula-retrieval | 0.00 |
| long-pdf-evidence | 0.00 |
| long-pdf-evidence-vectorless | 0.00 |
| memory-constrained-dense-retrieval | 0.00 |
| paper-metadata-retrieval | 0.00 |
| rust-bm25-search | 0.00 |
| scientific-paper-qa | 0.00 |
| training-error-tracing | 0.00 |
