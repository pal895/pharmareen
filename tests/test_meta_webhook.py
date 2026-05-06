from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main
from app.providers.meta_whatsapp import NormalizedMessage
from app.routes import meta_webhook


class FakeMetaClient:
    def __init__(self):
        self.sent = []

    def verify_webhook(self, mode, token, challenge):
        return challenge if mode == "subscribe" and token == "secret" else None

    def normalize_webhook(self, payload):
        return [
            NormalizedMessage(
                provider="meta",
                from_phone="254700000000",
                message_id="wamid.test",
                type="text",
                text="Panadol 2",
                timestamp="123",
                raw={},
            )
        ]

    async def send_text(self, to_phone, body):
        self.sent.append((to_phone, body))


class FakeRouter:
    async def handle(self, message, media_bytes=None, content_type=None):
        from app.services.message_router import RouterResult

        return RouterResult("Logged sale", saved=True, action_type="intake")


def test_meta_get_webhook_verification_works(monkeypatch):
    monkeypatch.setattr(meta_webhook, "get_meta_client", lambda: FakeMetaClient())

    with TestClient(main.app) as client:
        response = client.get(
            "/webhooks/meta/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "secret",
                "hub.challenge": "challenge-code",
            },
        )

    assert response.status_code == 200
    assert response.text == "challenge-code"


def test_meta_get_webhook_rejects_bad_token(monkeypatch):
    monkeypatch.setattr(meta_webhook, "get_meta_client", lambda: FakeMetaClient())

    with TestClient(main.app) as client:
        response = client.get(
            "/webhooks/meta/whatsapp",
            params={"hub.mode": "subscribe", "hub.verify_token": "bad", "hub.challenge": "x"},
        )

    assert response.status_code == 403


def test_meta_post_webhook_returns_200_and_sends_reply(monkeypatch):
    fake_client = FakeMetaClient()
    monkeypatch.setattr(meta_webhook, "get_meta_client", lambda: fake_client)
    monkeypatch.setattr(meta_webhook, "get_message_router", lambda: FakeRouter())

    with TestClient(main.app) as client:
        response = client.post("/webhooks/meta/whatsapp", json={"entry": [{"changes": [{"value": {"messages": [{}]}}]}]})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert fake_client.sent == [("254700000000", "Logged sale")]


def test_meta_provider_has_no_twilio_dependency():
    import inspect
    import app.providers.meta_whatsapp as meta_provider

    assert "twilio" not in inspect.getsource(meta_provider).lower()


def test_default_dev_verify_token_works_without_env_file():
    from app.config import Settings
    from app.providers.meta_whatsapp import MetaWhatsAppClient

    client = MetaWhatsAppClient(Settings(_env_file=None))

    assert client.verify_webhook("subscribe", "test_verify_token", "12345") == "12345"


def test_meta_post_ignores_unexpected_payload_shape(monkeypatch):
    monkeypatch.setattr(meta_webhook, "get_meta_client", lambda: FakeMetaClient())
    monkeypatch.setattr(meta_webhook, "get_message_router", lambda: FakeRouter())

    with TestClient(main.app) as client:
        response = client.post("/webhooks/meta/whatsapp", json={"entry": ["bad-entry"]})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_existing_public_routes_still_work():
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/status").status_code == 200
        assert client.get("/offline-test").status_code == 200
        assert client.get("/offline-html-test").status_code == 200
        response = client.get("/offline_app/index.html")

    assert response.status_code == 200
    assert "PharMareen Offline" in response.text