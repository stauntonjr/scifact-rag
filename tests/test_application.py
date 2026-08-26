from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from scifact_rag.application import RagApplication
from scifact_rag.domain import EvidenceDocument, SearchHit


class FakeCorpus:
    def documents(self) -> Iterable[EvidenceDocument]:
        return (
            EvidenceDocument("1", "one", "first"),
            EvidenceDocument("2", "two", "second"),
            EvidenceDocument("3", "three", "third"),
        )

    def queries(self) -> Mapping[str, str]:
        return {"q1": "first"}

    def qrels(self) -> Mapping[str, Mapping[str, int]]:
        return {"q1": {"1": 1}}


class FakeEmbedder:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]


class FakeStore:
    def __init__(self, hits: Sequence[SearchHit] = ()) -> None:
        self.initialized = False
        self.batches: list[list[EvidenceDocument]] = []
        self.hits = list(hits)

    def initialize(self) -> None:
        self.initialized = True

    def upsert(
        self, documents: Sequence[EvidenceDocument], embeddings: Sequence[Sequence[float]]
    ) -> None:
        assert len(documents) == len(embeddings)
        self.batches.append(list(documents))

    def search(self, embedding: Sequence[float], limit: int) -> list[SearchHit]:
        return self.hits[:limit]


class FakeGenerator:
    model = "fake-model"

    def __init__(self, text: str) -> None:
        self.text = text

    def generate(self, query: str, evidence: Sequence[SearchHit]) -> str:
        return self.text


def test_ingest_batches_every_document() -> None:
    store = FakeStore()
    application = RagApplication(store=store, embedder=FakeEmbedder(), generator=FakeGenerator(""))

    result = application.ingest(FakeCorpus(), batch_size=2)

    assert store.initialized
    assert result.documents == 3
    assert [[document.doc_id for document in batch] for batch in store.batches] == [
        ["1", "2"],
        ["3"],
    ]


def test_ask_accepts_only_retrieved_document_citations() -> None:
    hit = SearchHit("42", "evidence", "supported text", 0.9)
    store = FakeStore([hit])
    grounded = RagApplication(
        store=store,
        embedder=FakeEmbedder(),
        generator=FakeGenerator("Supported answer [42]"),
    )
    ungrounded = RagApplication(
        store=store,
        embedder=FakeEmbedder(),
        generator=FakeGenerator("Unsupported answer [99]"),
    )

    accepted = grounded.ask("question")
    rejected = ungrounded.ask("question")

    assert accepted.citations == ("42",)
    assert accepted.text == "Supported answer [42]"
    assert rejected.citations == ()
    assert rejected.text == "insufficient evidence"


def test_ask_without_evidence_does_not_call_generator() -> None:
    application = RagApplication(
        store=FakeStore(), embedder=FakeEmbedder(), generator=FakeGenerator("ignored")
    )

    answer = application.ask("question")

    assert answer.text == "insufficient evidence"
    assert answer.evidence == ()
