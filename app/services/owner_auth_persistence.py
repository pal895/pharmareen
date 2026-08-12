from __future__ import annotations

import logging
import time
from typing import Any

from app.config import Settings
from app.services.pharmacy_onboarding import PharmacyOnboardingService, admin_sheet_id, ensure_worksheet


ACTIVATION_SHEET = "Owner_Activations"
CREDENTIAL_SHEET = "Owner_Credentials"
SESSION_SHEET = "Owner_Sessions"
ACTIVATION_HEADERS = [
    "Token Digest", "Owner ID", "Phone Key", "Pharmacy ID", "Pharmacy Name",
    "Owner Name", "Expires At", "Used At",
]
CREDENTIAL_HEADERS = [
    "Phone Key", "Owner ID", "Pharmacy ID", "Pharmacy Name", "Owner Name",
    "PIN Hash", "Failed Attempts", "Locked Until", "Recovery Key Hash",
    "Recovery Failures", "Recovery Locked Until", "Recovery Rotated At",
]
SESSION_HEADERS = [
    "Session Digest", "Actor ID", "Pharmacy ID", "Role", "Display Name",
    "Expires At", "Revoked",
]

logger = logging.getLogger(__name__)


def owner_auth_sheet_id(settings: Settings) -> str:
    """Return the platform-managed durable auth workbook.

    A dedicated admin workbook wins when configured. Isolated deployments use
    the already configured registry workbook, avoiding per-pharmacy setup and
    never falling back to an ephemeral deployment file.
    """
    return admin_sheet_id(settings) or str(settings.google_sheets_spreadsheet_id or "").strip()


class GoogleSheetsOwnerAuthStateStore:
    """Durable owner-auth state in the protected PharMareen admin workbook.

    Raw activation values, private PINs, and raw session cookies are never written.
    Only one-way session digests and their authorization envelope are shared so
    authenticated requests survive deployment process handoffs.
    """

    def __init__(self, settings: Settings):
        self._onboarding = PharmacyOnboardingService(settings)
        self._sheet_id = owner_auth_sheet_id(settings)
        if not self._sheet_id:
            raise RuntimeError("Owner authentication durable workbook is not configured")

    def _spreadsheet(self):
        # Google can close an otherwise healthy Sheets HTTP connection between
        # the credential write and the immediately following Recovery Key
        # write. Retry only the idempotent workbook-open step; the existing
        # clear/update operations remain unchanged and never receive secrets.
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return self._onboarding._gspread_client().open_by_key(self._sheet_id)
            except Exception as exc:
                last_error = exc
                if attempt == 2:
                    raise
                logger.warning(
                    "OWNER_AUTH_SHEETS_OPEN_RETRY attempt=%d reason=%s",
                    attempt + 1,
                    type(exc).__name__,
                )
                time.sleep(0.35 * (2 ** attempt))
        assert last_error is not None
        raise last_error

    def load(self) -> dict[str, Any]:
        spreadsheet = self._spreadsheet()
        activations_ws = ensure_worksheet(spreadsheet, ACTIVATION_SHEET, ACTIVATION_HEADERS)
        credentials_ws = ensure_worksheet(spreadsheet, CREDENTIAL_SHEET, CREDENTIAL_HEADERS)
        sessions_ws = ensure_worksheet(spreadsheet, SESSION_SHEET, SESSION_HEADERS)
        activations: dict[str, Any] = {}
        credentials: dict[str, Any] = {}
        sessions: dict[str, Any] = {}
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
                    "recovery_key_hash": str(row.get("Recovery Key Hash") or ""),
                    "recovery_failures": int(row.get("Recovery Failures") or 0),
                    "recovery_locked_until": float(row.get("Recovery Locked Until") or 0),
                    "recovery_rotated_at": float(row.get("Recovery Rotated At") or 0),
                }
        for row in sessions_ws.get_all_records():
            digest = str(row.get("Session Digest") or "").strip()
            if digest:
                sessions[digest] = {
                    "session_digest": digest,
                    "actor_id": str(row.get("Actor ID") or ""),
                    "pharmacy_id": str(row.get("Pharmacy ID") or ""),
                    "role": str(row.get("Role") or ""),
                    "display_name": str(row.get("Display Name") or ""),
                    "expires_at": float(row.get("Expires At") or 0),
                    "revoked": str(row.get("Revoked") or "").strip().lower() in {"true", "yes", "1"},
                }
        return {"activations": activations, "credentials": credentials, "sessions": sessions}

    def save(self, payload: dict[str, Any]) -> None:
        spreadsheet = self._spreadsheet()
        activations_ws = ensure_worksheet(spreadsheet, ACTIVATION_SHEET, ACTIVATION_HEADERS)
        credentials_ws = ensure_worksheet(spreadsheet, CREDENTIAL_SHEET, CREDENTIAL_HEADERS)
        sessions_ws = ensure_worksheet(spreadsheet, SESSION_SHEET, SESSION_HEADERS)
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
                value.get("recovery_key_hash", ""), value.get("recovery_failures", 0),
                value.get("recovery_locked_until", 0), value.get("recovery_rotated_at", 0),
            ]
            for value in payload.get("credentials", {}).values()
        ]
        session_rows = [
            [
                value["session_digest"], value["actor_id"], value["pharmacy_id"],
                value["role"], value["display_name"], value["expires_at"],
                value["revoked"],
            ]
            for value in payload.get("sessions", {}).values()
        ]
        # Recovery changes credentials and sessions together. Persist sessions
        # first and the credential verifier last, so an interrupted write can
        # never rotate the owner's secret before its replacement session and
        # stale-session revocations are durable.
        sessions_ws.clear()
        sessions_ws.update("A1", [SESSION_HEADERS, *session_rows])
        credentials_ws.clear()
        credentials_ws.update("A1", [CREDENTIAL_HEADERS, *credential_rows])
        activations_ws.clear()
        activations_ws.update("A1", [ACTIVATION_HEADERS, *activation_rows])
