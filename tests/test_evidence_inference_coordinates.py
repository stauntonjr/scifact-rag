"""Synthetic coordinate checks; never commit publisher article text."""

import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
spec = importlib.util.spec_from_file_location(
    "coordinates", Path(__file__).parents[1] / "tools/evidence_inference_coordinates.py"
)
assert spec and spec.loader
coordinates = importlib.util.module_from_spec(spec)


def setup_module():
    assert spec is not None and spec.loader is not None and spec.origin is not None
    assert Path(spec.origin).exists(), "coordinate qualification implementation missing"
    spec.loader.exec_module(coordinates)


def test_unicode_newlines_preserve_raw_character_and_utf8_boundaries():
    raw = "α\r\nβ\r🙂\n".encode()
    view = coordinates.canonical_view(raw)
    assert view["text"] == "α\nβ\n🙂\n"
    assert view["raw_character_boundaries"] == [0, 1, 3, 4, 5, 6, 7]
    assert view["raw_byte_boundaries"] == [0, 2, 4, 6, 7, 11, 12]
    for a in range(6):
        for b in range(a + 1, 7):
            result = coordinates.qualify(view, view["text"][a:b], str(a), str(b))
            assert result["status"] == "exact_mapped"
            c, d = result["raw_byte_span"]
            assert coordinates.normalize(raw[c:d].decode()) == view["text"][a:b]


@pytest.mark.parametrize(
    "start,end,status",
    [
        ("-1", "-1", "publisher_unavailable"),
        ("x", "1", "invalid_offset"),
        ("0.0", "1", "invalid_offset"),
        ("-1", "1", "out_of_bounds"),
        ("2", "1", "out_of_bounds"),
        ("0", "4", "out_of_bounds"),
        ("1", "1", "empty_span"),
    ],
)
def test_reject_invalid_spans_without_python_slice_clamping(start, end, status):
    assert (
        coordinates.qualify(coordinates.canonical_view(b"abc"), "a", start, end)["status"] == status
    )


def test_no_heuristic_acceptance_or_unique_occurrence_requirement():
    view = coordinates.canonical_view(b"a a\r\n")
    assert coordinates.qualify(view, "a", "0", "1")["status"] == "exact_mapped"
    assert coordinates.qualify(view, "a", "1", "2")["status"] == "mismatch"
    assert coordinates.qualify(view, " a ", "0", "1")["status"] == "mismatch"
    assert coordinates.qualify(view, "", "0", "1")["status"] == "empty_evidence"
    with pytest.raises(UnicodeDecodeError):
        coordinates.canonical_view(b"\xff")


def test_frozen_selection_rejects_new_ids_and_duplicates():
    train = [str(i) for i in range(100)]
    selected = coordinates.select_articles(train)
    coordinates.validate_selection(
        selected, {"train": train, "validation": ["200"], "test": ["300"]}
    )
    for changed in (selected[:-1], selected[:-1] + ["200"], selected[:-1] + [selected[0]]):
        with pytest.raises(ValueError):
            coordinates.validate_selection(
                changed, {"train": train, "validation": ["200"], "test": ["300"]}
            )


def test_diagnostics_cannot_promote_repaired_evidence():
    view = coordinates.canonical_view(b"alpha beta alpha beta")
    result = coordinates.qualify(view, "alpha  beta", "0", "10")
    assert result["status"] == "mismatch"
    assert result["diagnostics"]["whitespace_collapsed_equal"] is True
    result = coordinates.qualify(view, "alpha beta", "1", "11")
    assert result["status"] == "mismatch"
    assert result["diagnostics"]["exact_occurrences_elsewhere"] == 2


def test_html_entity_and_shift_are_diagnostic_only():
    result = coordinates.qualify(coordinates.canonical_view(b" x < y."), "x &lt; y.", "0", "6")
    assert result["status"] == "mismatch"
    assert result["residual_category"] == "html_entity_text_elsewhere_nonmatching_coordinates"
    assert result["diagnostics"]["html_unescaped_occurrence_shifts"] == [1]


def test_frozen_inputs_fail_before_archive_content_inspection(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    archive.write_bytes(b"not an archive")
    selected = tmp_path / "selected.json"
    selected.write_text("[]")
    with pytest.raises(ValueError, match="archive digest"):
        coordinates.audit(archive, selected)
    monkeypatch.setattr(coordinates, "ARCHIVE_SHA256", coordinates.digest(archive.read_bytes()))
    with pytest.raises(ValueError, match="selection file digest"):
        coordinates.audit(archive, selected)


def test_audit_keeps_frozen_subset_and_original_prompt_exclusions(tmp_path, monkeypatch):
    import csv
    import io
    import json
    import tarfile

    def csv_data(rows):
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue().encode()

    ids = [str(i) for i in range(64)]
    selected = coordinates.select_articles(ids)
    article = selected[0]
    prompts = [
        {
            "PMCID": article,
            "PromptID": str(i),
            "Outcome": "o",
            "Intervention": "i",
            "Comparator": "" if i == 4 else "c",
        }
        for i in range(6)
    ]
    annotations = [
        {
            "PMCID": article,
            "PromptID": str(i),
            "UserID": "u",
            "Annotations": "β",
            "Evidence Start": "2",
            "Evidence End": "3",
            "Valid Label": "True",
            "Valid Reasoning": "False" if i == 5 else "True",
            "Label Code": "1",
            "Label": "significantly increase" if i == 3 else "significantly increased",
        }
        for i in range(6)
    ]
    annotations.append({**annotations[1], "Label Code": "-1", "Label": "significantly decreased"})
    annotations.append({key: ("200" if key == "PMCID" else "SEALED") for key in annotations[0]})
    prompts.append({key: ("200" if key == "PMCID" else "SEALED") for key in prompts[0]})
    files = {f"txt_files/PMC{a}.txt": "α\r\nβ".encode() for a in ids}
    files.update(
        {
            "splits/train_article_ids.txt": "\n".join(ids).encode(),
            "splits/validation_article_ids.txt": b"200",
            "splits/test_article_ids.txt": b"300",
            "txt_files/PMC200.txt": b"\xff",
            "txt_files/PMC300.txt": b"\xff",
            "README.md": b"### Questionable:\n2\n",
            "prompts_merged.csv": csv_data(prompts),
            "annotations_merged.csv": csv_data(annotations),
        }
    )
    archive = tmp_path / "fixture.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps(selected))
    monkeypatch.setattr(coordinates, "ARCHIVE_SHA256", coordinates.digest(archive.read_bytes()))
    monkeypatch.setattr(
        coordinates, "SELECTED_IDS_SHA256", coordinates.digest(selection.read_bytes())
    )
    summary, manifest = coordinates.audit(archive, selection)
    assert summary["span_counts"] == {"exact_mapped": 7}
    assert summary["eligible_prompts_before_license"] == 1
    assert summary["prompts_with_verified_label_disagreement"] == 1
    assert manifest["eligible_prompt_ids_before_license"] == ["0"]
    assert len(manifest["rows"]) == 7
    assert len(manifest["articles"]) == 64
    assert "SEALED" not in str(summary) + str(manifest)
