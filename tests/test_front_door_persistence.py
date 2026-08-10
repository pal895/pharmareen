from __future__ import annotations

import json

import pytest

from app.services.front_door_persistence import GoogleSheetsFrontDoorStore
from app import main


class Worksheet:
    def __init__(self, records=None):
        self.records = records or []
        self.updated = None

    def get_all_records(self):
        return self.records

    def clear(self):
        pass

    def update(self, cell, rows):
        self.updated = (cell, rows)


def store_with(ws):
    store = object.__new__(GoogleSheetsFrontDoorStore)
    store._worksheet = lambda: ws
    return store


def test_front_door_store_round_trips_platform_and_pharmacy_state():
    ws = Worksheet([
        {"Pharmacy ID": "__platform__", "State JSON": json.dumps({"community_counter": 2, "used_nonces": ["digest"], "pending_entries": {"nonce-digest": {"phone_key_digest": "phone-digest", "status": "active", "expires_at": 9999999999}}})},
        {"Pharmacy ID": "pharmacy-a", "State JSON": json.dumps({"pharmacy_id": "pharmacy-a", "members": {}})},
    ])
    loaded = store_with(ws).load()
    assert loaded["community_counter"] == 2
    assert loaded["used_nonces"] == ["digest"]
    assert loaded["pending_entries"]["nonce-digest"]["phone_key_digest"] == "phone-digest"
    assert loaded["pharmacies"]["pharmacy-a"]["pharmacy_id"] == "pharmacy-a"


def test_front_door_store_rejects_cross_pharmacy_binding_and_raw_secret_fields():
    broken = Worksheet([{"Pharmacy ID": "pharmacy-a", "State JSON": json.dumps({"pharmacy_id": "pharmacy-b"})}])
    with pytest.raises(RuntimeError):
        store_with(broken).load()
    safe = store_with(Worksheet())
    with pytest.raises(ValueError):
        safe.save({"pharmacies": {"pharmacy-a": {"pharmacy_id": "pharmacy-a", "raw_token": "secret"}}})


def test_front_door_store_serializes_only_bounded_digest_state():
    ws = Worksheet()
    store_with(ws).save({"community_counter": 1, "used_nonces": ["digest"], "pharmacies": {"pharmacy-a": {"pharmacy_id": "pharmacy-a", "phone_key_digest": "abc", "devices": {}}}})
    serialized = repr(ws.updated)
    assert "phone_key_digest" in serialized
    assert "raw_phone" not in serialized


def test_front_door_store_keeps_in_progress_identity_for_cross_worker_retry():
    ws = Worksheet()
    store_with(ws).save({"pending_entries": {"nonce": {
        "status": "provisioning", "expires_at": 9999999999,
        "identity_mode": "ms20_owned", "pharmacy_id": "pharmacy-stable", "owner_id": "owner-stable",
    }}, "pharmacies": {}})
    serialized = repr(ws.updated)
    assert "pharmacy-stable" in serialized and "owner-stable" in serialized


def test_worker_front_door_initialization_retries_after_transient_startup_failure(monkeypatch):
    attempts = []

    class Store:
        def __init__(self, _settings):
            pass

        def load(self):
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("temporary worksheet race")
            return {"version": 1, "pharmacies": {}}

    monkeypatch.setattr(main, "front_door_registry", None)
    monkeypatch.setattr(main, "has_google_credentials", lambda _settings: True)
    monkeypatch.setattr(main, "owner_auth_sheet_id", lambda _settings: "admin-workbook")
    monkeypatch.setattr(main, "GoogleSheetsFrontDoorStore", Store)
    monkeypatch.setenv("MS20_FRONT_DOOR_SIGNING_KEY", "worker-retry-front-door-key-123456789")
    with pytest.raises(RuntimeError, match="temporary worksheet race"):
        main.get_front_door_registry()
    recovered = main.get_front_door_registry()
    assert recovered is main.front_door_registry
    assert len(attempts) == 2


def test_customer_entry_signing_is_independent_from_optional_routing_key(monkeypatch):
    class Store:
        def __init__(self, _settings):
            pass
        def load(self):
            return {"version": 1, "pharmacies": {}}

    monkeypatch.setattr(main, "front_door_registry", None)
    monkeypatch.setattr(main, "has_google_credentials", lambda _settings: True)
    monkeypatch.setattr(main, "owner_auth_sheet_id", lambda _settings: "admin-workbook")
    monkeypatch.setattr(main, "GoogleSheetsFrontDoorStore", Store)
    monkeypatch.delenv("PHARMAREEN_TENANT_ROUTING_KEY", raising=False)
    monkeypatch.setenv("MS20_FRONT_DOOR_SIGNING_KEY", "independent-ms20-front-door-key-123456789")
    registry = main.get_front_door_registry()
    assert registry.signer is not None


def test_customer_entry_fails_before_rendering_fake_setup_when_signing_is_missing(monkeypatch):
    monkeypatch.setattr(main, "front_door_registry", None)
    monkeypatch.setattr(main, "has_google_credentials", lambda _settings: True)
    monkeypatch.setattr(main, "owner_auth_sheet_id", lambda _settings: "admin-workbook")
    monkeypatch.delenv("PHARMAREEN_TENANT_ROUTING_KEY", raising=False)
    monkeypatch.delenv("MS20_FRONT_DOOR_SIGNING_KEY", raising=False)
    with pytest.raises(RuntimeError, match="front-door signing is not configured"):
        main.get_front_door_registry()
