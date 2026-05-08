const makeWASocket = require('@whiskeysockets/baileys').default;
const { DisconnectReason, fetchLatestBaileysVersion, useMultiFileAuthState } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const P = require('pino');
const fs = require('fs');
require('dotenv').config();

const backendUrl = (process.env.PHARMAREEN_BACKEND_URL || 'http://localhost:5000').replace(/\/$/, '');
const sessionPath = process.env.BAILEYS_SESSION_PATH || './.baileys_auth';
const baileysLogLevel = process.env.BAILEYS_LOG_LEVEL || 'info';
const autoResetOnLoggedOut = String(process.env.AUTO_RESET_BAILEYS_ON_LOGOUT || 'true').toLowerCase() !== 'false';
const allowAllDirectChatsForTest = String(process.env.ALLOW_ALL_DIRECT_CHATS_FOR_TEST || 'false').toLowerCase() === 'true';
const allowedNumbers = parseAllowedNumbers(process.env.ALLOWED_WHATSAPP_NUMBERS || '');

function phoneDigits(value) {
  return String(value || '').replace(/whatsapp:/g, '').replace(/\D/g, '');
}

function parseAllowedNumbers(raw) {
  return new Set(String(raw || '').split(/[;,]/).map(phoneDigits).filter(Boolean));
}

function maskSender(value) {
  const digits = phoneDigits(value);
  if (digits) {
    if (digits.length <= 6) return `****${digits.slice(-2)}`;
    return `${digits.slice(0, 4)}******${digits.slice(-2)}`;
  }
  const text = String(value || 'unknown');
  return text.length <= 4 ? 'hidden' : `***${text.slice(-4)}`;
}

function isGroupJid(jid) {
  return String(jid || '').toLowerCase().endsWith('@g.us');
}

function isBroadcastJid(jid) {
  const text = String(jid || '').toLowerCase();
  return (
    text === 'status@broadcast' ||
    text.endsWith('@broadcast') ||
    text.endsWith('@newsletter') ||
    text.includes('newsletter') ||
    text.includes('channel')
  );
}

function jidDomain(jid) {
  const text = String(jid || '').toLowerCase();
  const atIndex = text.lastIndexOf('@');
  if (atIndex < 0) return 'unknown';
  return `@${text.slice(atIndex + 1).split(':')[0]}`;
}

function isDirectUserJid(jid) {
  const domain = jidDomain(jid);
  return domain === '@s.whatsapp.net' || domain === '@lid';
}

function jidDebug(jid) {
  return `jid_domain=${jidDomain(jid)}`;
}

function isAllowedDirectChat(jid) {
  if (!jid || isGroupJid(jid) || isBroadcastJid(jid) || !isDirectUserJid(jid)) {
    return { allowed: false, reason: 'not_direct_chat' };
  }
  if (allowAllDirectChatsForTest) {
    return { allowed: true, reason: 'test_mode_allowed_direct_chat' };
  }
  if (jidDomain(jid) === '@lid') {
    return { allowed: false, reason: 'sender_direct_but_no_phone_digits' };
  }
  if (allowedNumbers.size === 0) {
    return { allowed: false, reason: 'safe_mode_no_allowlist' };
  }
  const digits = phoneDigits(jid);
  if (!digits) {
    return { allowed: false, reason: 'sender_direct_but_no_phone_digits' };
  }
  return allowedNumbers.has(digits)
    ? { allowed: true, reason: 'allowed_number' }
    : { allowed: false, reason: 'sender_not_allowed' };
}

async function safeSendReply(sock, jid, text) {
  const safety = isAllowedDirectChat(jid);
  if (!safety.allowed) {
    console.log(`Reply blocked to ${maskSender(jid)} reason=${safety.reason}`);
    return false;
  }
  const body = String(text || '').slice(0, 4000);
  if (!body) return false;
  await sock.sendMessage(jid, { text: body });
  return true;
}

function extractText(message) {
  const content = message.message || {};
  if (content.conversation) return content.conversation;
  if (content.extendedTextMessage && content.extendedTextMessage.text) return content.extendedTextMessage.text;
  if (content.imageMessage && content.imageMessage.caption) return content.imageMessage.caption;
  if (content.videoMessage && content.videoMessage.caption) return content.videoMessage.caption;
  return '';
}

async function sendToBackend(text, sender, messageId) {
  const response = await axios.post(`${backendUrl}/bridge/whatsapp-web`, {
    message: text,
    from: sender,
    message_id: messageId || '',
    is_group: isGroupJid(sender),
    is_broadcast: isBroadcastJid(sender)
  }, { timeout: 60000 });
  return response.data || {};
}

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
    'BAILEYS_CONNECTION_UPDATE',
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

function clearBaileysSession(reason) {
  console.log(`Clearing Baileys session at ${sessionPath}. Reason: ${reason}`);
  fs.rmSync(sessionPath, { recursive: true, force: true });
}

async function startBaileys(options = {}) {
  const sessionResetAttempted = Boolean(options.sessionResetAttempted);
  console.log('PharMareen Baileys bridge starting...');
  console.log(`Backend: ${backendUrl}`);
  console.log(`Baileys session path: ${sessionPath}`);
  console.log(`Baileys log level: ${baileysLogLevel}`);
  if (allowedNumbers.size === 0) {
    console.log('SAFE MODE: no allowed numbers configured');
  } else {
    console.log(`Safety allowlist active: ${allowedNumbers.size} number(s).`);
  }
  if (allowAllDirectChatsForTest) {
    console.log('TEST MODE ACTIVE: allowing all direct chats that are not groups/broadcasts/status/newsletters/channels.');
  }
  console.log(`DEMO_MODE: ${process.env.DEMO_MODE || 'false'}`);
  console.log('GROUP REPLIES: DISABLED');
  console.log('UNKNOWN NUMBER REPLIES: DISABLED');
  console.log('Groups, broadcasts, newsletters, channels, and status messages are ignored.');
  console.log('A QR code will appear below if login is needed.');

  const { state, saveCreds } = await useMultiFileAuthState(sessionPath);
  const { version } = await fetchLatestBaileysVersion();
  console.log(`Baileys version: ${version.join('.')}`);
  const sock = makeWASocket({
    auth: state,
    version,
    logger: P({ level: baileysLogLevel }),
    printQRInTerminal: false,
    browser: ['PharMareen', 'Chrome', '1.0'],
    markOnlineOnConnect: false,
    syncFullHistory: false,
    connectTimeoutMs: 60000
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    logConnectionUpdate(update);
    if (qr) {
      console.log('\nSCAN THIS QR WITH WHATSAPP:');
      console.log('WhatsApp > Linked devices > Link a device\n');
      qrcode.generate(qr, { small: true });
    }
    if (connection === 'open') {
      console.log('Baileys bridge ready. Send a pharmacy message from an allowed direct chat.');
    }
    if (connection === 'close') {
      const statusCode = lastDisconnect && lastDisconnect.error && lastDisconnect.error.output
        ? lastDisconnect.error.output.statusCode
        : undefined;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log(`Baileys disconnected. statusCode=${statusCode || 'unknown'} reconnect=${shouldReconnect}`);
      if (!shouldReconnect && autoResetOnLoggedOut && !sessionResetAttempted) {
        clearBaileysSession('logged out or invalid stale session');
        startBaileys({ sessionResetAttempted: true }).catch((error) => console.error('Baileys reconnect after reset failed:', error.message));
        return;
      }
      if (shouldReconnect) startBaileys({ sessionResetAttempted }).catch((error) => console.error('Baileys reconnect failed:', error.message));
    }
  });

  sock.ev.on('messages.upsert', async ({ messages }) => {
    for (const msg of messages || []) {
      if (!msg.message || (msg.key && msg.key.fromMe)) continue;
      const sender = msg.key.remoteJid || 'unknown';
      const safety = isAllowedDirectChat(sender);
      if (!safety.allowed) {
        console.log(`Ignored WhatsApp message from ${maskSender(sender)} ${jidDebug(sender)} reason=${safety.reason}`);
        continue;
      }

      const text = extractText(msg).trim();
      const messageId = msg.key.id || '';
      if (!text) {
        console.log(`Allowed direct message from ${maskSender(sender)} had no text.`);
        await safeSendReply(sock, sender, 'Please send text for now, like: Panadol 2');
        continue;
      }

      console.log(`Incoming allowed direct message from ${maskSender(sender)} length=${text.length}`);
      try {
        const data = await sendToBackend(text, sender, messageId);
        if (data.status === 'ignored') {
          console.log(`Backend ignored message from ${maskSender(sender)} reason=${data.error_reason || 'unknown'}`);
          continue;
        }
        const reply = data.reply ? String(data.reply) : 'I received it, but no reply was generated.';
        await safeSendReply(sock, sender, reply);
        if (data.media_url) {
          await safeSendReply(sock, sender, `Report file: ${data.media_url}`);
        }
      } catch (error) {
        const status = error.response && error.response.status ? error.response.status : 'no-status';
        console.error(`Backend bridge error for ${maskSender(sender)} status=${status}: ${error.message}`);
        await safeSendReply(sock, sender, 'PharMareen is running, but I could not process that message right now.');
      }
    }
  });
}

startBaileys().catch((error) => {
  console.error('Failed to start Baileys bridge:', error.message);
  process.exit(1);
});
