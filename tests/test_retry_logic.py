from __future__ import annotations

from pathlib import Path


def test_retry_logic_tracks_retry_count_and_last_error():
    script = (Path(__file__).resolve().parents[1] / "offline_app" / "offline.js").read_text(encoding="utf-8")

    assert "retry_count" in script
    assert "last_error" in script
    assert "retry_count < 10" in script
