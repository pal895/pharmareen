const makeWASocket = require('@whiskeysockets/baileys').default;
const { DisconnectReason, fetchLatestBaileysVersion, useMultiFileAuthState } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const P = require('pino');
require('dotenv').config();

const backendUrl = (process.env.PHARMAREEN_BACKEND_URL || 'http://localhost:5000').replace(/\/$/, '');
const sessionPath = process.env.BAILEYS_SESSION_PATH || './.baileys_auth';

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
    message_id: messageId || ''
  }, { timeout: 60000 });
  return response.data || {};
}

async function startBaileys() {
  console.log('PharMareen Baileys bridge starting...');
  console.log(`Backend: ${backendUrl}`);
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
      console.log('Baileys bridge ready. Send a pharmacy message to this WhatsApp account.');
    }
    if (connection === 'close') {
      const statusCode = lastDisconnect && lastDisconnect.error && lastDisconnect.error.output
        ? lastDisconnect.error.output.statusCode
        : undefined;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log(`Baileys disconnected. Reconnect: ${shouldReconnect}`);
      if (shouldReconnect) startBaileys().catch((error) => console.error('Baileys reconnect failed:', error));
    }
  });

  sock.ev.on('messages.upsert', async ({ messages }) => {
    for (const msg of messages || []) {
      if (!msg.message || (msg.key && msg.key.fromMe)) continue;
      const sender = msg.key.remoteJid || 'unknown';
      const text = extractText(msg).trim();
      const messageId = msg.key.id || '';
      if (!text) {
        await sock.sendMessage(sender, { text: 'Please send text for now, like: Panadol 2' });
        continue;
      }
      console.log(`Incoming Baileys message from ${sender}: ${text}`);
      try {
        const data = await sendToBackend(text, sender, messageId);
        const reply = data.reply ? String(data.reply) : 'I received it, but no reply was generated.';
        await sock.sendMessage(sender, { text: reply.slice(0, 4000) });
        if (data.media_url) {
          await sock.sendMessage(sender, { text: `Report file: ${data.media_url}` });
        }
      } catch (error) {
        const detail = error.response && error.response.data ? JSON.stringify(error.response.data) : error.message;
        console.error('Backend bridge error:', detail);
        await sock.sendMessage(sender, { text: 'PharMareen is running, but I could not process that message right now.' });
      }
    }
  });
}

startBaileys().catch((error) => {
  console.error('Failed to start Baileys bridge:', error);
  process.exit(1);
});
