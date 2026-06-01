#!/usr/bin/env python3
import argparse
import copy
import json
import re
import shutil
import sqlite3
import uuid
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
W = f"{{{W_NS}}}"
ET.register_namespace("w", W_NS)


def qn(tag: str) -> str:
    return W + tag


def deep(elem: ET.Element | None) -> ET.Element | None:
    return copy.deepcopy(elem) if elem is not None else None


def text_needs_preserve(text: str) -> bool:
    return text.startswith(" ") or text.endswith(" ") or "  " in text or "\t" in text


def parse_year(raw: str | None) -> int | None:
    if not raw:
        return None
    match = re.search(r"(\d{4})", raw)
    return int(match.group(1)) if match else None


def parse_numeric_citation_token(token: str) -> list[int]:
    token = token.strip()[1:-1]
    refs: list[int] = []
    for part in token.split(","):
        part = part.strip()
        if "-" in part:
            start, end = [int(x.strip()) for x in part.split("-", 1)]
            refs.extend(range(start, end + 1))
        else:
            refs.append(int(part))
    return refs


def zotero_type_to_csl(item_type: str) -> str:
    return {
        "journalArticle": "article-journal",
        "book": "book",
        "bookSection": "chapter",
        "report": "report",
        "thesis": "thesis",
        "webpage": "webpage",
        "conferencePaper": "paper-conference",
    }.get(item_type, "article")


def fetch_item_metadata(db_path: Path, item_keys: set[str]) -> dict[str, dict]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    items: dict[str, dict] = {}

    for key in sorted(item_keys):
        cur.execute(
            """
            SELECT i.itemID, i.key, it.typeName
            FROM items i
            JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
            WHERE i.key = ?
            """,
            (key,),
        )
        row = cur.fetchone()
        if row is None:
            raise SystemExit(f"Missing Zotero item for key {key}")
        meta = {
            "itemID": row["itemID"],
            "key": row["key"],
            "itemType": row["typeName"],
            "fields": {},
            "creators": [],
        }
        cur.execute(
            """
            SELECT f.fieldName, v.value
            FROM itemData d
            JOIN fields f ON f.fieldID = d.fieldID
            JOIN itemDataValues v ON v.valueID = d.valueID
            WHERE d.itemID = ?
            """,
            (row["itemID"],),
        )
        for field_row in cur.fetchall():
            meta["fields"][field_row["fieldName"]] = field_row["value"]
        cur.execute(
            """
            SELECT c.lastName, c.firstName
            FROM itemCreators ic
            JOIN creators c ON c.creatorID = ic.creatorID
            WHERE ic.itemID = ?
            ORDER BY ic.orderIndex
            """,
            (row["itemID"],),
        )
        meta["creators"] = cur.fetchall()
        items[key] = meta

    return items


def build_citation_item(meta: dict, user_id: str) -> dict:
    fields = meta["fields"]
    item_data = {
        "id": meta["itemID"],
        "type": zotero_type_to_csl(meta["itemType"]),
        "title": fields.get("title", ""),
    }

    year = parse_year(fields.get("date"))
    if year is not None:
        item_data["issued"] = {"date-parts": [[year]]}

    creators = []
    for creator in meta["creators"]:
        last = (creator["lastName"] or "").strip()
        first = (creator["firstName"] or "").strip()
        if first:
            creators.append({"family": last, "given": first})
        elif last:
            creators.append({"literal": last})
    if creators:
        item_data["author"] = creators

    field_map = {
        "publicationTitle": "container-title",
        "journalAbbreviation": "container-title-short",
        "volume": "volume",
        "issue": "issue",
        "pages": "page",
        "DOI": "DOI",
        "publisher": "publisher",
        "place": "publisher-place",
        "edition": "edition",
        "ISBN": "ISBN",
        "url": "URL",
        "language": "language",
    }
    for src, dst in field_map.items():
        value = fields.get(src)
        if value:
            item_data[dst] = value

    return {
        "id": meta["itemID"],
        "uris": [f"http://zotero.org/users/{user_id}/items/{meta['key']}"],
        "itemData": item_data,
    }


def new_run(text: str, rpr: ET.Element | None) -> ET.Element:
    run = ET.Element(qn("r"))
    if rpr is not None:
        run.append(deep(rpr))
    t = ET.SubElement(run, qn("t"))
    if text_needs_preserve(text):
        t.set(f"{{{XML_NS}}}space", "preserve")
    t.text = text
    return run


def new_fld_char_run(kind: str, rpr: ET.Element | None) -> ET.Element:
    run = ET.Element(qn("r"))
    if rpr is not None:
        run.append(deep(rpr))
    fld = ET.SubElement(run, qn("fldChar"))
    fld.set(qn("fldCharType"), kind)
    return run


def new_instr_run(code: str, rpr: ET.Element | None) -> ET.Element:
    run = ET.Element(qn("r"))
    if rpr is not None:
        run.append(deep(rpr))
    instr = ET.SubElement(run, qn("instrText"))
    instr.set(f"{{{XML_NS}}}space", "preserve")
    instr.text = code
    return run


def build_field_code(token: str, item_keys: list[str], item_lookup: dict[str, dict], user_id: str) -> str:
    citation = {
        "citationID": f"generated-{uuid.uuid4().hex[:8]}",
        "properties": {
            "formattedCitation": token,
            "plainCitation": token,
            "noteIndex": 0,
        },
        "citationItems": [
            build_citation_item(item_lookup[item_key], user_id) for item_key in item_keys
        ],
        "schema": "https://github.com/citation-style-language/schema/raw/master/csl-citation.json",
    }
    return (
        " ADDIN ZOTERO_ITEM CSL_CITATION "
        + json.dumps(citation, ensure_ascii=False, separators=(",", ":"))
        + " \\* MERGEFORMAT "
    )


def load_user_id(db_path: Path) -> str:
    con = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    cur = con.cursor()
    cur.execute("SELECT value FROM settings WHERE setting='account' AND key='userID'")
    row = cur.fetchone()
    if row is None or not row[0]:
        raise SystemExit("Could not determine Zotero userID from settings table.")
    return str(row[0])


def load_numeric_map(path: Path | None) -> dict[str, list[str]]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[str, list[str]] = {}
    for key, value in raw.items():
        ref_num = int(key)
        token = f"[{ref_num}]"
        keys = value if isinstance(value, list) else [value]
        mapping[token] = [str(v) for v in keys]
    return mapping


def expand_numeric_patterns(ref_map: dict[str, list[str]]) -> dict[str, list[str]]:
    if not ref_map:
        return {}
    numeric_lookup = {int(token[1:-1]): keys[0] for token, keys in ref_map.items() if len(keys) == 1}
    expanded: dict[str, list[str]] = {}
    for ref_num, item_key in numeric_lookup.items():
        expanded[f"[{ref_num}]"] = [item_key]

    # This pattern is only used for token discovery; replacement still uses exact matched string.
    return expanded


def load_literal_map(path: Path | None) -> dict[str, list[str]]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[str, list[str]] = {}
    for token, value in raw.items():
        keys = value if isinstance(value, list) else [value]
        mapping[str(token)] = [str(v) for v in keys]
    return mapping


def find_numeric_tokens(text: str, ref_num_to_key: dict[int, str]) -> dict[str, list[str]]:
    pattern = re.compile(r"\[(?:\d+(?:\s*[-,]\s*\d+)*)\]")
    found: dict[str, list[str]] = {}
    for match in pattern.finditer(text):
        token = match.group(0)
        refs = parse_numeric_citation_token(token)
        keys: list[str] = []
        for ref_num in refs:
            if ref_num not in ref_num_to_key:
                raise SystemExit(f"Missing reference mapping for citation number {ref_num} in token {token}")
            keys.append(ref_num_to_key[ref_num])
        found[token] = keys
    return found


def build_ref_num_to_key_map(path: Path | None) -> dict[int, str]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {int(k): str(v) for k, v in raw.items()}


def replace_tokens_in_run(
    run: ET.Element,
    token_to_keys: dict[str, list[str]],
    item_lookup: dict[str, dict],
    user_id: str,
) -> tuple[list[ET.Element] | None, int]:
    texts = [child for child in list(run) if child.tag == qn("t")]
    if len(texts) != 1:
        return None, 0

    original_text = texts[0].text or ""
    if not original_text:
        return None, 0

    candidate_tokens = [token for token in token_to_keys if token in original_text]
    if not candidate_tokens:
        return None, 0

    candidate_tokens.sort(key=len, reverse=True)
    pattern = re.compile("(" + "|".join(re.escape(token) for token in candidate_tokens) + ")")
    if not pattern.search(original_text):
        return None, 0

    rpr = run.find(qn("rPr"))
    parts = pattern.split(original_text)
    new_runs: list[ET.Element] = []
    replaced = 0
    for part in parts:
        if not part:
            continue
        if part in token_to_keys:
            code = build_field_code(part, token_to_keys[part], item_lookup, user_id)
            new_runs.append(new_fld_char_run("begin", rpr))
            new_runs.append(new_instr_run(code, rpr))
            new_runs.append(new_fld_char_run("separate", rpr))
            new_runs.append(new_run(part, rpr))
            new_runs.append(new_fld_char_run("end", rpr))
            replaced += 1
        else:
            new_runs.append(new_run(part, rpr))
    return new_runs, replaced


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert plain in-text citations in a Word .docx into Zotero citation fields."
    )
    parser.add_argument("--docx", required=True, type=Path, help="Path to the target .docx")
    parser.add_argument("--db", required=True, type=Path, help="Path to zotero.sqlite")
    parser.add_argument(
        "--ref-map",
        type=Path,
        help="JSON mapping numeric reference number to Zotero item key, e.g. {\"1\": \"ABCD1234\"}",
    )
    parser.add_argument(
        "--citation-map",
        type=Path,
        help="JSON mapping literal citation strings to Zotero item key or list of item keys",
    )
    parser.add_argument(
        "--backup-suffix",
        default="_before_zotero_fields",
        help="Suffix for the backup file",
    )
    args = parser.parse_args()

    if args.ref_map is None and args.citation_map is None:
        raise SystemExit("Provide at least one of --ref-map or --citation-map")

    docx_path = args.docx.expanduser().resolve()
    db_path = args.db.expanduser().resolve()
    user_id = load_user_id(db_path)

    ref_num_to_key = build_ref_num_to_key_map(args.ref_map.expanduser().resolve() if args.ref_map else None)
    literal_map = load_literal_map(args.citation_map.expanduser().resolve() if args.citation_map else None)

    all_item_keys = set(ref_num_to_key.values())
    for keys in literal_map.values():
        all_item_keys.update(keys)
    item_lookup = fetch_item_metadata(db_path, all_item_keys)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = docx_path.with_name(f"{docx_path.stem}{args.backup_suffix}_{timestamp}{docx_path.suffix}")
    shutil.copy2(docx_path, backup)

    with zipfile.ZipFile(docx_path, "r") as zin:
        files = {name: zin.read(name) for name in zin.namelist()}

    root = ET.fromstring(files["word/document.xml"])
    replaced_tokens = 0
    scanned_runs = 0

    parent_map = {child: parent for parent in root.iter() for child in parent}
    for run in list(root.iter(qn("r"))):
        scanned_runs += 1
        texts = [child for child in list(run) if child.tag == qn("t")]
        if len(texts) != 1:
            continue
        visible_text = texts[0].text or ""
        if not visible_text:
            continue

        token_to_keys = dict(literal_map)
        if ref_num_to_key:
            token_to_keys.update(find_numeric_tokens(visible_text, ref_num_to_key))
        if not token_to_keys:
            continue

        replacement, replaced = replace_tokens_in_run(run, token_to_keys, item_lookup, user_id)
        if replacement is None:
            continue

        parent = parent_map.get(run)
        if parent is None or parent.tag == qn("del"):
            continue
        children = list(parent)
        idx = children.index(run)
        parent.remove(run)
        for offset, elem in enumerate(replacement):
            parent.insert(idx + offset, elem)
        replaced_tokens += replaced

    files["word/document.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in files.items():
            zout.writestr(name, data)

    print(
        json.dumps(
            {
                "docx": str(docx_path),
                "backup": str(backup),
                "citations_inserted": replaced_tokens,
                "runs_scanned": scanned_runs,
                "numeric_mapping_entries": len(ref_num_to_key),
                "literal_mapping_entries": len(literal_map),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
