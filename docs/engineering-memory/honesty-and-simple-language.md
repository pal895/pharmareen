# MS2.0 honesty and simple-language standard

This is a permanent, product-wide engineering standard. It applies to existing work when that work is next touched and to every new feature, message, workflow, and review. It is not limited to one screen or one test fixture.

## Honesty first

MS2.0 must never imply that it saw, read, calculated, or confirmed something that it did not.

For every important value, preserve its source and show that source when it helps the owner make a decision. Use clear labels such as:

- Seen in the photo
- Already stored in your pharmacy catalog
- Known from the medicine database
- Entered by you
- Calculated from saved records
- Waiting for your confirmation

Do not merge information from different sources in a way that hides where it came from. A value copied from a prepared test record, catalog, medicine database, invoice, barcode match, or earlier owner decision must not be described as read from a new photo.

When evidence is missing or unclear:

- say what could not be read;
- leave unsupported values empty;
- ask for a clearer photo or owner confirmation when needed;
- keep the action unsaved until required facts are confirmed;
- never guess, invent, silently fill, or hide uncertainty.

## Simple English

Write for a reader around 12 years old. Use familiar words, short sentences, and only the information needed for the next decision.

Prefer helpful everyday language:

- “Keep bright light off the medicine packs.” instead of “Avoid glare.”
- “I couldn't read this photo clearly. Please take another photo.” instead of “Recognition confidence is low.”
- “Something doesn't look right. Please check it.” instead of “Validation failed.”

If a simpler word keeps the meaning, use it. If a sentence can be shorter without losing necessary safety information, shorten it. Do not use technical language to make the product sound clever.

## Product-wide scope

This standard applies to:

- onboarding and setup;
- camera, shelf photos, barcodes, invoices, and other input methods;
- editable reviews, confirmations, and approval boundaries;
- notifications, reports, exports, errors, loading and success messages;
- help text, empty states, offline and sync states;
- all future features.

## Required implementation check

Before completing any UI or message change, check:

1. Does every important value have a truthful source?
2. Could the screen make the owner think MS2.0 saw more than it did?
3. Is uncertainty visible and actionable?
4. Are unsupported values empty rather than guessed?
5. Can a 12-year-old understand every sentence immediately?
6. Is the message as short as safety and meaning allow?
7. Does the wording sound like a helpful person?

These checks belong in design review, implementation review, regression tests where practical, and controlled live validation. Fix the shared source or message rule rather than patching one screen. Preserve already validated behavior unless new evidence shows a regression.

## Product goal

The owner should feel that MS2.0 is honest, easy to understand, helpful, and never trying to sound clever. Clarity is more important than technical language. Trust is more important than sounding intelligent.
