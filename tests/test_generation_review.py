from __future__ import annotations

import hashlib
import importlib.util
import json
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
