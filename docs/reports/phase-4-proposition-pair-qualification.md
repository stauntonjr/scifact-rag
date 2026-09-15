# Phase 4 grounded proposition-pair qualification

Date: 2026-09-15

Governing decision: [ADR-0031](../adr/0031-proposition-graph-scoring.md)  
Governing issue: [#9](https://github.com/stauntonjr/scifact-rag/issues/9)  
Evidence class: internal engineering qualification; no proposition-quality result

## Result

**Stopped before candidate-pool extraction.** The fixed Qwen configuration passed two of four
source-grounding probes. Explicit negation and scientific qualifier both returned proposition
payloads that failed exact source-span validation. The predeclared rule therefore prohibited the
5,027-source extraction pass, MiniLM feature computation, audit interpretation, and graph work.

This result does not show that proposition pairs lack value. It shows that the selected extractor,
prompt, and strict span contract did not qualify to test that hypothesis in this run.

## Frozen boundary

| Artifact or boundary | Verified value |
|---|---:|
| Phase 3 manifest SHA-256 | `121b7ce11a21a5fdfa7cf4f586c02f35015806f47ddc118fea912189092afcc5` |
| Phase 3 results SHA-256 | `40701fa9c161662c017602b0ac405e92c0212c0811eea4f4ccad7dbbb6a74b0e` |
| Claims | 160 |
| Distinct candidate documents | 4,867 |
| Frozen sources | 5,027 |
| Source manifest SHA-256 | `73581347b6551f2e537f63a0e52c3aadad0d2b1548e6edb208866723f55cb876` |
| Audit rows | 100 |
| Audit manifest SHA-256 | `0cb2803a99dfbae1950b600041259c6e67924db5d7529de3444496025e7e61f6` |
| Qualification SHA-256 | `2c337f76bc32317a42130dec02809e8a9ec69cdcc5a19e424e5c5fc37d56128c` |

The preflight authenticated the exact retained files and rejoined all 21,711 Phase 3 candidates to
the fixed evaluation claims, corpus documents, recomputed candidate identities, and gold labels.
The 100-row audit was frozen but not reviewed because no proposition result was accepted for
interpretation.

## Qualification

Model: `nvidia/Qwen3.6-35B-A3B-NVFP4`  
Prompt: `grounded-proposition-extraction-v1` (`d5059711...`)  
JSON Schema: `71dbcc03...`  
Seed: `1729`; temperature: `0`; thinking: disabled

| Probe | Outcome | Grounded propositions | Latency (ms) | Failure |
|---|---|---:|---:|---|
| Positive relation | pass | 1 | 12,110.63 | — |
| Explicit negation | fail | 0 | 4,023.65 | exact span mismatch |
| Scientific qualifier | fail | 0 | 4,600.99 | exact span mismatch |
| No relation | pass | 0 | 1,467.96 | — |

All probe text is ASCII, so the two failures are not explained by UTF-8 byte offsets versus Unicode
code-point offsets. The adapter failed closed and did not retain invalid proposition objects, so
this artifact does not support a more specific claim about which returned field was misgrounded.
No probe was retried.

## Decision

- Do not extract the candidate pool under this configuration.
- Do not compute the five pair features or their ROC-AUC/average precision.
- Do not interpret the frozen audit against proposition outcomes.
- Do not build graph paths, PostgreSQL projection tables, AGE integration, entity linking, learned
  fusion, or another model/prompt variant under Issue #9.
- Retain the bounded implementation and exact failure evidence. A future extraction-method
  comparison needs a new issue, a fresh frozen qualification contract, and owner approval.

Existing retrieval, generation, database, CLI defaults, public-test boundaries, and inactive
capabilities remain unchanged.
