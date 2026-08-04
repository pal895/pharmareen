import assert from "node:assert/strict";
import { OfflineQueue } from "../src/services/offlineQueue.js";
import { OfflineSyncGateway, actionToOfflineEntry } from "../src/services/offlineSyncGateway.js";
import { SyncAdapter } from "../src/services/syncAdapter.js";

const sale = { id: "action-sale-1", type: "SaleCard", fields: { medicine: "Ibuprofen", quantity: 2, unit: "tablet", payment: "cash" } };
assert.deepEqual(actionToOfflineEntry(sale, { id: "pharmacy-1" }), {
  id: "action-sale-1", action_id: "action-sale-1", pharmacy_id: "pharmacy-1", source: "ms20_main_app", created_at: "", retry_count: 0,
  action: "sale", type: "sale", drug_name: "Ibuprofen", quantity: 2, base_quantity: "", unit: "tablet", payment_method: "cash"
});

const storage = { value: "[]", getItem() { return this.value; }, setItem(_key, value) { this.value = value; } };
const queue = new OfflineQueue(storage);
queue.add(sale);
const calls = [];
const gateway = new OfflineSyncGateway({
  pharmacy: { id: "pharmacy-1" },
  backendGateway: { async requestJson(path, options) { calls.push({ path, options }); return { ok: true, data: { synced: [{ id: "action-sale-1", status: "synced", result_summary: "Saved once." }], failed: [], pending: [] } }; } }
});
const adapter = new SyncAdapter({ queue, cloudGateway: gateway });
const result = await adapter.syncOne("action-sale-1");
assert.equal(result.synced, true);
assert.equal(queue.list()[0].status, "synced");
assert.equal(calls.length, 1);
assert.equal(calls[0].path, "/offline/sync");
assert.equal(calls[0].options.body.entries.length, 1, "one review must send one item only");

const testGateway = new OfflineSyncGateway({
  pharmacy: { id: "pharmacy-1" },
  backendGateway: { async requestJson(path, options) { return { ok: true, data: { status: "saved", action_id: options.body.action_id, message: "Safe test saved." } }; } }
});
const connectionTest = await testGateway.testConnection("ms20-connection-test-001");
assert.equal(connectionTest.status, "saved");

const failingStorage = { value: "[]", getItem() { return this.value; }, setItem(_key, value) { this.value = value; } };
const failingQueue = new OfflineQueue(failingStorage);
failingQueue.add({ ...sale, id: "action-sale-2" });
const failingAdapter = new SyncAdapter({ queue: failingQueue, cloudGateway: { async saveAction() { throw new Error("Sheets unavailable"); } } });
const failed = await failingAdapter.syncOne("action-sale-2");
assert.equal(failed.synced, false);
assert.equal(failingQueue.list()[0].status, "pending", "failed item must remain safely queued");

console.log("Offline sync gateway verification passed.");
