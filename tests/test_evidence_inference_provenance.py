"""Synthetic provenance cases; no publisher article text is committed."""

import importlib.util
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
spec = importlib.util.spec_from_file_location(
    "provenance", Path(__file__).parents[1] / "tools/evidence_inference_provenance.py"
)
assert spec and spec.loader
provenance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provenance)


def xml(license_text="", href="", pmcid="123"):
    return (
        '<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
        f'<article-id pub-id-type="pmc">{pmcid}</article-id>'
        '<article-id pub-id-type="doi">10.1/example</article-id>'
        "<title-group><article-title>Example</article-title></title-group>"
        f'<permissions><license xlink:href="{href}">{license_text}</license></permissions>'
        "</article-meta></front></article>"
    ).encode()


def test_newline_equivalence_is_not_byte_identity():
    assert provenance.compare_text(b"a\r\nb\rc", b"a\nb\nc") == {
        "raw_bytes_equal": False,
        "lf_coordinate_text_equal": True,
    }
    assert not provenance.compare_text("é".encode(), "e\u0301".encode())["lf_coordinate_text_equal"]


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://creativecommons.org/licenses/by/4.0/", "attribution_research_candidate"),
        ("http://creativecommons.org/publicdomain/zero/1.0/", "attribution_research_candidate"),
        ("http://creativecommons.org/licenses/by-nc/3.0/", "noncommercial_research_conditional"),
        ("http://creativecommons.org/licenses/by-nc-sa/3.0/", "noncommercial_research_conditional"),
        ("http://creativecommons.org/licenses/by-nc-nd/4.0/", "unresolved_no_derivatives"),
        ("https://creativecommons.org.evil.org/licenses/by/4.0/", "unresolved_custom_or_missing"),
        ("http://creativecommons.org/licenses/by/9.9/", "unresolved_custom_or_missing"),
        ("http://creativecommons.org/licenses/by/4.0.evil", "unresolved_custom_or_missing"),
    ],
)
def test_rights_are_specific_to_recognized_license_url(url, expected):
    assert provenance.article_metadata(xml(href=url), "123")["rights_class"] == expected


def test_nested_license_link_recognized_but_unrelated_back_matter_not_used():
    data = xml(
        '<license-p>Terms <ext-link xlink:href="https://creativecommons.org/licenses/by/3.0/">here</ext-link></license-p>'
    )
    assert (
        provenance.article_metadata(data, "123")["rights_class"] == "attribution_research_candidate"
    )
    data = xml().replace(
        b"</article>", b"<back>https://creativecommons.org/licenses/by/4.0/</back></article>"
    )
    assert (
        provenance.article_metadata(data, "123")["rights_class"] == "unresolved_custom_or_missing"
    )


def test_conflicting_licenses_and_wrong_identity_remain_unresolved():
    data = xml(
        "https://creativecommons.org/licenses/by-nc/3.0/",
        "https://creativecommons.org/licenses/by/4.0/",
    )
    assert (
        provenance.article_metadata(data, "123")["rights_class"]
        == "unresolved_conflicting_licenses"
    )
    assert not provenance.article_metadata(xml(), "999")["pmcid_matches"]


def test_entity_declaration_rejected_without_external_resolution():
    with pytest.raises(ValueError, match="entity"):
        provenance.article_metadata(b'<!DOCTYPE article [<!ENTITY x "value">]>' + xml(), "123")


def test_cc0_clause_for_data_does_not_replace_article_license():
    data = xml(
        "Article license http://creativecommons.org/licenses/by/4.0/. "
        "The Creative Commons Public Domain Dedication waiver "
        "(http://creativecommons.org/publicdomain/zero/1.0/) applies to the data made available in this article, unless otherwise stated."
    )
    result = provenance.article_metadata(data, "123")
    assert result["rights_class"] == "attribution_research_candidate"
    assert result["recognized_cc_licenses"] == ["by/4.0"]
    assert result["data_only_cc0_clause"] is True


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    archive = tmp_path / "archive.tar.gz"
    raw = b"source\r\n"
    with tarfile.open(archive, "w:gz") as tar:
        item = tarfile.TarInfo("txt_files/PMC123.txt")
        item.size = len(raw)
        tar.addfile(item, io.BytesIO(raw))
    coordinates = tmp_path / "coordinates.json"
    coordinates.write_text(
        json.dumps(
            {
                "eligible_prompt_ids_before_license": ["p"],
                "rows": [
                    {"prompt_id": "p", "article_id": "123", "problems": []},
                    {"prompt_id": "p", "article_id": "123", "problems": ["non_exact_span"]},
                ],
            }
        )
    )
    ids = tmp_path / "candidate-article-ids.json"
    ids.write_text('["123"]')
    for name, path in (
        ("ARCHIVE_SHA256", archive),
        ("COORDINATE_MANIFEST_SHA256", coordinates),
        ("CANDIDATE_IDS_SHA256", ids),
    ):
        monkeypatch.setattr(provenance, name, provenance.digest(path.read_bytes()))
    records = []
    for kind, ext, data in (
        ("txt_files", "txt", b"source\n"),
        ("xml_files", "nxml", xml(href="https://creativecommons.org/licenses/by/4.0/")),
    ):
        relative = f"upstream/{kind}/PMC123.{ext}"
        target = tmp_path / relative
        target.parent.mkdir(parents=True)
        target.write_bytes(data)
        records.append(
            {
                "article_id": "123",
                "kind": kind,
                "path": relative,
                "url": f"https://raw.githubusercontent.com/jayded/evidence-inference/{provenance.REVISION}/annotations/{kind}/PMC123.{ext}",
                "sha256": provenance.digest(data),
                "bytes": len(data),
            }
        )
    (tmp_path / "acquisition-manifest.json").write_text(
        json.dumps({"revision": provenance.REVISION, "records": records})
    )
    return archive, coordinates, tmp_path


def test_audit_retains_frozen_row_rejections_and_attribution(inputs):
    summary, manifest = provenance.audit(*inputs)
    assert summary["scope"]["rows"] == 1
    assert summary["raw_byte_equal_articles"] == 0
    assert summary["lf_coordinate_equal_articles"] == 1
    assert summary["candidate_counts"]["attribution_research_candidate"] == {
        "articles": 1,
        "prompts": 1,
        "rows": 1,
    }
    assert manifest["articles"][0]["article_ids"]["doi"] == ["10.1/example"]
    assert manifest["articles"][0]["xml_to_txt_exact_reproduction"] == "not_established"


@pytest.mark.parametrize(
    "target", ["coordinates.json", "candidate-article-ids.json", "upstream/txt_files/PMC123.txt"]
)
def test_audit_fails_on_tampered_inputs(inputs, target):
    archive, coordinates, directory = inputs
    (directory / target).write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest"):
        provenance.audit(archive, coordinates, directory)


def test_audit_rejects_source_revision_and_duplicate_pairs(inputs):
    _, _, directory = inputs
    path = directory / "acquisition-manifest.json"
    data = json.loads(path.read_text())
    data["revision"] = "wrong"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="revision"):
        provenance.audit(*inputs)
    data["revision"] = provenance.REVISION
    data["records"].append(data["records"][0])
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Duplicate"):
        provenance.audit(*inputs)
