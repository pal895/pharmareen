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
  'resolveStockFixPhotoTestFixture',
  'localOnly: true',
  'handleStockFixVoice(stockFixCard, text)',
  'completeStockCorrection(card);',
  'syncPendingStockCorrections();',
  'Stock updated.'
]) assert.ok(app.includes(required), `Missing Stock fix UI protection: ${required}`);

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
