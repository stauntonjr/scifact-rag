from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import replace
from statistics import median

from .domain import (
    CandidateFeatureMatrix,
    CandidateFeatureRow,
    CandidateHit,
    CandidateScore,
    EvidenceDocument,
    RankingFeature,
    RetrievalCandidate,
    RetrievalSignal,
    SearchHit,
)
from .ports import (
    CandidateGenerator,
    CandidateScorer,
    Embedder,
    EvidenceStore,
    FeatureMatrixBuilder,
    RankAggregator,
    Reranker,
    Retriever,
    ScoreNormalizer,
)


class VectorRetriever:
    def __init__(
        self,
        store: EvidenceStore,
        embedder: Embedder,
        representations: Sequence[str],
    ) -> None:
        if not representations:
            raise ValueError("at least one vector representation is required")
        self._store = store
        self._embedder = embedder
        self._representations = tuple(representations)

    def search(self, query: str, limit: int) -> list[SearchHit]:
        vectors = self._embedder.embed([query])
        if len(vectors) != 1:
            raise ValueError("embedder returned the wrong number of query vectors")
        return self._store.search_vector(vectors[0], limit, self._representations)


class KeywordRetriever:
    def __init__(self, store: EvidenceStore) -> None:
        self._store = store

    def search(self, query: str, limit: int) -> list[SearchHit]:
        return self._store.search_keyword(query, limit)


class Bm25Retriever:
    def __init__(self, store: EvidenceStore) -> None:
        self._store = store

    def search(self, query: str, limit: int) -> list[SearchHit]:
        return self._store.search_bm25(query, limit)


class ReciprocalRankFusionRetriever:
    def __init__(
        self,
        retrievers: Sequence[Retriever],
        *,
        candidate_limit: int = 50,
        rank_constant: int = 60,
    ) -> None:
        if len(retrievers) < 2:
            raise ValueError("rank fusion requires at least two retrievers")
        if candidate_limit < 1 or rank_constant < 1:
            raise ValueError("rank fusion limits must be positive")
        self._retrievers = tuple(retrievers)
        self._candidate_limit = candidate_limit
        self._rank_constant = rank_constant

    def search(self, query: str, limit: int) -> list[SearchHit]:
        candidate_limit = max(limit, self._candidate_limit)
        scores: dict[str, float] = {}
        hits: dict[str, SearchHit] = {}
        for retriever in self._retrievers:
            seen: set[str] = set()
            for rank, hit in enumerate(retriever.search(query, candidate_limit), 1):
                if hit.doc_id in seen:
                    continue
                seen.add(hit.doc_id)
                hits.setdefault(hit.doc_id, hit)
                scores[hit.doc_id] = scores.get(hit.doc_id, 0.0) + 1.0 / (
                    self._rank_constant + rank
                )
        ranked_ids = sorted(scores, key=lambda doc_id: (-scores[doc_id], doc_id))[:limit]
        return [
            SearchHit(
                doc_id=doc_id,
                title=hits[doc_id].title,
                text=hits[doc_id].text,
                score=scores[doc_id],
            )
            for doc_id in ranked_ids
        ]


class RerankingRetriever:
    def __init__(
        self,
        retrievers: Sequence[Retriever],
        reranker: Reranker,
        *,
        candidate_limit: int = 50,
    ) -> None:
        if len(retrievers) < 2:
            raise ValueError("reranking requires at least two candidate retrievers")
        if candidate_limit < 1:
            raise ValueError("candidate limit must be positive")
        self._retrievers = tuple(retrievers)
        self._reranker = reranker
        self._candidate_limit = candidate_limit

    def search(self, query: str, limit: int) -> list[SearchHit]:
        candidates: dict[str, SearchHit] = {}
        for retriever in self._retrievers:
            for hit in retriever.search(query, self._candidate_limit):
                candidates.setdefault(hit.doc_id, hit)

        documents = list(candidates.values())
        scores = self._reranker.score(query, documents)
        if len(scores) != len(documents):
            raise ValueError("reranker returned the wrong number of scores")
        if any(not math.isfinite(score) for score in scores):
            raise ValueError("reranker returned a non-finite score")

        ranked = sorted(
            zip(documents, scores, strict=True),
            key=lambda item: (-item[1], item[0].doc_id),
        )[:limit]
        return [
            SearchHit(
                doc_id=document.doc_id,
                title=document.title,
                text=document.text,
                score=score,
            )
            for document, score in ranked
        ]


class Bm25CandidateGenerator:
    name = "bm25"

    def __init__(self, store: EvidenceStore) -> None:
        self._store = store

    def generate(self, query: str, limit: int) -> list[CandidateHit]:
        return self._store.retrieve_bm25_candidates(query, limit)


class VectorCandidateGenerator:
    def __init__(
        self,
        name: str,
        store: EvidenceStore,
        embedder: Embedder,
        representations: Sequence[str],
    ) -> None:
        if not name or not representations:
            raise ValueError("vector candidate generators require a name and representations")
        self.name = name
        self._store = store
        self._embedder = embedder
        self._representations = tuple(representations)

    def generate(self, query: str, limit: int) -> list[CandidateHit]:
        embedding = _embed_query(self._embedder, query)
        return self._store.retrieve_vector_candidates(
            embedding,
            limit,
            self._representations,
        )


class Bm25CandidateScorer:
    name = "bm25"

    def __init__(self, store: EvidenceStore) -> None:
        self._store = store

    def score(
        self,
        query: str,
        documents: Sequence[EvidenceDocument],
    ) -> list[CandidateScore]:
        return self._store.score_bm25_candidates(
            query,
            [document.doc_id for document in documents],
        )


class VectorCandidateScorer:
    def __init__(
        self,
        name: str,
        store: EvidenceStore,
        embedder: Embedder,
        representations: Sequence[str],
    ) -> None:
        if not name or not representations:
            raise ValueError("vector candidate scorers require a name and representations")
        self.name = name
        self._store = store
        self._embedder = embedder
        self._representations = tuple(representations)

    def score(
        self,
        query: str,
        documents: Sequence[EvidenceDocument],
    ) -> list[CandidateScore]:
        embedding = _embed_query(self._embedder, query)
        return self._store.score_vector_candidates(
            embedding,
            [document.doc_id for document in documents],
            self._representations,
        )


class RerankerCandidateScorer:
    def __init__(self, name: str, reranker: Reranker) -> None:
        if not name:
            raise ValueError("reranker candidate scorers require a name")
        self.name = name
        self._reranker = reranker

    def score(
        self,
        query: str,
        documents: Sequence[EvidenceDocument],
    ) -> list[CandidateScore]:
        hits = [SearchHit(item.doc_id, item.title, item.text, 0.0) for item in documents]
        scores = self._reranker.score(query, hits)
        if len(scores) != len(documents):
            raise ValueError("reranker returned the wrong number of scores")
        return [
            CandidateScore(
                document.doc_id,
                float(score),
                "title-abstract",
                matched_text=f"{document.title}\n{document.text}".strip(),
            )
            for document, score in zip(documents, scores, strict=True)
        ]


class TitleRerankerCandidateScorer:
    def __init__(self, name: str, reranker: Reranker) -> None:
        if not name:
            raise ValueError("title reranker candidate scorers require a name")
        self.name = name
        self._reranker = reranker

    def score(
        self,
        query: str,
        documents: Sequence[EvidenceDocument],
    ) -> list[CandidateScore]:
        views = [SearchHit(document.doc_id, "", document.title, 0.0) for document in documents]
        scores = self._reranker.score(query, views)
        if len(scores) != len(documents):
            raise ValueError("title reranker returned the wrong number of scores")
        return [
            CandidateScore(
                document.doc_id,
                float(score),
                "title",
                chunk_ordinal=0,
                matched_text=document.title,
            )
            for document, score in zip(documents, scores, strict=True)
        ]


class StoredChunkMaxRerankerCandidateScorer:
    def __init__(
        self,
        name: str,
        store: EvidenceStore,
        reranker: Reranker,
        representation: str,
    ) -> None:
        if not name or not representation:
            raise ValueError("chunk reranker candidate scorers require names")
        self.name = name
        self._store = store
        self._reranker = reranker
        self._representation = representation

    def score(
        self,
        query: str,
        documents: Sequence[EvidenceDocument],
    ) -> list[CandidateScore]:
        expected_ids = {document.doc_id for document in documents}
        if len(expected_ids) != len(documents):
            raise ValueError("chunk reranker input document identifiers must be unique")
        chunks = self._store.load_chunks(tuple(expected_ids), (self._representation,))
        seen: set[tuple[str, int]] = set()
        by_document: dict[str, list[tuple[int, str]]] = {doc_id: [] for doc_id in expected_ids}
        for chunk in chunks:
            identity = (chunk.doc_id, chunk.ordinal)
            if (
                chunk.doc_id not in expected_ids
                or chunk.representation != self._representation
                or identity in seen
            ):
                raise ValueError("chunk reranker store returned invalid or duplicate views")
            seen.add(identity)
            by_document[chunk.doc_id].append((chunk.ordinal, chunk.text))
        if any(not views for views in by_document.values()):
            raise ValueError("chunk reranker store omitted a candidate document view")

        flattened = [
            (doc_id, ordinal, text)
            for doc_id in sorted(by_document)
            for ordinal, text in sorted(by_document[doc_id])
        ]
        views = [SearchHit(doc_id, "", text, 0.0) for doc_id, _, text in flattened]
        scores = self._reranker.score(query, views)
        if len(scores) != len(flattened):
            raise ValueError("chunk reranker returned the wrong number of scores")

        best: dict[str, tuple[float, int, str]] = {}
        for (doc_id, ordinal, text), score in zip(flattened, scores, strict=True):
            candidate = (float(score), -ordinal, text)
            if doc_id not in best or candidate[:2] > best[doc_id][:2]:
                best[doc_id] = candidate
        return [
            CandidateScore(
                document.doc_id,
                best[document.doc_id][0],
                self._representation,
                chunk_ordinal=-best[document.doc_id][1],
                matched_text=best[document.doc_id][2],
            )
            for document in documents
        ]


class CompleteScoreFeatureMatrixBuilder:
    def build(
        self,
        candidates: Sequence[RetrievalCandidate],
    ) -> CandidateFeatureMatrix:
        if not candidates:
            return CandidateFeatureMatrix((), ())
        channels = tuple(
            signal.channel for signal in candidates[0].signals if not signal.generated_candidate
        )
        if not channels or len(set(channels)) != len(channels):
            raise ValueError("feature rows require unique complete scorer channels")

        rows: list[CandidateFeatureRow] = []
        for candidate in candidates:
            scoring_signals = [
                signal for signal in candidate.signals if not signal.generated_candidate
            ]
            by_channel = {signal.channel: signal for signal in scoring_signals}
            if len(by_channel) != len(scoring_signals) or set(by_channel) != set(channels):
                raise ValueError("candidates must have one complete score per channel")
            rows.append(
                CandidateFeatureRow(
                    candidate.document,
                    tuple(
                        RankingFeature(
                            channel=channel,
                            raw_score=by_channel[channel].score,
                            rank=by_channel[channel].rank,
                            representation=by_channel[channel].representation,
                            chunk_ordinal=by_channel[channel].chunk_ordinal,
                            matched_text=by_channel[channel].matched_text,
                        )
                        for channel in channels
                    ),
                )
            )
        return CandidateFeatureMatrix(channels, tuple(rows))


class RobustScoreNormalizer:
    def normalize(self, matrix: CandidateFeatureMatrix) -> CandidateFeatureMatrix:
        if not matrix.rows:
            return matrix
        validated_rows = _validated_feature_rows(matrix)
        normalized_by_channel = {
            channel: _robust_normalize(
                [features[channel].raw_score for _, features in validated_rows]
            )
            for channel in matrix.channels
        }
        return CandidateFeatureMatrix(
            matrix.channels,
            tuple(
                CandidateFeatureRow(
                    row.document,
                    tuple(
                        replace(
                            feature,
                            normalized_score=normalized_by_channel[feature.channel][row_index],
                        )
                        for feature in row.features
                    ),
                )
                for row_index, row in enumerate(matrix.rows)
            ),
        )


class IdentityScoreNormalizer:
    """Expose finite raw scores to score-fusion policies without rescaling them."""

    def normalize(self, matrix: CandidateFeatureMatrix) -> CandidateFeatureMatrix:
        if not matrix.rows:
            return matrix
        _validated_feature_rows(matrix)
        return CandidateFeatureMatrix(
            matrix.channels,
            tuple(
                CandidateFeatureRow(
                    row.document,
                    tuple(
                        replace(feature, normalized_score=feature.raw_score)
                        for feature in row.features
                    ),
                )
                for row in matrix.rows
            ),
        )


class ReciprocalRankAggregator:
    def __init__(self, *, rank_constant: int = 60) -> None:
        if rank_constant < 1:
            raise ValueError("rank constant must be positive")
        self._rank_constant = rank_constant

    def rank(
        self,
        matrix: CandidateFeatureMatrix,
        limit: int,
    ) -> list[SearchHit]:
        if limit < 1:
            raise ValueError("limit must be positive")
        if not matrix.rows:
            return []
        validated_rows = _validated_feature_rows(matrix)
        scores = {
            row.document.doc_id: sum(
                1.0 / (self._rank_constant + features[channel].rank) for channel in matrix.channels
            )
            for row, features in validated_rows
        }
        documents = {row.document.doc_id: row.document for row in matrix.rows}
        ranked_ids = sorted(scores, key=lambda doc_id: (-scores[doc_id], doc_id))[:limit]
        return [
            SearchHit(
                doc_id,
                documents[doc_id].title,
                documents[doc_id].text,
                scores[doc_id],
            )
            for doc_id in ranked_ids
        ]


class EqualScoreFusionPolicy:
    def rank(
        self,
        matrix: CandidateFeatureMatrix,
        limit: int,
    ) -> list[SearchHit]:
        if limit < 1:
            raise ValueError("limit must be positive")
        if not matrix.rows:
            return []
        validated_rows = _validated_feature_rows(matrix)
        scores: dict[str, float] = {}
        for row, features in validated_rows:
            normalized = [features[channel].normalized_score for channel in matrix.channels]
            if any(score is None or not math.isfinite(score) for score in normalized):
                raise ValueError("equal score fusion requires normalized feature scores")
            scores[row.document.doc_id] = sum(
                score for score in normalized if score is not None
            ) / len(normalized)
        documents = {row.document.doc_id: row.document for row in matrix.rows}
        ranked_ids = sorted(scores, key=lambda doc_id: (-scores[doc_id], doc_id))[:limit]
        return [
            SearchHit(
                doc_id,
                documents[doc_id].title,
                documents[doc_id].text,
                scores[doc_id],
            )
            for doc_id in ranked_ids
        ]


class PooledRankingRetriever:
    def __init__(
        self,
        generators: Sequence[CandidateGenerator],
        scorers: Sequence[CandidateScorer],
        aggregator: RankAggregator,
        *,
        candidate_limit: int = 50,
        feature_builder: FeatureMatrixBuilder | None = None,
        normalizer: ScoreNormalizer | None = None,
    ) -> None:
        if len(generators) < 2 or not scorers:
            raise ValueError("pooled ranking requires at least two generators and one scorer")
        if candidate_limit < 1:
            raise ValueError("candidate limit must be positive")
        generator_names = [generator.name for generator in generators]
        scorer_names = [scorer.name for scorer in scorers]
        if len(set(generator_names)) != len(generator_names):
            raise ValueError("candidate generator names must be unique")
        if len(set(scorer_names)) != len(scorer_names):
            raise ValueError("candidate scorer names must be unique")
        self._generators = tuple(generators)
        self._scorers = tuple(scorers)
        self._aggregator = aggregator
        self._feature_builder = feature_builder or CompleteScoreFeatureMatrixBuilder()
        self._normalizer = normalizer
        self._candidate_limit = candidate_limit

    @property
    def generator_limit(self) -> int:
        return self._candidate_limit

    @property
    def maximum_pool_size(self) -> int:
        return self._candidate_limit * len(self._generators)

    def search(self, query: str, limit: int) -> list[SearchHit]:
        hits, _ = self.search_with_candidates(query, limit)
        return hits

    def search_with_candidates(
        self,
        query: str,
        limit: int,
    ) -> tuple[list[SearchHit], list[RetrievalCandidate]]:
        hits, candidates, _ = self.search_with_features(query, limit)
        return hits, candidates

    def search_with_features(
        self,
        query: str,
        limit: int,
    ) -> tuple[list[SearchHit], list[RetrievalCandidate], CandidateFeatureMatrix]:
        candidates = self._generate(query)
        scored = self._score(query, candidates)
        matrix = self._feature_builder.build(scored)
        if self._normalizer is not None:
            matrix = self._normalizer.normalize(matrix)
        return self._aggregator.rank(matrix, limit), scored, matrix

    def _generate(self, query: str) -> list[RetrievalCandidate]:
        documents: dict[str, EvidenceDocument] = {}
        signals: dict[str, list[RetrievalSignal]] = {}
        for generator in self._generators:
            seen: set[str] = set()
            for rank, hit in enumerate(
                generator.generate(query, self._candidate_limit),
                1,
            ):
                doc_id = hit.document.doc_id
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                existing = documents.setdefault(doc_id, hit.document)
                if existing != hit.document:
                    raise ValueError("candidate generators returned conflicting document content")
                signals.setdefault(doc_id, []).append(
                    RetrievalSignal(
                        channel=generator.name,
                        representation=hit.representation,
                        score=hit.score,
                        rank=rank,
                        generated_candidate=True,
                        chunk_ordinal=hit.chunk_ordinal,
                        matched_text=hit.matched_text,
                    )
                )
        return [
            RetrievalCandidate(document, tuple(signals[doc_id]))
            for doc_id, document in documents.items()
        ]

    def _score(
        self,
        query: str,
        candidates: Sequence[RetrievalCandidate],
    ) -> list[RetrievalCandidate]:
        if not candidates:
            return []
        documents = [candidate.document for candidate in candidates]
        expected_ids = {document.doc_id for document in documents}
        score_signals: dict[str, list[RetrievalSignal]] = {
            document.doc_id: [] for document in documents
        }
        for scorer in self._scorers:
            scores = scorer.score(query, documents)
            by_id = {score.doc_id: score for score in scores}
            if len(by_id) != len(scores) or set(by_id) != expected_ids:
                raise ValueError(f"{scorer.name} did not score every pooled candidate exactly once")
            if any(not math.isfinite(score.score) for score in scores):
                raise ValueError(f"{scorer.name} returned a non-finite score")
            ranked = sorted(scores, key=lambda item: (-item.score, item.doc_id))
            previous_score: float | None = None
            previous_rank = 0
            for position, score in enumerate(ranked, 1):
                rank = previous_rank if previous_score == score.score else position
                score_signals[score.doc_id].append(
                    RetrievalSignal(
                        channel=scorer.name,
                        representation=score.representation,
                        score=score.score,
                        rank=rank,
                        generated_candidate=False,
                        chunk_ordinal=score.chunk_ordinal,
                        matched_text=score.matched_text,
                    )
                )
                previous_score = score.score
                previous_rank = rank
        return [
            RetrievalCandidate(
                candidate.document,
                (*candidate.signals, *score_signals[candidate.document.doc_id]),
            )
            for candidate in candidates
        ]


def _embed_query(embedder: Embedder, query: str) -> list[float]:
    vectors = embedder.embed([query])
    if len(vectors) != 1:
        raise ValueError("embedder returned the wrong number of query vectors")
    return vectors[0]


def _robust_normalize(values: Sequence[float]) -> tuple[float, ...]:
    if not values:
        return ()
    if any(not math.isfinite(value) for value in values):
        raise ValueError("score normalization requires finite values")
    if len(set(values)) == 1:
        return (0.5,) * len(values)

    center = median(values)
    absolute_deviations = [abs(value - center) for value in values]
    deviation = median(absolute_deviations)
    if deviation == 0:
        return _empirical_cdf(values)

    scale = 0.6744897501960817
    return tuple(_logistic(scale * (value - center) / deviation) for value in values)


def _validated_feature_rows(
    matrix: CandidateFeatureMatrix,
) -> tuple[tuple[CandidateFeatureRow, dict[str, RankingFeature]], ...]:
    if not matrix.channels or len(set(matrix.channels)) != len(matrix.channels):
        raise ValueError("feature matrices require unique scorer channels")
    rows: list[tuple[CandidateFeatureRow, dict[str, RankingFeature]]] = []
    document_ids: set[str] = set()
    for row in matrix.rows:
        if row.document.doc_id in document_ids:
            raise ValueError("feature matrices require unique candidate documents")
        document_ids.add(row.document.doc_id)
        by_channel = {feature.channel: feature for feature in row.features}
        if len(by_channel) != len(row.features) or set(by_channel) != set(matrix.channels):
            raise ValueError("feature rows require one complete feature per channel")
        if any(not math.isfinite(feature.raw_score) for feature in row.features):
            raise ValueError("feature matrices require finite raw scores")
        if any(feature.rank < 1 for feature in row.features):
            raise ValueError("feature matrices require positive scorer ranks")
        rows.append((row, by_channel))
    return tuple(rows)


def _empirical_cdf(values: Sequence[float]) -> tuple[float, ...]:
    denominator = len(values) - 1
    sorted_values = sorted(values)
    normalized: dict[float, float] = {}
    for value in set(sorted_values):
        positions = [index for index, item in enumerate(sorted_values) if item == value]
        normalized[value] = sum(positions) / len(positions) / denominator
    return tuple(normalized[value] for value in values)


def _logistic(value: float) -> float:
    if value >= 0:
        decay = math.exp(-value)
        return 1.0 / (1.0 + decay)
    growth = math.exp(value)
    return growth / (1.0 + growth)
