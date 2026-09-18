"""Offline article rights/source audit of the frozen coordinate-qualified subset.

The article-meta license travels with the pinned XML; repository MIT terms are
not substituted for article rights. Publisher-declared XML/TXT pairing is not
proof of an exact historical PMC version or a reproduced extraction pipeline.
"""

from __future__ import annotations

import argparse
import json
import re
import tarfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from evidence_inference_admission import digest, validate_members
from evidence_inference_coordinates import ARCHIVE_SHA256, normalize

REVISION = "a661e8c14f973398380c8865cf2f27a535aaaf6d"
COORDINATE_MANIFEST_SHA256 = "0565254b5faff2bd0b6fad630f800a85cb37939c7f93b3baf5cb8f389d2a4ced"
CANDIDATE_IDS_SHA256 = "3daf9898086bf5107d85a52f60e033655bb161a0a7e43134acc5d678c6cff8e9"
CC_URL = re.compile(
    r"https?://(?:www\.)?creativecommons\.org/"
    r"(?:licenses/(by(?:-nc)?(?:-sa|-nd)?)/(1\.0|2\.0|2\.5|3\.0|4\.0)"
    r"|publicdomain/(zero)/(1\.0))/?(?=$|[\s\"'<>),;]|\.(?:$|\s))",
    re.IGNORECASE,
)
XLINK = "{http://www.w3.org/1999/xlink}href"


def compare_text(archive: bytes, pinned: bytes) -> dict:
    return {
        "raw_bytes_equal": archive == pinned,
        "lf_coordinate_text_equal": normalize(archive.decode("utf-8"))
        == normalize(pinned.decode("utf-8")),
    }


def article_metadata(data: bytes, article_id: str) -> dict:
    # These frozen JATS files have public DOCTYPE declarations. ElementTree does
    # not fetch external DTDs; reject internal entity declarations explicitly.
    if b"<!ENTITY" in data.upper():
        raise ValueError("XML entity declarations are outside this bounded audit")
    root = ET.fromstring(data)
    meta = root.find("./front/article-meta")
    if meta is None:
        raise ValueError("Missing article-meta")

    def content(element):
        return " ".join("".join(element.itertext()).split())

    ids = {}
    for element in meta.findall("article-id"):
        ids.setdefault(element.get("pub-id-type", ""), []).append(content(element))
    licenses = []
    found = set()
    data_only_cc0 = False
    for element in meta.findall("./permissions/license"):
        text = content(element)
        hrefs = sorted({e.get(XLINK) for e in element.iter() if e.get(XLINK)})
        data_clause = bool(
            re.search(
                r"The Creative Commons Public Domain Dedication waiver "
                r"\(https?://creativecommons\.org/publicdomain/zero/1\.0/\) "
                r"applies to the data made available in this article, unless otherwise stated\.",
                text,
            )
        )
        data_only_cc0 = data_only_cc0 or data_clause
        for match in CC_URL.finditer(" ".join([text, *hrefs])):
            code, version, zero, zero_version = match.groups()
            if zero and data_clause:
                continue
            found.add((code.lower() if code else zero.lower(), version or zero_version))
        licenses.append({"hrefs": hrefs, "text": text, "attributes": element.attrib})
    if len(found) > 1:
        rights = "unresolved_conflicting_licenses"
    elif not found:
        rights = "unresolved_custom_or_missing"
    else:
        code, _ = next(iter(found))
        rights = (
            "unresolved_no_derivatives"
            if code.endswith("-nd")
            else "noncommercial_research_conditional"
            if "-nc" in code
            else "attribution_research_candidate"
            if code in {"by", "zero"}
            else "unresolved_sharealike"
        )
    pmcids = ids.get("pmc", []) + ids.get("pmcid", [])
    return {
        "pmcid_matches": len(pmcids) == 1 and pmcids[0].removeprefix("PMC") == article_id,
        "article_ids": ids,
        "title": content(meta.find("title-group")) if meta.find("title-group") is not None else "",
        "contributors": [content(e) for e in meta.findall("./contrib-group/contrib")],
        "copyright_statements": [
            content(e) for e in meta.findall("./permissions/copyright-statement")
        ],
        "licenses": licenses,
        "data_only_cc0_clause": data_only_cc0,
        "recognized_cc_licenses": [f"{c}/{v}" for c, v in sorted(found)],
        "rights_class": rights,
        "historical_pmc_version_exactness": "not_established",
        "xml_to_txt_exact_reproduction": "not_established",
    }


def checked_json(path: Path, expected: str) -> dict | list:
    data = path.read_bytes()
    if digest(data) != expected:
        raise ValueError(f"Frozen input digest mismatch: {path.name}")
    return json.loads(data)


def audit(archive: Path, coordinates: Path, source_dir: Path) -> tuple[dict, dict]:
    if digest(archive.read_bytes()) != ARCHIVE_SHA256:
        raise ValueError("Frozen archive digest mismatch")
    coordinate = checked_json(coordinates, COORDINATE_MANIFEST_SHA256)
    candidates = checked_json(source_dir / "candidate-article-ids.json", CANDIDATE_IDS_SHA256)
    eligible = set(coordinate["eligible_prompt_ids_before_license"])
    rows = [r for r in coordinate["rows"] if r["prompt_id"] in eligible and not r["problems"]]
    if {r["article_id"] for r in rows} != set(candidates):
        raise ValueError("Candidate articles do not match frozen coordinate qualification")
    acquisition_bytes = (source_dir / "acquisition-manifest.json").read_bytes()
    acquisition = json.loads(acquisition_bytes)
    if acquisition["revision"] != REVISION:
        raise ValueError("Pinned source revision mismatch")
    records = {}
    for record in acquisition["records"]:
        key = (record["article_id"], record["kind"])
        if key in records:
            raise ValueError("Duplicate acquisition record")
        records[key] = record
    expected_keys = {(a, k) for a in candidates for k in ("txt_files", "xml_files")}
    if set(records) != expected_keys:
        raise ValueError("Acquisition scope differs from frozen candidate pairs")
    results = []
    with tarfile.open(archive, "r:gz") as tar:
        validate_members(tar.getmembers())
        for article in candidates:
            pair = {}
            for kind, ext in (("txt_files", "txt"), ("xml_files", "nxml")):
                record = records[article, kind]
                relative = f"upstream/{kind}/PMC{article}.{ext}"
                url = f"https://raw.githubusercontent.com/jayded/evidence-inference/{REVISION}/annotations/{kind}/PMC{article}.{ext}"
                if record.get("path") != relative or record.get("url") != url:
                    raise ValueError("Acquisition source/path mismatch")
                data = (source_dir / relative).read_bytes()
                if digest(data) != record.get("sha256") or len(data) != record.get("bytes"):
                    raise ValueError("Acquired content digest/size mismatch")
                pair[kind] = data
            handle = tar.extractfile(f"txt_files/PMC{article}.txt")
            if handle is None:
                raise ValueError("Missing article source")
            raw = handle.read()
            comparison = compare_text(raw, pair["txt_files"])
            metadata = article_metadata(pair["xml_files"], article)
            linkage = comparison["lf_coordinate_text_equal"] and metadata["pmcid_matches"]
            article_rows = [r for r in rows if r["article_id"] == article]
            results.append(
                {
                    "article_id": article,
                    "archive_source_sha256": digest(raw),
                    "pinned_txt_sha256": digest(pair["txt_files"]),
                    "pinned_xml_sha256": digest(pair["xml_files"]),
                    **comparison,
                    **metadata,
                    "source_linkage": "publisher_paired_release_coordinate_equal"
                    if linkage
                    else "unresolved",
                    "candidate_status": metadata["rights_class"]
                    if linkage
                    else "unresolved_source_linkage",
                    "prompt_ids": sorted({r["prompt_id"] for r in article_rows}),
                    "qualified_row_count": len(article_rows),
                }
            )
    counts = {}
    for status in sorted({r["candidate_status"] for r in results}):
        group = [r for r in results if r["candidate_status"] == status]
        counts[status] = {
            "articles": len(group),
            "prompts": sum(len(r["prompt_ids"]) for r in group),
            "rows": sum(r["qualified_row_count"] for r in group),
        }
    summary = {
        "schema_version": 1,
        "decision": "bounded_rights_candidates_not_step2_admission",
        "archive_sha256": ARCHIVE_SHA256,
        "coordinate_manifest_sha256": COORDINATE_MANIFEST_SHA256,
        "candidate_ids_sha256": CANDIDATE_IDS_SHA256,
        "acquisition_manifest_sha256": digest(acquisition_bytes),
        "tool_sha256": digest(Path(__file__).read_bytes()),
        "source_revision": REVISION,
        "scope": {
            "articles": len(results),
            "prompts": len(eligible),
            "rows": len(rows),
            "model_calls": 0,
            "new_sample": False,
        },
        "raw_byte_equal_articles": sum(r["raw_bytes_equal"] for r in results),
        "lf_coordinate_equal_articles": sum(r["lf_coordinate_text_equal"] for r in results),
        "pmcid_matching_articles": sum(r["pmcid_matches"] for r in results),
        "candidate_counts": counts,
        "recognized_license_article_counts": dict(
            Counter(code for r in results for code in r["recognized_cc_licenses"])
        ),
        "limitations": [
            "Candidate rights categories are evidence-supported research screening, not legal certainty or Step 2 admission.",
            "Attribution and applicable notices must be preserved; third-party exclusions require separate handling.",
            "Noncommercial candidates are conditional on an explicitly noncommercial local research scope; ShareAlike obligations remain applicable.",
            "ND, conflicting, custom and missing terms remain unresolved under this bounded screen.",
            "Publisher-declared XML/TXT pairing plus pinned release and LF-coordinate identity do not prove exact XML extraction or historical PMC version identity.",
            "Repository MIT license does not establish article rights. Raw articles and detailed attribution/license records remain local ignored artifacts.",
        ],
    }
    subset_ids = {
        status: {
            "article_ids": [r["article_id"] for r in results if r["candidate_status"] == status],
            "prompt_ids": sorted(
                {p for r in results if r["candidate_status"] == status for p in r["prompt_ids"]}
            ),
        }
        for status in counts
    }
    return summary, {"summary": summary, "candidate_subset_ids": subset_ids, "articles": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--coordinates", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    summary, manifest = audit(args.archive, args.coordinates, args.source_dir)
    for path, value in ((args.summary, summary), (args.manifest, manifest)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
