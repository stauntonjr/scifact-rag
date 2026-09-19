#!/usr/bin/env python3
"""Fail-closed input binding for the retained evidence-selection audit."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

PREPARATION_SHA256 = "888834d7ff034b391f6d90edb9cc819f88e8265823fdf25579f35fce6c88fc20"
RUNTIME_SHA256 = "891d04c4be3175c803fd1308f1eb24cc6c56c386885d25851752dbac4ce2db9d"
LEDGER_SHA256 = "e5f629cd330609a436df7959a115508252b6e510166eb1a81d23c5c4862cd9e2"


class AuditError(ValueError):
    """The retained input tree cannot support a reproducible audit."""


@dataclass(frozen=True, slots=True)
class AuditInputs:
    root: Path
    prepared: Path
    run: Path
    ledger: Path
    evaluation: Path
    public_results: Path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind_inputs(root: Path, public_results: Path) -> AuditInputs:
    """Bind the exact, locally retained reader inputs without modifying them."""
    if not root.is_dir() or os.access(root, os.W_OK):
        raise AuditError("reader artifact root must be an existing read-only directory")
    prepared = root / "prepared-002"
    run = root / "live-20260919-001"
    ledger = run / "ledger.jsonl"
    evaluation = root / "evaluation-20260919-001" / "report.json"
    required = (prepared / "manifest.json", run / "runtime.json", ledger, evaluation, public_results)
    missing = next((path for path in required if not path.is_file()), None)
    if missing is not None:
        raise AuditError(f"missing required retained path: {missing.relative_to(root)}")
    if sha256_file(prepared / "manifest.json") != PREPARATION_SHA256:
        raise AuditError("preparation manifest SHA-256 mismatch")
    if sha256_file(run / "runtime.json") != RUNTIME_SHA256:
        raise AuditError("runtime SHA-256 mismatch")
    if sha256_file(ledger) != LEDGER_SHA256:
        raise AuditError("ledger SHA-256 mismatch")
    return AuditInputs(root, prepared, run, ledger, evaluation, public_results)
