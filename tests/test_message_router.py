from __future__ import annotations

import pytest

from app.domain import StockItem
from app.providers.meta_whatsapp import NormalizedMessage
from app.services.batch_service import BatchRecord, InMemoryBatchStore
from app.services.message_router import MessageRouter
from app.services.pending_actions import pending_actions


class FakeIntake:
    def __init__(self):
        self.messages = []

    def process_text(self, text):
        self.messages.append(text)
        return f"processed: {text}"


class FakeStore(InMemoryBatchStore):
    def find_stock(self, drug_name):
        if drug_name.lower() == "panadol":
            return StockItem("Panadol", selling_price=220, cost_price=140, current_stock=65, reorder_level=10)
        return None


@pytest.mark.anyio
async def test_text_sale_routes_to_existing_intake_logic():
    intake = FakeIntake()
    router = MessageRouter(intake, FakeStore())

    result = await router.handle(NormalizedMessage("meta", "2547", "wamid.1", "text", text="Panadol sold 2"))

    assert result.saved is True
    assert result.reply == "processed: Panadol sold 2"
    assert intake.messages == ["Panadol sold 2"]


@pytest.mark.anyio
async def test_drug_name_only_returns_drug_card():
    store = FakeStore()
    store.append_batch(BatchRecord("B1", "Panadol", 20, 15, expiry_date="2026-03-01"))
    store.append_batch(BatchRecord("B2", "Panadol", 50, 50, expiry_date="2027-01-01"))
    router = MessageRouter(FakeIntake(), store)

    result = await router.handle(NormalizedMessage("meta", "2547", "wamid.2", "text", text="Panadol"))

    assert "Panadol" in result.reply
    assert "Stock left: 65" in result.reply
    assert "Batches:" in result.reply
    assert "2026-03-01" in result.reply


@pytest.mark.anyio
async def test_low_risk_report_request_saves_automatically():
    intake = FakeIntake()
    router = MessageRouter(intake, FakeStore())

    result = await router.handle(NormalizedMessage("meta", "2547", "wamid.3", "text", text="profit today"))

    assert result.saved is True
    assert result.requires_confirmation is False
