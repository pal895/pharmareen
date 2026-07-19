from datetime import date

from app.main import resolve_report_period
from app.sheets import GoogleSheetsStore


def test_report_period_presets_and_custom_range():
    today = date(2026, 7, 19)
    assert resolve_report_period("Yesterday", today, today)[:2] == (date(2026, 7, 18), date(2026, 7, 18))
    assert resolve_report_period("Last 7 days", today, today)[:2] == (date(2026, 7, 13), today)
    assert resolve_report_period("Last 30 days", today, today)[:2] == (date(2026, 6, 20), today)
    assert resolve_report_period("Last 6 months", today, today)[:2] == (date(2026, 2, 1), today)
    assert resolve_report_period("This year", today, today)[:2] == (date(2026, 1, 1), today)
    assert resolve_report_period("Last week", today, today)[:2] == (date(2026, 7, 6), date(2026, 7, 12))
    assert resolve_report_period("2026-07-01 to 2026-07-18", today, today)[:2] == (date(2026, 7, 1), date(2026, 7, 18))
    assert resolve_report_period("report for 12 January", today, today)[:2] == (date(2026, 1, 12), date(2026, 1, 12))
    assert resolve_report_period("report from 1 June to 30 June", today, today)[:2] == (date(2026, 6, 1), date(2026, 6, 30))
    assert resolve_report_period("report six months ago", today, today)[:2] == (date(2026, 1, 19), date(2026, 1, 19))


def test_google_report_sources_use_one_batch_request():
    class Spreadsheet:
        def __init__(self): self.calls = 0
        def values_batch_get(self, ranges):
            self.calls += 1
            return {"valueRanges": [
                {"values": [["Date", "Drug Name", "Action", "Quantity"], ["2026-07-18", "Cetirizine", "Sold", 1]]},
                {"values": [["Timestamp", "Date", "Type", "Drug", "Quantity"], ["2026-07-18 10:00:00", "2026-07-18", "sale", "Cetirizine", 1]]},
            ]}

    spreadsheet = Spreadsheet()
    store = object.__new__(GoogleSheetsStore)
    store.spreadsheet = spreadsheet
    logs, transactions = store.read_report_source_records("2026-07-18", "2026-07-18")
    assert spreadsheet.calls == 1
    assert logs[0]["Drug Name"] == "Cetirizine"
    assert transactions[0]["Type"] == "sale"
