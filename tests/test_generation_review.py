from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]
TOOL = ROOT / "tools" / "generation_review.py"


def _tool_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generation_review", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _review_values(value: str | None = None) -> dict[str, str | None]:
    return {
        "comparison_omission": "not_applicable" if value else None,
        "grounded": "yes" if value else None,
        "intervention_omission": "not_applicable" if value else None,
        "material_overstatement": "none" if value else None,
        "negation_omission": "no" if value else None,
        "notes": "" if value else None,
        "outcome_omission": "not_applicable" if value else None,
        "population_omission": "not_applicable" if value else None,
        "qualifier_omission": "no" if value else None,
    }


def _worksheet(*, complete: bool = False) -> dict[str, object]:
    return {
        "completed_at": "2026-09-16T14:30:00Z" if complete else None,
        "reviewer": "Jack Rory Staunton" if complete else None,
        "rows": [
            {
                "answer": "The evidence supports the claim [12].",
                "claim": "Treatment A improves outcome B.",
                "evidence": [
                    {
                        "document_id": "12",
                        "text": "Treatment A improved outcome B in adults.",
                        "title": "A controlled study",
                    }
                ],
                "response_id": "0123456789abcdef0123456789abcdef",
                "review": _review_values("complete" if complete else None),
            },
            {
                "answer": "The evidence is insufficient.",
                "claim": "Exposure C causes outcome D.",
                "evidence": [
                    {
                        "document_id": "34",
                        "text": "Exposure C was associated with outcome D.",
                        "title": "An observational study",
                    }
                ],
                "response_id": "fedcba9876543210fedcba9876543210",
                "review": _review_values("complete" if complete else None),
            },
        ],
        "schema_version": "generation-human-review/v1",
        "selection_protocol": "docs/project/generation-human-review-v1.md",
    }


def _v2_review_values(*, complete: bool, material_error: bool = False) -> dict[str, object]:
    values: dict[str, object] = {
        **_review_values("complete" if complete else None),
        "causal_strengthening": (
            "yes" if complete and material_error else ("no" if complete else None)
        ),
        "population_generalization": "no" if complete else None,
        "material_errors": [],
    }
    if complete and material_error:
        values["grounded"] = "no"
        values["material_overstatement"] = "present"
        values["material_errors"] = [
            {
                "category": "causal_strengthening",
                "answer_span": {"start": 0, "end": 3},
                "evidence_spans": [{"evidence_index": 0, "start": 0, "end": 3}],
                "evidence_absent": False,
            }
        ]
    return values


def _v2_worksheet(*, complete: bool = False, material_error: bool = False) -> dict[str, object]:
    data = _worksheet(complete=complete)
    data["schema_version"] = "generation-human-review/v2"
    data["selection_protocol"] = "docs/project/generation-fidelity-v1.md"
    rows = data["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        row["review"] = _v2_review_values(
            complete=complete,
            material_error=material_error,
        )
    return data


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _write_json(path: Path, value: object) -> str:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_build_creates_offline_blinded_reviewer_without_mutating_source(tmp_path: Path) -> None:
    module = _tool_module()
    worksheet = tmp_path / "worksheet.json"
    output = tmp_path / "review.html"
    digest = _write_json(worksheet, _worksheet())
    original = worksheet.read_bytes()

    result = module.build_reviewer(
        worksheet,
        output,
        expected_sha256=digest,
        expected_rows=2,
    )

    assert result["rows"] == 2
    assert worksheet.read_bytes() == original
    rendered = output.read_text(encoding="utf-8")
    assert "Treatment A improves outcome B." in rendered
    assert "fedcba9876543210fedcba9876543210" in rendered
    assert "localStorage" in rendered
    assert "Export completed review" in rendered
    assert "default-src 'none'" in rendered
    assert "https://" not in rendered
    assert "http://" not in rendered
    assert "context_strategy" not in rendered
    assert "equivalent_policies" not in rendered


def test_build_rejects_unblinded_or_unexpected_fields(tmp_path: Path) -> None:
    module = _tool_module()
    data = _worksheet()
    rows = data["rows"]
    assert isinstance(rows, list)
    rows[0]["context_strategy"] = "whole-document"
    worksheet = tmp_path / "worksheet.json"
    output = tmp_path / "review.html"
    digest = _write_json(worksheet, data)

    with pytest.raises(module.ReviewValidationError, match="unexpected fields"):
        module.build_reviewer(
            worksheet,
            output,
            expected_sha256=digest,
            expected_rows=2,
        )
    assert not output.exists()


def test_validate_accepts_only_complete_human_review(tmp_path: Path) -> None:
    module = _tool_module()
    source = tmp_path / "source.json"
    completed = tmp_path / "completed.json"
    source_digest = _write_json(source, _worksheet())
    completed.write_text(json.dumps(_worksheet(complete=True)), encoding="utf-8")

    result = module.validate_completed(
        completed,
        source,
        expected_sha256=source_digest,
        expected_rows=2,
    )

    assert result == {
        "completed_at": "2026-09-16T14:30:00Z",
        "reviewer": "Jack Rory Staunton",
        "rows": 2,
        "status": "complete",
    }


def test_validate_rejects_incomplete_review(tmp_path: Path) -> None:
    module = _tool_module()
    source = tmp_path / "source.json"
    incomplete = tmp_path / "incomplete.json"
    source_digest = _write_json(source, _worksheet())
    incomplete.write_text(json.dumps(_worksheet()), encoding="utf-8")

    with pytest.raises(module.ReviewValidationError) as error:
        module.validate_completed(
            incomplete,
            source,
            expected_sha256=source_digest,
            expected_rows=2,
        )

    assert "reviewer is required" in str(error.value)
    assert "completed_at is required" in str(error.value)
    assert "review fields are incomplete" in str(error.value)


def test_validate_rejects_completed_review_with_changed_source_content(tmp_path: Path) -> None:
    module = _tool_module()
    source = tmp_path / "source.json"
    completed = tmp_path / "completed.json"
    source_digest = _write_json(source, _worksheet())
    changed = _worksheet(complete=True)
    rows = changed["rows"]
    assert isinstance(rows, list)
    rows[0]["claim"] = "A changed claim."
    completed.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(
        module.ReviewValidationError,
        match="non-review content differs from the frozen source",
    ):
        module.validate_completed(
            completed,
            source,
            expected_sha256=source_digest,
            expected_rows=2,
        )


def test_build_rejects_wrong_frozen_source_digest(tmp_path: Path) -> None:
    module = _tool_module()
    worksheet = tmp_path / "worksheet.json"
    output = tmp_path / "review.html"
    _write_json(worksheet, _worksheet())

    with pytest.raises(module.ReviewValidationError, match="worksheet SHA-256 mismatch"):
        module.build_reviewer(
            worksheet,
            output,
            expected_sha256="0" * 64,
            expected_rows=2,
        )
    assert not output.exists()


def test_public_cli_cannot_override_frozen_digest_or_row_count(tmp_path: Path) -> None:
    worksheet = tmp_path / "worksheet.json"
    output = tmp_path / "review.html"
    digest = _write_json(worksheet, _worksheet())

    result = _run(
        "build",
        "--worksheet",
        str(worksheet),
        "--output",
        str(output),
        "--expected-sha256",
        digest,
    )

    assert result.returncode == 2
    assert "unrecognized arguments: --expected-sha256" in result.stderr


def test_builder_requires_exact_frozen_row_count(tmp_path: Path) -> None:
    module = _tool_module()
    worksheet = tmp_path / "worksheet.json"
    output = tmp_path / "review.html"
    digest = _write_json(worksheet, _worksheet())

    with pytest.raises(module.ReviewValidationError, match="exactly 42 rows"):
        module.build_reviewer(worksheet, output, expected_sha256=digest)


def test_validator_reports_the_32_character_response_id_contract() -> None:
    module = _tool_module()
    data = _worksheet()
    rows = data["rows"]
    assert isinstance(rows, list)
    rows[0]["response_id"] = "too-short"

    with pytest.raises(
        module.ReviewValidationError,
        match=r"response_id must be 32 lowercase hexadecimal characters",
    ):
        module.validate_worksheet(data, require_complete=False)


def test_v2_accepts_blank_and_bounded_material_error_annotations() -> None:
    module = _tool_module()

    blank = module.validate_worksheet(_v2_worksheet(), require_complete=False)
    completed = module.validate_worksheet(
        _v2_worksheet(complete=True, material_error=True),
        require_complete=True,
    )

    assert blank["schema_version"] == "generation-human-review/v2"
    assert completed["schema_version"] == "generation-human-review/v2"


def test_v2_rejects_material_nonpass_without_annotation() -> None:
    module = _tool_module()
    data = _v2_worksheet(complete=True)
    rows = data["rows"]
    assert isinstance(rows, list) and isinstance(rows[0], dict)
    review = rows[0]["review"]
    assert isinstance(review, dict)
    review["grounded"] = "no"

    with pytest.raises(module.ReviewValidationError, match="requires a material error annotation"):
        module.validate_worksheet(data, require_complete=True)


def test_v2_rejects_annotation_on_a_clean_pass() -> None:
    module = _tool_module()
    data = _v2_worksheet(complete=True, material_error=True)
    rows = data["rows"]
    assert isinstance(rows, list) and isinstance(rows[0], dict)
    review = rows[0]["review"]
    assert isinstance(review, dict)
    review.update(
        {
            "causal_strengthening": "no",
            "grounded": "yes",
            "material_overstatement": "none",
        }
    )

    with pytest.raises(module.ReviewValidationError, match="clean pass must not contain"):
        module.validate_worksheet(data, require_complete=True)


@pytest.mark.parametrize(
    ("review_updates", "annotation_category", "missing_category"),
    [
        (
            {},
            "qualifier_loss",
            "causal_strengthening",
        ),
        (
            {"qualifier_omission": "yes"},
            "causal_strengthening",
            "qualifier_loss",
        ),
        (
            {
                "causal_strengthening": "no",
                "material_overstatement": "none",
            },
            "qualifier_loss",
            "unsupported_claim",
        ),
    ],
)
def test_v2_requires_annotations_matching_each_definite_material_error(
    review_updates: dict[str, str],
    annotation_category: str,
    missing_category: str,
) -> None:
    module = _tool_module()
    data = _v2_worksheet(complete=True, material_error=True)
    rows = data["rows"]
    assert isinstance(rows, list) and isinstance(rows[0], dict)
    review = rows[0]["review"]
    assert isinstance(review, dict)
    review.update(review_updates)
    material_errors = review["material_errors"]
    assert isinstance(material_errors, list) and isinstance(material_errors[0], dict)
    material_errors[0]["category"] = annotation_category

    with pytest.raises(
        module.ReviewValidationError,
        match=rf"missing matching material error categories: .*{missing_category}",
    ):
        module.validate_worksheet(data, require_complete=True)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("causal_strengthening", None, "review fields are incomplete"),
        ("population_generalization", "invented", "review fields are incomplete"),
    ],
)
def test_v2_requires_complete_new_categorical_fields(
    field: str,
    value: object,
    message: str,
) -> None:
    module = _tool_module()
    data = _v2_worksheet(complete=True)
    rows = data["rows"]
    assert isinstance(rows, list) and isinstance(rows[0], dict)
    review = rows[0]["review"]
    assert isinstance(review, dict)
    review[field] = value

    with pytest.raises(module.ReviewValidationError, match=message):
        module.validate_worksheet(data, require_complete=True)


def test_v2_rejects_unblinding_fields() -> None:
    module = _tool_module()
    for location in ("top", "row", "review"):
        data = _v2_worksheet()
        rows = data["rows"]
        assert isinstance(rows, list) and isinstance(rows[0], dict)
        review = rows[0]["review"]
        assert isinstance(review, dict)
        if location == "top":
            data["candidate_id"] = "candidate-v1"
        elif location == "row":
            rows[0]["candidate_id"] = "candidate-v1"
        else:
            review["candidate_id"] = "candidate-v1"
        with pytest.raises(module.ReviewValidationError, match="unexpected fields"):
            module.validate_worksheet(data, require_complete=False)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("answer-out-of-bounds", "answer_span"),
        ("evidence-index", "evidence_index"),
        ("evidence-out-of-bounds", r"evidence_spans\[0\]"),
        ("both-evidence-modes", "exactly one"),
        ("neither-evidence-mode", "exactly one"),
        ("duplicate", "duplicate material error"),
    ],
)
def test_v2_rejects_invalid_material_error_spans(mutation: str, message: str) -> None:
    module = _tool_module()
    data = _v2_worksheet(complete=True, material_error=True)
    rows = data["rows"]
    assert isinstance(rows, list) and isinstance(rows[0], dict)
    review = rows[0]["review"]
    assert isinstance(review, dict)
    material_errors = review["material_errors"]
    assert isinstance(material_errors, list) and isinstance(material_errors[0], dict)
    error = material_errors[0]
    evidence_spans = error["evidence_spans"]
    assert isinstance(evidence_spans, list) and isinstance(evidence_spans[0], dict)
    if mutation == "answer-out-of-bounds":
        error["answer_span"] = {"start": 0, "end": 999}
    elif mutation == "evidence-index":
        evidence_spans[0]["evidence_index"] = 99
    elif mutation == "evidence-out-of-bounds":
        evidence_spans[0]["end"] = 999
    elif mutation == "both-evidence-modes":
        error["evidence_absent"] = True
    elif mutation == "neither-evidence-mode":
        error["evidence_spans"] = []
    else:
        material_errors.append(dict(error))

    with pytest.raises(module.ReviewValidationError, match=message):
        module.validate_worksheet(data, require_complete=True)


def test_v2_accepts_explicit_evidence_absence() -> None:
    module = _tool_module()
    data = _v2_worksheet(complete=True, material_error=True)
    rows = data["rows"]
    assert isinstance(rows, list) and isinstance(rows[0], dict)
    review = rows[0]["review"]
    assert isinstance(review, dict)
    material_errors = review["material_errors"]
    assert isinstance(material_errors, list) and isinstance(material_errors[0], dict)
    material_errors[0]["evidence_spans"] = []
    material_errors[0]["evidence_absent"] = True

    validated = module.validate_worksheet(data, require_complete=True)

    assert validated["schema_version"] == "generation-human-review/v2"


def test_review_validator_rejects_unknown_schema_version() -> None:
    module = _tool_module()
    data = _v2_worksheet()
    data["schema_version"] = "generation-human-review/v3"

    with pytest.raises(module.ReviewValidationError, match="schema_version"):
        module.validate_worksheet(data, require_complete=False)


def test_v2_builder_renders_blinded_structured_fidelity_controls(tmp_path: Path) -> None:
    module = _tool_module()
    worksheet = tmp_path / "worksheet-v2.json"
    output = tmp_path / "review-v2.html"
    digest = _write_json(worksheet, _v2_worksheet())

    result = module.build_reviewer(
        worksheet,
        output,
        expected_sha256=digest,
        expected_rows=2,
    )

    rendered = output.read_text(encoding="utf-8")
    assert result["schema_version"] == "generation-human-review/v2"
    assert "Causal strengthening" in rendered
    assert "Population generalization" in rendered
    assert "Material error spans" in rendered
    assert "Answer span start" in rendered
    assert "Evidence absent" in rendered
    assert "default-src 'none'" in rendered
    assert "candidate_id" not in rendered
    assert "context_strategy" not in rendered
    assert "validateMaterialErrors(row, review, materialErrorConfig).length === 0" in rendered


def test_v2_browser_validator_rejects_invalid_material_error_states() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable for the executable offline-reviewer check")
    module = _tool_module()
    data = _v2_worksheet(complete=True, material_error=True)
    rows = data["rows"]
    assert isinstance(rows, list) and isinstance(rows[0], dict)
    valid = json.loads(json.dumps(rows[0]))
    invalid: list[dict[str, object]] = []

    no_annotation = json.loads(json.dumps(valid))
    no_annotation["review"]["material_errors"] = []
    invalid.append(no_annotation)

    mismatched = json.loads(json.dumps(valid))
    mismatched["review"]["material_errors"][0]["category"] = "qualifier_loss"
    invalid.append(mismatched)

    bad_answer_span = json.loads(json.dumps(valid))
    bad_answer_span["review"]["material_errors"][0]["answer_span"]["end"] = 999
    invalid.append(bad_answer_span)

    both_evidence_modes = json.loads(json.dumps(valid))
    both_evidence_modes["review"]["material_errors"][0]["evidence_absent"] = True
    invalid.append(both_evidence_modes)

    neither_evidence_mode = json.loads(json.dumps(valid))
    neither_evidence_mode["review"]["material_errors"][0]["evidence_spans"] = []
    invalid.append(neither_evidence_mode)

    bad_evidence_index = json.loads(json.dumps(valid))
    bad_evidence_index["review"]["material_errors"][0]["evidence_spans"][0]["evidence_index"] = 99
    invalid.append(bad_evidence_index)

    bad_evidence_span = json.loads(json.dumps(valid))
    bad_evidence_span["review"]["material_errors"][0]["evidence_spans"][0]["end"] = 999
    invalid.append(bad_evidence_span)

    duplicate = json.loads(json.dumps(valid))
    duplicate["review"]["material_errors"].append(
        json.loads(json.dumps(duplicate["review"]["material_errors"][0]))
    )
    invalid.append(duplicate)

    config = module._reviewer_config(module.SCHEMA_VERSION_V2)["material_error"]
    script = (
        module.BROWSER_VALIDATION_JAVASCRIPT
        + "\nconst rows = "
        + json.dumps([valid, *invalid])
        + ";\nconst config = "
        + json.dumps(config)
        + ";\nprocess.stdout.write(JSON.stringify(rows.map(row => "
        + "validateMaterialErrors(row, row.review, config))));\n"
    )

    result = subprocess.run(
        [node, "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    outcomes = json.loads(result.stdout)

    assert outcomes[0] == []
    assert all(outcome for outcome in outcomes[1:])


def test_v1_builder_does_not_render_v2_fidelity_controls(tmp_path: Path) -> None:
    module = _tool_module()
    worksheet = tmp_path / "worksheet-v1.json"
    output = tmp_path / "review-v1.html"
    digest = _write_json(worksheet, _worksheet())

    result = module.build_reviewer(
        worksheet,
        output,
        expected_sha256=digest,
        expected_rows=2,
    )

    rendered = output.read_text(encoding="utf-8")
    assert result["schema_version"] == "generation-human-review/v1"
    assert "Causal strengthening" not in rendered
    assert "Population generalization" not in rendered
    assert "Material error spans" not in rendered
    assert "function validateMaterialErrors" not in rendered


@pytest.mark.parametrize("schema_version", ["v1", "v2"])
@pytest.mark.parametrize("retained_path", ["output", "staging"])
def test_builder_refuses_to_overwrite_retained_paths(
    tmp_path: Path,
    schema_version: str,
    retained_path: str,
) -> None:
    module = _tool_module()
    worksheet = tmp_path / f"worksheet-{schema_version}.json"
    output = tmp_path / f"review-{schema_version}.html"
    staged = output.with_name(f".{output.name}.tmp")
    digest = _write_json(
        worksheet,
        _v2_worksheet() if schema_version == "v2" else _worksheet(),
    )
    retained = output if retained_path == "output" else staged
    retained.write_text("RETAINED-SENTINEL", encoding="utf-8")

    with pytest.raises(module.ReviewValidationError, match="already exists"):
        module.build_reviewer(
            worksheet,
            output,
            expected_sha256=digest,
            expected_rows=2,
        )

    assert retained.read_text(encoding="utf-8") == "RETAINED-SENTINEL"
    if retained_path == "staging":
        assert not output.exists()
