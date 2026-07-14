import fs from "node:fs";
import { findBarcodeTestFixture } from "../src/data/barcodeTestFixtures.js";

const manifest = JSON.parse(fs.readFileSync(new URL("../fixtures/barcode-unregistered.json", import.meta.url), "utf8"));
const png = fs.readFileSync(new URL("../fixtures/barcode-unregistered.png", import.meta.url));
const digits = manifest.barcode.split("").map(Number);
const check = (10 - (digits.slice(0, 12).reduce((sum, digit, index) => sum + digit * (index % 2 ? 3 : 1), 0) % 10)) % 10;

if (manifest.format !== "EAN-13" || digits.length !== 13 || check !== digits[12]) throw new Error("Unregistered fixture must be a valid readable EAN-13");
if (findBarcodeTestFixture(manifest.barcode)) throw new Error("Unregistered fixture must not have a controlled recognition mapping");
if (["6161109876546", "6161109876553"].includes(manifest.barcode)) throw new Error("Unregistered fixture must not reuse a saved live-test barcode");
if (png.length < 10000 || png.subarray(1, 4).toString() !== "PNG") throw new Error("Unregistered scannable PNG artifact is missing");
console.log("Unregistered barcode fixture verification passed: readable valid EAN-13, no registry mapping, no known fixture collision, and PNG artifact.");
