from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def test_python_app_main_starts_and_reports_clear_local_status(tmp_path):
    root = Path(__file__).resolve().parents[1]
    port = "8799"
    env = os.environ.copy()
    env["PORT"] = port
    env["APP_BASE_URL"] = f"http://localhost:{port}"
    env["PYTHONUNBUFFERED"] = "1"

    process = subprocess.Popen(
        [sys.executable, str(root / "app" / "main.py")],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    output = ""
    try:
        body = wait_for_health(port, process)
    finally:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate(timeout=10)

    assert '"status":"ok"' in body.replace(" ", "")
    assert "PharMareen System Running" in output
    assert "Status: http://localhost:8799/status" in output
    assert "localhost is not public" in output
    assert "Missing production settings" in output


def wait_for_health(port: str, process: subprocess.Popen[str]) -> str:
    deadline = time.time() + 35
    last_error = ""
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise AssertionError(f"app/main.py exited early with {process.returncode}:\n{output}")
        try:
            with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=2) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.5)
    raise AssertionError(f"app/main.py did not start in time: {last_error}")
