# Generation fidelity protocol v1

## Purpose and evidence status

This protocol measures whether a candidate preserves material scientific meaning in supplied
evidence. It does not change retrieval, generation, or product defaults. Historical SciFact
outcomes are development evidence and cannot be relabeled as untouched confirmation.

The protocol separates three questions:

1. Did retrieval and assembly supply enough evidence?
2. Did generation faithfully state the supplied evidence?
3. Did the final answer remain useful when the source was answerable?

A citation-valid answer can still fail fidelity. An abstention can avoid an unsupported statement
without becoming an adequate answer.

## Phases

- `development`: visible to developers and used for fixture, prompt, and tool development.
- `stress`: visible to developers and enriched for named failure classes. Stress results are
  reported separately from a representative primary cohort.
- `confirmation`: held by a named custodian, article-family disjoint from development and stress,
  and opened once only after code, prompts, runtime, analysis, retry, and decision rules freeze.

Changing a case from one phase to another after inspecting candidate output is prohibited. Once a
confirmation outcome is inspected, that cohort becomes development evidence for every later
candidate.

## Exposure identity

One article family includes preprints, accepted manuscripts, publisher versions, corrections,
paraphrases, and prompts derived from the same scientific result. Family assignment precedes
outcome generation. Exact-text deduplication alone is insufficient.

The exposure inventory records source identity, version, content digest, article-family digest,
project use, and the earliest known inspection class. Project-unseen means only that the project
cannot identify prior developer access. It does not prove absence from model pretraining.

## Roles and access

The custodian selects, rights-qualifies, annotates, freezes, and executes confirmation cases. The
developer may see only cohort identity, counts, digests, and opaque article-family digests before
unblinding. A manifest declaration is consistency evidence, not proof of human custody.

The custodian must not select sources, questions, or exclusions from candidate outcomes. The
developer must not receive questions, evidence packages, annotations, answers, mappings, or
aggregate outcomes before the frozen run is complete.

## Grounding and answerability

Grounding is judged only against supplied context. Full-source and gold annotations separately
measure answerability, retrieval, and assembly. Missing retrieval evidence, removed assembly
evidence, and generation misstatement are distinct failure sources.

Every material answer statement is assessed for qualifier, population or species, intervention or
exposure, comparator, outcome, causal strength, negation, and uncertainty when those distinctions
affect meaning. Absence of evidence is not evidence of no effect, and non-significance is not
equivalence.

## Conservative accounting

All scheduled cases remain in denominators. Missing output, execution failure, unresolved review,
invalid citation, and incorrect abstention are reported separately and count as non-passes in the
conservative quality composite. They are not relabeled as proven hallucinations.

Report unsupported substantive answers among all scheduled cases and among substantive outputs.
Also report adequate grounded answers among answerable cases, correct insufficiency, incorrect
abstention, task correctness, citation validity, and execution failures. No one metric substitutes
for the others.

## Review and paired analysis

Baseline and candidate use identical cached contexts. Review identities are random and opaque;
arm, expected stance, automatic metrics, and aggregate outcomes remain in a separate mapping.
Reviewers see only the question or claim, supplied evidence, and answer.

Article family—not prompt—is the resampling unit. Primary and enriched stress cohorts are never
pooled into an unweighted population rate. Related questions and byte-identical outputs do not
become independent observations through duplication.

Two independently blinded confirmation reviews and adjudication are required by any later
confirmation issue. Reviewer agreement is piloted only on development material. Unresolved
judgments follow a predeclared conservative rule rather than post-result convenience.

## Freeze and stop rules

Freeze repository commit, model and runtime revision, product and diagnostic prompt digests,
decoding settings, retrieval and context configuration, request ceiling, retry policy, cohort
digest, review rules, statistical analysis, and promotion rule before confirmation access.

Stop rather than open confirmation when custody, rights, identity, budget, or statistical power is
unresolved. Stop without candidate execution when a manifest or access declaration is invalid.
Do not change prompts, thresholds, exclusions, sample size, or failure handling and rerun the same
confirmation cohort.

## Deferred proposed promotion rule

The numerical thresholds in the owner plan are proposals for a later issue. Issue #26 neither
accepts them nor produces evidence against them. A later issue must prospectively accept its own
adequate-answer guard, fidelity threshold, paired uncertainty method, cost ceiling, and failure
composite before any hidden input is released.

## Issue #26 boundary

Issue #26 implements only model-free manifest, review, challenge, and documentation contracts. It
performs no model request, latency preflight, cohort acquisition, annotation, confirmation access,
candidate selection, default change, or quality-improvement claim.
