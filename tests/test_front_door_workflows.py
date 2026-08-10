from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.front_door import FrontDoorRegistry, MemoryFrontDoorStore, SignedEntryContext
from app.front_door_workflows import FrontDoorWorkflowService
from app.owner_auth import OwnerAuthService
from app.pharmacy_registry import RegistryWriteResult
from app import main


def services():
    store = MemoryFrontDoorStore()
    registry = FrontDoorRegistry(store, SignedEntryContext("front-door-workflow-signing-key-123456", ttl_seconds=600))
    registry.initialize_pharmacy(pharmacy_id="pharmacy-a", owner_id="owner-a", owner_name="Owner", owner_phone_key="2547001")
    return registry, FrontDoorWorkflowService(registry, session_ttl_seconds=60), store


def join_staff(registry, workflows, *, role="cashier", identity="verified:staff-a", device="phone-a"):
    token = registry.issue_invitation("pharmacy-a", owner_id="owner-a", role=role, display_name="Mary")
    return workflows.accept_staff_invitation(token, verified_identity=identity, pin="Staff1234", device_key=device, now=100)


def test_invited_staff_joins_existing_pharmacy_and_session_survives_service_restart():
    registry, workflows, store = services()
    joined = join_staff(registry, workflows)
    restarted = FrontDoorWorkflowService(FrontDoorRegistry(store), session_ttl_seconds=60)
    actor = restarted.authenticate_staff(joined["session"], pharmacy_id="pharmacy-a", device_key="phone-a", now=120)
    assert actor == {"pharmacy_id": "pharmacy-a", "actor_id": joined["actor_id"], "role": "cashier", "display_name": "Mary"}
    assert list(store.load()["pharmacies"]) == ["pharmacy-a"]


def test_invitation_replay_wrong_device_expiry_removal_and_session_revocation_fail_closed():
    registry, workflows, _ = services()
    token = registry.issue_invitation("pharmacy-a", owner_id="owner-a", role="pharmacist", display_name="Mary")
    joined = workflows.accept_staff_invitation(token, verified_identity="verified:staff-a", pin="Staff1234", device_key="phone-a", now=100)
    with pytest.raises(ValueError):
        workflows.accept_staff_invitation(token, verified_identity="verified:staff-b", pin="Staff1234", device_key="phone-b", now=100)
    with pytest.raises(ValueError, match="device"):
        workflows.authenticate_staff(joined["session"], pharmacy_id="pharmacy-a", device_key="other-phone", now=110)
    with pytest.raises(ValueError, match="session"):
        workflows.authenticate_staff(joined["session"], pharmacy_id="pharmacy-a", device_key="phone-a", now=161)
    replacement = workflows.sign_in_staff("pharmacy-a", verified_identity="verified:staff-a", pin="Staff1234", device_key="phone-a", now=200)
    digest = next(key for key, value in workflows.registry.store.load()["pharmacies"]["pharmacy-a"]["sessions"].items() if value["created_at"] == 200)
    workflows.revoke_session("pharmacy-a", owner_id="owner-a", session_digest=digest)
    with pytest.raises(ValueError, match="session"):
        workflows.authenticate_staff(replacement, pharmacy_id="pharmacy-a", device_key="phone-a", now=201)
    registry.remove_member("pharmacy-a", owner_id="owner-a", actor_id=joined["actor_id"])
    with pytest.raises(ValueError):
        workflows.sign_in_staff("pharmacy-a", verified_identity="verified:staff-a", pin="Staff1234", device_key="phone-a")


def test_staff_identity_and_sessions_are_tenant_and_pharmacy_isolated():
    registry, workflows, _ = services()
    registry.initialize_pharmacy(pharmacy_id="pharmacy-b", owner_id="owner-b", owner_name="Other", owner_phone_key="2547002")
    joined = join_staff(registry, workflows)
    with pytest.raises(ValueError):
        workflows.authenticate_staff(joined["session"], pharmacy_id="pharmacy-b", device_key="phone-a", now=110)
    with pytest.raises(ValueError):
        workflows.sign_in_staff("pharmacy-b", verified_identity="verified:staff-a", pin="Staff1234", device_key="phone-a")


def test_quick_pin_requires_primary_verification_and_stays_device_bound():
    registry, workflows, store = services()
    registry.bind_device("pharmacy-a", actor_id="owner-a", device_key="owner-phone")
    with pytest.raises(ValueError):
        workflows.configure_quick_pin("pharmacy-a", actor_id="owner-a", device_key="owner-phone", primary_verified=False, quick_pin="1234")
    workflows.configure_quick_pin("pharmacy-a", actor_id="owner-a", device_key="owner-phone", primary_verified=True, quick_pin="1234")
    device = next(iter(store.load()["pharmacies"]["pharmacy-a"]["devices"].values()))
    assert device["quick_pin_trust"] == "active"
    assert device["quick_pin_hash"] != "1234"
    with pytest.raises(ValueError):
        workflows.configure_quick_pin("pharmacy-a", actor_id="owner-a", device_key="other-phone", primary_verified=True, quick_pin="1234")


def test_loyalty_is_pharmacy_pooled_capped_and_idempotent_across_staff_devices():
    registry, workflows, store = services()
    joined = join_staff(registry, workflows)
    first = workflows.credit_loyalty("pharmacy-a", actor_id=joined["actor_id"], event_key="first-use", coins=40, reason="First useful workflow")
    duplicate = workflows.credit_loyalty("pharmacy-a", actor_id=joined["actor_id"], event_key="first-use", coins=40, reason="First useful workflow")
    second_device = workflows.credit_loyalty("pharmacy-a", actor_id=joined["actor_id"], event_key="first-use", coins=40, reason="First useful workflow")
    assert first == {"credited": True, "coins": 40, "balance": 40}
    assert duplicate == second_device == {"credited": False, "balance": 40}
    assert store.load()["pharmacies"]["pharmacy-a"]["loyalty"]["balance"] == 40


def test_community_uses_one_pharmacy_identity_and_owner_moderation():
    registry, workflows, store = services()
    joined = join_staff(registry, workflows)
    with pytest.raises(ValueError, match="Owner posting"):
        workflows.community_post("pharmacy-a", actor_id=joined["actor_id"], text="Stock discussion")
    post = workflows.community_post("pharmacy-a", actor_id="owner-a", text="  Pharmacy operations question  ", kind="question")
    workflows.moderate_post("pharmacy-a", owner_id="owner-a", post_id=post["post_id"], action="restrict")
    pharmacy = store.load()["pharmacies"]["pharmacy-a"]
    assert pharmacy["community"]["community_id"] == "001"
    assert pharmacy["community"]["posts"][0]["status"] == "restricted"


def test_billing_summary_counts_active_members_not_devices_and_makes_unqualified_state_truthful():
    registry, workflows, _ = services()
    joined = join_staff(registry, workflows)
    registry.bind_device("pharmacy-a", actor_id=joined["actor_id"], device_key="replacement-phone")
    summary = workflows.billing_summary("pharmacy-a", actor_id="owner-a")
    assert summary["active_seats"] == 2
    assert summary["device_count_is_seat_count"] is False
    assert summary["replacement_devices_add_seat"] is False
    assert summary["commercially_qualified"] is False
    assert summary["subscription_status"] == "unqualified"
    assert summary["may_redeem"] is True


def test_channel_verified_new_pharmacy_creates_one_tenant_owner_session_and_front_door(monkeypatch):
    registry = FrontDoorRegistry(MemoryFrontDoorStore(), SignedEntryContext("new-pharmacy-signing-key-which-is-long-123"))
    entry = registry.issue_new_pharmacy_context(verified_phone_key="254700000777")
    records = []

    class PharmacyRegistry:
        def register_pharmacy(self, details):
            record = {**details, "pharmacy_id": "afya-777"}
            records.append(record)
            return RegistryWriteResult(True, record, True, "created")

    auth = OwnerAuthService()
    monkeypatch.setattr(main, "front_door_registry", registry)
    monkeypatch.setattr(main, "get_pharmacy_registry", lambda: PharmacyRegistry())
    monkeypatch.setattr(main, "owner_auth_service", auth)
    with TestClient(main.app, base_url="https://ms20.test") as client:
        response = client.post("/api/ms20/front-door/new-pharmacy", json={
            "entry": entry, "phone": "+254700000777", "pharmacy_name": "Afya Chemist",
            "owner_name": "Njeri", "location": "Nakuru", "pin": "Owner1234",
            "terms_version": main.MS20_TERMS_VERSION, "privacy_version": main.MS20_PRIVACY_VERSION,
        })
    assert response.status_code == 200
    assert response.json()["pharmacy_id"] == "afya-777"
    assert response.cookies.get("ms20_owner_session")
    pharmacy = registry.store.load()["pharmacies"]["afya-777"]
    assert pharmacy["owner_id"].startswith("owner_") and "254700000777" not in pharmacy["owner_id"]
    assert pharmacy["compliance"]["terms_version"] == main.MS20_TERMS_VERSION
    assert len(records) == 1


def test_shared_link_creates_ms20_owned_pharmacy_and_owner_without_messaging_identity(monkeypatch):
    registry = FrontDoorRegistry(MemoryFrontDoorStore(), SignedEntryContext("public-start-signing-key-which-is-long-123"))
    records = []
    class PharmacyRegistry:
        def register_pharmacy(self, details):
            records.append(details)
            return RegistryWriteResult(True, details, True, "created")
    monkeypatch.setattr(main, "front_door_registry", registry)
    monkeypatch.setattr(main, "get_pharmacy_registry", lambda: PharmacyRegistry())
    monkeypatch.setattr(main, "owner_auth_service", OwnerAuthService())
    with TestClient(main.app, base_url="https://ms20.test") as client:
        page = client.get("/start")
        terms = client.get("/terms")
        privacy = client.get("/privacy")
        started = client.post("/api/ms20/front-door/start")
        created = client.post("/api/ms20/front-door/new-pharmacy", json={
            "entry": started.json()["entry"], "pharmacy_name": "Independent Chemist",
            "owner_name": "Owner", "location": "Nairobi", "pin": "Owner1234",
            "terms_version": main.MS20_TERMS_VERSION, "privacy_version": main.MS20_PRIVACY_VERSION,
        })
        legacy_verify = client.post("/api/ms20/front-door/verify", json={})
    assert page.status_code == 200
    assert "whatsapp" not in page.text.lower() and "verification code" not in page.text.lower()
    assert "Contact phone <small>(optional)" in page.text and "Primary Owner PIN" in page.text
    assert "at least 8 characters, including a letter and a number" in page.text
    assert "later 4-digit Quick PIN" in page.text and "show.onclick" in page.text
    assert "href='/terms'" in page.text and "href='/privacy'" in page.text
    assert terms.status_code == privacy.status_code == 200
    assert main.MS20_TERMS_VERSION in terms.text and main.MS20_PRIVACY_VERSION in privacy.text
    assert "Optional contact phone" in privacy.text and "does not define pharmacy identity" in privacy.text
    assert started.status_code == 200 and created.status_code == 200 and legacy_verify.status_code == 410
    assert created.cookies.get("ms20_owner_session")
    assert records[0]["owner_id"].startswith("owner_") and "254" not in records[0]["owner_id"]
    assert records[0]["pharmacy_id"].startswith("pharmacy_")


def test_shared_link_resumes_initialized_matching_pharmacy_without_duplicate(monkeypatch):
    registry = FrontDoorRegistry(MemoryFrontDoorStore(), SignedEntryContext("resume-signing-key-which-is-long-enough-123"))
    existing = {
        "pharmacy_id": "pharmacy_existing", "owner_id": "owner_existing",
        "pharmacy_name": "Mwangaza test pharmacy 0809", "owner_name": "Pal",
        "location": "Nairobi", "phone_number": "", "phone": "",
        "notes": "registered_by_live_onboarding", "status": "active", "active": "yes",
    }
    auth = OwnerAuthService()
    auth.initialize_first_owner(existing, "Owner1234", now=100)
    class PharmacyRegistry:
        def list_records(self):
            return [existing]
        def register_pharmacy(self, details):
            raise AssertionError("resume must not create a duplicate")
    monkeypatch.setattr(main, "front_door_registry", registry)
    monkeypatch.setattr(main, "get_pharmacy_registry", lambda: PharmacyRegistry())
    monkeypatch.setattr(main, "owner_auth_service", auth)
    with TestClient(main.app, base_url="https://ms20.test") as client:
        entry = client.post("/api/ms20/front-door/start").json()["entry"]
        response = client.post("/api/ms20/front-door/new-pharmacy", json={
            "entry": entry, "pharmacy_name": existing["pharmacy_name"],
            "owner_name": "Pal", "location": "Nairobi", "pin": "Owner1234",
            "terms_version": main.MS20_TERMS_VERSION, "privacy_version": main.MS20_PRIVACY_VERSION,
        })
    assert response.status_code == 200
    assert registry.store.load()["pharmacies"]["pharmacy_existing"]["owner_id"] == "owner_existing"


def test_independent_start_does_not_require_durable_store_until_create_claim():
    class Store:
        def __init__(self):
            self.value = {"version": 1, "community_counter": 0, "pharmacies": {}, "used_nonces": []}
            self.loads = 0
            self.saves = 0
        def load(self):
            self.loads += 1
            return self.value.copy()
        def save(self, value):
            self.saves += 1
            self.value = value

    store = Store()
    registry = FrontDoorRegistry(store, SignedEntryContext("deferred-claim-signing-key-which-is-long-123"))
    entry = registry.issue_independent_new_pharmacy_context()
    assert store.loads == store.saves == 0

    first = registry.claim_independent_new_pharmacy_context(entry)
    second = registry.claim_independent_new_pharmacy_context(entry)
    assert first == second
    assert first["pharmacy_id"].startswith("pharmacy_")
    assert first["owner_id"].startswith("owner_")
    assert store.loads == store.saves == 2


def test_same_verified_owner_phone_can_hold_isolated_credentials_for_two_pharmacies():
    auth = OwnerAuthService()
    owner_a = {"pharmacy_id": "pharmacy-a", "pharmacy_name": "A", "owner_name": "Owner", "phone_number": "+254700000777"}
    owner_b = {"pharmacy_id": "pharmacy-b", "pharmacy_name": "B", "owner_name": "Owner", "phone_number": "+254700000777"}
    auth.initialize_first_owner(owner_a, "OwnerA123", now=100)
    auth.initialize_first_owner(owner_b, "OwnerB123", now=100)
    _, session_a = auth.sign_in_with_pin(owner_a["phone_number"], "OwnerA123", pharmacy_id="pharmacy-a", now=101)
    _, session_b = auth.sign_in_with_pin(owner_b["phone_number"], "OwnerB123", pharmacy_id="pharmacy-b", now=101)
    assert session_a.pharmacy_id == "pharmacy-a" and session_b.pharmacy_id == "pharmacy-b"
    with pytest.raises(Exception):
        auth.sign_in_with_pin(owner_a["phone_number"], "OwnerA123", now=101)


def test_owner_invitation_and_staff_join_routes_are_one_use_and_do_not_create_a_tenant(monkeypatch):
    registry, _, store = services()
    monkeypatch.setattr(main, "front_door_registry", registry)
    main.app.dependency_overrides[main.require_owner_actor] = lambda: main.ActorContext(pharmacy_id="pharmacy-a", actor_id="owner-a", role="owner")
    try:
        with TestClient(main.app, base_url="https://ms20.test") as client:
            invited = client.post("/api/ms20/front-door/invitations", json={"role": "cashier", "display_name": "Mary"})
            entry = invited.json()["join_path"].split("entry=", 1)[1]
            from urllib.parse import unquote
            entry = unquote(entry)
            joined = client.post("/api/ms20/front-door/staff/join", json={"entry": entry, "pin": "Staff1234", "device_key": "phone-a"})
            replay = client.post("/api/ms20/front-door/staff/join", json={"entry": entry, "pin": "Staff1234", "device_key": "phone-b"})
    finally:
        main.app.dependency_overrides.pop(main.require_owner_actor, None)
    assert invited.status_code == 200
    assert joined.status_code == 200
    assert joined.cookies.get("ms20_staff_session")
    assert replay.status_code == 400
    assert list(store.load()["pharmacies"]) == ["pharmacy-a"]


def test_customer_visible_entry_pages_are_one_form_plain_language_and_no_internal_ids(monkeypatch):
    registry, _, _ = services()
    monkeypatch.setattr(main, "front_door_registry", registry)
    main.app.dependency_overrides[main.require_owner_actor] = lambda: main.ActorContext(pharmacy_id="pharmacy-a", actor_id="owner-a", role="owner")
    try:
        with TestClient(main.app, base_url="https://ms20.test") as client:
            new_page = client.get("/main-app/new-pharmacy?entry=signed-context")
            join_page = client.get("/main-app/join?entry=signed-invitation")
            access_page = client.get("/main-app/access")
    finally:
        main.app.dependency_overrides.pop(main.require_owner_actor, None)
    assert new_page.status_code == join_page.status_code == access_page.status_code == 200
    assert "Create your pharmacy" in new_page.text and new_page.text.count("<form") == 1
    assert "never creates another pharmacy" in join_page.text and join_page.text.count("<form") == 1
    assert "Invite staff" in access_page.text and "Commercial qualification pending" in access_page.text
    assert "pharmacy-a" not in new_page.text + join_page.text + access_page.text


def test_joined_staff_session_bootstraps_the_same_established_pharmacy_on_a_fresh_device(monkeypatch):
    registry, _, _ = services()
    monkeypatch.setattr(main, "front_door_registry", registry)
    monkeypatch.setattr(main, "first_owner_registry_record", lambda _request: {"pharmacy_id": "pharmacy-a", "owner_id": "owner-a", "owner_name": "Owner", "phone_number": "+2547001"})

    class Store:
        is_available = True
        def get_ms20_operations_state(self, pharmacy_id):
            return {"initialized": True, "catalog": [{"name": "Panadol", "stockLeft": 4}]}

    monkeypatch.setattr(main, "get_sheet_store", lambda: Store())
    main.app.dependency_overrides[main.require_owner_actor] = lambda: main.ActorContext(pharmacy_id="pharmacy-a", actor_id="owner-a", role="owner")
    try:
        with TestClient(main.app, base_url="https://ms20.test") as client:
            invitation = client.post("/api/ms20/front-door/invitations", json={"role": "pharmacist", "display_name": "Mary"}).json()["join_path"]
            from urllib.parse import unquote
            entry = unquote(invitation.split("entry=", 1)[1])
            assert client.post("/api/ms20/front-door/staff/join", json={"entry": entry, "pin": "Staff1234", "device_key": "fresh-phone"}).status_code == 200
            bootstrap = client.get("/api/ms20/operations/bootstrap")
    finally:
        main.app.dependency_overrides.pop(main.require_owner_actor, None)
    assert bootstrap.status_code == 200
    assert bootstrap.json()["operations_initialized"] is True
    assert bootstrap.json()["front_door"]["state"] == "established"
    assert bootstrap.json()["actor"]["role"] == "pharmacist"
    assert bootstrap.json()["actor"]["display_name"] == "Mary"


def test_billing_terms_fail_truthfully_until_qualified_and_loyalty_redemption_is_owner_only_idempotent():
    registry, workflows, _ = services()
    joined = join_staff(registry, workflows)
    workflows.credit_loyalty("pharmacy-a", actor_id=joined["actor_id"], event_key="useful-work", coins=50, reason="Useful work")
    pending = workflows.configure_billing("pharmacy-a", owner_id="owner-a", package="Launch", included_seats=2, additional_seat_cost=100, renewal_total=1000, coin_value=10, grace_days=7, provider_qualified=False)
    assert pending["commercially_qualified"] is False
    with pytest.raises(ValueError, match="Qualified"):
        workflows.redeem_loyalty_for_renewal("pharmacy-a", actor_id="owner-a", coins=10, idempotency_key="renewal-1")
    workflows.configure_billing("pharmacy-a", owner_id="owner-a", package="Launch", included_seats=2, additional_seat_cost=100, renewal_total=1000, coin_value=10, grace_days=7, provider_qualified=True)
    with pytest.raises(ValueError, match="authority"):
        workflows.redeem_loyalty_for_renewal("pharmacy-a", actor_id=joined["actor_id"], coins=10, idempotency_key="renewal-staff")
    first = workflows.redeem_loyalty_for_renewal("pharmacy-a", actor_id="owner-a", coins=10, idempotency_key="renewal-1")
    repeated = workflows.redeem_loyalty_for_renewal("pharmacy-a", actor_id="owner-a", coins=10, idempotency_key="renewal-1")
    assert first["coins_used"] == 10 and first["discount"] == 100 and first["remaining_payable"] == 900
    assert repeated["duplicate"] is True


def test_community_comments_appreciation_reports_and_moderation_are_pharmacy_scoped_and_deduplicated():
    registry, workflows, store = services()
    joined = join_staff(registry, workflows)
    post = workflows.community_post("pharmacy-a", actor_id="owner-a", text="How do we improve stock accuracy?", kind="question")
    state = store.load()
    state["pharmacies"]["pharmacy-a"]["community"]["posting_control"] = "members"
    store.save(state)
    commented = workflows.community_interact("pharmacy-a", actor_id=joined["actor_id"], post_id=post["post_id"], action="comment", text="Count fast movers daily")
    appreciated = workflows.community_interact("pharmacy-a", actor_id=joined["actor_id"], post_id=post["post_id"], action="appreciate")
    repeated = workflows.community_interact("pharmacy-a", actor_id=joined["actor_id"], post_id=post["post_id"], action="appreciate")
    reported = workflows.community_interact("pharmacy-a", actor_id=joined["actor_id"], post_id=post["post_id"], action="report", text="Needs owner review")
    assert len(commented["comments"]) == 1
    assert len(appreciated["appreciations"]) == len(repeated["appreciations"]) == 1
    assert len(reported["reports"]) == 1
    workflows.moderate_post("pharmacy-a", owner_id="owner-a", post_id=post["post_id"], action="remove")
    with pytest.raises(ValueError):
        workflows.community_interact("pharmacy-a", actor_id=joined["actor_id"], post_id=post["post_id"], action="comment", text="Hidden")
