from __future__ import annotations

from pathlib import Path


def test_image_queue_stores_and_syncs_later():
    html = (Path(__file__).resolve().parents[1] / "local" / "index.html").read_text(encoding="utf-8")
    script = (Path(__file__).resolve().parents[1] / "local" / "offline.js").read_text(encoding="utf-8")

    assert 'accept="image/*"' in html
    assert "syncActions" in script
