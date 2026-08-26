from __future__ import annotations

from collections.abc import Sequence
from typing import Any

_WINDOW_TOKENS = 126
_OVERLAP_TOKENS = 32


class MiniLmEmbedder:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model: Any = SentenceTransformer(model_name)

    def document_chunks(self, text: str) -> list[str]:
        tokenizer = self._model[0].tokenizer
        token_ids = tokenizer.encode(
            text,
            add_special_tokens=False,
            truncation=False,
            verbose=False,
        )
        step = _WINDOW_TOKENS - _OVERLAP_TOKENS
        chunks: list[str] = []
        for start in range(0, len(token_ids), step):
            window = token_ids[start : start + _WINDOW_TOKENS]
            if not window:
                break
            chunks.append(tokenizer.decode(window, skip_special_tokens=True))
            if start + _WINDOW_TOKENS >= len(token_ids):
                break
        return chunks or [text]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()
