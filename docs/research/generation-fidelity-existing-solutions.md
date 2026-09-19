# Generation-fidelity evaluation alternatives

- Date inspected: 2026-09-18
- Governing issue: [#26](https://github.com/stauntonjr/scifact-rag/issues/26)
- Decision: whether to reuse an existing public evaluation set or adapt the repository's
  evaluation contracts around a later project-sealed SciFact-like cohort
- Scope: model-free evaluation foundations only; no dataset acquisition or model execution
- Stop condition: enough primary evidence to decide the Issue #26 implementation boundary

## Constraints and comparison dimensions

The accepted product answers questions from retrieved scientific abstracts and must preserve
material qualifiers, population or species, causal strength, comparator, outcome, and uncertainty.
Issue #26 needs a development boundary that cannot be mistaken for untouched confirmation.

Candidates were compared on task fit, project exposure, prospective sealing, evidence
annotations, article-family grouping, rights provenance, integration effort, and risk of changing
the scientific question. Current official project pages, papers, repositories, and license files
were preferred over derivative summaries. Search terms included `PubMedQA official dataset`,
`SciFact official data license`, `QASPER scientific paper QA`, and `clustered validation reporting`.

## Candidates

| Candidate | Primary evidence | Task and exposure fit | License/provenance | Disposition |
|---|---|---|---|---|
| Existing SciFact rows | [Data contract](https://github.com/allenai/scifact/blob/master/doc/data.md), [paper](https://arxiv.org/abs/2004.14974) | Best task match, but this project has inspected its train validation and BEIR test material. It is development/regression evidence, not untouched confirmation. | Claims and evidence annotations are CC BY 4.0; S2ORC abstracts are ODC-By 1.0; code is Apache-2.0 per the [official license](https://github.com/allenai/scifact/blob/master/LICENSE.md). | Keep for development only. |
| PubMedQA | [Project](https://pubmedqa.github.io/), [paper](https://aclanthology.org/D19-1259/) | Uses abstracts, but predicts yes/no/maybe for article-authored research questions. Public release and task mismatch prevent the requested project-sealed SciFact-like confirmation claim. | Repository code and bundled materials carry an [MIT license](https://github.com/pubmedqa/pubmedqa/blob/master/LICENSE); article-text provenance still needs source-specific review before redistribution. | Do not adopt as confirmation. |
| QASPER | [Paper](https://aclanthology.org/2021.naacl-main.365/) | Information-seeking QA over full NLP papers, often with abstractive answers. Switching to it would change both document length and task semantics. It is also a public benchmark. | Paper and dataset provenance must be reviewed at acquisition time; Issue #26 acquires nothing. | Defer as a separate long-document study. |
| Newly authored SciFact-like cases from independently selected articles | SciFact's atomic-claim and rationale design supplies the closest pattern, but article selection and questions would be new | Can match the product task, keep article families disjoint, and remain project-sealed if a custodian owns selection and annotation before developer access. Public source material still cannot prove absence from model pretraining. | Every source article or abstract needs recorded rights, version, digest, and attribution. No blanket license may be inferred. | Recommended later cohort path. |

Cluster-aware reporting guidance reinforces that validation data with shared higher-level units
must report and analyze the clustering rather than treat all rows as independent. The
[TRIPOD-Cluster explanation](https://www.bmj.com/content/380/bmj-2022-071058) is not adopted as a
clinical-prediction standard for this RAG system; it is supporting precedent for keeping
article-family identity explicit in the future statistical protocol.

## Build, adopt, adapt, and defer

- **Build:** bespoke model services, graders, or an autonomous critic. Rejected: unnecessary and
  outside Issue #26.
- **Adopt:** use PubMedQA, QASPER, or another public benchmark as confirmation. Rejected: task or
  exposure mismatch.
- **Adapt:** reuse the repository's strict manifests, immutable artifacts, blinded review, and
  validation challenges for a versioned fidelity boundary. Selected for Issue #26.
- **Defer:** acquire and annotate a new article-family-disjoint cohort under a custodian. Selected
  for a later owner-approved issue.

## Recommendation and confidence

**Disposition: adapt.** Implement only model-free phase, manifest, rubric, and development-fixture
contracts now. A later issue may build a project-sealed cohort from independently selected,
rights-qualified articles. It must record that project-unseen is not proof of model-unseen.

Confidence is high that the three public alternatives do not satisfy the requested combination of
task fidelity and project sealing. Cohort feasibility, annotation cost, reviewer agreement, and
statistical power remain unknown because no source pool or hidden cases were opened.

Reopen this decision if the owner changes the target task, accepts a public benchmark as
confirmation, selects a source corpus, changes the rights boundary, or authorizes model execution.
