# SciFact RAG roadmap

Date: 2026-09-14

Owner: Jack Rory Staunton

Status: active

## Purpose

This roadmap turns the working SciFact RAG prototype into a measured, inspectable scientific
evidence application before adding more interfaces or agent-development evaluation. It orders work
by product value:

1. prove which evidence context should reach generation;
2. select a retrieval-default recommendation through one frozen comparison with its previously
   inspected evidence boundary disclosed;
3. add explicit scientific inference and stance scoring;
4. add a proposition graph as another evidence-grounded scorer;
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
| Generation | Corrected 160-claim automatic validation retains whole-document as default; adaptive is the one canonical chunk-aware policy and the frozen human review is pending | Do not rerun or tune on SciFact validation; complete the blinded review before closing Phase 1 |
| Scientific reasoning | Synonymy, polarity, negation, contradiction, and cross-sentence inference are not explicit scores | Retrieval relevance must not be mistaken for support or contradiction |
| Graph | Candidate/scorer provenance can accept another channel; proposition extraction and graph storage are not implemented | Graph scoring can be added without rewriting retrieval, but must be separately measured |
| Interfaces | CLI is active; HTTP, MCP, and web UI are inactive | New interfaces remain out of the current product proof |
| Planning | The public repository and bounded Issues exist; no dedicated SciFact roadmap Project is required for the current CLI proof | This document and accepted ADRs define sequence; each new architecture phase still needs a bounded Issue |

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

Scientific verification and proposition-graph scores will enter through complete scorer channels.
They will see the broad deduplicated candidate pool, not only the documents surviving an earlier
top-10 ranking. This prevents first-pass recall from acting as an unjustified gate on second-pass
evidence.

LangGraph is not part of the current topology. The path is a deterministic request pipeline with
replaceable ports, not a stateful agent workflow. Reconsider LangGraph only if the product gains a
real need for resumable branching, human review checkpoints, tool-driven generation, or durable
multi-step recovery that cannot remain clear in ordinary application services.

## Roadmap summary

| Order | Phase | Product result | Gate to proceed |
|---:|---|---|---|
| 0 | Establish the execution boundary | Reproducible manifests and canonical work items | Evaluation inputs and immutable settings recorded |
| 1 | Evaluate generation context | Whole-document control versus canonical adaptive chunking | Automatic decision recorded; frozen human review completed |
| 2 | Select the retrieval default | One defensible default plus retained opt-in experiments | Validation gate passed without test-set tuning |
| 3 | Add scientific inference scoring | Support, contradiction, and insufficiency become explicit evidence | Fixed validation comparison demonstrates useful incremental signal |
| 4 | Add proposition-graph scoring | Candidate-scoped graph evidence becomes a provenance-bearing ranking channel | Graph scorer improves a predeclared metric or closes a characterized failure set |
| 5 | Harden and release the CLI proof | Reproducible end-to-end application release | Clean DGX run and retained acceptance report pass |
| 6 | Add composition adapters | API, MCP, and small web UI reuse the same application services | CLI semantics remain unchanged across adapters |
| 7 | Evaluate the template and weaker models | Separate evidence about agent-development effectiveness | Product proof is already accepted |

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

## Phase 4: add proposition-graph scoring

### Goal

Represent the scientific relations inside the broad candidate pool so ranking and context assembly
can reason over entities, predicates, arguments, polarity, qualifiers, and evidence spans.

### Representation

Persist rebuildable, typed PostgreSQL projections for:

- documents and exact source spans;
- entity mentions and canonical entity records;
- propositions or triples;
- subject, predicate, object, and qualified argument roles;
- polarity, modality, population, intervention, comparator, outcome, and study-context qualifiers;
- provenance from every node and edge back to the document and exact evidence text;
- extractor model/revision, extraction time, and projection version.

Extracted propositions are source assertions, not accepted scientific truths. Similarity, graph
paths, and repeated assertions must never silently become epistemic status.

### Construction topology

1. Extract and persist propositions once as a rebuildable corpus projection.
2. Retrieve the broad lexical/vector candidate pool for a query.
3. Construct an induced query-time graph from every candidate in that pool, before final top-k
   ranking.
4. Link query entities and relations to candidate propositions while retaining ambiguous matches.
5. Emit one or more complete graph-derived scorer channels into the existing candidate feature
   matrix.
6. Let the ranking policy combine or select those scores under a separately frozen rule.

This design gives the graph access to candidates that could move substantially in the second pass.
It does not restrict graph scoring to first-pass top-10 results.

### First graph signals

The first fixed comparison should expose interpretable, untrained features:

- canonical entity overlap;
- predicate or relation compatibility;
- subject/object argument alignment;
- polarity and negation agreement or conflict;
- qualifier compatibility;
- shortest evidence-bearing path length;
- count of independent evidence spans without treating the count as truth.

Do not begin with learned fusion weights. Preserve every raw feature and its provenance so later
ranking policies can be evaluated without re-extracting the corpus.

### Storage decision

Use ordinary typed PostgreSQL tables and recursive SQL first. Apache AGE remains deferred until a
measured query or maintenance limitation cannot be expressed acceptably in that representation.
Graph retrieval as an independent candidate generator is also deferred; scoring the existing broad
pool is the first hypothesis.

### Exit gate

- Every graph score is traceable to exact source spans and extractor provenance.
- A fixed ablation compares the graph channel with the Phase 2 default and Phase 3 verifier.
- Promotion requires improved predeclared ranking or stance metrics, or a material reduction in a
  predeclared scientific-inference failure category.
- If the graph adds no unique signal, preserve the schema and report; do not expand to AGE, graph
  candidate generation, or learned graph ranking.

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

## Phase 6: add composition adapters

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

## Phase 7: evaluate the template and weaker-model development

This is a separate program-level goal and cannot delay the SciFact product proof.

After the CLI release gate passes:

- record which template capabilities were activated and why;
- compare actual delivery friction with the earlier greenfield observations;
- define a bounded with-template versus without-template evaluation only if an existing framework
  can be adopted cheaply;
- evaluate whether a weaker model in Pi becomes more effective with the accepted template;
- keep Pi adapter development, additional harness tests, and template-security expansion outside
  the SciFact application roadmap unless a concrete application failure activates them.

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
- HTTP, MCP, or web work before the CLI release gate;
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

## Planned work items

Create these Issues in order, splitting only when a reviewer could accept one result and reject the
next:

1. Freeze generation-evaluation manifest and run-artifact contract.
2. Retain the completed whole-document versus adaptive automatic comparison and its historical
   three-name evidence.
3. Complete the frozen blinded human review and close the generation-context decision without
   post-result tuning.
4. Compare the three frozen retrieval-default candidates on validation.
5. Decide and document the retrieval default.
6. Add one fixed scientific stance/inference scorer.
7. Define the proposition and provenance schema in an ADR.
8. Implement corpus proposition extraction and typed PostgreSQL projection.
9. Add candidate-scoped induced-graph scoring and its fixed ablation.
10. Complete the CLI release gate and publish the acceptance report.
11. Add HTTP, MCP, and web adapters as separate post-release Issues.
12. Decide whether to begin the separate template/Pi effectiveness program.

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
