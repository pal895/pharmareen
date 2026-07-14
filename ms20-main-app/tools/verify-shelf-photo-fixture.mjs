import fs from "node:fs";
import crypto from "node:crypto";
import { SourceBrain } from "../src/services/brainAdapters.js";
import { findShelfTestFixture, ShelfTestFixtures } from "../src/data/shelfTestFixtures.js";
import { catalogItemsToText, parseCatalogText } from "../src/services/catalogOnboarding.js";

const manifest = JSON.parse(fs.readFileSync(new URL("../fixtures/shelf-photo-b2.json", import.meta.url), "utf8"));
const png = fs.readFileSync(new URL("../fixtures/shelf-photo-b2.png", import.meta.url));
const app = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
const fixture = findShelfTestFixture({ fileName: manifest.fileName });
const contentHash = crypto.createHash("sha256").update(png).digest("hex");
const sourceBrain = new SourceBrain();
const knownCatalog = ["Cefixime", "Ceftriaxone", "Salbutamol", "Metformin", "Omeprazole", "Diclofenac", "Hydrocortisone", "Azithromycin", "Zinc", "Acyclovir", "Clotrimazole", "Doxycycline", "Chloramphenicol", "Albendazole", "Amlodipine", "Fluconazole", "Betamethasone", "Amitriptyline", "Artemether Lumefantrine", "Ciprofloxacin", "Loratadine", "Aspirin", "Atenolol", "Erythromycin", "Folic Acid", "Losartan", "Loperamide"];
const assert = (condition, message) => { if (!condition) throw new Error(message); };

assert(fixture && ShelfTestFixtures.length === 1, "Shelf fixture lookup must remain isolated");
assert(contentHash === manifest.sha256 && fixture.sha256 === contentHash, "Shelf fixture content hash must match its manifest and registry");
assert(findShelfTestFixture({ fileName: "renamed-by-android.png", sha256: contentHash }) === fixture, "Renamed photo-picker uploads must resolve by content hash");
assert(fixture.perceptualHash === manifest.perceptualHash && fixture.aspectRatio === manifest.aspectRatio, "Shelf visual fingerprint must match its manifest");
assert(findShelfTestFixture({ fileName: "reencoded-by-photos.jpg", perceptualHash: "0004043efebdff01", aspectRatio: 1.78 }) === fixture, "Re-encoded photo-library uploads must tolerate bounded visual changes");
assert(findShelfTestFixture({ perceptualHash: "ffffffffffffffff", aspectRatio: 1.78 }) === null, "Unrelated images must not resolve as controlled fixtures");
assert(png.length > 100000 && png.subarray(1, 4).toString() === "PNG", "Realistic shelf PNG fixture is missing");
assert(fixture.items.length === 2 && fixture.items.every((item) => sourceBrain.lookupMedicine(item.name).status === "matched"), "Every shelf proposal must resolve through Source Brain");
assert(fixture.items.every((item) => !knownCatalog.includes(item.name)), "Shelf fixture must not overlap the known 27-item live catalog");
assert(fixture.items.every((item) => item.shelf === "B2" && item.stock && item.cost_price && item.selling_price && item.batch && item.expiry), "Shelf fixture must retain complete review fields");
const roundTrip = parseCatalogText(catalogItemsToText(fixture.items));
assert(roundTrip.length === 2 && roundTrip.every((item) => item.shelf === "B2"), "Shelf rows must survive shared editable-list serialization");
assert(app.includes('data-scan-type="shelf_photo">Shelf photo</button>'), "Shelf fixture must have a dedicated owner-facing photo-library action");
assert(app.includes('state.pendingScanType = "shelf_photo"'), "Catalog shelf scan must retain its scan identity through file acquisition");
assert(app.includes('crypto.subtle.digest("SHA-256"'), "Shelf fixture recognition must survive photo-picker filename changes");
assert(app.includes("createImageBitmap(fileOrName)"), "Shelf fixture recognition must survive photo-library re-encoding");
assert(app.includes('addPhotoCards(file || "camera-photo.jpg"'), "Photo-library acquisition must retain file content for fixture verification");
assert(app.includes('createPasteImportCard(catalogItemsToText(recognizedItems))'), "Recognized shelf medicines must converge into the shared multi-row catalog review");
assert(app.includes("sourceBrain.lookupMedicine(item.name).status === \"matched\""), "Controlled shelf proposals must be Source Brain-gated");

console.log("Shelf photo fixture verification passed: realistic PNG, filename/exact/visual identity, negative isolation, two Source Brain medicines, complete fields, and shared review round trip.");
