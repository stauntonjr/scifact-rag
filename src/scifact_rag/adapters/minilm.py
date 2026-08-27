from __future__ import annotations

from collections.abc import Sequence
from typing import Any

_WINDOW_TOKENS = 126
_OVERLAP_TOKENS = 32


class MiniLmEmbedder:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model: Any = SentenceTransformer(model_name)

    def token_windows(self, text: str) -> list[str]:
        tokenizer = self._model[0].tokenizer
        token_ids = self._content_token_ids(text)
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

    def content_token_count(self, text: str) -> int:
        return len(self._content_token_ids(text))

    def bounded_token_windows(self, text: str) -> list[str]:
        tokenizer = self._model[0].tokenizer
        token_ids = self._content_token_ids(text)
        chunks: list[str] = []
        start = 0
        while start < len(token_ids):
            end = min(start + _WINDOW_TOKENS, len(token_ids))
            candidate = tokenizer.decode(token_ids[start:end], skip_special_tokens=True)
            while end > start and self.content_token_count(candidate) > _WINDOW_TOKENS:
                end -= 1
                candidate = tokenizer.decode(token_ids[start:end], skip_special_tokens=True)
            if end <= start:
                raise ValueError("tokenizer could not produce a bounded decoded window")
            chunks.append(candidate)
            if end >= len(token_ids):
                break
            start = max(start + 1, end - _OVERLAP_TOKENS)
        return chunks or [text]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def _content_token_ids(self, text: str) -> list[int]:
        return self._model[0].tokenizer.encode(
            text,
            add_special_tokens=False,
            truncation=False,
            verbose=False,
        )
