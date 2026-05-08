# PharMareen Windows WhatsApp Bridge

Use this when Replit Node/npm is unstable.

The setup is:

- Replit runs the FastAPI backend.
- Your Windows laptop runs the Baileys WhatsApp Web bridge.
- The local bridge sends safe messages to:
  `/bridge/whatsapp-web`

## 1. Install Node.js 20 LTS

Install Node.js 20 LTS from the official Node website:

https://nodejs.org/en/download

After installing, close Command Prompt and open a new Command Prompt.

Check:

```cmd
node -v
npm -v
```

## 2. Start the Replit backend

In Replit, keep FastAPI running.

Open:

```text
https://pharmareen-1--pal895.replit.app/health
```

Expected:

```json
{"status":"ok"}
```

## 3. Run the bridge from Windows CMD

Open Command Prompt in the project folder.

Example:

```cmd
cd /d "C:\Users\Pal\Desktop\pharmareen-git"
set PHARMAREEN_BACKEND_URL=https://pharmareen-1--pal895.replit.app
set ALLOWED_WHATSAPP_NUMBERS=254757637709
npm install
node baileys-bridge.js
```

Or use the helper:

```cmd
cd /d "C:\Users\Pal\Desktop\pharmareen-git"
set PHARMAREEN_BACKEND_URL=https://pharmareen-1--pal895.replit.app
set ALLOWED_WHATSAPP_NUMBERS=254757637709
start_local_whatsapp_bridge.bat
```

Phase 2 temporary test mode for newer Baileys direct-chat JIDs:

```cmd
cd /d "C:\Users\Pal\Desktop\pharmareen-git"
set PHARMAREEN_BACKEND_URL=https://pharmareen-1--pal895.replit.app
set ALLOWED_WHATSAPP_NUMBERS=254757637709
set ALLOW_ALL_DIRECT_CHATS_FOR_TEST=true
node local_whatsapp_bridge.js
```

This still blocks groups, broadcasts, status, newsletters, and channels. Use it only while testing `@lid` direct chats.

## 4. Scan the QR

When the QR appears:

1. Open WhatsApp on the phone.
2. Open Linked devices.
3. Tap Link a device.
4. Scan the QR in the Windows terminal.

Keep the terminal open.

## 5. Safety Rules

The bridge is locked down:

- Groups are ignored.
- Broadcast/status/newsletter/channel messages are ignored.
- Only direct 1-to-1 chats are processed.
- Only numbers in `ALLOWED_WHATSAPP_NUMBERS` are processed.
- Unknown numbers receive no reply.
- Blocked message bodies are not logged.
- Phone numbers are masked in logs.
- `DEMO_MODE=true` still obeys the allowlist.

If `ALLOWED_WHATSAPP_NUMBERS` is missing, the helper refuses to start.

## 6. Test Messages

From the allowed WhatsApp number, send:

```text
help
Panadol 2
Panadol stock
report today
```

## 7. Reset WhatsApp Login

If the QR does not appear or WhatsApp says the session is bad:

```cmd
set RESET_BAILEYS_SESSION=true
start_local_whatsapp_bridge.bat
```

After a clean login, you can close the window and reopen without the reset line.

## 8. QR Debug Only

To test QR without pharmacy backend processing:

```cmd
set BAILEYS_LOG_LEVEL=debug
set RESET_BAILEYS_SESSION=true
node scripts\baileys_qr_debug.js
```

This prints the Baileys version, session path, connection updates, QR presence, status code, and disconnect reason.
