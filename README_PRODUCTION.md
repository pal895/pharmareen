# PharMareen Production Deployment

## Active WhatsApp Provider

Production WhatsApp should use Meta WhatsApp Cloud API.

Webhook URL:

```text
https://YOUR-DOMAIN/bridge endpoints/meta/whatsapp
```

Set:

```text
WHATSAPP_PROVIDER=meta
META_VERIFY_TOKEN=
META_ACCESS_TOKEN=
META_PHONE_NUMBER_ID=
META_WABA_ID=
META_GRAPH_API_VERSION=v21.0
```

Keep the old WhatsApp Web bridge route only for compatibility while pharmacies move to Meta.

PharMareen can run locally for testing, or on a hosted public URL so WhatsApp Web bridge does not need ngrok.

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
PHARMACY_NAME=PharMareen
TIMEZONE=Africa/Nairobi
APP_BASE_URL=https://YOUR-DOMAIN

WHATSAPP_NUMBER=2547XXXXXXXXxxx
PHARMAREEN_BACKEND_URL=http://localhost:5000
WHATSAPP_WEB_SESSION_PATH=.wwebjs_auth
OWNER_WHATSAPP_TO=whatsapp:+254700000000

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

## WhatsApp Web bridge Webhook

In WhatsApp Web bridge Sandbox or production sender settings, set:

```text
When a message comes in:
https://YOUR-DOMAIN/bridge endpoint/whatsapp
Method: POST
```

The old local route still works:

```text
/bridge/whatsapp-web
```

## Important: Localhost vs WhatsApp

`http://localhost:8000` only works on the computer running PharMareen.

WhatsApp Web bridge cannot send messages to localhost because it is not public. If the app opens locally and `/health` works, the app is running, but WhatsApp still needs a public HTTPS URL.

For real pharmacy use:

1. Deploy PharMareen to Render, Railway, Fly.io, or a VPS.
2. Set `APP_BASE_URL=https://YOUR-DOMAIN`.
3. Set the WhatsApp Web bridge bridge endpoint to:

```text
https://YOUR-DOMAIN/bridge endpoint/whatsapp
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
  "service": "PharMareen",
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
