const makeWASocket = require('@whiskeysockets/baileys').default;
const { DisconnectReason, fetchLatestBaileysVersion, useMultiFileAuthState } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const P = require('pino');
const fs = require('fs');
require('dotenv').config();

const sessionPath = process.env.BAILEYS_SESSION_PATH || './.baileys_auth';
const logLevel = process.env.BAILEYS_LOG_LEVEL || 'info';
const autoResetOnLoggedOut = String(process.env.AUTO_RESET_BAILEYS_ON_LOGOUT || 'true').toLowerCase() !== 'false';

function describeDisconnect(lastDisconnect) {
  const error = lastDisconnect && lastDisconnect.error ? lastDisconnect.error : undefined;
  const output = error && error.output ? error.output : undefined;
  return {
    errorMessage: error && error.message ? error.message : '',
    statusCode: output && output.statusCode ? output.statusCode : undefined,
    boomStatusCode: output && output.statusCode ? output.statusCode : undefined,
    boomPayloadStatusCode: output && output.payload ? output.payload.statusCode : undefined,
    boomPayloadError: output && output.payload ? output.payload.error : undefined,
    boomPayloadMessage: output && output.payload ? output.payload.message : undefined
  };
}

function logConnectionUpdate(update) {
  const info = describeDisconnect(update.lastDisconnect);
  console.log(
    'BAILEYS_QR_DEBUG_UPDATE',
    JSON.stringify({
      connection: update.connection || '',
      hasQr: Boolean(update.qr),
      receivedPendingNotifications: Boolean(update.receivedPendingNotifications),
      isNewLogin: Boolean(update.isNewLogin),
      errorMessage: info.errorMessage,
      statusCode: info.statusCode,
      boomStatusCode: info.boomStatusCode,
      boomPayloadStatusCode: info.boomPayloadStatusCode,
      boomPayloadError: info.boomPayloadError,
      boomPayloadMessage: info.boomPayloadMessage
    })
  );
}

function clearSession(reason) {
  console.log(`Clearing Baileys session at ${sessionPath}. Reason: ${reason}`);
  fs.rmSync(sessionPath, { recursive: true, force: true });
}

async function start(options = {}) {
  const sessionResetAttempted = Boolean(options.sessionResetAttempted);
  if (process.env.RESET_BAILEYS_SESSION === 'true' && !sessionResetAttempted) {
    clearSession('RESET_BAILEYS_SESSION=true');
  }

  console.log('Baileys QR debug starting...');
  console.log(`Session path: ${sessionPath}`);
  console.log(`Log level: ${logLevel}`);

  const { state, saveCreds } = await useMultiFileAuthState(sessionPath);
  const { version } = await fetchLatestBaileysVersion();
  console.log(`Baileys version: ${version.join('.')}`);

  const sock = makeWASocket({
    auth: state,
    version,
    logger: P({ level: logLevel }),
    printQRInTerminal: false,
    browser: ['PharMareen QR Debug', 'Chrome', '1.0'],
    markOnlineOnConnect: false,
    syncFullHistory: false,
    connectTimeoutMs: 60000
  });

  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', (update) => {
    logConnectionUpdate(update);
    if (update.qr) {
      console.log('\nSCAN THIS QR WITH WHATSAPP:');
      console.log('WhatsApp > Linked devices > Link a device\n');
      qrcode.generate(update.qr, { small: true });
    }
    if (update.connection === 'open') {
      console.log('Baileys QR debug connected successfully.');
    }
    if (update.connection === 'close') {
      const statusCode = update.lastDisconnect && update.lastDisconnect.error && update.lastDisconnect.error.output
        ? update.lastDisconnect.error.output.statusCode
        : undefined;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log(`Baileys QR debug disconnected. statusCode=${statusCode || 'unknown'} reconnect=${shouldReconnect}`);
      if (!shouldReconnect && autoResetOnLoggedOut && !sessionResetAttempted) {
        clearSession('logged out or invalid stale session');
        start({ sessionResetAttempted: true }).catch((error) => {
          console.error('Baileys QR debug reconnect after reset failed:', error.message);
          process.exit(1);
        });
      }
    }
  });
}

start().catch((error) => {
  console.error('Baileys QR debug failed:', error.message);
  process.exit(1);
});
