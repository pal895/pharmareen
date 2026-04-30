from __future__ import annotations

from app.reports import (
    LowStockWarning,
    build_report_metrics,
    build_transaction_metrics,
    deterministic_recommendations,
    render_report,
)


def test_build_report_metrics_counts_sales_and_missed_requests():
    logs = [
        {
            "Date": "2026-04-27",
            "Time": "09:15:00",
            "Drug Name": "Panadol",
            "Action": "Sold",
            "Quantity": 2,
            "Price": 50,
            "Total Value": 100,
        },
        {
            "Date": "2026-04-27",
            "Time": "09:45:00",
            "Drug Name": "Vitamin C",
            "Action": "Out of Stock",
            "Quantity": 3,
            "Price": "",
            "Total Value": "",
        },
        {
            "Date": "2026-04-27",
            "Time": "10:10:00",
            "Drug Name": "Cough Syrup",
            "Action": "Not Sold",
            "Quantity": 1,
            "Price": "",
            "Total Value": "",
        },
    ]

    metrics = build_report_metrics(
        "2026-04-27",
        logs,
        [LowStockWarning("Panadol", current_stock=3, reorder_level=5)],
    )

    assert metrics.total_sales == 100
    assert metrics.total_items_sold == 2
    assert metrics.sale_transactions == 1
    assert metrics.most_requested == [("Vitamin C", 3), ("Panadol", 2), ("Cough Syrup", 1)]
    assert metrics.most_sold == [("Panadol", 2)]
    assert metrics.missed_sales == [("Vitamin C", 3)]
    assert metrics.not_sold == [("Cough Syrup", 1)]
    assert metrics.low_stock_warnings[0].drug_name == "Panadol"
    assert metrics.peak_activity_time == "09:00-09:59"


def old_test_render_report_contains_decision_sections():
    metrics = build_report_metrics(
        "2026-04-27",
        [
            {
                "Time": "18:02:00",
                "Drug Name": "Panadol",
                "Action": "Sold",
                "Quantity": 1,
                "Price": 50,
                "Total Value": 50,
            }
        ],
        [LowStockWarning("Panadol", current_stock=2, reorder_level=5)],
    )
    report = render_report(metrics, deterministic_recommendations(metrics))

    assert report.startswith("Zilla Pharmacy\nDaily Intelligence Report – 2026-04-27")
    assert "Total sales: Ksh 50" in report
    assert "Number of sale transactions: 1" in report
    assert "2. Most Requested Drugs" in report
    assert "6. Low Stock Warnings" in report
    assert "Best-selling drug: Panadol" in report


def old_test_daily_report_contains_zilla_pharmacy():
    metrics = build_report_metrics("2026-04-27", [], [])
    report = render_report(metrics, ["No urgent action found today."])

    assert "Zilla Pharmacy" in report.splitlines()[0]


def test_render_report_contains_demo_summary():
    metrics = build_report_metrics(
        "2026-04-27",
        [
            {
                "Time": "18:02:00",
                "Drug Name": "Panadol",
                "Action": "Sold",
                "Quantity": 1,
                "Price": 50,
                "Total Value": 50,
            }
        ],
        [LowStockWarning("Panadol", current_stock=2, reorder_level=5)],
    )
    report = render_report(metrics, deterministic_recommendations(metrics), report_time="18:30")

    assert report.startswith("📊 PharMareen Daily Report\nDate: 2026-04-27")
    assert "Sales: KES 50" in report
    assert "Cost: KES 0" in report
    assert "Gross Profit: KES 0" in report
    assert "Transactions: 1" in report
    assert "No-Stock Requests: 0" in report
    assert "Low Stock Items: Panadol (2)" in report
    assert "Best Seller: Panadol" in report


def test_daily_report_contains_pharmareen():
    metrics = build_report_metrics("2026-04-27", [], [])
    report = render_report(metrics, ["No urgent action found today."], report_time="08:00")

    assert report.splitlines()[0] == "📊 PharMareen Daily Report"


def test_transaction_metrics_calculates_peak_time():
    metrics = build_transaction_metrics(
        "2026-04-30",
        [
            {
                "Timestamp": "2026-04-30 16:15:00",
                "Date": "2026-04-30",
                "Type": "sale",
                "Drug": "Panadol",
                "Quantity": 2,
                "Total Sales": 440,
                "Total Cost": 280,
                "Profit": 160,
            },
            {
                "Timestamp": "2026-04-30 16:45:00",
                "Date": "2026-04-30",
                "Type": "late_sale",
                "Drug": "Panadol",
                "Quantity": 3,
                "Total Sales": 660,
                "Total Cost": 420,
                "Profit": 240,
            },
            {
                "Timestamp": "2026-04-30 10:00:00",
                "Date": "2026-04-30",
                "Type": "sale",
                "Drug": "Insulin",
                "Quantity": 1,
                "Total Sales": 1200,
                "Total Cost": 950,
                "Profit": 250,
            },
        ],
        [],
    )

    assert metrics.peak_activity_time == "4PM - 6PM"
    assert metrics.peak_sales_count == 2
    assert metrics.peak_items_sold == 5
    assert metrics.late_sale_transactions == 1
