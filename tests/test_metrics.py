from __future__ import annotations

import pytest

from scifact_rag.metrics import evaluate_rankings


def test_retrieval_metrics_match_small_known_example() -> None:
    metrics = evaluate_rankings(
        qrels={"q1": {"d1": 1, "d2": 1}, "q2": {"d3": 1}},
        rankings={"q1": ["d1", "x"], "q2": ["x", "d3"]},
        cutoff=2,
    )

    assert metrics.queries == 2
    assert metrics.ndcg == pytest.approx((1 / (1 + 1 / 1.5849625) + 1 / 1.5849625) / 2)
    assert metrics.mean_average_precision == pytest.approx((0.5 + 0.5) / 2)
    assert metrics.recall == pytest.approx((0.5 + 1.0) / 2)
    assert metrics.precision == pytest.approx(0.5)
    assert metrics.mean_reciprocal_rank == pytest.approx(0.75)
