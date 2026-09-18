"""Bounded, model-free audit of the publisher's Evidence Inference 2.0 archive.

Never extracts archive paths. Only selected training records are semantically
inspected; other rows are used solely for article/prompt membership counts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

SOURCE_URL = "https://evidence-inference.ebm-nlp.com/v2.0.tar.gz"
LABELS = {
    "-1": "significantly decreased",
    "0": "no significant difference",
    "1": "significantly increased",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def select_articles(ids: list[str]) -> list[str]:
    return sorted(set(ids), key=lambda x: (digest(f"ei-admission-v1:{x}".encode()), x))[:64]


def validate_members(members: list[tarfile.TarInfo]) -> None:
    names = set()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or "\\" in member.name:
            raise ValueError("Unsafe archive path")
        if member.name in names or not (member.isfile() or member.isdir()):
            raise ValueError("Duplicate or non-regular archive entry")
        if member.size > 100_000_000:
            raise ValueError("Oversized archive entry")
        names.add(member.name)
    if sum(m.size for m in members) > 1_000_000_000:
        raise ValueError("Oversized expanded archive")


def span_status(text: str, evidence: str, start: str, end: str) -> str:
    try:
        a, b = int(start), int(end)
    except ValueError:
        return "invalid_offset"
    if a == b == -1:
        return "publisher_unavailable"
    if not (0 <= a <= b < len(text)):
        return "out_of_bounds"
    if not evidence:
        return "empty_evidence"
    return "exact" if text[a : b + 1] == evidence else "mismatch"


def distribution(values: list[int]) -> dict:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0}
    return {
        "count": len(values),
        "min": ordered[0],
        "median": (ordered[(len(values) - 1) // 2] + ordered[len(values) // 2]) / 2,
        "max": ordered[-1],
        "total": sum(values),
    }


def audit(archive: Path) -> tuple[dict, dict]:
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        validate_members(members)

        def read(name: str) -> bytes:
            handle = tar.extractfile(name)
            if handle is None:
                raise ValueError("Expected regular file")
            return handle.read()

        def rows(name: str):
            return csv.DictReader(io.StringIO(read(name).decode("utf-8"), newline=""))

        hashes = {
            m.name: {"bytes": m.size, "sha256": digest(read(m.name))} for m in members if m.isfile()
        }
        splits = {
            s: read(f"splits/{s}_article_ids.txt").decode().splitlines()
            for s in ("train", "validation", "test")
        }
        split_sets = {s: set(ids) for s, ids in splits.items()}
        overlaps = {
            f"{a}/{b}": len(split_sets[a] & split_sets[b])
            for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))
        }
        if any(overlaps.values()):
            raise ValueError("Split overlap: refuse training content inspection")
        selected = select_articles(splits["train"])
        selected_set = set(selected)
        texts = {x: read(f"txt_files/PMC{x}.txt").decode("utf-8") for x in selected}
        prompts = {}
        article_prompts = defaultdict(list)
        all_prompt_ids = Counter()
        prompt_articles = set()
        prompt_counts = Counter()
        unassigned = 0
        for row in rows("prompts_merged.csv"):
            article, prompt = row["PMCID"], row["PromptID"]
            all_prompt_ids[prompt] += 1
            prompt_articles.add(article)
            assigned = [s for s, ids in split_sets.items() if article in ids]
            if not assigned:
                unassigned += 1
            for s in assigned:
                prompt_counts[s] += 1
            if article in selected_set:
                prompts[prompt] = row
                article_prompts[article].append(row)
        annotations = []
        annotation_counts = Counter()
        annotation_identity_failures = Counter()
        for row in rows("annotations_merged.csv"):
            article = row["PMCID"]
            assigned = [s for s, ids in split_sets.items() if article in ids]
            for s in assigned:
                annotation_counts[s] += 1
            if not assigned:
                annotation_identity_failures["article_outside_splits"] += 1
            if row["PromptID"] not in all_prompt_ids:
                annotation_identity_failures["unknown_prompt_id"] += 1
            if article in selected_set:
                annotations.append(row)
        readme = read("README.md").decode("utf-8-sig")
        flagged = set()
        for section in re.split(r"### (?:Incorrect|Questionable|Somewhat malformed):", readme)[1:]:
            flagged.update(re.findall(r"\b\d+\b", section.split("###")[0]))
        spans, label_texts, label_codes, flags, label_pairs = (
            Counter(),
            Counter(),
            Counter(),
            Counter(),
            Counter(),
        )
        diagnostic = Counter(
            documents_containing_CRLF=sum("\r\n" in text for text in texts.values())
        )
        by_prompt = defaultdict(list)
        eligible_rows = defaultdict(list)
        row_issues = Counter()
        for row in annotations:
            prompt = row["PromptID"]
            by_prompt[prompt].append(row)
            label_texts[row["Label"]] += 1
            label_codes[row["Label Code"]] += 1
            label_pairs[(row["Label Code"], row["Label"])] += 1
            status = span_status(
                texts[row["PMCID"]], row["Annotations"], row["Evidence Start"], row["Evidence End"]
            )
            spans[status] += 1
            a, b = (
                (-1, -1)
                if status == "invalid_offset"
                else (int(row["Evidence Start"]), int(row["Evidence End"]))
            )
            if a >= 0 and b >= a:
                raw = texts[row["PMCID"]]
                universal = raw.replace("\r\n", "\n").replace("\r", "\n")
                for mode, value in (("raw", raw), ("universal_newline", universal)):
                    diagnostic[mode + "_inclusive_exact"] += value[a : b + 1] == row["Annotations"]
                    diagnostic[mode + "_exclusive_exact"] += value[a:b] == row["Annotations"]
            for field in ("Valid Label", "Valid Reasoning", "In Abstract"):
                flags[f"{field}={row[field]}"] += 1
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
            if status != "exact":
                problems.append("non_exact_span")
            row_issues.update(problems)
            if not problems:
                eligible_rows[prompt].append(row)
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
        text_ids = {
            m.name.removeprefix("txt_files/PMC").removesuffix(".txt")
            for m in members
            if re.fullmatch(r"txt_files/PMC\d+\.txt", m.name)
        }
        roles = {
            k: distribution([len({p[k] for p in article_prompts.get(a, [])}) for a in selected])
            for k in ("Outcome", "Intervention", "Comparator")
        }
        summary = {
            "schema_version": 1,
            "source_url": SOURCE_URL,
            "archive_sha256": digest(archive.read_bytes()),
            "decision": (
                "not_admitted_grounding_contract_failure_and_unresolved_provenance"
                if not eligible
                else "not_admitted_pending_provenance"
            ),
            "model_calls": 0,
            "scope": {
                "selection": "lowest SHA256 of UTF-8 ei-admission-v1:<native numeric PMCID>",
                "article_limit": 64,
                "selected_articles": len(selected),
                "heldout_outcomes_inspected": False,
                "heldout_text_decoded": False,
                "all_file_hashing": True,
                "csv_access": "merged CSV parsed; nonselected records discarded after identity and membership counts; no nonselected outcomes aggregated or displayed",
            },
            "inventory": {
                "archive_members": len(members),
                "regular_files": len(hashes),
                "article_texts": len(text_ids),
                "prompt_bearing_articles": len(prompt_articles),
                "text_articles_without_prompts": len(text_ids - prompt_articles),
                "prompt_articles_missing_text": len(prompt_articles - text_ids),
                "embedded_license_files": [
                    n
                    for n in hashes
                    if re.search(r"license|copyright|provenance", n, re.IGNORECASE)
                ],
                "xml_files": sum(n.endswith((".xml", ".nxml")) for n in hashes),
            },
            "partitions": {
                "article_ids": {s: len(x) for s, x in splits.items()},
                "duplicate_ids": {s: len(x) - len(set(x)) for s, x in splits.items()},
                "overlap_counts": overlaps,
                "prompt_rows": dict(prompt_counts),
                "annotation_rows": dict(annotation_counts),
                "prompt_rows_outside_splits": unassigned,
                "duplicate_prompt_ids": sum(v - 1 for v in all_prompt_ids.values()),
                "annotation_identity_failures": dict(annotation_identity_failures),
            },
            "train_sample": {
                "prompt_rows": len(prompts),
                "annotation_rows": len(annotations),
                "articles_with_prompts": len(article_prompts),
                "articles_without_prompts": len(selected_set - set(article_prompts)),
                "label_text_counts": dict(label_texts),
                "label_code_counts": dict(label_codes),
                "label_pairs": [
                    {"code": c, "text": t, "count": n} for (c, t), n in sorted(label_pairs.items())
                ],
                "verification_flags": dict(flags),
                "span_counts": dict(spans),
                "unapproved_offset_diagnostics_not_inclusion": dict(diagnostic),
                "row_failure_counts_nonexclusive": dict(row_issues),
                "prompts_with_verified_label_disagreement": len(disputed),
                "prompts_without_annotations": len(set(prompts) - set(by_prompt)),
                "repeated_doctor_prompt_rows": sum(
                    v - 1
                    for v in Counter((r["UserID"], r["PromptID"]) for r in annotations).values()
                ),
                "eligible_prompts_before_license": len(eligible),
                "eligible_articles_before_license": len({prompts[p]["PMCID"] for p in eligible}),
                "article_character_lengths": distribution([len(t) for t in texts.values()]),
                "article_whitespace_word_lengths": distribution(
                    [len(t.split()) for t in texts.values()]
                ),
                "evidence_character_lengths": distribution(
                    [len(r["Annotations"]) for r in annotations]
                ),
                "prompts_per_article": distribution(
                    [len(article_prompts.get(a, [])) for a in selected]
                ),
                "distinct_roles_per_article": roles,
                "missing_role_fields": sum(
                    not p[k].strip()
                    for p in prompts.values()
                    for k in ("Outcome", "Intervention", "Comparator")
                ),
            },
            "offset_policy": "Release README specifies inclusive start/end; compare unchanged UTF-8 text[start:end+1] to unchanged Annotations. No normalization, search, fuzzy repair or delimiter splitting.",
            "inclusion_policy": "Training only; nonempty ICO; documented label text/code; both native verification flags True; exact inclusive span; exclude all README caveat categories and any verified-label-disputed prompt. At least one eligible native row required, without inventing majority labels. License remains separate prerequisite.",
            "limitations": [
                "Sample counts are development evidence only, not corpus-wide quality estimates.",
                "Supplied ICO roles do not establish role induction or population supervision.",
                "Archive README documents v1.1 patches and contains no per-article license metadata.",
                "4454 text articles and actual prompt-bearing article count require reconciliation to publication; text inventory is not annotated-corpus size.",
            ],
        }
        manifest = {
            "source_url": SOURCE_URL,
            "archive_sha256": summary["archive_sha256"],
            "files": hashes,
            "split_ids": splits,
            "selected_train_ids": selected,
            "eligible_train_prompt_ids_before_license": eligible,
            "license_status": "unresolved; see parent admission report",
            "tool_sha256": digest(Path(__file__).read_bytes()),
        }
        return summary, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    summary, manifest = audit(args.archive)
    for path, value in ((args.summary, summary), (args.manifest, manifest)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
