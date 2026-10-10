# Local scientific-review feasibility — 2026-09-20

**Recommendation:** evaluate Qwen3.8-27B-FP8 as one local assisted reviewer on the DGX Spark. Hardware feasibility is strong; rubric-specific scientific quality and practical latency remain unmeasured. Do not replace the completed assessment or call a local panel qualified.

## Live host evidence

Read-only inspection of dgx-tailnet returned:
- Host spark-3a8f; AArch64; NVIDIA GB10.
- 121 GiB reported total unified memory, 66 GiB used and 55 GiB available at inspection; 3.4 GiB swap in use.
- About 2.3 TiB free disk.
- Existing model endpoint advertises nvidia/Qwen3.6-35B-A3B-NVFP4 with a 32,768-token limit.
- Serving container reports vLLM 0.23.1rc1.dev1353+g81f51a780.d20260721.
- Other application/database and late-interaction services are active. A momentary 0% GPU utilization is not authorization to displace them or proof of sustained availability.

No model was downloaded, loaded, benchmarked or invoked; no service was stopped.

## Model choice and memory

Qwen3.8-27B is a published dense model. Official weights and an official FP8 checkpoint exist; the model card lists 262,144 native context and controllable thinking. This makes it a plausible candidate, not a validated scientific judge. [Official model card](https://huggingface.co/Qwen/Qwen3.8-27B), [official FP8 checkpoint](https://huggingface.co/Qwen/Qwen3.8-27B-FP8).

| Candidate | Assessment |
|---|---|
| Existing Qwen3.6-35B-A3B-NVFP4 | Lowest setup cost; already serving. Useful for adapter and instruction checks. Review quality is not established. |
| Qwen3.8-27B-FP8 | Recommended first new candidate. Approximately 25–30 GiB of weight storage, plus runtime/cache/workspace overhead. Plausible within current headroom with bounded context and concurrency; actual residency must be measured. |
| Qwen3.8-27B BF16 | Approximately 50–55 GiB for weights alone. Plausible on the whole machine, but current available memory leaves insufficient comfortable headroom for safe co-residency. Needs an agreed service schedule. |
| Qwen3.8-Flash-Next | Not the first choice on this shared host. Official architecture includes 125B language parameters, 51B n-gram parameters and 4B MTP parameters. Its 6B active language parameters do not mean a 6B memory footprint. Even idealized 4-bit storage for 180B parameters is about 84 GiB before overhead. |

Memory figures are arithmetic estimates, not measured runtime allocations; some tensors remain at higher precision. The Flash model's architecture is documented in its [official card](https://huggingface.co/Qwen/Qwen3.8-Flash-Next). Start with FP8 to avoid simultaneously introducing a new model and aggressive four-bit quantization; this is an experimental-design recommendation, not proof FP8 preserves every judgment.

## Serving and integration

vLLM publishes a Qwen3.8 recipe, but its documented hardware checks are not this GB10/AArch64 host. Do not infer compatibility from version numbering alone. Pin and verify the checkpoint, tokenizer/chat template, compatible ARM64 image, reasoning parser and quantization kernels. Prefer an isolated evaluation endpoint and leave the generator endpoint unchanged. [vLLM recipe](https://recipes.vllm.ai/Qwen/Qwen3.8-27B).

Use the full approved rubric in a fresh request, source text and strict JSON schema; no tool execution is needed. Retain attempt identities and source validation. vLLM supports JSON-schema structured output with reasoning, but exact quotations, interval correctness and semantic labels still require validation. [Structured-output documentation](https://docs.vllm.ai/en/latest/features/structured_outputs/).

A local HTTP transport is needed: the existing review coordinator's Codex-specific admission assumptions cannot be bypassed by changing a URL. Adapt its transport boundary, retain attribution, and explicitly version the new runtime profile and protocol.

Start with one request at a time and a context limit derived from the longest actual rubric-plus-case payload, reserving room for reasoning and final JSON. The published maximum context is not a sensible default allocation. Local inference removes remote service dependence but does not guarantee lower latency: the dense model, long instructions, reasoning output and memory contention all matter. Measure full-request median/tail time, valid judgments per minute, peak memory and failures.

## Scientific usefulness and the smallest decisive trial

The historical comparison-omission disagreement is not reference truth, and the old panel's labels must not become the local model's answer key. General model benchmarks do not validate this rubric.

Prepare 24 new diagnostic cases before judging: one unambiguous positive and one faithful negative for each of the eight granular fields, plus eight applicability/ambiguity/adequacy boundary cases. Use exact passages and independently reviewed expected decisions with explanations. Keep them distinct from rubric examples and resolve disputed references before scoring. This is a bounded feasibility probe, not a powered qualification sample.

One local reviewer makes one recorded attempt per case. Measure:
- semantic correctness against the reference explanations, separately from agreement;
- false positives on faithful answers, missed material transformations and proper uncertainty/applicability;
- adequate answers versus unnecessary refusals;
- raw schema success, exact-source validation, truncation, full latency and memory.

Inspect every error rather than applying another unexplained percentage gate. If failures concern instructions, repair those before any larger comparison. If critical source distinctions remain unreliable, use the model for evidence indexing and proposed annotations with explicit source review, not autonomous acceptance.

For actual candidate development, start with one local review plus source-based review of apparent wins, regressions and unresolved cases. Running the same checkpoint under several role names does not create independent judges; Qwen judging Qwen-generated answers also raises shared-error concerns. Separate sessions prevent peer leakage, not correlated mistakes. A second checkpoint or externally reviewed sample can test a different failure pattern, but still does not prove independence.

**Decision:** technically feasible to test; promising for inexpensive repeated development review; not yet established for autonomous scientific qualification. The next useful evidence is the small referenced trial with the corrected complete rubric, not a repeat of the old 42-case run.
