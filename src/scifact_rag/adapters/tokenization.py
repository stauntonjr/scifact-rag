from __future__ import annotations

from typing import Any


class HuggingFaceTokenBudget:
    """Count and split source text with one pinned model tokenizer."""

    def __init__(
        self,
        model_name: str,
        *,
        maximum_content_tokens: int,
        revision: str | None = None,
    ) -> None:
        if not model_name or maximum_content_tokens < 1:
            raise ValueError("token budget requires a model and positive content limit")
        from transformers import AutoTokenizer

        self._tokenizer: Any = AutoTokenizer.from_pretrained(
            model_name,
            revision=revision,
            use_fast=True,
        )
        self._maximum_content_tokens = maximum_content_tokens

    def content_token_count(self, text: str) -> int:
        return len(self._content_token_ids(text))

    def bounded_source_windows(self, text: str) -> list[str]:
        encoded = self._tokenizer(
            text,
            add_special_tokens=False,
            truncation=False,
            return_offsets_mapping=True,
            verbose=False,
        )
        offsets = [tuple(offset) for offset in encoded["offset_mapping"] if offset[1] > offset[0]]
        bounded: list[str] = []
        start = 0
        while start < len(offsets):
            end = min(start + self._maximum_content_tokens, len(offsets))
            candidate = text[offsets[start][0] : offsets[end - 1][1]]
            while (
                end > start and self.content_token_count(candidate) > self._maximum_content_tokens
            ):
                end -= 1
                if end > start:
                    candidate = text[offsets[start][0] : offsets[end - 1][1]]
            if end <= start:
                raise ValueError("tokenizer could not produce a bounded raw-source window")
            bounded.append(candidate)
            start = end
        return bounded or [text]

    def _content_token_ids(self, text: str) -> list[int]:
        return self._tokenizer.encode(
            text,
            add_special_tokens=False,
            truncation=False,
            verbose=False,
        )
