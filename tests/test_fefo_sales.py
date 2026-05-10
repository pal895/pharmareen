from __future__ import annotations

from app.services.batch_service import BatchRecord, BatchService, InMemoryBatchStore


def test_sale_deducts_from_earliest_expiry_batch_first():
    store = InMemoryBatchStore()
    store.append_batch(BatchRecord("A", "Panadol", 20, 20, expiry_date="2026-03-01"))
    store.append_batch(BatchRecord("B", "Panadol", 50, 50, expiry_date="2027-01-01"))
    service = BatchService(store)

    deductions = service.deduct_fefo("Panadol", 25)

    assert [(deduction.batch_id, deduction.quantity) for deduction in deductions] == [("A", 20), ("B", 5)]
    assert store.batches[0].current_remaining_units == 0
    assert store.batches[1].current_remaining_units == 45
