from __future__ import annotations

import pytest

from app.front_door import EntryKind, EntryState, FrontDoorRegistry, MemoryFrontDoorStore, SignedEntryContext, can_manage, resolve_front_door


def decision(**overrides):
    values = dict(pharmacy_id="pharmacy-a", actor_id="owner-a", role="owner", authenticated=True, durable_state_available=True, operations_initialized=False)
    values.update(overrides)
    return resolve_front_door(**values)


def test_established_pharmacy_resumes_without_onboarding():
    result = decision(operations_initialized=True)
    assert result.state == EntryState.ESTABLISHED
    assert result.allow_onboarding is False
    assert result.allow_recovery is False


def test_empty_authenticated_tenant_is_not_silently_classified_as_new():
    result = decision()
    assert result.state == EntryState.RECOVERY_OR_SETUP_REQUIRED
    assert result.allow_onboarding is True
    assert result.allow_recovery is True
    assert result.reason == "owner_must_classify_empty_tenant"


def test_unavailable_durable_state_never_exposes_setup_or_recovery():
    result = decision(durable_state_available=False)
    assert result.state == EntryState.STATE_CHECK_UNAVAILABLE
    assert result.allow_onboarding is False
    assert result.allow_recovery is False


def test_established_trusted_device_can_start_offline_but_unknown_or_revoked_device_cannot():
    offline = decision(durable_state_available=False, trusted_cached_established=True)
    revoked = decision(durable_state_available=False, trusted_cached_established=True, device_active=False)
    assert offline.state == EntryState.ESTABLISHED
    assert offline.reason == "trusted_offline_resume"
    assert revoked.state == EntryState.AUTHENTICATION_REQUIRED


def test_staff_cannot_create_or_recover_a_pharmacy():
    result = decision(actor_id="staff-a", role="cashier", entry_kind=EntryKind.STAFF_INVITATION)
    assert result.state == EntryState.STAFF_INVITATION_REQUIRED
    assert result.allow_onboarding is False
    assert result.allow_recovery is False


def test_signed_qr_link_context_is_tenant_bound_short_lived_and_tamper_proof():
    signer = SignedEntryContext("x" * 32, ttl_seconds=120)
    token = signer.issue(pharmacy_id="pharmacy-a", kind=EntryKind.STAFF_INVITATION, nonce="one-use-digest", now=100)
    payload = signer.verify(token, expected_kind=EntryKind.STAFF_INVITATION, now=150)
    assert payload["p"] == "pharmacy-a"
    with pytest.raises(ValueError):
        signer.verify(token + "x", now=150)
    with pytest.raises(ValueError):
        signer.verify(token, expected_kind=EntryKind.NEW_PHARMACY, now=150)
    with pytest.raises(ValueError):
        signer.verify(token, now=220)


def test_verified_new_pharmacy_context_is_digest_only_one_use_and_phone_bound():
    service, store = registry()
    token = service.issue_new_pharmacy_context(verified_phone_key="254700000001")
    durable = store.load()
    assert "254700000001" not in str(durable)
    with pytest.raises(ValueError):
        service.consume_new_pharmacy_context(token, phone_key="254700000002")
    service.consume_new_pharmacy_context(token, phone_key="254700000001")
    with pytest.raises(ValueError):
        service.consume_new_pharmacy_context(token, phone_key="254700000001")


def test_owner_only_authorities_remain_fixed_and_explicit():
    assert can_manage(set(), "owner", "billing") is True
    assert can_manage({"billing"}, "manager", "billing") is True
    assert can_manage(set(), "manager", "billing") is False
    assert can_manage({"billing"}, "cashier", "billing") is False


def registry():
    store = MemoryFrontDoorStore()
    signer = SignedEntryContext("entry-secret-which-is-long-enough-123", ttl_seconds=600)
    return FrontDoorRegistry(store, signer), store


def test_pharmacy_foundation_allocates_collision_safe_shared_identities_once():
    service, _ = registry()
    first = service.initialize_pharmacy(pharmacy_id="pharmacy-a", owner_id="owner-a", owner_name="Owner A", owner_phone_key="2547001")
    repeated = service.initialize_pharmacy(pharmacy_id="pharmacy-a", owner_id="owner-a", owner_name="Owner A", owner_phone_key="2547001")
    second = service.initialize_pharmacy(pharmacy_id="pharmacy-b", owner_id="owner-b", owner_name="Owner B", owner_phone_key="2547002")
    assert first["community"]["community_id"] == repeated["community"]["community_id"] == "001"
    assert second["community"]["community_id"] == "002"
    assert first["loyalty"]["pool_scope"] == "pharmacy"
    assert first["billing"]["active_seats"] == 1
    assert first["billing"]["device_count_is_seat_count"] is False


def test_existing_phone_key_owner_is_canonicalized_without_losing_authority_state():
    legacy_owner = "2547001"
    initial_service, store = registry()
    initial_service.initialize_pharmacy(
        pharmacy_id="pharmacy-a", owner_id=legacy_owner, owner_name="Owner A", owner_phone_key=legacy_owner
    )
    initial_service.bind_device("pharmacy-a", actor_id=legacy_owner, device_key="phone-a")

    restarted = FrontDoorRegistry(store)
    pharmacy = restarted.initialize_pharmacy(
        pharmacy_id="pharmacy-a",
        owner_id="owner_2547001",
        owner_name="Owner A",
        owner_phone_key=legacy_owner,
        trusted_legacy_owner_ids=(legacy_owner,),
    )

    assert pharmacy["owner_id"] == "owner_2547001"
    assert set(pharmacy["members"]) == {"owner_2547001"}
    assert pharmacy["billing"]["authority_actor_ids"] == ["owner_2547001"]
    assert next(iter(pharmacy["devices"].values()))["actor_id"] == "owner_2547001"
    assert restarted.pharmacy_authorities("pharmacy-a", actor_id="owner_2547001")["role"] == "owner"


@pytest.mark.parametrize("legacy_owner", ["unrelated-owner", "2547999"])
def test_unknown_or_cross_identity_owner_mismatch_remains_fail_closed(legacy_owner):
    service, _ = registry()
    service.initialize_pharmacy(
        pharmacy_id="pharmacy-a", owner_id=legacy_owner, owner_name="Owner A", owner_phone_key="2547001"
    )
    with pytest.raises(ValueError, match="owner mismatch"):
        service.initialize_pharmacy(
            pharmacy_id="pharmacy-a",
            owner_id="owner_2547001",
            owner_name="Owner A",
            owner_phone_key="2547001",
            trusted_legacy_owner_ids=("2547001",),
        )


def test_empty_tenant_classification_is_owner_only_and_cannot_flip():
    service, _ = registry()
    service.initialize_pharmacy(pharmacy_id="pharmacy-a", owner_id="owner-a", owner_name="Owner A", owner_phone_key="2547001")
    classified = service.classify_empty_pharmacy("pharmacy-a", owner_id="owner-a", classification="legacy_recovery")
    assert classified["entry_classification"] == "legacy_recovery"
    with pytest.raises(ValueError):
        service.classify_empty_pharmacy("pharmacy-a", owner_id="owner-a", classification="genuinely_new")


def test_invitation_join_is_one_use_role_fixed_and_does_not_create_another_pharmacy():
    service, store = registry()
    service.initialize_pharmacy(pharmacy_id="pharmacy-a", owner_id="owner-a", owner_name="Owner A", owner_phone_key="2547001")
    token = service.issue_invitation("pharmacy-a", owner_id="owner-a", role="cashier", display_name="Mary")
    member = service.accept_invitation(token, actor_id="staff-a", verified_identity=True, device_key="phone-a")
    assert member["role"] == "cashier"
    state = store.load()
    assert list(state["pharmacies"]) == ["pharmacy-a"]
    assert state["pharmacies"]["pharmacy-a"]["billing"]["active_seats"] == 2
    with pytest.raises(ValueError):
        service.accept_invitation(token, actor_id="staff-b", verified_identity=True)


def test_devices_do_not_multiply_seats_and_revocation_is_durable():
    service, store = registry()
    service.initialize_pharmacy(pharmacy_id="pharmacy-a", owner_id="owner-a", owner_name="Owner A", owner_phone_key="2547001")
    service.bind_device("pharmacy-a", actor_id="owner-a", device_key="old-phone")
    service.bind_device("pharmacy-a", actor_id="owner-a", device_key="replacement-phone")
    service.revoke_device("pharmacy-a", owner_id="owner-a", device_key="old-phone")
    pharmacy = store.load()["pharmacies"]["pharmacy-a"]
    assert pharmacy["billing"]["active_seats"] == 1
    assert sorted(device["status"] for device in pharmacy["devices"].values()) == ["active", "revoked"]


def test_owner_phone_change_and_recovery_force_session_device_and_quick_pin_recheck():
    service, store = registry()
    service.initialize_pharmacy(pharmacy_id="pharmacy-a", owner_id="owner-a", owner_name="Owner A", owner_phone_key="2547001")
    service.bind_device("pharmacy-a", actor_id="owner-a", device_key="phone-a")
    with pytest.raises(ValueError):
        service.change_owner_phone("pharmacy-a", owner_id="owner-a", new_phone_key="2547002", current_owner_verified=True, new_phone_verified=False)
    result = service.change_owner_phone("pharmacy-a", owner_id="owner-a", new_phone_key="2547002", current_owner_verified=True, new_phone_verified=True)
    recovery = service.complete_account_recovery("pharmacy-a", owner_id="owner-a", verified_identity=True)
    assert result == recovery == {"revoke_sessions": True, "recheck_devices": True, "recheck_quick_pin": True}
    assert next(iter(store.load()["pharmacies"]["pharmacy-a"]["devices"].values()))["status"] == "recheck_required"


def test_owner_recovery_device_uses_cryptographic_credential_and_quick_pin_is_not_proof():
    service = FrontDoorRegistry(MemoryFrontDoorStore())
    service.initialize_pharmacy(pharmacy_id="pharmacy-a", owner_id="owner-a", owner_name="Owner", owner_phone_key="")
    credential = "device-cryptographic-credential-" + "x" * 32
    service.enroll_owner_recovery_device("pharmacy-a", owner_id="owner-a", device_credential=credential)
    assert service.verify_owner_recovery_device("pharmacy-a", device_credential=credential) == "owner-a"
    with pytest.raises(ValueError):
        service.verify_owner_recovery_device("pharmacy-a", device_credential="1234")
    with pytest.raises(ValueError):
        service.verify_owner_recovery_device("pharmacy-b", device_credential=credential)


def test_community_loyalty_and_billing_authority_are_pharmacy_bound():
    service, _ = registry()
    service.initialize_pharmacy(pharmacy_id="pharmacy-a", owner_id="owner-a", owner_name="Owner A", owner_phone_key="2547001")
    token = service.issue_invitation("pharmacy-a", owner_id="owner-a", role="cashier", display_name="Mary")
    service.accept_invitation(token, actor_id="staff-a", verified_identity=True)
    owner = service.pharmacy_authorities("pharmacy-a", actor_id="owner-a")
    staff = service.pharmacy_authorities("pharmacy-a", actor_id="staff-a")
    assert owner["community"] == staff["community"]
    assert owner["loyalty"] == staff["loyalty"]
    assert owner["may_redeem"] is True
    assert staff["may_redeem"] is False
    assert staff["may_post"] is False


def test_referral_entry_is_signed_pharmacy_pooled_one_time_and_not_device_multiplied():
    service, store = registry()
    service.initialize_pharmacy(pharmacy_id="pharmacy-a", owner_id="owner-a", owner_name="Owner A", owner_phone_key="2547001")
    service.initialize_pharmacy(pharmacy_id="pharmacy-b", owner_id="owner-b", owner_name="Owner B", owner_phone_key="2547002")
    token = service.issue_referral_context("pharmacy-a", owner_id="owner-a")
    service.attribute_referral(token, new_pharmacy_id="pharmacy-b", new_owner_id="owner-b")
    assert store.load()["pharmacies"]["pharmacy-b"]["loyalty"]["referred_by_pharmacy_id"] == "pharmacy-a"
    with pytest.raises(ValueError):
        service.attribute_referral(token, new_pharmacy_id="pharmacy-b", new_owner_id="owner-b")


def test_provisioning_resume_compliance_subscription_and_quick_pin_boundaries_are_initialized():
    service, store = registry()
    foundation = service.initialize_pharmacy(pharmacy_id="pharmacy-a", owner_id="owner-a", owner_name="Owner A", owner_phone_key="2547001")
    assert foundation["billing"]["subscription_status"] == "unqualified"
    service.record_provisioning_resume("pharmacy-a", owner_id="owner-a", failed_step="catalog", resume_token="raw-resume-token")
    service.record_owner_acceptance("pharmacy-a", owner_id="owner-a", terms_version="terms-v1", privacy_version="privacy-v1")
    service.bind_device("pharmacy-a", actor_id="owner-a", device_key="phone-a")
    pharmacy = store.load()["pharmacies"]["pharmacy-a"]
    assert pharmacy["provisioning"]["status"] == "resume_required"
    assert pharmacy["provisioning"]["resume_token_digest"] != "raw-resume-token"
    assert pharmacy["compliance"]["terms_version"] == "terms-v1"
    assert next(iter(pharmacy["devices"].values()))["quick_pin_trust"] == "disabled"
