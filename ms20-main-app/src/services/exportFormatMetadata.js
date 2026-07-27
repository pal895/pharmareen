const formats = [
  {
    id: "xlsx", group: "polished", label: "Excel", extension: "xlsx",
    mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    purpose: "Analyze, filter, reconcile, calculate and plan purchasing.",
    recommendedApplication: "Microsoft Excel",
    fallbackApplications: ["Google Sheets", "LibreOffice Calc"],
    nextAction: "Open the downloaded workbook in Excel or another compatible spreadsheet application.",
    cardHelp: "Analyze, filter, reconcile, calculate and plan purchasing",
    historyDescription: "Polished workbook for inventory analysis and pharmacy operations.",
    completionWording: "Excel completed.",
    regenerationWording: "Download Excel again",
    icon: "spreadsheet", createsFile: true, downloadCapability: true, printBehavior: "none",
    safetyNotes: "No macros or AI formatting.", expiryBehavior: "Regenerate from the current canonical inventory snapshot."
  },
  {
    id: "pdf", group: "polished", label: "PDF", extension: "pdf", mime: "application/pdf",
    purpose: "Professional read-only phone sharing, printing and formal hand-offs.",
    recommendedApplication: "Adobe Acrobat Reader",
    fallbackApplications: ["Phone browser", "Another standard PDF reader"],
    nextAction: "Open the downloaded PDF in a PDF reader, share it or print it.",
    cardHelp: "Professional read-only phone sharing, printing and formal hand-offs",
    historyDescription: "Read-only owner copy for sharing, printing and formal hand-offs.",
    completionWording: "PDF completed.", regenerationWording: "Download PDF again",
    icon: "pdf", createsFile: true, downloadCapability: true, printBehavior: "optional",
    safetyNotes: "Read-only deterministic document.", expiryBehavior: "Regenerate from the current canonical inventory snapshot."
  },
  {
    id: "docx", group: "polished", label: "Word", extension: "docx",
    mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    purpose: "Review, correct, approve and add typed or handwritten notes.",
    recommendedApplication: "Microsoft Word", fallbackApplications: ["Google Docs", "LibreOffice Writer"],
    nextAction: "Open the editable file in Microsoft Word or another compatible document editor.",
    cardHelp: "Review, correct, approve and add typed or handwritten notes",
    historyDescription: "Editable owner review copy with notes and correction areas.",
    completionWording: "Word completed.", regenerationWording: "Download Word again",
    icon: "document", createsFile: true, downloadCapability: true, printBehavior: "optional",
    safetyNotes: "Editable OOXML with no macros or document protection.", expiryBehavior: "Regenerate from the current canonical inventory snapshot."
  },
  {
    id: "pptx", group: "polished", label: "Presentation", extension: "pptx",
    mime: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    purpose: "Brief management, staff, suppliers, investors or lenders on a large screen.",
    recommendedApplication: "Microsoft PowerPoint",
    fallbackApplications: ["Google Slides", "Another standards-compatible presentation application"],
    nextAction: "Open the downloaded presentation in Microsoft PowerPoint for the best experience.",
    cardHelp: "Brief management, staff, suppliers, investors or lenders on a large screen",
    historyDescription: "Nine-slide owner and management decision briefing.",
    completionWording: "Presentation completed.", regenerationWording: "Download Presentation again",
    icon: "presentation", createsFile: true, downloadCapability: true, printBehavior: "optional",
    safetyNotes: "Validated OOXML package; generic Android viewers are not guaranteed.", expiryBehavior: "Regenerate from the current canonical inventory snapshot."
  },
  {
    id: "print", group: "polished", label: "Print", extension: "", mime: "",
    purpose: "Produce a physical working inventory directly from the browser.",
    recommendedApplication: "Browser Print",
    fallbackApplications: ["Device system print controls"],
    nextAction: "Use browser Print and choose an available printer.",
    cardHelp: "Produce a physical working inventory directly from the browser",
    historyDescription: "Browser print view for a physical working inventory.",
    completionWording: "Print view ready.", regenerationWording: "Open print view again",
    icon: "print", createsFile: false, downloadCapability: false, printBehavior: "browser-system",
    safetyNotes: "Printer availability depends on the device and printer setup. Opening the dialog does not prove physical printing.",
    expiryBehavior: "Open a new print view from the current canonical inventory snapshot."
  },
  {
    id: "csv", group: "data", label: "CSV data file", extension: "csv", mime: "text/csv;charset=utf-8",
    purpose: "Exchange canonical records with another system or import workflow.",
    recommendedApplication: "Microsoft Excel",
    fallbackApplications: ["Google Sheets", "LibreOffice Calc", "Compatible pharmacy, inventory, accounting or data system"],
    nextAction: "Open it in Excel or Google Sheets to inspect the rows, or import it into another compatible system.",
    cardHelp: "Exchange canonical data with other systems and import workflows",
    historyDescription: "Canonical data rows for system exchange and import workflows.",
    completionWording: "CSV completed.", regenerationWording: "Download CSV again",
    icon: "data", createsFile: true, downloadCapability: true, printBehavior: "none",
    safetyNotes: "UTF-8 CSV with formula-injection protection; visual formatting is not preserved.",
    expiryBehavior: "Regenerate from the current canonical inventory snapshot."
  }
];

export const EXPORT_FORMATS = Object.freeze(formats.map((format) => Object.freeze({
  ...format,
  fallbackApplications: Object.freeze([...format.fallbackApplications]),
  accessibilityLabel: `${format.label}. ${format.purpose} ${format.nextAction}`
})));

export function exportFormat(formatId) {
  return EXPORT_FORMATS.find((format) => format.id === formatId) || null;
}

export function exportCompletionSummary(formatId, status) {
  const format = exportFormat(formatId);
  if (!format) return `Export ${status}.`;
  if (formatId === "print") {
    if (status === "print_dialog_opened") return "Print dialog opened. Choose an available printer using the browser or device controls.";
    if (status === "print_preparation_failed") return "Print preparation failed. Open the print view and try again.";
    return `${format.completionWording} ${format.nextAction}`;
  }
  return `${format.completionWording} ${format.nextAction}`;
}
