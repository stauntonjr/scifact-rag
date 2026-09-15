from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, cast

import httpx

from ..proposition import (
    GroundedProposition,
    GroundedSpan,
    PropositionPolarity,
    PropositionQualifier,
    QualifierRole,
    validate_propositions,
)
from ..proposition_evaluation import PropositionSource

PROPOSITION_PROMPT_ID = "grounded-proposition-extraction-v1"
PROPOSITION_SEED = 1729
_SPAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["start", "end", "text"],
    "properties": {
        "start": {"type": "integer", "minimum": 0},
        "end": {"type": "integer", "minimum": 1},
        "text": {"type": "string", "minLength": 1},
    },
}
_QUALIFIER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["role", "span"],
    "properties": {
        "role": {"enum": [role.value for role in QualifierRole]},
        "span": _SPAN_SCHEMA,
    },
}
_PROPOSITION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sentence", "subject", "predicate", "object", "polarity", "qualifiers"],
    "properties": {
        "sentence": _SPAN_SCHEMA,
        "subject": _SPAN_SCHEMA,
        "predicate": _SPAN_SCHEMA,
        "object": _SPAN_SCHEMA,
        "polarity": {"enum": [value.value for value in PropositionPolarity]},
        "qualifiers": {"type": "array", "items": _QUALIFIER_SCHEMA},
    },
}
_BASE_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["source_kind", "source_id", "source_sha256", "propositions"],
    "properties": {
        "source_kind": {"enum": ["claim", "document"]},
        "source_id": {"type": "string", "minLength": 1},
        "source_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "propositions": {"type": "array", "items": _PROPOSITION_SCHEMA},
    },
}
PROPOSITION_SCHEMA_SHA256 = hashlib.sha256(
    json.dumps(_BASE_RESPONSE_SCHEMA, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
_SYSTEM_PROMPT = f"""Protocol: {PROPOSITION_PROMPT_ID}
Schema SHA-256: {PROPOSITION_SCHEMA_SHA256}
Extract explicit scientific propositions only from the supplied source. Return verbatim subject,
predicate, object, and qualifier spans with Python Unicode code-point [start,end) offsets. Preserve
negation as polarity. Do not use outside knowledge, infer missing relations, normalize source text,
or call tools. Return an empty propositions array when no complete relation is explicit."""
PROPOSITION_PROMPT_SHA256 = hashlib.sha256(_SYSTEM_PROMPT.encode("utf-8")).hexdigest()
_RESPONSE_KEYS = {"source_kind", "source_id", "source_sha256", "propositions"}
_PROPOSITION_KEYS = {"sentence", "subject", "predicate", "object", "polarity", "qualifiers"}


class PropositionExtractionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class OpenAiCompatiblePropositionExtractor:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        if not base_url.strip() or not model.strip() or timeout_seconds <= 0:
            raise ValueError("extractor requires a URL, model, and positive timeout")
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._api_key = api_key
        self._timeout = timeout_seconds

    def extract(self, source: PropositionSource) -> tuple[GroundedProposition, ...]:
        request = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "source_kind": source.kind.value,
                            "source_id": source.source_id,
                            "source_sha256": source.sha256,
                            "source_text": source.text,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0,
            "seed": PROPOSITION_SEED,
            "max_tokens": 2048,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "grounded_propositions",
                    "strict": True,
                    "schema": _response_schema(source),
                },
            },
        }
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            response = httpx.post(
                self._endpoint,
                headers=headers,
                json=request,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise PropositionExtractionError("http", "proposition request failed") from error
        try:
            envelope = response.json()
            content = envelope["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise PropositionExtractionError(
                "envelope", "invalid chat-completions response"
            ) from error
        if not isinstance(content, str):
            raise PropositionExtractionError("envelope", "response content must be text")
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise PropositionExtractionError("json", "response content is not JSON") from error
        return self._parse_payload(source, payload)

    @staticmethod
    def _parse_payload(
        source: PropositionSource,
        payload: object,
    ) -> tuple[GroundedProposition, ...]:
        if not isinstance(payload, Mapping) or set(payload) != _RESPONSE_KEYS:
            raise PropositionExtractionError("schema", "response fields do not match schema")
        if (
            payload["source_kind"] != source.kind.value
            or payload["source_id"] != source.source_id
            or payload["source_sha256"] != source.sha256
        ):
            raise PropositionExtractionError(
                "source-mismatch", "response source does not match request"
            )
        raw_propositions = payload["propositions"]
        if not isinstance(raw_propositions, list):
            raise PropositionExtractionError("schema", "propositions must be an array")
        try:
            propositions = tuple(_parse_proposition(source, value) for value in raw_propositions)
        except (KeyError, TypeError, ValueError) as error:
            code = (
                "grounding" if isinstance(error, ValueError) and "span" in str(error) else "schema"
            )
            raise PropositionExtractionError(code, str(error)) from error
        try:
            validate_propositions(source.text, propositions)
        except (TypeError, ValueError) as error:
            raise PropositionExtractionError("grounding", str(error)) from error
        return propositions


def _response_schema(source: PropositionSource) -> dict[str, object]:
    schema = cast(dict[str, Any], json.loads(json.dumps(_BASE_RESPONSE_SCHEMA)))
    properties = cast(dict[str, object], schema["properties"])
    properties["source_kind"] = {"const": source.kind.value}
    properties["source_id"] = {"const": source.source_id}
    properties["source_sha256"] = {"const": source.sha256}
    return schema


def _parse_proposition(source: PropositionSource, raw: object) -> GroundedProposition:
    if not isinstance(raw, Mapping) or set(raw) != _PROPOSITION_KEYS:
        raise TypeError("proposition fields do not match schema")
    qualifiers = raw["qualifiers"]
    if not isinstance(qualifiers, list):
        raise TypeError("qualifiers must be an array")
    return GroundedProposition(
        source_kind=source.kind,
        source_id=source.source_id,
        source_sha256=source.sha256,
        sentence=_parse_span(raw["sentence"]),
        subject=_parse_span(raw["subject"]),
        predicate=_parse_span(raw["predicate"]),
        object=_parse_span(raw["object"]),
        polarity=PropositionPolarity(raw["polarity"]),
        qualifiers=tuple(_parse_qualifier(value) for value in qualifiers),
    )


def _parse_qualifier(raw: object) -> PropositionQualifier:
    if not isinstance(raw, Mapping) or set(raw) != {"role", "span"}:
        raise TypeError("qualifier fields do not match schema")
    return PropositionQualifier(QualifierRole(raw["role"]), _parse_span(raw["span"]))


def _parse_span(raw: object) -> GroundedSpan:
    if not isinstance(raw, Mapping) or set(raw) != {"start", "end", "text"}:
        raise TypeError("span fields do not match schema")
    return GroundedSpan(raw["start"], raw["end"], raw["text"])
