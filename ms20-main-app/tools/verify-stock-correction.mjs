import assert from "node:assert/strict";
import { applyStockCorrectionVoice, PharmacyPronunciationMemory, reviewStockCorrection, stockCorrectionGuidance, stockCorrectionSummary, trustedCatalogStock } from "../src/services/stockCorrectionPolicy.js";
import { executeStockCorrection, replayPendingStockCorrections } from "../src/services/stockCorrectionExecution.js";
import { OfflineQueue } from "../src/services/offlineQueue.js";
import { SyncAdapter } from "../src/services/syncAdapter.js";
import fs from "node:fs";
import crypto from "node:crypto";
import { findStockFixPhotoTestFixture, StockFixPhotoTestFixtures } from "../src/data/stockFixPhotoTestFixtures.js";

const catalog = [{ name: "Losartan", stock: 37, aliases: ["Losartan 50"] }];
assert.equal(trustedCatalogStock({ name: "Cefixime", stockLeft: 23 }), 23);
assert.equal(reviewStockCorrection({ medicine: "Cefixime", current_stock: 23, correct_stock: 22, reason: "Physical count" }, [{ name: "Cefixime", stockLeft: 23 }]).ok, true);

assert.equal(reviewStockCorrection({ medicine: "", current_stock: 37, correct_stock: 36, reason: "Count" }, catalog).ok, false);
assert.equal(reviewStockCorrection({ medicine: "Losartan", current_stock: 38, correct_stock: 36, reason: "Count" }, catalog).ok, false);
assert.equal(reviewStockCorrection({ medicine: "Losartan", current_stock: 37, correct_stock: -1, reason: "Count" }, catalog).ok, false);
const withoutReason = reviewStockCorrection({ medicine: "Losartan", current_stock: 37, correct_stock: 36, reason: "" }, catalog);
assert.equal(withoutReason.ok, true, "rush-hour Stock Fix must allow an omitted reason");
assert.equal(withoutReason.fields.reason, "");
assert.equal(reviewStockCorrection({ medicine: "Losartan", current_stock: 37, correct_stock: 37, reason: "Count" }, catalog).ok, false);

const approved = reviewStockCorrection({ medicine: "losartan 50", current_stock: "37", correct_stock: "36", reason: "Physical count" }, catalog);
assert.equal(approved.ok, true);
assert.deepEqual(approved.fields, {
  medicine: "Losartan",
  current_stock: 37,
  correct_stock: 36,
  reason: "Physical count",
  adjustment: -1,
  mutation_status: "ready"
});

assert.equal(stockCorrectionGuidance(approved.fields, catalog).ready, true);
assert.equal(stockCorrectionGuidance(approved.fields, catalog).message, "Ready. Check the details, then tap Confirm. If you are online, saved stock updates now.");
assert.match(stockCorrectionSummary(approved.fields), /Medicine: Losartan\. Current stock: 37\. Correct stock: 36\. Reason: Physical count\./);
assert.match(stockCorrectionSummary(withoutReason.fields), /Reason: not provided\./);

let voice = applyStockCorrectionVoice({ medicine: "", current_stock: "", correct_stock: "", reason: "", active_slide: 0 }, "Losartan", catalog);
assert.equal(voice.fields.medicine, "Losartan");
assert.equal(voice.fields.current_stock, 37);
assert.equal(voice.slide, 1);
voice = applyStockCorrectionVoice({ ...voice.fields, active_slide: 1 }, "36", catalog);
assert.equal(voice.fields.correct_stock, "36");
voice = applyStockCorrectionVoice({ ...voice.fields, active_slide: 2 }, "Physical count", catalog);
assert.equal(voice.fields.reason, "Physical count");
assert.equal(voice.review, true);
assert.equal(applyStockCorrectionVoice(voice.fields, "Confirm", catalog).intent, "confirm");
assert.equal(applyStockCorrectionVoice(voice.fields, "Cancel", catalog).intent, "cancel");
assert.equal(applyStockCorrectionVoice(voice.fields, "Change correct stock", catalog).slide, 2);
assert.equal(applyStockCorrectionVoice(voice.fields, "Change stock", catalog).slide, 1);

const coAmoxiclavCatalog = [{ name: "Co-Amoxiclav", stockLeft: 24 }];
let guided = applyStockCorrectionVoice({ medicine: "", current_stock: "", correct_stock: "", reason: "", active_slide: 0 }, "medicine Co-Amoxiclav", coAmoxiclavCatalog);
assert.equal(guided.fields.medicine, "Co-Amoxiclav");
assert.equal(guided.fields.current_stock, 24);
guided = applyStockCorrectionVoice({ ...guided.fields, active_slide: 1 }, "current stock is 24 new stock is 23", coAmoxiclavCatalog);
assert.equal(guided.fields.current_stock, "24");
assert.equal(guided.fields.correct_stock, "23");
guided = applyStockCorrectionVoice({ ...guided.fields, active_slide: 2 }, "no reason", coAmoxiclavCatalog);
assert.equal(guided.fields.reason, "");
assert.equal(guided.review, true);
assert.equal(applyStockCorrectionVoice({ medicine: "Co-Amoxiclav", current_stock: 24, correct_stock: "", reason: "", active_slide: 1 }, "new stock 23", coAmoxiclavCatalog).fields.correct_stock, "23");

const ambiguousCatalog = [{ name: "Losartan", stock: 37, aliases: ["lora"] }, { name: "Loratadine", stock: 12, aliases: ["lora"] }];
const uncertain = applyStockCorrectionVoice({}, "lora", ambiguousCatalog);
assert.ok(["disambiguate", "retry"].includes(uncertain.intent));

const pharmacyA = new PharmacyPronunciationMemory("pharmacy-a");
const pharmacyB = new PharmacyPronunciationMemory("pharmacy-b");
pharmacyA.remember("loss a ton", "Losartan");
assert.equal(pharmacyA.resolve("loss a ton"), "Losartan");
assert.equal(pharmacyB.resolve("loss a ton"), "");
pharmacyA.forget("loss a ton");
assert.equal(pharmacyA.resolve("loss a ton"), "");

const draft = { medicine: "Losartan", current_stock: "37", correct_stock: "36", reason: "Physical count" };
const acrossSlides = structuredClone(draft);
for (const activeSlide of [0, 1, 2, 0]) acrossSlides.active_slide = activeSlide;
delete acrossSlides.active_slide;
assert.deepEqual(acrossSlides, draft);

class MemoryStorage {
  constructor() { this.values = new Map(); }
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
}

const executionStorage = new MemoryStorage();
const executionQueue = new OfflineQueue(null);
let savedCatalog = [{ name: "Losartan", stockLeft: 37 }];
let persistenceCalls = 0;
const action = { id: "stock-fix-online-1", type: "StockCorrectionCard", fields: approved.fields };
const execute = (overrides = {}) => executeStockCorrection({
  action,
  catalog: savedCatalog,
  online: true,
  queue: executionQueue,
  storage: executionStorage,
  persistCatalog: (items) => { persistenceCalls += 1; savedCatalog = items; return true; },
  replaceCatalog: (items) => { savedCatalog = items; },
  ...overrides
});
assert.equal(execute().status, "completed");
assert.equal(savedCatalog[0].stockLeft, 36);
assert.equal(executionQueue.pendingCount(), 0);
assert.equal(execute().duplicate, true);
assert.equal(persistenceCalls, 1);

const optionalReasonStorage = new MemoryStorage();
const optionalReasonQueue = new OfflineQueue(null);
let optionalReasonCatalog = [{ name: "Metronidazole", stockLeft: 35 }];
const optionalReasonAction = {
  id: "stock-fix-optional-reason-1",
  type: "StockCorrectionCard",
  fields: reviewStockCorrection({ medicine: "Metronidazole", current_stock: 35, correct_stock: 34, reason: "" }, optionalReasonCatalog).fields
};
const optionalReasonResult = executeStockCorrection({
  action: optionalReasonAction,
  catalog: optionalReasonCatalog,
  online: true,
  queue: optionalReasonQueue,
  storage: optionalReasonStorage,
  persistCatalog: (items) => { optionalReasonCatalog = items; return true; },
  replaceCatalog: (items) => { optionalReasonCatalog = items; }
});
assert.equal(optionalReasonResult.status, "completed");
assert.equal(optionalReasonCatalog[0].stockLeft, 34);
assert.equal(JSON.parse(optionalReasonStorage.getItem("ms20-main-app:stock-fix-audit"))[0].reason, "", "audit must preserve an omitted reason as blank");

const offlineStorage = new MemoryStorage();
const offlineQueue = new OfflineQueue(null);
let offlineCatalog = [{ name: "Cefixime", stockLeft: 23 }];
const offlineAction = {
  id: "stock-fix-offline-1",
  type: "StockCorrectionCard",
  fields: reviewStockCorrection({ medicine: "Cefixime", current_stock: 23, correct_stock: 22, reason: "Count" }, offlineCatalog).fields
};
const offlineResult = executeStockCorrection({
  action: offlineAction,
  catalog: offlineCatalog,
  online: false,
  queue: offlineQueue,
  storage: offlineStorage,
  persistCatalog: () => { throw new Error("must not write while offline"); },
  replaceCatalog: () => { throw new Error("must not mutate while offline"); }
});
assert.equal(offlineResult.status, "pending");
assert.equal(offlineCatalog[0].stockLeft, 23);
assert.equal(offlineQueue.pendingCount(), 1);
assert.equal(executeStockCorrection({ ...offlineResult, action: offlineAction, catalog: offlineCatalog, online: false, queue: offlineQueue, storage: offlineStorage }).duplicate, true);

let replayWrites = 0;
const replay = replayPendingStockCorrections({
  getCatalog: () => offlineCatalog,
  online: true,
  queue: offlineQueue,
  storage: offlineStorage,
  persistCatalog: (items) => { replayWrites += 1; offlineCatalog = items; return true; },
  replaceCatalog: (items) => { offlineCatalog = items; }
});
assert.equal(replay[0].status, "completed");
assert.equal(offlineCatalog[0].stockLeft, 22);
assert.equal(offlineQueue.pendingCount(), 0);
assert.equal(replayWrites, 1);
assert.equal(replayPendingStockCorrections({ getCatalog: () => offlineCatalog, online: true, queue: offlineQueue, storage: offlineStorage }).length, 0);

const protectedQueue = new OfflineQueue(null);
protectedQueue.add({ id: "stock-fix-protected", type: "StockCorrectionCard", fields: offlineAction.fields });
const genericSync = new SyncAdapter({ queue: protectedQueue, cloudGateway: { saveAction: async () => ({ saved: true }) } });
await genericSync.syncPending({ excludeTypes: ["StockCorrectionCard"] });
assert.equal(protectedQueue.pendingCount(), 1);

const photoManifest = JSON.parse(fs.readFileSync(new URL("../fixtures/stock-fix-prednisolone-5mg.json", import.meta.url), "utf8"));
const photoPng = fs.readFileSync(new URL("../fixtures/stock-fix-prednisolone-5mg.png", import.meta.url));
const photoTransport = fs.readFileSync(new URL("../fixtures/stock-fix-prednisolone-5mg.ms20image", import.meta.url));
const photoHash = crypto.createHash("sha256").update(photoPng).digest("hex");
const photoFixture = findStockFixPhotoTestFixture({ fileName: photoManifest.fileName });
assert.equal(StockFixPhotoTestFixtures.length, 1);
assert.equal(photoHash, photoManifest.sha256);
assert.equal(crypto.createHash("sha256").update(photoTransport).digest("hex"), photoHash);
assert.equal(photoFixture.sha256, photoHash);
assert.equal(photoFixture.item.name, "Prednisolone");
assert.equal(photoFixture.item.stock, "");
assert.equal(findStockFixPhotoTestFixture({ sha256: photoHash }), photoFixture);
assert.equal(findStockFixPhotoTestFixture({ perceptualHash: photoFixture.perceptualHash, aspectRatio: 0.6667 }), photoFixture);
assert.equal(findStockFixPhotoTestFixture({ perceptualHash: "0000000000000000", aspectRatio: 0.6667 }), null);
const photoCatalog = [{ name: "Prednisolone", strength: "5 mg", stockLeft: 24 }];
assert.equal(reviewStockCorrection({ medicine: photoFixture.item.name, current_stock: 24, correct_stock: 23, reason: "Picture count" }, photoCatalog).ok, true);

console.log("Stock correction workflow verification passed: shared validation and entry, immediate online apply, offline single-queue fallback, automatic idempotent replay, and duplicate-confirm protection.");
