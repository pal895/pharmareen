import fs from "node:fs";
import { BarcodeTestFixtures, findBarcodeTestFixture } from "../src/data/barcodeTestFixtures.js";
import { SourceBrain } from "../src/services/brainAdapters.js";

const manifestUrls = [
  new URL("../fixtures/barcode-losartan-50mg.json", import.meta.url),
  new URL("../fixtures/barcode-loperamide-2mg.json", import.meta.url)
];
const knownCatalog = ["Cefixime", "Ceftriaxone", "Salbutamol", "Metformin", "Omeprazole", "Diclofenac", "Hydrocortisone", "Azithromycin", "Zinc", "Acyclovir", "Clotrimazole", "Doxycycline", "Chloramphenicol", "Albendazole", "Amlodipine", "Fluconazole", "Betamethasone", "Amitriptyline", "Artemether Lumefantrine", "Ciprofloxacin", "Loratadine", "Aspirin", "Atenolol", "Erythromycin", "Folic Acid", "Losartan"];

if (BarcodeTestFixtures.length !== manifestUrls.length) throw new Error("Fixture registry and manifests must remain isolated and synchronized");
for (const manifestUrl of manifestUrls) {
  const manifest = JSON.parse(fs.readFileSync(manifestUrl, "utf8"));
  const fixtureId = manifest.fixtureId || manifest.fixture_id;
  const png = fs.readFileSync(new URL(`../fixtures/${fixtureId}.png`, import.meta.url));
  const fixture = findBarcodeTestFixture(manifest.barcode);
  const source = new SourceBrain().lookupMedicine(manifest.medicine);
  const digits = manifest.barcode.split("").map(Number);
  const check = (10 - (digits.slice(0, 12).reduce((sum, digit, index) => sum + digit * (index % 2 ? 3 : 1), 0) % 10)) % 10;
  if (manifest.format !== "EAN-13" || digits.length !== 13 || check !== digits[12]) throw new Error(`${fixtureId} must be valid EAN-13`);
  if (!fixture || fixture.fixtureId !== fixtureId) throw new Error(`${fixtureId} registry lookup failed`);
  if (source.status !== "matched" || source.name !== manifest.medicine) throw new Error(`${fixtureId} must resolve through Source Brain`);
  if (fixtureId !== "barcode-losartan-50mg" && knownCatalog.includes(manifest.medicine)) throw new Error(`${fixtureId} must not duplicate the known 26-item live catalog`);
  if (fixtureId === "barcode-losartan-50mg" && (!knownCatalog.includes(manifest.medicine) || !manifest.catalog_status?.includes("Existing canonical medicine"))) {
    throw new Error("Losartan live fixture must target the existing canonical catalog medicine");
  }
  const expected = { ...manifest, stock: manifest.stock ?? manifest.initial_stock, cost_price: manifest.cost_price ?? manifest.buying_price };
  for (const field of ["strength", "barcode", "expiry", "stock", "cost_price", "selling_price", "batch"]) {
    if (String(fixture[field]) !== String(expected[field])) throw new Error(`${fixtureId} ${field} drifted`);
  }
  if (png.length < 10000 || png.subarray(1, 4).toString() !== "PNG") throw new Error(`${fixtureId} PNG artifact is missing or invalid`);
}
console.log("Barcode fixture verification passed: valid EAN-13 assets, existing-catalog Losartan targeting, isolated mappings, and PNG artifacts.");
