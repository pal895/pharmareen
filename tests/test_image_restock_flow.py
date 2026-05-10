from __future__ import annotations

import pytest

from app.providers.meta_whatsapp import NormalizedMessage
from app.services.batch_service import InMemoryBatchStore
from app.services.image_restock import ImageRestockExtraction, ImageRestockService
from app.services.message_router import MessageRouter
from app.services.pending_actions import pending_actions


class FakeImageService(ImageRestockService):
    def __init__(self, store):
        super().__init__(store=store)
        self.queued = []

    def extract(self, image_bytes, content_type=None):
        return ImageRestockExtraction(
            items=[{"drug_name": "Panadol 500mg", "quantity": "10 boxes", "expiry_date": "Jan 2027"}],
            confidence=0.9,
        )

    def queue_for_review(self, sender, extraction, raw=None):
        self.queued.append((sender, extraction))


class FakeIntake:
    def process_text(self, text):
        return "processed"


@pytest.mark.anyio
async def test_image_restock_goes_to_review_queue_not_direct_stock():
    store = InMemoryBatchStore()
    image_service = FakeImageService(store)
    router = MessageRouter(FakeIntake(), store, image_service=image_service)
    pending_actions.clear("2547")

    result = await router.handle(
        NormalizedMessage("meta", "2547", "wamid.image", "image", media_id="media1"),
        media_bytes=b"image",
        content_type="image/jpeg",
    )

    assert result.requires_confirmation is True
    assert "Confirm restock?" in result.reply
    assert image_service.queued
    assert store.batches == []


@pytest.mark.anyio
async def test_cancel_discards_pending_image_restock():
    store = InMemoryBatchStore()
    image_service = FakeImageService(store)
    router = MessageRouter(FakeIntake(), store, image_service=image_service)
    pending_actions.clear("2547")
    await router.handle(NormalizedMessage("meta", "2547", "wamid.image", "image"), media_bytes=b"image")

    result = await router.handle(NormalizedMessage("meta", "2547", "wamid.cancel", "text", text="cancel"))

    assert "Cancelled" in result.reply
    assert store.batches == []
