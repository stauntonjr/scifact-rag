from __future__ import annotations

from collections.abc import Sequence

import httpx

from ..domain import GeneratedAnswer, SearchHit

_SYSTEM = """You answer only from the supplied scientific evidence.
Use citations in the exact form [document_id] after each supported claim.
Report only what the evidence directly establishes. Do not turn associations or animal-model
results into human causal claims, and state material limitations when they affect the answer.
If the evidence does not support an answer, respond exactly: insufficient evidence
Do not use outside knowledge and do not call tools."""


class OpenAiCompatibleGenerator:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout_seconds

    @property
    def model(self) -> str:
        return self._model

    def generate(self, query: str, evidence: Sequence[SearchHit]) -> str:
        return self.generate_with_metrics(query, evidence).text

    def generate_with_metrics(
        self,
        query: str,
        evidence: Sequence[SearchHit],
    ) -> GeneratedAnswer:
        context = "\n\n".join(f"[{hit.doc_id}] {hit.title}\n{hit.text}" for hit in evidence)
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        response = httpx.post(
            f"{self._base_url}/chat/completions",
            headers=headers,
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {
                        "role": "user",
                        "content": f"Question: {query}\n\nEvidence:\n{context}",
                    },
                ],
                "temperature": 0.1,
                "max_tokens": 512,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("generator returned an invalid chat-completions response") from exc
        if not isinstance(content, str):
            raise TypeError("generator response content must be text")
        usage = payload.get("usage")
        if usage is None:
            input_tokens = None
            generated_tokens = None
        elif isinstance(usage, dict):
            input_tokens = _token_count(usage, "prompt_tokens")
            generated_tokens = _token_count(usage, "completion_tokens")
        else:
            raise TypeError("generator response usage must be an object")
        return GeneratedAnswer(content, input_tokens, generated_tokens)


def _token_count(usage: dict[object, object], field: str) -> int:
    value = usage.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"generator response {field} must be a non-negative integer")
    return value
