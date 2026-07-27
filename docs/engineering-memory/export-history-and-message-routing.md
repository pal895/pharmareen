# Export history and message routing

Export generation must not turn the main sales conversation into an audit log. The main chat may contain at most one compact `ExportHubCard`; each generation updates that card in place. Full history belongs inside Export Hub and is ordered newest first.

Each `ms20.export-history.v1` record contains a deterministic identifier, format, filename, pharmacy identity, Africa/Nairobi generation time, medicine count, operational purpose, opening guidance, status and version. Records are stored under a pharmacy-scoped key. Retrying the same file replaces its existing record.

Statuses are `completed`, `failed` or `unavailable`. Failed and unavailable records expose **Generate again**. Binary files are downloaded to the owner's device and never retained in browser storage; only the 50 newest metadata records per pharmacy are retained.

Office exports must be validated before download. PPTX validation checks the ZIP end record, required OOXML parts, content types, internal relationships and the nine-slide briefing contract. If a generic phone viewer rejects a PPTX that opens in Microsoft PowerPoint, record a viewer limitation and name the compatible application actually tested.
