#!/usr/bin/env python3
"""Prepare and validate bounded development-only generation-review pilot artifacts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from scifact_rag.generation_review_pilot import (
    AgentReviewValidationError,
    build_pilot_selection,
    build_review_v2_worksheet,
    build_source_inventory,
    canonical_json_sha256,
    project_agent_reviews,
    validate_agent_review,
)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AgentReviewValidationError(f"{path} is not valid JSON") from exc


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(value, indent=2, sort_keys=True) + "\n"
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(serialized)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _source_rows(worksheet: object) -> dict[str, dict[str, Any]]:
    if not isinstance(worksheet, dict) or not isinstance(worksheet.get("rows"), list):
        raise AgentReviewValidationError("source worksheet rows must be a list")
    rows = worksheet["rows"]
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("response_id"), str):
            result[row["response_id"]] = row
    if len(result) != len(rows):
        raise AgentReviewValidationError("source worksheet response IDs must be unique")
    return result


def _command_inventory(args: argparse.Namespace) -> dict[str, object]:
    worksheet = _load_json(args.worksheet)
    mapping = _load_json(args.mapping)
    if not isinstance(worksheet, dict) or not isinstance(mapping, dict):
        raise AgentReviewValidationError("worksheet and mapping must be JSON objects")
    inventory = build_source_inventory(
        worksheet,
        mapping,
        args.results.read_bytes(),
        worksheet_sha256=_sha256(args.worksheet),
        mapping_sha256=_sha256(args.mapping),
    )
    _write_json(args.output, inventory)
    return {
        "article_family_groups": len(inventory["article_family_groups"]),
        "output": str(args.output),
        "output_sha256": _sha256(args.output),
        "rows": len(inventory["rows"]),
    }


def _command_worksheet(args: argparse.Namespace) -> dict[str, object]:
    source = _load_json(args.source)
    selection = _load_json(args.selection)
    if not isinstance(source, dict) or not isinstance(selection, dict):
        raise AgentReviewValidationError("source and selection must be JSON objects")
    if args.stage is not None:
        selection = selection.get(args.stage)
        if not isinstance(selection, dict):
            raise AgentReviewValidationError(f"selection.{args.stage} must be an object")
    response_ids = selection.get("response_ids")
    if not isinstance(response_ids, list) or any(
        not isinstance(response_id, str) for response_id in response_ids
    ):
        raise AgentReviewValidationError("selection.response_ids must be a list of strings")
    worksheet = build_review_v2_worksheet(
        source,
        response_ids,
        order_seed=args.order_seed,
    )
    _write_json(args.output, worksheet)
    return {
        "output": str(args.output),
        "output_sha256": _sha256(args.output),
        "rows": len(worksheet["rows"]),
    }


def _command_select(args: argparse.Namespace) -> dict[str, object]:
    inventory = _load_json(args.inventory)
    if not isinstance(inventory, dict):
        raise AgentReviewValidationError("inventory must be a JSON object")
    selection = build_pilot_selection(inventory, args.clarification_group)
    _write_json(args.output, selection)
    return {
        "assessment_rows": len(selection["assessment"]["response_ids"]),
        "clarification_rows": len(selection["clarification"]["response_ids"]),
        "output": str(args.output),
        "output_sha256": _sha256(args.output),
    }


def _command_validate(args: argparse.Namespace) -> dict[str, object]:
    source = _load_json(args.source)
    review = _load_json(args.review)
    source_rows = _source_rows(source)
    if not isinstance(review, dict):
        raise AgentReviewValidationError("agent review must be a JSON object")
    response_id = review.get("response_id")
    if not isinstance(response_id, str):
        raise AgentReviewValidationError("agent review response_id must be text")
    source_row = source_rows.get(response_id)
    if source_row is None:
        raise AgentReviewValidationError("agent review response_id is not in the source")
    validated = validate_agent_review(review, source_row)
    return {
        "agent_review_sha256": canonical_json_sha256(validated),
        "response_id": response_id,
        "role": validated["role"],
        "status": "valid",
    }


def _command_project(args: argparse.Namespace) -> dict[str, object]:
    source = _load_json(args.source)
    reviews = _load_json(args.reviews)
    if not isinstance(source, dict) or not isinstance(reviews, list):
        raise AgentReviewValidationError("source must be an object and reviews must be a list")
    worksheet, adequacy = project_agent_reviews(source, reviews, role=args.role)
    _write_json(args.review_output, worksheet)
    _write_json(args.adequacy_output, adequacy)
    return {
        "adequacy_output_sha256": _sha256(args.adequacy_output),
        "review_output_sha256": _sha256(args.review_output),
        "role": args.role,
        "rows": len(reviews),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="Reconcile retained exposed evidence")
    inventory.add_argument("--worksheet", type=Path, required=True)
    inventory.add_argument("--mapping", type=Path, required=True)
    inventory.add_argument("--results", type=Path, required=True)
    inventory.add_argument("--output", type=Path, required=True)
    inventory.set_defaults(handler=_command_inventory)

    worksheet = subparsers.add_parser("worksheet", help="Build a frozen label-free worksheet")
    worksheet.add_argument("--source", type=Path, required=True)
    worksheet.add_argument("--selection", type=Path, required=True)
    worksheet.add_argument("--stage", choices=("clarification", "assessment"))
    worksheet.add_argument("--order-seed", required=True)
    worksheet.add_argument("--output", type=Path, required=True)
    worksheet.set_defaults(handler=_command_worksheet)

    select = subparsers.add_parser("select", help="Freeze a group-contained pilot split")
    select.add_argument("--inventory", type=Path, required=True)
    select.add_argument("--clarification-group", action="append", required=True)
    select.add_argument("--output", type=Path, required=True)
    select.set_defaults(handler=_command_select)

    validate = subparsers.add_parser("validate", help="Validate one source-bound agent review")
    validate.add_argument("--source", type=Path, required=True)
    validate.add_argument("--review", type=Path, required=True)
    validate.set_defaults(handler=_command_validate)

    project = subparsers.add_parser("project", help="Project envelopes into review-v2 artifacts")
    project.add_argument("--source", type=Path, required=True)
    project.add_argument("--reviews", type=Path, required=True)
    project.add_argument("--role", choices=("r1", "r2", "adjudicator"), required=True)
    project.add_argument("--review-output", type=Path, required=True)
    project.add_argument("--adequacy-output", type=Path, required=True)
    project.set_defaults(handler=_command_project)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = args.handler(args)
    except (AgentReviewValidationError, OSError, ValueError) as exc:
        print(f"generation review pilot: failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
