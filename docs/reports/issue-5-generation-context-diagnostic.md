# Issue #5: generation-context validation diagnostic

- Date: 2026-09-14
- Governing roadmap: `docs/project/roadmap.md`, Phase 1
- Governing decision: ADR-0028
- Evidence class: fixed validation execution; diagnostic rather than strategy-selection evidence
- Default changed: no

## Executive result

The fixed 160-claim validation execution completed all 480 planned claim/policy rows with no
retrieval, assembly, or generation failures. It does not support promoting a chunk-aware generation
policy. The two nominal chunk policies supplied byte-for-byte identical context for every claim,
while unconstrained sampling produced different answers for identical prompts. The run also did
not emit a machine-readable stance prediction, so the public stance labels cannot be scored
deterministically.

The deterministic context measurements still answer an important architectural question. Relative
to complete abstracts, the DP context reduced the largest prompt from 4,429 to 3,964 input tokens,
but left the overall median unchanged at 1,987.5 tokens. On the 31 validation claims where a cited
long parent was actually retrieved, DP increased the median prompt from 2,886 to 2,956 tokens and
reduced conditional gold evidence-sentence recall from 1.0000 to 0.9636. Whole-document therefore
remains the compatibility default. These SciFact abstracts do not exercise a Qwen context-window
constraint that would justify accepting the observed evidence loss.

## Provenance

| Field | Value |
|---|---|
| Run ID | `generation-validation-20260915T023804Z` |
| Repository commit | `60fae57c5e41d7b234cb388fd7b5e0a6a3edb652` |
| Source split | deterministic `train-validation` |
| Evaluation input SHA-256 | `34084490c48515f0c788da0960d7f426c0e64e4dcf9431b8721d824ba0349105` |
| Preflight SHA-256 | `6e4e06a7bfd9b5344c46d62f08e6e15bb799f68b8474f0ceb1c97971c2274492` |
| Raw result SHA-256 | `8478588ba9dff876e77bd72b6d2e2928dfadf03fb91eea66893a6f741fd86c12` |
| Aggregate report SHA-256 | `b9226f77455be87c1785106817edbdb5c410d20ea3d6b8541c33e79eed85076f` |
| Retrieval | `pooled-coref-interval-content-max-colbert`, top 5 |
| Generator | `nvidia/Qwen3.6-35B-A3B-NVFP4`, revision `1355db6a052410cfd62085d94b58866fd0f2c3c5` |
| Generator runtime | `eugr/spark-vllm@sha256:b1420ff7b3595efc5df7134683595ee8de3b1b650d8538da62e55d7a7951b2e0` |
| Generator settings | temperature 0.1, 512 maximum generated tokens, thinking disabled |
| ColBERT | `answerdotai/answerai-colbert-small-v1`, revision `c72aa89bc61afdd85373643f3a1a75b2aad6e0fe` |
| Application image | `sha256:ce1160f6c079fbda3c7249e92d0b880006b84bcd8da52b5eb4359e7fe78bb26a` |
| Started / completed | `2026-09-15T02:38:04Z` / `2026-09-15T03:02:28Z` |

The ignored local manifest records the remaining database, extension, tokenizer, serving-runtime,
and image revisions. Raw and aggregate result files are host-readable mode `0644`. The manifest is
mode `0664`; it was finalized with the completion time after the run.

## Preflight population

| Population | Claims |
|---|---:|
| Validation claims | 160 |
| Public stance labels | 160 |
| Sentence-level gold evidence | 101 |
| At least one relevant parent retrieved | 128 |
| Cited parent above the 510-token ColBERT content boundary | 33 |
| Such a long cited parent actually retrieved | 31 |

The planned minimum of 30 long-document cases was met. This is nevertheless a ColBERT chunking
boundary, not evidence that the 32K Qwen prompt window was stressed.

## Aggregate observations

| Policy | Rows | Failures | Citation-valid | Conditional evidence recall | Insufficient output | Median input tokens | Median generation latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Whole document | 160 | 0 | 0.9500 | 1.0000 | 0.5250 | 1,987.5 | 964.8 ms |
| Top DP chunks | 160 | 0 | 0.9688 | 0.9898 | 0.4938 | 1,987.5 | 1,201.9 ms |
| Adaptive | 160 | 0 | 0.9375 | 0.9898 | 0.5438 | 1,987.5 | 872.1 ms |

All three policies received the same ordered retrieved parents for all 160 claims. Every successful
row had server-reported input and generated token counts. Eleven whole-document, seven top-DP, and
eight adaptive generations reached the 512-token answer ceiling.

The citation and answer-rate differences are descriptive only. Of 160 top-DP/adaptive pairs, just
75 raw answers were identical even though all 160 pairs had identical supplied text and input-token
counts. The differing outcomes therefore measure sampling variance, not a policy effect. Several
strict citation failures were comma-separated multi-document citations such as `[doc1, doc2]`;
others were non-document bracketed text. Raw output remains retained rather than being silently
normalized after the fact.

## Deterministic context comparison

Top-DP and adaptive context were identical for all 160 claims. This follows from the current
definitions: a one-view raw DP representation is the complete abstract, while both policies choose
the same top two views when a parent has multiple views. The adaptive policy is therefore not an
independent experimental arm under the stored-representation invariant.

Compared with whole-document context:

- 89 claims had identical context and token count;
- 13 claims used fewer input tokens under DP, while 58 used more;
- mean input fell by only 9.99 tokens and median input did not change;
- mean supplied contexts increased from 5.00 to 5.81 because multiple chunks repeat parent titles;
- maximum input fell by 465 tokens; and
- three claims lost at least one retrieved gold evidence sentence under DP, including one claim
  whose conditional recall fell to 0.25.

On the 31 long-cited-parent/retrieved claims, DP used fewer tokens in 5 cases and more in 26. Its
mean token delta was +0.23 and its paired median delta was +63 tokens; the group medians were 2,886
for whole-document and 2,956 for DP. Citation-valid rate was 0.9355 for whole-document and top-DP,
and 0.8710 for adaptive, but those answer-dependent values remain sampling-confounded.

## Missing decision evidence

This run cannot satisfy the roadmap's quality decision gate:

1. The generator produced prose rather than a constrained stance field, so SUPPORT and CONTRADICT
   correctness cannot be recovered deterministically without inventing a post-hoc classifier.
2. Temperature 0.1 was frozen, but no per-claim sampling seed was fixed. Identical prompts therefore
   diverged.
3. No numerical non-inferiority margin was written in Issue #5 before results were opened, so one
   cannot be selected afterward.
4. The fixed blinded human groundedness/overstatement review has not occurred.
5. Adaptive and top-DP are the same effective policy and cannot establish relative superiority.

These are experimental-contract defects, not evidence that any answer-dependent aggregate is good
or bad.

## Disposition

Retain this execution as diagnostic evidence and keep Issue #5 open. Do not rerun the same protocol
or change the application default. The smallest corrective slice is to make evaluation generation
reproducible, emit an explicitly parseable SciFact stance without changing interactive `ask`, and
collapse or redefine the duplicate chunk arm before freezing a replacement comparison. A separate
fixed blinded human-review worksheet remains required before a generation-quality promotion.
