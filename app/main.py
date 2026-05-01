from __future__ import annotations

import logging
import os
import sys
import time
import traceback
from html import escape
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai import AIService
from app.config import Settings, get_settings
from app.intake import IntakeService
from app.pdf_reports import generate_daily_report_pdf, reports_pdf_dir
from app.reports import LowStockWarning, ReportMetrics, ReportService
from app.sheets import GoogleSheetsStore, SHEETS_UNAVAILABLE_MESSAGE, SheetsUnavailableError
from app.transcription import TranscriptionService, TranscriptionUnavailableError
from app.utils import now_in_timezone
from app.whatsapp import WhatsAppClient, twiml_response


logger = logging.getLogger(__name__)
processed_message_sids: set[str] = set()
pending_voice_confirmations: dict[str, tuple[str, float]] = {}
PENDING_VOICE_TTL_SECONDS = 600
startup_status_printed = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    print_startup_console_status()
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


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status", response_class=HTMLResponse)
def startup_status_page() -> str:
    settings = get_settings()
    store = get_sheet_store()
    base_url = effective_app_base_url(settings)
    webhook_url = webhook_url_for(settings)
    twilio_ready = twilio_credentials_found(settings)
    sheets_ready = bool(store.is_available)
    base_is_local = is_local_base_url(base_url)
    base_is_placeholder = is_placeholder_base_url(base_url)
    production_ready = base_url.startswith("https://") and not base_is_local and not base_is_placeholder
    warning = ""
    if base_is_local:
        warning = """
        <section class="warning">
          <strong>WhatsApp will NOT reply while APP_BASE_URL is localhost.</strong><br>
          Deploy to Render/Railway/Fly.io or use a public HTTPS tunnel, then put the webhook URL in Twilio.
        </section>
        """
    elif base_is_placeholder:
        warning = """
        <section class="warning">
          <strong>APP_BASE_URL is still a placeholder.</strong><br>
          Replace it with your real public HTTPS domain before connecting Twilio.
        </section>
        """
    elif production_ready:
        warning = """
        <section class="ready">
          <strong>Production URL looks ready.</strong><br>
          Put the webhook URL below into Twilio and send "start" on WhatsApp.
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
        <p>Use this page to see what is working before testing WhatsApp.</p>
        {warning}
        <section class="card">
          <div class="row"><span>App running</span><span class="ok">yes</span></div>
          <div class="row"><span>Google Sheets connected</span><span class="{status_class(sheets_ready)}">{yes_no(sheets_ready)}</span></div>
          <div class="row"><span>Twilio credentials found</span><span class="{status_class(twilio_ready)}">{yes_no(twilio_ready)}</span></div>
          <div class="row"><span>Production HTTPS URL ready</span><span class="{status_class(production_ready)}">{yes_no(production_ready)}</span></div>
          <div class="row"><span>APP_BASE_URL</span><span><code>{escape(base_url)}</code></span></div>
          <div class="row"><span>Webhook URL for Twilio</span><span><code>{escape(webhook_url)}</code></span></div>
        </section>
        <section class="card">
          <p><strong>Local app:</strong> <a href="http://localhost:5000">http://localhost:5000</a></p>
          <p><strong>Health check:</strong> <a href="http://localhost:5000/health">http://localhost:5000/health</a></p>
          <p><strong>WhatsApp:</strong> needs a public HTTPS production URL before Twilio can reach this app.</p>
        </section>
      </main>
    </body>
    </html>
    """


@app.get("/landing", response_class=HTMLResponse)
def landing_page() -> str:
    settings = get_settings()
    whatsapp_number = settings.twilio_whatsapp_from.replace("whatsapp:", "") or "Your WhatsApp number"
    click_link = whatsapp_click_link(settings.twilio_whatsapp_from)
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
    report_path = reports_pdf_dir() / safe_name
    if not report_path.exists() or report_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Report not found.")
    return FileResponse(report_path, media_type="application/pdf", filename=safe_name)


def whatsapp_click_link(value: str) -> str:
    digits = "".join(character for character in str(value or "").replace("whatsapp:", "") if character.isdigit())
    return f"https://wa.me/{digits}?text=start" if digits else "https://wa.me/?text=start"


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def status_class(value: bool) -> str:
    return "ok" if value else "bad"


def effective_app_base_url(settings: Settings) -> str:
    return (settings.public_base_url or "http://localhost:5000").rstrip("/")


def webhook_url_for(settings: Settings) -> str:
    return f"{effective_app_base_url(settings)}/webhook/whatsapp"


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


def twilio_credentials_found(settings: Settings) -> bool:
    return bool(
        settings.twilio_account_sid.strip()
        and settings.twilio_auth_token.strip()
        and settings.twilio_whatsapp_from.strip()
    )


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
    if not settings.twilio_account_sid.strip():
        missing.append("TWILIO_ACCOUNT_SID")
    if not settings.twilio_auth_token.strip():
        missing.append("TWILIO_AUTH_TOKEN")
    if not settings.twilio_whatsapp_from.strip():
        missing.append("TWILIO_WHATSAPP_NUMBER")
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
    ]
    base_url = effective_app_base_url(settings)
    if is_local_base_url(base_url):
        lines.extend(
            [
                "",
                "WARNING: WhatsApp will not receive messages from Twilio because localhost is not public.",
                "Use production hosting or a temporary public tunnel.",
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
        "twilio_account_sid_present": bool(settings.twilio_account_sid.strip()),
        "twilio_auth_token_present": bool(settings.twilio_auth_token.strip()),
        "twilio_whatsapp_number_present": bool(settings.twilio_whatsapp_from.strip()),
        "owner_whatsapp_to_present": bool(settings.owner_whatsapp_to.strip()),
        "google_sheet_id_present": bool(settings.google_sheets_spreadsheet_id.strip()),
        "google_credentials_present": google_credentials_present(settings),
        "openai_api_key_present": bool(settings.openai_api_key.strip()),
    }


@app.post("/debug/whatsapp-test")
async def debug_whatsapp_test() -> JSONResponse:
    settings = get_settings()
    form_values = {
        "Body": "start",
        "From": "whatsapp:+254700000000",
        "To": settings.twilio_whatsapp_from or "whatsapp:+14155238886",
        "MessageSid": f"SMDEBUG{int(time.time() * 1000)}",
        "NumMedia": "0",
    }
    try:
        result = await process_twilio_form_values(form_values)
        response_body = twiml_response(result.reply, media_url=result.media_url)
        return JSONResponse(
            {
                "status": "ok" if result.success else "error",
                "response_type": "twiml_xml",
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
        public_pdf_url = f"{effective_app_base_url(settings)}/reports/download/{pdf_path.name}"
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


@app.post("/webhook/whatsapp")
@app.post("/webhooks/twilio/whatsapp")
async def twilio_whatsapp_webhook(request: Request) -> Response:
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
    print("TWILIO WEBHOOK HIT", flush=True)
    print(f"BODY={body}", flush=True)
    print(f"FROM={from_number}", flush=True)
    print(f"TO={to_number}", flush=True)
    print(f"MESSAGESID={message_sid}", flush=True)
    print(f"COMMAND_HANDLER={classify_command_handler(body) if body else 'voice_or_media'}", flush=True)

    media_url: str | None = None
    try:
        if message_sid and message_sid in processed_message_sids:
            return Response(content=twiml_response("Already processed."), media_type="application/xml")

        pending = pending_voice_for_sender(from_number)
        if body and pending and body.lower() == "yes":
            incoming = IncomingInput(text=pending, is_voice=False)
            clear_pending_voice(from_number)
            reply = "✅ Confirmed. Records updated.\n\n" + get_intake_service().process_text(incoming.text)
        elif body:
            if pending:
                clear_pending_voice(from_number)
            incoming = IncomingInput(text=body, is_voice=False)
            reply = get_intake_service().process_text(incoming.text)
        else:
            whatsapp = get_whatsapp_client()
            incoming = await incoming_text_from_form(form_values, whatsapp, get_transcription_service())
            if incoming.is_voice and not voice_transcript_is_clear(incoming.text):
                store_pending_voice(from_number, incoming.text)
                reply = pending_voice_reply(incoming.text)
            else:
                reply = get_intake_service().process_text(incoming.text)
                if incoming.is_voice:
                    reply = voice_reply(incoming.text, reply)
        message_type = "voice" if not body and "incoming" in locals() and incoming.is_voice else "text"
        media_url = media_url_from_reply(reply)
        if media_url:
            reply = reply_for_pdf_media(reply)
        success = True
        if message_sid:
            processed_message_sids.add(message_sid)
    except UnsupportedInputError as exc:
        reply = str(exc)
        error_reason = reply
    except Exception:
        logger.exception("Failed to process WhatsApp webhook")
        traceback.print_exc()
        reply = "Sorry, I could not understand that. Please send it like: Panadol sold 2."
        error_reason = "Unhandled processing error"
    finally:
        log_webhook_request(from_number, message_type, success, error_reason)

    return Response(content=twiml_response(reply, media_url=media_url), media_type="application/xml")


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


@dataclass(frozen=True)
class WhatsAppProcessResult:
    reply: str
    media_url: str | None = None
    message_type: str = "text"
    success: bool = False
    error_reason: str = ""
    command_handler: str = "unknown"


async def process_twilio_form_values(form_values: dict[str, Any]) -> WhatsAppProcessResult:
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
            reply = "✅ Confirmed. Records updated.\n\n" + get_intake_service().process_text(incoming.text)
        elif body:
            if pending:
                command_handler = "voice_correction_text"
                clear_pending_voice(from_number)
            incoming = IncomingInput(text=body, is_voice=False)
            reply = get_intake_service().process_text(incoming.text)
        else:
            whatsapp = get_whatsapp_client()
            incoming = await incoming_text_from_form(form_values, whatsapp, get_transcription_service())
            message_type = "voice" if incoming.is_voice else "text"
            if incoming.is_voice and not voice_transcript_is_clear(incoming.text):
                command_handler = "voice_note_confirmation_required"
                store_pending_voice(from_number, incoming.text)
                reply = pending_voice_reply(incoming.text)
            else:
                command_handler = "voice_note_processed" if incoming.is_voice else classify_command_handler(incoming.text)
                reply = get_intake_service().process_text(incoming.text)
                if incoming.is_voice:
                    reply = voice_reply(incoming.text, reply)

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
    if text in {"start", "help"}:
        return "help_start"
    if text == "share":
        return "share"
    if "report" in text or "daily pdf" in text or "download today" in text:
        return "report"
    if "profit" in text:
        return "profit"
    if "stock" in text:
        return "stock_or_no_stock"
    if text.startswith("+") or "restock" in text or text.startswith("add "):
        return "restock"
    if text.startswith("later ") or text.startswith("missed ") or " missed " in text:
        return "late_sale"
    if "sold" in text or any(character.isdigit() for character in text):
        return "sale_or_batch"
    return "natural_or_ai_parser"


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
                    "Voice not enabled. Send text like: Panadol 2"
                )
            audio_bytes = await whatsapp.download_media(media_url)
            try:
                transcript = transcription_service.transcribe_audio(audio_bytes, content_type)
            except TranscriptionUnavailableError as exc:
                raise UnsupportedInputError(str(exc)) from exc
            if transcript:
                return IncomingInput(text=transcript, is_voice=True)
            raise UnsupportedInputError(unclear_voice_message())

    if body:
        return IncomingInput(text=body, is_voice=False)
    raise UnsupportedInputError("Please send WhatsApp text or a voice note only.")


def voice_reply(transcript: str, processed_reply: str) -> str:
    if "could not understand" in processed_reply.lower() or "please send it like" in processed_reply.lower():
        return unclear_voice_message()
    clean_reply = processed_reply
    if clean_reply.startswith("✅ Batch processed\n\n"):
        clean_reply = clean_reply.replace("✅ Batch processed\n\n", "", 1)
    clean_reply = clean_reply.replace("\n\nErrors:\n- None", "")
    return "\n".join(
        [
            "🎙️ Voice note received",
            "",
            "I understood:",
            clean_reply,
            "",
            "✅ Records updated.",
        ]
    )


def unclear_voice_message() -> str:
    return "⚠️ I could not clearly understand the voice note.\nPlease type it like:\nPanadol 2\nAmoxil 1"


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
            "🎙️ Voice note received",
            "",
            "I’m not fully sure I understood.",
            "",
            "I heard:",
            f"“{transcript}”",
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
    import re

    without_link = re.sub(r"\n*📄 PDF report:\nTap here to download:\s*https?://\S+?\.pdf", "", reply).strip()
    without_link = re.sub(r"\nhttps?://\S+?\.pdf", "", without_link).strip()
    if "📎 PDF report attached below." in without_link:
        return without_link
    return f"{without_link}\n\n📎 PDF report attached below."


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
    text = str(value or "").replace("whatsapp:", "").strip()
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
def get_sheet_store() -> GoogleSheetsStore:
    return GoogleSheetsStore(get_settings())


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
        app_base_url=settings.public_base_url,
        whatsapp_number=settings.twilio_whatsapp_from,
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
