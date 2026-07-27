# Export history and message routing

Export generation must not turn the main sales conversation into an audit log. The main chat may contain at most one compact `ExportHubCard`; each generation updates that card in place. Full history belongs inside Export Hub and is ordered newest first.

Each `ms20.export-history.v1` record contains a deterministic identifier, format, filename, pharmacy identity, Africa/Nairobi generation time, medicine count, operational purpose, opening guidance, status and version. Records are stored under a pharmacy-scoped key. Retrying the same file replaces its existing record.

Statuses include `completed`, `failed` and `unavailable`, plus truthful Print states `print_view_ready`, `print_dialog_opened` and `print_preparation_failed`. Browser APIs cannot prove a physical print completed or reliably distinguish cancellation, so MS2.0 claims neither. Failed and unavailable records expose regeneration. Files stay in device Downloads; only the 50 newest metadata records per pharmacy are retained.

Office exports must be validated before download. PPTX validation checks the ZIP end record, required OOXML parts, content types, internal relationships and the nine-slide briefing contract. PowerPoint is recommended; Google Slides and standards-compatible readers are valid fallbacks. Owner evidence on 2026-07-27 validated all nine slides in an Android compatible reader, permanently passing Presentation.
