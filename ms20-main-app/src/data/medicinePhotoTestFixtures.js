// Controlled live-test records only. Production medicine-photo recognition remains adapter-owned.
const MedicinePhotoTestFixtures = Object.freeze([
  Object.freeze({
    fixtureId: "medicine-photo-amoxicillin-500mg",
    fileName: "medicine-photo-amoxicillin-500mg.png",
    sha256: "5bbf45481b34879f17ba66dc4fe147f8c215c9f4c1e120546b92a37866e8c2af",
    perceptualHash: "ffffcfcff1c181ff",
    aspectRatio: 0.6667,
    visualTolerance: 20,
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
  const name = String(input?.fileName || "").trim().toLowerCase();
  const sha256 = String(input?.sha256 || "").trim().toLowerCase();
  const perceptualHashes = (Array.isArray(input?.perceptualHashes) ? input.perceptualHashes : [input?.perceptualHash])
    .map((hash) => String(hash || "").trim().toLowerCase())
    .filter(Boolean);
  const aspectRatio = Number(input?.aspectRatio || 0);
  const hammingDistance = (left, right) => {
    if (!left || !right || left.length !== right.length) return Infinity;
    let distance = 0;
    for (let index = 0; index < left.length; index += 1) {
      let value = Number.parseInt(left[index], 16) ^ Number.parseInt(right[index], 16);
      while (value) {
        distance += value & 1;
        value >>>= 1;
      }
    }
    return distance;
  };
  return MedicinePhotoTestFixtures.find((fixture) =>
    (name && fixture.fileName.toLowerCase() === name)
    || (sha256 && fixture.sha256 === sha256)
    || (perceptualHashes.length
      && Math.min(
        Math.abs(aspectRatio - fixture.aspectRatio),
        Math.abs((1 / Math.max(aspectRatio, 0.0001)) - fixture.aspectRatio)
      ) <= 0.15
      && perceptualHashes.some((hash) => hammingDistance(hash, fixture.perceptualHash) <= fixture.visualTolerance))
  ) || null;
}

export { MedicinePhotoTestFixtures };
