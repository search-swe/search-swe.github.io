# Community submission: claude-sonnet-5-5 (Claude Code harness)

**Equal-weight mean: 30.66 / 100** over all 47 Search-SWE tasks
(19 tasks scored 0, 4 perfect 100s).

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
- Integrating it into the board needs the publication pipeline to support a Claude Code model entry: `scripts/import_final_results.py` is currently pinned to Luna/Terra and reads Codex-native session receipts (`token_usage_record`, `task_started`/`task_complete`) for usage and cost, which Claude Code sessions do not emit in that schema.
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
| code-reranker-finetuning | 52.27 |
| visual-document-qa | 50.52 |
| join-aware-table-retrieval | 50.00 |
| reasoning-query-rewriting | 50.00 |
| composed-image-search | 48.94 |
| spoken-query-search | 43.76 |
| narrative-clue-search | 41.27 |
| long-document-reranking | 40.00 |
| layout-page-search | 37.48 |
| khmer-embedding-training | 36.83 |
| document-page-search | 32.67 |
| protein-text-bidirectional-retrieval | 32.58 |
| video-moment-search | 31.26 |
| agentic-search-vectorless | 29.92 |
| code-context-retrieval | 26.93 |
| agentic-search | 25.58 |
| financial-report-qa | 19.21 |
| methodology-inspiration-retrieval | 15.31 |
| multilingual-vector-postprocessing | 9.28 |
| biomedical-graph-retrieval | 0.00 |
| budgeted-bimetric-retrieval | 0.00 |
| budgeted-candidate-reranking | 0.00 |
| chunqiu-temporal-retrieval | 0.00 |
| code-embedding-finetuning | 0.00 |
| constrained-molecular-search | 0.00 |
| evolving-personal-memory | 0.00 |
| icsi-meeting-memory | 0.00 |
| large-scale-formula-retrieval | 0.00 |
| legal-stance-retrieval | 0.00 |
| long-pdf-evidence | 0.00 |
| long-pdf-evidence-vectorless | 0.00 |
| memory-constrained-dense-retrieval | 0.00 |
| paper-metadata-retrieval | 0.00 |
| quantity-aware-retrieval | 0.00 |
| query-encoder-alignment | 0.00 |
| rust-bm25-search | 0.00 |
| scientific-paper-qa | 0.00 |
| training-error-tracing | 0.00 |

