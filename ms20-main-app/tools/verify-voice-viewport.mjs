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
