# Deploy PharMareen Now

PharMareen works locally at `http://localhost:8000`, but WhatsApp needs a public HTTPS URL.

Use one of these options, then set Twilio to:

```text
https://YOUR-DOMAIN/webhook/whatsapp
```

The app start command is:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

If `$PORT` is missing, the deployment files use port `8000`.

## Required Environment Variables

Add these in Render, Railway, or Fly.io:

```env
PHARMACY_NAME=PharMareen
TIMEZONE=Africa/Nairobi
APP_BASE_URL=https://YOUR-DOMAIN

TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
OWNER_WHATSAPP_TO=whatsapp:+2547XXXXXXXX

GOOGLE_SHEET_ID=your-google-sheet-id
GOOGLE_SHEETS_CREDENTIALS={"type":"service_account",...}

OPENAI_API_KEY=your-openai-api-key
ENABLE_VOICE_INPUT=true

REPORT_STORAGE_MODE=local
REPORT_PUBLIC_DIR=reports_pdf
```

For `GOOGLE_SHEETS_CREDENTIALS`, paste the full service-account JSON as one environment variable. Do not upload `service-account.json` to GitHub.

## Option A: Render

1. Push this project to GitHub.
2. Open Render.
3. Create a new Web Service.
4. Select the GitHub repo.
5. Use build command:

```bash
pip install -r requirements.txt
```

6. Use start command:

```bash
sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
```

7. Add all required environment variables.
8. Deploy.
9. Copy the Render URL, for example:

```text
https://pharmareen.onrender.com
```

10. Set `APP_BASE_URL` to that URL.
11. Open:

```text
https://YOUR-RENDER-URL/status
```

12. Put this webhook in Twilio:

```text
https://YOUR-RENDER-URL/webhook/whatsapp
```

## Option B: Railway

1. Push this project to GitHub.
2. Open Railway.
3. Create a new project.
4. Choose Deploy from GitHub.
5. Select the PharMareen repo.
6. Railway can use `railway.json`. If it asks for a start command, use:

```bash
sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
```

7. Add all required environment variables.
8. Deploy.
9. Create or copy the public Railway domain.
10. Set `APP_BASE_URL` to that public domain.
11. Open:

```text
https://YOUR-RAILWAY-DOMAIN/status
```

12. Put this webhook in Twilio:

```text
https://YOUR-RAILWAY-DOMAIN/webhook/whatsapp
```

## Option C: Fly.io

1. Install `flyctl`.
2. Open a terminal in the project folder.
3. Run:

```bash
fly launch
```

4. Choose the existing `fly.toml` if asked.
5. Set secrets:

```bash
fly secrets set APP_BASE_URL=https://YOUR-FLY-APP.fly.dev
fly secrets set TWILIO_ACCOUNT_SID=your-twilio-account-sid
fly secrets set TWILIO_AUTH_TOKEN=your-twilio-auth-token
fly secrets set TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
fly secrets set OWNER_WHATSAPP_TO=whatsapp:+2547XXXXXXXX
fly secrets set GOOGLE_SHEET_ID=your-google-sheet-id
fly secrets set GOOGLE_SHEETS_CREDENTIALS='{"type":"service_account",...}'
fly secrets set OPENAI_API_KEY=your-openai-api-key
fly secrets set ENABLE_VOICE_INPUT=true
fly secrets set REPORT_STORAGE_MODE=local
fly secrets set REPORT_PUBLIC_DIR=reports_pdf
```

6. Deploy:

```bash
fly deploy
```

7. Open:

```text
https://YOUR-FLY-APP.fly.dev/status
```

8. Put this webhook in Twilio:

```text
https://YOUR-FLY-APP.fly.dev/webhook/whatsapp
```

## Twilio Console Steps

1. Open Twilio Console.
2. Go to Messaging.
3. Go to WhatsApp Sandbox or WhatsApp Sender.
4. Find `When a message comes in`.
5. Paste:

```text
https://YOUR-DOMAIN/webhook/whatsapp
```

6. Method: `POST`.
7. Click Save.
8. Send `start` from WhatsApp.

## Test Production

After deployment:

```bash
python scripts/test_production_url.py https://YOUR-DOMAIN
```

Expected:

```text
FINAL RESULT: PRODUCTION URL WORKS
```

## Troubleshooting

If WhatsApp gets no reply:

1. Open `https://YOUR-DOMAIN/status`.
2. Confirm `APP_BASE_URL` is the production HTTPS URL.
3. Confirm the Twilio webhook is exactly `/webhook/whatsapp`.
4. Confirm Twilio credentials are correct.
5. Confirm Google Sheets credentials are correct.
6. Confirm the Google Sheet is shared with the service-account email.
7. Check the hosting logs for errors.

If reports generate but PDF does not open on phone:

1. Confirm `APP_BASE_URL` starts with `https://`.
2. Open `https://YOUR-DOMAIN/reports/download/<file>.pdf` from your phone.
3. If using free hosting, make sure the app is awake before sending reports.
