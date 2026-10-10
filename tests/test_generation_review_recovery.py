import pytest
from test_generation_review_workflow import FakeTransport, manifest

from scifact_rag import generation_review_recovery as recovery
from scifact_rag import generation_review_workflow as w


class Flaky(FakeTransport):
    def dispatch(self, request, timeout_seconds):
        if not self.requests:
            self.requests.append(request)
            raise TimeoutError("attributable fake timeout")
        return super().dispatch(request, timeout_seconds)


def test_recovery_retries_preserves_failure_and_finishes(tmp_path):
    result = recovery.run(tmp_path / "run", manifest(), Flaky(), [])
    assert result["completed_turns"] == 8
    assert result["failed_turns"] == 1
    assert result["attempted_turns"] == 9
    assert result["execution_status"] == "execution_complete"
    assert result["unknown_turns"] == 0


def test_recovery_reuses_completed_without_dispatch_and_detects_tamper(tmp_path):
    source = tmp_path / "source"
    w.run(source, manifest(), FakeTransport())
    transport = FakeTransport()
    result = recovery.run(tmp_path / "recovered", manifest(), transport, [source])
    assert result["completed_turns"] == 8
    assert transport.requests == []
    path = next((source / "attempts").glob("*.result.json"))
    path.write_text("{}")
    with pytest.raises(w.WorkflowStop, match="digest"):
        recovery.run(tmp_path / "tampered", manifest(), FakeTransport(), [source])


def test_recovery_unknown_is_never_retried(tmp_path):
    source = tmp_path / "source"
    w.run(source, manifest(), FakeTransport())
    (source / "terminal.json").unlink()
    next((source / "attempts").glob("*.result.json")).unlink()
    with pytest.raises(w.WorkflowStop):
        recovery.run(tmp_path / "recovered", manifest(), FakeTransport(), [source])


def test_exact_quote_in_earlier_excerpt_of_same_document_is_valid():
    from test_generation_review_workflow import case, judgment

    source = case()
    value = judgment(source)
    source["evidence"].append(
        {
            "document_id": source["evidence"][0]["document_id"],
            "title": "Other excerpt",
            "text": "A different excerpt.",
        }
    )
    w.validate_judgment(value, source)


def test_quote_repeated_within_one_excerpt_still_ambiguous():
    from test_generation_review_workflow import case, judgment

    source = case()
    value = judgment(source)
    source["evidence"][0]["text"] *= 2
    with pytest.raises(w.WorkflowStop, match="ambiguous"):
        w.validate_judgment(value, source)


def test_identical_excerpts_do_not_make_document_quote_ambiguous():
    from test_generation_review_workflow import case, judgment

    source = case()
    value = judgment(source)
    source["evidence"].append(dict(source["evidence"][0]))
    w.validate_judgment(value, source)


def test_quote_in_distinct_excerpts_remains_ambiguous():
    from test_generation_review_workflow import case, judgment

    source = case()
    value = judgment(source)
    source["evidence"].append(
        {**source["evidence"][0], "text": "Prefix. " + source["evidence"][0]["text"]}
    )
    with pytest.raises(w.WorkflowStop, match="ambiguous"):
        w.validate_judgment(value, source)


def test_failed_raw_output_revalidation_preserves_original(tmp_path):
    import json

    source = tmp_path / "source"
    w.run(source, manifest(), FakeTransport())
    path = source / "attempts/001.result.json"
    result = json.loads(path.read_text())
    result.update(status="failed", judgment=None, validation_errors=["historical validator bug"])
    path.write_text(json.dumps(result))
    terminal = source / "terminal.json"
    t = json.loads(terminal.read_text())
    for old in (source / "attempts").glob("*.json"):
        if int(old.name.split(".")[0]) > 3:
            old.unlink()
    t["artifact_digests"] = {
        p.name: w._file_digest(p) for p in (source / "attempts").glob("*.json")
    }
    terminal.write_text(json.dumps(t))
    original = path.read_bytes()
    audit = []
    records, _, _, attempted, failed, _ = recovery.retain(manifest(), [source], audit)
    assert attempted == 3 and failed == 0 and len(records) == 3
    assert path.read_bytes() == original
    assert audit[0]["original_status"] == "failed" and audit[0]["current_valid"]


def test_quote_delimiters_only_normalized_when_inner_exact_unique():
    from test_generation_review_workflow import case, judgment

    source = case()
    value = judgment(source)
    value["rationale"]["answer_quotes"][0] = '"' + source["answer"] + '"'
    value["rationale"]["evidence_quotes"][0]["quote"] = '"' + source["evidence"][0]["text"] + '"'
    normalized, edits = recovery.normalize_quote_delimiters(value, source)
    w.validate_judgment(normalized, source)
    assert len(edits) == 2
    assert value["rationale"]["answer_quotes"][0].startswith('"')
    value["rationale"]["answer_quotes"][0] = '"Wrong paraphrase"'
    normalized, _ = recovery.normalize_quote_delimiters(value, source)
    with pytest.raises(w.WorkflowStop, match="not exact"):
        w.validate_judgment(normalized, source)


@pytest.mark.parametrize(
    "answer, quote",
    [
        ('"Exact."', '"Exact."'),
        ('"Exact." "Exact."', '"Exact."'),
        ("Exact. Exact.", '"Exact."'),
        ("Exact.", '""Exact.""'),
    ],
)
def test_delimiter_normalization_does_not_relax_exactness(answer, quote):
    from test_generation_review_workflow import case, judgment

    source = case()
    source["answer"] = answer
    value = judgment(source)
    value["rationale"]["answer_quotes"] = [quote]
    result, edits = recovery.normalize_quote_delimiters(value, source)
    assert result == value
    assert edits == []


def test_late_punctuation_normalization_remains_exact_and_opt_in():
    from test_generation_review_workflow import case, judgment

    source = case()
    source["answer"] = "Exact phrase, followed by more."
    value = judgment(source)
    value["rationale"]["answer_quotes"] = ["“Exact phrase.”"]
    original, edits = recovery.normalize_quote_delimiters(value, source)
    assert original == value and not edits
    normalized, edits = recovery.normalize_quote_delimiters(value, source, late=True)
    assert normalized["rationale"]["answer_quotes"] == ["Exact phrase"]
    assert edits
    w.validate_judgment(normalized, source)
    value["rationale"]["answer_quotes"] = ["“Wrong phrase.”"]
    result, edits = recovery.normalize_quote_delimiters(value, source, late=True)
    assert result == value and not edits


def test_late_fill_preserves_checkpoint_and_original_outputs(tmp_path):
    import json

    source = tmp_path / "source"
    w.run(source, manifest(), FakeTransport())
    for f in (source / "attempts").glob("*.json"):
        if int(f.name.split(".")[0]) > 3:
            f.unlink()
    target = source / "attempts/003.result.json"
    result = json.loads(target.read_text())
    value = json.loads(result["transport"]["raw_output"])
    value["rationale"]["answer_quotes"][0] = "“" + value["rationale"]["answer_quotes"][0] + "”"
    result["transport"]["raw_output"] = json.dumps(value)
    result.update(status="failed", judgment=None, validation_errors=["quote syntax"])
    target.write_text(json.dumps(result))
    terminal = source / "terminal.json"
    t = json.loads(terminal.read_text())
    t["artifact_digests"] = {
        f.name: w._file_digest(f) for f in (source / "attempts").glob("*.json")
    }
    terminal.write_text(json.dumps(t))
    selected, *_ = recovery.retain(manifest(), [source])
    before = {k: w.canonical_json_sha256(v) for k, v in selected.items()}
    original = target.read_bytes()
    filled, repairs = recovery.fill_missing_quotes(manifest(), [source], selected)
    assert len(selected) == 2 and len(filled) == 3 and len(repairs) == 1
    assert {k: w.canonical_json_sha256(filled[k]) for k in selected} == before
    assert {k: w.canonical_json_sha256(v) for k, v in selected.items()} == before
    assert target.read_bytes() == original
    again, repairs = recovery.fill_missing_quotes(manifest(), [source], filled)
    assert again == filled and repairs == []
