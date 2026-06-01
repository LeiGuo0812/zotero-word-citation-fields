---
name: zotero-word-citation-fields
description: Insert Zotero citations into Word .docx manuscripts by converting visible in-text citations into real Zotero Word fields. Use this when a user has a Word manuscript with numeric citations like [1], [1,2], [5-9] or author-year citations like (Smith, 2020), Smith (2020), or (Smith et al., 2020), and wants them linked to items in a local Zotero library or collection without relying on the Zotero citation picker dialog.
metadata:
  short-description: Convert Word citations into Zotero fields
  version: "1.1"
---

# Zotero Word Citation Fields

Use this skill when the user wants to turn visible citations in a `.docx` manuscript into actual Zotero Word fields.

This skill uses direct OOXML editing rather than the Zotero citation picker dialog. That path is often more reliable when:

- Zotero is installed locally but the citation picker is slow or stuck
- the Zotero local API times out
- the manuscript already has citation text in the right positions and only needs field conversion

## First question to ask

Before doing anything else, ask the user for the Zotero collection or folder that contains the manuscript references.

There are two main paths:

1. **User has a Zotero collection already**
   Then build a map from that collection and insert fields.

2. **User does not have a Zotero collection yet**
   Then explain that you can extract the Word reference list, validate the references, generate a RIS file, and have the user import that RIS into Zotero first.

Do not skip this branch point.

## Supported citation forms

### Numeric citations

The main insertion script can detect and convert numeric citations such as:

- `[1]`
- `[1,2]`
- `[5-9]`
- `[19-21,53]`

using a numeric reference-number map.

### Author-year citations

The main insertion script also supports literal author-year citation strings such as:

- `(Smith, 2020)`
- `Smith (2020)`
- `(Smith & Jones, 2021)`
- `Smith and Jones (2021)`
- `(Smith et al., 2022)`

For these, provide a literal citation-token map. A helper script can generate common author-year tokens from a Zotero collection, but ambiguous tokens should be reviewed before insertion.

## Workflow

### Path A: Zotero collection already exists

1. Ask for the Zotero collection or folder name.
2. Determine whether the manuscript uses numeric or author-year citations.
3. Build the required mapping:
   - Numeric: `build_ref_map.py`
   - Author-year: `build_author_year_map.py`
4. Back up the `.docx`.
5. Insert Zotero fields with `insert_word_citations.py`.
6. Open the result in Word and verify it loads normally.
7. Only refresh from the Zotero ribbon after checking the document's current style behavior.

### Path B: No Zotero collection yet

1. Tell the user you can extract the Word references and generate a RIS file.
2. Before generating RIS, validate the references.
3. Use `extract_references_to_ris.py` to:
   - extract the reference section
   - validate entries against Crossref
   - generate a RIS file only for resolved entries
   - produce a report listing unresolved or low-confidence references
4. Have the user import the RIS into Zotero.
5. After import, continue with Path A.

## Commands

### 1. Build a numeric reference map from a Zotero collection

Use when the Zotero collection items have numeric `callNumber` values matching the manuscript reference numbers.

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/build_ref_map.py \
  --db ~/Zotero/zotero.sqlite \
  --collection-name "ExampleCollection" \
  --out ref_map.json
```

### 2. Build an author-year literal citation map from a Zotero collection

Use when the manuscript uses author-year citations.

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/build_author_year_map.py \
  --db ~/Zotero/zotero.sqlite \
  --collection-name "ExampleCollection" \
  --out author_year_map.json \
  --unresolved-out citation_map_review.json
```

Review the unresolved report before insertion if there are ambiguous tokens.

### 3. Insert Zotero fields into the Word file

Numeric citations:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/insert_word_citations.py \
  --docx manuscript.docx \
  --db ~/Zotero/zotero.sqlite \
  --ref-map ref_map.json
```

Author-year citations:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/insert_word_citations.py \
  --docx manuscript.docx \
  --db ~/Zotero/zotero.sqlite \
  --citation-map author_year_map.json
```

Mixed or custom literal citations:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/insert_word_citations.py \
  --docx manuscript.docx \
  --db ~/Zotero/zotero.sqlite \
  --ref-map ref_map.json \
  --citation-map author_year_map.json
```

### 4. Validate Word references and generate RIS

Use when the user does not yet have the references in Zotero.

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/extract_references_to_ris.py \
  --docx manuscript.docx \
  --out-ris references_import.ris \
  --out-report references_validation.json
```

If the reference heading is nonstandard:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/extract_references_to_ris.py \
  --docx manuscript.docx \
  --heading "References" \
  --out-ris references_import.ris \
  --out-report references_validation.json
```

## Style handling

Do not force a fixed Zotero style just to increase matching success.

Preferred behavior:

- Keep the document's current Zotero preferences if they already exist.
- If the document has no Zotero style yet, let Zotero use its existing default behavior when the user later refreshes or sets document preferences.
- Warn the user that refreshing may re-render the citation punctuation or layout according to the active Zotero style.

Insertion success should be decoupled from citation-style choice.

## Important constraints

- This skill inserts Zotero fields into visible text citations. It does not decide which paper should be cited where.
- The insertion script works best when a citation token exists inside one visible text node. If Word has split a citation across multiple runs, normalization or a targeted fix may be needed.
- Deleted tracked text inside `<w:del>` is skipped.
- Visible inserted text inside `<w:ins>` is preserved and updated in place when possible.
- Author-year token generation is heuristic. Ambiguous forms, same-author same-year collisions, or journal-specific formatting differences must be reviewed.
- The RIS generation script validates against Crossref and may leave low-confidence or unresolved references out of the RIS file on purpose.

## References

- For the successful implementation summary and pitfalls, read [references/implementation-notes.md](references/implementation-notes.md).
