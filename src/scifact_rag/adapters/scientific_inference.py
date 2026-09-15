from __future__ import annotations

from collections.abc import Mapping

import httpx

from ..scientific_inference import (
    InferenceLogits,
    InferenceRequest,
    InferenceResponse,
    inference_request_payload,
)

_RESPONSE_SCHEMA = "scientific-inference-response/v1"
_RESPONSE_KEYS = {
    "schema_version",
    "attempt_id",
    "model_revision",
    "pair_token_count",
    "logits",
}
_LOGIT_KEYS = {"entailment", "contradiction", "neutral"}


class ScientificInferenceProtocolError(ValueError):
    """The internal classifier returned a response outside its strict contract."""


class TransformersScientificInferenceClient:
    """One-attempt client for the internal Transformers classification service."""

    def __init__(
        self,
        base_url: str,
        model_revision: str,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not base_url.strip() or not model_revision.strip() or timeout_seconds <= 0:
            raise ValueError("inference client requires a URL, revision, and positive timeout")
        self._endpoint = f"{base_url.rstrip('/')}/v1/classify"
        self._model_revision = model_revision
        self._timeout_seconds = timeout_seconds

    def classify(self, request: InferenceRequest) -> InferenceResponse:
        payload = inference_request_payload(request)
        response = httpx.post(
            self._endpoint,
            json=payload,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, Mapping):
            raise ScientificInferenceProtocolError("response must be a JSON object")
        if set(body) != _RESPONSE_KEYS:
            raise ScientificInferenceProtocolError("response fields do not match the schema")
        if body["schema_version"] != _RESPONSE_SCHEMA:
            raise ScientificInferenceProtocolError("response schema version is unsupported")
        if body["attempt_id"] != request.attempt_id:
            raise ScientificInferenceProtocolError("response attempt identifier does not match")
        if body["model_revision"] != self._model_revision:
            raise ScientificInferenceProtocolError("response model revision does not match")
        pair_token_count = body["pair_token_count"]
        if (
            isinstance(pair_token_count, bool)
            or not isinstance(pair_token_count, int)
            or pair_token_count != request.expected_pair_tokens
        ):
            raise ScientificInferenceProtocolError("response pair token count does not match")
        logits_body = body["logits"]
        if not isinstance(logits_body, Mapping) or set(logits_body) != _LOGIT_KEYS:
            raise ScientificInferenceProtocolError("response must contain exactly three logits")
        try:
            logits = InferenceLogits(
                entailment=_numeric_logit(logits_body["entailment"]),
                contradiction=_numeric_logit(logits_body["contradiction"]),
                neutral=_numeric_logit(logits_body["neutral"]),
            )
        except (TypeError, ValueError) as error:
            raise ScientificInferenceProtocolError(
                "response logits must be finite numbers"
            ) from error
        return InferenceResponse(
            attempt_id=request.attempt_id,
            model_revision=self._model_revision,
            pair_token_count=pair_token_count,
            logits=logits,
        )


def _numeric_logit(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("logit must be numeric")
    return float(value)
