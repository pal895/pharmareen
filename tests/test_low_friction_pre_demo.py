from __future__ import annotations

from app.config import Settings
from app.intake import parse_operating_commands
from app.main import report_public_base_url
from fastapi.testclient import TestClient
import app.main as main


def test_shortcuts_and_mixed_commands_parse_without_failing_whole_message():
    commands = parse_operating_commands("Panadol 2, ORS 1, Antacid 3, later Panadol 1, Panadol stock")

    assert commands is not None
    assert [command.kind for command in commands] == ["sale", "sale", "sale", "late_sale", "stock_check"]
    assert [command.drug_name for command in commands] == ["Panadol", "ORS", "Antacid", "Panadol", "Panadol"]


def test_low_typing_shortcuts_parse_to_panadol_actions():
    sale = parse_operating_commands("p2")
    restock = parse_operating_commands("p +20")
    stock = parse_operating_commands("stock p")

    assert sale and sale[0].kind == "sale"
    assert sale[0].drug_name == "Panadol"
    assert sale[0].quantity == 2
    assert restock and restock[0].kind == "restock"
    assert restock[0].drug_name == "Panadol"
    assert restock[0].quantity == 20
    assert stock and stock[0].kind == "stock_check"
    assert stock[0].drug_name == "Panadol"


def test_report_links_use_configured_app_base_url_even_for_runtime_urls(monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    settings = Settings(_env_file=None, public_base_url="https://temporary.riker.replit.dev")

    assert report_public_base_url(settings) == "https://temporary.riker.replit.dev"


def test_report_links_use_replit_dev_domain_when_no_app_base_url(monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("REPLIT_DEV_DOMAIN", "pharmareen-dev.riker.replit.dev")
    settings = Settings(_env_file=None, public_base_url="")

    assert report_public_base_url(settings) == "https://pharmareen-dev.riker.replit.dev"


def test_report_links_honor_explicit_public_base_url(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://pharmareen.example.com")
    settings = Settings(_env_file=None, public_base_url="http://localhost:5000")

    assert report_public_base_url(settings) == "https://pharmareen.example.com"


def test_supervisor_scripts_are_present_and_bridge_is_optional():
    start_script = open("start.sh", encoding="utf-8").read()
    start_all = open("scripts/start_all.sh", encoding="utf-8").read()
    check_all = open("scripts/check_all.sh", encoding="utf-8").read()
    stop_all = open("scripts/stop_all.sh", encoding="utf-8").read()
    deploy_start = open("scripts/replit_deploy_start.sh", encoding="utf-8").read()
    replit_config = open(".replit", encoding="utf-8").read()
    replit_nix = open("replit.nix", encoding="utf-8").read()

    assert "WHATSAPP_BRIDGE_ENABLED" in start_script
    assert "bridge.log" in start_script
    assert "bridge.pid" in start_script
    assert "local_whatsapp_bridge.js" in start_script
    assert "npm install" in start_script
    assert "BRIDGE_SCRIPT" in start_script
    assert "Backend stays running" in start_script
    assert "WHATSAPP_BRIDGE_ENABLED" in start_all
    assert "/debug/system-status" in check_all
    assert "local_whatsapp_bridge.js" in stop_all
    assert "git pull origin main" in deploy_start
    assert "Refreshing offline app static copies" in deploy_start
    assert "cp -f static/offline_app/* offline_app/" in deploy_start
    assert "npm install" in deploy_start
    assert "pkill -f \"uvicorn app.main:app\"" in deploy_start
    assert "WHATSAPP_BRIDGE_ENABLED" in deploy_start
    assert "/debug/offline-app" in deploy_start
    assert "/debug/system-status" in deploy_start
    assert 'run = "bash start.sh"' in replit_config
    assert "nodejs-20" in replit_config
    assert "pkgs.nodejs-20_x" in replit_nix
    assert "pkgs.nodePackages.npm" in replit_nix


def test_system_status_reports_bridge_runtime_readiness():
    with TestClient(main.app) as client:
        response = client.get("/debug/system-status")

    assert response.status_code == 200
    data = response.json()
    assert data["backend"] == "ok"
    assert data["offline_app"] == "ok"
    assert data["bridge"] in {"running", "missing"}
    assert data["node"] in {"installed", "missing"}
    assert data["details"]["backend"]["running"] is True
    assert "node_available" in data["details"]["bridge"]
    assert "npm_available" in data["details"]["bridge"]
    assert data["details"]["bridge"]["bridge_script"] == "local_whatsapp_bridge.js"
    assert data["details"]["bridge"]["bridge_script_exists"] is True
    assert data["details"]["bridge"]["endpoint"].endswith("/bridge/whatsapp-web")
