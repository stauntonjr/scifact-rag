from __future__ import annotations

import hashlib
from collections.abc import Sequence
from enum import StrEnum

import httpx

from ..domain import GeneratedAnswer, SearchHit

_SYSTEM = """You answer only from the supplied scientific evidence.
Use citations in the exact form [document_id] after each supported claim.
Report only what the evidence directly establishes. Do not turn associations or animal-model
results into human causal claims, and state material limitations when they affect the answer.
If the evidence does not support an answer, respond exactly: insufficient evidence
Do not use outside knowledge and do not call tools."""

_SCIFACT_CLAIM_VERIFICATION_SYSTEM = """You verify one scientific claim using only the supplied evidence.
The first line must be exactly one of:
VERDICT: SUPPORT
VERDICT: CONTRADICT
VERDICT: NOT_ENOUGH_INFO
Use SUPPORT only when the evidence directly supports the claim and CONTRADICT only when it directly
contradicts the claim. Otherwise use NOT_ENOUGH_INFO.
For SUPPORT or CONTRADICT, follow the verdict with a concise explanation. Put each document citation
in its own exact [document_id] brackets after the claim it supports. Do not combine document IDs in
one pair of brackets.
For NOT_ENOUGH_INFO, the second line must be exactly: insufficient evidence
Do not turn associations or animal-model results into human causal claims. Preserve material
negation, qualifiers, populations, interventions, comparisons, outcomes, and limitations.
Do not use outside knowledge and do not call tools."""


class GenerationPromptProfile(StrEnum):
    RAG_ANSWER = "rag-answer-v1"
    SCIFACT_CLAIM_VERIFICATION = "scifact-claim-verification-v1"


SCIFACT_EVALUATION_PROMPT_ID = GenerationPromptProfile.SCIFACT_CLAIM_VERIFICATION.value
SCIFACT_EVALUATION_PROMPT_SHA256 = hashlib.sha256(
    _SCIFACT_CLAIM_VERIFICATION_SYSTEM.encode("utf-8")
).hexdigest()
SCIFACT_EVALUATION_SEED = 1729

_PROMPTS = {
    GenerationPromptProfile.RAG_ANSWER: _SYSTEM,
    GenerationPromptProfile.SCIFACT_CLAIM_VERIFICATION: _SCIFACT_CLAIM_VERIFICATION_SYSTEM,
}


class OpenAiCompatibleGenerator:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        prompt_profile: GenerationPromptProfile = GenerationPromptProfile.RAG_ANSWER,
        seed: int | None = None,
    ) -> None:
        if isinstance(seed, bool) or (seed is not None and (not isinstance(seed, int) or seed < 0)):
            raise ValueError("generator seed must be a non-negative integer or None")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._system_prompt = _PROMPTS[prompt_profile]
        self._seed = seed

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
        request: dict[str, object] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {
                    "role": "user",
                    "content": f"Question: {query}\n\nEvidence:\n{context}",
                },
            ],
            "temperature": 0.1,
            "max_tokens": 512,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if self._seed is not None:
            request["seed"] = self._seed
        response = httpx.post(
            f"{self._base_url}/chat/completions",
            headers=headers,
            json=request,
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
