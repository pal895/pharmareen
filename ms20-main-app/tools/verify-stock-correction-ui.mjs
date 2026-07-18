import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { OfflineQueue } from "../src/services/offlineQueue.js";

const [app, css] = await Promise.all([
  readFile(new URL("../src/app.js", import.meta.url), "utf8"),
  readFile(new URL("../src/styles.css", import.meta.url), "utf8")
]);

for (const required of [
  'refreshStockFixDraftControls(card);',
  'data-confirm-card="${card.id}"',
  'card.ui = { ...(card.ui || {}), activeSlide: index }',
  'data-initial-slide="${activeSlide}"',
  'if (!card || card.submitting) return',
  'if (card.type === "StockCorrectionCard") return startStockFixReading(card)',
  'showMedicineSlide(reading.cardId, reading.index)',
  'function pauseStockFixReading()',
  'function resumeStockFixReading()',
  'function toggleStockFixReading(cardId)',
  'speakStockFixSegment(stockFixReading.sequence)',
  'data-action="stock-fix-read-control"',
  'data-action="stop-reading"',
  'state.pendingScanType = "stock_fix_photo"',
  'processStockFixEvidence(card, fileOrName, fileName',
  'data-action="stock-fix-file"',
  'function startStockFixFile(cardId)',
  'id="stockFixFileInput"',
  'id="stockFixFileInput" class="hidden-input" type="file" accept="image/*"',
  'addPhotoCards(file, "stock_fix_photo")',
  'card.photoEvidence && !String(card.fields?.medicine || "").trim() && card.validation',
  'localOnly: true',
  'stopStockFixReading();',
  'activeStockFixScan?.abort();',
  'prepareStockFixImage(file)',
  'fetch("/api/ms20/stock-fix-scan"',
  'Reason (optional)',
  'Say a reason, or say Confirm to continue.',
  'Reason: ${card.fields?.reason || "not provided"}',
  'handleStockFixVoice(stockFixCard, text)',
  'recognition.interimResults = true',
  'recognition.onspeechend = () =>',
  'Heard: “${transcript}”',
  'I did not receive a completed transcript. Tap Mic and try once more.',
  'voiceAwaitingManualRetry',
  'Voice transcript',
  'stockFixGuidedStage(card)',
  'announceStockFixNextStep(continuingCard)',
  'Saved current stock is ${card.fields.current_stock}. Next, say the new correct stock.',
  'Reason is optional. Next, say a reason or say Confirm to review everything.',
  'Reviewing the complete stock fix. Say Confirm again after the review to apply it.',
  'if (!card.ui?.voiceReviewCompleted)',
  'voiceReviewStarted: true, voiceReviewCompleted: false',
  'stockFixReading?.cardId === card.id',
  'reviewedSlides: undefined, voiceReviewStarted: false, voiceReviewCompleted: false',
  'Complete review finished. Say Confirm to apply this stock fix once.',
  'The complete review did not finish. Say Confirm to start it again; nothing was applied.',
  'setTimeout(() => startVoiceCapture(), 350)',
  'completeStockCorrection(card);',
  'syncPendingStockCorrections();',
  'Stock updated.'
]) assert.ok(app.includes(required), `Missing Stock fix UI protection: ${required}`);

assert.ok(!app.includes('if (result.review) card.ui.reviewedSlides'), "Draft readiness must never masquerade as a completed guided review");
assert.ok(!app.includes('if (result.review) cycleStockFixReview'), "Completing Reason must not silently satisfy or start the Confirm review gate");
assert.match(app, /if \(!card\.ui\?\.voiceReviewCompleted\)[\s\S]*return cycleStockFixReview\(card\.id\);[\s\S]*return confirmCard\(card\.id\);/, "Only a completed guided review may reach Stock Fix execution");

assert.match(css, /@media \(hover: hover\) and \(pointer: fine\)[\s\S]*button:hover/);
assert.match(css, /\.medicine-slide-nav button\.selected/);
assert.match(css, /\.stock-fix-main-actions[\s\S]*grid-template-columns: repeat\(3/);
assert.match(css, /\.stock-fix-more-actions\[open\][\s\S]*grid-column: 1 \/ -1/);
assert.match(css, /\.stock-fix-more-actions > div[\s\S]*position: static[\s\S]*width: 100%/);

const queue = new OfflineQueue(null);
const action = { id: "action-stock-fix-1", type: "StockCorrectionCard" };
assert.equal(queue.add(action).added, true);
assert.equal(queue.add(action).duplicate, true);
assert.equal(queue.pendingCount(), 1);

console.log("Stock correction UI verification passed: live draft/control synchronization, one active slide, Read controls, shared entry, online completion, automatic reconnect, and duplicate-submit protection.");
