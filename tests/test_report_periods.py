from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from time import sleep

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
    repeat_logs, repeat_transactions = store.read_report_source_records("2026-07-18", "2026-07-18")
    assert spreadsheet.calls == 1
    assert logs[0]["Drug Name"] == "Cetirizine"
    assert transactions[0]["Type"] == "sale"
    assert repeat_logs == logs
    assert repeat_transactions == transactions


def test_report_source_cache_makes_period_changes_fast_and_write_through():
    class Worksheet:
        def __init__(self): self.rows = []
        def append_row(self, row, value_input_option=None): self.rows.append(row)

    class Spreadsheet:
        def __init__(self):
            self.calls = 0
            self.daily = Worksheet()
            self.transactions = Worksheet()
        def values_batch_get(self, ranges):
            self.calls += 1
            return {"valueRanges": [
                {"values": [["Date", "Time", "Drug Name", "Action", "Quantity", "Price", "Total Value", "Notes"], ["2026-07-18", "10:00:00", "Cetirizine", "Sold", 1, 10, 10, ""]]},
                {"values": [["Timestamp", "Date", "Type", "Drug", "Quantity", "Unit Cost", "Unit Selling Price", "Total Cost", "Total Sales", "Profit", "Note"]]},
            ]}
        def worksheet(self, title):
            return self.daily if title == "Daily_Log" else self.transactions

    store = object.__new__(GoogleSheetsStore)
    store.spreadsheet = Spreadsheet()
    cold_started = perf_counter()
    store.read_report_source_records("2026-07-13", "2026-07-19")
    cold_elapsed = perf_counter() - cold_started
    repeat_started = perf_counter()
    store.read_report_source_records("2026-07-01", "2026-07-18")
    repeat_elapsed = perf_counter() - repeat_started

    class Event:
        drug_name = "Panadol"
        action = type("Action", (), {"value": "Out of Stock"})()
        quantity = 2
        notes = ""

    store.settings = type("Settings", (), {"timezone": "Africa/Nairobi"})()
    store.append_daily_log(Event(), None, None, created_at=datetime(2026, 7, 19, 12, 0, 0))
    logs, _transactions = store.read_report_source_records("2026-07-19", "2026-07-19")

    assert store.spreadsheet.calls == 1
    assert cold_elapsed < 0.1
    assert repeat_elapsed < 0.01
    assert logs[0]["Drug Name"] == "Panadol"


def test_concurrent_report_reads_coalesce_per_store_without_cross_pharmacy_leakage():
    class Spreadsheet:
        def __init__(self, medicine): self.calls = 0; self.medicine = medicine
        def values_batch_get(self, ranges):
            self.calls += 1
            sleep(0.05)
            return {"valueRanges": [
                {"values": [["Date", "Drug Name"], ["2026-07-19", self.medicine]]},
                {"values": [["Timestamp", "Date", "Type", "Drug", "Quantity"]]},
            ]}

    first = object.__new__(GoogleSheetsStore)
    first.spreadsheet = Spreadsheet("Pharmacy A medicine")
    second = object.__new__(GoogleSheetsStore)
    second.spreadsheet = Spreadsheet("Pharmacy B medicine")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _index: first.read_report_source_records("2026-07-19", "2026-07-19"), range(4)))
    other_logs, _ = second.read_report_source_records("2026-07-19", "2026-07-19")

    assert first.spreadsheet.calls == 1
    assert second.spreadsheet.calls == 1
    assert all(result[0][0]["Drug Name"] == "Pharmacy A medicine" for result in results)
    assert other_logs[0]["Drug Name"] == "Pharmacy B medicine"
