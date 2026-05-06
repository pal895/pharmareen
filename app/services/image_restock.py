from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ImageRestockExtraction:
    items: list[dict[str, Any]]
    confidence: float
    message: str = ""


class ImageRestockService:
    def __init__(self, ai_service: Any | None = None, store: Any | None = None):
        self.ai_service = ai_service
        self.store = store

    def extract(self, image_bytes: bytes, content_type: str | None = None) -> ImageRestockExtraction:
        extractor = getattr(self.ai_service, "extract_restock_from_image", None)
        if callable(extractor):
            result = extractor(image_bytes, content_type)
            if isinstance(result, ImageRestockExtraction):
                return result
            if isinstance(result, dict):
                return ImageRestockExtraction(
                    items=list(result.get("items") or []),
                    confidence=float(result.get("confidence") or 0),
                    message=str(result.get("message") or ""),
                )
        return ImageRestockExtraction(items=[], confidence=0.0, message="AI image extraction is not configured.")

    def queue_for_review(self, sender: str, extraction: ImageRestockExtraction, raw: dict[str, Any] | None = None) -> None:
        append_import_review = getattr(self.store, "append_import_review", None)
        if callable(append_import_review):
            append_import_review(
                {
                    "Sender": sender,
                    "Status": "pending_confirmation",
                    "Extracted Items": extraction.items,
                    "Confidence": extraction.confidence,
                    "Raw": raw or {},
                }
            )
