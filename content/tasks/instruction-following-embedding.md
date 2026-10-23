# Instruction-following Embedding

Adapt query embeddings to changed relevance instructions while retaining a fixed document-vector space.

* **Task name**: `search-swe/instruction-following-embedding`
* **Domain**: `compact query adapters`
* **Primary focus**: `Instruction-following Embedding`
* **Primary metric**: `Harmonic mean of three positive subset p-MRR values (otherwise zero), gated by six nDCG@10 checks`
* **Tags**: `compact query adapters`, `search-swe`

## Runtime and requirements

* **Agent budget**: `2 hours`
* **Compute**: `16` CPUs, `32 GiB` RAM, `32 GiB` storage; `1` GPU(s)

Offline A100 40 GB. Deployment increment: 512 KiB (524,288 bytes) for all JSON/safetensors. Final serving uses one complete E5 forward per query, fixed tokenizer/input format and mean pooling. Preparation: 3,600 seconds; each instruction version: one second including 1,000-candidate scoring.

## Public input and output contract

### Inputs

E5-large-v2, 1,717 training records, 98,312 corpus passages and 20 public paired-instruction groups are supplied; 84 groups are held out. Public group labels are validation-only: no gradient training, teacher targets or label-aware mining. Corpus text may independently serve as unlabeled anchors.

### Outputs

Submit `/app/submission/submission.json` with exactly `query_checkpoint` and `document_checkpoint`; document must be `base`. Query may be `base` or a safe relative standard PEFT LoRA directory containing configuration and safetensors. No custom code, tokenizer, output transform or document cache is deployed. Training may use larger intermediate models, but final weights must fit the payload and fixed serving rules.

Serving uses `query: {query}
Instruction: {instruction}` and `passage: {text}`, right truncation to 512 tokens, FP32 mean pooling over nonpadding tokens and L2 normalization. Document encoding stays unchanged; query workers cannot inspect candidates or rankings.

## Evaluation

For changed documents with original/revised ranks x/y, p-MRR uses `y/x-1` when x>=y, otherwise `1-x/y`. Average documents, queries and then obtain each subset value P. H is the harmonic mean of the three positive subset values, or zero if any is nonpositive.

Six subset/version nDCG@10 gates require at least 90% of frozen query-only reference quality. After those gates, reward is `clip(H/0.07054277758767746,0,1)` with B=0. Arithmetic macro p-MRR is diagnostic. Failure of either instruction version zeros the group; invalid payload, preparation/resource or audit failure zeros the task. The full source documents the six exact relevance floors.

Final reward requires a healthy, accepting independent trajectory and submission integrity audit. Audit failures are reported separately from retrieval quality and cannot produce positive credit.

See the [full instructions](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/instruction-following-embedding/instruction.md),
[task documentation](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/instruction-following-embedding/README.md)
and [runtime configuration](https://github.com/VectorSpaceLab/Search-SWE/blob/b17b701dfce01dc043e50180ed1bfe733b40f612/tasks/instruction-following-embedding/task.toml)
for the complete contract at the synchronized benchmark revision.
