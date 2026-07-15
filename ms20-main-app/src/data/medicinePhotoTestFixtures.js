import { matchesControlledImageFixture } from "./controlledImageIdentity.js";

// Controlled live-test records only. Production medicine-photo recognition remains adapter-owned.
const MedicinePhotoTestFixtures = Object.freeze([
  Object.freeze({
    fixtureId: "medicine-photo-amoxicillin-500mg",
    fileName: "medicine-photo-amoxicillin-500mg.png",
    sha256: "5bbf45481b34879f17ba66dc4fe147f8c215c9f4c1e120546b92a37866e8c2af",
    perceptualHash: "ffffcfcff1c181ff",
    perceptualHashes: Object.freeze([
      "ffffcfcff1c181ff",
      "0000fcffffe0b8fc",
      "0000fcffffe0b03c",
      "0000fefedefe0000",
      "0000feffdffe0000"
    ]),
    aspectRatio: 0.6667,
    visualTolerance: 12,
    item: Object.freeze({
      name: "Amoxicillin",
      strength: "500 mg",
      form: "capsule",
      unit: "capsule",
      pack_size: "20 capsules",
      stock: "",
      selling_price: "",
      cost_price: "",
      supplier: "",
      barcode: "6161109876577",
      batch: "AMX-500K",
      expiry: "2029-08",
      shelf: "",
      source: "controlled_medicine_photo_fixture"
    })
  })
]);

export function findMedicinePhotoTestFixture(identity = {}) {
  const input = typeof identity === "string" ? { fileName: identity } : identity;
  return MedicinePhotoTestFixtures.find((fixture) => matchesControlledImageFixture(fixture, input)) || null;
}

export { MedicinePhotoTestFixtures };
