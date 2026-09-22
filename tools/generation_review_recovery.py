"""Complete an owner-authorized assessment from verified physical attempts."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scifact_rag import generation_review_recovery as recovery
from scifact_rag import generation_review_workflow as w


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--runtime-profile", required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--complete-missing-format", action="store_true")
    args = parser.parse_args()
    source = json.loads((args.source[0] / "manifest.json").read_text())
    manifest = w.prepare_manifest(
        source["cases"],
        source["split"],
        source["families"],
        inventory_sha256=source["inventory_sha256"],
        selection_sha256=source["selection_sha256"],
        rubric=source["rubric"],
        mode=source["mode"],
    )
    transport = w.CodexTransport(args.runtime_profile, w.Campaign(args.campaign))
    if args.check_only:
        records, _, _, attempted, failed, duplicates = recovery.retain(manifest, args.source)
        if args.complete_missing_format:
            records, repairs = recovery.fill_missing_quotes(manifest, args.source, records)
            failed -= len(repairs)
        print(
            json.dumps(
                {
                    "retained": len(records),
                    "attempted": attempted,
                    "failed": failed,
                    "duplicates": duplicates,
                    "campaign": transport.campaign.accounting(),
                }
            )
        )
    else:
        result = recovery.run(
            args.output,
            manifest,
            transport,
            args.source,
            complete_missing_format=args.complete_missing_format,
        )
        print(json.dumps(result, sort_keys=True))
        return 0 if result["execution_status"] == "execution_complete" else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
