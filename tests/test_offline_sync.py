from __future__ import annotations

from app.services.offline_sync import OfflineSyncService


class FakeIntake:
    def __init__(self):
        self.messages = []

    def process_text(self, text):
        self.messages.append(text)
        return f"ok: {text}"


def test_offline_sale_syncs_correctly():
    intake = FakeIntake()
    service = OfflineSyncService(intake, set())

    result = service.sync_actions([
        {"action_id": "a1", "action_type": "sale", "drug_name": "Panadol", "quantity": 2}
    ])

    assert result["results"][0]["status"] == "synced"
    assert intake.messages == ["Panadol 2"]


def test_duplicate_action_id_does_not_double_count():
    intake = FakeIntake()
    service = OfflineSyncService(intake, set())
    action = {"action_id": "a1", "action_type": "sale", "drug_name": "Panadol", "quantity": 2}

    first = service.sync_actions([action])
    second = service.sync_actions([action])

    assert first["results"][0]["status"] == "synced"
    assert second["results"][0]["status"] == "already_synced"
    assert intake.messages == ["Panadol 2"]


def test_failed_action_returns_failed_status():
    service = OfflineSyncService(FakeIntake(), set())

    result = service.sync_actions([
        {"action_id": "bad1", "action_type": "unknown", "drug_name": "Panadol", "quantity": 1}
    ])

    assert result["results"][0]["status"] == "failed"
