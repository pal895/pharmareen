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