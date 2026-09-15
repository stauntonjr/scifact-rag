# ADR-0026: Title-separated retrieval and independent neural reranking

- Status: accepted implementation; default selection superseded by ADR-0029
- Date: 2026-08-27
- Decider: Jack Rory Staunton, human owner
- Governing issue: local retrieval-effectiveness decision; no GitHub repository or Issue exists

## Context

The MiniLM token-window, coreference-sentence, and semantic-packing channels each included the
document title. In pooled retrieval, this repeated the same title signal inside multiple vector
channels. It also made it impossible to measure the title independently. The owner selected a
fixed equal-RRF title-plus-token-window baseline, with the title removed from every
abstract-derived MiniLM representation.

The latest global-coreference-interval pool reaches validation candidate recall 0.925000 and
oracle nDCG@10 0.926414, while its best retained scorer, ColBERT, reaches nDCG@10 0.734958. The
remaining gap initially supported one generic set-aware/listwise scorer experiment. The owner
selected RankZephyr in parallel with the existing MS MARCO and ColBERT scorers, not a scorer fusion,
then deferred it after live throughput projected roughly 3.4 hours for 160 queries and after
rejecting its distilled-frontier-model approach for the practical path.

The AnswerAI model card reports SciFact nDCG@10 0.7477. That is external full-corpus ColBERT
retrieval evidence, not a directly comparable target for this project's candidate-constrained
160-query validation rerank. The project has not reproduced the model card's indexing and query
encoding stack.

## Decision

- Store one `title` embedding per non-empty document title. Token windows, coreference sentences,
  sentence packing, greedy coreference packing, and global interval packing contain abstract text
  only.
- Make `title-token-window-rrf` the CLI and composition default. It independently retrieves top 50
  title and abstract-token candidates and combines their ranks with fixed equal RRF `k=60`.
  `token-window` remains selectable as an abstract-only diagnostic. ADR-0029 later supersedes only
  this default choice; the strategy and title-separation architecture remain accepted and
  selectable.
- Expand the global-interval candidate pool to six fixed top-50 generators: BM25, title,
  abstract-token windows, proper-noun coreference sentences, nominal-coreference sentences, and
  global coreference-interval packing.
- Compare `pooled-coref-interval-msmarco`, `pooled-coref-interval-colbert`, and
  `pooled-coref-interval-rankzephyr` independently over that identical deduplicated pool. Each
  strategy has exactly one neural scorer; no retrieval score or second neural score enters its
  final order.
- Adapt RankLLM's canonical `castorini.cli.v1` HTTP envelope behind the existing reranker port.
  Candidate IDs must be unique, complete, and unchanged; the returned list order is authoritative.
- Pin RankLLM to source commit `8ad18be76c90aa97ffae50b84dbc326bedc724fd` and RankZephyr to
  Hugging Face revision `aa11d9da444ec3490827656c3b961d5c5f3af0eb`.
- Serve RankZephyr through the existing digest-pinned NVIDIA vLLM image with an 8,192-token model
  limit, BF16 weights, one sequence, and a 0.20 GPU-memory ceiling. A separate lightweight
  RankLLM HTTP coordinator uses the packaged RankZephyr prompt, one deterministic pass, variable
  passages, a 20-document window, stride 10, 4,096-token context, and at most 300 words per
  passage.
- Run fixed comparisons at cutoff 10 without sweeping weights, depths, windows, prompts, models, or
  fusions. The later 300-query test comparison is explicitly exploratory because those qrels had
  already informed earlier architecture work.

## Consequences

Title evidence is now visible and counted once in every MiniLM pool. Existing strategy names stay
selectable, but their vector inputs change from title-plus-abstract-derived text to abstract-only
text. The default CLI behavior changes before 1.0 and therefore has a minor release impact.

RankZephyr adds an opt-in 7B BF16 model service and a pinned RankLLM coordinator. It is materially
slower than the pointwise MS MARCO and late-interaction ColBERT scorers and may be sensitive to
first-stage candidate order. The fixed generator order is BM25, title, token windows,
proper-noun coreference, nominal coreference, then global interval packing; no order sweep is
authorized.

The pinned RankLLM commit's `rank-llm serve http` CLI passes an unsupported `use_litellm` keyword
to its own `ServerConfig`. Compose therefore starts the same pinned package through its public
`create_app(ServerConfig(...))` factory. No upstream ranking, prompt, request, response, or model
code is copied or patched.

The RankZephyr validation run was stopped after a bounded throughput observation: its sliding
windows took about seven seconds each and required about eleven sequential windows per query,
projecting roughly 3.4 hours for 160 queries. No partial effectiveness metric is claimed. The owner
declined that operating cost and the checkpoint's distilled-frontier-model approach. RankZephyr is
therefore deferred from the practical recommendation; its opt-in implementation remains, and its
model and coordinator services are stopped.

The owner then authorized one fixed comparison on the already-inspected 300-query test qrels. The
title-separated six-generator pool averages 137.69 documents, reaches candidate recall 0.950333,
and has oracle nDCG@10 0.951169. ColBERT reaches nDCG 0.744417, MAP 0.703911, recall 0.852667, and
MRR 0.716210 in 165.07 seconds. MS MARCO reaches nDCG 0.688308 and recall 0.812222 in 141.95
seconds. The current BM25-plus-abstract-token RRF reaches nDCG 0.669962 and recall 0.819222, while
the dedicated-title plus abstract-token equal-RRF default reaches only nDCG 0.548652 and recall
0.705167. This evidence does not authorize tuning, but it makes the default-policy choice a revisit
item.

The local ColBERT result is 0.003283 below AnswerAI's published full-corpus SciFact nDCG 0.7477.
That is close directional evidence, not protocol reproduction: the local strategy reranks a bounded
candidate pool through vLLM `HF_ColBERT`; the published result uses full-corpus indexing/search.

## Alternatives

| Alternative | Reason not selected |
|---|---|
| Keep titles embedded inside every vector channel | Repeats one signal and prevents independent attribution |
| Use abstract-only token windows as the default | Preserves a clean diagnostic but discards an inexpensive strong title signal |
| Weight the title channel | Requires a tuning decision the validation boundary does not support |
| Fuse MS MARCO, ColBERT, and RankZephyr | Confounds the requested independent scorer comparison |
| Build a bespoke listwise prompt/runtime | Duplicates maintained RankLLM semantics and increases protocol ownership |
| Reproduce published ColBERT first | Requires a separate full-corpus ColBERT index and benchmark protocol; it does not block the fixed reranker comparison |

## Verification and revisit triggers

Focused tests cover title exclusivity, abstract-only representations, default wiring, the exact
six-generator pool, and strict RankLLM identity/order handling. Live verification must prove the
pinned checkpoint path, vLLM model length and memory ceiling, RankLLM health, one correct ranking,
fresh representation counts, and one evaluation per scorer. The repository gate and independent
review bind the final candidate.

Reopen this decision if the candidate depth, generator order, prompt/window protocol, scorer
composition, model revision, test split, or default weights change; if RankLLM's pinned CLI defect
is fixed and the source revision is intentionally upgraded; or if a full-corpus ColBERT
reproduction is separately accepted.
