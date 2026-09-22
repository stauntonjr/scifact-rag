"""Prepare or explicitly execute the bounded local scientific-review diagnostic."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scifact_rag import local_review_diagnostic as diagnostic


def _write(path: Path, value: object) -> None:
    if path.exists():
        raise diagnostic.DiagnosticStop("refusing_to_overwrite_existing_artifact")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def prepare(args: argparse.Namespace) -> int:
    fixture = diagnostic.example_fixture()
    _write(args.fixture, fixture)
    loaded = diagnostic.load_fixture(args.fixture)
    print(
        json.dumps({"case_count": len(loaded["cases"]), "fixture_sha256": loaded["fixture_sha256"]})
    )
    return 0


def capture_preflight(args: argparse.Namespace) -> int:
    import httpx

    services = []
    for endpoint in args.endpoint:
        url = endpoint.rstrip("/") + "/v1/models"
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        services.append(
            {"endpoint": endpoint.rstrip("/"), "models": response.json().get("data", [])}
        )
    _write(args.output, {"captured_at": diagnostic._now(), "services": services})
    print(json.dumps({"service_count": len(services), "output": str(args.output)}))
    return 0


def execute(args: argparse.Namespace) -> int:
    if not args.execute:
        raise diagnostic.DiagnosticStop("live_execution_requires_explicit_execute")
    fixture = diagnostic.load_fixture(args.fixture)
    if not args.preflight.is_file():
        raise diagnostic.DiagnosticStop("missing_preflight")
    preflight = json.loads(args.preflight.read_text())
    rubric = args.rubric.read_text()
    transport = diagnostic.OpenAIHTTPTransport(args.endpoint, args.model)
    result = diagnostic.run(args.output, fixture, transport, preflight, rubric=rubric)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["execution_status"] == "execution_complete" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--fixture", type=Path, required=True)
    prepare_parser.set_defaults(handler=prepare)
    preflight_parser = commands.add_parser("preflight")
    preflight_parser.add_argument("--endpoint", action="append", required=True)
    preflight_parser.add_argument("--output", type=Path, required=True)
    preflight_parser.set_defaults(handler=capture_preflight)
    execute_parser = commands.add_parser("execute")
    execute_parser.add_argument("--fixture", type=Path, required=True)
    execute_parser.add_argument("--preflight", type=Path, required=True)
    execute_parser.add_argument("--rubric", type=Path, required=True)
    execute_parser.add_argument("--endpoint", required=True)
    execute_parser.add_argument("--model", required=True)
    execute_parser.add_argument("--output", type=Path, required=True)
    execute_parser.add_argument("--execute", action="store_true")
    execute_parser.set_defaults(handler=execute)
    args = parser.parse_args()
    try:
        return args.handler(args)
    except diagnostic.DiagnosticStop as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
