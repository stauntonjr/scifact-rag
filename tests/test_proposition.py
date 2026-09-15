from __future__ import annotations

import math
from dataclasses import replace

import pytest

from scifact_rag.proposition import (
    ExtractionCoverage,
    GroundedProposition,
    GroundedSpan,
    PropositionPolarity,
    PropositionQualifier,
    QualifierRole,
    SourceKind,
    evaluate_extraction_coverage,
    proposition_identity,
    score_proposition_pairs,
    source_digest,
    validate_propositions,
)


def _span(source: str, text: str) -> GroundedSpan:
    start = source.index(text)
    return GroundedSpan(start=start, end=start + len(text), text=text)


def _proposition(
    source: str,
    *,
    source_id: str,
    subject: str,
    predicate: str,
    object_: str,
    polarity: PropositionPolarity = PropositionPolarity.POSITIVE,
    qualifier: tuple[QualifierRole, str] | None = None,
) -> GroundedProposition:
    qualifiers = (
        (PropositionQualifier(qualifier[0], _span(source, qualifier[1])),)
        if qualifier is not None
        else ()
    )
    return GroundedProposition(
        source_kind=SourceKind.DOCUMENT,
        source_id=source_id,
        source_sha256=source_digest(source),
        sentence=GroundedSpan(0, len(source), source),
        subject=_span(source, subject),
        predicate=_span(source, predicate),
        object=_span(source, object_),
        polarity=polarity,
        qualifiers=qualifiers,
    )


def test_grounded_propositions_require_exact_source_spans_and_unique_identities() -> None:
    source = "In mice, aspirin did not reduce fever."
    proposition = _proposition(
        source,
        source_id="doc-1",
        subject="aspirin",
        predicate="reduce",
        object_="fever",
        polarity=PropositionPolarity.NEGATIVE,
        qualifier=(QualifierRole.SPECIES, "mice"),
    )

    validate_propositions(source, (proposition,))
    assert proposition.subject.canonical_key == "aspirin"
    assert GroundedSpan(0, 9, "—Aspirin—").canonical_key == "aspirin"
    assert proposition_identity(proposition) == proposition_identity(proposition)
    assert len(proposition_identity(proposition)) == 64

    invalid = (
        replace(proposition, source_sha256="0" * 64),
        replace(proposition, subject=GroundedSpan(10, 17, "ibuprofen")),
        replace(proposition, object=GroundedSpan(0, 5, "fever")),
        replace(proposition, sentence=GroundedSpan(0, 8, source[:8])),
        replace(proposition, polarity="negative"),  # type: ignore[arg-type]
        replace(
            proposition,
            qualifiers=(PropositionQualifier("species", proposition.qualifiers[0].span),),  # type: ignore[arg-type]
        ),
    )
    for candidate in invalid:
        with pytest.raises((TypeError, ValueError)):
            validate_propositions(source, (candidate,))
    with pytest.raises(ValueError, match="duplicate proposition"):
        validate_propositions(source, (proposition, proposition))


def test_pair_features_follow_frozen_formulas_and_stable_tie_break() -> None:
    claim_source = "Aspirin reduces fever in adults."
    claim = replace(
        _proposition(
            claim_source,
            source_id="claim-1",
            subject="Aspirin",
            predicate="reduces",
            object_="fever",
            qualifier=(QualifierRole.POPULATION, "adults"),
        ),
        source_kind=SourceKind.CLAIM,
    )
    document_source = "In adults, aspirin does not lower fever."
    document = _proposition(
        document_source,
        source_id="doc-1",
        subject="aspirin",
        predicate="lower",
        object_="fever",
        polarity=PropositionPolarity.NEGATIVE,
        qualifier=(QualifierRole.POPULATION, "adults"),
    )
    alternative_source = "Fever changes aspirin."
    alternative = _proposition(
        alternative_source,
        source_id="doc-1",
        subject="Fever",
        predicate="changes",
        object_="aspirin",
    )
    cosine = {
        ("Aspirin", "aspirin"): 0.8,
        ("Aspirin", "fever"): -0.2,
        ("fever", "aspirin"): -0.4,
        ("fever", "fever"): 1.0,
        ("reduces", "lower"): 0.6,
        ("adults", "adults"): 1.0,
    }

    features = score_proposition_pairs(
        (claim,),
        (document,),
        lambda left, right: cosine[(left, right)],
    )

    assert features.entity == pytest.approx(1.0)
    assert features.predicate == pytest.approx(0.8)
    assert features.argument_direction == pytest.approx(0.6)
    assert features.polarity == -1.0
    assert features.qualifier == 1.0
    assert features.proposition_pair_mean == pytest.approx((1.0 + 0.8 + 0.8 + 0.0 + 1.0) / 5)
    assert features.claim_proposition_id == proposition_identity(claim)
    assert features.document_proposition_id == proposition_identity(document)

    always_equal = lambda _left, _right: 0.0
    tied = score_proposition_pairs((claim,), (document, alternative), always_equal)
    assert tied.document_proposition_id == min(
        proposition_identity(document), proposition_identity(alternative)
    )
    with pytest.raises(ValueError, match="at least one"):
        score_proposition_pairs((claim,), (), always_equal)
    with pytest.raises(ValueError, match="finite cosine"):
        score_proposition_pairs((claim,), (document,), lambda _left, _right: math.nan)


def test_extraction_coverage_gate_uses_predeclared_thresholds() -> None:
    boundary = ExtractionCoverage(
        total_sources=1000,
        schema_valid_sources=990,
        total_claims=160,
        usable_claims=160,
        total_candidate_documents=800,
        usable_candidate_documents=760,
        decisive_documents=120,
        usable_decisive_documents=120,
        audit_documents=100,
        usable_audit_documents=100,
        target_documents=700,
        usable_target_documents=700,
    )
    assert evaluate_extraction_coverage(boundary).passed

    failures = {
        "schema-valid-sources": replace(boundary, schema_valid_sources=989),
        "usable-claims": replace(boundary, usable_claims=159),
        "usable-candidate-documents": replace(boundary, usable_candidate_documents=759),
        "usable-decisive-documents": replace(boundary, usable_decisive_documents=119),
        "usable-audit-documents": replace(boundary, usable_audit_documents=99),
        "usable-target-documents": replace(boundary, usable_target_documents=699),
    }
    for expected, coverage in failures.items():
        result = evaluate_extraction_coverage(coverage)
        assert not result.passed
        assert expected in result.failed_conditions
