# Scientific evidence fidelity and Lattice transfer research plan

> For execution: use the repository engineering loop for an approved bounded issue. This is a
> prospective research plan for owner review, not permission to implement or run its experiments.

**Goal:** Determine which scientific distinctions a compact source-grounded representation must
preserve, and supply evidence that can guide a later Lattice workspace experiment.

**Architecture:** Keep the completed SciFact application stable. Develop a finite offline
diagnostic over native annotations, separating evidence selection, semantic extraction, and state
use. Transfer specifications and small versioned results to Lattice, not a cross-repository service.

**Tech stack:** Existing Python application/evidence contracts and an already available fixed
local reader, selected and pinned in the prospective run manifest. No new model service or graph DB.

**Research basis:** [Dataset assessment](../../research/2026-09-17-lattice-evidence-data.md).
Status: proposed successor; no new SciFact research issue or experiment has been activated.

## Constraints and decision

- SciFact's prototype is complete. Template effectiveness is owned by
  [agentic-project-template #59](https://github.com/stauntonjr/agentic-project-template/issues/59).
- Lattice's sole active plan remains the full-training-set Re-DocRED native extraction baseline
  at DGX `e2051f4`. Do not change its objective, budget, thresholds, held-out access, or artifacts.
- Keep source selection, extraction quality, reader utility, interventions, and cost as separate
  evidence. External serialized propositions do not establish a latent LM workspace.
- Start with **Evidence Inference 2.0 admission** for the role-sensitive question. QASPER is the
  alternative for long-document QA, not a drop-in replacement under the same hypothesis.
- Do not collapse comparative-effect labels into SciFact stance or insufficiency classes. Supplied
  ICO prompts are supplied semantic roles, not successful role induction. Population extraction
  and broad biomedical synonym resolution are not supervised by this proposed first task.
- Keep the public test split unopened for outcome inspection. Project novelty is not proof of
  absence from base-model pretraining. All train-side diagnostics remain development evidence.
- No paid APIs, training, sweep, public-test run, source normalization, fuzzy span acceptance,
  graph infrastructure, or deployment changes are authorized by this plan.

## Step 1 — Admit the corpus without a model

Proposed issue title: “Admit Evidence Inference 2.0 for role-sensitive evidence diagnostics.”
Create this issue only after the owner selects the proposed direction. It owns admission only.

Proposed retained files:

- `docs/research/evidence-inference-admission.md`: source/license and annotation audit.
- `artifacts/evidence-inference-v2/source-manifest.json`: ignored local raw-file identities,
  publisher URLs, archive and file SHA-256, license/provenance, and split IDs.
- `docs/research/evidence-inference-admission-summary.json`: small publishable counts, hashes,
  inclusion rules, failures, and decision; no article text.

Acquire the publisher's v2.0 archive into a fresh ignored path. Inventory without displaying
evaluation records. Audit per-article license/provenance and reconcile actual files to the v2.0
publication; the older GitHub repository must not stand in for the acquired release.

Inspect at most 64 training articles, selected by sorted SHA-256 of `ei-admission-v1:<article-id>`.
Use native document grouping; all prompts from an article must stay in the same partition. Count
valid labels, disputed/invalid annotations, evidence availability, text lengths, article overlap,
role multiplicity, and split collisions. Verify offsets against the publisher text, including the
actual release's inclusive/exclusive convention. A deterministic end-offset conversion is allowed
only when documented by the release and verified; do not repair text or silently drop failures.

**Exit:** reproducible provenance, permitted use, disjoint article partitions, explicit annotation
semantics, exact-match coverage, and an inclusion policy derived only from train-side inspection.
If the data cannot support the proposed task, stop. An explicitly selected QASPER alternative gets
its own admission note and task definition. Do not run a model to conceal an admission problem.

## Step 2 — Locate the bottleneck with one fixed reader

This is a separate execution decision after admission. Reuse an existing reader endpoint only if
its model/runtime identity and output contract can be frozen; no model comparison is needed.
Define a native three-label classifier as a diagnostic adapter, without changing SciFact's public
`ask` contract. Labels are reported increase, decrease, and no significant difference. Invalid
model responses are explicit failures, never remapped to the third class.

Use at most 128 valid training prompts, article-grouped and selected by a seeded hash, independent
of outcomes. Freeze IDs, selection, prompt, decoding, evidence budget, metrics, and label aggregation
before dispatch. Prefer one already-valid native verified answer; retain disagreements and specify
the released aggregation rule rather than inventing a majority after seeing model outputs.

Compare three inputs to the **same fixed reader**:

1. Full publisher text when it fits the reader's declared input budget. Record overflow as a
   separate coverage stratum; do not silently truncate and call it full-text performance.
2. Existing SciFact-style bounded evidence selection adapted within the known source article.
   This is within-document selection, not open-corpus retrieval; do not report corpus recall.
3. Gold evidence text with ICO query, but **without the gold class**. Label this oracle-evidence
   diagnostic. It bounds selection error and is not a deployable baseline.

Cap at 384 first requests (128 per arm), no automatic retries, and no training. Before approval,
measure a small train-only service/latency preflight and publish a concrete wall-time/compute cap;
do not use a vague “one DGX” budget. Persist started/completed/unknown requests and sanitised failure
details at fresh paths. No service restarts or interference with Lattice GPU work.

Report native macro-F1 and per-class precision/recall, evidence precision/recall against valid
reference sets, exact grounding coverage, failures, input/output tokens, latency, and article-level
paired uncertainty. Do not bootstrap prompts as independent when they share a paper. Full-context
and selected-context arms measure quality/cost tradeoffs, not equal-compute superiority.

**Decision:** if oracle evidence does not improve the fixed reader, inspect reader/label handling
before investing in selection. If oracle helps but selection misses it, address selection. If
both preserve evidence yet role errors remain, a compact role representation is a defensible next
hypothesis. Small train-side results are descriptive; no significance or generalization claim and
no automatic continuation follows from any score.

## Step 3 — Test representation fidelity only if Step 2 motivates it

Design one new comparison, not a graph system. Give two paths the identical selected evidence:
raw evidence to the reader versus a compact extracted role record to that same reader. A frozen
writer may copy text/IDs; code resolves exact spans and rejects ambiguous matches. Preserve invalid
payload diagnostics separately. Do not ask the writer to calculate character offsets.

The writer must not see reference answers, evidence labels, or evaluation annotations. The
representation may contain its own predicted effect; score that prediction separately so a reader
merely echoing it cannot be described as independent reasoning. No hidden raw-text channel may
reach a claimed state-only reader. Charge writer, storage, reader, and setup costs together.

Measure role/order fidelity, effect preservation, coverage, and end-task quality. Use same-article
wrong-outcome distractors and reference-backed comparator contrasts where native annotations
support them. Arbitrary intervention/comparator swaps are not automatically valid new clinical
claims; construct paired labels only after checking scope and numerical/linguistic semantics.

Include explicit state deletion, wrong-record, role-swap, and serialization controls. A successful
external-state result demonstrates a representation interface and sensitivity, not spontaneous
induction, internal computation, or native hypergraph advantage. If exact grounding or semantic
fidelity fails, preserve that result and stop before corpus-scale extraction or graph work.

## Step 4 — Hand the evidence to Lattice without replacing its plan

After Lattice's active native baseline has been evaluated, review whether its remaining errors
overlap the role/evidence failure taxonomy. Transfer only source manifests, task definitions,
native label mappings, diagnostic reports, and source-grounded fixtures allowed by license.

A later Lattice experiment must separately specify a learned writer, persisted state, source-free
reader, and interventions; compare matched native/pairwise/unstructured controls where relevant.
Reuse the existing `semantic_ir_v1` and `lattice_lm.harness.result_io` boundaries. Supplied ICO
roles, external extractors, and oracle evidence cannot stand in for induced latent semantics.
Do not infer that success on clinical ICO will transfer from Wikipedia binary relations.

Before any outcome-based tuning, freeze a paper-disjoint development/confirmation design. Keep
official test sealed until a single confirmatory design is accepted. Select fresh internal
qualification items that were not used to develop the adapter. Repeatedly inspecting a new corpus
would recreate SciFact's evaluation limitation.

## Deliverable and stop boundary

The next executable work should be **Step 1 only**, after selection of this proposal. Its result is
an admission report and a yes/no decision on feasibility, not a trained model. Steps 2–4 are ordered
research choices, each requiring its own accepted question and bounded issue. They are not promises
to finish a new multi-phase project. Productization, graph storage, and template-effectiveness
experiments remain separate programs.
