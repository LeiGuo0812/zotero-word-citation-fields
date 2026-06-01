# zotero-word-citation-fields

`zotero-word-citation-fields` is a Codex skill for converting visible citations in a Word `.docx` manuscript into real Zotero citation fields without depending on the Zotero citation picker dialog.

This skill is designed for workflows where:

- the manuscript already contains visible citations in the correct locations
- Zotero Desktop is installed locally
- the user wants the final document to contain actual Zotero-managed citation fields
- the Zotero citation picker is slow, stuck, or impractical for large-scale cleanup

The implementation works by editing the Word document's OOXML structure directly and inserting valid `ZOTERO_ITEM CSL_CITATION` field codes.

## Why this exists

In many real manuscripts, citations already exist as plain text:

- numeric citations such as `[1]`, `[1,2]`, `[5-9]`
- author-year citations such as `(Smith, 2020)`, `Smith (2020)`, `(Smith et al., 2022)`

At that stage, the user often does not need help deciding *which* paper to cite. The hard part is converting visible citation text into actual Zotero fields at scale while preserving the Word document.

The default Zotero workflow is often inconvenient for this scenario because:

- the Zotero citation picker dialog may lag or time out
- inserting hundreds of citations manually is slow
- documents with tracked changes and comments are easy to disturb during manual cleanup

This skill addresses that gap.

## What the skill does

The skill supports two broad workflows.

### Workflow A: The references are already in a Zotero collection

Use this path when the user already has the manuscript references in Zotero.

The skill can:

- read the local `zotero.sqlite`
- build a mapping between manuscript citation markers and Zotero item keys
- insert Zotero Word citation fields into the `.docx`
- preserve visible citation text as the field result

### Workflow B: The references are not yet in Zotero

Use this path when the Word file has a reference list, but the references are not organized in Zotero yet.

The skill can:

- extract the reference section from the Word document
- validate references conservatively against Crossref
- generate a RIS file for high-confidence matches
- produce a validation report listing unresolved or low-confidence entries

That RIS can then be imported into Zotero, after which Workflow A can continue.

## Supported citation forms

### Numeric citations

The main insertion script can recognize:

- `[1]`
- `[1,2]`
- `[5-9]`
- `[19-21,53]`

Numeric matching is intended for manuscripts where citation numbers map cleanly to Zotero items through a numeric reference map.

### Author-year citations

The main insertion script can also recognize literal author-year tokens such as:

- `(Smith, 2020)`
- `Smith (2020)`
- `(Smith & Jones, 2021)`
- `Smith and Jones (2021)`
- `(Smith et al., 2022)`

Author-year support is token-based. That means the skill inserts fields for exact visible citation strings once a token-to-item mapping exists.

## What the skill does not do

This skill is intentionally narrow. It does **not**:

- decide which references should be cited in which sentence
- rewrite the manuscript's scholarly logic
- guarantee that every malformed reference can be resolved automatically
- guarantee that every possible journal-specific author-year punctuation style is recognized
- guarantee that Zotero `Refresh` will preserve the exact current visible punctuation

It is a field-insertion and workflow-automation tool, not a semantic citation recommender.

## Directory layout

```text
zotero-word-citation-fields/
├── README.md
├── SKILL.md
├── references/
│   └── implementation-notes.md
└── scripts/
    ├── build_author_year_map.py
    ├── build_ref_map.py
    ├── extract_references_to_ris.py
    └── insert_word_citations.py
```

## Requirements

The current implementation assumes:

- macOS or another environment with Python 3 available
- a local Zotero Desktop installation
- access to the local Zotero database file, usually `~/Zotero/zotero.sqlite`
- a Word manuscript in `.docx` format

Additional practical assumptions:

- the manuscript already contains visible citation markers in approximately correct locations
- the user can identify the Zotero collection containing the manuscript references, or is willing to import them first
- for RIS generation, the environment has internet access to query Crossref

## Core concept

The important technical idea is:

1. read the local Zotero database
2. map visible citation text to Zotero item keys
3. build a valid CSL citation JSON payload
4. insert a Word field with code like:

```text
ADDIN ZOTERO_ITEM CSL_CITATION {json} \* MERGEFORMAT
```

Once the field is in the document, Zotero can recognize it as a real citation field.

## Recommended workflow

## Step 1: Ask for the Zotero collection first

This is the intended branch point for the skill.

Ask the user:

- which Zotero collection or folder contains the manuscript references

Then choose one of the two paths below.

## Path A: User already has a Zotero collection

### A1. Decide whether the manuscript is numeric or author-year

Use numeric mapping when the manuscript looks like:

- `[1]`
- `[2,3]`
- `[7-10]`

Use author-year mapping when the manuscript looks like:

- `(Smith, 2020)`
- `Smith (2020)`
- `(Smith et al., 2022)`

If both types appear, the insertion script can accept both a numeric map and a literal citation map.

### A2. Build a numeric reference map

Use this when Zotero items in the target collection have `callNumber` values matching the manuscript reference numbers.

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/build_ref_map.py \
  --db ~/Zotero/zotero.sqlite \
  --collection-name "CY-BN_MRI" \
  --out ref_map.json
```

Expected behavior:

- each Zotero item is inspected
- `callNumber` is treated as the reference number
- items without numeric `callNumber` are skipped and reported
- duplicate numeric `callNumber` values cause the script to stop

Example output:

```json
{"path":"/absolute/path/ref_map.json","count":53}
```

### A3. Build an author-year literal citation map

Use this when the manuscript uses author-year citations.

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/build_author_year_map.py \
  --db ~/Zotero/zotero.sqlite \
  --collection-name "MyCollection" \
  --out author_year_map.json \
  --unresolved-out author_year_ambiguities.json
```

What this script does:

- reads creators and year from each Zotero item
- generates common literal citation tokens
- writes exact-token mappings for unambiguous cases
- writes a separate unresolved report for ambiguous tokens or skipped items

Example output:

```json
{
  "path":"/absolute/path/author_year_map.json",
  "count":130,
  "ambiguous_tokens":0,
  "skipped_items":0,
  "unresolved_report":"/absolute/path/author_year_ambiguities.json"
}
```

### A4. Insert Zotero fields into the Word manuscript

Numeric-only manuscript:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/insert_word_citations.py \
  --docx manuscript.docx \
  --db ~/Zotero/zotero.sqlite \
  --ref-map ref_map.json
```

Author-year-only manuscript:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/insert_word_citations.py \
  --docx manuscript.docx \
  --db ~/Zotero/zotero.sqlite \
  --citation-map author_year_map.json
```

Mixed manuscript:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/insert_word_citations.py \
  --docx manuscript.docx \
  --db ~/Zotero/zotero.sqlite \
  --ref-map ref_map.json \
  --citation-map author_year_map.json
```

What happens during insertion:

- the script loads the Zotero `userID` from the Zotero settings table
- item metadata is pulled from `zotero.sqlite`
- the original `.docx` is backed up automatically
- visible citation tokens are replaced with real Zotero citation fields
- the visible citation text is preserved as the field result

Example output:

```json
{
  "docx":"/absolute/path/manuscript.docx",
  "backup":"/absolute/path/manuscript_before_zotero_fields_20260601_120000.docx",
  "citations_inserted":36,
  "runs_scanned":4821,
  "numeric_mapping_entries":53,
  "literal_mapping_entries":0
}
```

### A5. Verify in Word before refreshing

After insertion:

- open the document in Word
- confirm the document loads normally
- confirm visible citations still look reasonable
- only then consider Zotero `Refresh`

This matters because Zotero `Refresh` may change punctuation or formatting depending on the active CSL style.

## Path B: User does not have a Zotero collection yet

### B1. Extract and validate references before generating RIS

Use:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/extract_references_to_ris.py \
  --docx manuscript.docx \
  --out-ris manuscript_references.ris \
  --out-report manuscript_references_validation.json
```

If the reference heading is nonstandard:

```bash
python3 ~/.codex/skills/zotero-word-citation-fields/scripts/extract_references_to_ris.py \
  --docx manuscript.docx \
  --heading "References" \
  --out-ris manuscript_references.ris \
  --out-report manuscript_references_validation.json
```

What this script does:

- reads visible paragraphs from the Word document
- locates the reference section
- checks each reference against Crossref
- writes RIS only for high-confidence matches
- writes a separate JSON validation report

This is intentionally conservative. Low-confidence entries are not silently converted into RIS.

Example output:

```json
{
  "references_found":61,
  "resolved":32,
  "unresolved":29,
  "ris_path":"/absolute/path/manuscript_references.ris",
  "report_path":"/absolute/path/manuscript_references_validation.json"
}
```

### B2. Import the RIS into Zotero

After RIS generation:

- import the RIS into Zotero
- organize the imported entries into a dedicated collection
- if needed, add missing `callNumber` values for numeric workflows

Then continue with Path A.

## Script reference

## `build_ref_map.py`

Purpose:

- build a `reference number -> Zotero item key` JSON map from a Zotero collection

Best used when:

- the manuscript uses numeric citations
- Zotero items already carry the manuscript reference numbers in `callNumber`

Failure conditions:

- target collection is missing
- multiple collections share the same name and no collection ID is given
- duplicate numeric `callNumber` values exist
- no usable numeric `callNumber` values are found

## `build_author_year_map.py`

Purpose:

- build a literal citation-token map from Zotero item metadata

Best used when:

- the manuscript uses author-year citations
- the manuscript's visible citation strings roughly match common generated patterns

Important caveat:

- generated author-year tokens are heuristic, not perfect

## `extract_references_to_ris.py`

Purpose:

- extract Word references
- validate them externally
- generate RIS only for high-confidence matches

Best used when:

- the user has a Word manuscript but has not populated Zotero yet

Important caveat:

- unresolved references are a feature, not necessarily a failure

## `insert_word_citations.py`

Purpose:

- replace visible in-text citations with real Zotero citation fields

Best used when:

- the citation placement is already correct
- the main need is field conversion, not citation selection

Important caveat:

- the script works best when a citation token appears inside one visible text node

## Input and output artifacts

Common inputs:

- `manuscript.docx`
- `~/Zotero/zotero.sqlite`
- `ref_map.json`
- `author_year_map.json`

Common outputs:

- a backup copy of the original `.docx`
- a modified `.docx` with Zotero citation fields
- `ref_map.json`
- `author_year_map.json`
- `author_year_ambiguities.json`
- `manuscript_references.ris`
- `manuscript_references_validation.json`

## Track changes and document safety

The insertion strategy was built with real edited manuscripts in mind.

Important current behavior:

- deleted text inside `<w:del>` is skipped
- visible inserted text inside `<w:ins>` is preserved where possible
- the script backs up the source `.docx` before modification

This does **not** mean every tracked-changes edge case is solved automatically. It means the current implementation is cautious and avoids rewriting more than necessary.

## Style handling

This skill does **not** force a specific Zotero style just to make insertion succeed.

Preferred behavior:

- if the document already has Zotero preferences, keep them
- if the document does not have Zotero preferences yet, let Zotero use the document's later chosen defaults
- warn the user that Zotero `Refresh` may change bracket style, punctuation, spacing, or citation layout

Insertion success should remain independent from final citation-style choice.

## Reliability notes

This skill exists partly because the Zotero citation picker is not always the most reliable automation target.

Observed practical advantages of the OOXML insertion route:

- no dependence on the picker dialog
- no need to click through every citation manually
- better fit for large retrospective cleanup
- better fit for documents already carrying tracked changes and comments

## Known limitations

The current implementation has important boundaries.

### 1. Exact-token bias

Author-year insertion is based on literal visible tokens. If the manuscript uses many punctuation variants, custom narrative phrasing, or inconsistent formatting, the token map may require manual review.

### 2. Split-run citations

The insertion logic works best when the visible citation is intact inside one text node. If Word splits one citation token across multiple runs, that instance may not be converted automatically.

### 3. Ambiguous author-year cases

Cases such as:

- same first author + same year
- short-form collisions
- atypical creator names

must be reviewed before trusting the mapping.

### 4. Conservative RIS generation

The RIS generator intentionally prefers omission over bad data. Some legitimate references may remain unresolved if Crossref matching confidence is too low.

### 5. Refresh may restyle citations

A successful field insertion does not guarantee the visible citation string will remain visually identical after Zotero `Refresh`.

## Troubleshooting

## Problem: `Collection not found`

Check:

- the collection name is correct
- the Zotero database path is correct
- the collection exists in the target Zotero library

If duplicate collection names exist, use `--collection-id`.

## Problem: duplicate numeric `callNumber`

This means at least two Zotero items claim the same manuscript number. Clean the collection first, then rebuild the numeric map.

## Problem: citation not converted

Possible reasons:

- the citation token was split across multiple Word runs
- the citation text was not present in the literal map
- the numeric map did not contain one of the cited reference numbers
- the citation was in deleted tracked text

## Problem: RIS generation missed many references

Possible reasons:

- the Word reference formatting is noisy
- the heading is nonstandard and `--heading` was needed
- the references are incomplete or malformed
- Crossref had no sufficiently confident match

## Problem: Zotero refresh changes brackets or punctuation

That is expected behavior when the active Zotero style renders citations differently from the currently visible field result.

## Validation recommendations

Before considering the workflow complete, verify:

- the modified `.docx` opens normally in Word
- the visible citations remain in the expected positions
- Zotero recognizes the inserted citations as fields
- the reference list and in-text citations still correspond semantically
- any ambiguous author-year mappings were manually checked
- unresolved RIS references were not silently ignored without review

## Example end-to-end use cases

### Use case 1: Numeric medical manuscript with existing Zotero collection

1. User has citations like `[1]`, `[2,3]`, `[10-12]`
2. Zotero collection already exists
3. Items in the collection have numeric `callNumber`
4. Run `build_ref_map.py`
5. Run `insert_word_citations.py`
6. Open in Word and verify before refreshing

### Use case 2: Author-year psychology manuscript with existing Zotero collection

1. User has citations like `(Smith, 2020)` and `Smith et al. (2022)`
2. Zotero collection already exists
3. Run `build_author_year_map.py`
4. Review ambiguities
5. Run `insert_word_citations.py`
6. Open in Word and verify

### Use case 3: Word manuscript without Zotero collection

1. User has a completed manuscript and reference list in Word
2. Run `extract_references_to_ris.py`
3. Import generated RIS into Zotero
4. Organize imported entries into a collection
5. Build numeric or author-year maps as appropriate
6. Insert citation fields

## Relationship to `SKILL.md`

`SKILL.md` is the concise operational entry point for Codex.

This `README.md` is the fuller human-facing documentation for:

- users deciding whether the skill fits their manuscript
- users preparing the right Zotero collection
- future maintainers extending the scripts
- public repository readers who need to understand the workflow and boundaries

## References

- See [SKILL.md](./SKILL.md) for the concise Codex-facing instructions.
- See [references/implementation-notes.md](./references/implementation-notes.md) for details on the successful implementation path and observed pitfalls.
