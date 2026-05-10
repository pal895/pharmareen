from __future__ import annotations

from app.services.batch_service import BatchService, InMemoryBatchStore


def test_restock_creates_batch_record():
    store = InMemoryBatchStore()
    service = BatchService(store)

    batch = service.create_batch(
        {
            "drug_name": "Panadol",
            "quantity_received": 100,
            "expiry_date": "Jan 2027",
            "supplier_name": "ABC Pharma",
            "invoice_number": "INV-2031",
        }
    )

    assert batch.batch_id
    assert batch.drug_name == "Panadol"
    assert batch.current_remaining_units == 100
    assert batch.expiry_date == "2027-01-01"
    assert store.batches == [batch]
