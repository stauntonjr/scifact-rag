"""Offline preparation and fail-closed runtime admission for review workflow v2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scifact_rag.generation_review_workflow import (
    Campaign,
    CodexTransport,
    WorkflowStop,
    freeze,
    prepare_manifest,
    qualify_runtime,
    report,
    run,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "freeze"):
        command = sub.add_parser(name)
        command.add_argument(
            "--input",
            type=Path,
            required=True,
            help="JSON object with prepare_manifest keyword fields",
        )
        command.add_argument("--output", type=Path, required=True)
    command = sub.add_parser("campaign-init")
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--prior-probe", type=Path, action="append", default=[])
    command = sub.add_parser("qualify-runtime")
    command.add_argument("--discovery", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    for name in ("rehearse", "run-development"):
        command = sub.add_parser(name)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--campaign", type=Path, required=True)
        command.add_argument("--runtime-profile", required=True)
    command = sub.add_parser("report")
    command.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in ("prepare", "freeze"):
            manifest = prepare_manifest(**json.loads(args.input.read_text()))
            freeze(args.output, manifest)
            result = {"status": "frozen", "mode": manifest["mode"]}
        elif args.command == "campaign-init":
            result = Campaign.create(args.output, args.prior_probe).accounting()
        elif args.command == "qualify-runtime":
            result = qualify_runtime(args.output, json.loads(args.discovery.read_text()))
        elif args.command == "report":
            result = report(args.run)
        else:
            manifest = json.loads(args.manifest.read_text())
            expected_mode = "fictional" if args.command == "rehearse" else "development"
            if manifest["mode"] != expected_mode:
                raise WorkflowStop("command_manifest_mode_mismatch")
            transport = CodexTransport(args.runtime_profile, Campaign(args.campaign))
            result = run(args.output, manifest, transport)
        print(json.dumps(result, sort_keys=True))
        return 2 if result.get("status") == "runtime_stopped" else 0
    except (WorkflowStop, OSError, ValueError, KeyError, TypeError) as exc:
        print(
            json.dumps(
                {
                    "status": "stopped",
                    "error_type": type(exc).__name__,
                    "code": str(exc) if isinstance(exc, WorkflowStop) else "invalid_input",
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
