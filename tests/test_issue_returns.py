from __future__ import annotations

import pytest

from app.providers.meta_whatsapp import NormalizedMessage
from app.services.batch_service import InMemoryBatchStore
from app.services.message_router import MessageRouter
from app.services.pending_actions import pending_actions


class FakeIntake:
    def process_text(self, text):
        return "processed"


@pytest.mark.anyio
async def test_bad_drug_does_not_save_without_confirmation():
    store = InMemoryBatchStore()
    router = MessageRouter(FakeIntake(), store)
    pending_actions.clear("2547")

    result = await router.handle(NormalizedMessage("meta", "2547", "wamid.1", "text", text="Panadol bad"))

    assert result.requires_confirmation is True
    assert store.issues == []
    assert "Reply YES" in result.reply


@pytest.mark.anyio
async def test_yes_commits_pending_bad_drug_issue():
    store = InMemoryBatchStore()
    router = MessageRouter(FakeIntake(), store)
    pending_actions.clear("2547")
    await router.handle(NormalizedMessage("meta", "2547", "wamid.1", "text", text="Panadol bad"))

    result = await router.handle(NormalizedMessage("meta", "2547", "wamid.2", "text", text="YES"))

    assert result.saved is True
    assert store.issues


@pytest.mark.anyio
async def test_return_does_not_save_until_confirmed_and_cancel_discards():
    store = InMemoryBatchStore()
    router = MessageRouter(FakeIntake(), store)
    pending_actions.clear("2548")

    first = await router.handle(NormalizedMessage("meta", "2548", "wamid.3", "text", text="Return Panadol"))
    second = await router.handle(NormalizedMessage("meta", "2548", "wamid.4", "text", text="CANCEL"))

    assert first.requires_confirmation is True
    assert "Cancelled" in second.reply
    assert store.returns == []
