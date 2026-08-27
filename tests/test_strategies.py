from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace

import pytest

from scifact_rag.adapters.coreference import FastCorefAnalyzer
from scifact_rag.adapters.minilm import MiniLmEmbedder
from scifact_rag.adapters.tokenization import HuggingFaceTokenBudget
from scifact_rag.domain import (
    CoreferenceAnalysis,
    CoreferenceMention,
    EvidenceDocument,
    SentenceSpan,
)
from scifact_rag.strategies import (
    COREF_NOMINAL_DP_COLBERT,
    COREF_NOMINAL_DP_MINILM,
    CanonicalizationPolicy,
    CompositeRepresentationStrategy,
    CoreferenceIntervalPackingStrategy,
    CoreferenceNominalDpStrategy,
    CoreferenceSentenceStrategy,
    DpBoundaryProfile,
    RetrievalStrategyName,
    SentencePackingStrategy,
    TitleStrategy,
    TokenWindowStrategy,
    _coreference_boundary_cut_cost,
    bm25_fusion_vector_strategy,
    coreference_policies,
    pooled_incremental_vector_strategy,
    pooled_single_reranker,
    resolve_coreferences,
)


def mention(
    text: str,
    value: str,
    pos: str,
    *,
    start: int = 0,
    possessive: bool = False,
) -> CoreferenceMention:
    resolved_start = text.index(value, start)
    return CoreferenceMention(
        resolved_start,
        resolved_start + len(value),
        value,
        (pos,),
        possessive,
    )


class FakeAnalyzer:
    def analyze(self, texts: Sequence[str]) -> list[CoreferenceAnalysis]:
        analyses: list[CoreferenceAnalysis] = []
        for text in texts:
            aspirin = mention(text, "Aspirin", "PROPN")
            pronoun = mention(text, "It", "PRON")
            analyses.append(CoreferenceAnalysis(text, ((aspirin, pronoun),)))
        return analyses

    def sentences(self, text: str) -> list[str]:
        return [part.strip() + "." for part in text.split(".") if part.strip()]

    def sentence_spans(self, text: str) -> list[SentenceSpan]:
        spans: list[SentenceSpan] = []
        cursor = 0
        for sentence in self.sentences(text):
            start = text.index(sentence, cursor)
            end = start + len(sentence)
            spans.append(SentenceSpan(start, end, sentence))
            cursor = end
        return spans


def test_proper_noun_and_nominal_policies_remain_distinct() -> None:
    text = "A treatment was tested. It helped."
    treatment = mention(text, "treatment", "NOUN")
    pronoun = mention(text, "It", "PRON")
    analysis = CoreferenceAnalysis(text, ((treatment, pronoun),))

    strict = resolve_coreferences(analysis, CanonicalizationPolicy.PROPER_NOUN)
    nominal = resolve_coreferences(analysis, CanonicalizationPolicy.EXPLICIT_NOMINAL)

    assert strict == text
    assert nominal == "A treatment was tested. treatment helped."


def test_proper_noun_policy_resolves_possessive_mentions() -> None:
    text = "Aspirin was tested. Its effect was measured."
    aspirin = mention(text, "Aspirin", "PROPN")
    possessive = mention(text, "Its", "PRON", possessive=True)
    analysis = CoreferenceAnalysis(text, ((aspirin, possessive),))

    resolved = resolve_coreferences(analysis, CanonicalizationPolicy.PROPER_NOUN)

    assert resolved == "Aspirin was tested. Aspirin's effect was measured."


def test_title_is_a_dedicated_single_representation() -> None:
    strategy = TitleStrategy()

    chunks = strategy.chunks(
        [EvidenceDocument("1", " Study title ", "Abstract"), EvidenceDocument("2", "", "Other")]
    )

    assert strategy.representations == ("title",)
    assert [
        (chunk.doc_id, chunk.ordinal, chunk.text, chunk.representation) for chunk in chunks
    ] == [("1", 0, "Study title", "title")]


def test_coreference_max_excludes_title_and_keeps_both_sentence_representations() -> None:
    strategy = CoreferenceSentenceStrategy(
        FakeAnalyzer(),
        coreference_policies(RetrievalStrategyName.COREF_MAX),
    )

    chunks = strategy.chunks([EvidenceDocument("1", "Study title", "Aspirin worked. It helped.")])

    assert strategy.name == "coref-max"
    assert strategy.representations == (
        "coref-propn-sentence",
        "coref-nominal-sentence",
    )
    assert {chunk.representation for chunk in chunks} == set(strategy.representations)
    assert all(chunk.text != "Study title" for chunk in chunks)
    assert any(chunk.text == "Aspirin helped." for chunk in chunks)


def test_token_window_strategy_embeds_only_the_abstract() -> None:
    seen: list[str] = []

    def window(text: str) -> list[str]:
        seen.append(text)
        return [text]

    strategy = TokenWindowStrategy(window)
    chunks = strategy.chunks([EvidenceDocument("1", "Title", "Abstract")])

    assert seen == ["Abstract"]
    assert chunks[0].representation == "token-window"


def test_sentence_pack_excludes_title_and_packs_adjacent_sentences() -> None:
    strategy = SentencePackingStrategy(
        FakeAnalyzer(),
        lambda text: len(text.split()),
        lambda text: [text],
        target_tokens=4,
        maximum_tokens=6,
    )

    chunks = strategy.chunks(
        [EvidenceDocument("1", "Study title", "Alpha beta. Gamma delta. Epsilon zeta.")]
    )

    assert strategy.name == "sentence-pack"
    assert strategy.representations == ("sentence-pack",)
    assert [(chunk.representation, chunk.text) for chunk in chunks] == [
        ("sentence-pack", "Alpha beta. Gamma delta."),
        ("sentence-pack", "Epsilon zeta."),
    ]


def test_only_a_crossing_coreference_chain_can_use_soft_boundary_slack() -> None:
    plain = SentencePackingStrategy(
        FakeAnalyzer(),
        lambda text: len(text.split()),
        lambda text: [text],
        target_tokens=4,
        maximum_tokens=6,
    )
    aware = SentencePackingStrategy(
        FakeAnalyzer(),
        lambda text: len(text.split()),
        lambda text: [text],
        coreference_aware=True,
        target_tokens=4,
        maximum_tokens=6,
    )
    document = EvidenceDocument("1", "", "Aspirin works today. It helps greatly.")

    assert [chunk.text for chunk in plain.chunks([document])] == [
        "Aspirin works today.",
        "It helps greatly.",
    ]
    assert [chunk.text for chunk in aware.chunks([document])] == [
        "Aspirin works today. Aspirin helps greatly."
    ]


def test_sentence_pack_uses_hard_split_for_an_overlong_sentence() -> None:
    strategy = SentencePackingStrategy(
        FakeAnalyzer(),
        lambda text: len(text.split()),
        lambda text: ["one two three four", "five six"],
        target_tokens=3,
        maximum_tokens=4,
    )

    chunks = strategy.chunks([EvidenceDocument("1", "", "one two three four five six.")])

    assert [chunk.text for chunk in chunks] == ["one two three four", "five six"]


def test_bounded_token_windows_account_for_decode_retokenization_growth() -> None:
    class GrowingTokenizer:
        def encode(self, text: str, **_: object) -> list[int]:
            if text == "source":
                return list(range(130))
            return list(range(len(text.split()) + 1))

        def decode(self, token_ids: Sequence[int], **_: object) -> str:
            return " ".join("token" for _ in token_ids)

    embedder = MiniLmEmbedder.__new__(MiniLmEmbedder)
    embedder._model = [SimpleNamespace(tokenizer=GrowingTokenizer())]

    chunks = embedder.bounded_token_windows("source")

    assert len(chunks) == 2
    assert all(embedder.content_token_count(chunk) <= 126 for chunk in chunks)


def test_exact_token_budget_hard_split_preserves_raw_source_substrings() -> None:
    class OffsetTokenizer:
        @staticmethod
        def _offsets(text: str) -> list[tuple[int, int]]:
            offsets: list[tuple[int, int]] = []
            cursor = 0
            for token in text.split():
                start = text.index(token, cursor)
                offsets.append((start, start + len(token)))
                cursor = start + len(token)
            return offsets

        def __call__(self, text: str, **_: object) -> dict[str, list[tuple[int, int]]]:
            return {"offset_mapping": self._offsets(text)}

        def encode(self, text: str, **_: object) -> list[int]:
            growth = 0 if text == source else 1
            return list(range(len(self._offsets(text)) + growth))

    budget = HuggingFaceTokenBudget.__new__(HuggingFaceTokenBudget)
    budget._tokenizer = OffsetTokenizer()
    budget._maximum_content_tokens = 2
    source = "Alpha  beta gamma   delta"

    chunks = budget.bounded_source_windows(source)

    assert chunks == ["Alpha", "beta", "gamma", "delta"]
    assert all(chunk in source for chunk in chunks)
    assert all(budget.content_token_count(chunk) <= 2 for chunk in chunks)


def test_coreference_chain_can_delay_a_soft_boundary_but_not_the_hard_limit() -> None:
    strategy = SentencePackingStrategy(
        FakeAnalyzer(),
        lambda text: len(text.split()),
        lambda text: [text],
        coreference_aware=True,
        target_tokens=2,
        maximum_tokens=5,
    )

    chunks = strategy.chunks(
        [EvidenceDocument("1", "", "Aspirin works. It reduces pain. Results persisted.")]
    )

    assert strategy.name == "coref-aware-pack"
    assert [chunk.text for chunk in chunks] == [
        "Aspirin works. Aspirin reduces pain.",
        "Results persisted.",
    ]
    assert all(len(chunk.text.split()) <= 5 for chunk in chunks)


def test_interval_packing_looks_ahead_to_preserve_a_chain_greedy_packing_cuts() -> None:
    text = "Background alpha beta gamma delta epsilon zeta. Aspirin works well. It reduces pain."
    aspirin = mention(text, "Aspirin", "PROPN")
    pronoun = mention(text, "It", "PRON")
    analyzer = FakeAnalyzer()
    analyzer.analyze = lambda texts: [  # type: ignore[method-assign]
        CoreferenceAnalysis(text, ((aspirin, pronoun),))
    ]
    greedy = SentencePackingStrategy(
        analyzer,
        lambda value: len(value.split()),
        lambda value: [value],
        coreference_aware=True,
        target_tokens=10,
        maximum_tokens=12,
    )
    interval = CoreferenceIntervalPackingStrategy(
        analyzer,
        lambda value: len(value.split()),
        lambda value: [value],
        target_tokens=10,
        maximum_tokens=12,
    )
    document = EvidenceDocument("1", "", text)

    assert [chunk.text for chunk in greedy.chunks([document])] == [
        "Background alpha beta gamma delta epsilon zeta. Aspirin works well.",
        "Aspirin reduces pain.",
    ]
    assert [chunk.text for chunk in interval.chunks([document])] == [
        "Background alpha beta gamma delta epsilon zeta.",
        "Aspirin works well. Aspirin reduces pain.",
    ]


def test_interval_boundary_cost_counts_each_proper_noun_chain_equally() -> None:
    text = "Aspirin and Ibuprofen worked. They helped."
    aspirin = mention(text, "Aspirin", "PROPN")
    ibuprofen = mention(text, "Ibuprofen", "PROPN")
    pronoun = mention(text, "They", "PRON")
    boundary = text.index("They")
    analysis = CoreferenceAnalysis(
        text,
        (
            (aspirin, pronoun),
            (ibuprofen, pronoun),
        ),
    )

    assert _coreference_boundary_cut_cost(analysis, boundary) == 2


def test_interval_packing_uses_bounded_fallback_for_an_overlong_sentence() -> None:
    text = "Aspirin one two three four five. It persisted."
    analyzer = FakeAnalyzer()
    strategy = CoreferenceIntervalPackingStrategy(
        analyzer,
        lambda value: len(value.split()),
        lambda value: ["Aspirin one two", "three four five."],
        target_tokens=3,
        maximum_tokens=3,
    )

    chunks = strategy.chunks([EvidenceDocument("1", "", text)])

    assert [chunk.text for chunk in chunks] == [
        "Aspirin one two",
        "three four five.",
        "Aspirin persisted.",
    ]
    assert all(len(chunk.text.split()) <= 3 for chunk in chunks)


def test_dual_nominal_dp_uses_one_analysis_and_raw_text_for_both_profiles() -> None:
    text = "The treatment works today. It reduces severe pain. Results persisted afterward."
    treatment = mention(text, "treatment", "NOUN")
    pronoun = mention(text, "It", "PRON")

    class CountingAnalyzer(FakeAnalyzer):
        calls = 0

        def analyze(self, texts: Sequence[str]) -> list[CoreferenceAnalysis]:
            self.calls += 1
            assert list(texts) == [text]
            return [CoreferenceAnalysis(text, ((treatment, pronoun),))]

    analyzer = CountingAnalyzer()
    strategy = CoreferenceNominalDpStrategy(
        analyzer,
        DpBoundaryProfile(
            COREF_NOMINAL_DP_MINILM,
            lambda value: len(value.split()),
            lambda value: [value],
            target_tokens=4,
            maximum_tokens=8,
            embedding_required=True,
        ),
        DpBoundaryProfile(
            COREF_NOMINAL_DP_COLBERT,
            lambda value: len(value.split()),
            lambda value: [value],
            target_tokens=12,
            maximum_tokens=12,
            embedding_required=False,
        ),
    )

    chunks = strategy.chunks([EvidenceDocument("1", "Title", text)])
    nominal = [chunk for chunk in chunks if chunk.representation == "coref-nominal-sentence"]
    small = [chunk for chunk in chunks if chunk.representation == COREF_NOMINAL_DP_MINILM]
    large = [chunk for chunk in chunks if chunk.representation == COREF_NOMINAL_DP_COLBERT]

    assert analyzer.calls == 1
    assert [chunk.text for chunk in nominal] == [
        "The treatment works today.",
        "treatment reduces severe pain.",
        "Results persisted afterward.",
    ]
    assert [chunk.text for chunk in small] == [
        "The treatment works today. It reduces severe pain.",
        "Results persisted afterward.",
    ]
    assert [chunk.text for chunk in large] == [text]
    assert all(chunk.text in text and chunk.embedding_required for chunk in small)
    assert all(chunk.text in text and not chunk.embedding_required for chunk in large)


def test_nominal_dp_boundary_cost_counts_noun_anchored_chains() -> None:
    text = "A treatment works. It helps. Evidence remains."
    analysis = CoreferenceAnalysis(
        text,
        ((mention(text, "treatment", "NOUN"), mention(text, "It", "PRON")),),
    )
    boundary = text.index("It")

    assert _coreference_boundary_cut_cost(analysis, boundary) == 0
    assert (
        _coreference_boundary_cut_cost(
            analysis,
            boundary,
            CanonicalizationPolicy.EXPLICIT_NOMINAL,
        )
        == 1
    )


@pytest.mark.parametrize(
    "analysis",
    (
        CoreferenceAnalysis(
            "Aspirin works. It helps.",
            (
                (
                    CoreferenceMention(0, 7, "Aspirin", ("PROPN",)),
                    CoreferenceMention(18, 23, "It", ("PRON",)),
                ),
            ),
        ),
        CoreferenceAnalysis(
            "Aspirin works. It helps.",
            (
                (
                    CoreferenceMention(0, 7, "Aspirin", ("PROPN",)),
                    CoreferenceMention(15, 99, "It", ("PRON",)),
                ),
            ),
        ),
    ),
)
def test_coreference_pack_rejects_invalid_mention_offsets(
    analysis: CoreferenceAnalysis,
) -> None:
    analyzer = FakeAnalyzer()
    analyzer.analyze = lambda texts: [analysis]  # type: ignore[method-assign]
    strategy = SentencePackingStrategy(
        analyzer,
        lambda text: len(text.split()),
        lambda text: [text],
        coreference_aware=True,
    )

    with pytest.raises(ValueError, match="invalid source offsets"):
        strategy.chunks([EvidenceDocument("1", "", "Aspirin works. It helps.")])


def test_coreference_pack_rejects_analysis_for_different_source_text() -> None:
    analyzer = FakeAnalyzer()
    analyzer.analyze = lambda texts: [CoreferenceAnalysis("different", ())]  # type: ignore[method-assign]
    strategy = SentencePackingStrategy(
        analyzer,
        lambda text: len(text.split()),
        lambda text: [text],
        coreference_aware=True,
    )

    with pytest.raises(ValueError, match="does not match"):
        strategy.chunks([EvidenceDocument("1", "", "Aspirin works. It helps.")])


def test_sentence_pack_rejects_invalid_source_offsets() -> None:
    analyzer = FakeAnalyzer()
    analyzer.sentence_spans = lambda text: [SentenceSpan(1, len(text), text)]  # type: ignore[method-assign]
    strategy = SentencePackingStrategy(analyzer, len, lambda text: [text])

    with pytest.raises(ValueError, match="invalid source offsets"):
        strategy.chunks([EvidenceDocument("1", "", "Sentence.")])


def test_sentence_segmentation_does_not_load_the_coreference_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyzer = FastCorefAnalyzer()
    sentence = SimpleNamespace(start_char=0, end_char=9, text="Sentence.")
    monkeypatch.setattr(
        analyzer, "_load_nlp", lambda: lambda text: SimpleNamespace(sents=[sentence])
    )

    assert analyzer.sentence_spans("Sentence.") == [SentenceSpan(0, 9, "Sentence.")]
    assert analyzer._model is None


def test_composite_strategy_populates_all_reranker_candidate_representations() -> None:
    strategy = CompositeRepresentationStrategy(
        RetrievalStrategyName.RERANK_MSMARCO.value,
        (
            TitleStrategy(),
            TokenWindowStrategy(lambda text: [text]),
            CoreferenceSentenceStrategy(
                FakeAnalyzer(),
                coreference_policies(RetrievalStrategyName.COREF_MAX),
            ),
        ),
    )

    chunks = strategy.chunks([EvidenceDocument("1", "Study title", "Aspirin worked. It helped.")])

    assert strategy.representations == (
        "title",
        "token-window",
        "coref-propn-sentence",
        "coref-nominal-sentence",
    )
    assert {chunk.representation for chunk in chunks} == set(strategy.representations)


def test_bm25_fusion_strategies_map_only_to_active_vector_approaches() -> None:
    assert {
        strategy: bm25_fusion_vector_strategy(strategy)
        for strategy in RetrievalStrategyName
        if bm25_fusion_vector_strategy(strategy) is not None
    } == {
        RetrievalStrategyName.BM25_TOKEN_WINDOW_RRF: RetrievalStrategyName.TOKEN_WINDOW,
        RetrievalStrategyName.BM25_COREF_PROPN_RRF: RetrievalStrategyName.COREF_PROPN,
        RetrievalStrategyName.BM25_COREF_NOMINAL_RRF: RetrievalStrategyName.COREF_NOMINAL,
        RetrievalStrategyName.BM25_COREF_MAX_RRF: RetrievalStrategyName.COREF_MAX,
        RetrievalStrategyName.BM25_SENTENCE_PACK_RRF: RetrievalStrategyName.SENTENCE_PACK,
        RetrievalStrategyName.BM25_COREF_AWARE_PACK_RRF: RetrievalStrategyName.COREF_AWARE_PACK,
        RetrievalStrategyName.BM25_COREF_INTERVAL_PACK_RRF: RetrievalStrategyName.COREF_INTERVAL_PACK,
    }


def test_incremental_pool_strategies_add_only_one_packing_approach() -> None:
    assert {
        strategy: pooled_incremental_vector_strategy(strategy)
        for strategy in RetrievalStrategyName
        if pooled_incremental_vector_strategy(strategy) is not None
    } == {
        RetrievalStrategyName.POOLED_SENTENCE_PACK_RRF: RetrievalStrategyName.SENTENCE_PACK,
        RetrievalStrategyName.POOLED_COREF_AWARE_PACK_RRF: RetrievalStrategyName.COREF_AWARE_PACK,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_PACK_RRF: RetrievalStrategyName.COREF_INTERVAL_PACK,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_MSMARCO: RetrievalStrategyName.COREF_INTERVAL_PACK,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT: RetrievalStrategyName.COREF_INTERVAL_PACK,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_RANKZEPHYR: RetrievalStrategyName.COREF_INTERVAL_PACK,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_MULTIVIEW_COLBERT: RetrievalStrategyName.COREF_INTERVAL_PACK,
    }


def test_expanded_interval_pool_rerankers_select_exactly_one_existing_scorer() -> None:
    assert {
        strategy: pooled_single_reranker(strategy)
        for strategy in RetrievalStrategyName
        if pooled_single_reranker(strategy) is not None
    } == {
        RetrievalStrategyName.POOLED_COLBERT: "colbert",
        RetrievalStrategyName.POOLED_COREF_INTERVAL_MSMARCO: "msmarco",
        RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT: "colbert",
        RetrievalStrategyName.POOLED_COREF_INTERVAL_RANKZEPHYR: "rankzephyr",
    }
    assert RetrievalStrategyName.TITLE_TOKEN_WINDOW_RRF.value == "title-token-window-rrf"


def test_robust_score_fusion_is_an_independent_opt_in_strategy() -> None:
    assert (
        RetrievalStrategyName.POOLED_FOUR_CHANNEL_ROBUST_SUM.value
        == "pooled-four-channel-robust-sum"
    )
    assert RetrievalStrategyName.TITLE_TOKEN_WINDOW_RRF.value == "title-token-window-rrf"


def test_colbert_is_an_independent_opt_in_pooled_strategy() -> None:
    assert RetrievalStrategyName.POOLED_COLBERT.value == "pooled-colbert"
    assert (
        RetrievalStrategyName.POOLED_COREF_INTERVAL_MULTIVIEW_COLBERT.value
        == "pooled-coref-interval-multiview-colbert"
    )
    assert RetrievalStrategyName.TITLE_TOKEN_WINDOW_RRF.value == "title-token-window-rrf"


def test_semantic_chunking_strategies_are_independent_from_the_title_fused_default() -> None:
    assert RetrievalStrategyName.SENTENCE_PACK.value == "sentence-pack"
    assert RetrievalStrategyName.COREF_AWARE_PACK.value == "coref-aware-pack"
    assert RetrievalStrategyName.COREF_INTERVAL_PACK.value == "coref-interval-pack"
    assert RetrievalStrategyName.TITLE_TOKEN_WINDOW_RRF.value == "title-token-window-rrf"
