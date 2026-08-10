"""One-time controlled enrollment for the pre-recovery Mwangaza partial tenant.

This is deliberately not a general reset tool.  It can enroll only the exact
authoritative pharmacy/owner pair, refuses an existing recovery factor, never
changes the PIN, and prints the newly generated key once for owner custody.
"""
from app.config import get_settings
from app.owner_auth import OwnerAuthService
from app.services.owner_auth_persistence import GoogleSheetsOwnerAuthStateStore


PHARMACY_ID = "pharmacy_2260644ed30c4e941dff33a2"
OWNER_ID = "owner_7bf5ceb64de96d78d516afa63"


def enroll_exact_mwangaza(service: OwnerAuthService) -> str:
    matches = [item for item in service._credentials.values() if item.pharmacy_id == PHARMACY_ID]
    if len(matches) != 1:
        raise SystemExit("MWANGAZA_CREDENTIAL_CONFLICT: expected exactly one credential")
    credential = matches[0]
    if credential.recovery_key_hash:
        raise SystemExit("RECOVERY_ALREADY_ENROLLED: migration is closed")
    # The broken partial saga committed its pre-registry owner identity into the
    # credential row.  This controlled migration makes the authoritative
    # registry owner ID win for this exact tenant before adding recovery.  It
    # does not alter or inspect the existing PIN verifier.
    credential.owner_id = OWNER_ID
    service._save_state()
    return service.enroll_recovery_key(pharmacy_id=PHARMACY_ID, owner_id=OWNER_ID)


def main() -> None:
    store = GoogleSheetsOwnerAuthStateStore(get_settings())
    service = OwnerAuthService()
    service.configure_persistence(loader=store.load, saver=store.save)
    key = enroll_exact_mwangaza(service)
    print(f"MWANGAZA_RECOVERY_KEY={key}")
    print(f"RECOVER_AT=/main-app/recover?pharmacy_id={PHARMACY_ID}")


if __name__ == "__main__":
    main()
