from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import zipfile
from collections.abc import Iterable, Mapping
from enum import StrEnum
from pathlib import Path

from ..domain import EvidenceDocument

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


def _qrels_file(split: QrelsSplit) -> str:
    return "test.tsv" if split is QrelsSplit.TEST else "train.tsv"


def _query_in_split(query_id: str, split: QrelsSplit) -> bool:
    if split is QrelsSplit.TEST:
        return True
    bucket = int(hashlib.sha256(query_id.encode()).hexdigest(), 16) % _SPLIT_BUCKETS
    in_validation = bucket == _VALIDATION_BUCKET
    return in_validation if split is QrelsSplit.TRAIN_VALIDATION else not in_validation


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
