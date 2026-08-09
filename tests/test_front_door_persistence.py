from __future__ import annotations

import json

import pytest

from app.services.front_door_persistence import GoogleSheetsFrontDoorStore


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
        {"Pharmacy ID": "__platform__", "State JSON": json.dumps({"community_counter": 2, "used_nonces": ["digest"]})},
        {"Pharmacy ID": "pharmacy-a", "State JSON": json.dumps({"pharmacy_id": "pharmacy-a", "members": {}})},
    ])
    loaded = store_with(ws).load()
    assert loaded["community_counter"] == 2
    assert loaded["used_nonces"] == ["digest"]
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
