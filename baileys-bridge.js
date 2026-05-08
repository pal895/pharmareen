const makeWASocket = require('@whiskeysockets/baileys').default;
const { DisconnectReason, fetchLatestBaileysVersion, useMultiFileAuthState } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const P = require('pino');
require('dotenv').config();

const backendUrl = (process.env.PHARMAREEN_BACKEND_URL || 'http://localhost:5000').replace(/\/$/, '');
const sessionPath = process.env.BAILEYS_SESSION_PATH || './.baileys_auth';
const allowedNumbers = parseAllowedNumbers(process.env.ALLOWED_WHATSAPP_NUMBERS || '');

function phoneDigits(value) {
  return String(value || '').replace(/whatsapp:/g, '').replace(/\D/g, '');
}

function parseAllowedNumbers(raw) {
  return new Set(String(raw || '').split(/[;,]/).map(phoneDigits).filter(Boolean));
}

function maskSender(value) {
  const digits = phoneDigits(value);
  if (digits) return `***${digits.slice(-4)}`;
  const text = String(value || 'unknown');
  return text.length <= 4 ? 'hidden' : `***${text.slice(-4)}`;
}

function isGroupJid(jid) {
  return String(jid || '').toLowerCase().endsWith('@g.us');
}

function isBroadcastJid(jid) {
  const text = String(jid || '').toLowerCase();
  return text === 'status@broadcast' || text.endsWith('@broadcast') || text.endsWith('@newsletter');
}

function isAllowedDirectChat(jid) {
  if (!jid || isGroupJid(jid) || isBroadcastJid(jid)) {
    return { allowed: false, reason: 'not_direct_chat' };
  }
  if (allowedNumbers.size === 0) {
    return { allowed: true, reason: 'direct_chat_no_allowlist' };
  }
  const digits = phoneDigits(jid);
  return allowedNumbers.has(digits)
    ? { allowed: true, reason: 'allowed_number' }
    : { allowed: false, reason: 'sender_not_allowed' };
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

async function startBaileys() {
  console.log('PharMareen Baileys bridge starting...');
  console.log(`Backend: ${backendUrl}`);
  if (allowedNumbers.size === 0) {
    console.log('SAFETY WARNING: ALLOWED_WHATSAPP_NUMBERS is empty. Direct 1-to-1 chats are allowed for demo mode.');
  } else {
    console.log(`Safety allowlist active: ${allowedNumbers.size} number(s).`);
  }
  console.log('Groups, broadcasts, and status messages are ignored.');
  console.log('A QR code will appear below if login is needed.');

  const { state, saveCreds } = await useMultiFileAuthState(sessionPath);
  const { version } = await fetchLatestBaileysVersion();
  const sock = makeWASocket({
    auth: state,
    version,
    logger: P({ level: 'silent' }),
    printQRInTerminal: false,
    browser: ['PharMareen', 'Chrome', '1.0']
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
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
      console.log(`Baileys disconnected. Reconnect: ${shouldReconnect}`);
      if (shouldReconnect) startBaileys().catch((error) => console.error('Baileys reconnect failed:', error.message));
    }
  });

  sock.ev.on('messages.upsert', async ({ messages }) => {
    for (const msg of messages || []) {
      if (!msg.message || (msg.key && msg.key.fromMe)) continue;
      const sender = msg.key.remoteJid || 'unknown';
      const safety = isAllowedDirectChat(sender);
      if (!safety.allowed) {
        console.log(`Ignored WhatsApp message from ${maskSender(sender)} reason=${safety.reason}`);
        continue;
      }

      const text = extractText(msg).trim();
      const messageId = msg.key.id || '';
      if (!text) {
        console.log(`Allowed direct message from ${maskSender(sender)} had no text.`);
        await sock.sendMessage(sender, { text: 'Please send text for now, like: Panadol 2' });
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
        await sock.sendMessage(sender, { text: reply.slice(0, 4000) });
        if (data.media_url) {
          await sock.sendMessage(sender, { text: `Report file: ${data.media_url}` });
        }
      } catch (error) {
        const status = error.response && error.response.status ? error.response.status : 'no-status';
        console.error(`Backend bridge error for ${maskSender(sender)} status=${status}: ${error.message}`);
        await sock.sendMessage(sender, { text: 'PharMareen is running, but I could not process that message right now.' });
      }
    }
  });
}

startBaileys().catch((error) => {
  console.error('Failed to start Baileys bridge:', error.message);
  process.exit(1);
});
