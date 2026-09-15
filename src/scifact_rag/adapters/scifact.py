from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import zipfile
from collections.abc import Iterable, Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from ..domain import EvidenceDocument
from ..evaluation import (
    GenerationEvaluationCase,
    GenerationEvaluationSet,
    GoldRationale,
    ScientificStance,
)

_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
_MD5 = "5f7d1de60b170fc8027bb7898e2efca1"
_VALIDATION_BUCKET = 4
_SPLIT_BUCKETS = 5


class QrelsSplit(StrEnum):
    TEST = "test"
    TRAIN_DEVELOPMENT = "train-development"
    TRAIN_VALIDATION = "train-validation"


class BeirSciFact:
    def __init__(self, root: Path, split: QrelsSplit = QrelsSplit.TEST) -> None:
        self.root = root
        self.split = split
        for relative in ("corpus.jsonl", "queries.jsonl", f"qrels/{_qrels_file(split)}"):
            if not (root / relative).is_file():
                raise FileNotFoundError(f"SciFact dataset is missing {relative}")

    @classmethod
    def ensure(
        cls,
        data_dir: Path,
        split: QrelsSplit = QrelsSplit.TEST,
    ) -> BeirSciFact:
        root = data_dir / "scifact"
        if (root / "corpus.jsonl").is_file():
            return cls(root, split)
        data_dir.mkdir(parents=True, exist_ok=True)
        archive = data_dir / "scifact.zip"
        with urllib.request.urlopen(_URL, timeout=60) as response, archive.open("wb") as target:
            shutil.copyfileobj(response, target)
        if _md5(archive) != _MD5:
            archive.unlink()
            raise ValueError("SciFact archive checksum mismatch")
        _extract_verified(archive, data_dir)
        return cls(root, split)

    def documents(self) -> Iterable[EvidenceDocument]:
        with (self.root / "corpus.jsonl").open(encoding="utf-8") as source:
            for line in source:
                raw = json.loads(line)
                yield EvidenceDocument(
                    doc_id=str(raw["_id"]),
                    title=str(raw.get("title", "")),
                    text=str(raw["text"]),
                )

    def queries(self) -> Mapping[str, str]:
        result: dict[str, str] = {}
        with (self.root / "queries.jsonl").open(encoding="utf-8") as source:
            for line in source:
                raw = json.loads(line)
                result[str(raw["_id"])] = str(raw["text"])
        return result

    def qrels(self) -> Mapping[str, Mapping[str, int]]:
        result: dict[str, dict[str, int]] = {}
        with (self.root / "qrels" / _qrels_file(self.split)).open(encoding="utf-8") as source:
            next(source)
            for line in source:
                query_id, doc_id, score = line.rstrip("\n").split("\t")
                if not _query_in_split(query_id, self.split):
                    continue
                result.setdefault(query_id, {})[doc_id] = int(score)
        return result


class SciFactGenerationEvaluationSource:
    def __init__(self, beir: BeirSciFact, official_root: Path) -> None:
        if beir.split is QrelsSplit.TEST:
            raise ValueError("generation evaluation construction cannot use the test split")
        self._beir = beir
        self._official_root = official_root
        for filename in ("claims_train.jsonl", "corpus.jsonl"):
            if not (official_root / filename).is_file():
                raise FileNotFoundError(f"official SciFact data is missing {filename}")

    def cases(self) -> GenerationEvaluationSet:
        official_claims = _records_by_id(
            self._official_root / "claims_train.jsonl",
            "id",
            "official SciFact claims",
        )
        official_documents = _records_by_id(
            self._official_root / "corpus.jsonl",
            "doc_id",
            "official SciFact corpus",
        )
        beir_queries = _records_by_id(
            self._beir.root / "queries.jsonl",
            "_id",
            "BEIR SciFact queries",
        )
        beir_document_ids = set(
            _records_by_id(
                self._beir.root / "corpus.jsonl",
                "_id",
                "BEIR SciFact corpus",
            )
        )
        qrels = self._beir.qrels()
        selected_claim_ids = {
            claim_id for claim_id in official_claims if _query_in_split(claim_id, self._beir.split)
        }
        if selected_claim_ids != set(qrels):
            raise ValueError("official claims and BEIR qrels do not define the same query IDs")

        cases = tuple(
            self._build_case(
                query_id,
                official_claims[query_id],
                beir_queries,
                qrels[query_id],
                official_documents,
                beir_document_ids,
            )
            for query_id in selected_claim_ids
        )
        return GenerationEvaluationSet(cases)

    def _build_case(
        self,
        query_id: str,
        claim: Mapping[str, Any],
        beir_queries: Mapping[str, Mapping[str, Any]],
        qrels: Mapping[str, int],
        official_documents: Mapping[str, Mapping[str, Any]],
        beir_document_ids: set[str],
    ) -> GenerationEvaluationCase:
        if query_id not in beir_queries:
            raise ValueError(f"official claim {query_id} is missing from BEIR queries")
        claim_text = claim.get("claim")
        beir_query = beir_queries[query_id]
        if not isinstance(claim_text, str) or claim_text != beir_query.get("text"):
            raise ValueError(f"official claim {query_id} does not match the BEIR query text")
        evidence = claim.get("evidence")
        if not isinstance(evidence, dict):
            raise TypeError(f"official claim {query_id} evidence must be an object")
        if evidence != (beir_query.get("metadata") or {}):
            raise ValueError(f"official claim {query_id} evidence does not match BEIR metadata")
        raw_cited = claim.get("cited_doc_ids")
        if not isinstance(raw_cited, list) or not raw_cited:
            raise ValueError(f"official claim {query_id} cited_doc_ids must be a non-empty array")
        cited = tuple(str(doc_id) for doc_id in raw_cited)
        cited_set = set(cited)
        if cited_set != set(qrels):
            raise ValueError(f"official claim {query_id} cited documents do not match BEIR qrels")
        missing_official = set(cited).difference(official_documents)
        missing_beir = set(cited).difference(beir_document_ids)
        if missing_official or missing_beir:
            raise ValueError(f"official claim {query_id} cites a missing corpus document")

        rationales: list[GoldRationale] = []
        labels: set[ScientificStance] = set()
        for doc_id, raw_rationales in evidence.items():
            if doc_id not in cited_set:
                raise ValueError(f"claim {query_id} evidence document {doc_id} is not cited")
            if not isinstance(raw_rationales, list) or not raw_rationales:
                raise ValueError(
                    f"claim {query_id} evidence for {doc_id} must be a non-empty array"
                )
            abstract = official_documents[doc_id].get("abstract")
            if not isinstance(abstract, list) or not all(
                isinstance(sentence, str) and sentence.strip() for sentence in abstract
            ):
                raise ValueError(f"official document {doc_id} has an invalid abstract")
            for raw_rationale in raw_rationales:
                if not isinstance(raw_rationale, dict):
                    raise TypeError(f"claim {query_id} rationale for {doc_id} must be an object")
                try:
                    label = ScientificStance(raw_rationale.get("label"))
                except ValueError as exc:
                    raise ValueError(
                        f"claim {query_id} rationale for {doc_id} has an invalid label"
                    ) from exc
                raw_indices = raw_rationale.get("sentences")
                if not isinstance(raw_indices, list) or not raw_indices:
                    raise ValueError(
                        f"claim {query_id} rationale for {doc_id} needs sentence indices"
                    )
                if any(
                    isinstance(index, bool)
                    or not isinstance(index, int)
                    or index < 0
                    or index >= len(abstract)
                    for index in raw_indices
                ):
                    raise ValueError(
                        f"claim {query_id} rationale sentence is outside document {doc_id}"
                    )
                indices = tuple(raw_indices)
                labels.add(label)
                rationales.append(
                    GoldRationale(
                        doc_id=doc_id,
                        label=label,
                        sentence_indices=indices,
                        sentences=tuple(abstract[index] for index in indices),
                    )
                )
        if len(labels) > 1:
            raise ValueError(f"official claim {query_id} has conflicting evidence labels")
        expected_stance = next(iter(labels), ScientificStance.NOT_ENOUGH_INFO)
        return GenerationEvaluationCase(
            schema_version="generation-evaluation-case/v1",
            query_id=query_id,
            claim=claim_text,
            source_split=self._beir.split.value,
            expected_stance=expected_stance,
            cited_document_ids=cited,
            rationales=tuple(rationales),
        )


def _qrels_file(split: QrelsSplit) -> str:
    return "test.tsv" if split is QrelsSplit.TEST else "train.tsv"


def _query_in_split(query_id: str, split: QrelsSplit) -> bool:
    if split is QrelsSplit.TEST:
        return True
    bucket = int(hashlib.sha256(query_id.encode()).hexdigest(), 16) % _SPLIT_BUCKETS
    in_validation = bucket == _VALIDATION_BUCKET
    return in_validation if split is QrelsSplit.TRAIN_VALIDATION else not in_validation


def _records_by_id(
    path: Path,
    id_field: str,
    description: str,
) -> dict[str, Mapping[str, Any]]:
    records: dict[str, Mapping[str, Any]] = {}
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{description} line {line_number} is invalid JSON") from exc
            if not isinstance(raw, dict) or id_field not in raw:
                raise ValueError(f"{description} line {line_number} has no {id_field}")
            record_id = str(raw[id_field])
            if record_id in records:
                raise ValueError(f"{description} contains duplicate ID {record_id}")
            records[record_id] = raw
    return records


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_verified(archive: Path, destination: Path) -> None:
    resolved_destination = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(resolved_destination):
                raise ValueError(f"SciFact archive contains an unsafe path: {member.filename}")
        bundle.extractall(destination)
