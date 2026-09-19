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
    for path in (root / "prepared-002", root / "live-20260919-001", root / "evaluation-20260919-001"):
        path.chmod(0o555)
    root.chmod(0o555)
    try:
        with pytest.raises(audit.AuditError, match="preparation manifest SHA-256 mismatch"):
            audit.bind_inputs(root, published)
    finally:
        root.chmod(0o755)
        for path in (root / "prepared-002", root / "live-20260919-001", root / "evaluation-20260919-001"):
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
    references = [{"prompt_id": "p1", "article_id": "a1", "target": "increased"}, {"prompt_id": "p2", "article_id": "a2", "target": "decreased"}]
    events = [
        terminal("p1", "a1", arm, "increased") for arm in ("full", "selected", "oracle")
    ] + [terminal("p2", "a2", arm, "decreased") for arm in ("full", "selected", "oracle")]
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
        audit.validate_source_windows([
            {"start": 0, "end": 4}, {"start": 3, "end": 7},
        ])


def test_two_window_upper_bound_cannot_cover_three_disjoint_required_windows():
    result = audit.two_window_upper_bound(
        [{"start": 0, "end": 2}, {"start": 4, "end": 6}, {"start": 8, "end": 10}],
        [[0, 2], [4, 6], [8, 10]],
    )
    assert result["recall"] == pytest.approx(2 / 3)


def test_public_summary_excludes_case_content():
    published = audit.public_summary({
        "input_digests": {"ledger": "a" * 64},
        "prompt_count": 101,
        "article_count": 20,
        "outcomes": {"selected_correct": 79},
        "geometry": {"max_complete": 3},
        "decision": "no-intervention",
        "raw_text": "must not escape",
    })
    assert published["prompt_count"] == 101
    assert "raw_text" not in published
    assert published["claim_boundary"] == "deterministic overlap and rank audit only"


def test_write_json_refuses_existing_output(tmp_path: Path):
    output = tmp_path / "audit.json"
    audit.write_json(output, {"schema_version": "test/v1"})
    with pytest.raises(audit.AuditError, match="output exists"):
        audit.write_json(output, {"schema_version": "test/v1"})
