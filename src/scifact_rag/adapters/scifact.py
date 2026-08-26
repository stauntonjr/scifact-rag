from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import zipfile
from collections.abc import Iterable, Mapping
from pathlib import Path

from ..domain import EvidenceDocument

_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
_MD5 = "5f7d1de60b170fc8027bb7898e2efca1"


class BeirSciFact:
    def __init__(self, root: Path) -> None:
        self.root = root
        for relative in ("corpus.jsonl", "queries.jsonl", "qrels/test.tsv"):
            if not (root / relative).is_file():
                raise FileNotFoundError(f"SciFact dataset is missing {relative}")

    @classmethod
    def ensure(cls, data_dir: Path) -> BeirSciFact:
        root = data_dir / "scifact"
        if (root / "corpus.jsonl").is_file():
            return cls(root)
        data_dir.mkdir(parents=True, exist_ok=True)
        archive = data_dir / "scifact.zip"
        with urllib.request.urlopen(_URL, timeout=60) as response, archive.open("wb") as target:
            shutil.copyfileobj(response, target)
        if _md5(archive) != _MD5:
            archive.unlink()
            raise ValueError("SciFact archive checksum mismatch")
        _extract_verified(archive, data_dir)
        return cls(root)

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
        with (self.root / "qrels/test.tsv").open(encoding="utf-8") as source:
            next(source)
            for line in source:
                query_id, doc_id, score = line.rstrip("\n").split("\t")
                result.setdefault(query_id, {})[doc_id] = int(score)
        return result


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
