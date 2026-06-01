# Implementation Notes

This skill came from a successful local Zotero-to-Word insertion workflow on macOS with Zotero Desktop and Microsoft Word.

## Working strategy

The reliable path for insertion was:

1. Avoid depending on the Zotero citation picker dialog.
2. Read Zotero metadata directly from the local `zotero.sqlite` database.
3. Build a CSL citation JSON payload for each numeric citation token.
4. Insert a Word field with code shaped like:

`ADDIN ZOTERO_ITEM CSL_CITATION {json} \* MERGEFORMAT`

5. Keep the visible field result equal to the current numeric text, such as `[1,2]`.
6. Let Zotero optionally normalize the field later through `Refresh`.

## Why this worked

Word and Zotero do not require the citation picker to create a valid citation field. They only require a valid field code and document-level Zotero preferences.

The document already contained Zotero preferences in `docProps/custom.xml`, for example:

- `ZOTERO_PREF_1`
- `ZOTERO_PREF_2`

That allowed Zotero to recognize the inserted fields later.

## Important pitfalls

### Local API may still fail

The Zotero connector may work while the local API on `127.0.0.1:23119` still times out. This does not block the OOXML field-insertion method.

### Refresh can change punctuation

Field insertion can preserve visible square brackets initially, but Zotero `Refresh` may re-render the citation according to the document's style.

Observed outcome:

- the inserted field stayed valid
- `Refresh` rewrote the citation formatting according to the configured CSL style

### Track changes behavior

If the citation token is inside visible inserted text under `<w:ins>`, replacing only the run contents preserves the tracked insertion wrapper. This is safer than reconstructing revision markup from scratch.

### Author-year support boundary

Author-year insertion works when the manuscript contains literal citation strings that can be matched exactly, for example:

- `(Smith, 2020)`
- `Smith (2020)`
- `(Smith et al., 2020)`

The insertion script can wrap those exact strings in Zotero fields if a token-to-item map is available.

The hard part is not field insertion; it is token mapping. A generated author-year map is only a heuristic and should be reviewed for:

- same-author same-year collisions
- multiple papers sharing the same generated short form
- journal-specific punctuation variants

### RIS generation boundary

When the user has no Zotero collection yet, the fallback path is:

1. extract the reference list from the Word file
2. validate each reference externally
3. generate RIS for high-confidence matches only

This is intentionally conservative. Low-confidence references should remain unresolved rather than silently producing bad RIS entries.

### Scope boundary

The helper script is best when citation markers exist as intact text tokens inside one text node, such as:

- `[1]`
- `[1,2]`
- `[5-9]`

If Word has split the token across runs, preprocess or repair that case manually.
