from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol

from app.domain import Action, StockItem
from app.utils import format_ksh, normalize_key, now_in_timezone, parse_int, parse_money


logger = logging.getLogger(__name__)


class DailyLogReader(Protocol):
    def read_daily_logs(self, report_date: str) -> list[dict[str, Any]]:
        ...

    def read_transactions(self, start_date: str, end_date: str | None = None) -> list[dict[str, Any]]:
        ...

    def append_daily_report(self, report_row: dict[str, Any]) -> None:
        ...

    def list_low_stock_items(self) -> list[StockItem]:
        ...


class WhatsAppSender(Protocol):
    def send_message(self, body: str, to: str | None = None) -> None:
        ...


class RecommendationEngine(Protocol):
    def generate_recommendations(self, metrics: dict[str, Any]) -> list[str]:
        ...


@dataclass(frozen=True)
class LowStockWarning:
    drug_name: str
    current_stock: int
    reorder_level: int


@dataclass(frozen=True)
class ReportMetrics:
    report_date: str
    total_sales: float
    total_items_sold: int
    sale_transactions: int
    most_requested: list[tuple[str, int]]
    most_sold: list[tuple[str, int]]
    missed_sales: list[tuple[str, int]]
    not_sold: list[tuple[str, int]]
    low_stock_warnings: list[LowStockWarning]
    peak_activity_time: str
    total_cost: float = 0.0
    gross_profit: float = 0.0
    restocks: list[tuple[str, int]] = field(default_factory=list)
    missing_profit_data: bool = False
    late_sale_transactions: int = 0
    peak_sales_count: int = 0
    peak_items_sold: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "date": self.report_date,
            "total_sales": self.total_sales,
            "total_items_sold": self.total_items_sold,
            "sale_transactions": self.sale_transactions,
            "most_requested": self.most_requested,
            "most_sold": self.most_sold,
            "missed_sales_out_of_stock": self.missed_sales,
            "not_sold_lost_opportunities": self.not_sold,
            "low_stock_warnings": [
                {
                    "drug_name": item.drug_name,
                    "current_stock": item.current_stock,
                    "reorder_level": item.reorder_level,
                }
                for item in self.low_stock_warnings
            ],
            "peak_activity_time": self.peak_activity_time,
            "total_cost": self.total_cost,
            "gross_profit": self.gross_profit,
            "restocks": self.restocks,
            "missing_profit_data": self.missing_profit_data,
            "late_sale_transactions": self.late_sale_transactions,
            "peak_sales_count": self.peak_sales_count,
            "peak_items_sold": self.peak_items_sold,
        }


class ReportService:
    def __init__(
        self,
        store: DailyLogReader,
        whatsapp: WhatsAppSender | None = None,
        recommender: RecommendationEngine | None = None,
        pharmacy_name: str = "PharMareen",
        timezone: str = "Africa/Nairobi",
    ):
        self.store = store
        self.whatsapp = whatsapp
        self.recommender = recommender
        self.pharmacy_name = pharmacy_name
        self.timezone = timezone

    def generate_daily_report(
        self,
        report_date: date | str,
        send_whatsapp: bool = True,
    ) -> str:
        date_text = report_date.isoformat() if isinstance(report_date, date) else report_date
        logs = self.store.read_daily_logs(date_text)
        try:
            transactions = self.store.read_transactions(date_text)
        except Exception:
            transactions = []
        try:
            low_stock = low_stock_from_items(self.store.list_low_stock_items())
        except Exception:
            logger.exception("Low-stock lookup failed; report will continue without low-stock section")
            low_stock = []
        metrics = build_transaction_metrics(date_text, transactions, low_stock) if transactions else build_report_metrics(date_text, logs, low_stock)
        recommendations = self._recommendations(metrics)
        report_text = render_report(
            metrics,
            recommendations,
            pharmacy_name=self.pharmacy_name,
            report_time=now_in_timezone(self.timezone).strftime("%H:%M"),
        )

        self.store.append_daily_report(
            {
                "Date": date_text,
                "Total Sales": metrics.total_sales,
                "Total Cost": metrics.total_cost,
                "Gross Profit": metrics.gross_profit,
                "Total Items Sold": metrics.total_items_sold,
                "Sale Transactions": metrics.sale_transactions,
                "Most Requested Drugs": summarize_pairs(metrics.most_requested),
                "Most Sold Drugs": summarize_pairs(metrics.most_sold),
                "Missed Sales": summarize_pairs(metrics.missed_sales),
                "Restocks Today": summarize_pairs(metrics.restocks),
                "Low Stock Warnings": summarize_low_stock(metrics.low_stock_warnings),
                "AI Recommendation Summary": " | ".join(recommendations),
                "Full Report Text": report_text,
            }
        )

        if send_whatsapp and self.whatsapp is not None:
            self.whatsapp.send_message(report_text)

        return report_text

    def _recommendations(self, metrics: ReportMetrics) -> list[str]:
        if self.recommender is not None:
            try:
                recommendations = self.recommender.generate_recommendations(metrics.as_dict())
                if recommendations:
                    return recommendations
            except Exception:
                logger.exception("AI recommendations failed; using deterministic recommendations")
        return deterministic_recommendations(metrics)


def build_report_metrics(
    report_date: str,
    logs: list[dict[str, Any]],
    low_stock_warnings: list[LowStockWarning] | None = None,
) -> ReportMetrics:
    total_sales = 0.0
    total_items_sold = 0
    sale_transactions = 0
    requested_counter: Counter[str] = Counter()
    sold_counter: Counter[str] = Counter()
    missed_counter: Counter[str] = Counter()
    not_sold_counter: Counter[str] = Counter()
    hour_counter: Counter[int] = Counter()

    for row in logs:
        drug_name = str(row.get("Drug Name") or "").strip()
        if not drug_name:
            continue

        quantity = parse_int(row.get("Quantity"), default=1) or 1
        action = Action.from_value(row.get("Action"))
        if action != Action.RESTOCKED:
            requested_counter[drug_name] += quantity

        hour = _hour_from_time(row.get("Time"))
        if hour is not None:
            hour_counter[hour] += 1

        if action in {Action.SOLD, Action.LATE_SALE}:
            sale_transactions += 1
            total_items_sold += quantity
            sold_counter[drug_name] += quantity
            total = parse_money(row.get("Total Value"))
            if total is None:
                price = parse_money(row.get("Price")) or 0
                total = price * quantity
            total_sales += total
        elif action == Action.OUT_OF_STOCK:
            missed_counter[drug_name] += quantity
        elif action == Action.NOT_SOLD:
            not_sold_counter[drug_name] += quantity

    peak_hour_count = max(hour_counter.values()) if hour_counter else 0
    return ReportMetrics(
        report_date=report_date,
        total_sales=total_sales,
        total_items_sold=total_items_sold,
        sale_transactions=sale_transactions,
        most_requested=top_pairs(requested_counter, limit=5),
        most_sold=top_pairs(sold_counter, limit=5),
        missed_sales=top_pairs(missed_counter, limit=5),
        not_sold=top_pairs(not_sold_counter, limit=5),
        low_stock_warnings=low_stock_warnings or [],
        peak_activity_time=format_peak_time(hour_counter),
        peak_sales_count=peak_hour_count,
        peak_items_sold=peak_hour_count,
    )


def build_transaction_metrics(
    report_date: str,
    transactions: list[dict[str, Any]],
    low_stock_warnings: list[LowStockWarning] | None = None,
) -> ReportMetrics:
    total_sales = 0.0
    total_cost = 0.0
    gross_profit = 0.0
    total_items_sold = 0
    sale_transactions = 0
    requested_counter: Counter[str] = Counter()
    sold_counter: Counter[str] = Counter()
    missed_counter: Counter[str] = Counter()
    not_sold_counter: Counter[str] = Counter()
    restock_counter: Counter[str] = Counter()
    missing_profit_data = False
    late_sale_transactions = 0
    peak_blocks: dict[int, dict[str, int]] = {}

    for row in transactions:
        drug_name = str(row.get("Drug") or "").strip()
        if not drug_name:
            continue

        quantity = parse_int(row.get("Quantity"), default=1) or 1
        transaction_type = normalize_key(row.get("Type"))

        if transaction_type in {"sale", "late sale", "late_sale"}:
            sale_transactions += 1
            if transaction_type in {"late sale", "late_sale"}:
                late_sale_transactions += 1
            total_items_sold += quantity
            sold_counter[drug_name] += quantity
            requested_counter[drug_name] += quantity
            block = two_hour_block_from_timestamp(row.get("Timestamp"))
            if block is not None:
                peak_blocks.setdefault(block, {"transactions": 0, "items": 0})
                peak_blocks[block]["transactions"] += 1
                peak_blocks[block]["items"] += quantity
            row_sales = parse_money(row.get("Total Sales"))
            row_cost = parse_money(row.get("Total Cost"))
            row_profit = parse_money(row.get("Profit"))
            if row_sales is None or row_cost is None or row_profit is None:
                missing_profit_data = True
            total_sales += row_sales or 0
            total_cost += row_cost or 0
            gross_profit += row_profit or 0
        elif transaction_type == "restock":
            restock_counter[drug_name] += quantity
        elif transaction_type in {"no stock", "no_stock", "out of stock"}:
            missed_counter[drug_name] += quantity
            requested_counter[drug_name] += quantity
        elif transaction_type in {"not sold", "not_sold"}:
            not_sold_counter[drug_name] += quantity
            requested_counter[drug_name] += quantity

    peak_time, peak_sales_count, peak_items_sold = summarize_peak_block(peak_blocks)
    return ReportMetrics(
        report_date=report_date,
        total_sales=total_sales,
        total_items_sold=total_items_sold,
        sale_transactions=sale_transactions,
        most_requested=top_pairs(requested_counter, limit=5),
        most_sold=top_pairs(sold_counter, limit=5),
        missed_sales=top_pairs(missed_counter, limit=5),
        not_sold=top_pairs(not_sold_counter, limit=5),
        low_stock_warnings=low_stock_warnings or [],
        peak_activity_time=peak_time,
        total_cost=total_cost,
        gross_profit=gross_profit,
        restocks=top_pairs(restock_counter, limit=5),
        missing_profit_data=missing_profit_data,
        late_sale_transactions=late_sale_transactions,
        peak_sales_count=peak_sales_count,
        peak_items_sold=peak_items_sold,
    )


def render_report(
    metrics: ReportMetrics,
    recommendations: list[str],
    pharmacy_name: str = "PharMareen",
    report_time: str | None = None,
) -> str:
    return render_daily_summary(metrics, pharmacy_name=pharmacy_name, report_time=report_time)

    # Legacy detailed report body is kept below for reference, but the demo report
    # intentionally uses the shorter pharmacy-owner summary above.
    best_seller = metrics.most_sold[0][0] if metrics.most_sold else "None"
    return "\n".join(
        [
            pharmacy_name,
            f"Daily Intelligence Report – {metrics.report_date}",
            "",
            "1. Sales Summary",
            f"- Total sales: {format_ksh(metrics.total_sales)}",
            f"- Total items sold: {metrics.total_items_sold}",
            f"- Number of sale transactions: {metrics.sale_transactions}",
            f"- Best-selling drug: {best_seller}",
            f"- Peak activity time: {metrics.peak_activity_time}",
            "",
            "2. Most Requested Drugs",
            numbered_pairs(metrics.most_requested),
            "",
            "3. Most Sold Drugs",
            numbered_pairs(metrics.most_sold),
            "",
            "4. Missed Demand / Out of Stock",
            request_lines(metrics.missed_sales, singular="request", plural="requests"),
            "",
            "5. Lost Opportunities",
            request_lines(metrics.not_sold, singular="lost opportunity", plural="lost opportunities"),
            "",
            "6. Low Stock Warnings",
            low_stock_lines(metrics.low_stock_warnings),
            "",
            "7. AI Recommendations",
            bullet_lines(recommendations),
        ]
    )


def render_daily_summary(
    metrics: ReportMetrics,
    pharmacy_name: str = "PharMareen",
    report_time: str | None = None,
) -> str:
    report_time = report_time or now_in_timezone("Africa/Nairobi").strftime("%H:%M")
    missed_demand_count = sum(count for _name, count in metrics.missed_sales)
    restock_count = sum(count for _name, count in metrics.restocks)
    best_seller = metrics.most_sold[0][0] if metrics.most_sold else "None"
    lines = [
        f"📊 {pharmacy_name} Daily Report",
        f"Date: {metrics.report_date}",
        "",
        f"Sales: {format_ksh(metrics.total_sales).replace('Ksh', 'KES')}",
        f"Cost: {format_ksh(metrics.total_cost).replace('Ksh', 'KES')}",
        f"Gross Profit: {format_ksh(metrics.gross_profit).replace('Ksh', 'KES')}",
        f"Items Sold: {metrics.total_items_sold}",
        f"Transactions: {metrics.sale_transactions}",
        f"Restocks: {restock_count}",
        f"No-Stock Requests: {missed_demand_count}",
        f"Best Seller: {best_seller}",
        f"Peak Time: {metrics.peak_activity_time}",
        f"Peak Sales Count: {metrics.peak_sales_count}",
        f"Peak Items Sold: {metrics.peak_items_sold}",
        f"Low Stock Items: {compact_low_stock(metrics.low_stock_warnings)}",
    ]
    if metrics.missing_profit_data:
        lines.append("- Warning: Some items had missing price data, so profit may be incomplete.")
    return "\n".join(lines)


def deterministic_recommendations(metrics: ReportMetrics) -> list[str]:
    recommendations: list[str] = []
    if metrics.low_stock_warnings:
        item = metrics.low_stock_warnings[0]
        recommendations.append(
            f"Restock {item.drug_name} urgently. It is at {item.current_stock}, "
            f"with reorder level {item.reorder_level}."
        )
    if metrics.missed_sales:
        top_missed = metrics.missed_sales[0][0]
        recommendations.append(
            f"Customers asked for {top_missed} while it was out of stock. Restock it to avoid missed sales."
        )
    if metrics.most_sold:
        top_sold = metrics.most_sold[0][0]
        recommendations.append(f"Keep extra stock of {top_sold}; it moved fastest today.")
    if metrics.not_sold:
        recommendations.append(f"Review why customers did not buy {metrics.not_sold[0][0]}.")
    return recommendations or ["No urgent action found today."]


def low_stock_from_items(items: list[StockItem]) -> list[LowStockWarning]:
    warnings: list[LowStockWarning] = []
    for item in items:
        if item.current_stock is None or item.reorder_level is None:
            continue
        warnings.append(
            LowStockWarning(
                drug_name=item.drug_name,
                current_stock=item.current_stock,
                reorder_level=item.reorder_level,
            )
        )
    return sorted(warnings, key=lambda item: (item.current_stock - item.reorder_level, item.drug_name))


def top_pairs(counter: Counter[str], limit: int = 5) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0].lower()))[:limit]


def summarize_pairs(items: list[tuple[str, int]]) -> str:
    return "; ".join(f"{name} - {count}" for name, count in items)


def summarize_low_stock(items: list[LowStockWarning]) -> str:
    return "; ".join(
        f"{item.drug_name} - {item.current_stock} left, reorder at {item.reorder_level}"
        for item in items
    )


def numbered_pairs(items: list[tuple[str, int]]) -> str:
    if not items:
        return "None logged."
    return "\n".join(
        f"{index}. {name} - {count}"
        for index, (name, count) in enumerate(items, start=1)
    )


def request_lines(items: list[tuple[str, int]], singular: str, plural: str) -> str:
    if not items:
        return "None logged."
    return "\n".join(
        f"- {name} - {count} {singular if count == 1 else plural}"
        for name, count in items
    )


def low_stock_lines(items: list[LowStockWarning]) -> str:
    if not items:
        return "None."
    return "\n".join(
        f"- {item.drug_name}: {item.current_stock} left. Reorder level: {item.reorder_level}."
        for item in items
    )


def compact_low_stock(items: list[LowStockWarning]) -> str:
    if not items:
        return "None."
    return ", ".join(f"{item.drug_name} ({item.current_stock})" for item in items)


def best_selling_medicines(items: list[tuple[str, int]]) -> str:
    if not items:
        return "None logged."
    return "; ".join(f"{name} - {count}" for name, count in items[:5])


def bullet_lines(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def format_peak_time(hour_counter: Counter[int]) -> str:
    if not hour_counter:
        return "No activity logged"
    hour = sorted(hour_counter.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return f"{hour:02d}:00-{hour:02d}:59"


def two_hour_block_from_timestamp(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace(" ", "T"))
    except ValueError:
        hour = _hour_from_time(text.split(" ", maxsplit=1)[-1])
    else:
        hour = parsed.hour
    if hour is None:
        return None
    return (hour // 2) * 2


def summarize_peak_block(blocks: dict[int, dict[str, int]]) -> tuple[str, int, int]:
    if not blocks:
        return "Not enough data yet", 0, 0
    block, counts = sorted(
        blocks.items(),
        key=lambda item: (-item[1]["transactions"], -item[1]["items"], item[0]),
    )[0]
    return format_two_hour_block(block), counts["transactions"], counts["items"]


def format_two_hour_block(start_hour: int) -> str:
    return f"{format_hour_label(start_hour)} - {format_hour_label((start_hour + 2) % 24)}"


def format_hour_label(hour: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    value = hour % 12
    if value == 0:
        value = 12
    return f"{value}{suffix}"


def _hour_from_time(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        hour = int(text.split(":", maxsplit=1)[0])
    except ValueError:
        return None
    return hour if 0 <= hour <= 23 else None
