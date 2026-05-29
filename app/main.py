from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from html import escape
from contextlib import asynccontextmanager
from dataclasses import dataclass
from difflib import SequenceMatcher
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai import AIService, ai_usage_snapshot, log_ai_route_decision
from app.config import Settings, get_settings
from app.demo_store import DemoPharmacyStore
from app.intake import IntakeService, normalize_key, normalize_spoken_command_text, parse_operating_commands
from app.pdf_reports import generate_daily_report_pdf, reports_pdf_dir
from app.reports import LowStockWarning, ReportMetrics, ReportService, build_report_metrics, build_transaction_metrics, low_stock_from_items
from app.routes.admin import router as admin_router
from app.routes.meta_webhook import meta_callback_router, router as meta_whatsapp_router
from app.routes.offline_sync import router as offline_sync_router
from app.services.photo_intake import (
    append_photo_intake_log,
    build_invoice_extraction_placeholder,
    build_media_job_placeholder,
    classify_photo_for_intake,
    ensure_photo_intake_dirs,
    google_sheets_preparation_helpers,
    read_photo_intake_stats,
    save_photo_upload,
)
from app.sheets import GoogleSheetsStore, SHEETS_UNAVAILABLE_MESSAGE, SheetsUnavailableError
from app.transcription import TranscriptionService, TranscriptionUnavailableError
from app.utils import now_in_timezone, parse_int
from app.whatsapp import WhatsAppClient, xml_message_response


logger = logging.getLogger(__name__)
processed_message_sids: set[str] = set()
offline_synced_entry_ids: set[str] = set()
offline_synced_entry_results: dict[str, dict[str, Any]] = {}
offline_media_job_results: dict[str, dict[str, Any]] = {}
offline_whatsapp_outbox: list[dict[str, Any]] = []
offline_whatsapp_confirmation_history: list[dict[str, Any]] = []
pending_voice_confirmations: dict[str, tuple[str, float]] = {}
pending_invoice_reviews: dict[str, dict[str, Any]] = {}
PENDING_VOICE_TTL_SECONDS = 600
startup_status_printed = False
XML_CONTENT_TYPE = "application/xml"
last_openai_error: dict[str, Any] = {
    "feature": "",
    "message": "",
    "quota_missing": False,
    "timestamp": "",
}
VOICE_QUOTA_REPLY = "🎧 Voice received safely. AI transcription is ready but OpenAI credits are not active yet."
PHOTO_QUOTA_REPLY = "📷 Photo received safely. Saved for review."
DEFAULT_PUBLIC_BASE_URL = "https://pharmareen-1--pal895.replit.app"
OFFLINE_BUILD_VERSION = "launch-usability-v2026-05-29-1"
OFFLINE_FRONTEND_MARKER = f"PHARMAREEN REAL PATH BUILD {OFFLINE_BUILD_VERSION}"
OFFLINE_APP_DIR = PROJECT_ROOT / "static" / "offline_app"
OFFLINE_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
    "X-PharMareen-Offline-Version": OFFLINE_BUILD_VERSION,
}


def current_git_commit_short() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def offline_confirmation_state_path() -> Path:
    return PROJECT_ROOT / "data" / "offline_whatsapp_confirmations.json"


def load_offline_confirmation_state() -> None:
    if offline_whatsapp_outbox or offline_whatsapp_confirmation_history:
        return
    path = offline_confirmation_state_path()
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Offline confirmation state could not be loaded", exc_info=True)
        return
    pending = data.get("pending") if isinstance(data, dict) else []
    history = data.get("history") if isinstance(data, dict) else []
    if isinstance(pending, list):
        offline_whatsapp_outbox.extend(item for item in pending if isinstance(item, dict))
    if isinstance(history, list):
        offline_whatsapp_confirmation_history.extend(item for item in history if isinstance(item, dict))


def save_offline_confirmation_state() -> None:
    try:
        path = offline_confirmation_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "pending": offline_whatsapp_outbox,
            "history": offline_whatsapp_confirmation_history[-100:],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.warning("Offline confirmation state could not be saved", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_offline_confirmation_state()
    print_startup_console_status()
    print("PHASE6_ROUTES_LOADED /offline-app /debug/offline-app")
    try:
        get_sheet_store().ensure_schema()
    except SheetsUnavailableError:
        logger.warning(SHEETS_UNAVAILABLE_MESSAGE)
    except Exception:
        logger.exception("Google Sheets schema setup failed; app will continue running")
    yield


app = FastAPI(
    title="Pharmacy Intelligence Assistant",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/offline-app", include_in_schema=False)
async def offline_app_redirect() -> RedirectResponse:
    return RedirectResponse(url="/offline_app/index.html")


@app.get("/debug/offline-app")
async def debug_offline_app() -> dict[str, Any]:
    return {
        "offline_app_installed": True,
        "offline_routes_ready": True,
        "sync_endpoint_ready": True,
        "offline_log_exists": (PROJECT_ROOT / "data" / "offline_sync_log.jsonl").exists(),
        "multi_command_parser_ready": (OFFLINE_APP_DIR / "parser.js").exists(),
        "photo_queue_ready": True,
        "audio_queue_ready": True,
        "voice_queue_ready": True,
        "persistent_storage_ready": True,
        "auto_sync_ready": True,
        "frontend_marker": OFFLINE_FRONTEND_MARKER,
        "served_index_path": str(OFFLINE_APP_DIR / "index.html"),
    }


@app.get("/debug/version")
async def debug_version() -> dict[str, Any]:
    return {
        "status": "ok",
        "offline_build_version": OFFLINE_BUILD_VERSION,
        "offline_frontend_marker": OFFLINE_FRONTEND_MARKER,
        "git_commit": current_git_commit_short(),
        "offline_app_index": str(OFFLINE_APP_DIR / "index.html"),
        "cache_control": OFFLINE_NO_CACHE_HEADERS["Cache-Control"],
    }


@app.get("/offline/medicine-names")
async def offline_medicine_names() -> dict[str, Any]:
    try:
        names = get_intake_service().store.list_master_drug_names()
    except Exception:
        names = []
    cleaned: list[str] = []
    seen: set[str] = set()
    for name in names:
        text = str(name or "").strip()
        key = normalize_key(text)
        if not text or key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return {"status": "ok", "medicines": cleaned[:200], "ai_used": False}


@app.get("/offline_app/index.html", include_in_schema=False)
async def offline_app_index_file() -> FileResponse:
    return FileResponse(
        OFFLINE_APP_DIR / "index.html",
        media_type="text/html",
        headers=OFFLINE_NO_CACHE_HEADERS,
    )


@app.get("/offline_app/app.js", include_in_schema=False)
async def offline_app_js_file() -> FileResponse:
    return FileResponse(
        OFFLINE_APP_DIR / "app.js",
        media_type="application/javascript",
        headers=OFFLINE_NO_CACHE_HEADERS,
    )


@app.get("/offline_app/parser.js", include_in_schema=False)
async def offline_parser_js_file() -> FileResponse:
    return FileResponse(
        OFFLINE_APP_DIR / "parser.js",
        media_type="application/javascript",
        headers=OFFLINE_NO_CACHE_HEADERS,
    )


@app.get("/offline_app/service-worker.js", include_in_schema=False)
async def offline_service_worker_file() -> FileResponse:
    return FileResponse(
        OFFLINE_APP_DIR / "service-worker.js",
        media_type="application/javascript",
        headers=OFFLINE_NO_CACHE_HEADERS,
    )


@app.get("/offline_app/styles.css", include_in_schema=False)
async def offline_styles_file() -> FileResponse:
    return FileResponse(
        OFFLINE_APP_DIR / "styles.css",
        media_type="text/css",
        headers=OFFLINE_NO_CACHE_HEADERS,
    )


@app.get("/offline_app/{asset_path:path}", include_in_schema=False)
async def offline_app_asset_file(asset_path: str) -> FileResponse:
    safe_path = Path(asset_path)
    if safe_path.is_absolute() or ".." in safe_path.parts:
        raise HTTPException(status_code=404, detail="Offline app asset not found.")
    file_path = OFFLINE_APP_DIR / safe_path
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Offline app asset not found.")
    media_types = {
        ".html": "text/html",
        ".js": "application/javascript",
        ".css": "text/css",
        ".json": "application/json",
        ".svg": "image/svg+xml",
    }
    return FileResponse(
        file_path,
        media_type=media_types.get(file_path.suffix.lower(), "application/octet-stream"),
        headers=OFFLINE_NO_CACHE_HEADERS,
    )


app.mount(
    "/offline_app",
    StaticFiles(directory=str(OFFLINE_APP_DIR), html=True),
    name="offline_app",
)

app.include_router(meta_whatsapp_router)
app.include_router(meta_callback_router)
app.include_router(offline_sync_router)
app.include_router(admin_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/offline-test")
def offline_test() -> dict[str, str]:
    return {"offline": "ok"}


@app.get("/offline-html-test", response_class=HTMLResponse)
def offline_html_test() -> str:
    return "<h1>PharMareen Offline Public Test OK</h1>"


def offline_entry_action(entry: dict[str, Any]) -> str:
    return str(entry.get("action") or entry.get("type") or entry.get("action_type") or "").strip().lower()


def offline_entry_to_command(entry: dict[str, Any]) -> str:
    command_text = str(entry.get("command_text") or "").strip()
    raw_text = str(entry.get("raw_text") or "").strip()
    action = offline_entry_action(entry)
    if command_text:
        return command_text
    if raw_text and action not in {"photo", "image", "voice", "audio"}:
        return raw_text

    drug_name = str(entry.get("drug_name") or "").strip()
    quantity = entry.get("quantity") or entry.get("total_received_quantity") or ""
    if not drug_name or not quantity:
        return ""
    if action == "sale":
        parts = [drug_name, "sold", str(quantity)]
        unit = str(entry.get("unit") or "").strip()
        if unit:
            parts.append(unit)
        payment = str(entry.get("payment_method") or "").strip()
        if payment:
            parts.append(payment)
        discount = entry.get("discount")
        if discount not in (None, "", 0):
            parts.extend(["discount", str(discount)])
        return " ".join(parts).strip()
    if action in {"restock", "bonus_restock", "discount_restock"}:
        parts = [drug_name, "restock", str(quantity)]
        unit = str(entry.get("unit") or "").strip()
        if unit:
            parts.append(unit)
        bonus_quantity = entry.get("bonus_quantity") or 0
        if bonus_quantity:
            parts.extend(["bonus", str(bonus_quantity)])
        actual_paid = entry.get("actual_paid_amount")
        if actual_paid not in (None, ""):
            parts.extend(["cost", str(actual_paid)])
        discount = entry.get("discount_amount")
        if discount not in (None, "", 0):
            parts.extend(["discount", str(discount)])
        supplier = str(entry.get("supplier") or "").strip()
        if supplier:
            parts.extend(["supplier", supplier])
        invoice = str(entry.get("invoice_number") or "").strip()
        if invoice:
            parts.extend(["invoice", invoice])
        batch = str(entry.get("batch_number") or "").strip()
        if batch:
            parts.extend(["batch", batch])
        expiry = str(entry.get("expiry_date") or "").strip()
        if expiry:
            parts.extend(["expiry", expiry])
        barcode = str(entry.get("barcode") or "").strip()
        if barcode:
            parts.extend(["barcode", barcode])
        return " ".join(parts).strip()
    return ""


def offline_sale_stock_safety_reply(entry: dict[str, Any], command_text: str, service: Any) -> str | None:
    """Block real offline sale sync before text routing when stock is unavailable."""
    action = offline_entry_action(entry)
    drug_name = str(entry.get("drug_name") or "").strip()
    quantity = parse_int(entry.get("quantity"), default=None)
    base_quantity = parse_int(entry.get("base_quantity"), default=None)
    unit = str(entry.get("unit") or "").strip()
    payment_method = str(entry.get("payment_method") or "").strip() or "Cash"

    if action != "sale":
        try:
            commands = parse_operating_commands(command_text) or []
        except Exception:
            commands = []
        sale_commands = [command for command in commands if command.kind in {"sale", "late_sale"}]
        if len(commands) != 1 or not sale_commands:
            return None
        command = sale_commands[0]
        drug_name = command.drug_name
        quantity = command.quantity
        base_quantity = command.base_quantity
        unit = command.unit
        payment_method = command.payment_method or payment_method

    if not drug_name or quantity is None or quantity <= 0:
        return None

    store = getattr(service, "store", None)
    safety_stock_lookup = getattr(store, "find_stock_for_safety", None)
    find_stock = safety_stock_lookup if callable(safety_stock_lookup) else getattr(store, "find_stock", None)
    if not callable(find_stock):
        return None
    try:
        pharmacy_id = str(entry.get("pharmacy_id") or "").strip()
        if callable(safety_stock_lookup):
            stock = find_stock(drug_name, pharmacy_id=pharmacy_id)
        else:
            stock = find_stock(drug_name)
    except Exception:
        return None
    if stock is None:
        return None

    if base_quantity is None:
        try:
            base_quantity = service._to_base_quantity(stock.drug_name, quantity, unit) if unit else quantity
        except Exception:
            base_quantity = quantity
    current_stock = parse_int(getattr(stock, "current_stock", None), default=None)
    if current_stock is None or base_quantity is None or current_stock >= base_quantity:
        return None

    print(
        "STOCK_SAFETY_BLOCKED_OFFLINE_SYNC "
        f"drug={stock.drug_name} requested={base_quantity} available={current_stock} "
        f"pharmacy_id={entry.get('pharmacy_id') or ''}",
        flush=True,
    )

    record_missed = getattr(service, "_record_missed_sale_attempt", None)
    if callable(record_missed):
        result = record_missed(
            stock=stock,
            display_quantity=quantity,
            base_quantity=base_quantity,
            unit=unit,
            payment_method=payment_method,
            note="Offline sync sale blocked because source-of-truth stock was insufficient.",
        )
        return getattr(result, "reply", None) or None

    available = max(current_stock, 0)
    return (
        f"⚠️ {stock.drug_name} out of stock. Sale not recorded. "
        f"Missed sale saved: {stock.drug_name} x{quantity}. Stock left: {available}"
    )


def offline_media_reply(entry: dict[str, Any]) -> str:
    action = offline_entry_action(entry)
    if action in {"photo", "image"}:
        purpose = str(entry.get("purpose") or "").replace("_", " ").strip()
        if "stock" in purpose:
            return "📷 Stock photo saved safely\nStatus: Needs review"
        if "receipt" in purpose:
            return "📷 Supplier receipt saved safely\nStatus: Needs review"
        return "📷 Invoice photo saved safely\nStatus: Needs review"
    if action in {"voice", "audio"}:
        return "🎤 Voice note saved safely\nStatus: Needs review"
    return "Voice/photo saved safely. Needs review."


def media_base64_from_offline_entry(entry: dict[str, Any]) -> tuple[str, str]:
    media_base64 = str(entry.get("media_base64") or "").strip()
    mime_type = str(entry.get("media_mime_type") or entry.get("file_type") or "").strip()
    data_url = str(entry.get("data_url") or "").strip()
    if not media_base64 and data_url:
        if data_url.startswith("data:") and "," in data_url:
            header, encoded = data_url.split(",", 1)
            media_base64 = encoded.strip()
            if not mime_type:
                mime_type = header[5:].split(";", 1)[0].strip()
        else:
            media_base64 = data_url
    return media_base64, mime_type


VOICE_MEDICINE_NAMES = [
    "Panadol",
    "Paracetamol",
    "Amoxyl",
    "Amoxicillin",
    "Cetirizine",
    "ORS",
    "Insulin",
    "Antacid",
    "Piriton",
    "Glucose",
    "Cough Syrup",
    "Antibiotic Cream",
    "WaterGuard",
    "PEP Lime Cordial",
]

VOICE_MEDICINE_ALIASES = {
    "anadol": "Panadol",
    "panado": "Panadol",
    "pandol": "Panadol",
    "panadol": "Panadol",
    "piritone": "Piriton",
    "piraton": "Piriton",
    "piriton": "Piriton",
    "pcm": "Paracetamol",
    "paracet": "Paracetamol",
    "paracetmol": "Paracetamol",
    "paracetamol": "Paracetamol",
    "amox": "Amoxyl",
    "amoxil": "Amoxyl",
    "amoxyl": "Amoxyl",
    "amoxicilin": "Amoxicillin",
    "amoxicillin": "Amoxicillin",
    "cet": "Cetirizine",
    "cetrizine": "Cetirizine",
    "cetirizine": "Cetirizine",
    "ors": "ORS",
    "glucose": "Glucose",
    "insulin": "Insulin",
    "antacid": "Antacid",
    "cough syrup": "Cough Syrup",
    "coughsirup": "Cough Syrup",
    "antibiotic cream": "Antibiotic Cream",
    "antibioticcream": "Antibiotic Cream",
    "water guard": "WaterGuard",
    "waterguard": "WaterGuard",
    "watergard": "WaterGuard",
    "pep lime": "PEP Lime Cordial",
    "pep lime cordial": "PEP Lime Cordial",
    "peplimecordial": "PEP Lime Cordial",
}

VOICE_NON_MEDICINE_WORDS = {
    "mbili",
    "bili",
    "billi",
    "melikas",
    "melikash",
    "mbilikas",
    "mbilikash",
    "tukas",
    "cash",
    "cashi",
    "kash",
    "pesa",
    "mpesa",
    "m-pesa",
    "credit",
    "card",
    "mixed",
    "moja",
    "tatu",
    "nne",
    "tano",
    "sita",
    "saba",
    "nane",
    "tisa",
    "kumi",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "ongeza",
    "niliuza",
    "nimeuza",
    "nimetoa",
    "sold",
    "sell",
    "sale",
    "restock",
}


def voice_token_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.lower(), right.lower()).ratio()


def split_joined_voice_words(text: str) -> str:
    clean = text
    quantity_words = "moja|mbili|bili|billi|tatu|nne|tano|sita|saba|nane|tisa|kumi|one|two|too|to|three|four|five|six|seven|eight|nine|ten|1|2|3|4|5|6|7|8|9|10"
    payment_words = "cash|cashi|kash|mpesa|m-pesa|pesa|credit|card"
    clean = re.sub(r"\b([A-Za-z]{3,})one(mpesa|cash|kash)\b", r"\1 one \2", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\b([A-Za-z]{3,})moja(mpesa|cash|kash)\b", r"\1 moja \2", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\b([A-Za-z]{3,})mbili(mpesa|cash|kash)\b", r"\1 mbili \2", clean, flags=re.IGNORECASE)
    clean = re.sub(rf"\b({quantity_words})\s*({payment_words})\b", r"\1 \2", clean, flags=re.IGNORECASE)
    clean = re.sub(rf"\b([A-Za-z]{{3,}})({quantity_words})\b", r"\1 \2", clean, flags=re.IGNORECASE)
    clean = re.sub(rf"\b([A-Za-z]{{3,}})({payment_words})\b", r"\1 \2", clean, flags=re.IGNORECASE)
    clean = re.sub(rf"\b([A-Za-z]{{3,}})(\d+)\b", r"\1 \2", clean, flags=re.IGNORECASE)
    return clean


def apply_voice_medicine_aliases(text: str) -> str:
    clean = text
    for alias, medicine in sorted(VOICE_MEDICINE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias == "pep lime":
            pattern = r"\bpep\s+lime\b(?!\s+cordial)"
        else:
            pattern = r"\b" + re.escape(alias).replace(r"\ ", r"\s+") + r"\b"
        clean = re.sub(pattern, medicine, clean, flags=re.IGNORECASE)
    return clean


def voice_medicine_names_from_inventory() -> list[str]:
    names: list[str] = []
    try:
        names.extend(str(name).strip() for name in get_intake_service().store.list_master_drug_names())
    except Exception:
        pass
    names.extend(VOICE_MEDICINE_NAMES)
    seen: set[str] = set()
    unique: list[str] = []
    for name in names:
        key = re.sub(r"[^a-z0-9]+", "", name.lower())
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(name)
    return unique


def repair_voice_medicine_tokens(text: str, medicine_names: list[str] | None = None) -> str:
    names = medicine_names or VOICE_MEDICINE_NAMES
    tokens = text.split()
    repaired: list[str] = []
    for token in tokens:
        bare = re.sub(r"[^A-Za-z]", "", token)
        if len(bare) < 5 or bare.lower() in VOICE_NON_MEDICINE_WORDS:
            repaired.append(token)
            continue
        best = max(names, key=lambda name: voice_token_similarity(bare, name)) if names else token
        score = voice_token_similarity(bare, best)
        if score >= 0.80:
            repaired.append(best)
        else:
            repaired.append(token)
    return " ".join(repaired)


def clean_voice_transcript_for_intake(transcript: str, medicine_names: list[str] | None = None) -> str:
    clean = " ".join(str(transcript or "").replace("\n", " ").split())
    if not clean:
        return ""
    clean = re.sub(r"[,;]+", ",", clean)
    clean = re.sub(r"\b(?:melikas|melikash|melicash|mbelikas|mbelikash|mbilikas|mbilikash)\b", "mbili cash", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\b([A-Za-z]{3,})(?:melikas|melikash|melicash|mbelikas|mbelikash|mbilikas|mbilikash)\b", r"\1 mbili cash", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\b(?:mbe?le|mbele|mbeli|mbili|mbil|mbil[iy]?|billi|bili|billy)\s*(?:kash|cash)\b", "mbili cash", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\b(?:mbe?le|mbele|mbeli)(?=cash|kash)\b", "mbili ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\b(?:tukas|tukash|two\s*kash|two\s*cash|too\s*cash|to\s*cash)\b", "two cash", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\b(?:moja|mojaa)\s*(?:mpesa|m-pesa)\b", "moja mpesa", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\b(?:tatu|tattoo)\s*(?:kash|cash|mpesa|m-pesa)\b", lambda m: m.group(0).replace("kash", "cash"), clean, flags=re.IGNORECASE)
    clean = split_joined_voice_words(clean)
    clean = re.sub(r"\b(?:billi|bili|billy|mbil|mbilii|mbele|mbeli)\b", "mbili", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\b(?:kash|cashi)\b", "cash", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bpesa\b", "mpesa", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bmpessa\b", "mpesa", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^nimetoa\s+", "sold ", clean, flags=re.IGNORECASE)
    clean = apply_voice_medicine_aliases(clean)
    clean = repair_voice_medicine_tokens(clean, medicine_names=medicine_names)
    comma_parts = [part.strip() for part in clean.split(",") if part.strip()]
    if len(comma_parts) > 1 and all(len(part.split()) == 1 for part in comma_parts):
        clean = " ".join(comma_parts)
    else:
        clean = ", ".join(comma_parts) if comma_parts else clean
    clean = re.sub(r"\s+na\s+(?=[A-Za-z])", ", ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\b(moja|mbili|tatu|one|two|three|\d+)\s*,\s*(cash|mpesa|m-pesa|credit|card)\b", r"\1 \2", clean, flags=re.IGNORECASE)
    return " ".join(clean.split())

def compact_offline_reply(reply: str, max_lines: int = 3) -> str:
    lines = [line.strip() for line in str(reply or "").replace("\r", "\n").splitlines() if line.strip()]
    clean_lines: list[str] = []
    for line in lines:
        if line.lower().startswith("command:"):
            continue
        if line.lower() == "result:":
            continue
        clean_lines.append(line)
    if not clean_lines:
        return "Synced safely"
    summary = " | ".join(clean_lines[:max_lines])
    return summary[:280]


def offline_result_summary(entry: dict[str, Any], result: dict[str, Any]) -> str:
    action = offline_entry_action(entry)
    reply = str(result.get("reply") or "").strip()
    if reply:
        summary = compact_offline_reply(reply, max_lines=4 if action in {"voice", "audio", "photo", "image"} else 3)
        if action in {"voice", "audio"} and "voice" not in summary.lower():
            return f"Offline voice processed | {summary}"
        return summary
    if action == "sale":
        drug = str(entry.get("drug_name") or "Sale").strip()
        quantity = entry.get("quantity") or ""
        payment = str(entry.get("payment_method") or "").strip()
        return f"{drug} x{quantity}{(' ' + payment) if payment else ''} recorded".strip()
    if action == "stock_check":
        drug = str(entry.get("drug_name") or "Stock").strip()
        return f"{drug} stock checked"
    if action in {"restock", "bonus_restock", "discount_restock"}:
        drug = str(entry.get("drug_name") or "Restock").strip()
        quantity = entry.get("total_received_quantity") or entry.get("quantity") or ""
        return f"{drug} +{quantity} recorded".strip()
    if action in {"photo", "image"}:
        return "Invoice photo saved safely"
    if action in {"voice", "audio"}:
        return "Voice note saved safely"
    return "Synced safely"


def offline_sync_success_message(entries: list[dict[str, Any]], synced: list[dict[str, Any]]) -> str:
    synced_by_id = {str(item.get("id") or ""): item for item in synced}
    lines = ["✅ Offline records synced safely"]
    for entry in entries:
        entry_id = str(entry.get("id") or entry.get("action_id") or "").strip()
        result = synced_by_id.get(entry_id)
        if not result:
            continue
        lines.append(f"• {offline_result_summary(entry, result)}")
    time_format = "%#I:%M %p" if os.name == "nt" else "%-I:%M %p"
    lines.append(f"Synced at {now_in_timezone(get_settings().timezone).strftime(time_format)}")
    return "\n".join(lines)


def remember_offline_synced_result(entry_id: str, record: dict[str, Any]) -> dict[str, Any]:
    stored = dict(record)
    stored.setdefault("id", entry_id)
    if not stored.get("reply") and stored.get("result_summary"):
        stored["reply"] = stored["result_summary"]
    if not stored.get("result_summary") and stored.get("reply"):
        stored["result_summary"] = compact_offline_reply(str(stored.get("reply") or ""))
    stored.setdefault("whatsapp_confirmation", "ready")
    offline_synced_entry_ids.add(entry_id)
    offline_synced_entry_results[entry_id] = stored
    return stored


def offline_media_job_id(entry: dict[str, Any]) -> str:
    for key in ("job_id", "event_id", "media_job_id", "upload_id", "content_hash"):
        value = str(entry.get(key) or "").strip()
        if value:
            return value if value.startswith("media-") else f"media-{value}" if key == "content_hash" else value
    data_url = str(entry.get("data_url") or entry.get("dataUrl") or "").strip()
    if data_url:
        return f"media-{hashlib.sha256(data_url.encode('utf-8')).hexdigest()}"
    for key in ("id", "action_id"):
        value = str(entry.get(key) or "").strip()
        if value:
            return value
    raw = "|".join(
        str(entry.get(key) or "")
        for key in ("file_name", "file_type", "purpose", "size", "timestamp")
    )
    return f"media-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}" if raw.strip("|") else ""


def cache_offline_media_result(job_id: str, record: dict[str, Any]) -> dict[str, Any]:
    cached = dict(record)
    cached["job_id"] = job_id
    offline_media_job_results[job_id] = cached
    return cached


def offline_confirmation_recipient(payload: dict[str, Any]) -> str:
    settings = get_settings()
    entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
    entry_confirmation = ""
    for entry in entries:
        if isinstance(entry, dict):
            entry_confirmation = str(entry.get("confirmation_whatsapp") or "").strip()
            if entry_confirmation:
                break
    raw = str(
        payload.get("confirmation_whatsapp")
        or payload.get("confirmation_whatsapp_number")
        or payload.get("linked_whatsapp")
        or entry_confirmation
        or payload.get("sender")
        or payload.get("whatsapp_sender")
        or settings.owner_whatsapp_to
        or ""
    ).strip()
    if not raw and settings.allowed_whatsapp_numbers.strip():
        raw = settings.allowed_whatsapp_numbers.split(",", 1)[0].strip()
    if not raw:
        return ""
    if "@" in raw:
        return raw
    digits = re.sub(r"\D", "", raw)
    return f"{digits}@s.whatsapp.net" if digits else raw


def has_explicit_offline_confirmation_recipient(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if str(
        payload.get("confirmation_whatsapp")
        or payload.get("confirmation_whatsapp_number")
        or payload.get("linked_whatsapp")
        or ""
    ).strip():
        return True
    entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
    return any(
        isinstance(entry, dict) and str(entry.get("confirmation_whatsapp") or "").strip()
        for entry in entries
    )


def queue_offline_whatsapp_confirmation(recipient: str, message: str, *, dedupe_key: str = "") -> dict[str, Any] | None:
    if not recipient or not message.strip():
        return None
    load_offline_confirmation_state()
    if dedupe_key:
        for existing in [*offline_whatsapp_outbox, *offline_whatsapp_confirmation_history]:
            if existing.get("dedupe_key") == dedupe_key and existing.get("to") == recipient:
                return {"status": "not_queued", "reason": "duplicate", "id": existing.get("id", ""), "to": mask_phone(recipient)}
    item = {
        "id": f"offline-confirm-{int(time.time() * 1000)}-{len(offline_whatsapp_outbox) + 1}",
        "to": recipient,
        "message": message.strip(),
        "created_at": now_in_timezone(get_settings().timezone).isoformat(timespec="seconds"),
        "status": "pending",
        "attempts": 0,
        "last_error": "",
        "dedupe_key": dedupe_key,
    }
    offline_whatsapp_outbox.append(item)
    save_offline_confirmation_state()
    print(f"offline confirmation queued for {mask_phone(recipient)}", flush=True)
    return {"status": "queued", "id": item["id"], "to": mask_phone(recipient)}


@app.get("/offline/whatsapp-confirmations")
def offline_whatsapp_confirmations(limit: int = Query(default=10, ge=1, le=50)) -> dict[str, Any]:
    load_offline_confirmation_state()
    pending = offline_whatsapp_outbox[:limit]
    return {
        "status": "ok",
        "pending_count": len(offline_whatsapp_outbox),
        "confirmations": pending,
        "pending": pending,
    }


@app.get("/debug/offline-confirmations")
def debug_offline_confirmations() -> dict[str, Any]:
    load_offline_confirmation_state()
    return {
        "status": "ok",
        "pending_count": len(offline_whatsapp_outbox),
        "pending": [
            {
                "id": str(item.get("id") or ""),
                "to": mask_phone(str(item.get("to") or "")),
                "message_preview": str(item.get("message") or "")[:120],
                "created_at": str(item.get("created_at") or ""),
                "attempts": int(item.get("attempts") or 0),
                "last_error": str(item.get("last_error") or ""),
            }
            for item in offline_whatsapp_outbox[:20]
        ],
        "sent_count": len([item for item in offline_whatsapp_confirmation_history if item.get("status") == "sent"]),
        "failed_count": len([item for item in offline_whatsapp_confirmation_history if item.get("status") == "failed"]),
        "recent": [
            {
                "id": str(item.get("id") or ""),
                "to": mask_phone(str(item.get("to") or "")),
                "status": str(item.get("status") or ""),
                "message_preview": str(item.get("message") or "")[:120],
                "created_at": str(item.get("created_at") or ""),
                "updated_at": str(item.get("updated_at") or ""),
                "last_error": str(item.get("last_error") or ""),
            }
            for item in offline_whatsapp_confirmation_history[-20:]
        ],
    }


@app.post("/offline/whatsapp-confirmations/ack")
async def offline_whatsapp_confirmations_ack(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    ids = {str(item).strip() for item in payload.get("ids", []) if str(item).strip()} if isinstance(payload, dict) else set()
    if not ids:
        return {"status": "ok", "acked": 0}
    before = len(offline_whatsapp_outbox)
    acked_items = [dict(item) for item in offline_whatsapp_outbox if str(item.get("id")) in ids]
    offline_whatsapp_outbox[:] = [item for item in offline_whatsapp_outbox if str(item.get("id")) not in ids]
    updated_at = now_in_timezone(get_settings().timezone).isoformat(timespec="seconds")
    for item in acked_items:
        item["status"] = "sent"
        item["updated_at"] = updated_at
        offline_whatsapp_confirmation_history.append(item)
        print(f"OFFLINE_CONFIRMATION_ACKED id={item.get('id', '')} to={mask_phone(str(item.get('to') or ''))}", flush=True)
    save_offline_confirmation_state()
    return {"status": "ok", "acked": before - len(offline_whatsapp_outbox)}


@app.post("/offline/whatsapp-confirmations/fail")
async def offline_whatsapp_confirmations_fail(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    item_id = str(payload.get("id") or "").strip() if isinstance(payload, dict) else ""
    error = sanitize_error_message(payload.get("error") or "send_failed") if isinstance(payload, dict) else "send_failed"
    if not item_id:
        return {"status": "error", "updated": 0, "error": "Missing id."}
    load_offline_confirmation_state()
    updated = 0
    updated_at = now_in_timezone(get_settings().timezone).isoformat(timespec="seconds")
    for item in offline_whatsapp_outbox:
        if str(item.get("id")) == item_id:
            item["attempts"] = int(item.get("attempts") or 0) + 1
            item["last_error"] = error
            item["updated_at"] = updated_at
            failed_record = dict(item)
            failed_record["status"] = "failed"
            offline_whatsapp_confirmation_history.append(failed_record)
            print(
                f"OFFLINE_CONFIRMATION_FAILED id={item_id} "
                f"to={mask_phone(str(item.get('to') or ''))} reason={error}",
                flush=True,
            )
            updated += 1
            break
    if updated:
        save_offline_confirmation_state()
    return {"status": "ok", "updated": updated}


@app.post("/debug/offline-confirmations/test")
async def debug_queue_test_offline_confirmation(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    raw_recipient = ""
    if isinstance(payload, dict):
        raw_recipient = str(payload.get("to") or payload.get("confirmation_whatsapp") or "").strip()
    recipient = offline_confirmation_recipient(
        {
            "confirmation_whatsapp": raw_recipient
        }
    )
    message = str(
        payload.get("message")
        if isinstance(payload, dict)
        else ""
    ).strip() or "✅ Offline confirmation test from PharMareen."
    queued = queue_offline_whatsapp_confirmation(recipient, message)
    return {"status": "ok" if queued else "error", "queued": queued or {"status": "not_queued"}}


@app.post("/debug/offline-confirmations/send-test")
async def debug_send_test_offline_confirmation(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    raw_recipient = str((payload.get("to") if isinstance(payload, dict) else "") or "").strip() or "+254728571649"
    recipient = offline_confirmation_recipient({"confirmation_whatsapp": raw_recipient})
    message = str((payload.get("message") if isinstance(payload, dict) else "") or "").strip()
    if not message:
        message = "✅ PharMareen bridge delivery test. If you see this, offline confirmations can reach WhatsApp."
    queued = queue_offline_whatsapp_confirmation(recipient, message)
    print(
        "OFFLINE_CONFIRMATION_QUEUED_REAL_SYNC "
        f"status={queued.get('status') if queued else 'not_queued'} "
        f"to={queued.get('to') if queued else ''} debug_send_test=True",
        flush=True,
    )
    return {
        "status": "queued_for_bridge" if queued else "error",
        "queued": queued or {"status": "not_queued"},
        "next_step": "Watch bridge.log for BRIDGE_PICKED_OFFLINE_CONFIRMATION and WHATSAPP_CONFIRMATION_SEND_RESULT.",
    }


@app.post("/offline/sync")
async def offline_sync_entries(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    entries = payload.get("entries") if isinstance(payload, dict) else None
    confirmation_whatsapp_present = has_explicit_offline_confirmation_recipient(payload if isinstance(payload, dict) else {})
    print(
        "REAL_OFFLINE_SYNC_RECEIVED "
        f"entries={len(entries) if isinstance(entries, list) else 0} "
        f"confirmation_whatsapp_present={confirmation_whatsapp_present}",
        flush=True,
    )
    if not isinstance(entries, list):
        return {"status": "error", "synced": [], "failed": [{"id": "", "error": "Send entries as a list."}], "pending": []}

    payload_items: list[dict[str, Any]] = []
    for entry in entries[:30]:
        if not isinstance(entry, dict):
            payload_items.append({"invalid": True})
            continue
        payload_items.append(
            {
                "id": str(entry.get("id") or entry.get("action_id") or "")[:80],
                "type": str(entry.get("type") or "")[:40],
                "action": str(entry.get("action") or "")[:40],
                "text": str(entry.get("command_text") or entry.get("raw_text") or "")[:160],
                "drug": str(entry.get("drug_name") or "")[:80],
                "quantity": entry.get("quantity"),
                "payment": str(entry.get("payment_method") or "")[:40],
                "confirmation_whatsapp_present": bool(str(entry.get("confirmation_whatsapp") or "").strip()),
            }
        )
    print(
        "REAL_BROWSER_OFFLINE_PAYLOAD_RECEIVED "
        + json.dumps(
            {
                "confirmation_whatsapp_present": confirmation_whatsapp_present,
                "entry_count": len(entries),
                "items": payload_items,
            },
            ensure_ascii=True,
        ),
        flush=True,
    )

    synced: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            failed.append({"id": "", "status": "failed", "error": "Entry must be an object."})
            continue
        entry_id = str(entry.get("id") or entry.get("action_id") or "").strip()
        action = offline_entry_action(entry)
        if not entry_id:
            failed.append({"id": "", "status": "failed", "error": "Missing id."})
            continue
        if entry_id in offline_synced_entry_ids:
            previous = dict(offline_synced_entry_results.get(entry_id) or {})
            if not previous:
                fallback_reply = offline_result_summary(entry, {})
                previous = {"id": entry_id, "reply": fallback_reply, "result_summary": fallback_reply, "whatsapp_confirmation": "ready"}
            previous["status"] = "already_synced"
            synced.append(previous)
            append_offline_sync_log(entry, "already_synced", str(previous.get("reply") or previous.get("result_summary") or "Synced safely"), "")
            continue
        if action in {"photo", "image", "voice", "audio"}:
            job_id = offline_media_job_id(entry)
            if job_id and job_id in offline_media_job_results and not boolish(entry.get("force_reprocess")):
                cached = dict(offline_media_job_results[job_id])
                cached["id"] = entry_id
                cached["status"] = "already_synced"
                synced.append(cached)
                log_ai_route_decision(
                    text=job_id,
                    route=str(cached.get("message_type") or action),
                    used_ai=False,
                    reason="offline_media_result_cache",
                    job_id=job_id,
                    from_cache=True,
                )
                append_offline_sync_log(entry, "already_synced", str(cached.get("reply") or cached.get("result_summary") or "Synced safely"), "")
                continue
            media_base64, media_mime_type = media_base64_from_offline_entry(entry)
            if media_base64 and media_mime_type:
                try:
                    result = await process_whatsapp_web_payload(
                        message="",
                        sender=str(payload.get("sender") or entry.get("sender") or "offline_app"),
                        message_id=entry_id,
                        media_base64=media_base64,
                        media_mime_type=media_mime_type,
                        media_caption=str(entry.get("command_text") or entry.get("raw_text") or entry.get("purpose") or ""),
                        media_filename=str(entry.get("file_name") or ""),
                        media_purpose=str(entry.get("purpose") or action),
                    )
                    status = "synced" if result.success else "pending"
                    record = {
                        "id": entry_id,
                        "status": status,
                        "reply": result.reply,
                        "result_summary": compact_offline_reply(result.reply),
                        "message_type": result.message_type,
                        "command_handler": result.command_handler,
                        "whatsapp_confirmation": "ready",
                        "job_id": job_id,
                    }
                    if result.success:
                        record = remember_offline_synced_result(entry_id, record)
                        if job_id:
                            cache_offline_media_result(job_id, record)
                        synced.append(record)
                        append_offline_sync_log(entry, "synced", result.reply, "")
                    else:
                        reason = result.reply or result.error_reason or "Could not process this item. Try again or remove before sync."
                        record["status"] = "failed"
                        record["reply"] = reason
                        record["result_summary"] = compact_offline_reply(reason)
                        if job_id:
                            cache_offline_media_result(job_id, record)
                        failed.append({"id": entry_id, "status": "failed", "error": reason, "job_id": job_id})
                        append_offline_sync_log(entry, "pending", result.reply, result.error_reason)
                except Exception as exc:
                    reason = sanitize_error_message(exc)
                    if not reason or "doctype" in reason.lower() or "unexpected token" in reason.lower():
                        reason = "Could not process this item. Try again or remove before sync."
                    record = {
                        "id": entry_id,
                        "status": "failed",
                        "reply": reason,
                        "result_summary": compact_offline_reply(reason),
                        "message_type": action,
                        "command_handler": "offline_media_failed",
                        "whatsapp_confirmation": "ready",
                        "job_id": job_id,
                    }
                    if job_id:
                        cache_offline_media_result(job_id, record)
                    failed.append({"id": entry_id, "status": "failed", "error": reason, "job_id": job_id})
                    append_offline_sync_log(entry, "pending", "", reason)
                continue
            reply = offline_media_reply(entry)
            record = remember_offline_synced_result(entry_id, {"id": entry_id, "status": "media_logged", "reply": reply, "result_summary": compact_offline_reply(reply), "whatsapp_confirmation": "ready", "job_id": job_id})
            if job_id:
                cache_offline_media_result(job_id, record)
            synced.append(record)
            append_offline_sync_log(entry, "media_logged", reply, "")
            continue
        if action == "barcode_mapping":
            reply = "Barcode saved for this medicine."
            record = remember_offline_synced_result(entry_id, {"id": entry_id, "status": "synced", "reply": reply, "result_summary": compact_offline_reply(reply), "whatsapp_confirmation": "ready"})
            synced.append(record)
            append_offline_sync_log(entry, "synced", reply, "")
            continue

        command_text = offline_entry_to_command(entry)
        if not command_text:
            reason = "Unknown offline entry saved for review."
            pending.append({"id": entry_id, "status": "pending", "reason": reason})
            append_offline_sync_log(entry, "pending", "", reason)
            continue
        entry_for_log = {**entry, "command_text": command_text}
        try:
            sync_sender = str(payload.get("sender") or entry.get("sender") or "offline_app")
            service = get_intake_service()
            stock_safety_reply = offline_sale_stock_safety_reply(entry, command_text, service)
            if stock_safety_reply:
                record = remember_offline_synced_result(
                    entry_id,
                    {
                        "id": entry_id,
                        "status": "synced",
                        "reply": stock_safety_reply,
                        "result_summary": compact_offline_reply(stock_safety_reply),
                        "whatsapp_confirmation": "ready",
                        "stock_safety": "missed_sale",
                    },
                )
                synced.append(record)
                append_offline_sync_log(entry_for_log, "synced", stock_safety_reply, "")
                continue
            reply = process_intake_text_for_sender(command_text, sync_sender)
            if is_offline_sync_failure_reply(reply):
                reason = sanitize_error_message(ValueError(reply))
                pending.append({"id": entry_id, "status": "pending", "reason": reason})
                append_offline_sync_log(entry_for_log, "pending", "", reason)
                continue
            record = remember_offline_synced_result(entry_id, {"id": entry_id, "status": "synced", "reply": reply, "result_summary": compact_offline_reply(reply), "whatsapp_confirmation": "ready"})
            synced.append(record)
            append_offline_sync_log(entry_for_log, "synced", reply, "")
        except Exception as exc:
            reason = sanitize_error_message(exc)
            pending.append({"id": entry_id, "status": "pending", "reason": reason})
            append_offline_sync_log(entry_for_log, "pending", "", reason)
    message = offline_sync_success_message(entries, synced) if synced else ""
    for item in synced:
        summary_payload = {
            "id": str(item.get("id") or ""),
            "status": str(item.get("status") or ""),
            "summary": compact_offline_reply(str(item.get("reply") or item.get("result_summary") or "")),
        }
        print(
            "REAL_OFFLINE_RESULT_SUMMARY "
            + json.dumps(summary_payload, ensure_ascii=True),
            flush=True,
        )
    has_new_synced_records = any(str(item.get("status") or "") != "already_synced" for item in synced)
    explicit_confirmation_recipient = has_explicit_offline_confirmation_recipient(payload if isinstance(payload, dict) else {})
    confirmation_recipient = offline_confirmation_recipient(payload if isinstance(payload, dict) else {})
    confirmation_status = None
    if message and confirmation_recipient and (has_new_synced_records or explicit_confirmation_recipient):
        synced_ids = ",".join(
            sorted(str(item.get("job_id") or item.get("id") or "") for item in synced if item.get("job_id") or item.get("id"))
        )
        confirmation_dedupe_key = hashlib.sha256(f"{confirmation_recipient}|{synced_ids}|{message}".encode("utf-8")).hexdigest()
        confirmation_status = queue_offline_whatsapp_confirmation(confirmation_recipient, message, dedupe_key=confirmation_dedupe_key)
        print(
            "OFFLINE_CONFIRMATION_QUEUED_REAL_SYNC "
            f"status={confirmation_status.get('status') if confirmation_status else 'not_queued'} "
            f"to={confirmation_status.get('to') if confirmation_status else ''}",
            flush=True,
        )
    else:
        reason = "missing_message" if not message else "missing_recipient" if not confirmation_recipient else "already_synced_without_explicit_recipient"
        print(
            "offline confirmation not queued "
            f"reason={reason} synced={len(synced)} explicit_recipient={explicit_confirmation_recipient}",
            flush=True,
        )
    return {
        "status": "ok",
        "message": message,
        "whatsapp_reply": message,
        "admin_message": message,
        "whatsapp_confirmation": confirmation_status or {"status": "not_queued"},
        "synced": synced,
        "failed": failed,
        "pending": pending,
    }


@app.get("/status", response_class=HTMLResponse)
def startup_status_page() -> str:
    settings = get_settings()
    store = get_sheet_store()
    base_url = effective_app_base_url(settings)
    bridge_url = whatsapp_bridge_url_for(settings)
    sheets_ready = bool(store.is_available)
    base_is_local = is_local_base_url(base_url)
    base_is_placeholder = is_placeholder_base_url(base_url)
    production_ready = base_url.startswith("https://") and not base_is_local and not base_is_placeholder
    warning = ""
    if base_is_local:
        warning = """
        <section class="warning">
          <strong>WhatsApp Web MVP can still run locally.</strong><br>
          Public report links will open on phones only after APP_BASE_URL is set to the Replit public URL.
        </section>
        """
    elif base_is_placeholder:
        warning = """
        <section class="warning">
          <strong>APP_BASE_URL is still a placeholder.</strong><br>
          Replace it with your real public Replit URL before sharing PDF report links.
        </section>
        """
    elif production_ready:
        warning = """
        <section class="ready">
          <strong>Public URL looks ready.</strong><br>
          Run the WhatsApp Web bridge, scan the QR code, then send "start" on WhatsApp.
        </section>
        """

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>PharMareen Status</title>
      <style>
        body {{ margin:0; font-family: Arial, sans-serif; background:#f6f8fb; color:#132238; }}
        main {{ max-width: 820px; margin: 0 auto; padding: 28px 18px; }}
        h1 {{ margin: 0 0 6px; font-size: 30px; }}
        .card {{ background:white; border:1px solid #d8e2eb; border-radius:8px; padding:18px; margin-top:16px; }}
        .row {{ display:flex; justify-content:space-between; gap:16px; border-bottom:1px solid #edf2f7; padding:10px 0; }}
        .row:last-child {{ border-bottom:0; }}
        .ok {{ color:#176b35; font-weight:bold; }}
        .bad {{ color:#a33a1f; font-weight:bold; }}
        .warning {{ background:#fff4df; border:1px solid #e8b45f; border-radius:8px; padding:14px; margin-top:16px; }}
        .ready {{ background:#e8f7ee; border:1px solid #79bd8f; border-radius:8px; padding:14px; margin-top:16px; }}
        code {{ background:#edf2f7; padding:3px 6px; border-radius:4px; word-break:break-all; }}
      </style>
    </head>
    <body>
      <main>
        <h1>PharMareen Status</h1>
        <p>Use this page before testing the WhatsApp Web MVP bridge.</p>
        {warning}
        <section class="card">
          <div class="row"><span>App running</span><span class="ok">yes</span></div>
          <div class="row"><span>Google Sheets connected</span><span class="{status_class(sheets_ready)}">{yes_no(sheets_ready)}</span></div>
          <div class="row"><span>WhatsApp provider</span><span><code>{escape(settings.whatsapp_provider)}</code></span></div>
          <div class="row"><span>Public HTTPS URL ready</span><span class="{status_class(production_ready)}">{yes_no(production_ready)}</span></div>
          <div class="row"><span>APP_BASE_URL</span><span><code>{escape(base_url)}</code></span></div>
          <div class="row"><span>WhatsApp Web bridge endpoint</span><span><code>{escape(bridge_url)}</code></span></div>
        </section>
        <section class="card">
          <p><strong>Local app:</strong> <a href="http://localhost:5000">http://localhost:5000</a></p>
          <p><strong>Health check:</strong> <a href="http://localhost:5000/health">http://localhost:5000/health</a></p>
          <p><strong>Bridge:</strong> run <code>./start_with_whatsapp_web.sh</code>, scan the QR code, then send <code>start</code>.</p>
        </section>
      </main>
    </body>
    </html>
    """


@app.get("/landing", response_class=HTMLResponse)
def landing_page() -> str:
    settings = get_settings()
    whatsapp_number = settings.whatsapp_number.replace("whatsapp:", "") or "Your WhatsApp number"
    click_link = whatsapp_click_link(settings.whatsapp_number)
    public_status_url = f"{effective_app_base_url(settings)}/status"
    qr_link = "https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=" + quote(click_link, safe="")
    return f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <link rel="manifest" href="/manifest.json">
      <title>PharMareen</title>
      <style>
        body {{ margin:0; font-family: Arial, sans-serif; background:#f6f8fb; color:#14213d; }}
        main {{ max-width: 760px; margin: 0 auto; padding: 32px 20px; }}
        h1 {{ font-size: 34px; margin: 0 0 8px; }}
        h2 {{ font-size: 20px; margin-top: 28px; }}
        .panel {{ background:white; border:1px solid #d9e2ec; border-radius:8px; padding:18px; margin-top:18px; }}
        .button {{ display:inline-block; background:#1f4e79; color:white; padding:12px 16px; border-radius:6px; text-decoration:none; font-weight:bold; }}
        .qr {{ width:180px; height:180px; border:1px solid #d9e2ec; border-radius:8px; }}
        code {{ background:#eef3f8; padding:3px 6px; border-radius:4px; }}
        li {{ margin: 8px 0; }}
      </style>
    </head>
    <body>
      <main>
        <h1>PharMareen</h1>
        <p>Run your pharmacy from WhatsApp.</p>
        <section class="panel">
          <h2>Save This WhatsApp Number</h2>
          <p><strong>{whatsapp_number}</strong></p>
          <p>Save this WhatsApp number and send <code>start</code>.</p>
          <p><a class="button" href="{click_link}">Open WhatsApp</a></p>
          <p><img class="qr" alt="WhatsApp start QR code" src="{qr_link}"></p>
        </section>
        <section class="panel">
          <h2>Basic Commands</h2>
          <ul>
            <li><code>Panadol 2</code> records a sale.</li>
            <li><code>+Panadol 20 2000</code> records stock received and cost.</li>
            <li><code>Panadol stock</code> checks stock.</li>
            <li><code>Insulin no stock</code> records missed demand.</li>
            <li><code>report today</code> sends a WhatsApp summary and PDF download link.</li>
          </ul>
        </section>
        <section class="panel">
          <h2>Reports</h2>
          <p>Daily and weekly reports are generated as printable PDFs with phone download links.</p>
          <p>Production status: <a href="{public_status_url}">{public_status_url}</a></p>
        </section>
        <section class="panel">
          <h2>Support</h2>
          <p>{settings.support_contact}</p>
        </section>
      </main>
    </body>
    </html>
    """


@app.get("/manifest.json")
def manifest() -> JSONResponse:
    return JSONResponse(
        {
            "name": "PharMareen",
            "short_name": "PharMareen",
            "start_url": "/landing",
            "display": "standalone",
            "background_color": "#f6f8fb",
            "theme_color": "#1f4e79",
            "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
        }
    )


@app.get("/icon.svg")
def icon() -> Response:
    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
      <rect width="192" height="192" rx="36" fill="#1f4e79"/>
      <path d="M52 96h88M96 52v88" stroke="#fff" stroke-width="22" stroke-linecap="round"/>
    </svg>
    """
    return Response(content=svg.strip(), media_type="image/svg+xml")


@app.get("/reports/download/{filename}")
def download_report(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    report_path = find_report_pdf(safe_name)
    if not report_path.exists() and safe_name.lower().endswith(".pdf"):
        report_path = regenerate_missing_report_pdf(safe_name)
    if not report_path.exists() or report_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Report not found.")
    return FileResponse(report_path, media_type="application/pdf", filename=safe_name)


def regenerate_missing_report_pdf(safe_name: str) -> Path:
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", safe_name)
    if not date_match:
        return reports_pdf_dir() / safe_name
    report_date = date_match.group(1)
    settings = get_settings()
    try:
        store = get_sheet_store()
        try:
            transactions = store.read_transactions(report_date)
        except Exception:
            transactions = []
        try:
            logs = store.read_daily_logs(report_date)
        except Exception:
            logs = []
        try:
            low_stock = low_stock_from_items(store.list_low_stock_items())
        except Exception:
            low_stock = []
        metrics = build_transaction_metrics(report_date, transactions, low_stock) if transactions else build_report_metrics(report_date, logs, low_stock)
    except Exception:
        metrics = ReportMetrics(
            report_date=report_date,
            total_sales=0,
            total_items_sold=0,
            sale_transactions=0,
            most_requested=[],
            most_sold=[],
            missed_sales=[],
            not_sold=[],
            low_stock_warnings=[],
            peak_activity_time="No sales yet",
        )
    try:
        generated = generate_daily_report_pdf(
            metrics,
            pharmacy_name=settings.pharmacy_name or "PharMareen",
            report_time=now_in_timezone(settings.timezone).strftime("%H:%M"),
        )
        target = reports_pdf_dir() / safe_name
        if generated.name != safe_name:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(generated, target)
            return target
        return generated
    except Exception:
        logger.exception("REPORT_PDF_REGEN_FAILED filename=%s", safe_name)
        return reports_pdf_dir() / safe_name


def report_pdf_search_dirs() -> list[Path]:
    candidates: list[Path] = []
    configured_reports = os.environ.get("PHARMAREEN_REPORTS_DIR")
    if configured_reports:
        candidates.append(Path(configured_reports).expanduser())
    report_public_dir = os.environ.get("REPORT_PUBLIC_DIR")
    if report_public_dir:
        candidates.append(PROJECT_ROOT / report_public_dir)
        candidates.append(Path.cwd() / report_public_dir)
    candidates.extend(
        [
            reports_pdf_dir(),
            PROJECT_ROOT / "reports_pdf",
            Path.cwd() / "reports_pdf",
            Path.home() / "Documents" / "reports_pdf",
            Path(tempfile.gettempdir()) / "reports_pdf",
        ]
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve() if candidate.exists() else candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def find_report_pdf(safe_name: str) -> Path:
    for folder in report_pdf_search_dirs():
        candidate = folder / safe_name
        if candidate.exists() and candidate.suffix.lower() == ".pdf":
            return candidate
    return reports_pdf_dir() / safe_name


def whatsapp_click_link(value: str) -> str:
    digits = "".join(character for character in str(value or "").replace("whatsapp:", "") if character.isdigit())
    return f"https://wa.me/{digits}?text=start" if digits else "https://wa.me/?text=start"


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def status_class(value: bool) -> str:
    return "ok" if value else "bad"


def effective_app_base_url(settings: Settings) -> str:
    return (settings.public_base_url or "http://localhost:5000").rstrip("/")


def report_public_base_url(settings: Settings) -> str:
    explicit_public = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if explicit_public.startswith("https://") and not is_placeholder_base_url(explicit_public):
        return explicit_public
    configured = (settings.public_base_url or "").strip().rstrip("/")
    if (
        configured.startswith("https://")
        and not is_local_base_url(configured)
        and not is_placeholder_base_url(configured)
    ):
        return configured
    replit_dev_domain = (os.getenv("REPLIT_DEV_DOMAIN") or "").strip().strip("/")
    if replit_dev_domain:
        if not replit_dev_domain.startswith(("http://", "https://")):
            replit_dev_domain = f"https://{replit_dev_domain}"
        replit_dev_domain = replit_dev_domain.rstrip("/")
        if replit_dev_domain.startswith("https://") and not is_placeholder_base_url(replit_dev_domain):
            return replit_dev_domain
    return DEFAULT_PUBLIC_BASE_URL


def whatsapp_bridge_url_for(settings: Settings) -> str:
    return f"{effective_app_base_url(settings)}/bridge/whatsapp-web"


def webhook_url_for(settings: Settings) -> str:
    return whatsapp_bridge_url_for(settings)


def is_local_base_url(value: str | None) -> bool:
    text = str(value or "").lower()
    return not text or "localhost" in text or "127.0.0.1" in text or text.startswith("http://0.0.0.0")


def is_placeholder_base_url(value: str | None) -> bool:
    text = str(value or "").lower()
    placeholders = [
        "your-domain",
        "your-production-domain",
        "your-public-url.example.com",
    ]
    return any(placeholder in text for placeholder in placeholders)


def whatsapp_bridge_configured(settings: Settings) -> bool:
    return True


def parse_allowed_whatsapp_numbers(settings: Settings) -> set[str]:
    raw = str(settings.allowed_whatsapp_numbers or "")
    numbers: set[str] = set()
    for item in raw.replace(";", ",").split(","):
        digits = phone_digits(item)
        if digits:
            numbers.add(digits)
    return numbers


def phone_digits(value: str) -> str:
    text = str(value or "").replace("whatsapp:", "")
    return "".join(character for character in text if character.isdigit())


def whatsapp_jid_domain(value: str) -> str:
    text = str(value or "").strip().lower()
    if "@" not in text:
        return "unknown"
    return f"@{text.rsplit('@', 1)[1].split(':', 1)[0]}"


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def is_direct_whatsapp_sender(sender: str, is_group: bool = False, is_broadcast: bool = False) -> bool:
    text = str(sender or "").strip().lower()
    if is_group or is_broadcast:
        return False
    if not text:
        return False
    blocked_markers = ("@g.us", "status@broadcast", "@broadcast", "@newsletter", "newsletter", "channel")
    if any(marker in text for marker in blocked_markers):
        return False
    return whatsapp_jid_domain(text) in {"@s.whatsapp.net", "@lid"}


def whatsapp_sender_allowed(
    sender: str,
    settings: Settings,
    is_group: bool = False,
    is_broadcast: bool = False,
    allow_all_direct_chats_for_test: bool | None = None,
) -> tuple[bool, str]:
    if not is_direct_whatsapp_sender(sender, is_group=is_group, is_broadcast=is_broadcast):
        return False, "not_direct_chat"
    effective_test_mode = settings.allow_all_direct_chats_for_test or boolish(allow_all_direct_chats_for_test)
    if effective_test_mode:
        return True, "test_mode_allowed_direct_chat"
    if whatsapp_jid_domain(sender) == "@lid":
        return False, "sender_direct_but_no_phone_digits"
    allowed_numbers = parse_allowed_whatsapp_numbers(settings)
    if not allowed_numbers:
        return False, "safe_mode_no_allowlist"
    digits = phone_digits(sender)
    if not digits:
        return False, "sender_direct_but_no_phone_digits"
    if digits in allowed_numbers:
        return True, "allowed_number"
    return False, "sender_not_allowed"


def should_use_demo_store(settings: Settings) -> bool:
    if settings.demo_mode:
        return True
    return not (settings.google_sheets_spreadsheet_id.strip() and google_credentials_present(settings))


def google_credentials_present(settings: Settings) -> bool:
    env_value = (
        os.getenv("GOOGLE_SHEETS_CREDENTIALS")
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        or ""
    ).strip()
    configured = str(settings.google_service_account_json or "").strip()
    if env_value:
        return True
    if configured.startswith("{") and "client_email" in configured:
        return True
    if configured and Path(configured).expanduser().exists():
        return True
    return False


def missing_startup_settings(settings: Settings) -> list[str]:
    missing: list[str] = []
    if not settings.google_sheets_spreadsheet_id.strip():
        missing.append("GOOGLE_SHEET_ID")
    if settings.enable_voice_input and not settings.openai_api_key.strip():
        missing.append("OPENAI_API_KEY for voice notes")
    return missing


def startup_console_lines() -> list[str]:
    settings = get_settings()
    port = os.getenv("PORT", "5000")
    lines = [
        "PharMareen System Running",
        f"Local app: http://localhost:{port}",
        f"Health: http://localhost:{port}/health",
        f"Status: http://localhost:{port}/status",
        "WhatsApp Web bridge: run ./start_with_whatsapp_web.sh and scan the QR code",
    ]
    base_url = effective_app_base_url(settings)
    if is_local_base_url(base_url):
        lines.extend(
            [
                "",
                "WARNING: APP_BASE_URL localhost is not public. WhatsApp Web can still process messages, but phone PDF links need the public Replit URL.",
            ]
        )
    missing = missing_startup_settings(settings)
    if missing:
        lines.extend(
            [
                "",
                "Local mode can still run.",
                "Missing production settings: " + ", ".join(missing),
            ]
        )
    return lines


def print_startup_console_status() -> None:
    global startup_status_printed
    if startup_status_printed:
        return
    startup_status_printed = True
    for line in startup_console_lines():
        print(line, flush=True)


@app.get("/test")
def test_google_sheets() -> dict[str, str]:
    store = get_sheet_store()
    if not store.is_available:
        return {
            "status": "sheets_unavailable",
            "message": SHEETS_UNAVAILABLE_MESSAGE,
        }

    return {
        "status": "ok",
        "message": "Google Sheets is configured.",
    }


@app.get("/debug/config")
def debug_config() -> dict[str, Any]:
    settings = get_settings()
    raw_base_url = (settings.public_base_url or "").strip()
    return {
        "app_running": True,
        "app_base_url": raw_base_url,
        "app_base_url_is_https": raw_base_url.lower().startswith("https://"),
        "app_base_url_has_placeholder": is_placeholder_base_url(raw_base_url),
        "whatsapp_provider": settings.whatsapp_provider,
        "whatsapp_number_present": bool(settings.whatsapp_number.strip()),
        "allowed_whatsapp_numbers_configured": bool(parse_allowed_whatsapp_numbers(settings)),
        "demo_mode_active": should_use_demo_store(settings),
        "whatsapp_web_bridge_endpoint": whatsapp_bridge_url_for(settings),
        "owner_whatsapp_to_present": bool(settings.owner_whatsapp_to.strip()),
        "google_sheet_id_present": bool(settings.google_sheets_spreadsheet_id.strip()),
        "google_credentials_present": google_credentials_present(settings),
        "openai_api_key_present": bool(settings.openai_api_key.strip()),
    }


def pid_file_running(path: Path) -> bool:
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                check=False,
                capture_output=True,
                text=True,
            )
            return str(pid) in result.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def bridge_process_running(script_name: str) -> bool:
    script = str(script_name or "local_whatsapp_bridge.js")
    try:
        if os.name == "nt":
            script_pattern = script.replace("'", "''")
            command = (
                "Get-CimInstance Win32_Process | "
                f"Where-Object {{ $_.CommandLine -match '{script_pattern}' }} | "
                "Select-Object -First 1 -ExpandProperty ProcessId"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
            return bool(result.stdout.strip())
        result = subprocess.run(
            ["pgrep", "-f", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


@app.get("/debug/system-status")
def debug_system_status() -> dict[str, Any]:
    settings = get_settings()
    backend_pid = os.getpid()
    bridge_pid_file = PROJECT_ROOT / "bridge.pid"
    backend_pid_file = PROJECT_ROOT / "server.pid"
    bridge_log = PROJECT_ROOT / "bridge.log"
    bridge_script_name = os.getenv("BRIDGE_SCRIPT") or "local_whatsapp_bridge.js"
    node_available = shutil.which("node") is not None
    npm_available = shutil.which("npm") is not None
    bridge_running = pid_file_running(bridge_pid_file) or bridge_process_running(bridge_script_name)
    offline_index = OFFLINE_APP_DIR / "index.html"
    return {
        "backend": "ok",
        "offline_app": "ok" if offline_index.exists() else "missing",
        "bridge": "running" if bridge_running else "missing",
        "node": "installed" if node_available else "missing",
        "npm": "installed" if npm_available else "missing",
        "details": {
            "backend": {
                "running": True,
                "pid": backend_pid,
                "health": "ok",
            },
            "bridge": {
                "enabled": boolish(os.getenv("WHATSAPP_BRIDGE_ENABLED")),
                "pid_file_exists": bridge_pid_file.exists(),
                "running": bridge_running,
                "log_exists": bridge_log.exists(),
                "node_available": node_available,
                "npm_available": npm_available,
                "bridge_script": bridge_script_name,
                "bridge_script_exists": (PROJECT_ROOT / bridge_script_name).exists(),
                "node_modules_exists": (PROJECT_ROOT / "node_modules").exists(),
                "safe_allowlist_configured": bool(parse_allowed_whatsapp_numbers(settings)),
                "test_mode": settings.allow_all_direct_chats_for_test,
                "endpoint": whatsapp_bridge_url_for(settings),
            },
            "reports": {
                "public_base_url": report_public_base_url(settings),
                "uses_stable_replit_domain": report_public_base_url(settings).startswith(DEFAULT_PUBLIC_BASE_URL),
                "reports_directory": str(reports_pdf_dir()),
            },
            "ai": {
                "openai_key_present": bool(settings.openai_api_key.strip()),
                "invoice_ai_enabled": boolish(os.getenv("ENABLE_INVOICE_AI")) or boolish(os.getenv("ENABLE_VISION_AI")),
                "vision_ai_enabled": boolish(os.getenv("ENABLE_VISION_AI")),
                "voice_ai_enabled": boolish(os.getenv("ENABLE_VOICE_INPUT")) or bool(settings.openai_api_key.strip()),
                "usage": ai_usage_snapshot(),
                "offline_media_job_cache": {
                    "count": len(offline_media_job_results),
                    "recent_job_ids": list(offline_media_job_results.keys())[-5:],
                },
            },
            "app": {
                "app_base_url": effective_app_base_url(settings),
                "report_base_url": report_public_base_url(settings),
            },
            "startup": {
                "backend_pid_file_exists": backend_pid_file.exists(),
                "backend_log_exists": (PROJECT_ROOT / "server.log").exists(),
                "start_all_script": (PROJECT_ROOT / "scripts" / "start_all.sh").exists(),
                "check_all_script": (PROJECT_ROOT / "scripts" / "check_all.sh").exists(),
                "stop_all_script": (PROJECT_ROOT / "scripts" / "stop_all.sh").exists(),
            },
        },
    }


@app.get("/debug/voice-ai")
def debug_voice_ai() -> dict[str, Any]:
    settings = get_settings()
    return {
        "voice_pipeline_installed": True,
        "photo_pipeline_installed": True,
        "openai_key_present": bool(settings.openai_api_key.strip()),
        "last_openai_error": last_openai_error.get("message") or "",
        "last_openai_feature": last_openai_error.get("feature") or "",
        "last_openai_error_at": last_openai_error.get("timestamp") or "",
        "quota_missing": bool(last_openai_error.get("quota_missing")),
    }


@app.get("/debug/photo-ai")
def debug_photo_ai() -> dict[str, Any]:
    settings = get_settings()
    paths = ensure_photo_intake_dirs(PROJECT_ROOT)
    stats = read_photo_intake_stats(PROJECT_ROOT)
    if bool(last_openai_error.get("quota_missing")):
        quota_status = "quota_missing"
    elif settings.openai_api_key.strip():
        quota_status = "key_present_ready_when_requested"
    else:
        quota_status = "openai_key_missing"
    return {
        "photo_pipeline_installed": True,
        "upload_folder_exists": paths["upload_dir"].exists(),
        "images_received_count": stats["images_received_count"],
        "openai_key_present": bool(settings.openai_api_key.strip()),
        "openai_quota_status": quota_status,
        "extraction_pipeline_ready": True,
        "last_uploaded_image": stats["last_uploaded_image"],
        "google_sheets_helpers_ready": True,
        "google_sheets_preparation": google_sheets_preparation_helpers(),
    }


@app.post("/debug/whatsapp-test")
async def debug_whatsapp_test() -> JSONResponse:
    settings = get_settings()
    form_values = {
        "Body": "start",
        "From": "whatsapp:+254700000000",
        "To": settings.whatsapp_number or "whatsapp:+14155238886",
        "MessageSid": f"SMDEBUG{int(time.time() * 1000)}",
        "NumMedia": "0",
    }
    try:
        result = await process_whatsapp_form_values(form_values)
        response_body = xml_message_response(result.reply, media_url=result.media_url)
        return JSONResponse(
            {
                "status": "ok" if result.success else "error",
                "response_type": "whatsapp_xml",
                "command_handler": result.command_handler,
                "response_body_preview": response_body[:1000],
                "exception": result.error_reason,
            }
        )
    except Exception as exc:
        logger.exception("Debug WhatsApp test failed")
        traceback.print_exc()
        return JSONResponse(
            {
                "status": "error",
                "response_type": "exception",
                "response_body_preview": "",
                "exception": str(exc),
            },
            status_code=500,
        )


@app.get("/debug/xml-test")
def debug_xml_test() -> Response:
    return xml_response("PharMareen XML test")


@app.get("/debug/report-test")
def debug_report_test() -> JSONResponse:
    settings = get_settings()
    try:
        today = now_in_timezone(settings.timezone).date().isoformat()
        metrics = ReportMetrics(
            report_date=today,
            total_sales=440,
            total_cost=280,
            gross_profit=160,
            total_items_sold=2,
            sale_transactions=1,
            most_requested=[("Panadol", 2), ("Insulin", 1)],
            most_sold=[("Panadol", 2)],
            missed_sales=[("Insulin", 1)],
            not_sold=[],
            low_stock_warnings=[LowStockWarning("Insulin", 1, 2)],
            peak_activity_time="4PM - 6PM",
            restocks=[("Panadol", 20)],
            peak_sales_count=1,
            peak_items_sold=2,
        )
        pdf_path = generate_daily_report_pdf(
            metrics,
            pharmacy_name=settings.pharmacy_name,
            report_time=now_in_timezone(settings.timezone).strftime("%H:%M"),
        )
        public_pdf_url = f"{report_public_base_url(settings)}/reports/download/{pdf_path.name}"
        return JSONResponse(
            {
                "status": "ok",
                "pdf_path": str(pdf_path),
                "public_pdf_url": public_pdf_url,
                "file_exists": pdf_path.exists(),
            }
        )
    except Exception as exc:
        logger.exception("Debug report test failed")
        traceback.print_exc()
        return JSONResponse(
            {
                "status": "error",
                "pdf_path": "",
                "public_pdf_url": "",
                "file_exists": False,
                "exception": str(exc),
            },
            status_code=500,
        )


@app.post("/intake/test")
async def intake_test(request: Request) -> dict[str, str]:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Send JSON like: {\"message\":\"Panadol sold 2\"}") from None

    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")

    reply = get_intake_service().process_text(message)
    return {
        "message": message,
        "reply": reply,
    }




@app.post("/bridge/whatsapp-web")
async def whatsapp_web_bridge(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Send JSON like: {\"message\":\"Panadol 2\", \"from\":\"254700000000\"}") from None

    message = str(payload.get("message") or payload.get("body") or "").strip()
    sender = str(payload.get("from") or payload.get("sender") or "whatsapp-web").strip()
    message_id = str(payload.get("message_id") or payload.get("id") or "").strip()
    media_base64 = str(payload.get("media_base64") or "").strip()
    media_mime_type = str(payload.get("media_mime_type") or payload.get("mimetype") or "").strip()
    media_caption = str(payload.get("caption") or payload.get("media_caption") or payload.get("message_caption") or "").strip()
    media_filename = str(payload.get("file_name") or payload.get("filename") or payload.get("media_filename") or "").strip()
    media_purpose = str(payload.get("purpose") or payload.get("media_purpose") or "").strip()
    voice_transcribe_only = boolish(
        payload.get("voice_transcribe_only")
        or payload.get("transcribe_only")
    )
    is_group = bool(payload.get("is_group"))
    is_broadcast = bool(payload.get("is_broadcast"))
    allow_all_direct_chats_for_test = boolish(
        payload.get("allow_all_direct_chats_for_test")
        or payload.get("ALLOW_ALL_DIRECT_CHATS_FOR_TEST")
    )
    if not message and not media_base64:
        raise HTTPException(status_code=400, detail="Message or media is required.")

    settings = get_settings()
    allowed, reason = whatsapp_sender_allowed(
        sender,
        settings,
        is_group=is_group,
        is_broadcast=is_broadcast,
        allow_all_direct_chats_for_test=allow_all_direct_chats_for_test,
    )
    if not allowed:
        logger.info(
            "WHATSAPP_WEB_IGNORED sender=%s jid_domain=%s reason=%s",
            mask_phone(sender),
            whatsapp_jid_domain(sender),
            reason,
        )
        return {
            "status": "ignored",
            "reply": "",
            "media_url": None,
            "message_type": "ignored",
            "command_handler": "ignored",
            "error_reason": reason,
        }

    if allow_all_direct_chats_for_test and whatsapp_jid_domain(sender) == "@lid":
        logger.info("BACKEND_TEST_MODE_ACCEPTED_LID sender=%s jid_domain=%s", mask_phone(sender), whatsapp_jid_domain(sender))

    logger.info(
        "WHATSAPP_WEB_ACCEPTED sender=%s message_length=%s has_media=%s",
        mask_phone(sender),
        len(message),
        bool(media_base64),
    )

    result = await process_whatsapp_web_payload(
        message=message,
        sender=sender,
        message_id=message_id,
        media_base64=media_base64,
        media_mime_type=media_mime_type,
        media_caption=media_caption,
        media_filename=media_filename,
        media_purpose=media_purpose,
        voice_transcribe_only=voice_transcribe_only,
    )
    log_webhook_request(sender, "whatsapp_web", result.success, result.error_reason)
    logger.info("BACKEND_REPLY_TEXT sender=%s reply=%s", mask_phone(sender), result.reply)
    return {
        "status": "ok" if result.success else "error",
        "reply": result.reply,
        "media_url": result.media_url,
        "message_type": result.message_type,
        "command_handler": result.command_handler,
        "error_reason": result.error_reason,
    }


async def process_whatsapp_web_payload(
    message: str,
    sender: str,
    message_id: str = "",
    media_base64: str = "",
    media_mime_type: str = "",
    media_caption: str = "",
    media_filename: str = "",
    media_purpose: str = "",
    voice_transcribe_only: bool = False,
) -> WhatsAppProcessResult:
    if message:
        invoice_review_reply = process_pending_invoice_review_message(sender, message)
        if invoice_review_reply:
            return WhatsAppProcessResult(
                reply=invoice_review_reply,
                message_type="text",
                success=True,
                command_handler="invoice_review",
            )
        return await process_whatsapp_form_values(
            {
                "Body": message,
                "From": sender,
                "MessageSid": message_id,
                "NumMedia": "0",
            }
        )

    if media_base64 and media_mime_type.lower().startswith("audio/"):
        transcription_service = get_transcription_service()
        if not transcription_service.is_available:
            return WhatsAppProcessResult(
                reply="Voice received, but voice is not enabled yet. Send text like: Panadol 2",
                message_type="voice",
                success=False,
                error_reason="voice_not_enabled",
                command_handler="voice_note_unavailable",
            )
        try:
            audio_bytes = base64.b64decode(media_base64)
            log_ai_route_decision(
                text=message_id or media_caption or "voice",
                route="audio/transcriptions",
                used_ai=True,
                reason="voice_transcription",
                job_id=message_id,
            )
            raw_transcript = transcription_service.transcribe_audio(audio_bytes, media_mime_type)
            clear_last_openai_error("voice")
            transcript = clean_voice_transcript_for_intake(raw_transcript, medicine_names=voice_medicine_names_from_inventory())
            if voice_transcribe_only:
                clean_transcript = transcript.strip()
                if not clean_transcript:
                    raise ValueError("OpenAI returned an empty transcription")
                return WhatsAppProcessResult(
                    reply=f"🎧 Voice received: {clean_transcript}",
                    message_type="voice",
                    success=True,
                    command_handler="voice_note_transcribed",
                )
            interpreted = normalize_spoken_command_text(transcript)
            reply = process_intake_text_for_sender(interpreted, sender)
            return WhatsAppProcessResult(
                reply=voice_reply(transcript, interpreted, reply),
                message_type="voice",
                success=True,
                command_handler="voice_note_processed",
            )
        except Exception as exc:
            record_openai_error("voice", exc)
            if is_openai_quota_error(exc):
                return WhatsAppProcessResult(
                    reply=VOICE_QUOTA_REPLY,
                    message_type="voice",
                    success=True,
                    error_reason="openai_insufficient_quota",
                    command_handler="voice_note_quota_missing",
                )
            return WhatsAppProcessResult(
                reply=voice_transcription_failed_message(),
                message_type="voice",
                success=False,
                error_reason=str(exc),
                command_handler="voice_note_failed",
            )

    if media_base64 and media_mime_type.lower().startswith("image/"):
        try:
            image_bytes = base64.b64decode(media_base64)
        except Exception as exc:
            return WhatsAppProcessResult(
                reply="Photo received, but I could not read the image file. Please resend a clearer photo.",
                message_type="image",
                success=False,
                error_reason=str(exc),
                command_handler="photo_decode_failed",
            )

        settings = get_settings()
        upload = save_photo_upload(
            PROJECT_ROOT,
            sender=sender,
            message_id=message_id,
            media_type=media_mime_type,
            image_bytes=image_bytes,
            timestamp=now_in_timezone(settings.timezone).isoformat(timespec="seconds"),
        )
        classification = classify_photo_for_intake(
            filename=media_filename or upload["relative_file_path"],
            caption=media_caption,
            purpose=media_purpose,
            media_type=media_mime_type,
        )
        media_job = build_media_job_placeholder(classification)
        extraction_status = media_job["processing_status"]
        legacy_extraction_status = "saved_needs_review" if settings.openai_api_key.strip() else "saved_needs_review_openai_key_missing"
        extraction = build_invoice_extraction_placeholder(extraction_status=legacy_extraction_status)
        ai_reply = ""
        ai_requested = photo_ai_requested(media_caption, media_purpose, classification) or bool(
            settings.openai_api_key.strip() and classification.get("media_kind") == "unknown_photo"
        )
        if ai_requested:
            if not settings.openai_api_key.strip():
                extraction_status = "saved_needs_review_openai_key_missing"
                media_job["processing_status"] = extraction_status
                extraction = build_invoice_extraction_placeholder(extraction_status=extraction_status)
                ai_reply = "📷 Photo received safely. AI reading is not enabled yet."
            elif not photo_ai_active_for_request(settings, media_caption, media_purpose, classification):
                extraction_status = "saved_needs_review_ai_disabled"
                media_job["processing_status"] = extraction_status
                extraction = build_invoice_extraction_placeholder(extraction_status=extraction_status)
                ai_reply = "Photo received safely. AI reading is switched off for now."
            else:
                try:
                    log_ai_route_decision(
                        text=message_id or media_caption or media_filename or "photo",
                        route="chat/completions",
                        used_ai=True,
                        reason="photo_invoice_extraction",
                        job_id=message_id,
                    )
                    extraction_result = get_ai_service().extract_restock_from_image(image_bytes, media_mime_type)
                    clear_last_openai_error("photo")
                    extraction_status = "needs_review"
                    extraction = {
                        "extraction_status": extraction_status,
                        "confidence": extraction_result.get("confidence", 0),
                        "message": extraction_result.get("message", ""),
                        "items": extraction_result.get("items", []),
                    }
                    media_job["processing_status"] = extraction_status
                    if extraction_has_invoice_structure(extraction_result, classification):
                        store_pending_invoice_review(sender, extraction_result)
                        ai_reply = format_invoice_extraction_reply(extraction_result)
                    else:
                        ai_reply = format_shelf_photo_reply_from_extraction(extraction_result)
                except Exception as exc:
                    record_openai_error("photo", exc)
                    if is_openai_quota_error(exc):
                        extraction_status = "waiting_for_openai_credits"
                        media_job["processing_status"] = extraction_status
                        extraction = build_invoice_extraction_placeholder(extraction_status=extraction_status)
                        ai_reply = "📷 Photo received safely. AI reading is ready but OpenAI credits are not active yet."
                    else:
                        extraction_status = "failed"
                        media_job["processing_status"] = extraction_status
                        extraction = build_invoice_extraction_placeholder(extraction_status=extraction_status)
                        ai_reply = "📷 Photo received safely. AI reading needs review."
        intake_record = {
            "sender": mask_phone(sender),
            "timestamp": upload["timestamp"],
            "media_type": media_mime_type,
            "file_path": upload["relative_file_path"],
            "message_id": message_id,
            "processing_status": extraction_status,
            "classification": classification,
            "media_job": media_job,
            "byte_count": len(image_bytes),
            "source": "whatsapp_web_bridge",
            "extraction": extraction,
        }
        append_photo_intake_log(PROJECT_ROOT, intake_record)
        logger.info(
            "PHOTO_RECEIVED sender=%s message_id=%s mime=%s bytes=%s file_path=%s kind=%s status=%s ai_needed=%s",
            mask_phone(sender),
            message_id,
            media_mime_type,
            len(image_bytes),
            upload["relative_file_path"],
            classification["media_kind"],
            extraction_status,
            classification["needs_ai"],
        )
        reply = ai_reply or classification["user_message"]
        if classification["media_kind"] in {"supplier_invoice", "supplier_receipt", "handwritten_invoice", "delivery_note"}:
            if "confirmation before stock update" not in reply:
                reply = f"{reply}\nWaiting for your confirmation before stock update."
        elif classification["media_kind"] == "pharmacy_stock_shelf_photo":
            reply = f"{reply}\nReply with quantities or scan barcode."

        return WhatsAppProcessResult(
            reply=reply,
            message_type="image",
            success=True,
            error_reason="photo_saved_for_review",
            command_handler="photo_received_saved_safely",
        )

    return WhatsAppProcessResult(
        reply="Please send text for now, like: Panadol 2",
        message_type="media",
        success=False,
        error_reason="unsupported_media",
        command_handler="unsupported_media",
    )


def photo_ai_enabled() -> bool:
    return (
        boolish(os.getenv("ENABLE_INVOICE_AI"))
        or boolish(os.getenv("ENABLE_VISION_AI"))
        or boolish(os.getenv("OPENAI_ENABLED"))
    )


def photo_ai_requested(caption: str, purpose: str, classification: dict[str, Any]) -> bool:
    direct_text = " ".join([str(caption or ""), str(purpose or "")]).lower()
    if any(word in direct_text for word in ["scan", "analyze", "analyse", "read", "extract", "invoice", "receipt", "supplier"]):
        return True
    media_kind = str(classification.get("media_kind") or "")
    return photo_ai_enabled() and media_kind in {"supplier_invoice", "supplier_receipt", "handwritten_invoice", "delivery_note"}


def photo_ai_active_for_request(settings: Settings, caption: str, purpose: str, classification: dict[str, Any]) -> bool:
    if photo_ai_enabled():
        return True
    direct_text = " ".join([str(caption or ""), str(purpose or "")]).lower()
    media_kind = str(classification.get("media_kind") or "")
    invoice_like = media_kind in {"supplier_invoice", "supplier_receipt", "handwritten_invoice", "delivery_note"}
    explicit_invoice = any(word in direct_text for word in ["invoice", "receipt", "supplier", "delivery note"])
    unknown_photo = media_kind == "unknown_photo"
    return bool(settings.openai_api_key.strip() and (invoice_like or explicit_invoice or unknown_photo))


def invoice_item_name(item: dict[str, Any]) -> str:
    return str(item.get("drug_name") or item.get("medicine") or item.get("name") or "Medicine").strip()


def invoice_item_quantity(item: dict[str, Any]) -> int | None:
    raw = item.get("quantity") or item.get("total_received_quantity") or item.get("ordered_quantity")
    try:
        quantity = int(float(str(raw).strip()))
    except Exception:
        return None
    return quantity if quantity > 0 else None


def invoice_item_unit(item: dict[str, Any]) -> str:
    return str(item.get("unit") or item.get("unit_type") or "").strip()


def invoice_item_cost(item: dict[str, Any]) -> Any:
    return item.get("cost") or item.get("unit_cost") or item.get("total_cost") or item.get("total") or ""


def invoice_review_key(sender: str) -> str:
    return mask_phone(sender)


def store_pending_invoice_review(sender: str, extraction_result: dict[str, Any]) -> None:
    items = [dict(item) for item in list(extraction_result.get("items") or [])]
    if not items:
        return
    pending_invoice_reviews[invoice_review_key(sender)] = {
        "supplier": str(extraction_result.get("supplier") or "").strip(),
        "invoice_number": str(extraction_result.get("invoice_number") or extraction_result.get("invoice") or "").strip(),
        "date": str(extraction_result.get("date") or extraction_result.get("invoice_date") or "").strip(),
        "items": items,
        "created_at": now_in_timezone(get_settings().timezone).isoformat(timespec="seconds"),
    }


def invoice_review_actions_text() -> str:
    return "Review needed before stock update.\nReply: approve, add all, edit 1 qty 20, edit 1 cost 250, remove 2, or cancel."


def extraction_has_invoice_structure(extraction_result: dict[str, Any], classification: dict[str, Any]) -> bool:
    media_kind = str(classification.get("media_kind") or "")
    if media_kind in {"supplier_invoice", "supplier_receipt", "handwritten_invoice", "delivery_note"}:
        return True
    photo_type = normalize_key(extraction_result.get("photo_type") or extraction_result.get("document_type") or extraction_result.get("image_type") or "")
    if any(word in photo_type for word in ["shelf", "product", "pack", "barcode", "random", "unclear"]):
        return False
    if any(word in photo_type for word in ["invoice", "receipt", "deliverynote", "supplier"]):
        return True
    metadata_keys = ["supplier", "supplier_name", "invoice", "invoice_number", "invoice_date", "date", "total", "grand_total"]
    if any(str(extraction_result.get(key) or "").strip() for key in metadata_keys):
        return True
    for item in extraction_result.get("items") or []:
        if any(str(item.get(key) or "").strip() for key in ["supplier", "supplier_name", "invoice_number", "cost", "unit_cost", "total", "total_cost"]):
            return True
    return False


def format_shelf_photo_reply_from_extraction(extraction_result: dict[str, Any]) -> str:
    items = list(extraction_result.get("items") or [])
    lines = ["\U0001F4F7 Shelf photo analyzed"]
    if items:
        lines.append("Products seen:")
        for index, item in enumerate(items[:8], start=1):
            lines.append(f"- {invoice_item_name(item)}")
    else:
        lines.append("No clear invoice data detected.")
    lines.extend([
        "Missing:",
        "- quantities",
        "- invoice values",
        "- supplier",
        "Reply example:",
        "restock PEP Lime Cordial 10",
        "or",
        "add new item PEP Lime Cordial price 250 stock 10",
    ])
    return "\n".join(lines)


def format_invoice_extraction_reply(extraction_result: dict[str, Any]) -> str:
    items = list(extraction_result.get("items") or [])
    supplier = str(extraction_result.get("supplier") or "").strip()
    if not supplier:
        for item in items:
            supplier = str(item.get("supplier") or item.get("supplier_name") or "").strip()
            if supplier:
                break
    lines = ["\U0001F4F7 Invoice processed"]
    if supplier:
        lines.append(f"Supplier: {supplier}")
    if items:
        lines.append("Items found:")
        missing_quantity: list[str] = []
        for index, item in enumerate(items[:8], start=1):
            name = invoice_item_name(item)
            quantity = invoice_item_quantity(item)
            unit = invoice_item_unit(item)
            cost = invoice_item_cost(item)
            detail = f"{index}. {name}"
            if quantity:
                detail += f" x{quantity}"
            else:
                missing_quantity.append(name)
            if unit:
                detail += f" {unit}"
            if cost not in ("", None):
                detail += f" - {cost}"
            lines.append(detail)
        if missing_quantity:
            lines.append("Some quantities are missing. Please reply like:")
            lines.append(f"{missing_quantity[0]} 10")
        lines.append(invoice_review_actions_text())
    else:
        message = str(extraction_result.get("message") or "").strip()
        lines.append(message or "No invoice data detected.")
        lines.append("Photo saved for review. No stock updated.")
    return "\n".join(lines)


def process_pending_invoice_review_message(sender: str, message: str) -> str | None:
    key = invoice_review_key(sender)
    pending = pending_invoice_reviews.get(key)
    if not pending:
        return None
    text = " ".join(str(message or "").strip().split())
    lower = text.lower()
    if lower in {"cancel", "cancel invoice", "cancel review"}:
        pending_invoice_reviews.pop(key, None)
        return "Invoice review cancelled. No stock updated."

    items = pending.get("items") or []

    def find_invoice_item(target_text: str) -> tuple[int, dict[str, Any] | None]:
        target_clean = str(target_text or "").strip()
        if target_clean.isdigit():
            index = int(target_clean) - 1
            if 0 <= index < len(items):
                return index, items[index]
            return -1, None
        target_lower = target_clean.lower()
        for index, item in enumerate(items):
            name = invoice_item_name(item)
            if target_lower in name.lower() or name.lower() in target_lower:
                return index, item
        return -1, None

    remove_match = re.fullmatch(r"remove\s+(?:item\s+)?(\d+)", lower)
    if remove_match:
        index = int(remove_match.group(1)) - 1
        if 0 <= index < len(items):
            removed = invoice_item_name(items.pop(index))
            return f"Removed {removed} from invoice review. Reply approve to add the remaining stock."
        return "That item number was not found. Reply remove item 1, or approve."

    remove_name_match = re.fullmatch(r"remove\s+(.+)", text, flags=re.IGNORECASE)
    if remove_name_match:
        index, item = find_invoice_item(remove_name_match.group(1))
        if item is not None:
            name = invoice_item_name(item)
            items.pop(index)
            return f"Removed {name} from invoice review. Reply approve to add the remaining stock."
        return "I could not find that invoice item. Try: remove item 1."

    rename_match = re.fullmatch(r"rename\s+(.+?)\s+to\s+(.+)", text, flags=re.IGNORECASE)
    if rename_match:
        target = rename_match.group(1).strip()
        value = rename_match.group(2).strip()
        _, item = find_invoice_item(target)
        if item is not None:
            name = invoice_item_name(item)
            item["drug_name"] = value
            return f"Renamed {name} to {value}. Reply approve to add stock."
        return "I could not find that invoice item. Try: rename old name to new name."

    indexed_add_match = re.fullmatch(
        r"add\s+(\d+)\s+price\s+(\d+(?:\.\d+)?)\s+stock\s+(\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if indexed_add_match:
        _, item = find_invoice_item(indexed_add_match.group(1))
        if item is not None:
            name = invoice_item_name(item)
            item["cost"] = indexed_add_match.group(2)
            item["quantity"] = indexed_add_match.group(3)
            return f"Updated {name}: quantity {indexed_add_match.group(3)}, cost {indexed_add_match.group(2)}. Reply approve."
        return "That item number was not found. Reply add 1 price 250 stock 10."

    quick_quantity_match = re.fullmatch(r"edit\s+(.+?)\s+(?:x\s*)?(\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if quick_quantity_match:
        target = quick_quantity_match.group(1).strip()
        value = quick_quantity_match.group(2).strip()
        if normalize_key(target).split()[-1:] not in (["qty"], ["quantity"], ["cost"], ["price"], ["name"]):
            _, item = find_invoice_item(target)
            if item is not None:
                name = invoice_item_name(item)
                item["quantity"] = value
                return f"Updated {name} quantity to {value}. Reply approve to add stock."
            return "I could not find that invoice item. Try: edit Panadol quantity 20."

    edit_match = re.fullmatch(r"edit\s+(.+?)\s+(quantity|qty|cost|price|name)\s+(.+)", text, flags=re.IGNORECASE)
    if edit_match:
        target = edit_match.group(1).strip()
        field = edit_match.group(2).lower()
        value = edit_match.group(3).strip()
        _, item = find_invoice_item(target)
        if item is not None:
            name = invoice_item_name(item)
            if field in {"quantity", "qty"}:
                item["quantity"] = value
                return f"Updated {name} quantity to {value}. Reply approve to add stock."
            if field in {"cost", "price"}:
                item["cost"] = value
                return f"Updated {name} cost to {value}. Reply approve to add stock."
            item["drug_name"] = value
            return f"Updated item name to {value}. Reply approve to add stock."
        return "I could not find that invoice item. Try: edit Panadol quantity 20."

    approve_phrases = {"approve", "approved", "review approved", "add to stock", "approve invoice", "save invoice", "add all", "skip unknown"}
    if lower not in approve_phrases:
        return None

    missing = [invoice_item_name(item) for item in items if invoice_item_quantity(item) is None]
    if missing:
        return "I found item names but not quantities. Please reply like:\n" + "\n".join(f"{name} 10" for name in missing[:3])

    supplier = str(pending.get("supplier") or "").strip()
    invoice_number = str(pending.get("invoice_number") or "").strip()
    lines = ["Invoice approved and stock updated"]
    needs_setup: list[str] = []
    for item in items:
        name = invoice_item_name(item)
        quantity = invoice_item_quantity(item) or 0
        unit = invoice_item_unit(item)
        cost = invoice_item_cost(item)
        command_parts = [f"{name} restock {quantity}"]
        if unit:
            command_parts.append(unit)
        if cost not in ("", None):
            command_parts.append(f"cost {cost}")
        if supplier:
            command_parts.append(f"supplier {supplier}")
        if invoice_number:
            command_parts.append(f"invoice {invoice_number}")
        intake_reply = process_intake_text_for_sender(" ".join(command_parts), sender)
        if invoice_stock_update_needs_new_item(intake_reply):
            needs_setup.append(f"- {name} x{quantity}")
            continue
        label = f"- {name} x{quantity}"
        if unit:
            label += f" {unit}"
        label += " added"
        lines.append(label)
    if needs_setup:
        guidance = [
            "Some invoice items need item setup before stock update.",
            "New item not in stock list:",
            *needs_setup,
            "Reply: add new item PEP Lime Cordial price 250 stock 10",
            "or edit the invoice item, then approve again.",
        ]
        return "\n".join(guidance)
    pending_invoice_reviews.pop(key, None)
    return "\n".join(lines)


def invoice_stock_update_needs_new_item(reply: str) -> bool:
    normalized = str(reply or "").lower()
    return any(
        phrase in normalized
        for phrase in [
            "not found in inventory",
            "not in stock list",
            "unknown medicine",
            "medicine not found",
            "add new item",
        ]
    )

def process_intake_text_for_sender(text: str, sender: str) -> str:
    intake_service = get_intake_service()
    try:
        return intake_service.process_text(text, conversation_id=sender)
    except TypeError as exc:
        if "conversation_id" not in str(exc):
            raise
        return intake_service.process_text(text)


@app.post("/webhook/whatsapp")
async def legacy_whatsapp_form_webhook(request: Request) -> Response:
    try:
        form = await request.form()
        form_values = {key: value for key, value in form.items()}
    except Exception:
        form_values = {}

    body = str(form_values.get("Body") or "").strip()
    from_number = str(form_values.get("From") or "").strip()
    to_number = str(form_values.get("To") or "").strip()
    message_sid = str(form_values.get("MessageSid") or "").strip()
    message_type = "text"
    success = False
    error_reason = ""
    print("WHATSAPP FORM WEBHOOK HIT", flush=True)
    print(f"BODY={body}", flush=True)
    print(f"FROM={from_number}", flush=True)
    print(f"TO={to_number}", flush=True)
    print(f"MESSAGESID={message_sid}", flush=True)
    print(f"COMMAND_HANDLER={classify_command_handler(body) if body else 'voice_or_media'}", flush=True)

    try:
        result = await process_whatsapp_form_values(form_values)
        print(f"COMMAND_HANDLER_RESULT={result.command_handler}", flush=True)
        log_webhook_request(from_number, result.message_type, result.success, result.error_reason)
        return xml_response(result.reply, media_url=result.media_url)
    except Exception:
        logger.exception("Failed to process WhatsApp webhook")
        traceback.print_exc()
        reply = "Sorry, I could not understand that. Please send it like: Panadol sold 2."
        error_reason = "Unhandled processing error"
        log_webhook_request(from_number, message_type, success, error_reason)

    return xml_response(reply)


@app.post("/reports/daily")
def generate_daily_report(
    report_date: date | None = Query(default=None),
    send_whatsapp: bool = Query(default=True),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    settings = get_settings()
    authorize_report_trigger(settings, authorization)

    target_date = report_date or now_in_timezone(settings.timezone).date()
    try:
        report_text = get_report_service().generate_daily_report(
            target_date,
            send_whatsapp=send_whatsapp,
        )
    except SheetsUnavailableError:
        raise HTTPException(status_code=503, detail=SHEETS_UNAVAILABLE_MESSAGE) from None
    except Exception:
        logger.exception("Failed to generate daily report")
        raise HTTPException(
            status_code=503,
            detail="I could not generate the daily report right now. Please check the Google Sheets connection.",
        ) from None
    return {
        "date": target_date.isoformat(),
        "sent_whatsapp": send_whatsapp,
        "report": report_text,
    }


@dataclass(frozen=True)
class IncomingInput:
    text: str
    is_voice: bool = False
    original_text: str = ""


@dataclass(frozen=True)
class WhatsAppProcessResult:
    reply: str
    media_url: str | None = None
    message_type: str = "text"
    success: bool = False
    error_reason: str = ""
    command_handler: str = "unknown"


async def process_whatsapp_form_values(form_values: dict[str, Any]) -> WhatsAppProcessResult:
    body = str(form_values.get("Body") or "").strip()
    from_number = str(form_values.get("From") or "").strip()
    message_sid = str(form_values.get("MessageSid") or "").strip()
    command_handler = classify_command_handler(body) if body else "voice_or_media"
    message_type = "text"
    media_url: str | None = None

    try:
        if message_sid and message_sid in processed_message_sids:
            return WhatsAppProcessResult(
                reply="Already processed.",
                message_type=message_type,
                success=True,
                command_handler="duplicate_message",
            )

        pending = pending_voice_for_sender(from_number)
        if body and pending and body.lower() == "yes":
            command_handler = "voice_confirmation_yes"
            incoming = IncomingInput(text=pending, is_voice=False)
            clear_pending_voice(from_number)
            reply = "Confirmed. Records updated.\n\n" + process_intake_text_for_sender(incoming.text, from_number)
        elif body:
            invoice_review_reply = process_pending_invoice_review_message(from_number, body)
            if invoice_review_reply:
                command_handler = "invoice_review"
                reply = invoice_review_reply
            else:
                if pending:
                    command_handler = "voice_correction_text"
                    clear_pending_voice(from_number)
                incoming = IncomingInput(text=body, is_voice=False)
                reply = process_intake_text_for_sender(incoming.text, from_number)
        else:
            whatsapp = get_whatsapp_client()
            incoming = await incoming_text_from_form(form_values, whatsapp, get_transcription_service())
            message_type = "voice" if incoming.is_voice else "text"
            if incoming.is_voice and not voice_transcript_is_clear(incoming.text):
                command_handler = "voice_note_confirmation_required"
                reply = voice_needs_correction_reply(incoming.original_text or incoming.text)
            else:
                command_handler = "voice_note_processed" if incoming.is_voice else classify_command_handler(incoming.text)
                reply = process_intake_text_for_sender(incoming.text, from_number)
                if incoming.is_voice:
                    reply = voice_reply(incoming.original_text or incoming.text, incoming.text, reply)


        media_url = media_url_from_reply(reply)
        if media_url:
            reply = reply_for_pdf_media(reply)
        if message_sid:
            processed_message_sids.add(message_sid)
        return WhatsAppProcessResult(
            reply=reply,
            media_url=media_url,
            message_type=message_type,
            success=True,
            command_handler=command_handler,
        )
    except UnsupportedInputError as exc:
        return WhatsAppProcessResult(
            reply=str(exc),
            message_type=message_type,
            success=False,
            error_reason=str(exc),
            command_handler=command_handler,
        )
    except Exception as exc:
        logger.exception("Failed to process WhatsApp form values")
        traceback.print_exc()
        return WhatsAppProcessResult(
            reply="Sorry, I could not understand that. Please send it like: Panadol sold 2.",
            message_type=message_type,
            success=False,
            error_reason=str(exc),
            command_handler=command_handler,
        )


def classify_command_handler(body: str) -> str:
    text = str(body or "").strip().lower()
    if not text:
        return "empty"
    if text in {"start", "help", "menu", "commands", "guide", "tutorial", "how do i use this", "what can you do"}:
        return "help_start"
    if text in {"hello", "hi", "hey", "habari", "morning", "good morning", "mambo", "sasa"}:
        return "greeting"
    if text == "share":
        return "share"
    if "report" in text or "daily pdf" in text or "download today" in text:
        return "report"
    if "profit" in text:
        return "profit"
    if "stock" in text:
        return "stock_or_no_stock"
    if (
        text.startswith("+")
        or "restock" in text
        or text.startswith(("add ", "received ", "stock ", "bonus ", "free ", "extra ", "bought "))
    ):
        return "restock"
    if text.startswith(("later ", "late ", "missed ")) or " missed " in text:
        return "late_sale"
    if "sold" in text or any(character.isdigit() for character in text):
        return "sale_or_batch"
    return "natural_or_ai_parser"


def logged_xml_message_response(message: str, media_url: str | None = None) -> str:
    clean_message = str(message or "")
    preview = clean_message.replace("\r", " ").replace("\n", " ")[:200]
    xml = xml_message_response(clean_message, media_url=media_url)
    xml_preview = xml.replace("\r", " ").replace("\n", " ")[:300]
    print(f"WHATSAPP_REPLY_LENGTH={len(clean_message)}", flush=True)
    print(f"WHATSAPP_REPLY_PREVIEW={preview}", flush=True)
    print(f"WHATSAPP_REPLY_XML_PREVIEW={xml_preview}", flush=True)
    print(f"WHATSAPP_REPLY_CONTENT_TYPE={XML_CONTENT_TYPE}", flush=True)
    return xml


def xml_response(message: str, media_url: str | None = None) -> Response:
    return Response(
        content=logged_xml_message_response(message, media_url=media_url),
        media_type=XML_CONTENT_TYPE,
        headers={"Content-Type": XML_CONTENT_TYPE},
    )


async def incoming_text_from_form(
    form_values: dict[str, Any],
    whatsapp: WhatsAppClient,
    transcription_service: TranscriptionService,
) -> IncomingInput:
    body = str(form_values.get("Body") or "").strip()
    media_count = int(str(form_values.get("NumMedia") or "0") or 0)

    if media_count == 0:
        if body:
            return IncomingInput(text=body, is_voice=False)
        raise UnsupportedInputError("Please send a short text message or voice note.")

    for index in range(media_count):
        content_type = str(form_values.get(f"MediaContentType{index}") or "").lower()
        media_url = str(form_values.get(f"MediaUrl{index}") or "").strip()
        if media_url and content_type.startswith("audio/"):
            if not transcription_service.is_available:
                raise UnsupportedInputError(
                    "ðŸŽ™ï¸ Voice received, but voice is not enabled yet.\nSend text like: Panadol 2"
                )
            try:
                audio_bytes = await whatsapp.download_media(media_url)
                log_ai_route_decision(
                    text=str(form_values.get("MessageSid") or media_url or "voice"),
                    route="audio/transcriptions",
                    used_ai=True,
                    reason="voice_transcription",
                    job_id=str(form_values.get("MessageSid") or ""),
                )
                transcript = clean_voice_transcript_for_intake(
                    transcription_service.transcribe_audio(audio_bytes, content_type),
                    medicine_names=voice_medicine_names_from_inventory(),
                )
            except TranscriptionUnavailableError as exc:
                raise UnsupportedInputError(voice_transcription_failed_message()) from exc
            except Exception as exc:
                raise UnsupportedInputError(voice_transcription_failed_message()) from exc
            if transcript:
                return IncomingInput(
                    text=normalize_spoken_command_text(transcript),
                    is_voice=True,
                    original_text=transcript,
                )
            raise UnsupportedInputError(voice_transcription_failed_message())

    if body:
        return IncomingInput(text=body, is_voice=False)
    raise UnsupportedInputError("Please send WhatsApp text or a voice note only.")


def voice_reply(original_transcript: str, interpreted_command: str, processed_reply: str) -> str:
    lower_reply = processed_reply.lower()
    failure_markers = [
        "could not understand",
        "could not be understood",
        "not fully sure",
        "please send it like",
        "didn\u2019t understand",
        "didn't understand",
        "was not found in inventory",
        "did you mean",
        "which medicine",
    ]
    if any(marker in lower_reply for marker in failure_markers) or ("errors:" in lower_reply and "- none" not in lower_reply):
        return voice_needs_correction_reply(original_transcript)
    clean_reply = processed_reply
    if clean_reply.startswith("\u2705 Batch processed\n\n"):
        clean_reply = clean_reply.replace("\u2705 Batch processed\n\n", "", 1)
    clean_reply = clean_reply.replace("\n\nErrors:\n- None", "")
    return "\n".join(
        [
            f"\U0001F399 Heard: {original_transcript}",
            f"Command: {interpreted_command}",
            "",
            clean_reply,
        ]
    )

def unclear_voice_message() -> str:
    return "⚠️ I could not clearly understand the voice note.\nPlease type it like:\nPanadol 2\nAmoxil 1"


def voice_needs_correction_reply(transcript: str) -> str:
    heard = transcript.strip() or "nothing clear"
    return (
        f"\U0001F399 Heard: {heard}\n"
        "I could not safely record that.\n"
        "Try: Panadol 2 cash"
    )

def voice_transcription_failed_message() -> str:
    return "🎙 I heard the voice but could not read it clearly. Try saying: \"Panadol two\" or type: Panadol 2."

def voice_transcript_is_clear(transcript: str) -> bool:
    from app.intake import parse_operating_commands

    commands = parse_operating_commands(transcript)
    return bool(commands and all(command.kind != "error" for command in commands))


def store_pending_voice(sender: str, transcript: str) -> None:
    pending_voice_confirmations[mask_phone(sender)] = (transcript, time.time() + PENDING_VOICE_TTL_SECONDS)


def pending_voice_for_sender(sender: str) -> str | None:
    key = mask_phone(sender)
    pending = pending_voice_confirmations.get(key)
    if not pending:
        return None
    transcript, expires_at = pending
    if time.time() > expires_at:
        pending_voice_confirmations.pop(key, None)
        return None
    return transcript


def clear_pending_voice(sender: str) -> None:
    pending_voice_confirmations.pop(mask_phone(sender), None)


def pending_voice_reply(transcript: str) -> str:
    return "\n".join(
        [
            "ðŸŽ™ï¸ Voice note received",
            "",
            "Iâ€™m not fully sure I understood.",
            "",
            "I heard:",
            f"â€œ{transcript}â€",
            "",
            "Please confirm by typing:",
            "yes",
            "",
            "Or correct it like:",
            "Panadol 2",
            "Amoxil 1",
        ]
    )


def media_url_from_reply(reply: str) -> str | None:
    import re

    if "attached below" not in reply.lower():
        return None
    match = re.search(r"https?://\S+?\.pdf", reply)
    return match.group(0) if match else None


def reply_for_pdf_media(reply: str) -> str:
    cleaned_lines: list[str] = []
    for line in str(reply or "").splitlines():
        lowered = line.lower()
        if ".pdf" in lowered and "http" in lowered:
            continue
        if "pdf report" in lowered or "attached below" in lowered or "tap here to download" in lowered:
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines).strip()
    return f"{cleaned}\n\n📎 PDF report attached below."
    import re

    without_link = re.sub(r"\n*ðŸ“„ PDF report:\nTap here to download:\s*https?://\S+?\.pdf", "", reply).strip()
    without_link = re.sub(r"\nhttps?://\S+?\.pdf", "", without_link).strip()
    if "ðŸ“Ž PDF report attached below." in without_link:
        return without_link
    return f"{without_link}\n\nðŸ“Ž PDF report attached below."


def authorize_report_trigger(settings: Settings, authorization: str | None) -> None:
    if not settings.report_trigger_token:
        return
    expected = f"Bearer {settings.report_trigger_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized report trigger")


def external_request_url(request: Request, settings: Settings) -> str:
    if not settings.public_base_url:
        return str(request.url)

    base = settings.public_base_url.rstrip("/")
    path = request.url.path
    query = request.url.query
    return f"{base}{path}{'?' + query if query else ''}"


def record_openai_error(feature: str, exc: Exception) -> None:
    message = sanitize_error_message(exc)
    last_openai_error.update(
        {
            "feature": feature,
            "message": message,
            "quota_missing": is_openai_quota_error(exc),
            "timestamp": now_in_timezone(get_settings().timezone).isoformat(timespec="seconds"),
        }
    )
    logger.warning(
        "OPENAI_MEDIA_ERROR feature=%s quota_missing=%s error=%s",
        feature,
        last_openai_error["quota_missing"],
        message,
    )


def clear_last_openai_error(feature: str) -> None:
    if last_openai_error.get("feature") == feature:
        last_openai_error.update({"feature": "", "message": "", "quota_missing": False, "timestamp": ""})


def is_openai_quota_error(exc: Exception) -> bool:
    text = sanitize_error_message(exc).lower()
    status_code = str(getattr(exc, "status_code", "") or getattr(getattr(exc, "response", None), "status_code", ""))
    return (
        "insufficient_quota" in text
        or ("quota" in text and "429" in text)
        or (status_code == "429" and "quota" in text)
    )


def sanitize_error_message(exc: Exception) -> str:
    text = str(exc or "").replace("\n", " ").replace("\r", " ").strip()
    if not text:
        text = type(exc).__name__
    return text[:500]


def save_photo_metadata(
    sender: str,
    message_id: str,
    media_mime_type: str,
    byte_count: int,
) -> dict[str, Any]:
    metadata_dir = PROJECT_ROOT / "data"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / "photo_intake_log.jsonl"
    row = {
        "timestamp": now_in_timezone(get_settings().timezone).isoformat(timespec="seconds"),
        "sender": mask_phone(sender),
        "message_id": message_id,
        "media_mime_type": media_mime_type,
        "byte_count": byte_count,
        "source": "whatsapp_web_bridge",
        "metadata_path": str(metadata_path.name),
    }
    with metadata_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    return row


def append_offline_sync_log(entry: dict[str, Any], status: str, reply: str, error: str) -> None:
    try:
        log_dir = PROJECT_ROOT / "data"
        log_dir.mkdir(parents=True, exist_ok=True)
        row = {
            "timestamp": now_in_timezone(get_settings().timezone).isoformat(timespec="seconds"),
            "id": str(entry.get("id") or entry.get("action_id") or ""),
            "entry_timestamp": str(entry.get("timestamp") or ""),
            "pharmacy_id": str(entry.get("pharmacy_id") or ""),
            "command_text": str(entry.get("command_text") or ""),
            "raw_text": str(entry.get("raw_text") or ""),
            "action": str(entry.get("action") or ""),
            "drug_name": str(entry.get("drug_name") or ""),
            "type": str(entry.get("type") or entry.get("action_type") or ""),
            "sync_status": status,
            "retry_count": entry.get("retry_count", 0),
            "last_error": error,
            "reply": reply[:500],
            "source": "offline_pwa",
        }
        with (log_dir / "offline_sync_log.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    except Exception:
        logger.debug("Offline sync log write skipped", exc_info=True)


def is_offline_sync_failure_reply(reply: str) -> bool:
    normalized = str(reply or "").lower()
    return (
        "i didn" in normalized and "understand" in normalized
        or "could not save" in normalized
        or "google sheets is not configured" in normalized
    )


def log_webhook_request(sender: str, message_type: str, success: bool, error_reason: str = "") -> None:
    try:
        store = get_sheet_store()
        append_request_log = getattr(store, "append_request_log", None)
        if append_request_log is None:
            return
        append_request_log(
            sender=mask_phone(sender),
            message_type=message_type,
            success=success,
            error_reason=error_reason,
        )
    except Exception:
        logger.debug("Request log write skipped", exc_info=True)


def mask_phone(value: str) -> str:
    digits = phone_digits(value)
    if digits:
        if len(digits) <= 6:
            return f"****{digits[-2:]}"
        return f"{digits[:4]}******{digits[-2:]}"
    text = str(value or "").strip()
    if len(text) <= 4:
        return "hidden"
    return f"***{text[-4:]}"


@lru_cache
def get_ai_service() -> AIService:
    return AIService(get_settings())


@lru_cache
def get_transcription_service() -> TranscriptionService:
    return TranscriptionService(get_settings())


@lru_cache
def get_sheet_store():
    settings = get_settings()
    if should_use_demo_store(settings):
        logger.warning("Using DEMO_MODE local store. Google Sheets writes are disabled.")
        return DemoPharmacyStore(settings)
    return GoogleSheetsStore(settings)


@lru_cache
def get_whatsapp_client() -> WhatsAppClient:
    return WhatsAppClient(get_settings())


@lru_cache
def get_intake_service() -> IntakeService:
    settings = get_settings()
    return IntakeService(
        get_ai_service(),
        get_sheet_store(),
        timezone=settings.timezone,
        pharmacy_name=settings.pharmacy_name,
        app_base_url=report_public_base_url(settings),
        whatsapp_number=settings.whatsapp_number,
    )


@lru_cache
def get_report_service() -> ReportService:
    settings = get_settings()
    return ReportService(
        store=get_sheet_store(),
        whatsapp=get_whatsapp_client(),
        recommender=get_ai_service(),
        pharmacy_name=settings.pharmacy_name,
        timezone=settings.timezone,
    )


class UnsupportedInputError(Exception):
    pass


def run_local_server() -> None:
    import uvicorn

    port = int(os.getenv("PORT", "5000"))
    try:
        uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
    except KeyboardInterrupt:
        print("PharMareen stopped.", flush=True)
    except BaseException as exc:
        print("PharMareen could not start.", flush=True)
        print(f"Error: {exc}", flush=True)
        try:
            input("Press any key to close.")
        except Exception:
            print("Press any key to close.", flush=True)
        raise


if __name__ == "__main__":
    run_local_server()
