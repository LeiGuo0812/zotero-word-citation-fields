#!/usr/bin/env python3
import argparse
import json
import sqlite3
from pathlib import Path


def build_map(db_path: Path, collection_id: int | None, collection_name: str | None) -> dict[int, str]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    if collection_id is None:
        cur.execute("SELECT collectionID, collectionName FROM collections WHERE collectionName = ?", (collection_name,))
        rows = cur.fetchall()
        if not rows:
            raise SystemExit(f"Collection not found: {collection_name}")
        if len(rows) > 1:
            ids = ", ".join(str(row["collectionID"]) for row in rows)
            raise SystemExit(f"Multiple collections named {collection_name!r}: {ids}. Use --collection-id.")
        collection_id = rows[0]["collectionID"]

    cur.execute(
        """
        SELECT i.key,
               MAX(CASE WHEN f.fieldName='callNumber' THEN v.value END) AS callNumber,
               MAX(CASE WHEN f.fieldName='title' THEN v.value END) AS title
        FROM collectionItems ci
        JOIN items i ON i.itemID = ci.itemID
        LEFT JOIN itemData d ON d.itemID = i.itemID
        LEFT JOIN fields f ON f.fieldID = d.fieldID
        LEFT JOIN itemDataValues v ON v.valueID = d.valueID
        WHERE ci.collectionID = ?
        GROUP BY i.itemID, i.key
        """,
        (collection_id,),
    )

    mapping: dict[int, str] = {}
    missing: list[str] = []
    duplicates: list[str] = []

    for row in cur.fetchall():
        call_number = (row["callNumber"] or "").strip()
        title = row["title"] or row["key"]
        if not call_number or not call_number.isdigit():
            missing.append(title)
            continue
        ref_num = int(call_number)
        if ref_num in mapping:
            duplicates.append(str(ref_num))
            continue
        mapping[ref_num] = row["key"]

    if duplicates:
        raise SystemExit(f"Duplicate numeric callNumber values in collection: {', '.join(sorted(set(duplicates)))}")

    if not mapping:
        raise SystemExit("No numeric callNumber values were found in the target collection.")

    if missing:
        print(json.dumps({"warning": "Some items were skipped because callNumber was missing or non-numeric", "items": missing}, ensure_ascii=False))

    return dict(sorted(mapping.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reference-number to Zotero item-key map from a Zotero collection.")
    parser.add_argument("--db", required=True, type=Path, help="Path to zotero.sqlite")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--collection-id", type=int)
    group.add_argument("--collection-name")
    parser.add_argument("--out", required=True, type=Path, help="Output JSON file")
    args = parser.parse_args()

    mapping = build_map(args.db.expanduser(), args.collection_id, args.collection_name)
    args.out.expanduser().write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"path": str(args.out.expanduser().resolve()), "count": len(mapping)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
