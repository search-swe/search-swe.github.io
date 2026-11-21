# Review response (PR #3, 2026-11-18)

## Evidence recovered (first priority)
Both datasets now carry `provenance_index.json` (per task: selected trial id, coding start/end + hours, verifier start/end, exit/exception, reward, trajectory sha256) and `evidence/<task>/` with redacted `result.json`, `config.json`, `reward.json`, `reward-details.json` and judge process/verdict logs for the flagged tasks.
HF commits: sonnet `4a3c2e22d672b90ea395f1943e39fa5910392b64`, argon `fedf0968e80cc5e783a57155a3ef57d98aa7fcfc`.

## Key dispositions
- **Argon 429-kept (retain, now evidence-backed):** instruction-following-embedding (100), code-reranker-finetuning (47.73), narrative-clue-search (16.70). provenance_index shows `coding_finished` **before** `verifier_started` on a complete submission, so the trailing 429 was post-completion — original valid scores kept, not replaced by the re-solve attempt.
- **Retain (reconciled):** sonnet `paper-metadata-retrieval` (judge_succeeded=True → genuine 0); argon `same-place-image-search` (judge verdict "yes"; 0 = incomplete submission, features.py only).
- **Pending — verifier-only re-eval (no verify-only mode in run_task.py; needs maintainer tooling):** sonnet `legal-stance-retrieval`, `quantity-aware-retrieval` (judge_succeeded=False, coding valid + submission preserved); sonnet biomedical/chunqiu/icsi/code-embedding/query-encoder and argon query-encoder (judge verdict + exit + reward-details supplied in evidence/ to distinguish confirmed-reject vs verification-failure).
- **Pending — coding rerun:** sonnet `rust-bm25-search` (confirmed ECONNRESET; re-solve needs the Claude-Code-via-Vertex-gateway route re-applied; original record kept); argon `large-scale-formula-retrieval` (no valid run — cgroup platform limit; **marked pending**, not 0).

## Provisional means (Formula pending)
- gemini-4-argon: **32.61** (47-task, Formula=0) / **33.32** (46 resolved). Provisional.
- claude-sonnet-5-5: **30.66** / **31.33**. Provisional.
Final means will be recomputed once Formula and the verifier-only re-evals resolve.

## Doc fixes
Removed the duplicate Formula row in the Argon README and marked Formula pending; updated the Sonnet note (board inclusion at maintainers' discretion; dropped the outdated Codex-pinned claim). Argon `high` effort accepted; tokens/costs remain `unknown`.

Per-item records with evidence links: `review-response-2026-11-18.json`.
