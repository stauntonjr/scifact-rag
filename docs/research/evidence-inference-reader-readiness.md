# Fixed-reader diagnostic readiness

Date: 2026-09-18. Governing work: [Issue #23](https://github.com/stauntonjr/scifact-rag/issues/23).
The [protocol](evidence-inference-reader-protocol.md) and
[cohort](evidence-inference-reader-cohort.json) remain unchanged. The owner authorized implementation
and the bounded live diagnostic after Lattice finishes, and explicitly authorized transfer of the
qualified public article text and prompts to the owner's DGX. This is fixed-model inference, not
a new training fit. No model request has been made by this work.

## Source and tokenizer qualification

CPU preparation preserves 20 articles, 101 prompts and 1,599 query-window pairs, without changing
the prior qualification or filling the sample from excluded articles. Article/evidence text and
attribution records remain in ignored local artifacts. Exact source-byte roundtrips are required.

The active reader's retained startup log resolves the model and tokenizer to
`nvidia/Qwen3.6-35B-A3B-NVFP4@1355db6a052410cfd62085d94b58866fd0f2c3c5`.
Its image ID is `sha256:a71834dea8f397350f037feb84269a07d76e7843d5380cc3d82d792ea0ec119f`;
vLLM is `0.23.1rc1.dev1353+g81f51a780.d20260721`, with Transformers 5.14.1. The
chat-template SHA-256 is `e84f32a23fdda27689f868aa4a1a5621f41133e51a48d7f3efcbea2839574259`.
This is startup-log evidence for the loaded revision, not an inference from the mutable cache ref.

The selector uses `answerdotai/answerai-colbert-small-v1` at the protocol's pinned revision
`c72aa89bc61afdd85373643f3a1a75b2aad6e0fe`. Its deployed image maps to the Compose-pinned digest
`nvcr.io/nvidia/vllm@sha256:bebcf9576b1720214319ee5c7ee4f7661954cbbf59ed3fcd188cd79a67f1967e`;
vLLM is `0.22.1+7b9cb5b7.nv26.6.55915567`, with Transformers 5.6.0.

Only tokenizer/configuration files were copied from the deployed snapshots. Local CPU checks
compare exact token-ID hashes under repository Transformers 5.15.1 with the deployed library
versions: all 202 full/oracle payloads match reader 5.14.1, and all 409 distinct selector queries
and documents match selector 5.6.0. This is local library parity using copied files, not an HTTP
tokenization or inference test of the server. Individual file hashes and results are retained in
`artifacts/evidence-inference-v2/reader-v1/runtime/`.

| Prepared input | Minimum tokens | Maximum tokens | Overflows |
|---|---:|---:|---:|
| Full article with complete reader chat template | 977 | 14,052 | 0 |
| Oracle evidence with complete reader chat template | 208 | 554 | 0 |

Selector query/document serializations have a maximum of 512 tokens including special tokens.
Selected-reader inputs are constructed only after counted selector responses and checked against
the same reader budget before dispatch. All counts above are preparation measurements, not model
performance or latency estimates.

## Verification and live gate

All 86 focused audit/reader tests pass, including 47 new preparation/runner/evaluation tests.
Fresh preparation with the committed implementation reproduced the counts above. Its manifest
SHA-256 is `888834d7ff034b391f6d90edb9cc819f88e8265823fdf25579f35fce6c88fc20`.
Independent review and the final repository gate are required before live execution.
Live latency remains unmeasured. The original CPU
probe exposed a structured-tokenizer-return counting error before any inference; that probe is
diagnostic evidence only and cannot authorize execution. Final preparation must use the repaired,
independently reviewed code at a fresh output path; `prepared-002` is the current qualified preparation.

The two standalone tools expose `--help`: `tools/evidence_inference_reader.py` has `prepare` and
`evaluate` commands; `tools/evidence_inference_reader_run.py` defaults to network-disabled runtime
validation and requires `--execute` plus verified local tokenizer inputs to dispatch. Preparation
refuses existing output paths. Runtime validation requires recorded model/image/template identities,
token accounting and exclusive-device evidence. Operator observations must be fresh; supplying a
JSON file is not an automatic live inspection of Lattice or the GPU.

The runner adapts the existing ColBERT request and indexed-response contract inside its coordinator
so it can retain raw payload/response evidence and enforce a total deadline. It does not alter the
product adapter or call its network-owning `score()` method. The scientific class parser, evaluator
and native task remain separate from the product's public `ask` behavior.
Independent review found and repaired two failure-path defects before inference: reader model or
token-accounting mismatch now records a failed experimental request rather than a scored completion;
HTTP errors and malformed JSON retain received status and exact body bytes. These failures halt
dispatch without retry. Optional malformed response/usage metadata cannot crash the partial-report
writer; only nonnegative integer token counts are aggregated. Deadline/transport uncertainty
remains explicitly unknown.

The latest read-only resource observation found the Lattice native fit and two Lattice audit
containers still running, with GPU utilization 92%. A running container's zero `ExitCode` field
is not successful completion. Do not infer a free device from that field or from low utilization.
Inspect actual process completion and any successor evaluation before issuing GPU requests.

The owner's conditional authorization is retained: once Lattice and competing GPU work are done,
verify current service identities, availability and exclusive allocation. Then execute only the
frozen protocol's counted preflight and, if its projection passes, the remaining schedule within
303 reader requests, 101 selector requests, 20,000 pairs and 5,400 seconds total. Preflight is
included; no automatic retry or resume, service restart, model substitution or budget extension.

If readiness fails, preserve the offline artifacts and pending issue. No empty or synthetic
evaluation report may be represented as the clinical diagnostic result.
