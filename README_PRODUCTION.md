# MS2.0 Production Deployment

## Current Primary Product

MS2.0 is now Main App-first. The production owner experience should be validated from:

```text
ms20-main-app/
```

The Main App uses editable cards, offline-first queue behavior, local-first parsing, and safe backend route metadata. Confirmed Main App cards are protected as `safe_queue_only` until live write sync is deliberately enabled and tested.

For Replit live testing, pull the latest GitHub update in Replit, then verify:

```bash
cd ms20-main-app
npm run verify
npm run check
```

Use the backend-served Main App route for phone testing:

```text
https://$REPLIT_DEV_DOMAIN/main-app/
```

The bare Replit domain can remain the backend status route. Do not use desktop `127.0.0.1` as live readiness proof.

WhatsApp/Baileys below is preserved as an optional external integration layer. Do not start or test it during Main App live testing unless explicitly requested.

## Active WhatsApp Provider

Production WhatsApp should use the Baileys WhatsApp bridge.

Webhook URL:

```text
https://YOUR-DOMAIN/webhooks/baileys/whatsapp
```

Set:

```text
WHATSAPP_BRIDGE_ENABLED=true
PHARMAREEN_BACKEND_URL=http://localhost:5000
OWNER_WHATSAPP_TO=whatsapp:+254700000000
```

Keep old Meta/Twilio/WhatsApp Web bridge routes only for compatibility with older installs.

MS2.0 can run locally for testing, or on a hosted public URL so WhatsApp Web bridge does not need ngrok.

## Pharmacy Registry Model

Replit Secrets are for system credentials/config only. Do not store customer pharmacy phone numbers there as the long-term production model.

Production pharmacy access is registry-first:

- Google Sheet tab: `Pharmacies`
- Required identity fields: pharmacy ID, pharmacy name, owner name, phone number, location, timezone, currency, status, active flag, created timestamp
- `ALLOWED_WHATSAPP_NUMBERS` is only a temporary development override for controlled testing
- Unregistered direct WhatsApp numbers can only start onboarding/register a pharmacy
- Registered and active numbers route to their pharmacy workspace

## Recommended Hosting

Use any Python web host that supports FastAPI and environment variables:

- Render
- Railway
- Fly.io
- A small VPS

## Start Command

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

If your host does not provide `PORT`, use the safe fallback command:

```bash
sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
```

Deployment files are included for:

- Render: `render.yaml`
- Railway: `railway.json`
- Fly.io: `fly.toml` and `Dockerfile`
- Procfile-based hosts: `Procfile`

## Required Environment Variables

```env
PHARMACY_NAME=MS2.0
TIMEZONE=Africa/Nairobi
APP_BASE_URL=https://YOUR-DOMAIN

WHATSAPP_NUMBER=2547XXXXXXXXxxx
PHARMAREEN_BACKEND_URL=http://localhost:5000
WHATSAPP_WEB_SESSION_PATH=.wwebjs_auth
OWNER_WHATSAPP_TO=whatsapp:+254700000000
PHARMACY_REGISTRY_AUTH_ENABLED=true

GOOGLE_SHEET_ID=your-google-sheet-id
GOOGLE_SHEETS_CREDENTIALS={"type":"service_account",...}

OPENAI_API_KEY=sk-your-openai-key
OPENAI_PARSE_MODEL=gpt-5
OPENAI_TRANSCRIPTION_MODEL=whisper-1
ENABLE_VOICE_INPUT=true

REPORT_STORAGE_MODE=local
REPORT_PUBLIC_DIR=reports_pdf
```

`GOOGLE_SHEETS_CREDENTIALS` can be the full service-account JSON string. For local Windows use, `GOOGLE_SERVICE_ACCOUNT_JSON=./service-account.json` still works.

## Baileys WhatsApp Bridge Webhook

In the Baileys bridge runtime, point inbound messages to:

```text
When a message comes in:
https://YOUR-DOMAIN/webhooks/baileys/whatsapp
Method: POST
```

Compatibility routes still exist for older clients:

```text
/webhooks/twilio/whatsapp
/bridge/whatsapp-web
```

## Important: Localhost vs WhatsApp

`http://localhost:8000` only works on the computer running MS2.0.

The Baileys bridge can post to localhost when it runs beside the backend. Public HTTPS is still required for deployed browser/offline links and external callbacks.

For real pharmacy use:

1. Deploy MS2.0 to Render, Railway, Fly.io, or a VPS.
2. Set `APP_BASE_URL=https://YOUR-DOMAIN`.
3. Set the Baileys bridge endpoint to:

```text
https://YOUR-DOMAIN/webhooks/baileys/whatsapp
```

4. Open:

```text
https://YOUR-DOMAIN/status
```

The status page will show whether Google Sheets and WhatsApp Web bridge settings are ready.

## Health Check

Use:

```text
https://YOUR-DOMAIN/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "MS2.0",
  "version": "day-2"
}
```

## PDF Reports

Daily and weekly reports are saved as PDFs and served through:

```text
https://YOUR-DOMAIN/reports/download/<file-name>.pdf
```

For a simple MVP, local app storage is enough. For long-term production, move report storage to S3, Google Cloud Storage, or similar and set `REPORT_STORAGE_MODE` accordingly in a future upgrade.

## Local Development Still Works

Run locally:

```bash
setup.bat
run.bat
```

Local bridge endpoint testing can still use ngrok, but production should point WhatsApp Web bridge directly to the hosted URL.

## Readiness Checks

Before pushing online:

```bash
python scripts/check_production_ready.py
```

After deploying online:

```bash
python scripts/test_production_url.py https://YOUR-DOMAIN
```
