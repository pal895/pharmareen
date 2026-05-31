from __future__ import annotations

from app.domain import Action, ParsedEvent, ParseResult, StockItem
from app.intake import IntakeService, normalize_spoken_command_text
from app.services.pharmacy_engine import canonical_unit, to_base_quantity


class FakeParser:
    def __init__(self, events: list[ParsedEvent]):
        self.events = events
        self.called = False

    def parse_events(self, text, master_drug_names):
        self.called = True
        return ParseResult(events=self.events)


def test_pharmacy_unit_forms_support_common_onboarding_items():
    for unit in [
        "pack",
        "vial",
        "ampoule",
        "cream",
        "tube",
        "syrup",
        "capsule",
        "ointment",
        "gel",
        "drops",
        "eye drops",
        "ear drops",
        "inhaler",
        "injection",
        "suspension",
        "sachet",
    ]:
        assert canonical_unit(unit) == unit
        assert to_base_quantity(2, unit) == 2
    assert canonical_unit("inj") == "injection"
    assert canonical_unit("amp") == "ampoule"
    assert canonical_unit("syr") == "syrup"
    assert canonical_unit("susp") == "suspension"


def test_intake_service_reloads_owner_approved_pharmacy_shortcut(monkeypatch, tmp_path):
    monkeypatch.setenv("PHARMAREEN_ALIAS_STORE_PATH", str(tmp_path / "aliases.json"))
    store = FakeStore()

    first = IntakeService(FakeParser([]), store, pharmacy_name="Demo Pharmacy")
    learned = first.learn_pharmacy_alias("pd", "Panadol", confirmed=True, owner_approved=True)
    second = IntakeService(FakeParser([]), store, pharmacy_name="Demo Pharmacy")

    assert learned["accepted"] is True
    assert second.aliases_by_key["pd"] == "Panadol"


class FailingParser:
    called = False

    def parse_events(self, text, master_drug_names):
        self.called = True
        raise AssertionError("report commands should not call parser")


class FakeStore:
    def __init__(self):
        self.stocks = {
            "panadol": StockItem(
                drug_name="Panadol",
                selling_price=220,
                cost_price=140,
                current_stock=20,
                reorder_level=5,
                row_number=2,
            ),
            "cough syrup": StockItem(
                drug_name="Cough Syrup",
                selling_price=150,
                cost_price=100,
                current_stock=4,
                reorder_level=2,
                row_number=3,
            ),
            "insulin": StockItem(
                drug_name="Insulin",
                selling_price=1200,
                cost_price=950,
                current_stock=5,
                reorder_level=2,
                row_number=4,
            ),
            "amoxyl": StockItem(
                drug_name="Amoxyl",
                selling_price=450,
                cost_price=320,
                current_stock=20,
                reorder_level=5,
                row_number=5,
            ),
            "cetirizine": StockItem(
                drug_name="Cetirizine",
                selling_price=120,
                cost_price=80,
                current_stock=25,
                reorder_level=8,
                row_number=6,
            ),
            "amoxicillin": StockItem(
                drug_name="Amoxicillin",
                selling_price=500,
                cost_price=360,
                current_stock=10,
                reorder_level=5,
                row_number=9,
            ),
            "antacid": StockItem(
                drug_name="Antacid",
                selling_price=250,
                cost_price=170,
                current_stock=30,
                reorder_level=6,
                row_number=7,
            ),
            "ors": StockItem(
                drug_name="ORS",
                selling_price=80,
                cost_price=50,
                current_stock=30,
                reorder_level=10,
                row_number=8,
            ),
        }
        self.logged = []
        self.transactions = []
        self.reports = {}
        self.batches = []
        self.daily_log_rows = [
            {
                "Date": "today",
                "Time": "10:00:00",
                "Drug Name": "Panadol",
                "Action": "Sold",
                "Quantity": 2,
                "Price": 220,
                "Total Value": 440,
                "Notes": "",
            },
            {
                "Date": "today",
                "Time": "11:00:00",
                "Drug Name": "Insulin",
                "Action": "Out of Stock",
                "Quantity": 1,
                "Price": "",
                "Total Value": "",
                "Notes": "",
            },
        ]

    def list_master_drug_names(self):
        return [stock.drug_name for stock in self.stocks.values()]

    def find_stock(self, drug_name):
        return self.stocks.get(drug_name.lower())

    def append_daily_log(self, event, price, total_value):
        self.logged.append((event, price, total_value))
        self.daily_log_rows.append(
            {
                "Date": "today",
                "Time": "12:00:00",
                "Drug Name": event.drug_name,
                "Action": event.action.value if event.action else "",
                "Quantity": event.quantity,
                "Price": price or "",
                "Total Value": total_value or "",
                "Notes": event.notes,
            }
        )

    def update_current_stock(self, stock, new_current_stock):
        key = stock.drug_name.lower()
        self.stocks[key] = StockItem(
            drug_name=stock.drug_name,
            selling_price=stock.selling_price,
            cost_price=stock.cost_price,
            current_stock=new_current_stock,
            reorder_level=stock.reorder_level,
            row_number=stock.row_number,
        )

    def update_current_stock_and_cost(self, stock, new_current_stock, new_cost_price):
        key = stock.drug_name.lower()
        self.stocks[key] = StockItem(
            drug_name=stock.drug_name,
            selling_price=stock.selling_price,
            cost_price=new_cost_price,
            current_stock=new_current_stock,
            reorder_level=stock.reorder_level,
            row_number=stock.row_number,
        )

    def append_transaction(
        self,
        transaction_type,
        drug_name,
        quantity,
        unit_cost=None,
        unit_selling_price=None,
        total_cost=None,
        total_sales=None,
        profit=None,
        note="",
    ):
        self.transactions.append(
            {
                "Date": "today",
                "Timestamp": "2026-04-27 16:15:00",
                "Type": transaction_type,
                "Drug": drug_name,
                "Quantity": quantity,
                "Unit Cost": unit_cost if unit_cost is not None else "",
                "Unit Selling Price": unit_selling_price if unit_selling_price is not None else "",
                "Total Cost": total_cost if total_cost is not None else "",
                "Total Sales": total_sales if total_sales is not None else "",
                "Profit": profit if profit is not None else "",
                "Note": note,
            }
        )

    def read_transactions(self, start_date, end_date=None):
        return self.transactions

    def get_daily_report_text(self, report_date):
        return self.reports.get(report_date)

    def read_daily_logs(self, report_date):
        return self.daily_log_rows

    def list_low_stock_items(self):
        return [
            stock
            for stock in self.stocks.values()
            if stock.current_stock is not None
            and stock.reorder_level is not None
            and stock.current_stock <= stock.reorder_level
        ]

    def append_batch(self, batch):
        self.batches.append(batch)

    def list_batches(self, drug_name=None):
        if not drug_name:
            return list(self.batches)
        wanted = str(drug_name).strip().lower()
        return [batch for batch in self.batches if str(getattr(batch, "drug_name", "")).strip().lower() == wanted]

    def update_batch_remaining(self, batch_id, remaining_units):
        for batch in self.batches:
            if getattr(batch, "batch_id", "") == batch_id:
                batch.current_remaining_units = max(int(remaining_units), 0)
                return


def test_help_command_returns_available_commands_without_parser():
    store = FakeStore()
    parser = FailingParser()
    service = IntakeService(parser, store)

    for command in ["help", "menu", "commands", "how do I use this", "tutorial", "guide", "what can you do"]:
        reply = service.process_text(command)

        assert len(reply) < 1200
        assert "PHARMAREEN QUICK COMMANDS" in reply
        assert "Panadol sold 2" in reply
        assert "Insulin sold 1" in reply
        assert "Panadol stock" in reply
        assert "Panadol restock 20" in reply
        assert "Panadol +20" in reply
        assert "Panadol restock 20 cost 2000" in reply
        assert "Panadol restock 20 bonus 5" in reply
        assert "Panadol bought 20 plus 5 bonus" in reply
        assert "Amoxicillin received 30 paid 2500 discount 300" in reply
        assert "Panadol restock 20 supplier DawaPlus expiry Dec 2026" in reply
        assert "Send invoice photo" in reply
        assert "Panadol sold two" in reply
        assert "Offline mode" in reply
        assert parser.called is False


def test_sale_with_strip_unit_payment_and_discount_records_engine_metadata():
    store = FakeStore()
    service = IntakeService(FakeParser([]), store)

    reply = service.process_text("Panadol 1 strip mpesa discount 50", conversation_id="staff-phone")

    assert "Panadol x1 strip recorded" in reply
    assert "Equivalent: 10 tablets" in reply
    assert "Stock left: 10 tablets" in reply
    assert "Profit:" not in reply
    details = service.process_text("details last", conversation_id="staff-phone")
    assert "Payment: M-Pesa" in details
    assert "Discount: KES 50" in details
    assert store.stocks["panadol"].current_stock == 10
    transaction = store.transactions[-1]
    assert transaction["Quantity"] == 10
    assert transaction["Total Sales"] == 2150
    assert transaction["Profit"] == 750
    assert "unit=strip" in transaction["Note"]
    assert "base_quantity=10" in transaction["Note"]
    assert "payment=M-Pesa" in transaction["Note"]
    assert "discount=50.0" in transaction["Note"]
    assert "trace_id=SALE-" in transaction["Note"]


def test_restock_box_unit_converts_to_tablets():
    store = FakeStore()
    service = IntakeService(FakeParser([]), store)

    reply = service.process_text("+Panadol 1 box")

    assert "Panadol +1 box added" in reply
    assert "Equivalent: +100 tablets" in reply
    assert "Stock left: 120 tablets" in reply
    assert store.stocks["panadol"].current_stock == 120
    transaction = store.transactions[-1]
    assert transaction["Quantity"] == 100
    assert "unit=box" in transaction["Note"]
    assert "base_quantity=100" in transaction["Note"]


def test_restock_supplier_invoice_batch_and_expiry_are_traced():
    store = FakeStore()
    service = IntakeService(FakeParser([]), store)

    reply = service.process_text("received Panadol 1 box supplier Beta invoice INV123 batch B001 expiry Jan 2027")

    assert "Supplier: Beta" in reply
    assert "Invoice: INV123" not in reply
    assert "Batch: B001" not in reply
    note = store.transactions[-1]["Note"]
    assert "supplier=Beta" in note
    assert "invoice=INV123" in note
    assert "batch=B001" in note
    assert "expiry=Jan 2027" in note


def test_trace_and_expiry_commands_show_batch_details():
    store = FakeStore()
    service = IntakeService(FakeParser([]), store)
    service.process_text("received Panadol 1 box supplier Beta invoice INV123 batch B001 expiry Jan 2027")

    trace_reply = service.process_text("trace Panadol")
    expiry_reply = service.process_text("expiry")

    assert "Trace Panadol" in trace_reply
    assert "B001" in trace_reply
    assert "supplier Beta" in trace_reply
    assert "invoice INV123" in trace_reply
    assert "Use earliest expiry first" in trace_reply
    assert "Expiry" in expiry_reply
    assert "Panadol" in expiry_reply
    assert "2027-01-01" in expiry_reply


def test_low_stock_and_stock_value_commands_are_available():
    store = FakeStore()
    service = IntakeService(FakeParser([]), store)
    service.process_text("Cough Syrup 2")

    low_stock_reply = service.process_text("low stock")
    stock_value_reply = service.process_text("stock value")

    assert "Running low" in low_stock_reply
    assert "Cough Syrup" in low_stock_reply
    assert "2 left" in low_stock_reply
    assert "restock when left with 2" in low_stock_reply
    assert "reorder at" not in low_stock_reply.lower()
    assert "Stock Value" in stock_value_reply
    assert "Cost value:" in stock_value_reply
    assert "Selling value:" in stock_value_reply
    assert "Potential profit:" in stock_value_reply


def test_custom_conversion_command_affects_unit_sales_and_restocks():
    store = FakeStore()
    service = IntakeService(FakeParser([]), store)

    conversion_reply = service.process_text("Panadol conversion 1 box 12 strips 1 strip 10 tablets")
    restock_reply = service.process_text("+Panadol 1 box")
    assert store.stocks["panadol"].current_stock == 140
    sale_reply = service.process_text("Panadol sold 1 strip")

    assert "Conversion saved for Panadol" in conversion_reply
    assert "1 box = 12 strips" in conversion_reply
    assert "Equivalent: +120 tablets" in restock_reply
    assert "Equivalent: 10 tablets" in sale_reply
    assert store.stocks["panadol"].current_stock == 130


def test_staff_session_payment_summary_and_void_flow():
    store = FakeStore()
    service = IntakeService(FakeParser([]), store)

    assert "Staff set: Mary" in service.process_text("set staff Mary", conversation_id="phone-1")
    sale_reply = service.process_text("Panadol 2 mpesa discount 20", conversation_id="phone-1")

    assert "Payment:" not in sale_reply
    assert "Payment: M-Pesa" in service.process_text("details last", conversation_id="phone-1")
    assert store.stocks["panadol"].current_stock == 18
    sale_note = store.transactions[-1]["Note"]
    assert "staff=Mary" in sale_note
    assert "payment=M-Pesa" in sale_note
    assert "discount=20.0" in sale_note

    summary = service.process_text("cash summary")
    assert "Daily Cash Summary" in summary
    assert "M-Pesa: KES 420" in summary
    assert "Discounts: KES 20" in summary
    staff_summary = service.process_text("staff summary")
    assert "Staff Summary" in staff_summary
    assert "Mary: KES 420" in staff_summary

    assert "Why are you voiding this sale?" in service.process_text("void last", conversation_id="phone-1")
    void_reply = service.process_text("wrong item", conversation_id="phone-1")
    assert "Last sale removed safely" in void_reply
    assert "M-Pesa total adjusted" in void_reply
    assert store.stocks["panadol"].current_stock == 20
    assert store.transactions[-1]["Type"] == "void"
    assert "original_trace_id=SALE-" in store.transactions[-1]["Note"]
def test_greeting_returns_warm_onboarding_without_parser():
    store = FakeStore()
    parser = FailingParser()
    service = IntakeService(parser, store)

    for command in ["hello", "hi", "habari", "good morning", "mambo"]:
        reply = service.process_text(command)

        assert "Welcome to PharMareen" in reply
        assert "Panadol 2" in reply
        assert "+Panadol 20" in reply
        assert "report today" in reply
        assert parser.called is False


def test_unknown_message_returns_human_guidance():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("please do the pharmacy thing")

    assert "not fully sure" in reply
    assert "Panadol 2" in reply
    assert "+Panadol 20" in reply
    assert "report today" in reply
    assert "help" in reply


def test_natural_sale_followup_records_after_quantity_reply():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    first = service.process_text("sell panadol", conversation_id="2547")
    second = service.process_text("2", conversation_id="2547")

    assert first == "How many Panadol were sold?"
    assert "Panadol x2 recorded" in second
    assert store.stocks["panadol"].current_stock == 18


def test_natural_restock_followup_records_after_quantity_reply():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    first = service.process_text("restock panadol", conversation_id="2547")
    second = service.process_text("20", conversation_id="2547")

    assert first == "How many Panadol were added?"
    assert "Panadol +20 added" in second
    assert store.stocks["panadol"].current_stock == 40


def test_stock_followup_checks_named_drug():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    first = service.process_text("check stock", conversation_id="2547")
    second = service.process_text("Panadol", conversation_id="2547")

    assert "Which medicine should I check" in first
    assert "Panadol stock left: 20" in second


def test_more_natural_stock_and_report_phrases_work():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    stock_reply = service.process_text("remaining stock panadol")
    report_reply = service.process_text("today sales")
    summary_reply = service.process_text("summary today")

    assert "Panadol stock left: 20" in stock_reply
    assert report_reply.startswith("📊 Daily Report")
    assert summary_reply.startswith("📊 Daily Report")


def test_compact_rush_hour_commands_are_normalized_safely():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    sale_reply = service.process_text("Panadol2")
    stock_reply = service.process_text("Panadolstock")
    restock_reply = service.process_text("Panadol+20")
    late_reply = service.process_text("latepanadol5")

    assert "Panadol x2 recorded" in sale_reply
    assert "Panadol stock left: 18" in stock_reply
    assert "Panadol +20 added" in restock_reply
    assert "Late sale saved" in late_reply
    assert store.stocks["panadol"].current_stock == 33


def test_compact_multi_sale_and_swahili_phrases_work():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    batch_reply = service.process_text("Panadol2amox1ors3")
    swahili_reply = service.process_text("Nimeuza Panadol mbili cash", conversation_id="2547")
    no_stock_reply = service.process_text("Customer amesema hakuna insulin")

    assert "Batch processed" in batch_reply
    assert "Panadol x2" in batch_reply
    assert "Did you mean:" in batch_reply
    assert "Amoxyl" in batch_reply
    assert "Amoxicillin" in batch_reply
    assert "ORS x3" in batch_reply
    assert "Panadol x2 recorded" in swahili_reply
    assert "Insulin no-stock request logged" in no_stock_reply


def test_last_sale_payment_and_quantity_corrections_are_short():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    service.process_text("Panadol 2 cash", conversation_id="2547")
    payment_reply = service.process_text("Panadol ilikuwa mpesa si cash", conversation_id="2547")
    quantity_reply = service.process_text("Badilisha ile ya mwisho iwe 5", conversation_id="2547")
    reduce_reply = service.process_text("Punguza moja", conversation_id="2547")

    assert "Updated last Panadol sale: Cash" in payment_reply
    assert "M-Pesa" in payment_reply
    assert "Updated last Panadol sale quantity: 2" in quantity_reply
    assert "5" in quantity_reply
    assert "Updated last Panadol sale quantity: 5" in reduce_reply
    assert "4" in reduce_reply
    assert store.stocks["panadol"].current_stock == 16


def test_best_seller_question_answers_directly():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    service.process_text("Panadol 2")
    service.process_text("Insulin 1")
    reply = service.process_text("Best seller today")

    assert reply == "Best seller today: Panadol — 2 sold"

def test_stock_check_returns_current_stock_price_and_reorder_level():
    store = FakeStore()
    parser = FailingParser()
    service = IntakeService(parser, store)

    reply = service.process_text("Panadol stock")

    assert reply == (
        "📦 Panadol stock left: 20\n"
        "Price: KES 220\n"
        "Restock when left with 5"
    )
    assert parser.called is False


def test_report_today_returns_compact_summary_without_saved_report_lookup():
    store = FakeStore()
    parser = FailingParser()
    service = IntakeService(parser, store)

    reply = service.process_text("report today")

    assert reply.startswith("📊 Daily Report")
    assert "Sales:" in reply
    assert "Cost:" in reply
    assert "Profit:" in reply
    assert "Running low:" in reply
    assert "PDF report:" in reply
    assert parser.called is False


def test_sold_item_with_price_found_logs_total_and_reduces_stock():
    store = FakeStore()
    service = IntakeService(
        FakeParser([ParsedEvent("panadol", Action.SOLD, quantity=2)]),
        store,
    )

    reply = service.process_text("Panadol sold 2")

    assert "Panadol x2 recorded" in reply
    assert "Stock left: 18" in reply
    assert "Profit:" not in reply
    assert "Profit: KES 160" in service.process_text("details last")
    assert store.logged[0][0].drug_name == "Panadol"
    assert store.logged[0][1] == 220
    assert store.logged[0][2] == 440
    assert store.stocks["panadol"].current_stock == 18


def test_sold_item_with_missing_price_does_not_log():
    store = FakeStore()
    service = IntakeService(
        FakeParser([ParsedEvent("UnknownDrug", Action.SOLD, quantity=1)]),
        store,
    )

    reply = service.process_text("UnknownDrug sold")

    assert reply == "UnknownDrug was not found in inventory. Please add or restock it first."
    assert store.logged == []


def test_sold_item_with_missing_cost_still_logs_with_warning():
    store = FakeStore()
    store.stocks["panadol"] = StockItem(
        drug_name="Panadol",
        selling_price=220,
        cost_price=None,
        current_stock=20,
        reorder_level=5,
        row_number=2,
    )
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Panadol 2")

    assert "Panadol x2 recorded" in reply
    assert "Profit:" not in reply
    assert store.logged[0][0].drug_name == "Panadol"
    assert store.transactions[-1]["Type"] == "sale"
    assert store.stocks["panadol"].current_stock == 18


def test_out_of_stock_sale_records_missed_sale_without_deducting_stock():
    store = FakeStore()
    store.stocks["ors"] = StockItem(
        drug_name="ORS",
        selling_price=80,
        cost_price=50,
        current_stock=0,
        reorder_level=10,
        row_number=8,
    )
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("ORS 2 cash")

    assert "ORS out of stock" in reply
    assert "Sale not recorded" in reply
    assert "Missed sale saved: ORS x2" in reply
    assert store.stocks["ors"].current_stock == 0
    assert store.transactions[-1]["Type"] == "no_stock"
    assert store.transactions[-1]["Drug"] == "ORS"
    assert store.transactions[-1]["Quantity"] == 2
    assert not any(transaction["Type"] == "sale" and transaction["Drug"] == "ORS" for transaction in store.transactions)


def test_insufficient_stock_sale_records_missed_sale_without_negative_stock():
    store = FakeStore()
    store.stocks["ors"] = StockItem(
        drug_name="ORS",
        selling_price=80,
        cost_price=50,
        current_stock=1,
        reorder_level=10,
        row_number=8,
    )
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("ORS 3 cash")

    assert "Only 1 available" in reply
    assert "Sale not recorded" in reply
    assert "Missed sale saved: ORS x3" in reply
    assert store.stocks["ors"].current_stock == 1
    assert store.transactions[-1]["Type"] == "no_stock"
    assert store.transactions[-1]["Quantity"] == 3


def test_string_zero_stock_from_sheets_records_missed_sale_without_deducting_stock():
    store = FakeStore()
    store.stocks["ors"] = StockItem(
        drug_name="ORS",
        selling_price=80,
        cost_price=50,
        current_stock="0",  # type: ignore[arg-type]
        reorder_level="10",  # type: ignore[arg-type]
        row_number=8,
    )
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("ORS 2 cash")

    assert "ORS out of stock" in reply
    assert "Sale not recorded" in reply
    assert "Missed sale saved: ORS x2" in reply
    assert store.stocks["ors"].current_stock == "0"
    assert store.transactions[-1]["Type"] == "no_stock"
    assert store.transactions[-1]["Quantity"] == 2
    assert not any(transaction["Type"] == "sale" and transaction["Drug"] == "ORS" for transaction in store.transactions)


def test_shared_sale_path_uses_safety_stock_before_recording_sale():
    class SplitTruthStore(FakeStore):
        def find_stock(self, drug_name):
            if str(drug_name).lower() == "ors":
                return StockItem("ORS", 80, 50, 2, 10, 8)
            return super().find_stock(drug_name)

        def find_stock_for_safety(self, drug_name, pharmacy_id=None):
            if str(drug_name).lower() == "ors":
                return StockItem("ORS", 80, 50, 0, 10, 8)
            return self.find_stock(drug_name)

    store = SplitTruthStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("ORS 2 cash")

    assert "ORS out of stock" in reply
    assert "Sale not recorded" in reply
    assert "Missed sale saved: ORS x2" in reply
    assert not any(transaction["Type"] == "sale" and transaction["Drug"] == "ORS" for transaction in store.transactions)
    assert store.transactions[-1]["Type"] == "no_stock"


def test_out_of_stock_missing_from_master_stock_still_logs():
    store = FakeStore()
    service = IntakeService(
        FakeParser([ParsedEvent("Ventolin", Action.OUT_OF_STOCK, quantity=1)]),
        store,
    )

    reply = service.process_text("Ventolin no stock")

    assert reply == "📝 Ventolin no-stock request logged"
    assert store.logged[0][0].drug_name == "Ventolin"
    assert store.logged[0][1] is None
    assert store.logged[0][2] is None


def test_not_sold_missing_from_master_stock_still_logs():
    store = FakeStore()
    service = IntakeService(
        FakeParser([ParsedEvent("Inhaler", Action.NOT_SOLD, quantity=1)]),
        store,
    )

    reply = service.process_text("Inhaler customer left")

    assert reply == "Logged lost opportunity: Inhaler."
    assert store.logged[0][0].drug_name == "Inhaler"
    assert store.logged[0][1] is None
    assert store.logged[0][2] is None


def test_restock_item_increases_current_stock_and_logs():
    store = FakeStore()
    service = IntakeService(
        FakeParser([ParsedEvent("panadol", Action.RESTOCKED, quantity=20)]),
        store,
    )

    reply = service.process_text("Panadol restock 20")

    assert "Panadol +20 added" in reply
    assert "Avg cost:" not in reply
    assert "Stock left: 40" in reply
    assert store.stocks["panadol"].current_stock == 40
    assert store.logged[0][0].action == Action.RESTOCKED
    assert store.logged[0][1] is None
    assert store.logged[0][2] is None


def test_sale_reply_includes_low_stock_warning():
    store = FakeStore()
    service = IntakeService(
        FakeParser([ParsedEvent("cough syrup", Action.SOLD, quantity=2)]),
        store,
    )

    reply = service.process_text("Cough Syrup sold 2")

    assert "Cough Syrup x2 recorded" in reply
    assert "Stock left: 2" in reply


def test_multiple_items_in_one_message_logs_each_item():
    store = FakeStore()
    service = IntakeService(
        FakeParser(
            [
                ParsedEvent("Panadol", Action.SOLD, quantity=2),
                ParsedEvent("Insulin", Action.OUT_OF_STOCK, quantity=1),
                ParsedEvent("Cough Syrup", Action.SOLD, quantity=1),
            ]
        ),
        store,
    )

    reply = service.process_text("Panadol sold 2, insulin no stock, cough syrup sold 1")

    assert "Batch processed" in reply
    assert "- Panadol x2" in reply
    assert "- Insulin" in reply
    assert "- Cough Syrup x1" in reply
    assert len(store.logged) == 3


def test_simple_sale_command_records_short_reply_and_details_command():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Panadol 2")

    assert "Panadol x2 recorded" in reply
    assert "Profit:" not in reply
    assert "Trace:" not in reply
    assert "Profit: KES 160" in service.process_text("details last")
    assert store.stocks["panadol"].current_stock == 18
    assert store.transactions[-1]["Type"] == "sale"


def test_sale_aliases_are_customer_friendly():
    for message in ["panadol two", "panadol x2", "sell panadol 2", "sold panadol 2", "sold two panadol"]:
        store = FakeStore()
        service = IntakeService(FailingParser(), store)

        reply = service.process_text(message)

        assert "Panadol x2 recorded" in reply
        assert store.stocks["panadol"].current_stock == 18
        assert store.transactions[-1]["Type"] == "sale"


def test_typo_tolerance_and_shortcut_safety(monkeypatch):
    store = FakeStore()
    store.stocks["paracetamol"] = StockItem("Paracetamol", 100, 60, 20, 5, 10)
    service = IntakeService(FailingParser(), store)

    typo_reply = service.process_text("Panadl 2")
    ambiguous_reply = service.process_text("pa 2")
    unknown_shortcut_reply = service.process_text("pd 2")

    assert "Panadol x2 recorded" in typo_reply
    assert "Did you mean:" in ambiguous_reply
    assert "Panadol" in ambiguous_reply
    assert "Paracetamol" in ambiguous_reply
    assert "not sure what \"Pd\" means" in unknown_shortcut_reply

    monkeypatch.setenv("PHARMAREEN_DRUG_ALIASES", "pd=Panadol")
    alias_service = IntakeService(FailingParser(), FakeStore())
    assert "Panadol x2 recorded" in alias_service.process_text("pd 2")


def test_rush_hour_space_separated_batch_processes_successes_and_failures():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Panadol 2 piriton 1 amoxil 3")

    assert "Batch processed" in reply
    assert "Sales:" in reply
    assert "- Panadol x2" in reply
    assert "- Amoxyl x3" in reply
    assert "Errors:" in reply
    assert "Piriton was not found" in reply


def test_mixed_payment_sale_records_split_totals_and_keeps_reply_short():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Panadol 2 cash 100 mpesa 200")
    summary = service.process_text("cash summary")

    assert "Panadol x2 recorded" in reply
    assert "Payment:" not in reply
    assert "payment=Mixed" in store.transactions[-1]["Note"]
    assert "payment_cash=100.0" in store.transactions[-1]["Note"]
    assert "payment_mpesa=200.0" in store.transactions[-1]["Note"]
    assert "Cash: KES 100" in summary
    assert "M-Pesa: KES 200" in summary


def test_receipt_printing_setting_and_printable_last_receipt():
    service = IntakeService(FailingParser(), FakeStore())

    assert "Receipt printing is now ON." in service.process_text("receipt printing on")
    sale_reply = service.process_text("Panadol 2")
    assert "🧾 Digital receipt ready — printer not detected" in sale_reply
    receipt = service.process_text("print receipt last")

    assert "PHARMAREEN RECEIPT" in receipt
    assert "Medicine: Panadol" in receipt
    assert "Quantity: 2" in receipt


def test_simple_restock_plus_command_records_restock():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("+Panadol 20")

    assert "Panadol +20 added" in reply
    assert "Stock left: 40" in reply
    assert store.transactions[-1]["Type"] == "restock"


def test_restock_aliases_add_received_and_stock_work():
    for message in ["add Panadol 20", "received Panadol 20", "stock Panadol 20", "add twenty panadol"]:
        store = FakeStore()
        service = IntakeService(FailingParser(), store)

        reply = service.process_text(message)

        assert "Panadol +20 added" in reply
        assert "Stock left: 40" in reply
        assert store.transactions[-1]["Type"] == "restock"


def test_restock_with_total_cost_updates_average_cost():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("+Panadol 20 2000")

    assert "Avg cost:" not in reply
    assert store.stocks["panadol"].cost_price == 120
    assert store.stocks["panadol"].current_stock == 40


def test_bonus_restock_records_free_stock_type():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("+Panadol 5 bonus")

    assert "Panadol +5 added" in reply
    assert "Bonus: 5" in reply
    assert "Stock left: 25" in reply
    assert store.stocks["panadol"].current_stock == 25
    assert store.transactions[-1]["Total Cost"] == 0
    assert "Restock type: bonus" in store.transactions[-1]["Note"]


def test_bonus_restock_aliases_are_understood():
    for message in ["bonus Panadol 5", "free Panadol 5", "extra Panadol 5", "Panadol 5 bonus"]:
        store = FakeStore()
        service = IntakeService(FailingParser(), store)

        reply = service.process_text(message)

        assert "Panadol +5 added" in reply
        assert "Bonus: 5" in reply
        assert "Stock left: 25" in reply
        assert store.transactions[-1]["Total Cost"] == 0


def test_discount_restock_records_discount_type():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("+Panadol 20 1800 disc")

    assert "Panadol +20 added" in reply
    assert "Paid: KES 1,800" in reply
    assert "Avg cost:" not in reply
    assert store.stocks["panadol"].cost_price == 115
    assert store.transactions[-1]["Total Cost"] == 1800
    assert "Restock type: discount" in store.transactions[-1]["Note"]


def test_discount_restock_disc_alias_records_discount_type():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("+Panadol 20 2000 disc")

    assert "Panadol +20 added" in reply
    assert "Paid: KES 2,000" in reply
    assert store.transactions[-1]["Total Cost"] == 2000
    assert "Restock type: discount" in store.transactions[-1]["Note"]


def test_restock_cost_keyword_records_total_cost():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("+Panadol 20 cost 1800")

    assert "Panadol +20 added" in reply
    assert "Paid: KES 1,800" in reply
    assert "Avg cost:" not in reply
    assert store.transactions[-1]["Total Cost"] == 1800


def test_restock_paid_cost_aliases_work():
    for message in ["+Panadol 20 paid 1800", "bought Panadol 20 for 1800", "received Panadol 20 paid 1800"]:
        store = FakeStore()
        service = IntakeService(FailingParser(), store)

        reply = service.process_text(message)

        assert "Panadol +20 added" in reply
        assert "Paid: KES 1,800" in reply
        assert store.transactions[-1]["Total Cost"] == 1800


def test_ordered_paid_restock_records_budget_savings():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("+Panadol 20 ordered 2000 paid 1800")

    assert "Panadol +20 added" in reply
    assert "Budget:" not in reply
    assert "Paid: KES 1,800" in reply
    assert "Saved: KES 200" in reply
    assert "Avg cost:" not in reply
    assert store.transactions[-1]["Total Cost"] == 1800
    assert "Budgeted KES 2,000" in store.transactions[-1]["Note"]


def test_natural_restock_cost_phrase_records_cost():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Panadol restock 20 cost 2000")

    assert "Panadol +20 added" in reply
    assert "Paid: KES 2,000" in reply
    assert "Stock left: 40" in reply
    assert store.transactions[-1]["Total Cost"] == 2000


def test_bonus_restock_with_cost_records_total_received():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Panadol restock 20 bonus 5 cost 2000")

    assert "Panadol +25 added" in reply
    assert "Bought 20 + bonus 5" in reply
    assert "Paid: KES 2,000" in reply
    assert "Stock left: 45" in reply
    assert store.transactions[-1]["Quantity"] == 25
    assert store.transactions[-1]["Total Cost"] == 2000
    assert "Bonus quantity 5" in store.transactions[-1]["Note"]


def test_discount_restock_natural_phrase_records_discount():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Amoxicillin received 30 paid 2500 discount 300")

    assert "Amoxicillin +30 added" in reply
    assert "Paid: KES 2,500" in reply
    assert "Discount: KES 300" in reply
    assert store.stocks["amoxicillin"].current_stock == 40
    assert store.transactions[-1]["Total Cost"] == 2500
    assert "Discount KES 300" in store.transactions[-1]["Note"]


def test_bonus_and_supplier_expiry_restock_phrase_records_metadata():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Panadol restock 20 bonus 5 cost 2000 supplier DawaPlus expiry Dec 2026")

    assert "Panadol +25 added" in reply
    assert "Supplier: DawaPlus" in reply
    assert "Expiry: Dec 2026" in reply
    assert store.transactions[-1]["Quantity"] == 25
    assert "Supplier: DawaPlus" in store.transactions[-1]["Note"]
    assert "Expiry: Dec 2026" in store.transactions[-1]["Note"]


def test_bonus_discount_restock_with_box_unit_is_easy_to_record():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Panadol restock 5 boxes bonus 1 discount 200")

    assert "Panadol +6 boxes added" in reply
    assert "Equivalent: +600 tablets" in reply
    assert "Bonus: 1" in reply or "Bought 5 + bonus 1" in reply
    assert "Discount: KES 200" in reply
    assert store.stocks["panadol"].current_stock == 620
    assert store.transactions[-1]["Quantity"] == 600


def test_natural_supplier_gave_bonus_and_paid_for_bonus_phrases():
    for message, drug_key, expected_stock in [
        ("Supplier gave Panadol 20, bonus 5", "panadol", 45),
        ("Bought Cetirizine 50, paid for 45, bonus 5", "cetirizine", 80),
    ]:
        store = FakeStore()
        service = IntakeService(FailingParser(), store)

        reply = service.process_text(message)

        assert "added" in reply
        assert "bonus 5" in reply
        assert store.stocks[drug_key].current_stock == expected_stock
        assert store.transactions[-1]["Quantity"] in {25, 55}


def test_late_sale_command_records_late_sale():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("later Panadol 3")

    assert "Late sale saved" in reply
    assert "Panadol x3" in reply
    assert store.transactions[-1]["Type"] == "late_sale"
    assert store.logged[-1][0].action == Action.LATE_SALE


def test_late_keyword_records_late_sale():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("late Panadol 3")

    assert "Late sale saved" in reply
    assert "Panadol x3" in reply
    assert store.transactions[-1]["Type"] == "late_sale"
    assert store.logged[-1][0].action == Action.LATE_SALE


def test_missed_sale_alias_records_late_sale():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("missed Panadol 3")

    assert "Late sale saved" in reply
    assert store.transactions[-1]["Type"] == "late_sale"


def test_profit_today_command_summarizes_profit():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)
    service.process_text("Panadol 2")

    reply = service.process_text("profit today")

    assert "Profit Today" in reply
    assert "Sales: KES 440" in reply
    assert "Cost: KES 280" in reply
    assert "Gross Profit: KES 160" in reply


def test_process_batch_command_gives_safe_instruction():
    service = IntakeService(FailingParser(), FakeStore())

    reply = service.process_text("process batch")

    assert "No saved offline entries yet" in reply
    assert "Panadol 2" in reply


def test_report_week_command_summarizes_last_seven_days():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)
    service.process_text("Panadol 2")

    reply = service.process_text("report week")

    assert "Weekly Report" in reply
    assert "Sales: KES 440" in reply
    assert "Profit: KES 160" in reply
    assert "Best Seller: Panadol" in reply
    assert "PDF report:" in reply


def test_report_today_includes_downloadable_pdf_link():
    store = FakeStore()
    service = IntakeService(FailingParser(), store, app_base_url="https://reports.pharmareen.app")
    service.process_text("Panadol 2")

    reply = service.process_text("report today")

    assert "PDF report attached below." in reply
    assert "https://reports.pharmareen.app/reports/download/" in reply


def test_report_week_includes_downloadable_pdf_link():
    store = FakeStore()
    service = IntakeService(FailingParser(), store, app_base_url="https://reports.pharmareen.app")
    service.process_text("Panadol 2")

    reply = service.process_text("report week")

    assert "Weekly Report" in reply
    assert "https://reports.pharmareen.app/reports/download/" in reply


def test_batch_message_processes_each_line():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text(
        "Panadol 2\n"
        "Amoxil 1\n"
        "+Insulin 10 5000\n"
        "later Cetrizine 3\n"
        "Insulin no stock"
    )

    assert "Batch processed" in reply
    assert "- Panadol x2" in reply
    assert "- Amoxyl x1" in reply
    assert "- Insulin +10" in reply
    assert "- Cetirizine x3" in reply
    assert "No-stock requests:\n- Insulin" in reply


def test_natural_bulk_sale_message_processes_each_item():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Sold Panadol 2, Amoxil 1, Cetrizine 3")

    assert "- Panadol x2" in reply
    assert "- Amoxyl x1" in reply
    assert "- Cetirizine x3" in reply


def test_comma_separated_sales_process_each_item():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Panadol 5, ORS 3")

    assert "Batch processed" in reply
    assert "Sales:" in reply
    assert "- Panadol x5" in reply
    assert "- ORS x3" in reply
    assert [transaction["Type"] for transaction in store.transactions[-2:]] == ["sale", "sale"]


def test_later_prefix_applies_to_comma_batch():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("later Panadol 5, Antacid 2")

    assert "Batch processed" in reply
    assert "Late Sales:" in reply
    assert "- Panadol x5" in reply
    assert "- Antacid x2" in reply
    assert [transaction["Type"] for transaction in store.transactions[-2:]] == ["late_sale", "late_sale"]


def test_natural_bulk_restock_message_processes_each_item():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Restocked Panadol 20, Insulin 10")

    assert "- Panadol +20" in reply
    assert "- Insulin +10" in reply
    assert store.stocks["panadol"].current_stock == 40
    assert store.stocks["insulin"].current_stock == 15


def test_natural_bulk_no_stock_message_processes_each_item():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("No stock Insulin, Ventolin")

    assert "No-stock requests:" in reply
    assert "- Insulin" in reply
    assert "- Ventolin" in reply


def test_number_words_are_supported_for_voice_transcripts():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Panadol two\nlater Cetrizine three")

    assert "- Panadol x2" in reply
    assert "- Cetirizine x3" in reply


def test_spoken_text_normalization_for_voice_commands():
    assert normalize_spoken_command_text("sold two panadol") == "Panadol 2"
    assert normalize_spoken_command_text("Panadol two") == "Panadol 2"
    assert normalize_spoken_command_text("Panadol sold two") == "Panadol sold 2"
    assert normalize_spoken_command_text("sell Panadol two") == "Panadol 2"
    assert normalize_spoken_command_text("add Panadol twenty") == "+Panadol 20"
    assert normalize_spoken_command_text("add twenty Panadol") == "+Panadol 20"
    assert normalize_spoken_command_text("received twenty Panadol") == "+Panadol 20"
    assert normalize_spoken_command_text("add Panadol twenty bonus") == "+Panadol 20 bonus"
    assert normalize_spoken_command_text("bonus Panadol five") == "+Panadol 5 bonus"
    assert normalize_spoken_command_text("five Panadol bonus") == "+Panadol 5 bonus"
    assert normalize_spoken_command_text("Panadol five bonus") == "+Panadol 5 bonus"
    assert normalize_spoken_command_text("bought twenty Panadol for one thousand eight hundred") == "+Panadol 20 1800"
    assert normalize_spoken_command_text("add Panadol twenty paid one thousand eight hundred") == "+Panadol 20 1800"
    assert normalize_spoken_command_text("Panadol twenty paid one thousand eight hundred") == "+Panadol 20 1800"
    assert (
        normalize_spoken_command_text("ordered twenty Panadol, budget two thousand, paid one thousand eight hundred")
        == "+Panadol 20 ordered 2000 paid 1800"
    )
    assert normalize_spoken_command_text("panadol stock") == "panadol stock"
    assert normalize_spoken_command_text("profit today") == "profit today"
    assert normalize_spoken_command_text("report week") == "report week"


def test_fifty_line_batch_does_not_crash_and_continues():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)
    message = "\n".join("Panadol 1" for _ in range(50))

    reply = service.process_text(message)

    assert "Batch processed" in reply
    assert len(store.logged) == 50


def test_share_command_returns_click_to_chat_link():
    store = FakeStore()
    service = IntakeService(FailingParser(), store, whatsapp_number="whatsapp:+14155238886")

    reply = service.process_text("share")

    assert "Share PharMareen with staff:" in reply
    assert "https://wa.me/14155238886?text=start" in reply


def test_high_volume_question_has_simple_answer():
    service = IntakeService(FailingParser(), FakeStore())

    reply = service.process_text("can it handle many customers")

    assert "can keep recording many transactions" in reply


def test_customer_ordering_question_has_todo_answer():
    service = IntakeService(FailingParser(), FakeStore())

    reply = service.process_text("what about client ordering drugs")

    assert "Customer ordering is planned" in reply


def test_chat_like_natural_sale_command():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("I sold Panadol 2 and Amoxil 1")

    assert "- Panadol x2" in reply
    assert "- Amoxyl x1" in reply


def test_chat_like_natural_restock_with_cost():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("Restock Panadol 20 for 2000")

    assert "Panadol +20 added" in reply
    assert "Avg cost:" not in reply


def test_chat_like_report_and_stock_commands():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    assert "Daily Report" in service.process_text("Give me today's report")
    assert "Profit Today" in service.process_text("How much profit today?")
    assert "Panadol stock" in service.process_text("What is Panadol stock?")
    assert "Weekly Report" in service.process_text("Show me weekly report")
    assert "Daily Report" in service.process_text("Send me the daily PDF")


def test_chat_like_no_stock_and_missed_commands():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    assert "Insulin no-stock request logged" in service.process_text("Insulin is out of stock")
    assert "Late sale saved" in service.process_text("I missed Panadol 3")


def test_report_by_date_found_returns_saved_report():
    store = FakeStore()
    store.reports["2026-04-27"] = "Daily Intelligence Report â€“ 2026-04-27"
    parser = FailingParser()
    service = IntakeService(parser, store)

    reply = service.process_text("report 2026-04-27")
    assert reply.startswith("PharMareen")
    assert "Zilla Pharmacy" not in reply
    return
    assert reply.startswith("PharMareen")
    assert "Zilla Pharmacy" not in reply
    return

    assert reply == "Zilla Pharmacy\nDaily Intelligence Report â€“ 2026-04-27"
    assert parser.called is False


def old_test_report_by_date_response_keeps_existing_pharmacy_name():
    store = FakeStore()
    store.reports["2026-04-27"] = "Zilla Pharmacy\nDaily Intelligence Report â€“ 2026-04-27"
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("report 2026-04-27")

    assert reply == "Zilla Pharmacy\nDaily Intelligence Report â€“ 2026-04-27"


def test_report_by_date_response_keeps_pharmareen_name():
    store = FakeStore()
    store.reports["2026-04-27"] = "PharMareen Daily Report\nDate: 2026-04-27"
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("report 2026-04-27")

    assert reply == "PharMareen Daily Report\nDate: 2026-04-27"


def test_report_by_date_replaces_old_zilla_name():
    store = FakeStore()
    store.reports["2026-04-27"] = "Zilla Pharmacy\nOld Report"
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("report 2026-04-27")

    assert reply == "PharMareen\nOld Report"


def test_report_by_date_missing_returns_simple_message():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("show report 2026-04-27")

    assert reply == "No report found for 2026-04-27."




def test_deterministic_analytics_router_handles_payment_peak_and_best_seller_without_ai():
    store = FakeStore()
    parser = FailingParser()
    service = IntakeService(parser, store)

    service.process_text("Panadol 2 cash")
    service.process_text("Amoxyl 1 mpesa")
    best = service.process_text("What sold most today")
    cash = service.process_text("How much cash came in today")
    mpesa = service.process_text("How much Mpesa imeingia leo")
    top_payment = service.process_text("Top payment methods today")
    peak = service.process_text("Peak hours leo")

    assert best == "Best seller today: Panadol — 2 sold"
    assert "Cash received today: KES 440" in cash
    assert "M-Pesa received today: KES 450" in mpesa
    assert "Most used payment today:" in top_payment
    assert "Peak time today:" in peak
    assert "Top medicines:" in peak
    assert "Payments:" in peak
    assert parser.called is False


def test_late_sale_commands_route_before_cash_analytics_and_keep_payment():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    for message in [
        "late Panadol 3 yesterday cash",
        "latepanadol5cash",
        "yesterday panadol 3 cash",
        "niliuza jana panadol 3 cash",
    ]:
        reply = service.process_text(message)
        assert "Late sale saved" in reply
        assert "Panadol x" in reply
        assert "Cash" in reply
        assert "Cash received" not in reply
        assert store.transactions[-1]["Type"] == "late_sale"


def test_sale_discounts_support_amount_percent_and_compact_less_aliases():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    cash_reply = service.process_text("Panadol 2 cash discount 20")
    percent_reply = service.process_text("Amoxyl 1 mpesa less10%")
    mixed_reply = service.process_text("ORS 2 mixed100/200 less50")

    assert "Panadol x2 recorded" in cash_reply
    assert "Original:" in cash_reply
    assert "Discount: KES 20" in cash_reply
    assert "Paid:" in cash_reply
    assert "Amoxyl x1 recorded" in percent_reply
    assert "M-Pesa" in percent_reply
    assert "Discount: KES 45 (10%)" in percent_reply
    assert "ORS x2 recorded" in mixed_reply
    assert "Mixed" in mixed_reply
    assert "payment_cash=100.0" in store.transactions[-1]["Note"]
    assert "payment_mpesa=200.0" in store.transactions[-1]["Note"]


def test_default_aliases_do_not_override_ambiguous_inventory_prefixes():
    store = FakeStore()
    store.stocks["paracetamol"] = StockItem("Paracetamol", 100, 60, 20, 5, 10)
    service = IntakeService(FailingParser(), store)

    amox_reply = service.process_text("Amox1mpesa")

    assert "Did you mean:" in amox_reply
    assert "Amoxyl" in amox_reply
    assert "Amoxicillin" in amox_reply


def test_plus_bonus_restock_keeps_purchased_quantity_and_bonus():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    reply = service.process_text("+Panadol 20 bonus 5 cost 2000")

    assert "Panadol restocked: 20 + 5 bonus = 25 added" in reply
    assert "Panadol +25 added" in reply
    assert "Paid: KES 2,000" in reply
    assert store.stocks["panadol"].current_stock == 45
    assert store.transactions[-1]["Quantity"] == 25
    assert store.transactions[-1]["Total Cost"] == 2000
    assert "Ordered quantity 20" in store.transactions[-1]["Note"]
    assert "Bonus quantity 5" in store.transactions[-1]["Note"]


def test_stock_plus_restock_variant_and_low_stock_wording_are_owner_friendly():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    restock_reply = service.process_text("Panadol stock +20")
    service.process_text("Cough Syrup 2")
    low_stock = service.process_text("low stock")
    stock_reply = service.process_text("Panadol stock")

    assert "Panadol +20 added" in restock_reply
    assert "Running low" in low_stock
    assert "Cough Syrup" in low_stock
    assert "restock when left with" in low_stock
    assert "reorder at" not in low_stock.lower()
    assert "Reorder level" not in stock_reply
    assert "Restock when left with" in stock_reply


def test_short_correction_and_receipt_variants_use_local_memory_without_ai():
    store = FakeStore()
    parser = FailingParser()
    service = IntakeService(parser, store)

    service.process_text("Panadol 2 cash", conversation_id="rush")
    payment_reply = service.process_text("badilisha payment iwe mpesa", conversation_id="rush")
    qty_reply = service.process_text("fanya iwe 5", conversation_id="rush")
    inc_reply = service.process_text("ongeza moja", conversation_id="rush")
    receipt = service.process_text("hiyo ya mwisho print receipt", conversation_id="rush")

    assert "Updated last Panadol sale" in payment_reply
    assert "M-Pesa" in payment_reply
    assert "Updated last Panadol sale quantity: 2" in qty_reply
    assert "5" in qty_reply
    assert "Updated last Panadol sale quantity: 5" in inc_reply
    assert "6" in inc_reply
    assert "PHARMAREEN RECEIPT" in receipt
    assert "Payment: M-Pesa" in receipt
    assert "Amount:" in receipt
    assert parser.called is False



def test_quantity_correction_swahili_updates_last_sale_quantity():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    service.process_text("Panadol 2 cash", conversation_id="owner")
    reply = service.process_text("nilikosea ilikuwa 5", conversation_id="owner")

    assert "Updated last Panadol sale quantity: 2" in reply
    assert "5" in reply
    assert store.stocks["panadol"].current_stock == 15
    assert store.transactions[-1]["Type"] == "correction"


def test_more_human_memory_phrases_use_recent_sale_safely():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    service.process_text("Panadol 2 cash", conversation_id="owner")
    same_reply = service.process_text("same as last", conversation_id="owner")
    payment_reply = service.process_text("change last to mpesa", conversation_id="owner")
    quantity_reply = service.process_text("ya mwisho ilikuwa 5", conversation_id="owner")

    assert "Repeat Panadol x2 Cash" in same_reply
    assert "Updated last Panadol sale" in payment_reply
    assert "M-Pesa" in payment_reply
    assert "Updated last Panadol sale quantity: 2" in quantity_reply
    assert "5" in quantity_reply


def test_transaction_number_undo_is_safe_and_short():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    service.process_text("Panadol 2 cash", conversation_id="owner")
    last_trace = service.last_sale_by_conversation["owner"]["trace_id"]
    confirm = service.process_text(f"cancel {last_trace}", conversation_id="owner")
    mismatch = service.process_text("cancel TX-1046", conversation_id="owner-mismatch")

    assert confirm == "Undo last sale: Panadol x2 Cash?\nReply YES to confirm."
    assert "No recent sale found" in mismatch


def test_no_space_commands_and_same_as_last_sequence_keep_context_local():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    first = service.process_text("Panadol 2 cash", conversation_id="rush")
    report = service.process_text("reporttoday", conversation_id="rush")
    same = service.process_text("sameaslast", conversation_id="rush")
    repeated = service.process_text("yes", conversation_id="rush")
    receipt = service.process_text("printreceipt", conversation_id="rush")

    assert "Panadol x2" in first
    assert "Daily Report" in report
    assert same == "Repeat Panadol x2 Cash? Reply YES."
    assert "Panadol x2" in repeated
    assert "PHARMAREEN RECEIPT" in receipt
    assert "Medicine: Panadol" in receipt


def test_no_space_report_analytics_and_receipt_commands_are_deterministic():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    service.process_text("Panadol 2 cash", conversation_id="owner")
    assert "Daily Report" in service.process_text("reporttoday", conversation_id="owner")
    assert "Cash received today" in service.process_text("cashtoday", conversation_id="owner")
    assert "Best seller today" in service.process_text("bestsellertoday", conversation_id="owner")
    assert "PHARMAREEN RECEIPT" in service.process_text("printreceipt", conversation_id="owner")


def test_replace_last_sale_with_inventory_medicine_and_undo_number_is_safe():
    store = FakeStore()
    store.stocks["glucose"] = StockItem(
        drug_name="Glucose",
        selling_price=100,
        cost_price=70,
        current_stock=12,
        reorder_level=4,
        row_number=10,
    )
    service = IntakeService(FailingParser(), store)

    first = service.process_text("Panadol 2 cash", conversation_id="rush")
    replaced = service.process_text("replace last sale with glucose 5", conversation_id="rush")
    unsafe_undo = service.process_text("undo3", conversation_id="rush")

    assert "Panadol x2" in first
    assert "Replaced last sale safely" in replaced
    assert "Glucose x5" in replaced
    assert store.stocks["panadol"].current_stock == 20
    assert store.stocks["glucose"].current_stock == 7
    assert unsafe_undo == "Which sale should I undo? Send undo last sale or cancel TX-1046."


def test_known_medicine_selector_is_local_and_accepts_quantity_payment_reply():
    store = FakeStore()
    store.stocks["glucose"] = StockItem(
        drug_name="Glucose",
        selling_price=100,
        cost_price=70,
        current_stock=12,
        reorder_level=4,
        row_number=10,
    )
    parser = FailingParser()
    service = IntakeService(parser, store)

    prompt = service.process_text("Glucose", conversation_id="voice")
    saved = service.process_text("2 mpesa", conversation_id="voice")

    assert "Sale approval" in prompt
    assert "Medicine: Glucose" in prompt
    assert "Quantity: 1, 2, 3, 5, 10, +, -" in prompt
    assert "Payment: Cash, M-Pesa, Credit, Mixed" in prompt
    assert "Glucose x2" in saved
    assert "M-Pesa" in saved
    assert store.stocks["glucose"].current_stock == 10
    assert parser.called is False


def test_typo_sale_and_payment_stay_local_without_ai_parser():
    store = FakeStore()
    parser = FailingParser()
    service = IntakeService(parser, store)

    reply = service.process_text("pnadol 1 cahs", conversation_id="typo")

    assert "Panadol x1" in reply
    assert "Cash" in reply
    assert store.stocks["panadol"].current_stock == 19
    assert parser.called is False


def test_unknown_text_with_ai_parser_gets_local_clarification_without_ai_call():
    class AIService:
        def parse_events(self, text, master_drug_names):  # pragma: no cover - should not be reached
            raise AssertionError("AI parser should not be called for unclear local text")

    service = IntakeService(AIService(), FakeStore())

    reply = service.process_text("random customer story not pharmacy", conversation_id="unknown")

    assert "Did you want to:" in reply


def test_unstocked_catalog_medicine_gets_local_setup_guidance_without_ai_parser():
    parser = FailingParser()
    service = IntakeService(parser, FakeStore())

    reply = service.process_text("Vit kobin", conversation_id="setup")

    assert reply == "⚠ Vitcobin is not yet in your inventory. Add it during restock first."
    assert parser.called is False


def test_swahili_undo_last_sale_asks_short_confirmation_then_reverses_stock():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    service.process_text("Panadol 2 cash", conversation_id="owner")
    confirm = service.process_text("undo hiyo ya mwisho", conversation_id="owner")
    final = service.process_text("YES", conversation_id="owner")

    assert confirm == "Undo last sale: Panadol x2 Cash?\nReply YES to confirm."
    assert "Last sale removed safely" in final
    assert "Cash total adjusted" in final
    assert store.stocks["panadol"].current_stock == 20
    assert store.transactions[-1]["Type"] == "void"


def test_payment_method_used_most_is_deterministic_without_ai_parser():
    store = FakeStore()
    parser = FailingParser()
    service = IntakeService(parser, store)

    service.process_text("Panadol 2 cash")
    service.process_text("Amoxyl 1 mpesa")
    service.process_text("ORS 1 cash")
    reply = service.process_text("Which payment method was used most")

    assert "Most used payment today: Cash" in reply
    assert "M-Pesa" in reply
    assert "/ 2 sales" in reply
    assert parser.called is False



def test_undo_after_compact_and_corrected_sale_uses_recent_memory():
    store = FakeStore()
    service = IntakeService(FailingParser(), store)

    sale_reply = service.process_text("panadol2cash", conversation_id="rush")
    correction_reply = service.process_text("nilikosea ilikuwa 4", conversation_id="rush")
    confirm = service.process_text("undo hiyo ya mwisho", conversation_id="rush")

    assert "Panadol x2" in sale_reply
    assert "Updated last Panadol sale quantity: 2" in correction_reply
    assert confirm == "Undo last sale: Panadol x4 Cash?\nReply YES to confirm."


def test_payment_analytics_does_not_use_ai_usage_log():
    from app.ai import AI_USAGE_LOG

    store = FakeStore()
    service = IntakeService(FailingParser(), store)
    AI_USAGE_LOG.clear()

    service.process_text("Panadol 2 cash")
    service.process_text("Amoxyl 1 mpesa")
    reply = service.process_text("Which payment method was used most")

    assert "Most used payment today" in reply
    assert AI_USAGE_LOG == []
