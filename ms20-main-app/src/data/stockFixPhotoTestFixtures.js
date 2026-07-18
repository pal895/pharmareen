import { matchesControlledImageFixture } from "./controlledImageIdentity.js";

// Controlled Stock Fix live-test evidence only. Production recognition remains adapter-owned.
const StockFixPhotoTestFixtures = Object.freeze([
  Object.freeze({
    fixtureId: "stock-fix-prednisolone-5mg",
    fileName: "stock-fix-prednisolone-5mg.png",
    sha256: "c21df57c10a9cf8c39972674274e7ad8c50d0953b15902e18bba23b958974874",
    perceptualHash: "fcfcf4f4fcfc4000",
    perceptualHashes: Object.freeze([
      "fcfcf4f4fcfc4000", "3f7f3f3f333f0000", "00023f3f2f2f3f3f", "0000fcccfcfcfefc",
      "fcfce0e4fcfc7c00", "3f7f7f73737b0000", "003e3f3f27073f3f", "0000dececefefefc",
      "f0fcc0e6fefe7e00", "3f7f7b73727a7800", "007e7f7f67033f0f", "001e5e4ecedefefc",
      "f970607cfcfcfcc0", "406060767efefe80", "600062667efefe60"
    ]),
    aspectRatio: 0.6667,
    aspectTolerance: 0.2,
    visualTolerance: 12,
    item: Object.freeze({
      name: "Prednisolone",
      strength: "5 mg",
      form: "tablet",
      unit: "tablet",
      pack_size: "100 tablets",
      stock: "",
      batch: "PRE-5T",
      expiry: "2028-11",
      source: "controlled_stock_fix_photo_fixture"
    })
  })
]);

export function findStockFixPhotoTestFixture(identity = {}) {
  const input = typeof identity === "string" ? { fileName: identity } : identity;
  return StockFixPhotoTestFixtures.find((fixture) => matchesControlledImageFixture(fixture, input)) || null;
}

export { StockFixPhotoTestFixtures };
