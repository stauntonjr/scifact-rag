from __future__ import annotations

import math
from collections.abc import Sequence
from enum import StrEnum

from .domain import EvidenceChunk, SearchHit
from .ports import Reranker, StoredChunkSource
from .strategies import COREF_NOMINAL_DP_COLBERT


class GenerationContextStrategyName(StrEnum):
    WHOLE_DOCUMENT = "whole-document"
    TOP_DP_CHUNKS = "top-dp-chunks"
    ADAPTIVE = "adaptive"


class WholeDocumentContextAssembler:
    def assemble(self, query: str, evidence: Sequence[SearchHit]) -> list[SearchHit]:
        return list(evidence)


class DpChunkContextAssembler:
    """Select bounded ColBERT-ranked DP chunks within retrieved parent documents."""

    def __init__(
        self,
        store: StoredChunkSource,
        reranker: Reranker,
        *,
        adaptive: bool = False,
        chunks_per_document: int = 2,
        representation: str = COREF_NOMINAL_DP_COLBERT,
    ) -> None:
        if chunks_per_document < 1:
            raise ValueError("chunks_per_document must be positive")
        if not representation:
            raise ValueError("generation context representation must not be empty")
        self._store = store
        self._reranker = reranker
        self._adaptive = adaptive
        self._chunks_per_document = chunks_per_document
        self._representation = representation

    def assemble(self, query: str, evidence: Sequence[SearchHit]) -> list[SearchHit]:
        if not evidence:
            return []
        parent_by_id = {hit.doc_id: hit for hit in evidence}
        if len(parent_by_id) != len(evidence):
            raise ValueError("generation context requires unique retrieved document identifiers")

        chunks = self._store.load_chunks(tuple(parent_by_id), (self._representation,))
        chunks_by_document = self._validate_chunks(chunks, set(parent_by_id))
        missing = [doc_id for doc_id in parent_by_id if not chunks_by_document[doc_id]]
        if missing:
            raise ValueError(
                "generation context store omitted required "
                f"{self._representation} views for: {', '.join(missing)}"
            )

        whole_document_ids = {
            hit.doc_id
            for hit in evidence
            if self._adaptive
            and len(chunks_by_document[hit.doc_id]) == 1
            and chunks_by_document[hit.doc_id][0].text == hit.text
        }
        flattened = [
            chunk
            for hit in evidence
            if hit.doc_id not in whole_document_ids
            for chunk in chunks_by_document[hit.doc_id]
        ]
        scores = (
            self._reranker.score(
                query,
                [SearchHit(chunk.doc_id, "", chunk.text, 0.0) for chunk in flattened],
            )
            if flattened
            else []
        )
        if len(scores) != len(flattened):
            raise ValueError("generation chunk reranker returned the wrong number of scores")
        if any(not math.isfinite(float(score)) for score in scores):
            raise ValueError("generation chunk reranker returned a non-finite score")

        scored_by_document: dict[str, list[tuple[float, EvidenceChunk]]] = {
            doc_id: [] for doc_id in parent_by_id
        }
        for chunk, score in zip(flattened, scores, strict=True):
            scored_by_document[chunk.doc_id].append((float(score), chunk))

        assembled: list[SearchHit] = []
        for parent in evidence:
            if parent.doc_id in whole_document_ids:
                assembled.append(parent)
                continue
            selected = sorted(
                scored_by_document[parent.doc_id],
                key=lambda item: (-item[0], item[1].ordinal),
            )[: self._chunks_per_document]
            for _, chunk in sorted(selected, key=lambda item: item[1].ordinal):
                assembled.append(SearchHit(parent.doc_id, parent.title, chunk.text, parent.score))
        return assembled

    def _validate_chunks(
        self,
        chunks: Sequence[EvidenceChunk],
        expected_ids: set[str],
    ) -> dict[str, list[EvidenceChunk]]:
        by_document: dict[str, list[EvidenceChunk]] = {doc_id: [] for doc_id in expected_ids}
        seen: set[tuple[str, int]] = set()
        for chunk in chunks:
            identity = (chunk.doc_id, chunk.ordinal)
            if (
                chunk.doc_id not in expected_ids
                or chunk.representation != self._representation
                or identity in seen
                or not chunk.text.strip()
            ):
                raise ValueError("generation context store returned an invalid or duplicate view")
            seen.add(identity)
            by_document[chunk.doc_id].append(chunk)
        for document_chunks in by_document.values():
            document_chunks.sort(key=lambda chunk: chunk.ordinal)
        return by_document
