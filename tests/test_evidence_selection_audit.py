import importlib.util
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).parents[1] / "tools" / "evidence_selection_audit.py"
spec = importlib.util.spec_from_file_location("evidence_selection_audit", TOOL)
assert spec and spec.loader
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def make_retained_tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "reader-v1"
    (root / "prepared-002").mkdir(parents=True)
    (root / "live-20260919-001").mkdir()
    (root / "evaluation-20260919-001").mkdir()
    for path in (
        root / "prepared-002" / "manifest.json",
        root / "live-20260919-001" / "runtime.json",
        root / "live-20260919-001" / "ledger.jsonl",
        root / "evaluation-20260919-001" / "report.json",
    ):
        path.write_text("{}")
    published = tmp_path / "published.json"
    published.write_text("{}")
    return root, published


def test_bind_inputs_requires_exact_reader_tree_not_read_only_permissions(tmp_path: Path):
    root = tmp_path / "reader-v1"
    root.mkdir()
    with pytest.raises(audit.AuditError, match="prepared-002"):
        audit.bind_inputs(root, tmp_path / "published.json")


def test_bind_inputs_rejects_digest_drift_before_case_loading(tmp_path: Path):
    root, published = make_retained_tree(tmp_path)
    for path in (
        root / "prepared-002",
        root / "live-20260919-001",
        root / "evaluation-20260919-001",
    ):
        path.chmod(0o555)
    root.chmod(0o555)
    try:
        with pytest.raises(audit.AuditError, match="preparation manifest SHA-256 mismatch"):
            audit.bind_inputs(root, published)
    finally:
        root.chmod(0o755)
        for path in (
            root / "prepared-002",
            root / "live-20260919-001",
            root / "evaluation-20260919-001",
        ):
            path.chmod(0o755)


def terminal(prompt_id: str, article_id: str, arm: str, label: str) -> dict[str, object]:
    return {
        "prompt_id": prompt_id,
        "article_id": article_id,
        "arm": arm,
        "status": "completed",
        "response": {"choices": [{"message": {"content": f'{{"label":"{label}"}}'}}]},
    }


def test_reconcile_outcomes_joins_differently_ordered_sources_by_id():
    prepared = [{"prompt_id": "p2", "article_id": "a2"}, {"prompt_id": "p1", "article_id": "a1"}]
    references = [
        {"prompt_id": "p1", "article_id": "a1", "target": "increased"},
        {"prompt_id": "p2", "article_id": "a2", "target": "decreased"},
    ]
    events = [terminal("p1", "a1", arm, "increased") for arm in ("full", "selected", "oracle")] + [
        terminal("p2", "a2", arm, "decreased") for arm in ("full", "selected", "oracle")
    ]
    rows = audit.reconcile_outcomes(prepared, references, events)
    assert [row.prompt_id for row in rows] == ["p2", "p1"]
    assert rows[0].article_id == "a2"


def test_reconcile_outcomes_preserves_abstention_as_wrong():
    prepared = [{"prompt_id": "p1", "article_id": "a1"}]
    references = [{"prompt_id": "p1", "article_id": "a1", "target": "increased"}]
    events = [terminal("p1", "a1", arm, "increased") for arm in ("full", "oracle")]
    events.append(terminal("p1", "a1", "selected", "insufficient_evidence"))
    row = audit.reconcile_outcomes(prepared, references, events)[0]
    assert row.predictions["selected"] == "insufficient_evidence"
    assert row.abstentions["selected"] is True
    assert row.correctness["selected"] is False


def test_reference_spans_union_but_source_window_overlap_fails():
    assert audit.coverage([[0, 4], [3, 8]], [[2, 6]])["reference_characters"] == 8
    with pytest.raises(audit.AuditError, match="overlapping source windows"):
        audit.validate_source_windows(
            [
                {"start": 0, "end": 4},
                {"start": 3, "end": 7},
            ]
        )


def test_two_window_upper_bound_cannot_cover_three_disjoint_required_windows():
    result = audit.two_window_upper_bound(
        [{"start": 0, "end": 2}, {"start": 4, "end": 6}, {"start": 8, "end": 10}],
        [[0, 2], [4, 6], [8, 10]],
    )
    assert result["recall"] == pytest.approx(2 / 3)


def test_public_summary_excludes_case_content():
    published = audit.public_summary(
        {
            "input_digests": {"ledger": "a" * 64},
            "prompt_count": 101,
            "article_count": 1,
            "per_article": [
                {
                    "article_ordinal": 1,
                    "prompt_count": 101,
                    "correct": {"full": 92},
                    "wrong": {"full": 9},
                    "abstentions": {"full": 0},
                    "geometry": {},
                    "mean_actual_recall": 0.5,
                    "mean_maximum_recall": 1.0,
                }
            ],
            "outcomes": {"selected_correct": 79},
            "geometry": {"max_complete": 3},
            "decision": "no-intervention",
            "raw_text": "must not escape",
        }
    )
    assert published["prompt_count"] == 101
    assert "raw_text" not in published
    assert published["claim_boundary"] == "deterministic overlap and rank audit only"


def test_write_json_refuses_existing_output(tmp_path: Path):
    output = tmp_path / "audit.json"
    audit.write_json(output, {"schema_version": "test/v1"})
    with pytest.raises(audit.AuditError, match="output exists"):
        audit.write_json(output, {"schema_version": "test/v1"})


@pytest.mark.parametrize("interval", [[True, 3], [1.0, 3], [-1, 3], [3, 3], [0, 20]])
def test_malformed_or_out_of_bounds_reference_fails(interval):
    with pytest.raises(audit.AuditError, match="interval"):
        audit.validate_intervals([interval], 10)


def test_score_ties_preserve_distinct_repeated_text_offsets():
    windows = [
        {"start": 0, "end": 2, "text": "aa"},
        {"start": 2, "end": 4, "text": "aa"},
        {"start": 4, "end": 6, "text": "aa"},
    ]
    scores = {"results": [{"index": i, "relevance_score": 1} for i in [2, 0, 1]]}
    rows = audit.rank_windows(windows, scores, [[4, 6]], [[0, 2], [2, 4]])
    assert [r["rank"] for r in rows] == [1, 2, 3]
    assert [r["reference_overlap_characters"] for r in rows] == [0, 0, 2]
    with pytest.raises(audit.AuditError, match="selected.*rank"):
        audit.rank_windows(windows, scores, [[4, 6]], [[0, 2], [4, 6]])


def test_single_window_and_unsorted_upper_bound_ties():
    assert audit.two_window_upper_bound([{"start": 5, "end": 8}], [[5, 8]])["intervals"] == (
        (5, 8),
    )
    assert audit.two_window_upper_bound(
        [{"start": 8, "end": 10}, {"start": 0, "end": 2}, {"start": 4, "end": 6}], [[0, 10]]
    )["intervals"] == ((0, 2), (4, 6))


def test_extra_terminal_identity_rejected():
    prompts = [{"prompt_id": "p", "article_id": "a"}]
    refs = [{"prompt_id": "p", "article_id": "a", "target": "decreased"}]
    events = [terminal("p", "a", arm, "decreased") for arm in audit.ARMS]
    events.append(terminal("extra", "a", "full", "decreased"))
    with pytest.raises(audit.AuditError, match="membership"):
        audit.reconcile_outcomes(prompts, refs, events)


def test_all_partitions_and_reverse_contrasts_include_article_counts():
    import itertools

    rows = [
        audit.OutcomeRow(
            str(i),
            "a",
            "decreased",
            {a: "decreased" if b else "increased" for a, b in zip(audit.ARMS, bits)},
            dict(zip(audit.ARMS, bits)),
            dict.fromkeys(audit.ARMS, False),
        )
        for i, bits in enumerate(itertools.product([False, True], repeat=3))
    ]
    outcomes = audit.aggregate_outcomes(rows)
    assert len(outcomes["partition"]) == 8
    assert all(v == {"prompt_count": 1, "article_count": 1} for v in outcomes["partition"].values())
    assert outcomes["contrasts"]["selected_correct_full_wrong"]["prompt_count"] == 2
    assert outcomes["error_population"] == {"prompt_count": 7, "article_count": 1}


def synthetic_audit_inputs(tmp_path, monkeypatch):
    import json

    import test_evidence_inference_reader_run as fixture

    fixture.setup_module()
    reader, prepared, _runtime, run, _, _ = fixture.synthetic_run(tmp_path, monkeypatch)
    root = tmp_path / "reader-v1"
    root.mkdir()
    prepared.rename(root / "prepared-002")
    run.rename(root / "live-20260919-001")
    prepared, run = root / "prepared-002", root / "live-20260919-001"
    evaluation = root / "evaluation-20260919-001"
    report = reader.evaluate(prepared, run / "ledger.jsonl", evaluation)
    public = tmp_path / "published.json"
    public.write_text(json.dumps(report))
    for name, path in [
        ("PREPARATION_SHA256", prepared / "manifest.json"),
        ("RUNTIME_SHA256", run / "runtime.json"),
        ("LEDGER_SHA256", run / "ledger.jsonl"),
    ]:
        monkeypatch.setattr(audit, name, audit.sha256_file(path))
    monkeypatch.setattr(
        audit,
        "EXPECTED_COUNTS",
        {"articles": 4, "prompts": 4, "reader_calls": 12, "selector_calls": 4, "pairs": 4},
    )
    monkeypatch.setattr(audit, "EXPECTED_CORRECT", dict.fromkeys(audit.ARMS, 4))
    monkeypatch.setattr(audit, "EXPECTED_ABSTENTIONS", dict.fromkeys(audit.ARMS, 0))
    return audit.bind_inputs(root, public)


def test_complete_synthetic_audit_is_text_free_and_preserves_input_hashes(tmp_path, monkeypatch):
    import json

    inputs = synthetic_audit_inputs(tmp_path, monkeypatch)
    before = {str(p): audit.sha256_file(p) for p in inputs.root.rglob("*") if p.is_file()}
    result = audit.run_audit(inputs, tmp_path / "out")
    assert result["prompt_count"] == 4
    assert len(result["outcomes"]["partition"]) == 8
    assert "synthetic evidence" not in "".join(p.read_text() for p in (tmp_path / "out").iterdir())
    assert before == {str(p): audit.sha256_file(p) for p in inputs.root.rglob("*") if p.is_file()}
    assert (
        json.loads((tmp_path / "out" / "selection-audit-manifest.json").read_text())[
            "input_hashes_before"
        ]
        == json.loads((tmp_path / "out" / "verification.json").read_text())["input_hashes_after"]
    )
    with pytest.raises(audit.AuditError, match="output exists"):
        audit.run_audit(inputs, tmp_path / "out")


@pytest.mark.parametrize(
    "mutation", ["order", "selected", "public", "reference", "missing_selected"]
)
def test_input_drift_refuses_publication(tmp_path, monkeypatch, mutation):
    import json

    inputs = synthetic_audit_inputs(tmp_path, monkeypatch)
    if mutation == "order":
        run = json.loads((inputs.run / "run.json").read_text())
        run["schedule"].reverse()
        (inputs.run / "run.json").write_text(json.dumps(run))
    elif mutation == "selected":
        path = next(inputs.run.glob("selected-*.json"))
        item = json.loads(path.read_text())
        item["intervals"] = [[0, 1]]
        path.write_text(json.dumps(item))
    elif mutation == "public":
        inputs.public_results.write_text("{}")
    elif mutation == "missing_selected":
        next(inputs.run.glob("selected-*.json")).unlink()
    else:
        (inputs.prepared / "references.jsonl").write_text("{}\n")
    with pytest.raises(audit.AuditError):
        audit.run_audit(inputs, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_missing_external_public_result_has_clean_error(tmp_path):
    root, public = make_retained_tree(tmp_path)
    public.unlink()
    with pytest.raises(audit.AuditError, match="missing required retained path"):
        audit.bind_inputs(root, public)


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_selector_scores_fail(score):
    with pytest.raises(audit.AuditError, match="score"):
        audit.rank_windows(
            [{"start": 0, "end": 2}],
            {"results": [{"index": 0, "relevance_score": score}]},
            [[0, 2]],
            [[0, 2]],
        )


def test_public_projection_rejects_nested_source_content():
    with pytest.raises(audit.AuditError, match="nonaggregate"):
        audit.public_summary(
            {
                "input_digests": {"ledger": "a" * 64},
                "prompt_count": 1,
                "article_count": 1,
                "per_article": [],
                "outcomes": {"correct": {"full": "raw article text"}},
                "geometry": {},
                "decision": "no-intervention",
            }
        )


def test_inference_order_independent_of_preparation_and_no_overlapping_requests(
    tmp_path, monkeypatch
):
    import json

    inputs = synthetic_audit_inputs(tmp_path, monkeypatch)
    prompts = audit.read_jsonl(inputs.prepared / "prompts.jsonl")
    events = audit.read_jsonl(inputs.ledger)
    run = json.loads((inputs.run / "run.json").read_text())
    audit.validate_inference_order(list(reversed(prompts)), run, events)
    events[1], events[2] = events[2], events[1]
    with pytest.raises(audit.AuditError, match="inference event order"):
        audit.validate_inference_order(prompts, run, events)


def test_geometry_failure_retains_preanalysis_manifest_but_no_results(tmp_path, monkeypatch):
    inputs = synthetic_audit_inputs(tmp_path, monkeypatch)

    def reject(*args):
        assert (tmp_path / "out" / "selection-audit-manifest.json").is_file()
        raise audit.AuditError("synthetic analysis stop")

    monkeypatch.setattr(audit, "rank_windows", reject)
    with pytest.raises(audit.AuditError, match="synthetic analysis stop"):
        audit.run_audit(inputs, tmp_path / "out")
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["selection-audit-manifest.json"]


def test_article_summaries_preserve_prompt_multiplicity_without_article_ids():
    cases = [
        {
            "article_id": "z",
            "correctness": dict.fromkeys(audit.ARMS, True),
            "abstentions": dict.fromkeys(audit.ARMS, False),
            "geometry": "actual_equals_maximum|maximum_complete",
            "actual": {"recall": 1.0},
            "maximum": {"recall": 1.0},
        },
        {
            "article_id": "a",
            "correctness": dict.fromkeys(audit.ARMS, False),
            "abstentions": dict.fromkeys(audit.ARMS, True),
            "geometry": "actual_below_maximum|maximum_complete",
            "actual": {"recall": 0.0},
            "maximum": {"recall": 1.0},
        },
        {
            "article_id": "a",
            "correctness": dict.fromkeys(audit.ARMS, True),
            "abstentions": dict.fromkeys(audit.ARMS, False),
            "geometry": "actual_equals_maximum|maximum_incomplete",
            "actual": {"recall": 0.5},
            "maximum": {"recall": 0.5},
        },
    ]
    rows = audit.article_summaries(cases)
    assert [r["article_ordinal"] for r in rows] == [1, 2]
    assert [r["prompt_count"] for r in rows] == [2, 1]
    assert (
        rows[0]["correct"]["full"]
        == rows[0]["wrong"]["full"]
        == rows[0]["abstentions"]["full"]
        == 1
    )
    assert rows[0]["mean_actual_recall"] == 0.25
    assert rows[0]["mean_maximum_recall"] == 0.75
    assert all("article_id" not in r for r in rows)


def test_audit_publishes_article_breakdown_and_recall_means(tmp_path, monkeypatch):
    inputs = synthetic_audit_inputs(tmp_path, monkeypatch)
    summary = audit.run_audit(inputs, tmp_path / "out")
    assert len(summary["per_article"]) == 4
    assert sum(r["prompt_count"] for r in summary["per_article"]) == summary["prompt_count"]
    assert (
        summary["geometry"]["mean_actual_recall"]
        == summary["geometry"]["mean_maximum_recall"]
        == 1.0
    )
    assert audit.public_summary(summary)["per_article"] == summary["per_article"]
    summary["geometry"]["mean_actual_recall"] = float("nan")
    with pytest.raises(audit.AuditError, match="recall"):
        audit.public_summary(summary)
