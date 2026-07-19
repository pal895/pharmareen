from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_startup_exposes_truthful_warmup_marker_with_bounded_recent_log_polling():
    source = (ROOT / "start.sh").read_text(encoding="utf-8")

    assert 'tail -n 200 "$BACKEND_LOG"' in source
    assert 'grep -aF "REPORT_SOURCE_SNAPSHOT_WARMED"' in source
    assert "for _ in $(seq 1 30)" in source
    assert 'echo "$WARMUP_MARKER"' in source
    assert "did not appear within 15 seconds" in source
    assert "logs=<number>" not in source
