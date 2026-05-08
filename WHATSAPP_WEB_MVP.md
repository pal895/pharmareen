# WhatsApp Web MVP Bridge

This is the temporary MVP channel while Meta Cloud API is blocked by business verification.

## What It Does

- Runs the existing PharMareen FastAPI backend on port 5000.
- Starts a WhatsApp Web client using `whatsapp-web.js`.
- Prints a QR code in the terminal.
- After QR login, listens for incoming WhatsApp messages.
- Sends message text and sender ID to the existing backend endpoint:
  `/bridge/whatsapp-web`
- Sends the backend reply back to WhatsApp.

The pharmacy logic stays inside FastAPI. The Node bridge only moves messages in and out of WhatsApp Web.

## Environment Variables

```env
PHARMAREEN_BACKEND_URL=http://localhost:5000
WHATSAPP_WEB_SESSION_PATH=.wwebjs_auth
WHATSAPP_WEB_CHROME_PATH=
```

`WHATSAPP_WEB_CHROME_PATH` is optional. Set it only if Replit needs an explicit Chromium path.

## Install Node Dependencies

```bash
npm install
```

## Run Backend Only

```bash
./start.sh
```

## Run Backend + WhatsApp Web Bridge

```bash
./start_with_whatsapp_web.sh
```

Or in two terminals:

```bash
./start.sh
npm run wa:bridge
```

## QR Login

1. Start the bridge.
2. Wait for the QR code in the terminal.
3. Open WhatsApp on the phone.
4. Tap Linked devices.
5. Tap Link a device.
6. Scan the QR code.
7. Send test messages:

```text
help
Panadol 2
Panadol stock
report today
```

## If whatsapp-web.js Fails on Replit

If Chromium cannot start, the backend is still ready. Use Baileys as the next fallback because it does not require a full browser session.

## Safety Guardrails

The WhatsApp Web bridge is locked down for demo safety:

- Group chats are ignored.
- Broadcast/status/newsletter messages are ignored.
- Only direct 1-to-1 chats are processed.
- Logs mask phone numbers and do not print full message bodies from unknown chats.
- Replies are only sent to allowed direct chats.

Set this in Replit Secrets before a real demo:

```env
ALLOWED_WHATSAPP_NUMBERS=2547XXXXXXXX
```

Use comma-separated numbers for more than one staff phone.

## Demo Mode

If Google Sheets credentials are missing, PharMareen automatically uses safe local demo data so commands can be tested without changing real pharmacy records.

You can force this mode with:

```env
DEMO_MODE=true
```

For a real pharmacy, add Google Sheets credentials and set:

```env
DEMO_MODE=false
```
