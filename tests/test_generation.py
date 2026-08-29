from __future__ import annotations

from collections.abc import Sequence

import pytest

from scifact_rag.domain import EvidenceChunk, SearchHit
from scifact_rag.generation import DpChunkContextAssembler, WholeDocumentContextAssembler
from scifact_rag.strategies import COREF_NOMINAL_DP_COLBERT


class FakeChunkStore:
    def __init__(self, chunks: Sequence[EvidenceChunk]) -> None:
        self.chunks = list(chunks)
        self.requests: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    def load_chunks(
        self,
        document_ids: Sequence[str],
        representations: Sequence[str],
    ) -> list[EvidenceChunk]:
        self.requests.append((tuple(document_ids), tuple(representations)))
        return self.chunks


class FakeReranker:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.calls: list[tuple[str, list[SearchHit]]] = []

    def score(self, query: str, documents: Sequence[SearchHit]) -> list[float]:
        self.calls.append((query, list(documents)))
        return [self.scores[document.text] for document in documents]


def _chunk(doc_id: str, ordinal: int, text: str) -> EvidenceChunk:
    return EvidenceChunk(
        doc_id,
        ordinal,
        text,
        COREF_NOMINAL_DP_COLBERT,
        embedding_required=False,
    )


def test_whole_document_context_preserves_retrieved_evidence() -> None:
    evidence = [SearchHit("1", "Title", "Whole abstract.", 0.8)]

    assembled = WholeDocumentContextAssembler().assemble("claim", evidence)

    assert assembled == evidence
    assert assembled is not evidence


def test_top_dp_chunks_preserve_parent_rank_and_source_order_with_a_per_parent_cap() -> None:
    parents = [
        SearchHit("2", "Second", "second whole", 0.9),
        SearchHit("1", "First", "first whole", 0.8),
    ]
    store = FakeChunkStore(
        [
            _chunk("1", 2, "one-c"),
            _chunk("2", 1, "two-b"),
            _chunk("1", 0, "one-a"),
            _chunk("2", 0, "two-a"),
            _chunk("1", 1, "one-b"),
            _chunk("2", 2, "two-c"),
        ]
    )
    reranker = FakeReranker(
        {
            "two-a": 0.8,
            "two-b": 0.1,
            "two-c": 0.9,
            "one-a": 0.2,
            "one-b": 0.7,
            "one-c": 0.6,
        }
    )

    assembled = DpChunkContextAssembler(store, reranker).assemble("claim", parents)

    assert [(hit.doc_id, hit.text, hit.score) for hit in assembled] == [
        ("2", "two-a", 0.9),
        ("2", "two-c", 0.9),
        ("1", "one-b", 0.8),
        ("1", "one-c", 0.8),
    ]
    assert store.requests == [
        (("2", "1"), (COREF_NOMINAL_DP_COLBERT,)),
    ]
    assert reranker.calls[0][0] == "claim"
    assert [hit.text for hit in reranker.calls[0][1]] == [
        "two-a",
        "two-b",
        "two-c",
        "one-a",
        "one-b",
        "one-c",
    ]


def test_adaptive_preserves_exact_single_view_abstract_and_scores_long_documents() -> None:
    parents = [
        SearchHit("short", "Short", "Exact abstract.", 0.9),
        SearchHit("long", "Long", "Long complete abstract.", 0.8),
    ]
    store = FakeChunkStore(
        [
            _chunk("short", 0, "Exact abstract."),
            _chunk("long", 0, "Long first."),
            _chunk("long", 1, "Long second."),
            _chunk("long", 2, "Long third."),
        ]
    )
    reranker = FakeReranker({"Long first.": 0.4, "Long second.": 0.9, "Long third.": 0.8})

    assembled = DpChunkContextAssembler(store, reranker, adaptive=True).assemble("claim", parents)

    assert assembled == [
        parents[0],
        SearchHit("long", "Long", "Long second.", 0.8),
        SearchHit("long", "Long", "Long third.", 0.8),
    ]
    assert [hit.text for hit in reranker.calls[0][1]] == [
        "Long first.",
        "Long second.",
        "Long third.",
    ]
    assert all(not hit.title for hit in reranker.calls[0][1])


def test_adaptive_does_not_invoke_the_reranker_when_all_abstracts_are_exact_views() -> None:
    parent = SearchHit("short", "Short", "Exact abstract.", 0.9)
    reranker = FakeReranker({})

    assembled = DpChunkContextAssembler(
        FakeChunkStore([_chunk("short", 0, "Exact abstract.")]),
        reranker,
        adaptive=True,
    ).assemble("claim", [parent])

    assert assembled == [parent]
    assert reranker.calls == []


@pytest.mark.parametrize(
    "chunks",
    (
        [],
        [_chunk("foreign", 0, "foreign")],
        [_chunk("1", 0, "one"), _chunk("1", 0, "duplicate")],
        [EvidenceChunk("1", 0, "wrong", "token-window")],
        [_chunk("1", 0, "   ")],
    ),
)
def test_dp_context_rejects_missing_or_invalid_stored_views(
    chunks: list[EvidenceChunk],
) -> None:
    assembler = DpChunkContextAssembler(FakeChunkStore(chunks), FakeReranker({}))

    with pytest.raises(ValueError):
        assembler.assemble("claim", [SearchHit("1", "Title", "whole", 1.0)])


def test_dp_context_rejects_nonfinite_or_misaligned_scores() -> None:
    chunk = _chunk("1", 0, "one")
    parent = [SearchHit("1", "Title", "whole", 1.0)]

    with pytest.raises(ValueError, match="non-finite"):
        DpChunkContextAssembler(
            FakeChunkStore([chunk]),
            FakeReranker({"one": float("nan")}),
        ).assemble("claim", parent)

    class MissingScoreReranker:
        def score(self, query: str, documents: Sequence[SearchHit]) -> list[float]:
            return []

    with pytest.raises(ValueError, match="wrong number"):
        DpChunkContextAssembler(FakeChunkStore([chunk]), MissingScoreReranker()).assemble(
            "claim", parent
        )
