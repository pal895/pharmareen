import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createVoiceViewportAnchor, restoreVoiceViewportAnchor, settleVoiceViewportAnchor } from "../src/services/voiceViewportAnchor.js";

globalThis.CSS = { escape: (value) => String(value).replaceAll('"', '\\"') };
const rootPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const appSource = fs.readFileSync(path.join(rootPath, "src/app.js"), "utf8");
const cssSource = fs.readFileSync(path.join(rootPath, "src/styles.css"), "utf8");

assert.match(appSource, /data-action="catalog-edit-field-voice"/, "every long-card field exposes a reachable inline Mic");
assert.match(appSource, /selectCatalogVoiceField\(dataset\.cardId, dataset\.field\);\s*startCatalogEditVoice\(dataset\.cardId\);/, "inline Mic selects the exact target before reusing shared capture");
assert.match(cssSource, /\.catalog-edit-field-heading[\s\S]*justify-content: space-between/, "field and Mic remain colocated in long cards");
assert.match(
  appSource,
  /if \(activeVoiceViewportAnchor && refreshContextualFieldVoiceDom\(\)\) return;\s*const existingPrintFrame/,
  "contextual field voice takes render ownership before global DOM replacement"
);
assert.match(
  appSource,
  /function refreshContextualFieldVoiceDom\(\)[\s\S]*target\.value = nextValue[\s\S]*refreshCatalogEditReviewDom\(card, draft\)[\s\S]*restoreVoiceViewportAnchor/,
  "the active field, validation review and viewport update in place throughout transcription"
);
assert.match(
  appSource,
  /if \(activeVoiceViewportAnchor && refreshContextualFieldVoiceDom\(\)\) return;[\s\S]*else \{\s*scrollChatToBottom\(\);/,
  "ordinary chat-bottom scrolling is unreachable while the contextual session owns the viewport"
);
assert.match(
  appSource,
  /if \(action === "start-voice"\) startVoiceCapture\(\);/,
  "the normal composer Mic remains on the shared capture path outside contextual sessions"
);
assert.match(appSource, /preserveInlineCardViewport\(actionElement\)/, "every card action captures the shared viewport anchor before mutation");
assert.match(appSource, /else if \(activeCardViewportAnchor\)[\s\S]*settleVoiceViewportAnchor[\s\S]*else \{\s*scrollChatToBottom\(\);/, "inline card rerenders restore the card instead of scrolling to chat bottom");
assert.match(appSource, /function addFeed[\s\S]*activeCardViewportAnchor = null/, "a genuine new message releases inline viewport ownership");
assert.match(appSource, /input\.addEventListener\("focus", \(\) => preserveInlineCardViewport\(input\)\)/, "manual field editing also owns the shared viewport");
assert.match(cssSource, /\.sale-edit-field \.catalog-edit-field-heading button[\s\S]*width: 44px/, "Sale correction uses a compact but safe inline Mic target");
assert.match(appSource, /if \(card\.type === "SaleCard"\)[\s\S]*refreshProductionSaleCardControls\(card\)[\s\S]*restoreVoiceViewportAnchor[\s\S]*return true;/, "Sales field voice updates in place without remounting its carousel");
assert.match(appSource, /startSaleEditFieldVoice[\s\S]*activeVoiceViewportAnchor = createVoiceViewportAnchor[\s\S]*data-field/, "Sales voice owns the exact selected field for its complete lifecycle");
assert.match(appSource, /PRODUCTION_SALE_REFRESH_FIELDS[\s\S]*?"supplier"[\s\S]*?"barcode"[\s\S]*?"batch"[\s\S]*?"expiry"[\s\S]*?"aliases"[\s\S]*?"note"/, "Slide 3 fields share the in-place refresh registry.");
assert.match(appSource, /querySelectorAll\(`input\[data-card-id=.*select\[data-card-id=/, "In-place voice refresh targets editable controls instead of Mic buttons.");
assert.doesNotMatch(appSource, /startSaleEditFieldVoice[\s\S]*requestAnimationFrame\(\(\) => root\.querySelector[\s\S]*?\.focus/, "Sales voice never schedules a competing focus jump");
assert.match(appSource, /if \(!settleVoiceViewportAnchor[\s\S]*scrollChatToBottom\(\)/, "removing a card falls back to the recent conversation end rather than scrollTop zero");

const oldContainer = {
  id: "chatBody",
  dataset: {},
  className: "chat-body",
  scrollTop: 640,
  scrollLeft: 0,
  parentElement: null
};
const oldTarget = {
  parentElement: oldContainer,
  selectionStart: 3,
  selectionEnd: 3,
  getBoundingClientRect: () => ({ top: 180 })
};
const view = {
  document: { body: {} },
  scrollX: 0,
  scrollY: 24,
  getComputedStyle: (element) => element === oldContainer ? { overflowY: "auto" } : {},
  scrollTo() {},
  scrollBy() {}
};
const selector = '[data-catalog-edit-field="aliases"][data-card-id="catalog-1"]';
const anchor = createVoiceViewportAnchor({ querySelector: (query) => query === selector ? oldTarget : null }, {
  cardId: "catalog-1",
  field: "aliases"
}, view);

assert.equal(anchor.field, "aliases", "the exact active voice field is retained");
assert.equal(anchor.scrollPositions[0].top, 640, "the nearest scroll container is captured");
assert.equal(anchor.top, 180, "the field viewport position is captured");

const cardSelector = '.card-message[data-card-id="sale-1"]';
const cardTarget = { parentElement: oldContainer, getBoundingClientRect: () => ({ top: 92 }) };
const cardAnchor = createVoiceViewportAnchor({ querySelector: (query) => query === cardSelector ? cardTarget : null }, {
  cardId: "sale-1",
  selector: cardSelector
}, view);
assert.equal(cardAnchor.top, 92, "the same anchor service supports whole-card inline interactions");
assert.equal(cardAnchor.scrollPositions[0].top, 640, "whole-card actions preserve the chat scroll container");

let focused = false;
let caret = null;
let viewportCorrection = 0;
const newContainer = { ...oldContainer, scrollTop: 0 };
const newTarget = {
  getBoundingClientRect: () => ({ top: 205 }),
  focus: ({ preventScroll }) => { focused = preventScroll; },
  setSelectionRange: (start, end) => { caret = [start, end]; }
};
const newRoot = {
  querySelector(query) {
    if (query === selector) return newTarget;
    if (query === "#chatBody") return newContainer;
    return null;
  }
};
const restored = restoreVoiceViewportAnchor(newRoot, anchor, {
  scrollTo() {},
  scrollBy: (_x, y) => { viewportCorrection = y; }
});

assert.equal(restored, true, "the anchor restores after a rerender");
assert.equal(newContainer.scrollTop, 640, "rerendering does not move the nearest scroll container");
assert.equal(focused, true, "focus is restored without browser-driven scrolling");
assert.deepEqual(caret, [3, 3], "caret position is restored");
assert.equal(viewportCorrection, 25, "the field returns to its prior viewport coordinate");
focused = false;
caret = null;
restoreVoiceViewportAnchor(newRoot, anchor, {
  scrollTo() {},
  scrollBy() {}
}, { restoreFocus: false });
assert.equal(focused, false, "listening preserves the anchor without reopening the mobile keyboard");
assert.deepEqual(caret, [3, 3], "keyboard dismissal retains the selected field caret without forcing focus");
assert.equal(restoreVoiceViewportAnchor({ querySelector: () => null }, anchor, view), false, "cleanup is safe after navigation");

const scheduledFrames = [];
newContainer.scrollTop = 0;
const settlingView = {
  scrollTo() {},
  scrollBy() {},
  requestAnimationFrame(callback) {
    scheduledFrames.push(callback);
  }
};
assert.equal(
  settleVoiceViewportAnchor(newRoot, anchor, settlingView, { restoreFocus: false }),
  true,
  "the rebuilt scroll container is restored immediately"
);
assert.equal(newContainer.scrollTop, 640, "the first restoration happens before the browser can paint the rebuilt chat");
newContainer.scrollTop = 0;
scheduledFrames.shift()();
assert.equal(newContainer.scrollTop, 640, "the anchor survives the first mobile layout frame");
newContainer.scrollTop = 0;
scheduledFrames.shift()();
assert.equal(newContainer.scrollTop, 640, "the anchor survives the settled mobile layout frame");

console.log("Shared editable-card voice viewport verification passed.");
