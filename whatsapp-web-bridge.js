const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
require('dotenv').config();

const backendUrl = (process.env.PHARMAREEN_BACKEND_URL || 'http://localhost:5000').replace(/\/$/, '');
const sessionPath = process.env.WHATSAPP_WEB_SESSION_PATH || './.wwebjs_auth';
const chromePath = process.env.WHATSAPP_WEB_CHROME_PATH || process.env.PUPPETEER_EXECUTABLE_PATH;

const puppeteer = {
  headless: true,
  args: [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--no-first-run',
    '--no-zygote'
  ]
};
if (chromePath) {
  puppeteer.executablePath = chromePath;
}

console.log('PharMareen WhatsApp Web bridge starting...');
console.log(`Backend: ${backendUrl}`);
console.log('A QR code will appear below if login is needed.');

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: sessionPath, clientId: 'pharmareen' }),
  puppeteer
});

client.on('qr', (qr) => {
  console.log('\nSCAN THIS QR WITH WHATSAPP:');
  console.log('WhatsApp > Linked devices > Link a device\n');
  qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
  console.log('WhatsApp Web bridge ready. Send a pharmacy message to this WhatsApp account.');
});

client.on('authenticated', () => {
  console.log('WhatsApp Web authenticated. Session will be reused when possible.');
});

client.on('auth_failure', (message) => {
  console.error('WhatsApp Web authentication failed:', message);
});

client.on('disconnected', (reason) => {
  console.error('WhatsApp Web disconnected:', reason);
});

async function buildPayload(message) {
  const payload = {
    message: (message.body || '').trim(),
    from: message.from || 'unknown',
    message_id: message.id && (message.id._serialized || message.id.id) ? (message.id._serialized || message.id.id) : ''
  };

  if (message.hasMedia) {
    const media = await message.downloadMedia();
    if (media && media.data) {
      payload.media_base64 = media.data;
      payload.media_mime_type = media.mimetype || '';
      payload.media_filename = media.filename || '';
    }
  }
  return payload;
}

client.on('message', async (message) => {
  if (message.fromMe) return;

  try {
    const payload = await buildPayload(message);
    if (!payload.message && !payload.media_base64) {
      await message.reply('Please send text for now, like: Panadol 2');
      return;
    }

    console.log(`Incoming WhatsApp Web message from ${payload.from}: ${payload.message || payload.media_mime_type || 'media'}`);

    const response = await axios.post(`${backendUrl}/bridge/whatsapp-web`, payload, { timeout: 60000 });
    const reply = response.data && response.data.reply ? String(response.data.reply) : 'I received it, but no reply was generated.';
    await message.reply(reply.slice(0, 4000));

    if (response.data && response.data.media_url) {
      await message.reply(`Report file: ${response.data.media_url}`);
    }
  } catch (error) {
    const detail = error.response && error.response.data ? JSON.stringify(error.response.data) : error.message;
    console.error('Backend bridge error:', detail);
    await message.reply('PharMareen is running, but I could not process that message right now.');
  }
});

client.initialize().catch((error) => {
  console.error('Failed to start WhatsApp Web bridge:', error);
  console.error('The startup script will try the Baileys fallback next if ENABLE_BAILEYS_FALLBACK is true.');
  process.exit(1);
});
