from datetime import date

from app.main import resolve_report_period


def test_report_period_presets_and_custom_range():
    today = date(2026, 7, 19)
    assert resolve_report_period("Yesterday", today, today)[:2] == (date(2026, 7, 18), date(2026, 7, 18))
    assert resolve_report_period("Last 7 days", today, today)[:2] == (date(2026, 7, 13), today)
    assert resolve_report_period("Last week", today, today)[:2] == (date(2026, 7, 6), date(2026, 7, 12))
    assert resolve_report_period("2026-07-01 to 2026-07-18", today, today)[:2] == (date(2026, 7, 1), date(2026, 7, 18))
