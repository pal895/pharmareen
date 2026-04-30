from __future__ import annotations

import html
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


APP_EXE = Path(r"C:\Program Files (x86)\ZillaPharmacy\ZillaPharmacyApp.exe")
BASE_URL = "http://localhost:8000"


def main() -> int:
    if not ensure_app_running():
        print("PDF REPORT TEST: FAIL")
        print("Could not start or reach the installed app.")
        return 1

    try:
        response = post_whatsapp("report today")
    except Exception as exc:
        print("PDF REPORT TEST: FAIL")
        print(f"Webhook error: {exc}")
        return 1

    pdf_link = extract_pdf_link(response)
    if not pdf_link:
        print("PDF REPORT TEST: FAIL")
        print("PDF link was not found in the report today response.")
        print(response)
        return 1

    if not downloadable(pdf_link):
        print("PDF REPORT TEST: FAIL")
        print(f"PDF link was returned but could not be downloaded: {pdf_link}")
        return 1

    print("PDF REPORT TEST: PASS")
    print(f"PDF LINK: {pdf_link}")
    return 0


def ensure_app_running() -> bool:
    if health_ok(wait_seconds=2):
        return True
    if not APP_EXE.exists():
        return False

    try:
        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen([str(APP_EXE)], cwd=str(APP_EXE.parent), creationflags=creationflags)
    except Exception:
        return False

    return health_ok(wait_seconds=90)


def health_ok(wait_seconds: int) -> bool:
    deadline = time.time() + wait_seconds
    while time.time() <= deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=5) as response:
                body = response.read().decode("utf-8", errors="replace")
                if response.status == 200 and '"status":"ok"' in body.replace(" ", ""):
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def post_whatsapp(message: str) -> str:
    data = urllib.parse.urlencode(
        {
            "Body": message,
            "From": "whatsapp:+254700000000",
            "To": "whatsapp:+14155238886",
            "MessageSid": f"SM-PDF-{int(time.time() * 1000)}",
            "NumMedia": "0",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/webhooks/twilio/whatsapp",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        body = response.read().decode("utf-8", errors="replace")
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {body}")
        return body


def extract_pdf_link(response: str) -> str | None:
    text = html.unescape(response)
    match = re.search(r"(https?://\S+?\.pdf)", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()


def downloadable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            first_bytes = response.read(5)
            return response.status == 200 and first_bytes.startswith(b"%PDF")
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
