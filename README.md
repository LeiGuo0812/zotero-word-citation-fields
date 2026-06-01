# zotero-word-citation-fields

Convert visible citations in a Word `.docx` manuscript into real Zotero citation fields without relying on the Zotero citation picker dialog.

This skill is intended for cleanup and migration workflows where the manuscript already contains citations in roughly the right places, but those citations are still plain text instead of Zotero-managed fields.

## What it solves

Typical starting point:

- numeric citations such as `[1]`, `[1,2]`, `[5-9]`
- author-year citations such as `(Smith, 2020)` or `Smith (2020)`
- a Word manuscript that already has tracked changes, comments, or heavy editing history
- a Zotero picker workflow that is too slow, unreliable, or impractical to use citation-by-citation

This skill converts those visible citations into valid Word `ZOTERO_ITEM CSL_CITATION` fields by editing the document's OOXML directly.

## When to use it

Use this skill when:

- the document is a `.docx`
- the visible citation positions are already mostly correct
- the main goal is field conversion, not deciding what to cite
- the references already exist in Zotero, or can be imported into Zotero first

Do not use this skill as a substitute for scholarly citation review. It does not decide which source belongs in which sentence.

## Main workflows

There are two supported paths.

### Path A: References already exist in Zotero

Use this when the manuscript references already live in a Zotero collection.

Workflow:

1. Identify the Zotero collection containing the manuscript references.
2. Determine whether the manuscript uses numeric citations, author-year citations, or both.
3. Build the necessary citation map from `zotero.sqlite`.
4. Back up the `.docx`.
5. Insert Zotero fields into the document.
6. Open the result in Word and verify before refreshing with Zotero.

### Path B: References are not yet in Zotero

Use this when the Word document contains a reference list, but Zotero has not been populated yet.

Workflow:

1. Extract the reference section from the Word document.
2. Validate references conservatively against Crossref.
3. Generate a RIS file for high-confidence matches only.
4. Import that RIS into Zotero.
5. Continue with Path A.

## Supported citation forms

### Numeric citations

Recognized forms include:

- `[1]`
- `[1,2]`
- `[5-9]`
- `[19-21,53]`

### Author-year citations

Recognized literal forms include:

- `(Smith, 2020)`
- `Smith (2020)`
- `(Smith & Jones, 2021)`
- `Smith and Jones (2021)`
- `(Smith et al., 2022)`

Author-year matching is token-based. In practice, that means the visible string in Word must match a token produced or supplied in the citation map.

## Repository layout

```text
zotero-word-citation-fields/
├── README.md
├── SKILL.md
├── .gitignore
├── references/
│   └── implementation-notes.md
└── scripts/
    ├── build_author_year_map.py
    ├── build_ref_map.py
    ├── extract_references_to_ris.py
    └── insert_word_citations.py
```

## Requirements

- Python 3
- Zotero Desktop with access to the local `zotero.sqlite`
- a Word `.docx` manuscript
- internet access if you need Crossref validation for RIS generation

Typical Zotero database path:

```text
~/Zotero/zotero.sqlite
```

## Quick start

### Numeric workflow

Build a numeric reference map from a Zotero collection whose items use `callNumber` as the manuscript reference number:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/build_ref_map.py \
  --db ~/Zotero/zotero.sqlite \
  --collection-name "ExampleCollection" \
  --out ref_map.json
```

Insert Zotero fields into the manuscript:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/insert_word_citations.py \
  --docx manuscript.docx \
  --db ~/Zotero/zotero.sqlite \
  --ref-map ref_map.json
```

### Author-year workflow

Build a literal token map from a Zotero collection:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/build_author_year_map.py \
  --db ~/Zotero/zotero.sqlite \
  --collection-name "ExampleCollection" \
  --out author_year_map.json \
  --unresolved-out citation_map_review.json
```

Insert Zotero fields into the manuscript:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/insert_word_citations.py \
  --docx manuscript.docx \
  --db ~/Zotero/zotero.sqlite \
  --citation-map author_year_map.json
```

### Mixed workflow

If the manuscript contains both numeric and author-year citations:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/insert_word_citations.py \
  --docx manuscript.docx \
  --db ~/Zotero/zotero.sqlite \
  --ref-map ref_map.json \
  --citation-map author_year_map.json
```

### RIS generation workflow

If the references are not yet in Zotero:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/extract_references_to_ris.py \
  --docx manuscript.docx \
  --out-ris references_import.ris \
  --out-report references_validation.json
```

If the heading is nonstandard:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/extract_references_to_ris.py \
  --docx manuscript.docx \
  --heading "References" \
  --out-ris references_import.ris \
  --out-report references_validation.json
```

## Scripts

### `build_ref_map.py`

Builds a `reference number -> Zotero item key` JSON map from a Zotero collection.

Use it when:

- the manuscript uses numeric citations
- Zotero items already carry those numbers in `callNumber`

Stops with an error when:

- the collection is missing
- multiple collections share the same name and no ID is provided
- duplicate numeric `callNumber` values are found
- no valid numeric `callNumber` values exist

### `build_author_year_map.py`

Builds a literal citation-token map from Zotero item metadata.

Use it when:

- the manuscript uses author-year citations
- the visible citation strings roughly match common generated patterns

Also writes an unresolved review file for ambiguous or skipped cases when requested.

### `extract_references_to_ris.py`

Extracts a reference section from Word, validates entries against Crossref, and writes RIS for high-confidence matches only.

Use it when:

- the manuscript has a reference list
- Zotero is not ready yet
- you want a conservative import path rather than guessing missing metadata

### `insert_word_citations.py`

Replaces visible in-text citations with real Zotero citation fields.

Use it when:

- citation placement is already correct
- the main need is field conversion
- you want to preserve visible text while making Zotero recognize the citation

## Generated files

Common generated artifacts:

- `ref_map.json`
- `author_year_map.json`
- `citation_map_review.json`
- `references_import.ris`
- `references_validation.json`
- a timestamped backup copy of the source `.docx`

## Document safety behavior

Current behavior is intentionally conservative:

- the original `.docx` is backed up before modification
- deleted tracked text inside `<w:del>` is skipped
- visible inserted text inside `<w:ins>` is preserved where possible

This helps with heavily edited manuscripts, but it is not a guarantee that every possible Word revision edge case will be handled automatically.

## Style behavior

This skill does not force a specific Zotero CSL style just to make insertion succeed.

Recommended behavior:

- keep the document's current Zotero preferences if they already exist
- otherwise let Zotero use the user's normal defaults later
- warn users that Zotero `Refresh` may change brackets, punctuation, spacing, or overall citation rendering

In other words, field insertion and final citation styling are treated as separate problems.

## Limitations

Known boundaries of the current implementation:

- author-year matching is exact-token oriented and may miss punctuation variants
- citations split across multiple Word runs may not be converted automatically
- ambiguous same-author same-year cases require manual review
- RIS generation is conservative and may intentionally leave some references unresolved
- Zotero `Refresh` may restyle successfully inserted citations

## Troubleshooting

### `Collection not found`

Check:

- the Zotero database path
- the collection name
- whether duplicate collection names exist

If duplicate names exist, use a collection ID instead of a collection name.

### Duplicate numeric `callNumber`

Two or more Zotero items claim the same manuscript number. Clean the collection, then rebuild the numeric map.

### Citation not converted

Common causes:

- the token was split across multiple runs in Word
- the token was missing from the literal citation map
- one cited number was missing from the numeric map
- the text was inside deleted revision markup

### RIS output resolves fewer references than expected

Common causes:

- the reference heading was nonstandard
- the reference formatting was noisy
- the reference text was incomplete
- Crossref confidence was below the threshold

## Validation checklist

Before considering the workflow complete, verify:

- the modified `.docx` opens normally in Word
- visible citations are still in the right places
- Zotero recognizes the inserted citations as fields
- ambiguous author-year mappings were reviewed manually
- unresolved RIS references were checked rather than ignored

## Notes for maintainers

- `SKILL.md` is the concise Codex-facing operating guide
- `README.md` is the public human-facing repository overview
- `references/implementation-notes.md` records implementation details and observed pitfalls

## Related files

- [SKILL.md](./SKILL.md)
- [references/implementation-notes.md](./references/implementation-notes.md)
