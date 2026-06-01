# zotero-word-citation-fields

Codex skill for converting visible citations in Word `.docx` manuscripts into real Zotero citation fields.

## What it supports

- Numeric citations like `[1]`, `[1,2]`, `[5-9]`
- Author-year citations like `(Smith, 2020)`, `Smith (2020)`, `(Smith et al., 2022)`
- Building Zotero collection maps from `zotero.sqlite`
- Extracting and validating Word reference lists before generating RIS for Zotero import

## Main files

- `SKILL.md`
- `scripts/build_ref_map.py`
- `scripts/build_author_year_map.py`
- `scripts/extract_references_to_ris.py`
- `scripts/insert_word_citations.py`
- `references/implementation-notes.md`
