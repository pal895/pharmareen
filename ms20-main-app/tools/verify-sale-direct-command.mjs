import assert from "node:assert/strict";
import fs from "node:fs";
import { parseSaleDirectCommand } from "../src/services/saleDirectCommand.js";

assert.deepEqual(parseSaleDirectCommand("open sale 1"), { action: "open", target: "number", saleNumber: 1 });
assert.deepEqual(parseSaleDirectCommand("  OPEN   SALE 42 "), { action: "open", target: "number", saleNumber: 42 });
assert.equal(parseSaleDirectCommand("open sale 0"), null);
assert.equal(parseSaleDirectCommand("open 1"), null);
assert.equal(parseSaleDirectCommand("open last sale"), null);

const app = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
assert.match(app, /parseSaleDirectCommand\(trimmed\)/);
assert.match(app, /direct\.action === "open"/);
assert.match(app, /openCompletedSale\(\{ saleNumber: direct\.saleNumber \}\)/);
assert.match(app, /No completed Sale/);

console.log("SALE_DIRECT_COMMAND_OK case=open-by-number route=shared-sale-detail mutation=none");
