from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
SHOWCASE = ROOT / "docs/showcase/scifact-ui"


def test_showcase_contains_recording_and_live_entry_point() -> None:
    html = (SHOWCASE / "index.html").read_text(encoding="utf-8")

    for marker in (
        '<video controls preload="metadata"',
        "scifact-ui-full.mp4",
        "scifact-ui-full.vtt",
        "scifact-ui-poster.png",
        'id="live-status"',
        'id="live-link"',
        'id="live-retry"',
        'src="./showcase.js"',
        "Research demonstration only",
    ):
        assert marker in html
    assert "claim-input" not in html
    assert "analytics" not in html.lower()


def test_showcase_assets_and_offline_page_are_present() -> None:
    assert (SHOWCASE / "showcase.js").is_file()
    offline = (SHOWCASE / "offline.html").read_text(encoding="utf-8")
    assert "temporarily unavailable" in offline.lower()
    assert "scifact-ui/" in offline
    assert "clinical decision" in offline.lower()


def test_showcase_script_is_one_shot_and_fails_closed() -> None:
    script = (SHOWCASE / "showcase.js").read_text(encoding="utf-8")

    for marker in (
        "/readyz",
        "AbortController",
        "response.status === 200",
        'payload.schema_version === "readiness/v1"',
        'payload.status === "ready"',
        "live-retry",
        'credentials: "omit"',
    ):
        assert marker in script
    assert "setInterval" not in script
    assert "localStorage" not in script
    assert "document.cookie" not in script


def test_live_link_hidden_state_overrides_button_display() -> None:
    stylesheet = (SHOWCASE / "showcase.css").read_text(encoding="utf-8")
    import re

    hidden_rule = re.search(r"\.live-link\[hidden\]\s*\{([^}]+)\}", stylesheet)
    assert hidden_rule is not None
    assert re.search(r"display:\s*none\s*;", hidden_rule.group(1))
