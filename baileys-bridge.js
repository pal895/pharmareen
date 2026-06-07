const makeWASocket = require('@whiskeysockets/baileys').default;
const {
  DisconnectReason,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
  generateWAMessageFromContent,
  proto,
  useMultiFileAuthState
} = require('@whiskeysockets/baileys');
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
const allowedNumbers = parseAllowedNumbers(
  `${process.env.ALLOWED_WHATSAPP_NUMBERS || ''},${process.env.ALLOWED_DIRECT_CHAT_NUMBERS || ''}`
);
const allowedLids = parseAllowedLids(
  `${process.env.ALLOWED_DIRECT_CHAT_LIDS || ''},${process.env.ALLOWED_WHATSAPP_LIDS || ''}`
);
const offlineConfirmationPollMs = Number(process.env.OFFLINE_CONFIRMATION_POLL_MS || 10000);
let offlineConfirmationPoller = null;
let reconnectTimer = null;
const phoneByLid = new Map();
const currentRuntimeStatus = {
  state: 'starting',
  connected: false,
  qr_required: false,
  last_message_received: '',
  last_reply_sent: '',
  last_error: ''
};

function phoneDigits(value) {
  return String(value || '').replace(/whatsapp:/g, '').replace(/\D/g, '');
}

function parseAllowedNumbers(raw) {
  return new Set(String(raw || '').split(/[;,]/).map(phoneDigits).filter(Boolean));
}

function normalizeLid(value) {
  let text = String(value || '').trim().toLowerCase().replace(/whatsapp:/g, '');
  if (!text) return '';
  if (text.includes('@')) text = text.slice(0, text.lastIndexOf('@'));
  if (text.includes(':')) text = text.split(':')[0];
  return text.replace(/[^a-z0-9]/g, '');
}

function parseAllowedLids(raw) {
  return new Set(String(raw || '').split(/[;,]/).map(normalizeLid).filter(Boolean));
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

function senderIdentityFromMessage(msg) {
  const key = (msg && msg.key) || {};
  const senderJid = key.remoteJid || 'unknown';
  const candidates = [
    key.remoteJid,
    key.participant,
    key.remoteJidAlt,
    key.participantAlt,
    key.senderPn,
    key.senderJid,
    msg && msg.participant,
    msg && msg.sender
  ].filter(Boolean);
  let normalizedPhone = '';
  let normalizedLid = '';
  for (const candidate of candidates) {
    const domain = jidDomain(candidate);
    if (!normalizedPhone && domain === '@s.whatsapp.net') normalizedPhone = phoneDigits(candidate);
    if (!normalizedLid && domain === '@lid') normalizedLid = normalizeLid(candidate);
  }
  if (!normalizedPhone && normalizedLid && phoneByLid.has(normalizedLid)) {
    normalizedPhone = phoneByLid.get(normalizedLid);
  }
  return { senderJid, normalizedPhone, normalizedLid };
}

function isAllowedDirectChat(jid, identity = {}) {
  if (!jid || isGroupJid(jid) || isBroadcastJid(jid) || !isDirectUserJid(jid)) {
    return { allowed: false, reason: 'not_direct_chat' };
  }
  if (allowAllDirectChatsForTest) {
    return { allowed: true, reason: 'test_mode_allowed_direct_chat' };
  }
  if (allowedNumbers.size === 0 && allowedLids.size === 0) {
    return { allowed: false, reason: 'safe_mode_no_allowlist' };
  }
  const domain = jidDomain(jid);
  const normalizedPhone = identity.normalizedPhone || (domain === '@s.whatsapp.net' ? phoneDigits(jid) : '');
  const normalizedLid = identity.normalizedLid || (domain === '@lid' ? normalizeLid(jid) : '');
  if (normalizedPhone && allowedNumbers.has(normalizedPhone)) {
    return { allowed: true, reason: 'allowed_number' };
  }
  if (normalizedLid && allowedLids.has(normalizedLid)) {
    return { allowed: true, reason: 'allowed_lid' };
  }
  if (domain === '@lid' && !normalizedPhone && allowedLids.size === 0) {
    return { allowed: false, reason: 'sender_direct_but_no_phone_digits' };
  }
  if (domain === '@lid') {
    return { allowed: false, reason: 'sender_lid_not_allowed' };
  }
  if (!normalizedPhone) {
    return { allowed: false, reason: 'sender_direct_but_no_phone_digits' };
  }
  return { allowed: false, reason: 'sender_not_allowed' };
}

function logAllowlistDecision(identity, safety) {
  console.log(
    `ALLOWLIST_DECISION sender_jid=${identity.senderJid || ''} sender_domain=${jidDomain(identity.senderJid || '')} ` +
    `normalized_phone=${identity.normalizedPhone || ''} normalized_lid=${identity.normalizedLid || ''} ` +
    `allowed=${Boolean(safety && safety.allowed)} reason=${(safety && safety.reason) || 'unknown'}`
  );
}

function indexContactIdentity(contact) {
  const candidates = [
    contact && contact.id,
    contact && contact.jid,
    contact && contact.lid,
    contact && contact.phoneNumber,
    contact && contact.pn
  ].filter(Boolean);
  let lid = '';
  let phone = '';
  for (const candidate of candidates) {
    const domain = jidDomain(candidate);
    if (!lid && domain === '@lid') lid = normalizeLid(candidate);
    if (!phone && domain === '@s.whatsapp.net') phone = phoneDigits(candidate);
    if (!phone && String(candidate || '').startsWith('+')) phone = phoneDigits(candidate);
  }
  if (lid && phone) {
    phoneByLid.set(lid, phone);
    console.log(`CONTACT_IDENTITY_INDEXED normalized_lid=${lid} normalized_phone=${phone}`);
  }
}

async function safeSendReply(sock, jid, text) {
  const startedAt = Date.now();
  const safety = isAllowedDirectChat(jid);
  if (!safety.allowed) {
    console.log(`Reply blocked to ${maskSender(jid)} reason=${safety.reason}`);
    return false;
  }
  const body = String(text || '').slice(0, 4000);
  if (!body) return false;
  console.log(`WHATSAPP_SEND_TARGET jid=${maskSender(jid)} ${jidDebug(jid)} length=${body.length}`);
  try {
    const result = await sock.sendMessage(jid, { text: body });
    const messageId = result && result.key ? result.key.id : '';
    console.log(`WHATSAPP_REPLY_SENT to ${maskSender(jid)} ${jidDebug(jid)} message_id=${messageId || 'unknown'} length=${body.length}`);
    console.log(`WHATSAPP_SEND_TIMING jid=${maskSender(jid)} elapsed_ms=${Date.now() - startedAt}`);
    reportRuntimeStatus({ state: 'connected', connected: true, last_reply_sent: new Date().toISOString(), last_error: '' });
    return true;
  } catch (error) {
    console.error(`WHATSAPP_SEND_FAILED to ${maskSender(jid)} ${jidDebug(jid)}: ${error.stack || error.message}`);
    reportRuntimeStatus({ last_error: `reply_send_failed: ${error.message || error}` });
    return false;
  }
}

function logSelectorCardFallback(data, sender) {
  const card = data && data.selector_card;
  if (!card || card.type !== 'sale_selector') return;
  console.log(
    `SELECTOR_CARD_FALLBACK sender=${maskSender(sender)} medicine=${card.medicine || ''} ` +
    `quantity=${card.quantity || 1} payment=${card.payment || 'Cash'} interactive=false`
  );
}

function selectorRows(card) {
  const quantity = Number(card.quantity || 1) || 1;
  const payment = String(card.payment || 'Cash');
  return [
    { title: 'Confirm', rowId: 'confirm', description: `${card.medicine || 'Medicine'} x${quantity} ${payment}` },
    { title: 'Cancel', rowId: 'cancel', description: 'Do not save' },
    { title: '+', rowId: '+', description: 'Add one' },
    { title: '-', rowId: '-', description: 'Remove one' },
    ...[1, 2, 3, 5, 10].map(qty => ({ title: `${qty} Cash`, rowId: `${qty} cash`, description: `Qty ${qty}, Cash` })),
    ...[1, 2, 3, 5, 10].map(qty => ({ title: `${qty} M-Pesa`, rowId: `${qty} mpesa`, description: `Qty ${qty}, M-Pesa` })),
    { title: 'Credit', rowId: `${quantity} credit`, description: `Qty ${quantity}, Credit` },
    { title: 'Mixed', rowId: `${quantity} mixed`, description: `Qty ${quantity}, Mixed` }
  ];
}

function compactSelectorText(card, replyText) {
  const quantity = Number(card.quantity || 1) || 1;
  const payment = String(card.payment || 'Cash');
  const medicine = String(card.medicine || 'Medicine');
  return [
    `${medicine} x${quantity} • ${payment}`,
    'Choose: 1/2/3/5/10, Cash/M-Pesa/Credit/Mixed',
    'Confirm | Cancel'
  ].join('\n');
}

function selectorListMessage(card, body) {
  const rows = selectorRows(card);
  return proto.Message.fromObject({
    listMessage: {
      title: `${card.medicine || 'Medicine'} sale`,
      description: body,
      buttonText: 'Choose',
      listType: 1,
      footerText: 'PharMareen',
      sections: [
        { title: 'Save', rows: rows.slice(0, 4) },
        { title: 'Cash', rows: rows.slice(4, 9) },
        { title: 'M-Pesa', rows: rows.slice(9, 14) },
        { title: 'Other', rows: rows.slice(14) }
      ]
    }
  });
}

function selectorButtonsMessage(card, body) {
  return proto.Message.fromObject({
    buttonsMessage: {
      contentText: body,
      footerText: 'PharMareen',
      headerType: 1,
      buttons: [
        { buttonId: 'confirm', buttonText: { displayText: 'Confirm' }, type: 1 },
        { buttonId: '+', buttonText: { displayText: '+' }, type: 1 },
        { buttonId: 'cancel', buttonText: { displayText: 'Cancel' }, type: 1 }
      ]
    }
  });
}

async function relaySelectorNativeMessage(sock, jid, messageContent) {
  const message = generateWAMessageFromContent(jid, messageContent, {
    userJid: sock && sock.user && sock.user.id ? sock.user.id : undefined
  });
  await sock.relayMessage(jid, message.message, { messageId: message.key.id });
  return message;
}

async function safeSendSelectorReply(sock, jid, data, replyText) {
  const card = data && data.selector_card;
  if (!card || card.type !== 'sale_selector') {
    return safeSendReply(sock, jid, replyText);
  }
  const safety = isAllowedDirectChat(jid);
  if (!safety.allowed) {
    console.log(`Reply blocked to ${maskSender(jid)} reason=${safety.reason}`);
    return false;
  }
  const body = compactSelectorText(card, replyText).slice(0, 1000);
  const startedAt = Date.now();
  console.log(
    `SELECTOR_INTERACTIVE_ATTEMPT sender=${maskSender(jid)} medicine=${card.medicine || ''} ` +
    `quantity=${card.quantity || 1} payment=${card.payment || 'Cash'}`
  );
  try {
    console.log(`SELECTOR_LIST_ATTEMPT sender=${maskSender(jid)}`);
    const result = await relaySelectorNativeMessage(sock, jid, selectorListMessage(card, body));
    const messageId = result && result.key ? result.key.id : '';
    console.log(
      `SELECTOR_INTERACTIVE_SENT sender=${maskSender(jid)} type=list message_id=${messageId || 'unknown'} ` +
      `elapsed_ms=${Date.now() - startedAt}`
    );
    reportRuntimeStatus({ state: 'connected', connected: true, last_reply_sent: new Date().toISOString(), last_error: '' });
    return true;
  } catch (listError) {
    console.error(`SELECTOR_LIST_FAILED sender=${maskSender(jid)} error=${listError.stack || listError.message}`);
  }
  try {
    console.log(`SELECTOR_BUTTONS_ATTEMPT sender=${maskSender(jid)}`);
    const result = await relaySelectorNativeMessage(sock, jid, selectorButtonsMessage(card, body));
    const messageId = result && result.key ? result.key.id : '';
    console.log(
      `SELECTOR_INTERACTIVE_SENT sender=${maskSender(jid)} type=buttons message_id=${messageId || 'unknown'} ` +
      `elapsed_ms=${Date.now() - startedAt}`
    );
    reportRuntimeStatus({ state: 'connected', connected: true, last_reply_sent: new Date().toISOString(), last_error: '' });
    return true;
  } catch (buttonError) {
    console.error(`SELECTOR_INTERACTIVE_FAILED sender=${maskSender(jid)} fallback=text error=${buttonError.stack || buttonError.message}`);
    logSelectorCardFallback(data, jid);
    return safeSendReply(sock, jid, body);
  }
}

function extractText(message) {
  const content = unwrapMessageContent(message.message || {});
  if (content.conversation) return content.conversation;
  if (content.extendedTextMessage && content.extendedTextMessage.text) return content.extendedTextMessage.text;
  if (content.buttonsResponseMessage) {
    return content.buttonsResponseMessage.selectedDisplayText || content.buttonsResponseMessage.selectedButtonId || '';
  }
  if (content.listResponseMessage) {
    const selected = content.listResponseMessage.singleSelectReply || {};
    return content.listResponseMessage.title || selected.selectedRowId || content.listResponseMessage.description || '';
  }
  if (content.templateButtonReplyMessage) {
    return content.templateButtonReplyMessage.selectedDisplayText || content.templateButtonReplyMessage.selectedId || '';
  }
  if (content.interactiveResponseMessage && content.interactiveResponseMessage.nativeFlowResponseMessage) {
    const flow = content.interactiveResponseMessage.nativeFlowResponseMessage;
    if (flow.paramsJson) {
      try {
        const parsed = JSON.parse(flow.paramsJson);
        return parsed.title || parsed.id || parsed.name || '';
      } catch {
        return flow.paramsJson;
      }
    }
  }
  if (content.imageMessage && content.imageMessage.caption) return content.imageMessage.caption;
  if (content.videoMessage && content.videoMessage.caption) return content.videoMessage.caption;
  return '';
}

function unwrapMessageContent(content) {
  let current = content || {};
  for (let index = 0; index < 5; index += 1) {
    if (current.ephemeralMessage && current.ephemeralMessage.message) {
      current = current.ephemeralMessage.message;
      continue;
    }
    if (current.viewOnceMessage && current.viewOnceMessage.message) {
      current = current.viewOnceMessage.message;
      continue;
    }
    if (current.viewOnceMessageV2 && current.viewOnceMessageV2.message) {
      current = current.viewOnceMessageV2.message;
      continue;
    }
    if (current.documentWithCaptionMessage && current.documentWithCaptionMessage.message) {
      current = current.documentWithCaptionMessage.message;
      continue;
    }
    return current;
  }
  return current;
}

function audioMessageFrom(message) {
  const content = unwrapMessageContent(message.message || {});
  if (content.audioMessage) return content.audioMessage;
  if (content.pttMessage) return content.pttMessage;
  return null;
}

function imageMessageFrom(message) {
  const content = unwrapMessageContent(message.message || {});
  if (content.imageMessage) return content.imageMessage;
  return null;
}

function isAudioMessage(message) {
  return Boolean(audioMessageFrom(message));
}

function isImageMessage(message) {
  return Boolean(imageMessageFrom(message));
}

function audioMimeType(message) {
  const audio = audioMessageFrom(message);
  return (audio && audio.mimetype) || 'audio/ogg';
}

function imageMimeType(message) {
  const image = imageMessageFrom(message);
  return (image && image.mimetype) || 'image/jpeg';
}

async function downloadMediaBase64(sock, msg) {
  const buffer = await downloadMediaMessage(
    msg,
    'buffer',
    {},
    {
      logger: P({ level: 'silent' }),
      reuploadRequest: sock.updateMediaMessage
    }
  );
  return Buffer.from(buffer).toString('base64');
}

async function downloadAudioBase64(sock, msg) {
  return downloadMediaBase64(sock, msg);
}

async function downloadImageBase64(sock, msg) {
  return downloadMediaBase64(sock, msg);
}

async function sendToBackend(text, sender, messageId, extraPayload = {}, identity = {}) {
  const url = `${backendUrl}/bridge/whatsapp-web`;
  const payload = {
    message: text,
    from: sender,
    sender_jid: identity.senderJid || sender,
    sender_phone: identity.normalizedPhone || '',
    sender_lid: identity.normalizedLid || '',
    message_id: messageId || '',
    is_group: isGroupJid(sender),
    is_broadcast: isBroadcastJid(sender),
    allow_all_direct_chats_for_test: allowAllDirectChatsForTest,
    ...extraPayload
  };
  console.log(`BACKEND_REQUEST_URL ${url}`);
  console.log(
    `BACKEND_REQUEST_PAYLOAD sender=${maskSender(sender)} ${jidDebug(sender)} ` +
    `normalized_phone=${identity.normalizedPhone || ''} normalized_lid=${identity.normalizedLid || ''} ` +
    `message_length=${String(text || '').length} has_media=${Boolean(extraPayload.media_base64)} ` +
    `media_mime_type=${extraPayload.media_mime_type || ''} test_mode=${allowAllDirectChatsForTest}`
  );
  const response = await axios.post(url, payload, { timeout: 60000 });
  console.log(`BACKEND_HTTP_STATUS ${response.status}`);
  console.log(`BACKEND_JSON_RESPONSE ${JSON.stringify(response.data || {})}`);
  return response.data || {};
}

function normalizeConfirmationJid(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  if (raw.includes('@')) return raw;
  const digits = phoneDigits(raw);
  return digits ? `${digits}@s.whatsapp.net` : raw;
}

async function reportRuntimeStatus(patch = {}) {
  Object.assign(currentRuntimeStatus, patch);
  try {
    await axios.post(`${backendUrl}/bridge/runtime-status`, currentRuntimeStatus, { timeout: 5000 });
  } catch (error) {
    console.log(`BRIDGE_RUNTIME_STATUS_SKIPPED ${error.message}`);
  }
}

setInterval(() => reportRuntimeStatus({}), 10000);

async function resolveOfflineConfirmationTarget(sock, rawTarget, itemId) {
  const normalized = normalizeConfirmationJid(rawTarget);
  console.log(`normalized jid=${normalized} ${jidDebug(normalized)}`);
  if (!normalized) {
    console.log(`offline confirmation send failed id=${itemId || 'unknown'} reason=missing_target`);
    return '';
  }
  if (jidDomain(normalized) !== '@s.whatsapp.net' || typeof sock.onWhatsApp !== 'function') {
    return normalized;
  }

  try {
    const lookup = await sock.onWhatsApp(normalized);
    const results = Array.isArray(lookup) ? lookup : [];
    const match = results.find((row) => row && row.exists);
    const resolved = match && match.jid ? match.jid : '';
    console.log(
      `offline confirmation onWhatsApp result id=${itemId || 'unknown'} ` +
      `exists=${Boolean(resolved)} jid=${maskSender(resolved || normalized)}`
    );
    if (!resolved) {
      console.log(
        `offline confirmation send failed id=${itemId || 'unknown'} ` +
        `to=${maskSender(normalized)} reason=number_not_registered_on_whatsapp`
      );
      console.log(
        `confirmation delivery result id=${itemId || 'unknown'} sent=false ` +
        `acked=false reason=number_not_registered_on_whatsapp`
      );
      return '';
    }
    return resolved;
  } catch (error) {
    console.log(
      `offline confirmation onWhatsApp check failed id=${itemId || 'unknown'} ` +
      `reason=${error.message || error} fallback=normalized_jid`
    );
    return normalized;
  }
}

async function sendOfflineConfirmation(sock, target, text, itemId) {
  const safety = isAllowedDirectChat(target);
  if (!safety.allowed) {
    console.log(
      `offline confirmation send failed id=${itemId || 'unknown'} ` +
      `to=${maskSender(target)} reason=${safety.reason}`
    );
    console.log(
      `confirmation delivery result id=${itemId || 'unknown'} sent=false ` +
      `acked=false reason=${safety.reason}`
    );
    return { sent: false, error: safety.reason };
  }

  const body = String(text || '').slice(0, 4000);
  if (!body) {
    console.log(`offline confirmation send failed id=${itemId || 'unknown'} reason=empty_message`);
    console.log(`confirmation delivery result id=${itemId || 'unknown'} sent=false acked=false reason=empty_message`);
    return { sent: false, error: 'empty_message' };
  }

  console.log(`sending offline confirmation id=${itemId || 'unknown'} to=${maskSender(target)} length=${body.length}`);
  console.log(`WHATSAPP_CONFIRMATION_SEND_TARGET id=${itemId || 'unknown'} jid=${target} ${jidDebug(target)} length=${body.length}`);
  console.log(`WHATSAPP_SEND_TARGET jid=${maskSender(target)} ${jidDebug(target)} length=${body.length}`);
  try {
    const result = await sock.sendMessage(target, { text: body });
    const messageId = result && result.key ? result.key.id : '';
    console.log(
      `offline confirmation sent successfully id=${itemId || 'unknown'} ` +
      `to=${maskSender(target)} message_id=${messageId || 'unknown'}`
    );
    console.log(
      `confirmation delivery result id=${itemId || 'unknown'} sent=true ` +
      `acked=false message_id=${messageId || 'unknown'}`
    );
    console.log(
      `WHATSAPP_CONFIRMATION_SEND_RESULT id=${itemId || 'unknown'} sent=true ` +
      `acked=false message_id=${messageId || 'unknown'}`
    );
    reportRuntimeStatus({ state: 'connected', connected: true, last_reply_sent: new Date().toISOString(), last_error: '' });
    return { sent: true, messageId };
  } catch (error) {
    const reason = error && (error.stack || error.message) ? (error.stack || error.message) : String(error);
    console.error(`offline confirmation send failed id=${itemId || 'unknown'} to=${maskSender(target)} reason=${reason}`);
    console.log(
      `confirmation delivery result id=${itemId || 'unknown'} sent=false ` +
      `acked=false reason=${error.message || 'send_failed'}`
    );
    console.log(
      `WHATSAPP_CONFIRMATION_SEND_RESULT id=${itemId || 'unknown'} sent=false ` +
      `acked=false reason=${error.message || 'send_failed'}`
    );
    reportRuntimeStatus({ last_error: `offline_confirmation_send_failed: ${error.message || error}` });
    return { sent: false, error: error.message || 'send_failed' };
  }
}

async function pollOfflineConfirmations(sock) {
  try {
    const response = await axios.get(`${backendUrl}/offline/whatsapp-confirmations`, { timeout: 10000 });
    const payload = response.data || {};
    const confirmations = Array.isArray(payload.confirmations)
      ? payload.confirmations
      : (Array.isArray(payload.pending) ? payload.pending : []);
    const pendingCount = Number(payload.pending_count || confirmations.length || 0);
    if (pendingCount && !confirmations.length) {
      console.log(`OFFLINE_CONFIRMATION_FORMAT_EMPTY pending_count=${pendingCount}`);
    }
    if (!confirmations.length) return;
    const sentIds = [];
    for (const item of confirmations) {
      const rawTarget = item.to || item.sender || item.jid;
      console.log(`bridge picked offline confirmation id=${item.id || 'unknown'} to=${maskSender(rawTarget)}`);
      console.log(`BRIDGE_PICKED_OFFLINE_CONFIRMATION id=${item.id || 'unknown'} to=${maskSender(rawTarget)}`);
      const target = await resolveOfflineConfirmationTarget(sock, rawTarget, item.id);
      const message = String(item.message || '').trim();
      if (!target || !message) continue;
      const delivery = await sendOfflineConfirmation(sock, target, message, item.id);
      if (delivery.sent && item.id) {
        sentIds.push(item.id);
      } else {
        console.log(`offline confirmation send failed id=${item.id || 'unknown'} to=${maskSender(target)}`);
        if (item.id) {
          try {
            await axios.post(
              `${backendUrl}/offline/whatsapp-confirmations/fail`,
              { id: item.id, error: delivery.error || 'send_failed' },
              { timeout: 10000 }
            );
          } catch (error) {
            console.log(`offline confirmation failure report skipped id=${item.id} reason=${error.message}`);
          }
        }
      }
    }
    if (sentIds.length) {
      await axios.post(`${backendUrl}/offline/whatsapp-confirmations/ack`, { ids: sentIds }, { timeout: 10000 });
      console.log(`OFFLINE_CONFIRMATIONS_SENT count=${sentIds.length}`);
      for (const sentId of sentIds) {
        console.log(`OFFLINE_CONFIRMATION_ACKED id=${sentId}`);
        console.log(`confirmation delivery result id=${sentId} sent=true acked=true`);
        console.log(`WHATSAPP_CONFIRMATION_SEND_RESULT id=${sentId} sent=true acked=true`);
      }
    }
  } catch (error) {
    console.log(`OFFLINE_CONFIRMATION_POLL_SKIPPED ${error.message}`);
  }
}

function startOfflineConfirmationPolling(sock) {
  if (!offlineConfirmationPollMs || offlineConfirmationPollMs < 1000) return;
  if (offlineConfirmationPoller) clearInterval(offlineConfirmationPoller);
  offlineConfirmationPoller = setInterval(() => pollOfflineConfirmations(sock), offlineConfirmationPollMs);
  pollOfflineConfirmations(sock);
}

function scheduleReconnect(options = {}) {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    startBaileys(options).catch((error) => {
      console.error('Baileys reconnect failed:', error.message);
      reportRuntimeStatus({ state: 'error', connected: false, last_error: `reconnect_failed: ${error.message}` });
      scheduleReconnect(options);
    });
  }, 3000);
}

function extractBackendReply(data) {
  const keys = ['reply', 'message', 'text', 'response', 'whatsapp_reply'];
  for (const key of keys) {
    const value = data && data[key];
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return '✅ PharMareen received your message.';
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
  reportRuntimeStatus({ state: 'starting', connected: false, qr_required: false, last_error: '' });
  console.log(`Backend: ${backendUrl}`);
  console.log(`Baileys session path: ${sessionPath}`);
  console.log(`Baileys log level: ${baileysLogLevel}`);
  if (allowedNumbers.size === 0 && allowedLids.size === 0) {
    console.log('SAFE MODE: no allowed direct chat numbers or LIDs configured');
  } else {
    console.log(`Safety allowlist active: ${allowedNumbers.size} number(s), ${allowedLids.size} LID(s).`);
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
    reportRuntimeStatus({
      state: connection || (qr ? 'qr_required' : 'connecting'),
      connected: connection === 'open',
      qr_required: Boolean(qr),
      last_error: connection === 'close' ? (describeDisconnect(lastDisconnect).errorMessage || 'connection_closed') : ''
    });
    if (qr) {
      console.log('\nSCAN THIS QR WITH WHATSAPP:');
      console.log('WhatsApp > Linked devices > Link a device\n');
      qrcode.generate(qr, { small: true });
    }
    if (connection === 'open') {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      reconnectTimer = null;
      console.log('Baileys bridge ready. Send a pharmacy message from an allowed direct chat.');
      startOfflineConfirmationPolling(sock);
    }
    if (connection === 'close') {
      if (offlineConfirmationPoller) clearInterval(offlineConfirmationPoller);
      offlineConfirmationPoller = null;
      const statusCode = lastDisconnect && lastDisconnect.error && lastDisconnect.error.output
        ? lastDisconnect.error.output.statusCode
        : undefined;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log(`Baileys disconnected. statusCode=${statusCode || 'unknown'} reconnect=${shouldReconnect}`);
      if (!shouldReconnect && autoResetOnLoggedOut && !sessionResetAttempted) {
        clearBaileysSession('logged out or invalid stale session');
        scheduleReconnect({ sessionResetAttempted: true });
        return;
      }
      if (shouldReconnect) scheduleReconnect({ sessionResetAttempted });
    }
  });

  sock.ev.on('contacts.update', (updates) => {
    for (const contact of updates || []) {
      indexContactIdentity(contact);
    }
  });

  sock.ev.on('messages.upsert', async ({ messages }) => {
    for (const msg of messages || []) {
      if (!msg.message || (msg.key && msg.key.fromMe)) continue;
      const identity = senderIdentityFromMessage(msg);
      const sender = identity.senderJid;
      const safety = isAllowedDirectChat(sender, identity);
      logAllowlistDecision(identity, safety);
      if (!safety.allowed) {
        console.log(
          `Ignored WhatsApp message from ${maskSender(sender)} sender_jid=${sender} sender_domain=${jidDomain(sender)} ` +
          `normalized_phone=${identity.normalizedPhone || ''} normalized_lid=${identity.normalizedLid || ''} reason=${safety.reason}`
        );
        continue;
      }
      if (safety.reason === 'test_mode_allowed_direct_chat') {
        console.log(`TEST MODE ACCEPTED DIRECT CHAT from ${maskSender(sender)} ${jidDebug(sender)}`);
      }

      const text = extractText(msg).trim();
      const messageId = msg.key.id || '';
      reportRuntimeStatus({ state: 'connected', connected: true, last_message_received: new Date().toISOString(), last_error: '' });
      console.log(`INCOMING_SENDER_JID ${maskSender(sender)} ${jidDebug(sender)}`);
      if (isImageMessage(msg)) {
        const mimeType = imageMimeType(msg);
        console.log(`PHOTO_MESSAGE_RECEIVED from ${maskSender(sender)} ${jidDebug(sender)} mime_type=${mimeType} caption_length=${text.length}`);
        try {
          const mediaBase64 = await downloadImageBase64(sock, msg);
          console.log(`PHOTO_MESSAGE_DOWNLOADED from ${maskSender(sender)} bytes_base64_length=${mediaBase64.length}`);
          const data = await sendToBackend('', sender, messageId, {
            media_base64: mediaBase64,
            media_mime_type: mimeType,
            media_caption: text
          }, identity);
          console.log(`BACKEND_REPLY_RECEIVED from ${maskSender(sender)} status=${data.status || 'unknown'} handler=${data.command_handler || 'unknown'} reason=${data.error_reason || 'none'}`);
          const reply = extractBackendReply(data);
          console.log(`EXTRACTED_REPLY_TEXT ${reply}`);
          await safeSendSelectorReply(sock, sender, data, reply);
        } catch (error) {
          const status = error.response && error.response.status ? error.response.status : 'no-status';
          console.error(`Photo bridge error for ${maskSender(sender)} status=${status}: ${error.stack || error.message}`);
          await safeSendReply(sock, sender, 'I received the photo, but could not process it right now.');
        }
        continue;
      }

      if (!text && isAudioMessage(msg)) {
        const mimeType = audioMimeType(msg);
        console.log(`VOICE_MESSAGE_RECEIVED from ${maskSender(sender)} ${jidDebug(sender)} mime_type=${mimeType}`);
        try {
          const mediaBase64 = await downloadAudioBase64(sock, msg);
          console.log(`VOICE_MESSAGE_DOWNLOADED from ${maskSender(sender)} bytes_base64_length=${mediaBase64.length}`);
          const data = await sendToBackend('', sender, messageId, {
            media_base64: mediaBase64,
            media_mime_type: mimeType,
            voice_transcribe_only: false
          }, identity);
          console.log(`BACKEND_REPLY_RECEIVED from ${maskSender(sender)} status=${data.status || 'unknown'} handler=${data.command_handler || 'unknown'} reason=${data.error_reason || 'none'}`);
          const reply = extractBackendReply(data);
          console.log(`EXTRACTED_REPLY_TEXT ${reply}`);
          await safeSendSelectorReply(sock, sender, data, reply);
        } catch (error) {
          const status = error.response && error.response.status ? error.response.status : 'no-status';
          console.error(`Voice bridge error for ${maskSender(sender)} status=${status}: ${error.stack || error.message}`);
          await safeSendReply(sock, sender, 'I received the voice note, but could not transcribe it right now.');
        }
        continue;
      }

      if (!text) {
        console.log(`Allowed direct message from ${maskSender(sender)} had no text.`);
        await safeSendReply(sock, sender, 'Please send text for now, like: Panadol 2');
        continue;
      }

      console.log(`Incoming allowed direct message from ${maskSender(sender)} length=${text.length}`);
      console.log(`INCOMING_MESSAGE_TEXT ${text}`);
      try {
        const data = await sendToBackend(text, sender, messageId, {}, identity);
        console.log(`BACKEND_REPLY_RECEIVED from ${maskSender(sender)} status=${data.status || 'unknown'} handler=${data.command_handler || 'unknown'} reason=${data.error_reason || 'none'}`);
        if (data.status === 'ignored') {
          console.log(`Backend ignored message from ${maskSender(sender)} reason=${data.error_reason || 'unknown'}`);
          continue;
        }
        const reply = extractBackendReply(data);
        console.log(`EXTRACTED_REPLY_TEXT ${reply}`);
        await safeSendSelectorReply(sock, sender, data, reply);
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
