from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
]


def main() -> int:
    print("PharMareen Google Permission Diagnostic")
    print("=" * 44)

    try:
        info = load_service_account_info()
    except Exception as exc:
        print_fail("Load service account credentials", exc)
        return 1

    client_email = str(info.get("client_email") or "").strip()
    project_id = str(info.get("project_id") or "").strip()
    admin_sheet_id = (os.environ.get("PHARMAREEN_ADMIN_SHEET_ID") or "").strip()

    print(f"service_account_client_email={client_email or 'MISSING'}")
    print(f"project_id={project_id or 'MISSING'}")
    print(f"PHARMAREEN_ADMIN_SHEET_ID={admin_sheet_id or 'MISSING'}")
    print("private_key=NOT_PRINTED")

    try:
        credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
        print_pass("Create scoped credentials", f"scopes={', '.join(credentials.scopes or [])}")
    except Exception as exc:
        print_fail("Create scoped credentials", exc)
        return 1

    try:
        sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        print_pass("Initialize Sheets and Drive clients")
    except Exception as exc:
        print_fail("Initialize Sheets and Drive clients", exc)
        return 1

    admin_tabs: list[str] = []
    if admin_sheet_id:
        admin_tabs = test_open_admin_sheet(sheets, admin_sheet_id)
        test_write_admin_sheet(sheets, admin_sheet_id, admin_tabs, client_email)
    else:
        print_fail("Open admin sheet", "PHARMAREEN_ADMIN_SHEET_ID is missing")
        print_fail("Write admin sheet row", "PHARMAREEN_ADMIN_SHEET_ID is missing")

    test_create_spreadsheet_with_sheets_api(sheets)
    test_create_spreadsheet_with_drive_api(drive)
    return 0


def load_service_account_info() -> dict[str, Any]:
    raw = (os.environ.get("GOOGLE_SHEETS_CREDENTIALS") or "").strip()
    if raw:
        info = json.loads(raw)
        if not isinstance(info, dict):
            raise ValueError("GOOGLE_SHEETS_CREDENTIALS must be a JSON object")
        return info

    path_value = (
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        or "service-account.json"
    )
    path = Path(path_value).expanduser()
    if not path.exists():
        raise FileNotFoundError(
            "No GOOGLE_SHEETS_CREDENTIALS JSON and no service-account.json file found"
        )
    info = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(info, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return info


def test_open_admin_sheet(sheets: Any, admin_sheet_id: str) -> list[str]:
    try:
        result = (
            sheets.spreadsheets()
            .get(
                spreadsheetId=admin_sheet_id,
                fields="spreadsheetId,properties.title,sheets.properties.title",
            )
            .execute()
        )
        title = result.get("properties", {}).get("title", "")
        tabs = [
            sheet.get("properties", {}).get("title", "")
            for sheet in result.get("sheets", [])
            if sheet.get("properties", {}).get("title")
        ]
        print_pass(
            "Open admin sheet with Sheets API",
            f"title={title or 'UNKNOWN'}; tabs={', '.join(tabs) or 'NONE'}",
        )
        return tabs
    except Exception as exc:
        print_fail("Open admin sheet with Sheets API", exc)
        return []


def test_write_admin_sheet(
    sheets: Any,
    admin_sheet_id: str,
    tabs: list[str],
    client_email: str,
) -> None:
    target_tab = "Pharmacies" if "Pharmacies" in tabs else (tabs[0] if tabs else "Pharmacies")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = [
        "DEBUG_PERMISSION_TEST",
        "PharMareen Permission Diagnostic",
        client_email,
        "",
        "",
        "",
        "",
        timestamp,
        "debug",
        "Safe permission test row; no secrets stored",
    ]
    try:
        (
            sheets.spreadsheets()
            .values()
            .append(
                spreadsheetId=admin_sheet_id,
                range=f"{target_tab}!A:J",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            )
            .execute()
        )
        print_pass("Write admin sheet row", f"tab={target_tab}")
    except Exception as exc:
        print_fail("Write admin sheet row", exc)


def test_create_spreadsheet_with_sheets_api(sheets: Any) -> None:
    title = f"PharMareen Permission Debug Sheets {timestamp_slug()}"
    try:
        result = (
            sheets.spreadsheets()
            .create(
                body={"properties": {"title": title}},
                fields="spreadsheetId,spreadsheetUrl",
            )
            .execute()
        )
        spreadsheet_id = result.get("spreadsheetId", "")
        url = result.get("spreadsheetUrl", "")
        print_pass(
            "Create spreadsheet with Sheets API",
            f"spreadsheet_id={spreadsheet_id}; url={url}",
        )
    except Exception as exc:
        print_fail("Create spreadsheet with Sheets API", exc)


def test_create_spreadsheet_with_drive_api(drive: Any) -> None:
    title = f"PharMareen Permission Debug Drive {timestamp_slug()}"
    try:
        result = (
            drive.files()
            .create(
                body={
                    "name": title,
                    "mimeType": "application/vnd.google-apps.spreadsheet",
                },
                fields="id,name,webViewLink",
            )
            .execute()
        )
        print_pass(
            "Create spreadsheet file with Drive API",
            f"file_id={result.get('id', '')}; url={result.get('webViewLink', '')}",
        )
    except Exception as exc:
        print_fail("Create spreadsheet file with Drive API", exc)


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def print_pass(step: str, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"PASS: {step}{suffix}")


def print_fail(step: str, error: object) -> None:
    print(f"FAIL: {step} - {format_error(error)}")


def format_error(error: object) -> str:
    if isinstance(error, HttpError):
        status = getattr(error.resp, "status", "")
        reason = getattr(error.resp, "reason", "")
        content = ""
        try:
            raw = error.content.decode("utf-8") if isinstance(error.content, bytes) else str(error.content)
            parsed = json.loads(raw)
            content = json.dumps(parsed.get("error", parsed), ensure_ascii=True)
        except Exception:
            content = str(getattr(error, "content", ""))[:500]
        return f"HttpError status={status} reason={reason} details={content}"
    return f"{type(error).__name__}: {error}"


if __name__ == "__main__":
    sys.exit(main())
