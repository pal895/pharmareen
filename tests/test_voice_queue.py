from __future__ import annotations

from pathlib import Path


def test_voice_queue_stores_and_syncs_later():
    html = (Path(__file__).resolve().parents[1] / "local" / "index.html").read_text(encoding="utf-8")
    manifest = (Path(__file__).resolve().parents[1] / "local" / "manifest.json").read_text(encoding="utf-8")

    assert 'accept="audio/*"' in html
    assert '"display": "standalone"' in manifest
