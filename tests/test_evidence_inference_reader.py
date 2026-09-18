"""Model-free contracts using synthetic source strings only."""

import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
spec = importlib.util.spec_from_file_location(
    "reader", Path(__file__).parents[1] / "tools/evidence_inference_reader.py"
)
assert spec and spec.loader
reader = importlib.util.module_from_spec(spec)


def setup_module():
    assert spec and spec.loader and spec.origin
    assert Path(spec.origin).exists(), "reader implementation missing"
    spec.loader.exec_module(reader)


class Characters:
    chat_template = "synthetic-template"

    def encode(self, text, add_special_tokens=False, **kwargs):
        return list(range(len(text) + (2 if add_special_tokens else 0)))

    def __call__(self, text, **kwargs):
        return {"offset_mapping": [(i, i + 1) for i in range(len(text))]}

    def apply_chat_template(self, messages, **kwargs):
        return list(range(sum(len(m["content"]) for m in messages) + 10))


def test_windows_keep_repeated_source_offsets_and_unicode_roundtrip():
    view = reader.canonical_view("α\r\nrepeat repeat\r🙂".encode())
    windows = reader.source_windows(view, Characters(), limit=7)
    assert [(w["start"], w["end"]) for w in windows] == [(0, 7), (7, 14), (14, 17)]
    assert "".join(w["text"] for w in windows) == view["text"]
    for w in windows:
        a, b = w["raw_byte_span"]
        assert reader.normalize(view["bytes"][a:b].decode()) == w["text"]
        assert w["selector_tokens"] <= 512


def test_interval_union_counts_whitespace_once():
    assert reader.union_intervals([[1, 4], [3, 7], [7, 8], [10, 12]]) == [[1, 8], [10, 12]]


def test_messages_do_not_include_reference_metadata():
    p = {"intervention": "I", "comparator": "C", "outcome": "O", "label": "increased", "row_id": 3}
    payload = reader.reader_payload(p, ["A"], Characters())
    assert (
        payload["payload"]["messages"][1]["content"]
        == '{"intervention": "I", "comparator": "C", "outcome": "O", "evidence": ["A"]}'
    )
    assert payload["payload"]["chat_template_kwargs"] == {"enable_thinking": False}


@pytest.mark.parametrize(
    "text",
    [
        '{"label":"decreased","x":0}',
        '{"label":"decreased","label":"increased"}',
        "[]",
        '```{"label":"decreased"}```',
        '{"label":"decreased"} extra',
    ],
)
def test_parser_rejects_noncontract_output(text):
    with pytest.raises(ValueError):
        reader.parse_label(text)


def test_parser_preserves_abstention():
    assert reader.parse_label(' {"label":"insufficient_evidence"} ') == "insufficient_evidence"


def test_metrics_keep_failure_and_abstention_in_denominator():
    results = [
        ("decreased", "decreased"),
        ("increased", "decreased"),
        ("no_significant_difference", "insufficient_evidence"),
        ("increased", None),
    ]
    report = reader.native_metrics(results)
    assert report["accuracy"] == 0.25
    assert report["classes"]["increased"]["false_negative"] == 2
    assert report["classes"]["decreased"]["false_positive"] == 1
    assert report["class_counts"] == {
        "decreased": 1,
        "no_significant_difference": 1,
        "increased": 2,
    }


def test_span_coverage_unions_overlapping_intervals():
    assert reader.span_coverage([[0, 4], [2, 6]], [[3, 5], [4, 8]]) == {
        "precision": 0.5,
        "recall": 0.6,
        "selected_characters": 6,
        "reference_characters": 5,
        "intersection_characters": 3,
    }


def test_bootstrap_keeps_article_prompt_multiplicity():
    rows = [
        {
            "article_id": "a",
            "target": "increased",
            "predictions": {a: "increased" for a in reader.ARMS},
        },
        {
            "article_id": "a",
            "target": "decreased",
            "predictions": {a: "decreased" for a in reader.ARMS},
        },
        {"article_id": "b", "target": "decreased", "predictions": {a: None for a in reader.ARMS}},
    ]
    result = reader.cluster_bootstrap(rows)
    assert result["replicates"] == 2000
    assert result["seed"] == 1729
    assert all(r["accuracy"]["interval_95"] == [0, 0] for r in result["deltas"].values())
    assert result["absent_class_replicates"] == 2000


def test_chat_template_explicitly_requests_token_id_list():
    class BatchDefault:
        def apply_chat_template(self, messages, **kwargs):
            if kwargs.get("return_dict") is not False:
                return {"input_ids": list(range(40000)), "attention_mask": []}
            return list(range(40000))

    result = reader.reader_payload(
        {"intervention": "i", "comparator": "c", "outcome": "o"}, ["x"], BatchDefault()
    )
    assert result["input_tokens"] == 40000
    assert not result["fits"]


def synthetic_sources(tmp_path, monkeypatch, *, dispute=False, failed=False):
    import csv
    import io
    import json
    import tarfile

    raw = "α\r\nrepeat repeat".encode()
    view = reader.canonical_view(raw)
    rows = []
    records = []
    for i, (start, end) in enumerate(((2, 8), (9, 15))):
        row = {
            "PromptID": "p",
            "PMCID": "a",
            "Intervention": "I",
            "Comparator": "C",
            "Outcome": "O",
            "Annotations": view["text"][start:end],
            "Evidence Start": str(start),
            "Evidence End": str(end),
            "Label Code": "1" if dispute and i else "-1",
            "Label": reader.LABELS["1" if dispute and i else "-1"],
            "Valid Label": "True",
            "Valid Reasoning": "True",
        }
        if failed:
            row["Annotations"] = "not matching"
        rows.append(row)
        records.append(
            {
                "csv_data_row_zero_based": i,
                "prompt_id": "p",
                "problems": [],
                "annotation_row_sha256": reader.digest(json.dumps(row, sort_keys=True).encode()),
                **reader.qualify(view, row["Annotations"], str(start), str(end)),
            }
        )

    def csv_bytes(data):
        handle = io.StringIO(newline="")
        writer = csv.DictWriter(handle, list(data[0]))
        writer.writeheader()
        writer.writerows(data)
        return handle.getvalue().encode()

    archive = tmp_path / "archive.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, data in {
            "txt_files/PMCa.txt": raw,
            "prompts_merged.csv": csv_bytes(
                [
                    {
                        "PromptID": "p",
                        "PMCID": "a",
                        "Intervention": "I",
                        "Comparator": "C",
                        "Outcome": "O",
                    }
                ]
            ),
            "annotations_merged.csv": csv_bytes(rows),
        }.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    coord = tmp_path / "coordinates.json"
    reader.write_json(coord, {"rows": records})
    article = {"article_id": "a", "prompt_ids": ["p"]}
    provenance = {
        "summary": {},
        "articles": [{**article, "candidate_status": "attribution_research_candidate"}],
    }
    prov = tmp_path / "provenance.json"
    reader.write_json(prov, provenance)
    cohort = tmp_path / "cohort.json"
    reader.write_json(
        cohort,
        {
            "articles": [article],
            "prompt_count": 1,
            "archive_sha256": reader.digest(archive.read_bytes()),
            "provenance_manifest_sha256": reader.digest(prov.read_bytes()),
            "coordinate_manifest_sha256": reader.digest(coord.read_bytes()),
        },
    )
    monkeypatch.setattr(reader, "COHORT_SHA256", reader.digest(cohort.read_bytes()))
    monkeypatch.setattr(reader, "provenance_audit", lambda *args: ({}, provenance))
    return archive, cohort, prov, coord


def test_source_join_collapses_annotators_and_preserves_repeated_intervals(tmp_path, monkeypatch):
    paths = synthetic_sources(tmp_path, monkeypatch)
    _, prompts, _, references, _ = reader.qualified_inputs(*paths)
    assert list(prompts) == ["p"]
    assert references == [
        {"prompt_id": "p", "article_id": "a", "target": "decreased", "intervals": [[2, 8], [9, 15]]}
    ]


@pytest.mark.parametrize("problem", ["dispute", "failed", "tamper"])
def test_source_join_rejects_disagreement_failed_span_and_digest_tamper(
    tmp_path, monkeypatch, problem
):
    paths = synthetic_sources(
        tmp_path, monkeypatch, dispute=problem == "dispute", failed=problem == "failed"
    )
    if problem == "tamper":
        paths[0].write_bytes(paths[0].read_bytes() + b"x")
    with pytest.raises(ValueError):
        reader.qualified_inputs(*paths)
