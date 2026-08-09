from __future__ import annotations

import pytest

from app.front_door import EntryKind, EntryState, SignedEntryContext, can_manage, resolve_front_door


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


def test_owner_only_authorities_remain_fixed_and_explicit():
    assert can_manage(set(), "owner", "billing") is True
    assert can_manage({"billing"}, "manager", "billing") is True
    assert can_manage(set(), "manager", "billing") is False
    assert can_manage({"billing"}, "cashier", "billing") is False
