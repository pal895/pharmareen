"""Exact, fail-closed identity reconciliation for the legacy Mwangaza tenant."""
from app.config import get_settings
from app.front_door import FrontDoorRegistry
from app.owner_auth import OwnerAuthService, registry_owner_login_key
from app.pharmacy_registry import GoogleSheetsPharmacyRegistry
from app.services.front_door_persistence import GoogleSheetsFrontDoorStore
from app.services.owner_auth_persistence import GoogleSheetsOwnerAuthStateStore
from app.sheets import GoogleSheetsStore


PHARMACY_ID = "pharmacy_2260644ed30c4e941dff33a2"


def reconcile_exact_mwangaza(registry, auth: OwnerAuthService, front_door: FrontDoorRegistry) -> str:
    records = [row for row in registry.list_records() if row.get("pharmacy_id") == PHARMACY_ID]
    if len(records) != 1:
        raise SystemExit("MWANGAZA_REGISTRY_CONFLICT: expected exactly one record")
    registry_owner = str(records[0].get("owner_id") or "")
    if not registry_owner:
        raise SystemExit("MWANGAZA_REGISTRY_OWNER_MISSING")

    credentials = [item for item in auth._credentials.values() if item.pharmacy_id == PHARMACY_ID]
    if len(credentials) != 1:
        raise SystemExit("MWANGAZA_CREDENTIAL_OWNER_CONFLICT")
    if not credentials[0].recovery_key_hash:
        raise SystemExit("MWANGAZA_RECOVERY_FACTOR_MISSING")

    # The exact, unique live registry row is the authorization authority.  The
    # legacy saga may have persisted a different provisional actor into the
    # credential/front-door stores; preserve the credential verifier while
    # canonically rebinding that one row to the registry actor.
    credential = credentials[0]
    credential.owner_id = registry_owner
    credential.phone_key = registry_owner_login_key(records[0])
    auth._credentials = {
        auth._credential_key(item.pharmacy_id, item.phone_key): item
        for item in auth._credentials.values()
    }
    auth._save_state()
    front_door.reconcile_authenticated_registry_owner(PHARMACY_ID, owner_id=registry_owner)

    replacement_key = auth.enroll_recovery_key(
        pharmacy_id=PHARMACY_ID, owner_id=registry_owner, allow_existing=True,
    )
    for session in auth._sessions.values():
        if session.pharmacy_id == PHARMACY_ID:
            session.revoked = True
    auth._save_state()

    record = registry.find_by_id(PHARMACY_ID, active_only=False)
    front = front_door.store.load().get("pharmacies", {}).get(PHARMACY_ID, {})
    credential = [item for item in auth._credentials.values() if item.pharmacy_id == PHARMACY_ID]
    device_actors = {
        str(item.get("actor_id") or "") for item in front.get("devices", {}).values()
        if item.get("status") == "active"
    }
    if (
        not record or record.get("owner_id") != registry_owner
        or len(credential) != 1 or credential[0].owner_id != registry_owner
        or credential[0].phone_key != registry_owner_login_key(record)
        or front.get("owner_id") != registry_owner
        or any(actor != registry_owner for actor in device_actors)
        or any(not session.revoked for session in auth._sessions.values() if session.pharmacy_id == PHARMACY_ID)
    ):
        raise SystemExit("MWANGAZA_IDENTITY_CHAIN_NOT_ALIGNED")
    return replacement_key


def main() -> None:
    settings = get_settings()
    sheets = GoogleSheetsStore(settings)
    registry = GoogleSheetsPharmacyRegistry(sheets, timezone_name=settings.timezone, currency="KES")
    auth = OwnerAuthService()
    auth_store = GoogleSheetsOwnerAuthStateStore(settings)
    auth.configure_persistence(loader=auth_store.load, saver=auth_store.save)
    front_door = FrontDoorRegistry(GoogleSheetsFrontDoorStore(settings))
    key = reconcile_exact_mwangaza(registry, auth, front_door)
    print("MWANGAZA_IDENTITY_CHAIN_ALIGNED=true")
    print(f"MWANGAZA_RECOVERY_KEY={key}")


if __name__ == "__main__":
    main()
