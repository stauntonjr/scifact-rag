# Evidence Inference fixed-reader diagnostic results

Date: 2026-09-19. [Issue #23](https://github.com/stauntonjr/scifact-rag/issues/23).
Protocol: [fixed-reader v1](evidence-inference-reader-protocol.md).
Full text and oracle evidence each produced 92 correct native labels out of 101; the two-window
ColBERT selection produced 79. This supports investigating evidence selection on this cohort,
while preserving a separate reader/label diagnosis for errors remaining with oracle evidence.

## Completed execution

All 101 prompts from the same 20 qualified training articles completed all three arms. There were
303 reader requests, 101 selector requests and 1,599 scored pairs, with no retries. The run took
238.925 seconds including the counted preflight. The preflight used 3 selector and 9 reader
requests in 6.850 seconds and projected 1,148.521 seconds, below the frozen 5,400-second ceiling.
There were no unknown/failed requests, invalid label outputs, context overflows or missing triplets.
Abstentions remain wrong predictions for native targets; they are not mapped to the neutral class.

| Context | Correct / 101 | Accuracy | Macro-F1 | Abstentions | Reader input tokens | Reader time |
|---|---:|---:|---:|---:|---:|---:|
| Full article | 92 | 91.09% | 0.9086 | 0 | 915,798 | 157.127 s |
| Selected two windows | 79 | 78.22% | 0.8019 | 5 | 139,463 | 41.778 s |
| Oracle evidence | 92 | 91.09% | 0.9134 | 1 | 28,335 | 29.458 s |

Selector cost was 9.503 seconds and 803,367 serialized input tokens; selected-arm reader plus
selector time was 51.282 seconds. These service times differ from total coordinator wall time.
Output tokens were 1,221 full, 1,254 selected and 1,246 oracle. Reference class counts were
35 decreased, 30 increased and 36 no-significant-difference. Per-class precision/recall,
confusion counts and all accounting fields are in the [text-free result JSON](evidence-inference-reader-results.json).

## Paired descriptive uncertainty and coverage

All 101 common-fit triplets enter the paired comparison, with zero attrition. The prespecified
2,000-replicate article-cluster bootstrap (20 articles, numpy PCG64 seed 1729) gives:

| Difference | Accuracy delta [95% interval] | Macro-F1 delta [95% interval] |
|---|---:|---:|
| Selected minus full | -0.1287 [-0.1926, -0.0561] | -0.1067 [-0.1682, -0.0428] |
| Oracle minus selected | +0.1287 [+0.0266, +0.2143] | +0.1115 [+0.0182, +0.1946] |
| Oracle minus full | 0.0000 [-0.0481, +0.0455] | +0.0048 [-0.0474, +0.0529] |

No bootstrap replicate lacked a native class. These intervals describe this small inspected
training cohort; they are not significance or generalization claims.

Mean selected/reference character-overlap precision was 2.76% and recall 46.98%, with 100% exact
source-byte roundtrip coverage. The annotations mark short evidence spans; overlap measures
reference-span coverage, not clinical entailment, complete evidence or role correctness.

## Runtime and evidence boundary

The owner explicitly released the GPU while Lattice continued CPU-probe development and authorized
reader/selector restoration on September 19. Both services had already been restored, but the
reader advertised 262,144 tokens. The idle reader was restored to its previously qualified
32,768-token startup recipe before dispatch; no software, model or scientific protocol was changed.
The healthy selector was left running. This restoration is the explicit owner-authorized exception
to the protocol's earlier prohibition on service changes. Lattice was not modified.

Reader: `nvidia/Qwen3.6-35B-A3B-NVFP4`, revision
`1355db6a052410cfd62085d94b58866fd0f2c3c5`, image
`sha256:a71834dea8f397350f037feb84269a07d76e7843d5380cc3d82d792ea0ec119f`,
vLLM `0.23.1rc1.dev1353+g81f51a780.d20260721`. Selector revision and image match the
[readiness report](evidence-inference-reader-readiness.md). Deployed tokenizer file hashes matched
the frozen inventory, all 202 full/oracle input counts reproduced locally, and every reader
response passed the live model-ID and input-token-count checks. Both services were healthy and
GPU process inspection showed no competing Lattice GPU workload. Public text was sent through
local-only SSH forwarding to the owner's DGX under the prior explicit transfer authorization.

Local ignored artifacts under `artifacts/evidence-inference-v2/reader-v1/`:
`prepared-002`, `live-20260919-001`, `evaluation-20260919-001`, and the runtime identity/owner-release
records. No earlier diagnostic ledger existed; the September 18 readiness stop sent zero requests.
The paused heartbeat remains paused; this completed attempt must not be rerun automatically.

- Preparation manifest SHA-256: `888834d7ff034b391f6d90edb9cc819f88e8265823fdf25579f35fce6c88fc20`.
- Runtime SHA-256: `891d04c4be3175c803fd1308f1eb24cc6c56c386885d25851752dbac4ce2db9d`.
- Ledger SHA-256: `e5f629cd330609a436df7959a115508252b6e510166eb1a81d23c5c4862cd9e2`.

## Implication for the next research decision

The narrow next hypothesis is that evidence selection can preserve the reader's full-context
accuracy while reducing context. First inspect the retained selected-versus-oracle disagreements
and evidence coverage; do not tune on this cohort and claim fresh validation. A later test should
freeze its hypothesis and use untouched articles. For Lattice, this offers a downstream test of
whether representations preserve decisive evidence and intervention/comparator/outcome relations.
It does not show that role confusion caused the errors: supplied ICO roles are inputs, not learned
roles, and labels alone cannot identify the failure mechanism.

Oracle did not improve accuracy over full text, so these results do not justify graph infrastructure,
a new extractor, training, or changing Lattice's current plan. The results are descriptive,
training-side evidence on 20 previously inspected articles. Publisher-paired provenance limitations,
unknown pretraining contamination and absence of clinical validation remain unchanged.
