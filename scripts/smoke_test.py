from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


TIMEOUT_SECONDS = 30
RETRY_SECONDS = 45


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/smoke_test.py https://YOUR-REPLIT-URL")
        return 1

    base_url = sys.argv[1].strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        print("BASE URL: FAIL")
        print("Use a full URL like: https://your-app.replit.app")
        return 1

    checks = [
        ("HEALTH", lambda: get_json_contains(base_url, "/health", '"status":"ok"')),
        ("STATUS PAGE", lambda: get_text_contains(base_url, "/status", "Webhook URL for Twilio")),
        ("DEBUG CONFIG", lambda: get_debug_config(base_url)),
        ("WHATSAPP WEBHOOK DEBUG", lambda: post_debug_whatsapp(base_url)),
        ("PDF REPORT DEBUG", lambda: get_report_debug(base_url)),
    ]

    failed = 0
    print(f"Testing: {base_url}")
    print()
    for label, check in checks:
        try:
            ok, detail = check()
        except Exception as exc:
            ok, detail = False, str(exc)
        print(f"{label}: {'PASS' if ok else 'FAIL'}")
        if detail:
            print(f"  {detail}")
        if not ok:
            failed += 1

    print()
    if failed:
        print(f"FINAL RESULT: FAIL ({failed} checks failed)")
        return 1
    print("FINAL RESULT: PASS")
    return 0


def get_json_contains(base_url: str, path: str, expected: str) -> tuple[bool, str]:
    status, body = request_with_retry(f"{base_url}{path}")
    compact = body.replace(" ", "")
    return status == 200 and expected.replace(" ", "") in compact, f"HTTP {status}"


def get_text_contains(base_url: str, path: str, expected: str) -> tuple[bool, str]:
    status, body = request_with_retry(f"{base_url}{path}")
    return status == 200 and expected in body, f"HTTP {status}"


def get_debug_config(base_url: str) -> tuple[bool, str]:
    status, body = request_with_retry(f"{base_url}/debug/config")
    data = parse_json(body)
    required_keys = [
        "app_running",
        "app_base_url",
        "app_base_url_is_https",
        "app_base_url_has_placeholder",
        "twilio_account_sid_present",
        "twilio_auth_token_present",
        "twilio_whatsapp_number_present",
        "owner_whatsapp_to_present",
        "google_sheet_id_present",
        "google_credentials_present",
        "openai_api_key_present",
    ]
    missing = [key for key in required_keys if key not in data]
    ok = status == 200 and not missing and data.get("app_running") is True
    detail = (
        f"HTTP {status}; APP_BASE_URL={data.get('app_base_url')}; "
        f"https={data.get('app_base_url_is_https')}; "
        f"twilio={data.get('twilio_account_sid_present') and data.get('twilio_auth_token_present') and data.get('twilio_whatsapp_number_present')}; "
        f"sheets={data.get('google_sheet_id_present') and data.get('google_credentials_present')}"
    )
    if missing:
        detail += f"; missing keys={', '.join(missing)}"
    return ok, detail


def post_debug_whatsapp(base_url: str) -> tuple[bool, str]:
    request = urllib.request.Request(
        f"{base_url}/debug/whatsapp-test",
        data=b"",
        method="POST",
    )
    status, body = request_with_retry(request)
    data = parse_json(body)
    preview = str(data.get("response_body_preview") or "")
    ok = status == 200 and data.get("status") == "ok" and "<Response><Message>" in preview
    return ok, f"HTTP {status}; status={data.get('status')}; handler={data.get('command_handler')}"


def get_report_debug(base_url: str) -> tuple[bool, str]:
    status, body = request_with_retry(f"{base_url}/debug/report-test")
    data = parse_json(body)
    ok = status == 200 and data.get("status") == "ok" and data.get("file_exists") is True
    return ok, f"HTTP {status}; file_exists={data.get('file_exists')}; public_pdf_url={data.get('public_pdf_url')}"


def request_with_retry(request_or_url) -> tuple[int, str]:
    deadline = time.time() + RETRY_SECONDS
    last_error: Exception | None = None
    while time.time() <= deadline:
        try:
            with urllib.request.urlopen(request_or_url, timeout=TIMEOUT_SECONDS) as response:
                body = response.read().decode("utf-8", errors="replace")
                return response.status, body
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return exc.code, body
        except Exception as exc:
            last_error = exc
            time.sleep(3)
    raise last_error or RuntimeError("Request failed")


def parse_json(body: str) -> dict:
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Expected JSON but got: {body[:300]}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
