from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from .domain import (
    CoreferenceAnalysis,
    CoreferenceMention,
    EvidenceChunk,
    EvidenceDocument,
    SentenceSpan,
)
from .ports import CoreferenceAnalyzer, RepresentationStrategy

_TITLE = "title"
_TOKEN_WINDOW = "token-window"
_SENTENCE_PACK = "sentence-pack"
_COREF_AWARE_PACK = "coref-aware-pack"
_COREF_INTERVAL_PACK = "coref-interval-pack"
COREF_NOMINAL_DP_MINILM = "coref-nominal-dp-minilm"
COREF_NOMINAL_DP_COLBERT = "coref-nominal-dp-colbert"
_COREF_PROPN = "coref-propn-sentence"
_COREF_NOMINAL = "coref-nominal-sentence"
_POSSESSIVE_SUFFIX = "'s"


class RetrievalStrategyName(StrEnum):
    TITLE_TOKEN_WINDOW_RRF = "title-token-window-rrf"
    TOKEN_WINDOW = "token-window"
    SENTENCE_PACK = "sentence-pack"
    COREF_AWARE_PACK = "coref-aware-pack"
    COREF_INTERVAL_PACK = "coref-interval-pack"
    COREF_PROPN = "coref-propn"
    COREF_NOMINAL = "coref-nominal"
    COREF_MAX = "coref-max"
    KEYWORD = "keyword"
    BM25 = "bm25"
    HYBRID_RRF = "hybrid-rrf"
    BM25_TOKEN_WINDOW_RRF = "bm25-token-window-rrf"
    BM25_COREF_PROPN_RRF = "bm25-coref-propn-rrf"
    BM25_COREF_NOMINAL_RRF = "bm25-coref-nominal-rrf"
    BM25_COREF_MAX_RRF = "bm25-coref-max-rrf"
    BM25_SENTENCE_PACK_RRF = "bm25-sentence-pack-rrf"
    BM25_COREF_AWARE_PACK_RRF = "bm25-coref-aware-pack-rrf"
    BM25_COREF_INTERVAL_PACK_RRF = "bm25-coref-interval-pack-rrf"
    RERANK_MSMARCO = "rerank-msmarco"
    POOLED_FOUR_CHANNEL_RRF = "pooled-four-channel-rrf"
    POOLED_MSMARCO_RRF = "pooled-msmarco-rrf"
    POOLED_FOUR_CHANNEL_ROBUST_SUM = "pooled-four-channel-robust-sum"
    POOLED_COLBERT = "pooled-colbert"
    POOLED_SENTENCE_PACK_RRF = "pooled-sentence-pack-rrf"
    POOLED_COREF_AWARE_PACK_RRF = "pooled-coref-aware-pack-rrf"
    POOLED_COREF_INTERVAL_PACK_RRF = "pooled-coref-interval-pack-rrf"
    POOLED_COREF_INTERVAL_MSMARCO = "pooled-coref-interval-msmarco"
    POOLED_COREF_INTERVAL_COLBERT = "pooled-coref-interval-colbert"
    POOLED_COREF_INTERVAL_RANKZEPHYR = "pooled-coref-interval-rankzephyr"
    POOLED_COREF_NOMINAL_DP_COLBERT = "pooled-coref-nominal-dp-colbert"
    POOLED_COREF_INTERVAL_MULTIVIEW_COLBERT = "pooled-coref-interval-multiview-colbert"


class CanonicalizationPolicy(StrEnum):
    PROPER_NOUN = "proper-noun"
    EXPLICIT_NOMINAL = "explicit-nominal"


class TitleStrategy:
    name = _TITLE
    representations = (_TITLE,)

    def chunks(self, documents: Sequence[EvidenceDocument]) -> list[EvidenceChunk]:
        return [
            EvidenceChunk(document.doc_id, 0, document.title.strip(), _TITLE)
            for document in documents
            if document.title.strip()
        ]


class TokenWindowStrategy:
    name = RetrievalStrategyName.TOKEN_WINDOW.value
    representations = (_TOKEN_WINDOW,)

    def __init__(self, window: Callable[[str], list[str]]) -> None:
        self._window = window

    def chunks(self, documents: Sequence[EvidenceDocument]) -> list[EvidenceChunk]:
        return [
            EvidenceChunk(
                document.doc_id,
                ordinal,
                text,
                representation=_TOKEN_WINDOW,
            )
            for document in documents
            for ordinal, text in enumerate(self._window(document.text))
        ]


class SentencePackingStrategy:
    def __init__(
        self,
        analyzer: CoreferenceAnalyzer,
        token_count: Callable[[str], int],
        hard_split: Callable[[str], list[str]],
        *,
        coreference_aware: bool = False,
        target_tokens: int = 112,
        maximum_tokens: int = 126,
    ) -> None:
        if target_tokens < 1 or maximum_tokens < target_tokens:
            raise ValueError("sentence packing limits must be positive and ordered")
        self._analyzer = analyzer
        self._token_count = token_count
        self._hard_split = hard_split
        self._coreference_aware = coreference_aware
        self._target_tokens = target_tokens
        self._maximum_tokens = maximum_tokens

    @property
    def name(self) -> str:
        return _COREF_AWARE_PACK if self._coreference_aware else _SENTENCE_PACK

    @property
    def representations(self) -> tuple[str, ...]:
        return (self.name,)

    def chunks(self, documents: Sequence[EvidenceDocument]) -> list[EvidenceChunk]:
        analyses = (
            self._analyzer.analyze([document.text for document in documents])
            if self._coreference_aware
            else [None] * len(documents)
        )
        if len(analyses) != len(documents):
            raise ValueError("coreference analyzer returned the wrong number of documents")

        chunks: list[EvidenceChunk] = []
        for document, analysis in zip(documents, analyses, strict=True):
            if analysis is not None:
                _validate_coreference_analysis(document.text, analysis)
            spans = self._validated_sentence_spans(document.text)
            packed = self._pack(document.text, spans, analysis)
            for ordinal, text in enumerate(packed):
                chunks.append(EvidenceChunk(document.doc_id, ordinal, text, self.name))
        return chunks

    def _validated_sentence_spans(self, text: str) -> list[SentenceSpan]:
        return _validated_sentence_spans(self._analyzer, text)

    def _pack(
        self,
        source: str,
        spans: Sequence[SentenceSpan],
        analysis: CoreferenceAnalysis | None,
    ) -> list[str]:
        groups: list[list[SentenceSpan]] = []
        current: list[SentenceSpan] = []
        for span in spans:
            if current:
                proposed_text = self._render(source, (*current, span), analysis)
                boundary = span.start
                crossing_chain = analysis is not None and _crosses_coreference_boundary(
                    analysis, boundary
                )
                if self._token_count(proposed_text) > self._maximum_tokens or (
                    self._token_count(proposed_text) > self._target_tokens and not crossing_chain
                ):
                    groups.append(current)
                    current = []
            current.append(span)
        if current:
            groups.append(current)

        return self._complete_groups(source, groups, analysis)

    def _complete_groups(
        self,
        source: str,
        groups: Sequence[Sequence[SentenceSpan]],
        analysis: CoreferenceAnalysis | None,
    ) -> list[str]:
        packed: list[str] = []
        for group in groups:
            text = self._render(source, group, analysis)
            if self._token_count(text) <= self._maximum_tokens:
                packed.append(text)
            else:
                packed.extend(self._hard_split(text))
        if any(self._token_count(text) > self._maximum_tokens for text in packed):
            raise ValueError("hard sentence split exceeded the model token limit")
        return packed

    def _render(
        self,
        source: str,
        spans: Sequence[SentenceSpan],
        analysis: CoreferenceAnalysis | None,
    ) -> str:
        start = spans[0].start
        end = spans[-1].end
        if analysis is None:
            return source[start:end].strip()
        return _resolve_coreferences_in_span(
            analysis,
            CanonicalizationPolicy.PROPER_NOUN,
            start,
            end,
        ).strip()


class CoreferenceIntervalPackingStrategy(SentencePackingStrategy):
    """Globally pack sentences while minimizing equal-cost coreference cuts."""

    def __init__(
        self,
        analyzer: CoreferenceAnalyzer,
        token_count: Callable[[str], int],
        hard_split: Callable[[str], list[str]],
        *,
        target_tokens: int = 112,
        maximum_tokens: int = 126,
    ) -> None:
        super().__init__(
            analyzer,
            token_count,
            hard_split,
            coreference_aware=True,
            target_tokens=target_tokens,
            maximum_tokens=maximum_tokens,
        )

    @property
    def name(self) -> str:
        return _COREF_INTERVAL_PACK

    def _pack(
        self,
        source: str,
        spans: Sequence[SentenceSpan],
        analysis: CoreferenceAnalysis | None,
    ) -> list[str]:
        if analysis is None:
            raise ValueError("interval packing requires coreference analysis")
        if not spans:
            return []

        selected = _select_interval_groups(
            spans,
            analysis,
            lambda group: self._render(source, group, analysis),
            self._token_count,
            target_tokens=self._target_tokens,
            maximum_tokens=self._maximum_tokens,
            boundary_policy=CanonicalizationPolicy.PROPER_NOUN,
        )
        return self._complete_groups(source, selected, analysis)


@dataclass(frozen=True, slots=True)
class DpBoundaryProfile:
    representation: str
    token_count: Callable[[str], int]
    hard_split: Callable[[str], list[str]]
    target_tokens: int
    maximum_tokens: int
    embedding_required: bool

    def __post_init__(self) -> None:
        if (
            not self.representation
            or self.target_tokens < 1
            or self.maximum_tokens < self.target_tokens
        ):
            raise ValueError("DP boundary profile limits must be positive and ordered")


class CoreferenceNominalDpStrategy:
    """Emit nominal sentence candidates and raw DP views from one analysis."""

    name = "coref-nominal-dual-dp"

    def __init__(
        self,
        analyzer: CoreferenceAnalyzer,
        minilm_profile: DpBoundaryProfile,
        colbert_profile: DpBoundaryProfile,
    ) -> None:
        if minilm_profile.representation != COREF_NOMINAL_DP_MINILM:
            raise ValueError("MiniLM DP profile has the wrong representation")
        if colbert_profile.representation != COREF_NOMINAL_DP_COLBERT:
            raise ValueError("ColBERT DP profile has the wrong representation")
        if not minilm_profile.embedding_required or colbert_profile.embedding_required:
            raise ValueError("only the MiniLM DP profile may require embeddings")
        self._analyzer = analyzer
        self._profiles = (minilm_profile, colbert_profile)
        self.representations = (
            _COREF_NOMINAL,
            minilm_profile.representation,
            colbert_profile.representation,
        )

    def chunks(self, documents: Sequence[EvidenceDocument]) -> list[EvidenceChunk]:
        analyses = self._analyzer.analyze([document.text for document in documents])
        if len(analyses) != len(documents):
            raise ValueError("coreference analyzer returned the wrong number of documents")

        chunks: list[EvidenceChunk] = []
        for document, analysis in zip(documents, analyses, strict=True):
            _validate_coreference_analysis(document.text, analysis)
            resolved = resolve_coreferences(analysis, CanonicalizationPolicy.EXPLICIT_NOMINAL)
            chunks.extend(
                EvidenceChunk(document.doc_id, ordinal, sentence.strip(), _COREF_NOMINAL)
                for ordinal, sentence in enumerate(self._analyzer.sentences(resolved))
                if sentence.strip()
            )
            spans = _validated_sentence_spans(self._analyzer, document.text)
            source = document.text
            for profile in self._profiles:
                groups = _select_interval_groups(
                    spans,
                    analysis,
                    lambda group, source=source: _raw_group_text(source, group),
                    profile.token_count,
                    target_tokens=profile.target_tokens,
                    maximum_tokens=profile.maximum_tokens,
                    boundary_policy=CanonicalizationPolicy.EXPLICIT_NOMINAL,
                )
                texts = _complete_raw_groups(source, groups, profile)
                chunks.extend(
                    EvidenceChunk(
                        document.doc_id,
                        ordinal,
                        text,
                        profile.representation,
                        embedding_required=profile.embedding_required,
                    )
                    for ordinal, text in enumerate(texts)
                )
        return chunks


class CompositeRepresentationStrategy:
    def __init__(
        self,
        name: str,
        strategies: Sequence[RepresentationStrategy],
    ) -> None:
        if len(strategies) < 2:
            raise ValueError("a composite strategy requires at least two strategies")
        self.name = name
        self._strategies = tuple(strategies)
        self.representations = tuple(
            dict.fromkeys(
                representation
                for strategy in self._strategies
                for representation in strategy.representations
            )
        )

    def chunks(self, documents: Sequence[EvidenceDocument]) -> list[EvidenceChunk]:
        return [chunk for strategy in self._strategies for chunk in strategy.chunks(documents)]


class DocumentOnlyStrategy:
    representations: tuple[str, ...] = ()

    def __init__(
        self,
        name: RetrievalStrategyName = RetrievalStrategyName.KEYWORD,
    ) -> None:
        if name not in (RetrievalStrategyName.KEYWORD, RetrievalStrategyName.BM25):
            raise ValueError("document-only strategy must be keyword or bm25")
        self.name = name.value

    def chunks(self, documents: Sequence[EvidenceDocument]) -> list[EvidenceChunk]:
        return []


class CoreferenceSentenceStrategy:
    def __init__(
        self,
        analyzer: CoreferenceAnalyzer,
        policies: Sequence[CanonicalizationPolicy],
    ) -> None:
        if not policies:
            raise ValueError("at least one canonicalization policy is required")
        self._analyzer = analyzer
        self._policies = tuple(dict.fromkeys(policies))

    @property
    def name(self) -> str:
        if self._policies == (CanonicalizationPolicy.PROPER_NOUN,):
            return RetrievalStrategyName.COREF_PROPN.value
        if self._policies == (CanonicalizationPolicy.EXPLICIT_NOMINAL,):
            return RetrievalStrategyName.COREF_NOMINAL.value
        return RetrievalStrategyName.COREF_MAX.value

    @property
    def representations(self) -> tuple[str, ...]:
        return tuple(_representation(policy) for policy in self._policies)

    def chunks(self, documents: Sequence[EvidenceDocument]) -> list[EvidenceChunk]:
        analyses = self._analyzer.analyze([document.text for document in documents])
        if len(analyses) != len(documents):
            raise ValueError("coreference analyzer returned the wrong number of documents")

        chunks: list[EvidenceChunk] = []
        for document, analysis in zip(documents, analyses, strict=True):
            for policy in self._policies:
                resolved = resolve_coreferences(analysis, policy)
                sentences = self._analyzer.sentences(resolved)
                for ordinal, sentence in enumerate(sentences):
                    if sentence.strip():
                        chunks.append(
                            EvidenceChunk(
                                document.doc_id,
                                ordinal,
                                sentence.strip(),
                                _representation(policy),
                            )
                        )
        return chunks


def resolve_coreferences(
    analysis: CoreferenceAnalysis,
    policy: CanonicalizationPolicy,
) -> str:
    return _resolve_coreferences_in_span(analysis, policy, 0, len(analysis.text))


def _resolve_coreferences_in_span(
    analysis: CoreferenceAnalysis,
    policy: CanonicalizationPolicy,
    start_offset: int,
    end_offset: int,
) -> str:
    replacements: list[tuple[int, int, str]] = []
    for cluster in analysis.clusters:
        canonical = _canonical_mention(cluster, policy)
        if canonical is None:
            continue
        for mention in cluster:
            if mention == canonical or mention.text == canonical.text:
                continue
            if mention.start < start_offset or mention.end > end_offset:
                continue
            replacement = canonical.text
            if mention.is_possessive:
                replacement = f"{replacement}{_POSSESSIVE_SUFFIX}"
            replacements.append((mention.start, mention.end, replacement))

    resolved = analysis.text[start_offset:end_offset]
    next_start = end_offset
    for start, end, replacement in sorted(replacements, reverse=True):
        if start < start_offset or end <= start or end > end_offset or end > next_start:
            continue
        local_start = start - start_offset
        local_end = end - start_offset
        resolved = f"{resolved[:local_start]}{replacement}{resolved[local_end:]}"
        next_start = start
    return resolved


def _validated_sentence_spans(
    analyzer: CoreferenceAnalyzer,
    text: str,
) -> list[SentenceSpan]:
    spans = analyzer.sentence_spans(text)
    if not spans and text.strip():
        start = len(text) - len(text.lstrip())
        end = len(text.rstrip())
        return [SentenceSpan(start, end, text[start:end])]
    previous_end = 0
    for span in spans:
        if (
            span.start < previous_end
            or span.end <= span.start
            or span.end > len(text)
            or text[span.start : span.end].strip() != span.text
        ):
            raise ValueError("sentence analyzer returned invalid source offsets")
        previous_end = span.end
    return spans


def _select_interval_groups(
    spans: Sequence[SentenceSpan],
    analysis: CoreferenceAnalysis,
    render: Callable[[Sequence[SentenceSpan]], str],
    token_count: Callable[[str], int],
    *,
    target_tokens: int,
    maximum_tokens: int,
    boundary_policy: CanonicalizationPolicy,
) -> list[list[SentenceSpan]]:
    if not spans:
        return []
    states: list[tuple[tuple[int, int, int, tuple[int, ...]], list[list[SentenceSpan]]] | None] = [
        None
    ] * (len(spans) + 1)
    states[0] = ((0, 0, 0, ()), [])
    for end in range(1, len(spans) + 1):
        best: tuple[tuple[int, int, int, tuple[int, ...]], list[list[SentenceSpan]]] | None = None
        for start in range(end):
            previous = states[start]
            if previous is None:
                continue
            group = list(spans[start:end])
            tokens = token_count(render(group))
            if tokens > maximum_tokens and len(group) > 1:
                continue
            boundary_cost = (
                _coreference_boundary_cut_cost(analysis, spans[end].start, boundary_policy)
                if end < len(spans)
                else 0
            )
            previous_cost, previous_groups = previous
            cost = (
                previous_cost[0] + boundary_cost,
                previous_cost[1] + (tokens - target_tokens) ** 2,
                previous_cost[2] + 1,
                (*previous_cost[3], end),
            )
            candidate = (cost, [*previous_groups, group])
            if best is None or candidate[0] < best[0]:
                best = candidate
        states[end] = best
    selected = states[-1]
    if selected is None:
        raise ValueError("no valid interval packing could be constructed")
    return selected[1]


def _raw_group_text(source: str, group: Sequence[SentenceSpan]) -> str:
    return source[group[0].start : group[-1].end].strip()


def _complete_raw_groups(
    source: str,
    groups: Sequence[Sequence[SentenceSpan]],
    profile: DpBoundaryProfile,
) -> list[str]:
    packed: list[str] = []
    for group in groups:
        text = _raw_group_text(source, group)
        if profile.token_count(text) <= profile.maximum_tokens:
            packed.append(text)
        else:
            packed.extend(profile.hard_split(text))
    if any(profile.token_count(text) > profile.maximum_tokens for text in packed):
        raise ValueError("hard DP split exceeded the profile token limit")
    return packed


def _crosses_coreference_boundary(analysis: CoreferenceAnalysis, boundary: int) -> bool:
    return _coreference_boundary_cut_cost(analysis, boundary) > 0


def _coreference_boundary_cut_cost(
    analysis: CoreferenceAnalysis,
    boundary: int,
    policy: CanonicalizationPolicy = CanonicalizationPolicy.PROPER_NOUN,
) -> int:
    return sum(
        1
        for cluster in analysis.clusters
        if _canonical_mention(cluster, policy) is not None
        and any(mention.end <= boundary for mention in cluster)
        and any(mention.start >= boundary for mention in cluster)
    )


def _validate_coreference_analysis(source: str, analysis: CoreferenceAnalysis) -> None:
    if analysis.text != source:
        raise ValueError("coreference analysis does not match the source text")
    for cluster in analysis.clusters:
        for mention in cluster:
            if (
                mention.start < 0
                or mention.end <= mention.start
                or mention.end > len(source)
                or source[mention.start : mention.end] != mention.text
            ):
                raise ValueError("coreference mention has invalid source offsets")


def _canonical_mention(
    cluster: Sequence[CoreferenceMention],
    policy: CanonicalizationPolicy,
) -> CoreferenceMention | None:
    accepted = {"PROPN"}
    if policy is CanonicalizationPolicy.EXPLICIT_NOMINAL:
        accepted.add("NOUN")
    candidates = [mention for mention in cluster if accepted.intersection(mention.pos_tags)]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda mention: (len(mention.text.split()), len(mention.text), -mention.start),
    )


def _representation(policy: CanonicalizationPolicy) -> str:
    if policy is CanonicalizationPolicy.PROPER_NOUN:
        return _COREF_PROPN
    return _COREF_NOMINAL


def coreference_policies(
    strategy: RetrievalStrategyName,
) -> tuple[CanonicalizationPolicy, ...]:
    if strategy is RetrievalStrategyName.COREF_PROPN:
        return (CanonicalizationPolicy.PROPER_NOUN,)
    if strategy is RetrievalStrategyName.COREF_NOMINAL:
        return (CanonicalizationPolicy.EXPLICIT_NOMINAL,)
    if strategy is RetrievalStrategyName.COREF_MAX:
        return (
            CanonicalizationPolicy.PROPER_NOUN,
            CanonicalizationPolicy.EXPLICIT_NOMINAL,
        )
    raise ValueError(f"{strategy.value} is not a coreference strategy")


def bm25_fusion_vector_strategy(
    strategy: RetrievalStrategyName,
) -> RetrievalStrategyName | None:
    return {
        RetrievalStrategyName.BM25_TOKEN_WINDOW_RRF: RetrievalStrategyName.TOKEN_WINDOW,
        RetrievalStrategyName.BM25_COREF_PROPN_RRF: RetrievalStrategyName.COREF_PROPN,
        RetrievalStrategyName.BM25_COREF_NOMINAL_RRF: RetrievalStrategyName.COREF_NOMINAL,
        RetrievalStrategyName.BM25_COREF_MAX_RRF: RetrievalStrategyName.COREF_MAX,
        RetrievalStrategyName.BM25_SENTENCE_PACK_RRF: RetrievalStrategyName.SENTENCE_PACK,
        RetrievalStrategyName.BM25_COREF_AWARE_PACK_RRF: RetrievalStrategyName.COREF_AWARE_PACK,
        RetrievalStrategyName.BM25_COREF_INTERVAL_PACK_RRF: RetrievalStrategyName.COREF_INTERVAL_PACK,
    }.get(strategy)


def pooled_incremental_vector_strategy(
    strategy: RetrievalStrategyName,
) -> RetrievalStrategyName | None:
    return {
        RetrievalStrategyName.POOLED_SENTENCE_PACK_RRF: RetrievalStrategyName.SENTENCE_PACK,
        RetrievalStrategyName.POOLED_COREF_AWARE_PACK_RRF: RetrievalStrategyName.COREF_AWARE_PACK,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_PACK_RRF: RetrievalStrategyName.COREF_INTERVAL_PACK,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_MSMARCO: RetrievalStrategyName.COREF_INTERVAL_PACK,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT: RetrievalStrategyName.COREF_INTERVAL_PACK,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_RANKZEPHYR: RetrievalStrategyName.COREF_INTERVAL_PACK,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_MULTIVIEW_COLBERT: RetrievalStrategyName.COREF_INTERVAL_PACK,
    }.get(strategy)


def pooled_single_reranker(strategy: RetrievalStrategyName) -> str | None:
    return {
        RetrievalStrategyName.POOLED_COLBERT: "colbert",
        RetrievalStrategyName.POOLED_COREF_INTERVAL_MSMARCO: "msmarco",
        RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT: "colbert",
        RetrievalStrategyName.POOLED_COREF_INTERVAL_RANKZEPHYR: "rankzephyr",
    }.get(strategy)
