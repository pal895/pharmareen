import fs from "node:fs";
import { BarcodeTestFixtures, findBarcodeTestFixture } from "../src/data/barcodeTestFixtures.js";
import { SourceBrain } from "../src/services/brainAdapters.js";

const manifest = JSON.parse(fs.readFileSync(new URL("../fixtures/barcode-losartan-50mg.json", import.meta.url), "utf8"));
const png = fs.readFileSync(new URL("../fixtures/barcode-losartan-50mg.png", import.meta.url));
const fixture = findBarcodeTestFixture(manifest.barcode);
const source = new SourceBrain().lookupMedicine(manifest.medicine);
const knownCatalog = ["Cefixime", "Ceftriaxone", "Salbutamol", "Metformin", "Omeprazole", "Diclofenac", "Hydrocortisone", "Azithromycin", "Zinc", "Acyclovir", "Clotrimazole", "Doxycycline", "Chloramphenicol", "Albendazole", "Amlodipine", "Fluconazole", "Betamethasone", "Amitriptyline", "Artemether Lumefantrine", "Ciprofloxacin", "Loratadine", "Aspirin", "Atenolol", "Erythromycin", "Folic Acid"];
const digits = manifest.barcode.split("").map(Number);
const check = (10 - (digits.slice(0, 12).reduce((sum, digit, index) => sum + digit * (index % 2 ? 3 : 1), 0) % 10)) % 10;

if (manifest.format !== "EAN-13" || digits.length !== 13 || check !== digits[12]) throw new Error("Fixture barcode must be valid EAN-13");
if (!fixture || BarcodeTestFixtures.length !== 1) throw new Error("Fixture registry lookup failed or is not isolated");
if (source.status !== "matched" || source.name !== manifest.medicine) throw new Error("Fixture medicine must resolve through Source Brain");
if (knownCatalog.includes(manifest.medicine)) throw new Error("Fixture medicine must not duplicate the known 25-item live catalog");
if (fixture.strength !== manifest.strength || fixture.barcode !== manifest.barcode || fixture.expiry !== manifest.expiry) throw new Error("Expected fixture fields drifted");
if (png.length < 10000 || png.subarray(1, 4).toString() !== "PNG") throw new Error("Scannable PNG artifact is missing or invalid");
console.log("Barcode fixture verification passed: valid EAN-13, Source Brain match, isolated mapping, non-duplicate medicine, PNG artifact.");
