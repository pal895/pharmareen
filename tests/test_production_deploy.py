from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_deployment_files_exist_and_include_start_commands():
    required_files = [
        "render.yaml",
        "railway.json",
        "fly.toml",
        "Dockerfile",
        "Procfile",
        "runtime.txt",
        "DEPLOY_NOW.md",
    ]
    for file_name in required_files:
        assert (ROOT / file_name).exists(), file_name

    expected = "uvicorn app.main:app --host 0.0.0.0 --port"
    for file_name in ["render.yaml", "railway.json", "Dockerfile", "Procfile", "DEPLOY_NOW.md"]:
        assert expected in (ROOT / file_name).read_text(encoding="utf-8")


def test_env_example_has_required_production_keys():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    required_keys = [
        "APP_BASE_URL=",
        "TWILIO_ACCOUNT_SID=",
        "TWILIO_AUTH_TOKEN=",
        "TWILIO_WHATSAPP_NUMBER=",
        "OWNER_WHATSAPP_TO=",
        "GOOGLE_SHEET_ID=",
        "GOOGLE_SHEETS_CREDENTIALS=",
        "OPENAI_API_KEY=",
        "ENABLE_VOICE_INPUT=true",
        "REPORT_STORAGE_MODE=local",
        "REPORT_PUBLIC_DIR=reports_pdf",
    ]
    for key in required_keys:
        assert key in text


def test_production_readiness_script_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_production_ready.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "FINAL RESULT: PRODUCTION READY" in result.stdout
