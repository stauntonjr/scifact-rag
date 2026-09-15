from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Protocol

from .scientific_inference import (
    DEBERTA_MODEL,
    DEBERTA_REVISION,
    InferenceLogits,
    InferenceRequest,
)

_REQUEST_SCHEMA = "scientific-inference-request/v1"
_RESPONSE_SCHEMA = "scientific-inference-response/v1"
_REQUEST_KEYS = {
    "schema_version",
    "attempt_id",
    "premise",
    "hypothesis",
    "expected_pair_tokens",
}
_MAXIMUM_REQUEST_BYTES = 1024 * 1024


class ClassificationBackend(Protocol):
    @property
    def model_revision(self) -> str: ...

    @property
    def id2label(self) -> Mapping[int, str]: ...

    def classify_pair(self, premise: str, hypothesis: str) -> tuple[Sequence[float], int]: ...


def classify_payload(
    payload: object,
    backend: ClassificationBackend,
    *,
    maximum_pair_tokens: int,
    expected_revision: str = DEBERTA_REVISION,
) -> dict[str, object]:
    if maximum_pair_tokens < 1:
        raise ValueError("maximum pair tokens must be positive")
    if backend.model_revision != expected_revision:
        raise ValueError("configured model revision does not match the immutable revision")
    label_index = _canonical_label_index(backend.id2label)
    request = _parse_request(payload)
    raw_logits, pair_token_count = backend.classify_pair(request.premise, request.hypothesis)
    if isinstance(pair_token_count, bool) or not isinstance(pair_token_count, int):
        raise TypeError("backend pair token count must be an integer")
    if pair_token_count > maximum_pair_tokens:
        raise ValueError("premise and hypothesis exceed the model token limit")
    if pair_token_count != request.expected_pair_tokens:
        raise ValueError("computed pair token count differs from the expected count")
    if len(raw_logits) != 3:
        raise ValueError("backend must return exactly three logits")
    try:
        logits = InferenceLogits(
            entailment=float(raw_logits[label_index["entailment"]]),
            contradiction=float(raw_logits[label_index["contradiction"]]),
            neutral=float(raw_logits[label_index["neutral"]]),
        )
    except (IndexError, TypeError, ValueError) as error:
        raise ValueError("backend logits must be three finite numbers") from error
    return {
        "schema_version": _RESPONSE_SCHEMA,
        "attempt_id": request.attempt_id,
        "model_revision": backend.model_revision,
        "pair_token_count": pair_token_count,
        "logits": {
            "entailment": logits.entailment,
            "contradiction": logits.contradiction,
            "neutral": logits.neutral,
        },
    }


class TransformersClassificationBackend:
    """Lazy production backend; importing this module never loads a model."""

    def __init__(self, model_name: str, model_revision: str) -> None:
        if model_name != DEBERTA_MODEL or model_revision != DEBERTA_REVISION:
            raise ValueError("service requires the pinned DeBERTa model and revision")
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self._model_revision = model_revision
        self._tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            revision=model_revision,
            use_fast=True,
        )
        self._model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            revision=model_revision,
        ).to("cuda")
        self._model.eval()
        self._id2label = {
            int(index): str(label).lower() for index, label in self._model.config.id2label.items()
        }
        _canonical_label_index(self._id2label)

    @property
    def model_revision(self) -> str:
        return self._model_revision

    @property
    def id2label(self) -> Mapping[int, str]:
        return self._id2label

    def classify_pair(self, premise: str, hypothesis: str) -> tuple[Sequence[float], int]:
        encoded = self._tokenizer(
            premise,
            hypothesis,
            add_special_tokens=True,
            truncation=False,
            return_tensors="pt",
        )
        pair_token_count = int(encoded["input_ids"].shape[-1])
        encoded = {name: value.to("cuda") for name, value in encoded.items()}
        with self._torch.inference_mode():
            raw_logits = self._model(**encoded).logits[0].detach().float().cpu().tolist()
        return raw_logits, pair_token_count


def _parse_request(payload: object) -> InferenceRequest:
    if not isinstance(payload, Mapping) or set(payload) != _REQUEST_KEYS:
        raise ValueError("request fields do not match the schema")
    if payload["schema_version"] != _REQUEST_SCHEMA:
        raise ValueError("request schema version is unsupported")
    attempt_id = payload["attempt_id"]
    premise = payload["premise"]
    hypothesis = payload["hypothesis"]
    pair_tokens = payload["expected_pair_tokens"]
    if (
        not isinstance(attempt_id, str)
        or not isinstance(premise, str)
        or not isinstance(hypothesis, str)
    ):
        raise TypeError("request identifiers and text fields must be strings")
    if isinstance(pair_tokens, bool) or not isinstance(pair_tokens, int):
        raise TypeError("expected pair tokens must be an integer")
    return InferenceRequest(attempt_id, premise, hypothesis, pair_tokens)


def _canonical_label_index(id2label: Mapping[int, str]) -> dict[str, int]:
    normalized = {int(index): str(label).lower() for index, label in id2label.items()}
    if set(normalized) != {0, 1, 2} or set(normalized.values()) != {
        "entailment",
        "contradiction",
        "neutral",
    }:
        raise ValueError("checkpoint label map must contain the exact three canonical labels")
    return {label: index for index, label in normalized.items()}


def _handler(
    backend: ClassificationBackend,
    maximum_pair_tokens: int,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/health":
                self._write(404, {"error": "not_found"})
                return
            self._write(
                200,
                {
                    "status": "ready",
                    "model": DEBERTA_MODEL,
                    "model_revision": backend.model_revision,
                    "maximum_pair_tokens": maximum_pair_tokens,
                },
            )

        def do_POST(self) -> None:
            if self.path != "/v1/classify":
                self._write(404, {"error": "not_found"})
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length < 1 or content_length > _MAXIMUM_REQUEST_BYTES:
                    self._write(413, {"error": "invalid_request_size"})
                    return
                payload = json.loads(self.rfile.read(content_length))
                response = classify_payload(
                    payload,
                    backend,
                    maximum_pair_tokens=maximum_pair_tokens,
                )
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
                self._write(400, {"error": type(error).__name__, "message": str(error)})
                return
            self._write(200, response)

        def log_message(self, format: str, *args: object) -> None:
            print(f"scientific-inference {self.command} {self.path}", flush=True)

        def _write(self, status: int, payload: Mapping[str, object]) -> None:
            body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main() -> None:
    model_name = os.environ.get("SCIENTIFIC_INFERENCE_MODEL", DEBERTA_MODEL)
    model_revision = os.environ.get("SCIENTIFIC_INFERENCE_REVISION", DEBERTA_REVISION)
    maximum_pair_tokens = int(os.environ.get("SCIENTIFIC_INFERENCE_MAX_TOKENS", "512"))
    backend = TransformersClassificationBackend(model_name, model_revision)
    server = HTTPServer(("0.0.0.0", 80), _handler(backend, maximum_pair_tokens))
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
