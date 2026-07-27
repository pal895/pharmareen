# Export format purpose

## Permanent engineering question

Before implementing, redesigning or approving any Export Hub format, answer:

> Why would a pharmacy owner deliberately choose this format instead of every other available export?

A format is justified only when it solves a distinct real pharmacy workflow. Multiple file extensions must not be used to disguise the same generic document.

## Shared contract

- The shared `EXPORT_FORMATS` registry carries a concise owner-facing explanation and a machine-readable unique purpose for every format.
- The Export Hub must make the choice understandable without separate documentation.
- Every renderer consumes the same immutable, validated, pharmacy-scoped canonical snapshot; purpose changes presentation and workflow, never source truth.
- New formats require a distinct purpose, focused regression coverage, deterministic generation, pharmacy isolation, zero routine AI formatting, and legal/IP-safe assets.
- If a distinct purpose cannot be stated clearly, redesign or reject the format.

## Current responsibilities

- **Excel:** inventory analysis, purchasing, reconciliation, calculations, filtering and pharmacy operations.
- **PDF:** professional read-only phone sharing, formal hand-offs and printing.
- **Word:** editable owner review, corrections, approval and typed or handwritten working notes.
- **CSV:** imports, exports, interoperability and machine-to-machine exchange.
- **Presentation:** management, staff, supplier, investor or lender briefings on a large screen.
- **Print:** an immediate physical working inventory produced from the browser.

Shared canonical parity does not mean identical design. Each format must prioritize the information and interaction needed for its own job.

## Presentation Owner Briefing

Presentation exists for owner and management decisions, not for reproducing the inventory register. Its deterministic nine-slide sequence is title, baseline overview, inventory position, stock/value summary, low-stock attention, expiry outlook, supplier overview, owner actions and closing decision path. Detailed reconciliation remains in Excel and record corrections remain in Word.

Before download, the production path validates the PPTX container, required OOXML parts, content types, relationships and slide count. The exact generated file is tested in Microsoft PowerPoint; generic ad-supported phone viewers are not compatibility authorities.
