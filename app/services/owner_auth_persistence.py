from __future__ import annotations

from typing import Any

from app.config import Settings
from app.services.pharmacy_onboarding import PharmacyOnboardingService, admin_sheet_id, ensure_worksheet


ACTIVATION_SHEET = "Owner_Activations"
CREDENTIAL_SHEET = "Owner_Credentials"
ACTIVATION_HEADERS = [
    "Token Digest", "Owner ID", "Phone Key", "Pharmacy ID", "Pharmacy Name",
    "Owner Name", "Expires At", "Used At",
]
CREDENTIAL_HEADERS = [
    "Phone Key", "Owner ID", "Pharmacy ID", "Pharmacy Name", "Owner Name",
    "PIN Hash", "Failed Attempts", "Locked Until",
]


def owner_auth_sheet_id(settings: Settings) -> str:
    """Return the platform-managed durable auth workbook.

    A dedicated admin workbook wins when configured. Isolated deployments use
    the already configured registry workbook, avoiding per-pharmacy setup and
    never falling back to an ephemeral deployment file.
    """
    return admin_sheet_id(settings) or str(settings.google_sheets_spreadsheet_id or "").strip()


class GoogleSheetsOwnerAuthStateStore:
    """Durable owner-auth state in the protected PharMareen admin workbook.

    Raw activation values, private PINs, and session cookies are never written.
    """

    def __init__(self, settings: Settings):
        self._onboarding = PharmacyOnboardingService(settings)
        self._sheet_id = owner_auth_sheet_id(settings)
        if not self._sheet_id:
            raise RuntimeError("Owner authentication durable workbook is not configured")

    def _spreadsheet(self):
        return self._onboarding._gspread_client().open_by_key(self._sheet_id)

    def load(self) -> dict[str, Any]:
        spreadsheet = self._spreadsheet()
        activations_ws = ensure_worksheet(spreadsheet, ACTIVATION_SHEET, ACTIVATION_HEADERS)
        credentials_ws = ensure_worksheet(spreadsheet, CREDENTIAL_SHEET, CREDENTIAL_HEADERS)
        activations: dict[str, Any] = {}
        credentials: dict[str, Any] = {}
        for row in activations_ws.get_all_records():
            digest = str(row.get("Token Digest") or "").strip()
            if digest:
                activations[digest] = {
                    "token_digest": digest,
                    "owner_id": str(row.get("Owner ID") or ""),
                    "phone_key": str(row.get("Phone Key") or ""),
                    "pharmacy_id": str(row.get("Pharmacy ID") or ""),
                    "pharmacy_name": str(row.get("Pharmacy Name") or ""),
                    "owner_name": str(row.get("Owner Name") or ""),
                    "expires_at": float(row.get("Expires At") or 0),
                    "used_at": float(row.get("Used At") or 0),
                }
        for row in credentials_ws.get_all_records():
            phone_key = str(row.get("Phone Key") or "").strip()
            if phone_key:
                credentials[phone_key] = {
                    "owner_id": str(row.get("Owner ID") or ""),
                    "phone_key": phone_key,
                    "pharmacy_id": str(row.get("Pharmacy ID") or ""),
                    "pharmacy_name": str(row.get("Pharmacy Name") or ""),
                    "owner_name": str(row.get("Owner Name") or ""),
                    "pin_hash": str(row.get("PIN Hash") or ""),
                    "failed_attempts": int(row.get("Failed Attempts") or 0),
                    "locked_until": float(row.get("Locked Until") or 0),
                }
        return {"activations": activations, "credentials": credentials}

    def save(self, payload: dict[str, Any]) -> None:
        spreadsheet = self._spreadsheet()
        activations_ws = ensure_worksheet(spreadsheet, ACTIVATION_SHEET, ACTIVATION_HEADERS)
        credentials_ws = ensure_worksheet(spreadsheet, CREDENTIAL_SHEET, CREDENTIAL_HEADERS)
        activation_rows = [
            [
                value["token_digest"], value["owner_id"], value["phone_key"],
                value["pharmacy_id"], value["pharmacy_name"], value["owner_name"],
                value["expires_at"], value["used_at"],
            ]
            for value in payload.get("activations", {}).values()
        ]
        credential_rows = [
            [
                value["phone_key"], value["owner_id"], value["pharmacy_id"],
                value["pharmacy_name"], value["owner_name"], value["pin_hash"],
                value["failed_attempts"], value["locked_until"],
            ]
            for value in payload.get("credentials", {}).values()
        ]
        activations_ws.clear()
        activations_ws.update("A1", [ACTIVATION_HEADERS, *activation_rows])
        credentials_ws.clear()
        credentials_ws.update("A1", [CREDENTIAL_HEADERS, *credential_rows])
