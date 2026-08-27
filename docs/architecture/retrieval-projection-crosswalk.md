# SciFact and Procurement retrieval-projection crosswalk

Status: accepted direction and implemented SciFact boundary as of 2026-08-26. This document does
not claim a shared package, a Procurement second vertical, or implemented Procurement vector/graph
adapters.

## Repository roles

SciFact remains the greenfield retrieval application built from the agentic project template. It
owns public-corpus adapters, PostgreSQL and model mechanics, retrieval experiments, DGX Compose,
metrics, and the leaderboard.

Procurement Intelligence Lab remains a separate application and the likely owner of generalized
evidence-intelligence semantics. Its current platform contracts define evidence, assertion-ledger,
scope, and rebuildable retrieval-projection lifecycles. Its accepted architecture keeps Postgres
canonical and lexical/vector/graph indexes derived. SciFact neither imports nor copies those
contracts in this slice.

The agentic project template owns neither runtime architecture. It retains inactive capability
skeletons and activation guidance only.

## Concept mapping

| SciFact concept | Procurement direction | Current ownership |
|---|---|---|
| `EvidenceDocument` and matched passage | Artifact/evidence reference | SciFact application; future semantic alignment |
| Extracted scientific proposition | Source assertion, not truth | Deferred SciFact graph slice; future shared semantics |
| BM25 or dense candidate index | Rebuildable lexical/vector projection | SciFact adapter implemented; Procurement generic lifecycle implemented |
| Proposition graph | Rebuildable graph projection | Deferred in both applications |
| `RetrievalSignal` | Projection hit plus provenance and epistemic status | SciFact ranking implementation |
| `CandidateFeatureMatrix` | Query-local projection-score table with provenance | SciFact ranking implementation; possible neutral contract after two consumers |
| Candidate scorer | Projection-specific scoring strategy | SciFact application port; candidate for later extraction |
| Score normalizer and ranking policy | Projection-score transformation and setwise ordering | SciFact application ports; no learned policy yet |
| Leaderboard run | Benchmark manifest and result | SciFact validation evidence |
| Final retrieved evidence | Evidence-preserving application result | Separate application behavior |

## Dependency direction

```text
current:
  SciFact domain/application <- SciFact ports <- SciFact adapters
  Procurement platform       <- Procurement verticals/adapters

forbidden in this slice:
  SciFact -> Procurement application package
  Procurement platform -> SciFact
  Agentic template -> either runtime architecture

future candidate after two-consumer evidence:
  neutral evidence/retrieval contracts <- SciFact adapter
                                       <- Procurement adapter
```

## Projection invariants carried forward

- Extracted propositions are evidence-bearing assertions, not canonical scientific truth.
- Every graph node or relation must retain its document and exact evidence-span provenance.
- Lexical, vector, and graph structures are rebuildable derived projections.
- Projection configuration and implementation versions must be explicit before shared extraction.
- Similarity or graph-path scores do not silently become epistemic status.
- Normalized fusion features do not silently become relevance probabilities or confidence.
- A failed or stale future projection must be visible rather than served as current evidence.

The current pooled-ranking implementation establishes scoring provenance but does not yet implement
the full projection build, freshness, failure, deletion, or assertion-ledger lifecycle. Those
responsibilities remain owned by the inactive `semantic-evidence-ledger` capability until a
separate owner-approved activation replaces its empty contract.

## Promotion gates

1. The SciFact pooled scorer boundary passes focused, integration, full, and independent checks.
2. A separately scoped proposition-graph scorer improves the frozen validation boundary or
   produces decisive error-analysis evidence while preserving exact source spans.
3. Procurement's next-vertical gate is ready and a canonical work item selects SciFact or another
   candidate; no active second vertical is inferred from this document.
4. Two consumers demonstrate the same stable semantic contract before shared code is extracted.
5. Shared extraction chooses a neutral package and versioning boundary rather than a direct
   dependency on either application.
