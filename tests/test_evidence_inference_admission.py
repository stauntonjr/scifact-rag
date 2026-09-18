"""Synthetic tests for bounded admission; no real corpus text in fixtures."""

import csv
import importlib.util
import io
import tarfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "evidence_inference_admission",
    Path(__file__).parents[1] / "tools" / "evidence_inference_admission.py",
)
assert spec and spec.loader
admission = importlib.util.module_from_spec(spec)
spec.loader.exec_module(admission)


@pytest.mark.parametrize(
    "name,kind",
    [("../escape", tarfile.REGTYPE), ("/abs", tarfile.REGTYPE), ("link", tarfile.SYMTYPE)],
)
def test_archive_rejects_unsafe_entries(name, kind):
    member = tarfile.TarInfo(name)
    member.type = kind
    with pytest.raises(ValueError):
        admission.validate_members([member])


def test_exact_inclusive_span_keeps_failures():
    assert admission.span_status("α beta", "beta", "2", "5") == "exact"
    assert admission.span_status("α beta", "beta", "2", "6") == "out_of_bounds"
    assert admission.span_status("α beta", "Beta", "2", "5") == "mismatch"
    assert admission.span_status("a\r\nb", "b", "2", "2") == "mismatch"
    assert admission.span_status("text", "text", "-1", "-1") == "publisher_unavailable"
    assert admission.span_status("text", "text", "x", "1") == "invalid_offset"


def test_hash_selection_is_order_independent_and_bounded():
    ids = [str(x) for x in range(100)]
    chosen = admission.select_articles(ids)
    assert len(chosen) == 64
    assert chosen == admission.select_articles(list(reversed(ids)) + ids)


def csv_bytes(headers, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue().encode()


@pytest.mark.parametrize("start,status,eligible", [("0", "exact", 1), ("bad", "invalid_offset", 0)])
def test_audit_does_not_decode_heldout_text_or_inspect_heldout_outcomes(
    tmp_path, start, status, eligible
):
    files = {
        "README.md": b"Inclusive start and end.",
        "splits/train_article_ids.txt": b"1\n4\n",
        "txt_files/PMC4.txt": b"unannotated",
        "splits/validation_article_ids.txt": b"2\n",
        "splits/test_article_ids.txt": b"3\n",
        "txt_files/PMC1.txt": b"evidence",
        "txt_files/PMC2.txt": b"\xff",
        "txt_files/PMC3.txt": b"\xff",
        "prompts_merged.csv": csv_bytes(
            ["PromptID", "PMCID", "Outcome", "Intervention", "Comparator"],
            [["a", "1", "o", "i", "c"], ["b", "3", "SEALED", "SEALED", "SEALED"]],
        ),
        "annotations_merged.csv": csv_bytes(
            [
                "UserID",
                "PromptID",
                "PMCID",
                "Valid Label",
                "Valid Reasoning",
                "Label",
                "Annotations",
                "Label Code",
                "In Abstract",
                "Evidence Start",
                "Evidence End",
            ],
            [
                [
                    "u",
                    "a",
                    "1",
                    "True",
                    "True",
                    "significantly increased",
                    "evidence",
                    "1",
                    "False",
                    start,
                    "7",
                ],
                [
                    "u",
                    "b",
                    "3",
                    "SEALED",
                    "SEALED",
                    "SEALED",
                    "SEALED",
                    "SEALED",
                    "SEALED",
                    "SEALED",
                    "SEALED",
                ],
            ],
        ),
    }
    archive = tmp_path / "fixture.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, content in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            tar.addfile(member, io.BytesIO(content))
    summary, manifest = admission.audit(archive)
    assert summary["train_sample"]["span_counts"] == {status: 1}
    assert summary["train_sample"]["eligible_prompts_before_license"] == eligible
    assert summary["train_sample"]["articles_with_prompts"] == 1
    assert summary["train_sample"]["articles_without_prompts"] == 1
    assert summary["partitions"]["annotation_rows"] == {"train": 1, "test": 1}
    assert "SEALED" not in str(summary) + str(manifest)
    assert len(manifest["files"]) == len(files)
