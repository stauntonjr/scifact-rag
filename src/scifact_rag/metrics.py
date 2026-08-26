from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from .domain import RetrievalMetrics


def evaluate_rankings(
    qrels: Mapping[str, Mapping[str, int]],
    rankings: Mapping[str, Sequence[str]],
    cutoff: int,
) -> RetrievalMetrics:
    if cutoff < 1:
        raise ValueError("cutoff must be positive")
    if not qrels:
        raise ValueError("qrels must not be empty")

    ndcg_total = 0.0
    average_precision_total = 0.0
    recall_total = 0.0
    precision_total = 0.0
    reciprocal_rank_total = 0.0

    for query_id, relevance in qrels.items():
        relevant = {doc_id: grade for doc_id, grade in relevance.items() if grade > 0}
        ranked = list(rankings.get(query_id, ()))[:cutoff]
        gains = [relevant.get(doc_id, 0) for doc_id in ranked]
        dcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(gains, 1))
        ideal = sorted(relevant.values(), reverse=True)[:cutoff]
        idcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal, 1))
        ndcg_total += dcg / idcg if idcg else 0.0

        hits = 0
        precision_sum = 0.0
        first_relevant_rank = 0
        for rank, doc_id in enumerate(ranked, 1):
            if doc_id not in relevant:
                continue
            hits += 1
            precision_sum += hits / rank
            if first_relevant_rank == 0:
                first_relevant_rank = rank
        average_precision_total += precision_sum / len(relevant) if relevant else 0.0
        recall_total += hits / len(relevant) if relevant else 0.0
        precision_total += hits / cutoff
        reciprocal_rank_total += 1 / first_relevant_rank if first_relevant_rank else 0.0

    count = len(qrels)
    return RetrievalMetrics(
        queries=count,
        cutoff=cutoff,
        ndcg=ndcg_total / count,
        mean_average_precision=average_precision_total / count,
        recall=recall_total / count,
        precision=precision_total / count,
        mean_reciprocal_rank=reciprocal_rank_total / count,
    )
