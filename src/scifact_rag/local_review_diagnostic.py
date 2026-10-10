"""Bounded, source-validated local reviewer diagnostic.

This module deliberately does not start, stop, or configure model services.  A caller
must capture service state before dispatch and explicitly opt in to an HTTP transport.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from . import generation_review_workflow as workflow

CASE_COUNT = 24
TIMEOUT_SECONDS = 120.0
MAX_OUTPUT_TOKENS = 8192


class DiagnosticStop(ValueError):
    """A diagnostic boundary that must prevent additional dispatch."""


class UnknownDispatch(RuntimeError):
    """The request may have reached a server, so it must remain unclassified."""


class RuntimeIdentityMismatch(DiagnosticStop):
    """The endpoint returned a different runtime identity; stop that arm."""


@dataclass(frozen=True)
class LocalTransportResult:
    raw_output: str
    model: str | None
    request_id: str | None
    status_code: int | None
    usage: dict[str, int | None] | None = None
    error_class: str | None = None


class LocalTransport(Protocol):
    kind: str
    model_id: str

    def dispatch(self, payload: dict[str, Any], timeout_seconds: float) -> LocalTransportResult: ...


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha(value: object) -> str:
    return workflow.canonical_json_sha256(value)


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def _error_case(
    number: int,
    target: str,
    claim: str,
    evidence: str,
    error_answer: str,
    faithful_answer: str,
    category: str,
) -> list[dict[str, Any]]:
    common = {
        "claim": claim,
        "evidence": [
            {"document_id": f"D{number:02d}", "title": "Synthetic study", "text": evidence}
        ],
    }
    return [
        _case(number, target, "error", error_answer, category=category, **common),
        _case(number + 1, target, "faithful", faithful_answer, **common),
    ]


def _case(
    number: int,
    target: str,
    variant: str,
    answer: str,
    claim: str,
    evidence: list[dict[str, str]],
    category: str | None = None,
    boundary: str | None = None,
) -> dict[str, Any]:
    expected = _expected(
        target=target, category=category, answer=answer, evidence=evidence, boundary=boundary
    )
    return {
        "case": {
            "response_id": f"{number:032x}",
            "claim": claim,
            "answer": answer,
            "evidence": evidence,
        },
        "reference": {
            "target": target,
            "variant": variant,
            "expected": expected,
            "explanation": _explanation(target, variant, boundary),
        },
    }


def _expected(
    *,
    target: str,
    category: str | None,
    answer: str,
    evidence: list[dict[str, str]],
    boundary: str | None,
) -> dict[str, Any]:
    review = {field: "no" for field in workflow.TRISTATE_FIELDS}
    review.update({"grounded": "yes", "material_overstatement": "none"})
    adequacy = {
        "supplied_context_answerability": "answerable",
        "answer_adequacy": "adequate",
        "insufficiency_handling": "not_applicable",
    }
    if category:
        field = {
            "qualifier_loss": "qualifier_omission",
            "population_generalization": "population_generalization",
            "intervention_change": "intervention_omission",
            "comparison_change": "comparison_omission",
            "outcome_change": "outcome_omission",
            "negation_loss": "negation_omission",
            "causal_strengthening": "causal_strengthening",
        }[category]
        review[field] = "yes"
        if target in workflow.TRISTATE_FIELDS:
            review[target] = "yes"
        review["grounded"] = "no"
        review["material_overstatement"] = "present"
        adequacy["answer_adequacy"] = "inadequate"
    if boundary == "appropriate_refusal":
        review.update({field: "not_applicable" for field in workflow.TRISTATE_FIELDS})
        adequacy = {
            "supplied_context_answerability": "not_answerable",
            "answer_adequacy": "not_applicable",
            "insufficiency_handling": "appropriate",
        }
    elif boundary == "unnecessary_refusal":
        adequacy.update(
            {"answer_adequacy": "inadequate", "insufficiency_handling": "inappropriate"}
        )
    elif boundary == "mixed_answerable":
        review["grounded"] = "yes"
        review["material_overstatement"] = "none"
        adequacy = {
            "supplied_context_answerability": "answerable",
            "answer_adequacy": "adequate",
            "insufficiency_handling": "appropriate",
        }
    elif boundary == "overlap":
        review["population_omission"] = "yes"
        review["population_generalization"] = "yes"
        review["causal_strengthening"] = "yes"
        review["grounded"] = "no"
        review["material_overstatement"] = "present"
        adequacy["answer_adequacy"] = "inadequate"
    return {"review_v2": review, "adequacy": adequacy}


def _explanation(target: str, variant: str, boundary: str | None) -> str:
    if boundary:
        return f"Boundary case: {boundary}."
    return f"The {variant} contrast tests {target} against the supplied evidence only."


def example_fixture() -> dict[str, Any]:
    """Deterministic 24-case fixture; expected labels never enter model payloads."""
    cases: list[dict[str, Any]] = []
    pairs = [
        (
            "qualifier_omission",
            "A four-week study found that Drug Arbor may reduce symptom score; later persistence was not evaluated.",
            "Does Drug Arbor provide durable symptom benefit?",
            "Drug Arbor provides durable symptom benefit.",
            "Drug Arbor may reduce symptom score at four weeks; later persistence was not evaluated.",
            "qualifier_loss",
        ),
        (
            "population_omission",
            "Among adults with severe asthma, Therapy Birch reduced exacerbations.",
            "Who benefited from Therapy Birch?",
            "Therapy Birch reduces exacerbations in patients.",
            "Among adults with severe asthma, Therapy Birch reduced exacerbations.",
            "population_generalization",
        ),
        (
            "population_generalization",
            "In cultured mouse cells, Compound Cedar reduced viral replication. No animal or human outcomes were studied.",
            "What did Compound Cedar do?",
            "Compound Cedar works in humans.",
            "In cultured mouse cells, Compound Cedar reduced viral replication.",
            "population_generalization",
        ),
        (
            "intervention_omission",
            "The combination of Drug Delta and exercise improved walking distance; neither component was tested alone.",
            "What improved walking distance?",
            "Drug Delta alone improved walking distance.",
            "The combination of Drug Delta and exercise improved walking distance.",
            "intervention_change",
        ),
        (
            "comparison_omission",
            "Drug Elm reduced pain more than placebo. Standard treatment was not studied.",
            "How did Drug Elm compare?",
            "Drug Elm is superior to standard treatment.",
            "Drug Elm reduced pain more than placebo.",
            "comparison_change",
        ),
        (
            "outcome_omission",
            "Treatment Fir reduced biomarker B. Survival and symptoms were not assessed.",
            "What outcome changed with Treatment Fir?",
            "Treatment Fir improves survival.",
            "Treatment Fir reduced biomarker B; survival was not assessed.",
            "outcome_change",
        ),
        (
            "negation_omission",
            "Exposure Grove did not increase hospitalization during the study period.",
            "Did Exposure Grove increase hospitalization?",
            "Exposure Grove increased hospitalization.",
            "Exposure Grove did not increase hospitalization during the study period.",
            "negation_loss",
        ),
        (
            "causal_strengthening",
            "In an observational cohort, Exposure Harbor was associated with lower risk. The study did not establish causation.",
            "What was observed for Exposure Harbor?",
            "Exposure Harbor causes lower risk.",
            "Exposure Harbor was associated with lower risk.",
            "causal_strengthening",
        ),
    ]
    for index, (target, evidence, claim, error, faithful, category) in enumerate(pairs):
        cases.extend(_error_case(index * 2 + 1, target, claim, evidence, error, faithful, category))
    boundaries = [
        (
            "comparison_omission",
            "The claim asks whether Drug Ibis beat placebo. The study reports Drug Ibis reduced pain more than placebo.",
            "Did Drug Ibis beat placebo?",
            "Drug Ibis reduced pain.",
            None,
            "comparator_in_claim",
        ),
        (
            "qualifier_omission",
            "The difference was not statistically significant; equivalence was not tested.",
            "Are the treatments equivalent?",
            "The treatments are equivalent.",
            "qualifier_loss",
            "non_significance",
        ),
        (
            "comparison_omission",
            "One supplied study found A better than placebo; another equally applicable study found no difference. Neither explains the conflict.",
            "Does A outperform placebo?",
            "The evidence is mixed and does not resolve whether A outperforms placebo.",
            None,
            "mixed_answerable",
        ),
        (
            "answerability",
            "The supplied passage describes laboratory storage methods and contains no result about the claim.",
            "Does Device Juniper reduce mortality?",
            "Insufficient evidence.",
            None,
            "appropriate_refusal",
        ),
        (
            "adequacy",
            "A randomized trial found Drug Kite reduced symptom score at four weeks.",
            "Did Drug Kite reduce symptom score at four weeks?",
            "Insufficient evidence.",
            None,
            "unnecessary_refusal",
        ),
        (
            "adequacy",
            "Among adults with condition L, Treatment Larch may improve a laboratory marker; clinical benefit was not assessed.",
            "What can be concluded about Treatment Larch?",
            "Among adults with condition L, Treatment Larch may improve a laboratory marker; clinical benefit was not assessed.",
            None,
            "narrow_adequate",
        ),
        (
            "overlap",
            "In cultured rat cells, Exposure Maple was associated with lower biomarker B; causation and human outcomes were not studied.",
            "What does Exposure Maple do in humans?",
            "Exposure Maple prevents disease in humans.",
            None,
            "overlap",
        ),
        (
            "contradiction",
            "A randomized trial found Drug North did not improve survival compared with placebo.",
            "Does Drug North improve survival?",
            "Drug North did not improve survival compared with placebo.",
            None,
            "supported_contradiction",
        ),
    ]
    for offset, (target, evidence, claim, answer, category, boundary) in enumerate(
        boundaries, start=17
    ):
        cases.append(
            _case(
                offset,
                target,
                "boundary",
                answer,
                claim,
                [
                    {
                        "document_id": f"D{offset:02d}",
                        "title": "Synthetic boundary study",
                        "text": evidence,
                    }
                ],
                category=category,
                boundary=boundary,
            )
        )
    return {"schema_version": "local-review-diagnostic/v1", "cases": cases}


def load_fixture(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if value.get("schema_version") != "local-review-diagnostic/v1":
        raise DiagnosticStop("fixture_schema")
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != CASE_COUNT:
        raise DiagnosticStop("fixture_case_count")
    ids = [item.get("case", {}).get("response_id") for item in cases]
    if len(set(ids)) != CASE_COUNT or any(not isinstance(key, str) for key in ids):
        raise DiagnosticStop("fixture_identity")
    targets = {item.get("reference", {}).get("target") for item in cases}
    required = set(workflow.TRISTATE_FIELDS)
    if not required.issubset(targets):
        raise DiagnosticStop("fixture_granular_coverage")
    fixture = dict(value)
    fixture["rubric_sha256"] = _sha("local-review-rubric-v3")
    fixture["fixture_sha256"] = _sha(value)
    return fixture


def expected_for_case(response_id: str) -> dict[str, Any]:
    """Return coordinator-only synthetic reference data for offline test transports."""
    for item in example_fixture()["cases"]:
        if item["case"]["response_id"] == response_id:
            return item["reference"]["expected"]
    raise DiagnosticStop("unknown_fixture_case")


def model_payload(item: dict[str, Any], rubric: str) -> dict[str, Any]:
    """Return only the source case, rubric and schema; never reference labels or pair identity."""
    return {"case": item["case"], "rubric": rubric, "schema": judgment_schema(final=False)}


def judgment_schema(*, final: bool = False) -> dict[str, Any]:
    return workflow.judgment_schema(final=final)


def judgment_from_expected(source: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """Test helper yielding a source-valid judgment with the supplied expected classifications."""
    review = dict(expected["review_v2"])
    categories = []
    mappings = {
        "causal_strengthening": "causal_strengthening",
        "comparison_omission": "comparison_change",
        "intervention_omission": "intervention_change",
        "negation_omission": "negation_loss",
        "outcome_omission": "outcome_change",
        "population_generalization": "population_generalization",
        "population_omission": "population_generalization",
        "qualifier_omission": "qualifier_loss",
    }
    for field, category in mappings.items():
        if review[field] == "yes" and category not in categories:
            categories.append(category)
    annotations = [
        {
            "answer_span": {"start": 0, "end": len(source["answer"])},
            "category": category,
            "evidence_absent": False,
            "evidence_spans": [
                {"evidence_index": 0, "start": 0, "end": len(source["evidence"][0]["text"])}
            ],
        }
        for category in categories
    ]
    return {
        "schema_version": "generation-model-judgment/v2",
        "response_id": source["response_id"],
        "review_v2": {**review, "material_errors": annotations, "notes": "Synthetic reference."},
        "adequacy": {**expected["adequacy"], "rationale": "Synthetic reference."},
        "rationale": {
            "summary": "Synthetic source-bound reference.",
            "answer_quotes": [source["answer"]],
            "evidence_quotes": [
                {
                    "document_id": source["evidence"][0]["document_id"],
                    "quote": source["evidence"][0]["text"],
                }
            ],
        },
    }


def _fresh(root: Path) -> None:
    if root.exists():
        raise DiagnosticStop("nonfresh_output_root")
    root.mkdir(parents=True)


def run(
    root: Path,
    fixture: dict[str, Any],
    transport: LocalTransport,
    preflight: dict[str, Any] | None,
    *,
    rubric: str,
) -> dict[str, Any]:
    if (
        not preflight
        or not isinstance(preflight.get("services"), list)
        or not preflight["services"]
    ):
        raise DiagnosticStop("missing_service_preflight")
    _fresh(root)
    _write(root / "fixture.json", fixture)
    _write(root / "service-baseline.json", preflight)
    attempts = root / "attempts"
    attempts.mkdir()
    stopped_unknown = False
    stopped_identity = False
    for ordinal, item in enumerate(fixture["cases"], start=1):
        source = item["case"]
        request = model_payload(item, rubric)
        provenance = {
            "ordinal": ordinal,
            "response_id": source["response_id"],
            "started_at": _now(),
            "model_id": transport.model_id,
            "input_sha256": _sha(source),
            "request_sha256": _sha(request),
            "rubric_sha256": _sha(rubric),
            "schema_sha256": _sha(request["schema"]),
            "fixture_sha256": fixture["fixture_sha256"],
            "preflight_sha256": _sha(preflight),
        }
        base = f"{ordinal:03d}"
        _write(attempts / f"{base}.start.json", provenance)
        output: LocalTransportResult | None = None
        fatal = False
        try:
            output = transport.dispatch(request, TIMEOUT_SECONDS)
            if output.status_code != 200:
                raise DiagnosticStop("local_transport_status")
            if output.model != transport.model_id:
                raise RuntimeIdentityMismatch("local_transport_identity")
            value = json.loads(output.raw_output)
            workflow.validate_judgment(value, source)
            status = "completed"
            errors: list[str] = []
            semantic = _semantic_disagreements(value, item["reference"]["expected"])
        except KeyboardInterrupt:
            raise
        except UnknownDispatch:
            stopped_unknown = True
            break
        except RuntimeIdentityMismatch as exc:
            status = "failed"
            value = None
            semantic = []
            errors = [str(exc)]
            stopped_identity = True
            fatal = True
        except Exception as exc:  # noqa: BLE001 - persist attributable non-successes
            if output is None:
                stopped_unknown = True
                break
            status = "failed"
            value = None
            semantic = []
            errors = [str(exc) if isinstance(exc, DiagnosticStop) else type(exc).__name__]
        _write(
            attempts / f"{base}.result.json",
            {
                "status": status,
                "judgment": value,
                "semantic_disagreements": semantic,
                "validation_errors": errors,
                "attempt_start_sha256": _sha(provenance),
                "completed_at": _now(),
                "transport": asdict(output) if output is not None else None,
            },
        )
        if fatal:
            break
    _write(
        root / "terminal.json",
        {
            "ended_at": _now(),
            "status": (
                "unknown_dispatch"
                if stopped_unknown
                else "runtime_identity_mismatch"
                if stopped_identity
                else "complete"
            ),
        },
    )
    result = report(root, fixture)
    _write(root / "report.json", result)
    return result


def _semantic_disagreements(value: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    differences = []
    for section in ("review_v2", "adequacy"):
        for key, expected_value in expected[section].items():
            if value[section][key] != expected_value:
                differences.append(f"{section}.{key}")
    return differences


def report(root: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    attempts = root / "attempts"
    starts = sorted(attempts.glob("*.start.json")) if attempts.exists() else []
    results = sorted(attempts.glob("*.result.json")) if attempts.exists() else []
    completed = [
        json.loads(path.read_text())
        for path in results
        if json.loads(path.read_text())["status"] == "completed"
    ]
    unknown = len(starts) - len(results)
    return {
        "execution_status": "execution_complete"
        if len(results) == CASE_COUNT
        else "execution_incomplete",
        "scheduled": CASE_COUNT,
        "attempted": len(starts),
        "completed": len(completed),
        "failed": len(results) - len(completed),
        "unknown": unknown,
        "not_attempted": CASE_COUNT - len(starts),
        "semantic_disagreements": sum(
            len(record["semantic_disagreements"]) for record in completed
        ),
        "fixture_sha256": fixture["fixture_sha256"],
    }


class OpenAIHTTPTransport:
    """Explicit opt-in vLLM-compatible transport; it never manages a server."""

    kind = "local_http"

    def __init__(self, base_url: str, model_id: str):
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id

    def dispatch(self, payload: dict[str, Any], timeout_seconds: float) -> LocalTransportResult:
        import httpx

        request = payload
        try:
            response = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.model_id,
                    "messages": [{"role": "user", "content": json.dumps(request, sort_keys=True)}],
                    "max_tokens": MAX_OUTPUT_TOKENS,
                    "temperature": 0,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {"name": "judgment", "schema": request["schema"]},
                    },
                },
                timeout=timeout_seconds,
            )
        except httpx.RequestError as exc:
            raise UnknownDispatch("local_http_request_outcome_unknown") from exc
        raw = ""
        observed_model = None
        request_id = response.headers.get("x-request-id")
        usage = None
        try:
            body = response.json()
            if response.status_code == 200:
                raw = body["choices"][0]["message"]["content"]
                observed_model = body.get("model")
                raw_usage = body.get("usage", {})
                usage = {
                    key: raw_usage.get(key)
                    for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                }
        except (KeyError, TypeError, ValueError):
            pass
        return LocalTransportResult(
            raw_output=raw,
            model=observed_model,
            request_id=request_id,
            status_code=response.status_code,
            usage=usage,
            error_class=None if response.status_code == 200 else "http_error",
        )
