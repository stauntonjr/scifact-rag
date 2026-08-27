from __future__ import annotations

from collections.abc import Sequence

import httpx

from ..domain import SearchHit


class TeiReranker:
    def __init__(self, base_url: str, *, timeout_seconds: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def score(self, query: str, documents: Sequence[SearchHit]) -> list[float]:
        if not documents:
            return []
        response = httpx.post(
            f"{self._base_url}/rerank",
            json={
                "query": query,
                "texts": [f"{document.title}\n{document.text}".strip() for document in documents],
                "return_text": False,
                "truncate": True,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or len(payload) != len(documents):
            raise ValueError("reranker returned the wrong number of scores")

        scores: list[float | None] = [None] * len(documents)
        try:
            for result in payload:
                index = result["index"]
                if not isinstance(index, int) or index < 0 or index >= len(documents):
                    raise ValueError("reranker returned an invalid document index")
                if scores[index] is not None:
                    raise ValueError("reranker returned a duplicate document index")
                scores[index] = float(result["score"])
        except (KeyError, TypeError) as exc:
            raise ValueError("reranker returned an invalid response") from exc
        if any(score is None for score in scores):
            raise ValueError("reranker omitted a document score")
        return [score for score in scores if score is not None]


class VllmColbertReranker:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout_seconds: float = 120.0,
    ) -> None:
        if not model:
            raise ValueError("late-interaction reranker requires a model")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    def score(self, query: str, documents: Sequence[SearchHit]) -> list[float]:
        if not documents:
            return []
        response = httpx.post(
            f"{self._base_url}/rerank",
            json={
                "model": self._model,
                "query": query,
                "documents": [
                    f"{document.title}\n{document.text}".strip() for document in documents
                ],
                "return_documents": False,
                "truncate_prompt_tokens": 512,
                "truncation_side": "right",
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise TypeError("late-interaction reranker returned an invalid response")
        results = payload["results"]
        if len(results) != len(documents):
            raise ValueError("late-interaction reranker returned the wrong number of scores")

        scores: list[float | None] = [None] * len(documents)
        try:
            for result in results:
                index = result["index"]
                if not isinstance(index, int) or index < 0 or index >= len(documents):
                    raise ValueError("late-interaction reranker returned an invalid document index")
                if scores[index] is not None:
                    raise ValueError(
                        "late-interaction reranker returned a duplicate document index"
                    )
                scores[index] = float(result["relevance_score"])
        except (KeyError, TypeError) as exc:
            raise ValueError("late-interaction reranker returned an invalid response") from exc
        if any(score is None for score in scores):
            raise ValueError("late-interaction reranker omitted a document score")
        return [score for score in scores if score is not None]


class RankLlmReranker:
    """Adapt RankLLM's listwise HTTP result order to the scalar reranker port."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 300.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def score(self, query: str, documents: Sequence[SearchHit]) -> list[float]:
        if not documents:
            return []
        response = httpx.post(
            f"{self._base_url}/v1/rerank",
            json={
                "query": query,
                "candidates": [
                    {
                        "docid": document.doc_id,
                        "score": 0.0,
                        "text": f"{document.title}\n{document.text}".strip(),
                    }
                    for document in documents
                ],
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != "castorini.cli.v1"
            or payload.get("repo") != "rank_llm"
            or payload.get("command") != "rerank"
            or payload.get("status") != "success"
            or payload.get("exit_code") != 0
            or not isinstance(payload.get("artifacts"), list)
        ):
            raise ValueError("RankLLM returned an invalid response envelope")

        artifacts = [
            artifact
            for artifact in payload["artifacts"]
            if isinstance(artifact, dict) and artifact.get("name") == "rerank-results"
        ]
        if len(artifacts) != 1 or artifacts[0].get("kind") != "data":
            raise ValueError("RankLLM returned an invalid rerank-results artifact")
        results = artifacts[0].get("value")
        if not isinstance(results, list) or len(results) != 1:
            raise ValueError("RankLLM returned the wrong number of query results")
        result = results[0]
        ranked = result.get("candidates") if isinstance(result, dict) else None
        if not isinstance(ranked, list) or len(ranked) != len(documents):
            raise ValueError("RankLLM returned the wrong number of candidates")

        expected = {document.doc_id for document in documents}
        if len(expected) != len(documents):
            raise ValueError("RankLLM input document identifiers must be unique")
        ranks: dict[str, int] = {}
        for rank, candidate in enumerate(ranked):
            doc_id = candidate.get("docid") if isinstance(candidate, dict) else None
            if not isinstance(doc_id, str) or doc_id not in expected:
                raise ValueError("RankLLM returned an unknown document identifier")
            if doc_id in ranks:
                raise ValueError("RankLLM returned a duplicate document identifier")
            ranks[doc_id] = rank
        if set(ranks) != expected:
            raise ValueError("RankLLM omitted a document identifier")

        # The upstream list order is authoritative. Strictly descending ordinal
        # scores preserve it through the application's scalar scorer boundary.
        return [float(len(documents) - ranks[document.doc_id]) for document in documents]
