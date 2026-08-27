from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import pytest

from scifact_rag.domain import (
    CandidateFeatureMatrix,
    CandidateFeatureRow,
    CandidateHit,
    CandidateScore,
    EvidenceChunk,
    EvidenceDocument,
    RankingFeature,
    SearchHit,
)
from scifact_rag.ports import EvidenceStore
from scifact_rag.retrievers import (
    EqualScoreFusionPolicy,
    IdentityScoreNormalizer,
    PooledRankingRetriever,
    ReciprocalRankAggregator,
    ReciprocalRankFusionRetriever,
    RerankingRetriever,
    RobustScoreNormalizer,
    StoredChunkMaxRerankerCandidateScorer,
    TitleRerankerCandidateScorer,
)


class FakeRetriever:
    def __init__(self, doc_ids: Sequence[str]) -> None:
        self._hits = [SearchHit(doc_id, doc_id, doc_id, 1.0) for doc_id in doc_ids]
        self.limits: list[int] = []

    def search(self, query: str, limit: int) -> list[SearchHit]:
        self.limits.append(limit)
        return self._hits[:limit]


class FakeReranker:
    def __init__(self, scores: Sequence[float]) -> None:
        self._scores = list(scores)
        self.documents: list[SearchHit] = []

    def score(self, query: str, documents: Sequence[SearchHit]) -> list[float]:
        self.documents = list(documents)
        return self._scores


class FakeCandidateGenerator:
    def __init__(self, name: str, doc_ids: Sequence[str]) -> None:
        self.name = name
        self._hits = [
            CandidateHit(
                EvidenceDocument(doc_id, f"title-{doc_id}", f"text-{doc_id}"),
                1.0 / rank,
                f"{name}-representation",
                rank - 1,
                f"matched-{name}-{doc_id}",
            )
            for rank, doc_id in enumerate(doc_ids, 1)
        ]
        self.limits: list[int] = []

    def generate(self, query: str, limit: int) -> list[CandidateHit]:
        self.limits.append(limit)
        return self._hits[:limit]


class FakeCandidateScorer:
    def __init__(self, name: str, scores: dict[str, float]) -> None:
        self.name = name
        self._scores = scores

    def score(
        self,
        query: str,
        documents: Sequence[EvidenceDocument],
    ) -> list[CandidateScore]:
        return [
            CandidateScore(
                document.doc_id,
                self._scores[document.doc_id],
                f"{self.name}-representation",
                7,
                f"matched-{self.name}-{document.doc_id}",
            )
            for document in documents
            if document.doc_id in self._scores
        ]


class FakeChunkStore:
    def __init__(self, chunks: Sequence[EvidenceChunk]) -> None:
        self._chunks = list(chunks)
        self.requests: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    def load_chunks(
        self,
        document_ids: Sequence[str],
        representations: Sequence[str],
    ) -> list[EvidenceChunk]:
        self.requests.append((tuple(document_ids), tuple(representations)))
        return self._chunks


def test_reciprocal_rank_fusion_rewards_agreement_and_is_deterministic() -> None:
    retriever = ReciprocalRankFusionRetriever(
        (FakeRetriever(("dense", "shared")), FakeRetriever(("shared", "keyword")))
    )

    hits = retriever.search("query", 3)

    assert [hit.doc_id for hit in hits] == ["shared", "dense", "keyword"]
    assert hits[0].score == pytest.approx(1 / 61 + 1 / 62)


def test_reranking_deduplicates_fixed_candidate_pools_and_uses_only_new_scores() -> None:
    lexical = FakeRetriever(("shared", "bm25"))
    dense = FakeRetriever(("dense", "shared"))
    reranker = FakeReranker((0.1, 0.8, 0.8))
    retriever = RerankingRetriever((lexical, dense), reranker, candidate_limit=50)

    hits = retriever.search("query", 3)

    assert lexical.limits == [50]
    assert dense.limits == [50]
    assert [document.doc_id for document in reranker.documents] == ["shared", "bm25", "dense"]
    assert [(hit.doc_id, hit.score) for hit in hits] == [
        ("bm25", 0.8),
        ("dense", 0.8),
        ("shared", 0.1),
    ]


@pytest.mark.parametrize("scores", ((0.5,), (0.5, float("nan"))))
def test_reranking_rejects_invalid_score_outputs(scores: Sequence[float]) -> None:
    retriever = RerankingRetriever(
        (FakeRetriever(("one",)), FakeRetriever(("two",))),
        FakeReranker(scores),
    )

    with pytest.raises(ValueError, match="wrong number|non-finite"):
        retriever.search("query", 2)


def test_title_reranker_scores_title_without_abstract() -> None:
    reranker = FakeReranker((0.75,))
    scorer = TitleRerankerCandidateScorer("colbert-title", reranker)

    scores = scorer.score("query", [EvidenceDocument("1", "Only title", "Never send this")])

    assert [(hit.title, hit.text) for hit in reranker.documents] == [("", "Only title")]
    assert scores == [CandidateScore("1", 0.75, "title", 0, "Only title")]


def test_chunk_reranker_scores_every_stored_view_and_keeps_per_document_max() -> None:
    representation = "coref-nominal-dp-colbert"
    store = FakeChunkStore(
        (
            EvidenceChunk("b", 1, "b later", representation, False),
            EvidenceChunk("a", 1, "a later", representation, False),
            EvidenceChunk("a", 0, "a first", representation, False),
            EvidenceChunk("b", 0, "b first", representation, False),
        )
    )
    reranker = FakeReranker((0.2, 0.9, 0.9, 0.9))
    scorer = StoredChunkMaxRerankerCandidateScorer(
        "colbert-content", cast(EvidenceStore, store), reranker, representation
    )
    documents = (
        EvidenceDocument("b", "B", "whole b"),
        EvidenceDocument("a", "A", "whole a"),
    )

    scores = scorer.score("query", documents)

    assert [(hit.doc_id, hit.text) for hit in reranker.documents] == [
        ("a", "a first"),
        ("a", "a later"),
        ("b", "b first"),
        ("b", "b later"),
    ]
    assert scores == [
        CandidateScore("b", 0.9, representation, 0, "b first"),
        CandidateScore("a", 0.9, representation, 1, "a later"),
    ]


def test_chunk_reranker_requires_one_or_more_valid_views_for_every_document() -> None:
    representation = "coref-nominal-dp-colbert"
    scorer = StoredChunkMaxRerankerCandidateScorer(
        "colbert-content",
        cast(
            EvidenceStore,
            FakeChunkStore((EvidenceChunk("a", 0, "a", representation, False),)),
        ),
        FakeReranker((1.0,)),
        representation,
    )

    with pytest.raises(ValueError, match="omitted a candidate document view"):
        scorer.score(
            "query",
            (EvidenceDocument("a", "A", "a"), EvidenceDocument("b", "B", "b")),
        )


def test_pooled_ranking_preserves_generation_provenance_and_fuses_complete_scores() -> None:
    lexical = FakeCandidateGenerator("bm25", ("shared", "lexical"))
    dense = FakeCandidateGenerator("dense", ("shared", "dense"))
    retriever = PooledRankingRetriever(
        (lexical, dense),
        (
            FakeCandidateScorer("bm25", {"shared": 0.9, "lexical": 0.8, "dense": 0.1}),
            FakeCandidateScorer("dense", {"shared": 0.9, "dense": 0.8, "lexical": 0.1}),
        ),
        ReciprocalRankAggregator(),
        candidate_limit=2,
    )

    hits, candidates, matrix = retriever.search_with_features("query", 3)

    assert lexical.limits == [2]
    assert dense.limits == [2]
    assert retriever.maximum_pool_size == 4
    assert [hit.doc_id for hit in hits] == ["shared", "dense", "lexical"]
    shared = next(item for item in candidates if item.document.doc_id == "shared")
    generated = [signal for signal in shared.signals if signal.generated_candidate]
    rescored = [signal for signal in shared.signals if not signal.generated_candidate]
    assert [(signal.channel, signal.rank) for signal in generated] == [
        ("bm25", 1),
        ("dense", 1),
    ]
    assert {signal.channel for signal in rescored} == {"bm25", "dense"}
    assert all(signal.chunk_ordinal == 7 for signal in rescored)
    assert all(signal.matched_text for signal in shared.signals)
    assert hits[0].score == pytest.approx(2 / 61)
    shared_row = next(row for row in matrix.rows if row.document.doc_id == "shared")
    assert matrix.channels == ("bm25", "dense")
    assert [
        (feature.channel, feature.raw_score, feature.rank) for feature in shared_row.features
    ] == [
        ("bm25", 0.9, 1),
        ("dense", 0.9, 1),
    ]
    assert all(
        feature.representation.endswith("-representation") for feature in shared_row.features
    )
    assert all(feature.chunk_ordinal == 7 for feature in shared_row.features)
    assert all(feature.matched_text for feature in shared_row.features)


def test_pooled_ranking_accepts_one_complete_late_interaction_scorer() -> None:
    retriever = PooledRankingRetriever(
        (
            FakeCandidateGenerator("bm25", ("shared", "lexical")),
            FakeCandidateGenerator("dense", ("shared", "dense")),
        ),
        (
            FakeCandidateScorer(
                "colbert",
                {"shared": 10.0, "lexical": 20.0, "dense": 30.0},
            ),
        ),
        ReciprocalRankAggregator(),
        candidate_limit=2,
    )

    hits, candidates, matrix = retriever.search_with_features("query", 3)

    assert [hit.doc_id for hit in hits] == ["dense", "lexical", "shared"]
    assert matrix.channels == ("colbert",)
    assert all(len(row.features) == 1 for row in matrix.rows)
    assert all(
        [signal.channel for signal in candidate.signals if not signal.generated_candidate]
        == ["colbert"]
        for candidate in candidates
    )


def test_pooled_ranking_rejects_an_incomplete_score_channel() -> None:
    retriever = PooledRankingRetriever(
        (
            FakeCandidateGenerator("one", ("shared",)),
            FakeCandidateGenerator("two", ("other",)),
        ),
        (
            FakeCandidateScorer("one", {"shared": 1.0, "other": 0.5}),
            FakeCandidateScorer("two", {"shared": 1.0}),
        ),
        ReciprocalRankAggregator(),
    )

    with pytest.raises(ValueError, match="score every pooled candidate exactly once"):
        retriever.search("query", 2)


def test_robust_normalization_uses_mad_logistic_and_deterministic_fallbacks() -> None:
    documents = tuple(EvidenceDocument(str(index), str(index), str(index)) for index in range(4))
    matrix = CandidateFeatureMatrix(
        ("distributed", "sparse", "constant"),
        tuple(
            CandidateFeatureRow(
                document,
                (
                    RankingFeature("distributed", float(index), index + 1, "document"),
                    RankingFeature(
                        "sparse",
                        10.0 if index == 3 else 0.0,
                        index + 1,
                        "document",
                    ),
                    RankingFeature("constant", 7.0, 1, "document"),
                ),
            )
            for index, document in enumerate(documents)
        ),
    )

    normalized = RobustScoreNormalizer().normalize(matrix)

    def channel_scores(index: int) -> list[float]:
        scores = [row.features[index].normalized_score for row in normalized.rows]
        assert all(score is not None for score in scores)
        return [score for score in scores if score is not None]

    distributed = channel_scores(0)
    sparse = channel_scores(1)
    constant = channel_scores(2)
    assert distributed == sorted(distributed)
    assert distributed[0] == pytest.approx(1 - distributed[-1])
    assert distributed[1] == pytest.approx(1 - distributed[2])
    assert sparse == pytest.approx([1 / 3, 1 / 3, 1 / 3, 1.0])
    assert constant == [0.5, 0.5, 0.5, 0.5]


def test_identity_normalizer_preserves_raw_scores_as_normalized_scores() -> None:
    document = EvidenceDocument("one", "one", "one")
    matrix = CandidateFeatureMatrix(
        ("title", "content"),
        (
            CandidateFeatureRow(
                document,
                (
                    RankingFeature("title", -2.5, 1, "title"),
                    RankingFeature("content", 7.25, 1, "content"),
                ),
            ),
        ),
    )

    normalized = IdentityScoreNormalizer().normalize(matrix)

    assert [feature.normalized_score for feature in normalized.rows[0].features] == [
        -2.5,
        7.25,
    ]
    assert [feature.raw_score for feature in normalized.rows[0].features] == [-2.5, 7.25]


def test_equal_score_fusion_averages_normalized_features_setwise() -> None:
    first = EvidenceDocument("first", "first", "first")
    second = EvidenceDocument("second", "second", "second")
    matrix = CandidateFeatureMatrix(
        ("lexical", "dense"),
        (
            CandidateFeatureRow(
                first,
                (
                    RankingFeature("lexical", 9.0, 1, "document", normalized_score=0.9),
                    RankingFeature("dense", 1.0, 2, "document", normalized_score=0.1),
                ),
            ),
            CandidateFeatureRow(
                second,
                (
                    RankingFeature("lexical", 6.0, 2, "document", normalized_score=0.6),
                    RankingFeature("dense", 6.0, 1, "document", normalized_score=0.6),
                ),
            ),
        ),
    )

    hits = EqualScoreFusionPolicy().rank(matrix, 2)

    assert [(hit.doc_id, hit.score) for hit in hits] == [
        ("second", pytest.approx(0.6)),
        ("first", pytest.approx(0.5)),
    ]


def test_ranking_policies_reject_incomplete_feature_rows() -> None:
    document = EvidenceDocument("one", "one", "one")
    incomplete = CandidateFeatureMatrix(
        ("lexical", "dense"),
        (
            CandidateFeatureRow(
                document,
                (RankingFeature("lexical", 1.0, 1, "document"),),
            ),
        ),
    )

    with pytest.raises(ValueError, match="one complete feature per channel"):
        ReciprocalRankAggregator().rank(incomplete, 1)
