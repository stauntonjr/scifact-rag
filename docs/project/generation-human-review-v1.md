# Generation groundedness review v1

## Purpose

This protocol freezes the human-review subset for the repaired Phase 1 generation-context
comparison before its outputs are generated. It measures evidence grounding and material
scientific overstatement without an LLM judge. It cannot promote a default because Issue #5 did
not predeclare a numerical non-inferiority margin before the first validation result was opened.

## Fixed selection

The population is the 160-row validation input with SHA-256
`34084490c48515f0c788da0960d7f426c0e64e4dcf9431b8721d824ba0349105`. Long cases are those whose
preflight row has `long_cited_parent_retrieved=true`.

For each stratum, sort eligible query IDs by the hexadecimal SHA-256 of
`scifact-generation-human-review-v1\0{query_id}` and take the requested count:

| Stratum | SUPPORT | CONTRADICT | NOT_ENOUGH_INFO | Total |
|---|---:|---:|---:|---:|
| Long/retrieved | 5 | 4 | 3 (all available) | 12 |
| Other | 4 | 4 | 4 | 12 |

The resulting fixed query IDs, listed without their expected stance for the review handoff, are:

```text
30 1115 953 1084 933 1120 886 1360 952 1053 1085 1052
1340 846 441 863 330 772 927 341 1387 622 689 422
```

This selection uses only query ID, public annotations, and the pre-run retrieval/length preflight.
It does not inspect generated text or answer metrics.

## Blinded worksheet

After generation, create one row per distinct `(query_id, supplied_contexts, raw_generated_text)`.
Do not duplicate a row for a policy whose exact prompt reused an earlier response. Assign opaque
response IDs by sorting SHA-256 of
`scifact-generation-human-review-order-v1\0{query_id}\0{context_strategy}`. The reviewer-facing
worksheet must include the claim, supplied title/text evidence, answer, and document IDs, but omit:

- policy name and reuse source;
- expected and predicted stance;
- automatic correctness, evidence-recall, citation-validity, token, and latency fields; and
- aggregate results.

Retain a separate mapping from opaque response ID to query ID, policy, and raw-result identity so
the completed review can be joined without modifying raw model output.

## Human rubric

For every distinct answer, record these fields:

| Field | Allowed values | Question |
|---|---|---|
| `grounded` | `yes`, `no`, `uncertain` | Is every material answer claim directly supported by the supplied evidence? |
| `material_overstatement` | `none`, `present`, `uncertain` | Does the answer materially strengthen association, causality, population, intervention, comparison, outcome, or certainty beyond the evidence? |
| `negation_omission` | `yes`, `no`, `not_applicable`, `uncertain` | Is a material negation lost? |
| `qualifier_omission` | same | Is a material limitation or qualifier lost? |
| `population_omission` | same | Is the studied population changed or omitted materially? |
| `intervention_omission` | same | Is the intervention or exposure changed or omitted materially? |
| `comparison_omission` | same | Is the comparator changed or omitted materially? |
| `outcome_omission` | same | Is the measured outcome changed or omitted materially? |
| `notes` | free text | Cite the smallest evidence/answer span needed to explain a non-pass or uncertainty. |

The human reviewer records their identity and UTC completion time. `uncertain` is not silently
treated as a pass. Automatic stance and citation scores remain separate from this rubric.

## Interpretation boundary

The corrected validation execution may characterize whole-document versus DP context and verify
the measurement path. It may not choose a new default. Whole-document remains the compatibility
default unless a later, prospectively margined decision run and completed human review authorize a
change.
