# Pharmacy Intelligence Assistant

A simple MVP for pharmacy owners who only want to send WhatsApp text messages or WhatsApp voice notes.

The app receives a WhatsApp update, handles known pharmacy flows locally first, logs the event in Google Sheets, updates stock after sales, and generates daily WhatsApp reports for business decisions.

Default system display name: `MS2.0`.

## Baileys WhatsApp Bridge Mode

Baileys is the active WhatsApp bridge for the current production runtime.

Run the backend:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 5000
```

Set these environment variables:

```text
WHATSAPP_BRIDGE_ENABLED=true
PHARMAREEN_BACKEND_URL=http://localhost:5000
OWNER_WHATSAPP_TO=whatsapp:+254700000000
OPENAI_API_KEY=
GOOGLE_SHEET_ID=
GOOGLE_SHEETS_CREDENTIALS=
PHARMACY_REGISTRY_AUTH_ENABLED=true
```

Baileys bridge endpoint URL:

```text
https://YOUR-DOMAIN/webhooks/baileys/whatsapp
```

Legacy Meta/Twilio environment variables may remain for compatibility, but they are not the active live messaging bridge.

## Pharmacy Registry

Production pharmacy numbers live in the Google Sheet `Pharmacies` registry, not permanently in Replit Secrets. `ALLOWED_WHATSAPP_NUMBERS` remains available only as a temporary development override for controlled testing. Registered active numbers are served normally; unregistered direct numbers can only start onboarding or receive the setup prompt.

## AI Safety Rules

Low-risk messages save automatically:

```text
Panadol sold 2
Panadol stock
report today
```

High-risk messages ask before saving:

```text
Panadol bad
Return Panadol
Panadol restocked 100 exp Jan 2027
```

Reply `YES` to confirm, `EDIT` to correct, or `CANCEL` to discard.

## Offline App

Open:

```text
/offline_app/index.html
```

The offline app saves sales/restocks locally when internet is poor. When the connection returns, it auto-syncs to:

```text
POST /sync/offline-actions
```

It retries every 30 seconds, tracks failed items, and keeps a visible status banner:

- Offline - saving safely
- Syncing...
- Synced
- Some items not synced yet

Images and voice files can be queued offline. They are uploaded and processed only after internet returns.

## Easiest Windows Setup

For beginner-friendly Windows setup, open:

```text
EASY_SETUP.md
```

Or double-click:

```text
start_here.bat
```

Common one-click scripts:

- `setup.bat`: create virtual environment, install requirements, and create `.env` if missing.
- `run.bat`: start the app at `http://localhost:8000`.
- `seed_prices.bat`: add sample testing prices to `Master_Stock`.
- `daily_report.bat`: generate today's report from the local app.
- `ngrok_start.bat`: start ngrok for local WhatsApp Web bridge testing.
- `test.bat`: run tests.

For production without ngrok, see `README_PRODUCTION.md`.

## FAST TEST

Use this when you want to prove the Windows installer build works.

1. Double-click `build_install_prove.bat`.
2. Install `dist\ZillaPharmacySetup.exe`.
3. Double-click `prove_app_works.bat`.
4. If `APP WORKING` appears, the app is running.

Installed app path:

```text
C:\Program Files (x86)\ZillaPharmacy\ZillaPharmacyApp.exe
```

If Google Sheets is not configured yet, the app still starts. `/health` should return:

```json
{"status":"ok","service":"MS2.0","version":"day-2"}
```

## What The System Does

- Accepts WhatsApp text messages.
- Accepts WhatsApp voice notes.
- Transcribes voice notes to text.
- Parses one or many pharmacy events from the text.
- Logs sales, missed demand, and lost opportunities.
- Looks up sale prices from `Master_Stock`.
- Reduces `Current Stock` after sales.
- Warns when stock reaches `Reorder Level`.
- Saves daily reports in `Daily_Reports`.
- Lets the owner fetch saved reports by WhatsApp command.

The owner never enters prices in WhatsApp and never uses forms.

## How The Owner Uses It

The owner sends short natural messages:

```text
Panadol sold 2
sold 2 panadol
Insulin no stock
3 people asked vitamin c
customer asked inhaler but left
cough syrup sold one
amoxyl asked not available
malaria tablets too expensive
paracetamol sold 2 packets
Panadol sold 2, insulin no stock, cough syrup sold 1
```

The owner can also send a voice note saying the same thing. Voice notes are only transcribed to text, then processed by the same logic as normal WhatsApp messages.

## Actions

- `Sold`: sale happened.
- `Out of Stock`: customer asked, but the pharmacy did not have it.
- `Not Sold`: customer asked, but did not buy because they left, price was too high, or another non-stock reason.

If quantity is missing, the app uses `1`.

## Google Sheets Setup

Create one Google Sheet and share it with your Google service account email.

The app creates or repairs these worksheets on startup.

### Master_Stock

| Drug Name | Selling Price | Cost Price | Current Stock | Reorder Level |
| --- | --- | --- | --- | --- |
| Panadol | 200 | 120 | 20 | 5 |

Only `Drug Name` and `Selling Price` are required for sales. `Current Stock` and `Reorder Level` are optional, but needed for stock updates and low-stock warnings.

### Daily_Log

| Date | Time | Drug Name | Action | Quantity | Price | Total Value | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |

For `Sold`, price and total value are filled from `Master_Stock`.

For `Out of Stock` and `Not Sold`, price and total value stay blank, even if the drug is not in `Master_Stock`.

### Daily_Reports

| Date | Total Sales | Total Items Sold | Most Requested Drugs | Most Sold Drugs | Missed Sales | Low Stock Warnings | AI Recommendation Summary | Full Report Text |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

`Full Report Text` is what the app sends back when the owner asks for an old report.

## Seeding Test Prices

You can fill `Master_Stock` with sample testing prices:

```powershell
python scripts/seed_test_prices.py
```

This adds missing sample drugs only. It does not replace existing owner-entered prices.

To overwrite the sample drugs during testing:

```powershell
python scripts/seed_test_prices.py --overwrite
```

Important:

- These prices are only for testing.
- They are not official or final pharmacy prices.
- The pharmacy owner should adjust prices in `Master_Stock` before real use.
- Use `--overwrite` only when you want to reset the sample testing rows.

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
PHARMACY_NAME=Zilla Pharmacy
TIMEZONE=Africa/Nairobi
PUBLIC_BASE_URL=https://your-public-url.example.com
WHATSAPP_PROVIDER=whatsapp_web
REPORT_TRIGGER_TOKEN=change-this-report-token

OPENAI_API_KEY=sk-your-openai-key
OPENAI_PARSE_MODEL=gpt-5
OPENAI_TRANSCRIPTION_MODEL=whisper-1

GOOGLE_SHEETS_SPREADSHEET_ID=your-google-sheet-id
GOOGLE_SERVICE_ACCOUNT_JSON=./service-account.json

WHATSAPP_NUMBER=2547XXXXXXXXxxx
PHARMAREEN_BACKEND_URL=http://localhost:5000
WHATSAPP_WEB_SESSION_PATH=.wwebjs_auth
OWNER_WHATSAPP_TO=whatsapp:+254700000000
```

`GOOGLE_SERVICE_ACCOUNT_JSON` can be a path to a service account JSON file or the raw JSON string.

If `PHARMACY_NAME` is missing, the app uses `Zilla Pharmacy`.

## Run Locally

Requires Python 3.10 or newer.

```powershell
cd "C:\Users\Pal\Documents\New project\pharmacy-intelligence-assistant"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Expose local server for WhatsApp Web bridge:

```powershell
ngrok http 8000
```

Set `PUBLIC_BASE_URL` to the ngrok HTTPS URL.

## Connect WhatsApp Web bridge

In WhatsApp Web bridge sandbox or sender settings, set the incoming message bridge endpoint to:

```text
POST https://your-public-url/bridge/whatsapp-web
```

Keep `WHATSAPP_PROVIDER=whatsapp_web` in production.

## Voice Notes

Voice note flow:

1. Owner sends WhatsApp voice note.
2. WhatsApp Web bridge sends the media URL to the bridge endpoint.
3. App downloads the audio from WhatsApp Web bridge.
4. OpenAI transcribes the audio to text.
5. The same parser handles the transcript.
6. One or multiple entries are logged.
7. The owner receives the same summary reply as text messages.

## Daily Report

Manual trigger:

```powershell
curl -X POST "https://your-public-url/reports/daily?send_whatsapp=true" -H "Authorization: Bearer change-this-report-token"
```

Trigger for a specific date:

```powershell
curl -X POST "https://your-public-url/reports/daily?report_date=2026-04-27&send_whatsapp=true" -H "Authorization: Bearer change-this-report-token"
```

Cron example:

```cron
0 21 * * * curl -X POST "https://your-public-url/reports/daily?send_whatsapp=true" -H "Authorization: Bearer change-this-report-token"
```

The report includes:

- `Zilla Pharmacy` at the top
- Sales summary
- Most requested drugs
- Most sold drugs
- Missed demand / out of stock
- Lost opportunities
- Low stock warnings
- AI recommendations

## Fetch Saved Reports By WhatsApp

The owner can send:

```text
report today
report yesterday
report 2026-04-27
show report 2026-04-27
```

If the report exists in `Daily_Reports`, the app sends the saved `Full Report Text`.
If an older saved report does not include the pharmacy name, the app adds `Zilla Pharmacy` before sending it.

If not found, the app replies:

```text
No report found for 2026-04-27.
```

## Expected Behaviour

Owner sends:

```text
Panadol sold 2
```

Reply:

```text
Logged sale: Panadol x2 = Ksh 400.
```

Owner sends:

```text
Insulin no stock
```

Reply:

```text
Logged missed demand: Insulin.
```

Owner sends:

```text
Panadol sold 2, insulin no stock, inhaler customer left
```

Reply:

```text
Logged 3 entries:

- Panadol sold 2
- Insulin missed demand
- Inhaler lost opportunity
```

## Testing

```powershell
pytest
```

Tests use fake services and do not call WhatsApp Web bridge, OpenAI, or Google Sheets.

## API Summary

- `GET /health`: health check.
- `POST /bridge/whatsapp-web`: WhatsApp Web bridge bridge endpoint.
- `POST /reports/daily`: generate, save, and optionally send the daily report.
