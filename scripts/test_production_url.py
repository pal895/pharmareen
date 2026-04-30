from __future__ import annotations

import sys
import time
import urllib.parse
import urllib.request


TIMEOUT_SECONDS = 30
RETRY_SECONDS = 45


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/test_production_url.py https://YOUR-DOMAIN")
        return 1

    base_url = sys.argv[1].strip().rstrip("/")
    if not base_url.startswith("https://") and not base_url.startswith("http://"):
        print("FAIL: URL must start with https://")
        return 1

    checks = [
        ("GET /health", lambda: get_contains(base_url, "/health", '"status":"ok"')),
        ("GET /status", lambda: get_contains(base_url, "/status", "Webhook URL for Twilio")),
        ("GET /", lambda: get_contains(base_url, "/", "Run your pharmacy from WhatsApp")),
        ("POST /webhook/whatsapp", lambda: post_twilio_sample(base_url)),
    ]

    failed = 0
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

    if failed:
        print(f"FINAL RESULT: FAIL ({failed} checks failed)")
        return 1
    print("FINAL RESULT: PRODUCTION URL WORKS")
    return 0


def get_contains(base_url: str, path: str, expected: str) -> tuple[bool, str]:
    url = f"{base_url}{path}"
    response, body = open_with_retry(url)
    compact_body = body.replace(" ", "")
    compact_expected = expected.replace(" ", "")
    return compact_expected in compact_body, f"{response.status} {url}"


def post_twilio_sample(base_url: str) -> tuple[bool, str]:
    url = f"{base_url}/webhook/whatsapp"
    data = urllib.parse.urlencode(
        {
            "Body": "start",
            "From": "whatsapp:+254700000000",
            "To": "whatsapp:+14155238886",
            "MessageSid": f"SMPRODTEST{int(time.time() * 1000)}",
            "NumMedia": "0",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    response, body = open_with_retry(request)
    ok = response.status == 200 and "<Response><Message>" in body
    return ok, f"{response.status} {url}"


def open_with_retry(request_or_url):
    deadline = time.time() + RETRY_SECONDS
    last_error: Exception | None = None
    while time.time() <= deadline:
        try:
            response = urllib.request.urlopen(request_or_url, timeout=TIMEOUT_SECONDS)
            body = response.read().decode("utf-8", errors="replace")
            return response, body
        except Exception as exc:
            last_error = exc
            time.sleep(3)
    raise last_error or RuntimeError("Request failed")


if __name__ == "__main__":
    raise SystemExit(main())
