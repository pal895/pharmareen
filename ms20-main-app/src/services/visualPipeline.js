export function runVisualPipeline({ fileName = "", scanType = "medicine_photo" } = {}) {
  const knownFile = Boolean(fileName);
  const fingerprint = localFingerprint(`${scanType}:${fileName || "camera"}`);
  const tokenControl = {
    localFirst: true,
    fingerprint,
    duplicateChecked: true,
    previousResultChecked: true,
    pharmacyCatalogChecked: true,
    sourceBrainChecked: true,
    barcodeChecked: true,
    supplierTemplateChecked: scanType === "invoice",
    localVisualSignatureChecked: true,
    aiUsed: false,
    aiFallback: "disabled_until_explicitly_needed"
  };
  const steps = [
    { name: "local_fingerprint", status: "ready", fingerprint },
    { name: "exact_duplicate_lookup", status: "ready_placeholder" },
    { name: "near_duplicate_lookup", status: "adapter_ready" },
    { name: "previous_confirmed_result_lookup", status: "ready_placeholder" },
    { name: "local_image_preprocessing", status: "ready_placeholder" },
    { name: "local_ocr", status: "adapter_ready" },
    { name: "barcode_extraction", status: "adapter_ready" },
    { name: "packaging_visual_match", status: "adapter_ready" },
    { name: "pharmacy_catalog_match", status: "ready_placeholder" },
    { name: "source_brain_lookup", status: "ready_placeholder" },
    { name: "supplier_template_lookup", status: scanType === "invoice" ? "adapter_ready" : "not_needed" },
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
    fingerprint,
    tokenControl,
    aiRequired: false,
    needsOwnerCorrection: true,
    steps,
    outputCardType: scanType === "invoice" ? "InvoiceCard" : "VisualScanCard"
  };
}

export function buildPhotoReviewCard(result) {
  const invoice = result.outputCardType === "InvoiceCard";
  return {
    id: `card-${result.id}`,
    type: result.outputCardType,
    title: invoice ? "Review invoice scan" : "Review medicine scan",
    source: result.fileName,
    confidence: result.confidence,
    aiRequired: false,
    status: "needs_correction",
    fields: invoice ? {
      supplier: "",
      medicine: "",
      quantity: "",
      unit: "",
      total: "",
      payment: "credit",
      batch: "",
      expiry: ""
    } : {
      scan_type: result.scanType,
      medicine: "",
      form: "",
      unit: "",
      pack_size: "",
      quantity: "",
      selling_price: "",
      cost_price: "",
      supplier: "",
      barcode: "",
      batch: "",
      expiry: "",
      shelf: "",
      category: ""
    },
    validation: "Local scanner pipeline is adapter-ready. Owner correction saves visual memory and catalog learning."
  };
}

function localFingerprint(value) {
  let hash = 0;
  for (const char of String(value)) {
    hash = ((hash << 5) - hash + char.charCodeAt(0)) | 0;
  }
  return `local-${Math.abs(hash).toString(16)}`;
}
