# Dataset assessment for a Lattice-informed scientific evidence successor

Date inspected: 2026-09-17 (America/New_York). Status: research proposal, not dataset admission or
experiment authorization. Decision: **adapt** existing evidence-selection and provenance contracts;
investigate Evidence Inference 2.0 first for semantic-role fidelity. Keep QASPER as the alternative
for a different, long-document QA question. No runtime dependency, corpus, model, or capability was
added during this assessment.

## What would actually inform Lattice?

Lattice seeks a learned relational semantic workspace inside an autoregressive LM. Its current
DGX branch at [e2051f4](https://github.com/stauntonjr/lattice/commit/e2051f4a57ff7637563e757fa4f544fa04ee46d0)
has CPU-qualified Tasks 1–2 of a full-corpus Re-DocRED native extraction baseline; its current-work
record says no new GPU fit has run. The Mac planning branch at `fed38d1` agrees. The previous
four-document writer result did not generalize. Preserve the active plan and closed evidence.

Three credible directions:

1. **Role-sensitive scientific evidence fidelity — recommended bridge.** Determine whether
   evidence selection and a compact representation retain who was compared, which outcome was
   measured, and the reported direction. Distinguish selection failure, extraction failure, and
   state-use failure. This supplies realistic requirements for Lattice without claiming an external
   JSON representation proves a latent workspace.
2. **Long-document QA/context efficiency.** QASPER directly tests evidence retrieval and bounded
   context against full papers. Strong SciFact continuity; weaker native supervision for relational
   semantics. Best choice if context efficiency is the immediate objective.
3. **Immediate scientific graph or joint Lattice transfer training.** Defer. SciFact extraction did
   not qualify, and Lattice first needs its native baseline. Another jointly changing model, task,
   representation, and data source would make a negative result hard to interpret.

## Candidates and admission status

| Dataset | Fit and annotation | Access/license evidence | Decision and limits |
|---|---|---|---|
| Evidence Inference 2.0 | Full clinical trial articles, intervention/comparator/outcome prompts, directional labels, and supporting spans | Official v2.0 archive responds HTTP 200. Source repository has MIT license; per-article full-text rights and exact archive terms still need auditing | First admission target; best role-sensitive bridge. ICO is supplied, not induced; population is not a supervised prompt role |
| QASPER v0.3 | Full NLP papers, human QA and supporting evidence, including unanswerable questions | Author-linked AllenAI card states CC BY 4.0; official train/dev and test/evaluator archives respond HTTP 200 | Strong alternative for long-context evidence and abstention. Not a native relation-graph benchmark; figures/tables require explicit handling |
| ContractNLI | 607 contracts with 17 fixed hypotheses, three-way entailment and evidence-span indices | Official Stanford release states CC BY 4.0 | Useful later transfer test for negation/exceptions; domain shift and fixed hypotheses weaken its priority for scientific semantics |
| EvidenceBench / EvidenceBench-100k | Biomedical hypothesis-to-evidence selection; larger set uses LLM-generated annotations | Official repository specifies different licenses: original test CC-BY, original train/dev CC-BY-NC-SA, 100k CC-BY-NC | Defer first use: licensing and synthetic-label provenance complicate a clean independent semantic test |
| Re-DocRED / ProPara | Native relation/state supervision already present in Lattice | Governed by Lattice's existing source registry and retained artifacts | Reuse existing lessons; not a fresh SciFact successor or a reason to interrupt the active native baseline |

The Evidence Inference paper reports 12,616 prompts from 3,346 articles. Its labels describe
comparative effect direction; **no significant difference is not insufficient evidence**, nor a
generic NLI-neutral class. Supplied ICO fields allow role-use evaluation but not a claim of
unsupervised entity/role discovery. [Paper](https://aclanthology.org/2020.bionlp-1.13/).

Evidence Inference's historical annotation documentation specifies inclusive end offsets and
acknowledges imperfect or missing alignment. Do not assume those historical details are unchanged
in v2.0: inspect the acquired archive first. Preserve publisher text; record coordinate conversion
and alignment failures rather than accepting fuzzy repair. Repository MIT licensing alone is not
proof of permission to redistribute every article. [Annotation specification](https://github.com/jayded/evidence-inference/blob/a661e8c14f973398380c8865cf2f27a535aaaf6d/annotations/README.md),
[annotation process](https://github.com/jayded/evidence-inference/blob/a661e8c14f973398380c8865cf2f27a535aaaf6d/README.annotation_process.md),
[repository license](https://github.com/jayded/evidence-inference/blob/a661e8c14f973398380c8865cf2f27a535aaaf6d/LICENSE).

QASPER has 5,049 questions over 1,585 papers. Its evidence can include paragraphs and non-textual
items. A text-only first experiment must disclose exclusions and preserve all excluded counts;
neither absence of a text span nor a false yes/no answer is an unanswerable label. The official
scoring implementation provides a reference without requiring adoption of its old training stack.
[Author dataset card](https://huggingface.co/datasets/allenai/qasper/blob/fdc9d8214fbab5dd782958601db4d678e6934a54/README.md),
[baseline repository](https://github.com/allenai/qasper-led-baseline/tree/afd0fb96bf78ce8cd8157639c6f6a6995e4f9089).

Further sources: [ContractNLI publisher](https://stanfordnlp.github.io/contract-nli/),
[EvidenceBench publisher](https://github.com/EvidenceBench/EvidenceBench).
Do not use the existence of an HF mirror as independent proof of licensing, fidelity, or novelty.

## Verified access and provenance

Headers only were fetched; no archive was downloaded or evaluation record read.

| Publisher artifact | HTTP | Reported bytes |
|---|---:|---:|
| `https://evidence-inference.ebm-nlp.com/v2.0.tar.gz` | 200 | 36,528,800 |
| `https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-train-dev-v0.3.tgz` | 200 | 10,835,856 |
| `https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-test-and-evaluator-v0.3.tgz` | 200 | 3,865,061 |

These are reachability observations, not content hashes or integrity checks. Actual acquisition
must record SHA-256, version, file inventory, split identity, license files, and upstream provenance.
Evidence Inference repository inspected: `a661e8c14f973398380c8865cf2f27a535aaaf6d` (historical v1
materials must not be relabelled v2). QASPER HF metadata: `fdc9d8214fbab5dd782958601db4d678e6934a54`;
the loader points at v0.3 archives. Its default loader references test data too, so do not invoke
it blindly for a training-only admission pass.

“Fresh” means not used for this project's model/parameter selection. All candidates are public
and may have been seen during base-model pretraining. Neither provenance nor metadata search
proves contamination-free generalization. QASPER's public landing page exposed a training preview
during this research; no held-out content was intentionally opened. Search inspected dataset
documentation, including publisher examples and historical quality caveats; freeze a separate
evaluation manifest rather than treating those examples as unseen qualification cases.

## Search scope and stopping rule

Primary-source queries covered Evidence Inference 2.0 full text/license, QASPER full-paper evidence
and license, ContractNLI evidence spans/license, and EvidenceBench annotation provenance/license.
Official papers, publisher repositories, author-linked dataset cards, and download metadata were
admitted; secondary comparisons and benchmark leaderboards were not used to rank candidates.

Stop research once two viable but distinct questions and their admission risks are clear. A general
dataset/model survey would not improve the immediate decision. Next step is bounded admission of
Evidence Inference, with no model calls. If its provenance or alignment cannot support the desired
comparison, stop and choose the QASPER question explicitly; do not silently substitute benchmarks.

Capability disposition: use the active SciFact product-validation contracts for finite diagnostic
artifacts; existing application composition supplies reusable baselines. Semantic evidence ledger,
graph, durable memory, and other inactive capabilities remain not-applicable. Lattice retains its
own `semantic_ir_v1` and result-publication ownership; do not create a shared runtime or parallel
state schema merely to link the projects.
