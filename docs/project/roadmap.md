# SciFact RAG roadmap

Date: 2026-09-17

Owner: Jack Rory Staunton

Status: completed prototype at the accepted DGX-local boundary

## Purpose

This roadmap records the completed SciFact RAG prototype. Phases 1–6 reached their accepted
completion or explicit stop decisions; no additional implementation is owed within this scope.
The retained delivery sequence was:

1. prove which evidence context should reach generation;
2. select a retrieval-default recommendation through one frozen comparison with its previously
   inspected evidence boundary disclosed;
3. add explicit scientific inference and stance scoring;
4. test grounded proposition structure before earning any graph work;
5. harden and release the CLI vertical slice;
6. add API, MCP, and web adapters only after the common application layer is accepted.

The roadmap is a planning and sequencing document. Accepted ADRs remain authoritative for durable
architecture decisions. Each delivery phase must be represented by one or more bounded GitHub
Issues before implementation and must receive its own design or implementation plan when its gate
opens.

## Product objective

Deliver a reproducible CLI application on one DGX Spark that:

- ingests all 5,183 public BEIR SciFact documents into PostgreSQL;
- retrieves and ranks evidence with measured effectiveness;
- supplies sufficient, bounded evidence to the hosted Qwen NVFP4 generator;
- returns a scientifically qualified answer with valid parent-document citations, or exactly
  `insufficient evidence`;
- preserves enough provenance to explain which representation, scorer, passage, and source
  contributed to the result.

The prototype is accepted only when retrieval and generation have both been evaluated. A successful
retrieval benchmark plus a few plausible generated examples is not sufficient.

## Current position

| Surface | Current state | Consequence |
|---|---|---|
| Corpus and storage | All 5,183 documents are ingested into PostgreSQL with dense representations and BM25 | Corpus ingestion is no longer the critical path |
| Candidate generation | The six-generator pool reaches 0.950333 candidate recall and 0.951169 oracle nDCG on the already-inspected 300-query test set | Candidate breadth is strong; final ordering is the measured bottleneck |
| Pointwise ranking | Whole-title-plus-abstract ColBERT reaches test nDCG 0.744417 and recall 0.852667 under a local protocol that is not identical to the published full-corpus protocol | ColBERT is the practical ranking leader, but the result does not authorize further test-set tuning |
| Long-document ranking | Fixed-pool DP content-max ColBERT reaches development nDCG 0.755459 and recall 0.870853, close to the whole-document control at 0.759619 and 0.869055 | DP content views are a credible scalable representation even though the complete multiview fusion regressed |
| Current retrieval default | DP content-max ColBERT is applied through one shared default constant after it reached validation nDCG 0.742493 and recall 0.806250 versus 0.673519 and 0.787500 for BM25 plus token windows | BM25/token-window remains the fast/no-ColBERT fallback; no retrieval retuning is planned |
| Generation | Corrected automatic validation and the completed 24-claim blinded review retain whole-document as default; adaptive is the canonical scalable opt-in | Phase 1 is complete; do not rerun or tune on SciFact validation |
| Scientific reasoning | Synonymy, polarity, negation, contradiction, and cross-sentence inference are not explicit scores | Retrieval relevance must not be mistaken for support or contradiction |
| Proposition/graph | A strict four-probe Qwen qualification stopped before pool extraction after two exact-span failures | The graph was not earned; retain the bounded code and do not build projection infrastructure |
| Interfaces | CLI, loopback HTTP, two-tool DGX-local MCP, and the Issue #13 same-process evidence-inspection UI are accepted | Phase 6 is complete; preserve one application layer across adapters |
| Planning | Public GitHub Project #17 tracks the bounded roadmap Issues; Issue #10 completed the CLI release gate | This document and accepted ADRs define sequence; each new architecture phase still needs a bounded Issue |

The public test qrels have been inspected repeatedly. Their scores are descriptive historical
evidence only. They are not a parameter-selection surface.

## Architectural through-line

The application remains a modular monolith with one explicit composition root:

```text
CLI query
   |
   v
candidate generators ----> deduplicated broad candidate pool
   |                                  |
   |                                  v
   +------------------------> complete scorer channels
                                      |
                                      v
                              ranking policy
                                      |
                                      v
                         parent-document retrieval
                                      |
                                      v
                      generation-context assembler
                                      |
                                      v
                         Qwen NVFP4 generator
                                      |
                                      v
                  qualified answer + parent citations
```

Any future scientific scorer must enter through a complete scorer channel over the broad candidate
pool, not only documents surviving an earlier top-10 ranking. The Phase 4 proposition attempt did
not qualify its extractor, so no such channel is currently authorized.

LangGraph is not part of the current topology. The path is a deterministic request pipeline with
replaceable ports, not a stateful agent workflow. Reconsider LangGraph only if the product gains a
real need for resumable branching, human review checkpoints, tool-driven generation, or durable
multi-step recovery that cannot remain clear in ordinary application services.

## Roadmap summary

| Order | Phase | Product result | Gate to proceed |
|---:|---|---|---|
| 0 | Establish the execution boundary | Reproducible manifests and canonical work items | Evaluation inputs and immutable settings recorded |
| 1 | Evaluate generation context | Completed: whole-document retained; adaptive remains the scalable opt-in | Automatic decision and frozen human review recorded |
| 2 | Select the retrieval default | One defensible default plus retained opt-in experiments | Validation gate passed without test-set tuning |
| 3 | Add scientific inference scoring | Support, contradiction, and insufficiency become explicit evidence | Fixed validation comparison demonstrates useful incremental signal |
| 4 | Test grounded proposition pairs | Determine whether explicit structure merits graph work | Stopped at the frozen extraction qualification; graph work is not earned |
| 5 | Harden and release the CLI proof | Completed: reproducible end-to-end CLI application acceptance | Clean DGX run and retained acceptance report passed |
| 6 | Add composition adapters | API, MCP, and small web UI reuse the same application services | CLI semantics remain unchanged across adapters |

Only one phase is active at a time unless work items are demonstrably independent and do not share
an evaluation boundary.

## Phase 0: establish the execution boundary

### Outcome

Make subsequent measurements reproducible and turn this roadmap into bounded executable work
without adding product features.

### Work

1. Publish or otherwise reconcile the three clean local commits that contain the multiview
   ablations and generation-context strategies before new application changes are stacked on them.
2. Create one GitHub Issue for Phase 1 and separate decision Issues for the generation-context and
   retrieval-default promotions. Do not copy the template program backlog into this repository.
3. Record one run manifest schema containing:
   - repository commit;
   - corpus archive checksum and source split;
   - evaluation-manifest checksum;
   - retrieval and context strategy names;
   - candidate limit and answer limit;
   - generator, MiniLM, MS MARCO, ColBERT, tokenizer, container, and database-extension revisions;
   - generator temperature, answer-token limit, and thinking setting;
   - start/end timestamps and host identity;
   - per-query output artifact path.
4. Preserve raw per-query results. Aggregate metrics without discarding failures, timeouts,
   insufficient-evidence responses, or malformed outputs.
5. Mark the existing 300-query BEIR test results as already inspected. No later phase may use them
   to choose weights, thresholds, candidate depth, models, or defaults.

### Exit gate

- The Phase 1 Issue contains the frozen comparison protocol and links to this roadmap.
- A dry run can emit a complete manifest without calling the live generator.
- There is one named location for raw results and one for aggregate reports.
- No retrieval, prompt, or model behavior changes in this phase.

## Phase 1: evaluate generation-context strategies

Status: completed 2026-09-16. The corrected automatic comparison and frozen blinded review confirm
whole-document as the compatibility default while retaining adaptive as the scalable opt-in.

### Question

For a fixed retrieved parent ranking, should Qwen receive complete abstracts or the adaptive
ColBERT-selected DP context?

### Fixed comparison

Compare exactly these distinct policies in future runs:

- `whole-document`: title plus complete abstract for every retrieved parent;
- `adaptive`: complete abstract when its stored DP representation is one exact view, otherwise the
  same top-two selection.

`top-dp-chunks` remains an accepted compatibility alias for `adaptive`. The retained validation
report contains both historical names and proved their contexts and outputs identical on all 160
claims; new paired runs do not create a redundant third row.

Hold the following constant across paired runs:

- repository commit and database contents;
- retrieval strategy, returned parent order, and answer limit;
- Qwen checkpoint, endpoint, prompt, temperature `0.1`, maximum 512 answer tokens, and
  `enable_thinking=false`;
- ColBERT checkpoint and tokenizer revision used for chunk selection;
- citation parser and invalid-citation fallback behavior.

### Evaluation data

Create a versioned manifest from public SciFact training material. Every row must contain the claim
or question, public source split, expected stance when available, gold parent document IDs, gold
evidence sentence identifiers when available, and a stable query ID. The manifest construction
must fail if a source row cannot be joined unambiguously.

Use the existing deterministic 649-query development and 160-query validation partition as the
selection boundary where compatible IDs exist. Development is for evaluator implementation and
failure analysis. The 160-query validation partition is for the one fixed policy comparison.
Unsupported controls must be declared in the manifest rather than invented during result review.
The original hidden SciFact test labels are out of scope.

Before live evaluation, report how many validation queries have:

- an available stance label;
- sentence-level gold evidence;
- at least one relevant parent retrieved;
- a gold parent whose abstract exceeds the 510-token ColBERT content boundary.

If fewer than 30 validation cases exercise the long-document branch, the run may establish SciFact
quality compatibility but must not claim general long-document superiority.

### Measurements

Record paired per-query measurements for:

- relevant-parent retrieval success before context assembly;
- gold evidence-sentence recall in the assembled context, conditional on retrieving a gold parent;
- supplied parent count, context count, distinct cited-parent count, and citation validity;
- stance or answer correctness where the public annotation supports deterministic scoring;
- exact insufficient-evidence behavior on declared unsupported controls;
- groundedness and material scientific overstatement on a fixed blinded human-review subset;
- input tokens under the Qwen tokenizer, generated tokens, latency, and failures;
- omissions of negation, qualifier, population, intervention, comparison, or outcome context.

The first comparison does not use an LLM judge. Deterministic annotations and a fixed human rubric
remain distinguishable in the result artifact.

The fixed human subset selection and rubric are recorded in
`docs/project/generation-human-review-v1.md`. The reviewer receives blinded policy/output rows;
automatic stance and citation scores remain outside that worksheet.

### Decision rule

- Keep `whole-document` if the chunk-aware policy does not preserve answer/stance correctness and
  citation validity while materially reducing context on cases that actually require chunking.
- Promote `adaptive` only if it is non-inferior on the fixed quality measures and reduces median
  input tokens or truncation exposure on the long-document subset.
- If the validation set is too small for a long-document conclusion, retain whole-document as the
  default and carry adaptive forward as the explicitly scalable opt-in policy.

Any numerical non-inferiority margin must be written into the Phase 1 Issue before the result is
opened. It may not be chosen after observing outcomes.

### Exit gate

- The retained historical report compares all three recorded names on identical parent rankings;
  future reports compare the two distinct policies.
- Every aggregate number can be traced to a per-query record and run manifest.
- Failures and missing annotations are reported explicitly.
- ADR-0028 is confirmed or superseded with the selected default and its evidence boundary.

## Phase 2: select the retrieval default

Status: fixed comparison, decision, and runtime-default implementation complete.

### Question

Which already-defined retrieval architecture should be the simple operational default without
tuning to the public test qrels?

### Candidate set

Freeze a small comparison before running it. The initial candidates are:

1. BM25 plus abstract token-window equal RRF: the strongest simple hybrid already measured;
2. six-generator candidate pooling followed by whole-document ColBERT: the strongest practical
   measured ranker;
3. six-generator candidate pooling followed by DP content-max ColBERT: the scalable near-runner-up
   that avoids the regressive title and robust-normalization bundle.

Do not add RankZephyr, new fusion weights, a model sweep, or another representation to this decision.
The dedicated title embedding remains a candidate generator where declared, but it is not
automatically fused into the final score.

### Evaluation protocol

- Use the deterministic training-derived validation boundary, not the inspected 300-query test
  qrels, for selection.
- Hold generator depth, final cutoff, corpus rows, model revisions, and score aggregation fixed.
- Report nDCG, MAP, recall, precision, MRR, candidate recall, oracle nDCG, latency, and service
  requirements.
- Inspect query-level transitions: newly rescued relevant documents, lost relevant documents, and
  changes in top-rank ordering.
- Treat candidate recall as a diagnostic and guardrail, not as a gate that prevents a stronger
  second-pass scorer from operating on the broad pool.

### Decision rule

Choose the simplest Pareto-efficient candidate on ranking quality, relevant-document recall, and
operational cost. ColBERT may become the default only if its fixed validation improvement justifies
the GPU service dependency. DP content-max may become the default long-document scorer even if the
short SciFact whole-document control remains slightly stronger. Do not average title and content or
apply robust normalization unless a future separately approved hypothesis reopens that bundle.

### Exit gate

- One retrieval strategy is the documented and implemented default.
- Other measured strategies remain named, opt-in experiments rather than deleted code.
- README, CLI help, composition defaults, ADRs, and tests agree.
- The public test set is used at most once as confirmation after the decision is frozen, and the
  confirmation cannot trigger retuning.

### Recorded outcome

Issue #6 completed 480/480 fixed validation rows without failures. DP content-max ColBERT led every
reported effectiveness metric at nDCG@10 0.742493 and recall@10 0.806250. Its 638.94 ms median
latency was about 8.1 times the 78.70 ms BM25/token-window baseline, but the 0.068975 absolute nDCG
gain justified the existing ColBERT dependency for the retrieval-effectiveness objective.
ADR-0029 selects content-max and Issue #7 applies it through one shared CLI/composition default;
BM25/token-window remains the fast/no-ColBERT alternative. The already-inspected evidence boundary
prevents a clean generalization claim, and neither another test run nor a tuning cycle is
authorized.

## Phase 3: add scientific inference and stance scoring

### Goal

Make support, contradiction, uncertainty, and scientific qualification explicit instead of asking
lexical or semantic relevance scores to stand in for them.

### Architecture

Add one complete, provenance-bearing scorer over every document in the broad candidate pool. Its
input is the raw query/claim plus the candidate's best evidence spans. Its output retains separate
support, contradiction, and unknown/insufficient values rather than collapsing them immediately
into one relevance probability.

The first implementation should use one fixed pretrained reranking or natural-language-inference
model that can be served on the existing DGX topology. It must not train on the evaluation labels.
A model survey may select the checkpoint, but only one primary model and one declared control enter
the first fixed evaluation.

### Required phenomena

The scorer and error analysis must represent:

- biomedical aliases and synonymy;
- directional relations and reversed arguments;
- positive versus negative polarity;
- explicit negation and contradiction;
- population, intervention, comparator, and outcome qualifiers;
- association versus causation;
- animal, in-vitro, and human evidence boundaries;
- cross-sentence evidence that cannot be judged from one isolated sentence.

Coreference is an input normalization aid only. It does not own any of these judgments.

### Evaluation

- Evaluate stance accuracy or macro-F1 where public SciFact labels support it.
- Evaluate evidence-sentence recall and citation correctness independently from stance.
- Compare retrieval ranking with and without the new channel on the same candidate pool.
- Retain a categorized failure set for synonym, polarity, negation, qualifier, and cross-sentence
  errors.
- Report calibration descriptively; do not label model scores as probabilities unless calibrated
  on a separately declared set.

### Exit gate

The scorer proceeds to default ranking or generation only if it contributes unique signal on the
fixed validation boundary. If it merely reproduces ColBERT ordering or harms evidence recall, retain
the interface and failure corpus but do not promote the model.

### Outcome (2026-09-15)

Issue #8 completed the fixed diagnostic over all 21,711 candidates in the 160 frozen claim pools
with no failed or unknown outcomes. Evidence-sentence recall was 0.899522, but three-way macro-F1
was 0.324781 versus 0.332410 for the neutral-prior control; rare-class precision was 0.036027 for
entailment and 0.009807 for contradiction. The channel is retained with its provenance and failure
corpus but is not promoted into retrieval or generation. See
`docs/reports/phase-3-scientific-inference-validation.md`.

## Phase 4: test grounded proposition pairs

### Outcome (2026-09-15)

Issue #9 deliberately reduced the proposed graph system to one proposition-pair experiment. It
froze 160 claims, the 4,867 distinct documents in their Phase 3 pools, a deterministic 100-row error
audit, five untrained pair features, strict extraction gates, and a mechanical continuation rule.
No PostgreSQL table, graph path, service, dependency, default, or capability activation was added.

The existing Qwen NVFP4 endpoint then ran exactly four frozen qualification probes. Positive
relation and no-relation passed. Explicit negation and scientific qualifier failed exact source-
span grounding, so the predeclared stop rule fired before any of the 5,027 pool sources was sent and
before MiniLM pair scoring or audit interpretation. The graph was not earned.

Retain the model-neutral contracts, strict adapter, authenticated Phase 3 boundary, and bounded CLI
workflow as a failed-but-informative experiment. Do not change the prompt, retry the probes, swap
extractors, activate `semantic-evidence-ledger`, or build graph infrastructure under Issue #9. Any
new extraction-method comparison requires a separately approved issue and an uninspected decision
boundary. The completed blinded generation review closes Phase 1, so the product roadmap now
advances to hardening the CLI vertical slice.

## Phase 5: harden and release the CLI vertical slice

### Work

- Add a generator-token budget only if Phase 1 shows prompt overflow, avoidable context cost, or
  long-document truncation. Budget under the Qwen tokenizer, not the ColBERT tokenizer.
- Add adjacent-sentence or coreference-neighbor expansion only for a documented missing-context
  failure class and charge it against the same token budget.
- Emit retrieval, ranking, context-selection, generation, citation, latency, and failure metadata
  in one inspectable run artifact.
- Verify an empty-volume ingest and an existing-volume no-op ingest on the DGX Compose topology.
- Verify representative supported, contradicted, qualified, and insufficient-evidence cases.
- Reconcile the 11.71 GB application image only after product acceptance; image slimming is not a
  prerequisite unless it prevents reproducible operation.
- Produce a release report that distinguishes engineering checks, validation results, inspected
  test confirmation, and manual scientific review.

### Release gate

- A clean public clone can build and run with documented prerequisites.
- All 5,183 documents ingest reproducibly.
- The selected retrieval and generation defaults complete end to end.
- Citations resolve only to supplied parent documents.
- Unsupported evidence returns exactly `insufficient evidence`.
- Required checks and the Compose smoke pass.
- The release report records model/container revisions, metrics, limitations, and known failure
  classes.

### Outcome (2026-09-16)

Issue #10 completed the first CLI release gate on one DGX Spark. A clean public branch validated
Compose and built from locked dependencies. A separately named empty PostgreSQL volume ingested all
5,183 documents, and a second full ingest preserved the exact document tuple digest, all seven
representation counts, 5,183 BM25 vectors, and the 8,306,688-byte BM25 index before a successful
live BM25 query.

Acceptance exposed and corrected one adapter defect: 512 documents expanded to 15,256
representation rows and exceeded PostgreSQL's 65,535 bind-parameter limit. Representation inserts
are now partitioned below a bound derived from the table column count while the document upsert,
BM25 update, delete, and every partition remain in one transaction. Focused unit and PostgreSQL
tests cover bounded statements and later-partition rollback.

The fixed four-case live artifact retained eight whole-document/adaptive rows with zero failures,
valid supplied-parent citations, correct selected-sample stances, exact `insufficient evidence`
with no citations, and association language for the qualified antidepressant example. Two direct
default `ask` calls separately confirmed supported citation behavior and exact insufficiency. The
initial loopback-only ColBERT network failure remains retained rather than being erased. See
`docs/reports/issue-10-cli-acceptance.md` for the evidence boundary and artifact digests.

## Phase 6: add composition adapters

Status: complete. HTTP was accepted under Issue #11, MCP under Issue #12, and the final small web
adapter under Issue #13 on 2026-09-17.

After the CLI proof is accepted, expose the same application services through thin adapters in
this order:

1. HTTP API;
2. MCP server;
3. small web UI.

Adapters may translate transport schemas, authentication, and presentation, but they must not own
retrieval, ranking, context selection, generation policy, or citations. Contract tests must submit
the same request through CLI and each new adapter and compare the normalized application result.

The web UI should remain an evidence inspection surface, not a second application architecture. It
should show the answer, parent citations, supplied evidence text, and the active strategy names.

The accepted HTTP slice exposes only health, search, and ask through FastAPI/Uvicorn. It preserves CLI
limits, strategy enums, dataclass results, exact insufficiency, and parent citations; the Compose
port is host-loopback only. Completion requires full engineering checks plus retained live parity
for one supported and one insufficient-evidence case. That gate passed on the DGX Spark with all
citations constrained to supplied parents and exact insufficiency retained.

The MCP slice exposes exactly `search_scifact` and `answer_scifact` through the official Python SDK
v2.2.0 at `http://127.0.0.1:8091/mcp`. It preserves the same limits, strategies, structured result
fields, exact insufficiency, and parent citations. One refusal-only pre-dispatch validator closes
the SDK's unknown-argument and rejected-value-disclosure gaps before application resolution. Unit,
schema, failure, Compose, and normalized CLI-parity checks passed. The official URL client also
passed discovery, supported-answer, exact-insufficiency, parent-citation, and invalid-input gates;
the retained evidence is in `docs/reports/issue-12-mcp-acceptance.md`.

The web slice serves one packaged evidence inspector from the existing FastAPI process at `/` and
uses same-origin calls to the accepted search and answer endpoints. It adds no runtime dependency,
service, port, CORS policy, or application semantics. The page shows answers, active strategies,
parent citations, ordered evidence, document IDs, scores, and complete supplied evidence text;
exact insufficiency and bounded error states remain explicit. ADR-0034 records the same-process
boundary. Issue #13 requires retained supported, insufficient-evidence, validation, and unavailable
browser evidence plus deterministic delivered-document and CSS checks for responsive, focus, and
reduced-motion behavior before acceptance.

That acceptance is complete. The retained report records cited-answer rendering, exact
insufficiency with evaluated evidence preserved, bounded validation and unavailable states,
API-only restoration, packaged resources, accessibility markers, and explicit local-only limits.

Issue #25 delivered the static GitHub Pages showcase. Issue #27 adds its optional live-readiness
link and the opt-in public-demo application boundary. The recording and offline fallback remain the
durable public artifacts; the anonymous live path is disabled by default and, when enabled, uses
only the single-worker API while inference and storage remain on the DGX. It has no uptime,
clinical-use, or supported-third-party-API commitment. VPS edge deployment is maintained in the
separate `vps-srv` repository under its own plan and acceptance boundary. Eleven matrix rows are
provisionally complete; M09 and the API-only rollback exercise remain pending. Issue #27 remains
open until those checks, final exact-revision SciFact CI, and independent cross-repository
approval are complete.

## Handoff to the template program

Template/Pi effectiveness belongs to `agentic-project-template`, not to a SciFact product phase.
The original sequencing guard is satisfied by the completed prototype. The receiving
[program roadmap](https://github.com/stauntonjr/agentic-project-template/blob/docs/scifact-program-handoff/docs/project/roadmap.md)
and [Issue #59](https://github.com/stauntonjr/agentic-project-template/issues/59) own the retrospective,
matched template comparison, and any later smaller-model Pi evaluation. SciFact contributes its
retained acceptance evidence; no SciFact feature, harness expansion, or model run is required.

## Explicit deferrals

The following are not active work:

- RankZephyr effectiveness evaluation;
- fusion-weight or threshold sweeps;
- query-side coreference rewriting;
- supervised training on SciFact labels;
- Apache AGE;
- graph-based candidate generation;
- a learned graph ranker;
- LangGraph orchestration;
- production or multi-node deployment;
- tool-calling by the generator;
- bespoke template-adoption evaluation;
- weaker-model or Pi optimization.

A deferred item may be activated only by a measured failure, an accepted decision, and a bounded
Issue that identifies what current approach cannot do.

## Stop rules

To prevent activity from replacing progress:

- Do not add a representation, scorer, model, or storage technology without a named hypothesis and
  fixed comparison.
- Do not run more than two development diagnostics for one hypothesis before reviewing the result.
- Do not tune on the already-inspected 300-query test qrels.
- Do not promote a component because it improves candidate oracle metrics while final ranking or
  answer quality regresses.
- Do not build graph retrieval before candidate-scoped graph scoring demonstrates unique signal.
- Do not build a workflow engine for a deterministic pipeline.
- Do not expand the template or its test corpus to make this application pass.
- Stop a phase when its exit gate is met or its hypothesis fails; record the decision before
  beginning another architecture branch.

## Completion and optional successors

There are no remaining implementation obligations for the accepted prototype. CLI, HTTP, MCP,
and web acceptance are complete under Issues #10–#13; the repository's main branch contains that
work. Completion is not a claim of production readiness, general scientific reasoning, or clean
generalization from the repeatedly inspected SciFact evaluation data.

Future scientific research and deployed-service requirements are new scope. The
[dataset assessment](../research/2026-09-17-lattice-evidence-data.md) and
[proposed research plan](../superpowers/plans/2026-09-17-scientific-evidence-successor.md) explore a
separate Lattice-informed direction; they do not reopen Phase 4 or authorize experiments.
Corpus proposition extraction, PostgreSQL projection, and graph scoring remain deferred.

## Evidence and decision artifacts

Each measured phase produces:

- a machine-readable run manifest;
- immutable per-query results;
- one aggregate report with paired comparisons;
- a short error analysis tied to retained query IDs;
- an ADR confirming, superseding, or rejecting the attempted default or architecture;
- an updated leaderboard when retrieval or ranking metrics are applicable;
- an updated handoff that names the next active gate.

The report must distinguish implemented behavior, engineering verification, development evidence,
validation evidence, already-inspected test evidence, and live product examples. No category may be
used as a substitute for another.
