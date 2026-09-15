# Issue #5: corrected generation-context validation

- Date: 2026-09-14
- Governing roadmap: `docs/project/roadmap.md`, Phase 1
- Governing decision: ADR-0028
- Evidence class: corrected fixed validation execution; automatic measures complete, human review pending
- Default changed: no

## Executive result

The corrected fixed 160-claim comparison completed all 480 policy rows with zero execution
failures. Every output contained a parseable SciFact verdict. Whole-document stance accuracy was
0.8125; the single effective DP policy scored 0.8250. That two-claim net difference does not justify
a default change: DP and whole-document tied at 0.8387 on the 31 long/retrieved claims, DP did not
reduce median input tokens overall or on that subset, and DP reduced conditional gold
evidence-sentence recall.

`top-dp-chunks` and `adaptive` remain operationally identical for this stored representation. The
corrected evaluator generated only once for an exact claim/context pair and retained the same
response in every equivalent policy row. All 160 DP/adaptive contexts, answers, verdicts, citation
outcomes, and token counts are therefore exactly equal rather than being confounded by backend
nondeterminism.

Whole-document remains the compatibility default. The corrected automatic result characterizes the
tradeoff but cannot authorize a promotion: Issue #5 had no prospectively declared non-inferiority
margin, and the frozen blinded human groundedness review is not yet scored.

## Provenance

| Field | Value |
|---|---|
| Run ID | `generation-validation-v2-20260915T032341Z` |
| Repository commit | `ad24c77f51cf30f6fa9db6b26dde2ee16fddb914` |
| Source split | deterministic `train-validation` |
| Evaluation input SHA-256 | `34084490c48515f0c788da0960d7f426c0e64e4dcf9431b8721d824ba0349105` |
| Final manifest SHA-256 | `7348418473ec279c840561862475d9dca73a6f91db239f7fadb5e23ea9422882` |
| Raw result SHA-256 | `006b88286e24efc5b6b1a66f23f3e88a814048a4cb06c8cee1336d24728c7aec` |
| Aggregate report SHA-256 | `a80c00696e1a666b454f0d4346aa1646408031508c621a775a1b7242a03dc3ba` |
| Retrieval | `pooled-coref-interval-content-max-colbert`, top 5 |
| Generator | `nvidia/Qwen3.6-35B-A3B-NVFP4`, revision `1355db6a052410cfd62085d94b58866fd0f2c3c5` |
| Generator runtime | `eugr/spark-vllm@sha256:b1420ff7b3595efc5df7134683595ee8de3b1b650d8538da62e55d7a7951b2e0` |
| Evaluation prompt | `scifact-claim-verification-v1`, SHA-256 `da2020ff9e88c9450ea898fd0fc0b4baa5a0b9da04d347e04acb8c83fb757e98` |
| Generator settings | temperature 0.1, seed 1729, 512 maximum generated tokens, thinking disabled |
| ColBERT | `answerdotai/answerai-colbert-small-v1`, revision `c72aa89bc61afdd85373643f3a1a75b2aad6e0fe` |
| Application image | `sha256:99d2424c4087e75f6fd1587736270a78d3f06a0dfba36ef0a5c572e53818edd1` |
| Started / completed | `2026-09-15T03:23:41Z` / `2026-09-15T03:36:09Z` |

The final manifest records all database, extension, tokenizer, serving-runtime, and image
revisions. Raw and aggregate result artifacts are host-readable mode `0644`.

## Contract integrity

| Check | Result |
|---|---:|
| Planned / retained rows | 480 / 480 |
| Unique query/policy pairs | 480 |
| Complete three-policy query groups | 160 |
| Queries with identical retrieved parent order across policies | 160 |
| Execution failures | 0 |
| Parseable verdicts | 480 |
| Missing server token counts | 0 |
| Actual Qwen requests | 231 |
| Exact-prompt response reuses | 249 |
| DP/adaptive contexts and raw answers equal | 160 / 160 |

The fixed seed remains recorded, but it is not claimed to make this vLLM/Qwen runtime numerically
deterministic. An isolated long-prompt probe diverged at both temperature 0.1 and 0.0 despite an
identical seed. Exact-prompt reuse, not the seed alone, removes within-comparison variance.

## Automatic results

| Policy | Stance correct | Stance accuracy | Citation-valid | Conditional evidence recall | Median input tokens | Median generation latency |
|---|---:|---:|---:|---:|---:|---:|
| Whole document | 130 / 160 | 0.8125 | 0.9750 | 1.0000 | 2,088.5 | 2,108.5 ms |
| Top DP chunks | 132 / 160 | 0.8250 | 0.9750 | 0.9898 | 2,088.5 | 1,993.3 ms |
| Adaptive | 132 / 160 | 0.8250 | 0.9750 | 0.9898 | 2,088.5 | 1,993.3 ms |

All policies scored 160 verdicts. Whole-document and DP differed on only four: DP corrected three
whole-document errors (`680`, `758`, and `978`) and introduced one error (`500`). The other 156
verdicts were equal. Relevant-parent retrieval was fixed at 0.8000. Whole-document accuracy was
0.8828 when at least one gold parent was retrieved and 0.5312 otherwise; DP was 0.8906 and 0.5625,
respectively. This preserves the distinction between retrieval failure and generation behavior.

Four rows per effective policy failed the strict citation gate. One generation per effective
policy reached the 512-token answer ceiling. Exact reuse makes equal-policy citation and completion
outcomes identical rather than repeated samples.

## Context and long-document result

Relative to whole-document context, DP:

- used identical text on 89 claims, more input tokens on 58, and fewer on 13;
- changed mean input by -9.99 tokens and median input by zero;
- reduced maximum input from 4,530 to 4,065 tokens;
- increased mean supplied context rows from 5.00 to 5.81 because parent titles repeat; and
- omitted at least one retrieved gold sentence on three claims, reducing mean conditional recall
  from 1.0000 to 0.9898.

On the 31 long-cited-parent/retrieved claims, both policies scored 26/31 stance decisions (0.8387)
and 29/31 citation-valid answers (0.9355). Whole-document retained every conditional gold sentence;
DP recall was 0.9636. DP used more tokens on 26 long cases and fewer on five; its paired median delta
was +63 tokens, while group medians were 2,987 whole-document and 3,057 DP. Mean token delta was
only +0.23 because a few large reductions offset the repeated-title overhead. Maximum input fell
from 4,530 to 4,065 tokens, still far below the served 32K Qwen window.

The current DP policy therefore provides a lower worst-case prompt but no material efficiency gain
on this corpus. Its scaling rationale remains plausible for documents much longer than SciFact
abstracts; this validation does not demonstrate it.

## Human-review handoff

The prospective selection and rubric are in `docs/project/generation-human-review-v1.md`. The local
review worksheet contains 42 distinct responses across the 24 frozen claims after exact-equivalent
outputs are deduplicated:

| Artifact | SHA-256 | State |
|---|---|---|
| `artifacts/generation-validation-v2-human-review.json` | `f6387ab3f4c1fe2110fbf671689377d624c1a10194ef1b34c805b34fdcb5f00b` | 42 rows; reviewer and 378 rubric fields blank |
| `artifacts/generation-validation-v2-human-review-map.json` | `deb59a6c5c031313adf266bf1efd2b345d999087c0b0a94845c50e01f610e0ae` | retained separately from reviewer-facing data |

The worksheet omits policy name, expected stance, predicted stance, automatic correctness, tokens,
latency, and aggregate results. A human reviewer must fill the rubric, identity, and UTC completion
time; an agent must not invent that provenance.

## Disposition

Keep whole-document as the simple generation default. Keep one chunk-aware strategy as an opt-in
scalability path, but treat `top-dp-chunks` and `adaptive` as duplicate public behavior until a
separate simplification decision removes or redefines one. Do not run another SciFact validation
comparison or tune the context policy from these results. Issue #5 remains open only for the frozen
human review and its joined report; that review cannot retroactively promote a policy without the
missing prospective margin.
