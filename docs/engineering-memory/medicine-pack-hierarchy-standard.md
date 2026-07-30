# Authoritative Medicine Pack Hierarchy

Authority date: 2026-07-30  
State: implemented; awaiting Production Sales Card owner validation

Each catalog medicine may define:

- `baseStockUnit`: the unit counted in stock.
- `units`: permitted selling units.
- `unitConversions`: base-stock units consumed by one selling unit.
- `unitPrices`: exact approved selling price per selling unit.
- optional pack-level barcodes through the existing verified product/catalog source boundary.

No conversion or price is global. A packet, strip, box, bottle or carton relationship is valid only when it came from approved pharmacy catalog/onboarding/import/edit data or another verified deterministic owner-controlled source.

The deterministic sale parser separates medicine identity, quantity, normalized selling unit and payment. Singular/plural and common short forms normalize locally. The Production Sale model calculates:

`base stock deduction = selling quantity × authoritative unit conversion`

`expected total = selling quantity × authoritative unit price`

If conversion is missing, Confirm is blocked and Correct asks in natural pharmacy wording using the actual units, such as “How many tablets are in one box?” If price is missing, Confirm is blocked and Correct asks for the exact selling-unit price. The base-unit price is never substituted for a larger pack. A successful catalog medicine match remains attached even when the requested selling unit is not configured; known stock, identity, clinical description, buying price and traceability are never blanked. An approved confirmation persists both facts to that existing medicine for later offline deterministic use; an incomplete or cancelled draft persists nothing.

The local parser recognizes common pharmacy units and all pharmacy-configured unit keys. Irregular singular/plural forms are explicit (`box`/`boxes`), so the unit cannot be absorbed into medicine identity. This rule is shared by typed and voice command adapters.

Transaction metadata records the spoken selling unit, selling quantity, base stock unit, pack conversion and base-stock deduction. Stock mutation uses the base-stock deduction so queued/replayed transactions and future undo/report/export consumers retain auditable pack truth.

## Fixture classes

- Paracetamol: tablet base; packet conversion and price known.
- Amoxil: capsule base; box conversion known but price missing.
- ORS: sachet base; requested carton relationship missing.

These are behavior fixtures, not universal medicine assumptions.
