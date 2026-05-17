# PharMareen pharmacy training datasets

These JSONL files are deterministic simulation examples for the local-first pharmacy assistant. They cover rushed sales, shorthand, Swahili/English phrases, corrections, payment flows, supplier/restock patterns, offline sync, media intake, barcode mapping, and analytics requests.

Normal sales, restocks, reports, analytics, receipts, corrections, stock checks, barcode lookup, and offline typed sync should stay local and must not call OpenAI. Media/voice/photo rows document where AI is allowed later after safe capture, local classification, and owner confirmation.

Media intelligence cases teach PharMareen to classify photos before extraction: supplier invoice, supplier receipt, stock shelf, medicine pack, barcode image, handwritten note, delivery note, blurry/unclear image, mixed photo, and non-pharmacy photo. Stock is never updated from media until the owner confirms.
