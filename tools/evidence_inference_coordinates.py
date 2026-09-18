"""Frozen training-only coordinate qualification; source bytes are never rewritten."""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

from evidence_inference_admission import LABELS, digest, select_articles, validate_members

SELECTED_IDS_SHA256 = "8aee2a757b3e914036c9750b14d3870c4ceb174a389cd5b480d280d80f7d5021"
ARCHIVE_SHA256 = "6abe0d4ec0d331834981c0171c3c79d47515761867f82f1dc6066e43863a1586"


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def canonical_view(data: bytes) -> dict:
    raw = data.decode("utf-8")
    text, chars, byte_offsets = [], [0], [0]
    i = byte_index = 0
    while i < len(raw):
        width = 2 if raw[i : i + 2] == "\r\n" else 1
        chunk = raw[i : i + width]
        text.append("\n" if chunk in ("\r", "\r\n") else chunk)
        i += width
        byte_index += len(chunk.encode("utf-8"))
        chars.append(i)
        byte_offsets.append(byte_index)
    return {
        "text": "".join(text),
        "raw": raw,
        "bytes": data,
        "raw_character_boundaries": chars,
        "raw_byte_boundaries": byte_offsets,
    }


def qualify(view: dict, evidence: str, start: str, end: str) -> dict:
    if not all(re.fullmatch(r"-?\d+", value, flags=re.ASCII) for value in (start, end)):
        return {"status": "invalid_offset"}
    a, b = int(start), int(end)
    if a == b == -1:
        return {"status": "publisher_unavailable"}
    if not 0 <= a <= b <= len(view["text"]):
        return {"status": "out_of_bounds"}
    if a == b:
        return {"status": "empty_span"}
    if not evidence:
        return {"status": "empty_evidence"}
    c, d = (view["raw_character_boundaries"][i] for i in (a, b))
    u, v = (view["raw_byte_boundaries"][i] for i in (a, b))
    segment = view["text"][a:b]
    roundtrip = normalize(view["bytes"][u:v].decode("utf-8"))
    result = {
        "status": "mismatch",
        "canonical_span": [a, b],
        "raw_character_span": [c, d],
        "raw_byte_span": [u, v],
        "canonical_segment_sha256": digest(segment.encode()),
        "raw_segment_sha256": digest(view["bytes"][u:v]),
    }
    if roundtrip != segment or view["bytes"][u:v].decode("utf-8") != view["raw"][c:d]:
        result["status"] = "roundtrip_failure"
    elif segment == evidence:
        result["status"] = "exact_mapped"
    else:
        positions = [m.start() for m in re.finditer(f"(?={re.escape(evidence)})", view["text"])]
        decoded = html.unescape(evidence)
        decoded_positions = (
            [m.start() for m in re.finditer(f"(?={re.escape(decoded)})", view["text"])]
            if decoded
            else []
        )
        diagnostic = {
            "whitespace_collapsed_equal": segment.split() == evidence.split(),
            "html_unescaped_equal": segment == decoded,
            "html_unescaped_whitespace_equal": segment.split() == decoded.split(),
            "evidence_contains_html_entity": decoded != evidence,
            "html_unescaped_occurrence_shifts": [p - a for p in decoded_positions],
            "evidence_contains_delimiter": "\\n" in evidence or "\\t" in evidence,
            "evidence_length": len(evidence),
            "span_length": b - a,
            "exact_occurrences_elsewhere": len(positions),
            "exact_occurrence_shifts": [p - a for p in positions],
        }
        result["diagnostics"] = diagnostic
        result["residual_category"] = (
            "whitespace_only_at_supplied_span"
            if diagnostic["whitespace_collapsed_equal"]
            else "html_entity_at_supplied_span"
            if diagnostic["html_unescaped_equal"]
            else "html_entity_and_whitespace_at_supplied_span"
            if diagnostic["html_unescaped_whitespace_equal"]
            else "exact_text_elsewhere_nonmatching_coordinates"
            if positions
            else "html_entity_text_elsewhere_nonmatching_coordinates"
            if decoded != evidence and decoded_positions
            else "unexplained_nonmatching_text_or_coordinates"
        )
    return result


def validate_selection(selected: list[str], splits: dict) -> None:
    if len(selected) != 64 or selected != select_articles(splits["train"]):
        raise ValueError("Frozen ordered 64-article selection differs")
    sets = [set(splits[s]) for s in ("train", "validation", "test")]
    if any(len(splits[s]) != len(set(splits[s])) for s in splits):
        raise ValueError("Duplicate split ID")
    if any(sets[i] & sets[j] for i, j in ((0, 1), (0, 2), (1, 2))):
        raise ValueError("Overlapping splits")


def audit(archive: Path, selected_path: Path) -> tuple[dict, dict]:
    archive_hash = digest(archive.read_bytes())
    if archive_hash != ARCHIVE_SHA256:
        raise ValueError("Frozen archive digest mismatch")
    selected_bytes = selected_path.read_bytes()
    if digest(selected_bytes) != SELECTED_IDS_SHA256:
        raise ValueError("Frozen selection file digest mismatch")
    selected = json.loads(selected_bytes)
    with tarfile.open(archive, "r:gz") as tar:
        validate_members(tar.getmembers())

        def read(name):
            handle = tar.extractfile(name)
            if handle is None:
                raise ValueError("Missing regular member")
            return handle.read()

        splits = {
            s: read(f"splits/{s}_article_ids.txt").decode().splitlines()
            for s in ("train", "validation", "test")
        }
        validate_selection(selected, splits)
        selected_set = set(selected)
        views = {a: canonical_view(read(f"txt_files/PMC{a}.txt")) for a in selected}

        def rows(name):
            return csv.DictReader(io.StringIO(read(name).decode("utf-8"), newline=""))

        prompts = {}
        for row in rows("prompts_merged.csv"):
            if row["PMCID"] in selected_set:
                if row["PromptID"] in prompts:
                    raise ValueError("Ambiguous duplicate selected prompt")
                prompts[row["PromptID"]] = row
        flagged = set()
        for section in re.split(
            r"### (?:Incorrect|Questionable|Somewhat malformed):",
            read("README.md").decode("utf-8-sig"),
        )[1:]:
            flagged.update(re.findall(r"\b\d+\b", section.split("###")[0]))
        retained, by_prompt, eligible_rows = [], defaultdict(list), defaultdict(list)
        failures, statuses, residuals = Counter(), Counter(), Counter()
        for index, row in enumerate(rows("annotations_merged.csv")):
            if row["PMCID"] not in selected_set:
                continue
            prompt = row["PromptID"]
            by_prompt[prompt].append(row)
            result = qualify(
                views[row["PMCID"]], row["Annotations"], row["Evidence Start"], row["Evidence End"]
            )
            statuses[result["status"]] += 1
            if "residual_category" in result:
                residuals[result["residual_category"]] += 1
            problems = []
            if row["Label Code"] not in LABELS:
                problems.append("non_native_label_code")
            elif LABELS[row["Label Code"]] != row["Label"]:
                problems.append("undocumented_label_text")
            for field in ("Valid Label", "Valid Reasoning"):
                if row[field] != "True":
                    problems.append(field.lower().replace(" ", "_") + "_not_true")
            if prompt not in prompts or prompts[prompt]["PMCID"] != row["PMCID"]:
                problems.append("prompt_article_mismatch")
            if prompt in flagged:
                problems.append("publisher_flagged_prompt")
            if result["status"] != "exact_mapped":
                problems.append("non_exact_span")
            failures.update(problems)
            if not problems:
                eligible_rows[prompt].append(index)
            retained.append(
                {
                    "csv_data_row_zero_based": index,
                    "article_id": row["PMCID"],
                    "prompt_id": prompt,
                    "user_id": row["UserID"],
                    "source_offsets": [row["Evidence Start"], row["Evidence End"]],
                    "annotation_row_sha256": digest(json.dumps(row, sort_keys=True).encode()),
                    "evidence_sha256": digest(row["Annotations"].encode()),
                    "problems": problems,
                    **result,
                }
            )
        disputed = {
            p
            for p, rs in by_prompt.items()
            if len(
                {
                    r["Label Code"]
                    for r in rs
                    if r["Valid Label"] == "True" and r["Label Code"] in LABELS
                }
            )
            > 1
        }
        eligible = sorted(
            p
            for p in eligible_rows
            if p not in disputed
            and all(prompts[p][k].strip() for k in ("Outcome", "Intervention", "Comparator"))
        )
        summary = {
            "schema_version": 1,
            "archive_sha256": archive_hash,
            "selected_ids_file_sha256": digest(selected_bytes),
            "tool_sha256": digest(Path(__file__).read_bytes()),
            "decision": "coordinate_subset_qualified_not_admitted_pending_provenance",
            "scope": {
                "selected_training_articles": len(selected),
                "prompts": len(prompts),
                "annotation_rows": len(retained),
                "heldout_text_decoded": False,
                "heldout_outcomes_inspected": False,
                "model_calls": 0,
                "csv_access": "merged CSV traversed; nonselected rows discarded on PMCID",
            },
            "span_counts": dict(statuses),
            "residual_categories": dict(residuals),
            "residual_classification": "Exclusive first match: whitespace equality, HTML entity equality, combined HTML/whitespace equality at supplied span, unchanged evidence elsewhere, HTML-decoded evidence elsewhere, unexplained. Per-row diagnostic flags may overlap; all residuals rejected.",
            "row_failure_counts_nonexclusive": dict(failures),
            "prompts_with_verified_label_disagreement": len(disputed),
            "eligible_prompts_before_license": len(eligible),
            "eligible_articles_before_license": len({prompts[p]["PMCID"] for p in eligible}),
            "eligible_rows_in_eligible_prompts_before_license": sum(
                len(eligible_rows[p]) for p in eligible
            ),
            "coordinate_policy": "Strict UTF-8 decode; CRLF and lone CR to LF; half-open character spans; exact unchanged evidence; unique canonical boundary mapping to original characters and UTF-8 bytes; mapped raw bytes must roundtrip through same newline transformation. No heuristic repairs admitted.",
            "inclusion_policy": "Original label, verification, ICO, publisher caveat and disagreement rules unchanged; exact_mapped replaces inclusive raw span only. Rights remain unresolved; Step 2 inactive.",
            "limitations": [
                "Frozen development subset only; not a corpus-wide estimate.",
                "Mapping is conditional on exact equality, not proof of a universal publisher offset convention.",
                "Residual diagnostic equality and shifted occurrences are not repairs or causal proof.",
                "Normalization alone is lossy; retained original bytes and boundary maps preserve source recovery.",
            ],
        }
        manifest = {
            "summary": summary,
            "selected_train_ids": selected,
            "eligible_prompt_ids_before_license": eligible,
            "rows": retained,
            "articles": {
                a: {
                    "source_sha256": digest(v["bytes"]),
                    "canonical_sha256": digest(v["text"].encode()),
                    "raw_character_boundaries": v["raw_character_boundaries"],
                    "raw_byte_boundaries": v["raw_byte_boundaries"],
                }
                for a, v in views.items()
            },
        }
        return summary, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--selected-ids", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    summary, manifest = audit(args.archive, args.selected_ids)
    for path, value in ((args.summary, summary), (args.manifest, manifest)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
