import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  buildTransactionNotification,
  mergeNotifications,
  notificationToCard,
} from "../src/services/notificationCenter.js";

const transaction = {
  id: "sale-payment-failure-fixture",
  saleLabel: "Sale 7",
  status: "failed",
  amount: 240,
  metadata: { medicine: "Amoxicillin", quantity: 2, stockApplied: false },
};
const now = new Date("2026-07-29T10:00:00.000Z");

const failed = buildTransactionNotification({ transaction, status: "failed", now });
assert.equal(failed.id, "payment-sale-payment-failure-fixture-failed");
assert.equal(failed.title, "Sale 7 payment failed");
assert.match(failed.message, /Stock and paid records were not changed\./);
assert.equal(failed.actionTarget, "payment:sale-payment-failure-fixture");
assert.equal(failed.origin, "transaction");
assert.equal(failed.aiUsed, false);

const failedCard = notificationToCard(failed);
assert.deepEqual(failedCard.notificationAction, {
  label: "Review payment",
  targetCardId: "payment:sale-payment-failure-fixture",
});

const preservedAfterProjection = mergeNotifications([failed], []);
assert.equal(preservedAfterProjection.length, 1, "A transaction alert must survive deterministic notification rebuild.");
assert.equal(preservedAfterProjection[0].id, failed.id);

const repeated = buildTransactionNotification({ transaction, status: "failed", now: new Date("2026-07-29T10:01:00.000Z") });
const deduplicated = mergeNotifications([failed], [repeated]);
assert.equal(deduplicated.length, 1, "Repeating the same terminal event must not duplicate the alert.");
assert.equal(deduplicated[0].createdAt, failed.createdAt, "An unchanged alert must preserve its original timestamp.");

const cancelled = buildTransactionNotification({
  transaction: { ...transaction, id: "sale-payment-cancel-fixture", saleLabel: "Sale 8" },
  status: "cancelled",
  now,
});
assert.equal(cancelled.title, "Sale 8 payment cancelled");
assert.equal(cancelled.actionTarget, "payment:sale-payment-cancel-fixture");

assert.throws(() => buildTransactionNotification({ transaction, status: "confirmed", now }), /failed or cancelled/);

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const appSource = fs.readFileSync(path.join(root, "src", "app.js"), "utf8");
assert.ok(appSource.includes('startsWith("payment:")'), "Review payment must route to the Payment Queue.");
const failureBranch = appSource.match(/else if \(result\.updated && \["failed", "cancelled"\][\s\S]*?\n  }\n  state\.ui\.screen/)?.[0] || "";
assert.ok(failureBranch.includes("addTransactionNotification"), "Terminal failure must create the durable notification.");
assert.ok(!failureBranch.includes("addFeed("), "Terminal failure must not add operational chat noise.");

console.log("PAYMENT_FAILURE_NOTIFICATION_OK durable=1 action=payment_queue stock_paid_unchanged=asserted_by_tce chat_noise=0");
