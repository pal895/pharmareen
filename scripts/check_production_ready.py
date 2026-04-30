from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ENV_KEYS = [
    "APP_BASE_URL",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_WHATSAPP_NUMBER",
    "OWNER_WHATSAPP_TO",
    "GOOGLE_SHEET_ID",
    "GOOGLE_SHEETS_CREDENTIALS",
    "OPENAI_API_KEY",
    "ENABLE_VOICE_INPUT",
    "REPORT_STORAGE_MODE",
    "REPORT_PUBLIC_DIR",
]
REQUIRED_REQUIREMENTS = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "openai",
    "twilio",
    "gspread",
    "google-auth",
    "reportlab",
]


def main() -> int:
    checks = [
        ("requirements.txt exists", requirements_exists),
        ("requirements.txt has production packages", requirements_has_packages),
        ("app imports successfully", app_imports),
        ("/health route exists", lambda: route_exists("/health")),
        ("/status route exists", lambda: route_exists("/status")),
        ("/webhook/whatsapp route exists", lambda: route_exists("/webhook/whatsapp")),
        ("old Twilio route still exists", lambda: route_exists("/webhooks/twilio/whatsapp")),
        ("/debug/config route exists", lambda: route_exists("/debug/config")),
        ("/debug/whatsapp-test route exists", lambda: route_exists("/debug/whatsapp-test")),
        ("/debug/report-test route exists", lambda: route_exists("/debug/report-test")),
        ("APP_BASE_URL config works", app_base_url_config_works),
        (".env.example has required production env vars", env_example_has_required_keys),
        ("render.yaml exists", lambda: file_exists("render.yaml")),
        ("railway.json exists", lambda: file_exists("railway.json")),
        ("fly.toml exists", lambda: file_exists("fly.toml")),
        ("Procfile exists", lambda: file_exists("Procfile")),
        ("Dockerfile exists", lambda: file_exists("Dockerfile")),
        ("smoke test script exists", lambda: file_exists("scripts/smoke_test.py")),
        ("deployment docs exist", lambda: file_exists("DEPLOY_NOW.md") and file_exists("README_PRODUCTION.md")),
        ("start command documented", start_command_documented),
    ]

    failed = 0
    for label, check in checks:
        try:
            ok = bool(check())
        except Exception as exc:
            ok = False
            print(f"{label}: FAIL ({exc})")
        else:
            print(f"{label}: {'PASS' if ok else 'FAIL'}")
        if not ok:
            failed += 1

    if failed:
        print(f"FINAL RESULT: FAIL ({failed} checks failed)")
        return 1
    print("FINAL RESULT: PRODUCTION READY")
    return 0


def requirements_exists() -> bool:
    return (ROOT / "requirements.txt").exists()


def requirements_has_packages() -> bool:
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    return all(package in text for package in REQUIRED_REQUIREMENTS)


def app_imports() -> bool:
    add_root_to_path()
    import app.main  # noqa: F401

    return True


def route_exists(path: str) -> bool:
    add_root_to_path()
    from app.main import app

    return any(getattr(route, "path", None) == path for route in app.routes)


def app_base_url_config_works() -> bool:
    add_root_to_path()
    from app.config import Settings

    settings = Settings(_env_file=None, APP_BASE_URL="https://pharmareen.example.com")
    return settings.public_base_url == "https://pharmareen.example.com"


def env_example_has_required_keys() -> bool:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    return all(f"{key}=" in text for key in REQUIRED_ENV_KEYS)


def file_exists(name: str) -> bool:
    return (ROOT / name).exists()


def start_command_documented() -> bool:
    expected = "uvicorn app.main:app --host 0.0.0.0 --port"
    files = ["render.yaml", "railway.json", "Procfile", "Dockerfile", "README_PRODUCTION.md", "DEPLOY_NOW.md"]
    return all(expected in (ROOT / file_name).read_text(encoding="utf-8") for file_name in files)


def add_root_to_path() -> None:
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


if __name__ == "__main__":
    raise SystemExit(main())
