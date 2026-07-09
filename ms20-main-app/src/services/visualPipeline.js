export function runVisualPipeline({ fileName = "", scanType = "medicine_photo" } = {}) {
  const knownFile = Boolean(fileName);
  const steps = [
    { name: "local_image_preprocessing", status: "ready_placeholder" },
    { name: "local_ocr", status: "ready_placeholder" },
    { name: "barcode_extraction", status: "ready_placeholder" },
    { name: "packaging_visual_match", status: "ready_placeholder" },
    { name: "pharmacy_catalog_match", status: "ready_placeholder" },
    { name: "source_brain_lookup", status: "ready_placeholder" },
    { name: "confidence_scoring", status: "ready_placeholder" },
    { name: "visual_memory_save", status: "ready_placeholder" },
    { name: "ai_fallback_adapter", status: "disabled_until_explicitly_needed" }
  ];

  return {
    id: `visual-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    scanType,
    fileName: fileName || "demo-photo.jpg",
    confidence: knownFile ? 0.68 : 0.42,
    localFirst: true,
    aiRequired: false,
    needsOwnerCorrection: true,
    steps,
    outputCardType: scanType === "invoice" ? "InvoiceCard" : "VisualScanCard"
  };
}

export function buildPhotoReviewCard(result) {
  return {
    id: `card-${result.id}`,
    type: result.outputCardType,
    title: result.outputCardType === "InvoiceCard" ? "Review invoice scan" : "Review medicine scan",
    source: result.fileName,
    confidence: result.confidence,
    aiRequired: false,
    status: "needs_correction",
    fields: {
      scan_type: result.scanType,
      medicine: "",
      form: "",
      unit: "",
      pack_size: "",
      category: ""
    },
    validation: "Local scan placeholder. Owner correction saves visual memory."
  };
}
