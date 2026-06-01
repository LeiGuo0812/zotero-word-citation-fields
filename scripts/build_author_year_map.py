#!/usr/bin/env python3
import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path


def normalize_surname(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return raw
    raw = re.sub(r"\s+", " ", raw)
    return raw


def parse_year(raw: str | None) -> str | None:
    if not raw:
        return None
    match = re.search(r"(\d{4})", raw)
    return match.group(1) if match else None


def load_collection_items(db_path: Path, collection_id: int | None, collection_name: str | None) -> list[dict]:
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
        SELECT i.itemID, i.key,
               MAX(CASE WHEN f.fieldName='date' THEN v.value END) AS date,
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

    items: list[dict] = []
    for row in cur.fetchall():
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
        creators = cur.fetchall()
        items.append(
            {
                "key": row["key"],
                "title": row["title"],
                "year": parse_year(row["date"]),
                "creators": creators,
            }
        )
    return items


def generate_tokens(item: dict) -> list[str]:
    creators = item["creators"]
    year = item["year"]
    if not creators or not year:
        return []

    surnames = [normalize_surname(c["lastName"] or c["firstName"] or "") for c in creators]
    surnames = [s for s in surnames if s]
    if not surnames:
        return []

    if len(surnames) == 1:
        lead = surnames[0]
        return [f"({lead}, {year})", f"{lead} ({year})"]
    if len(surnames) == 2:
        a, b = surnames[:2]
        return [
            f"({a} and {b}, {year})",
            f"({a} & {b}, {year})",
            f"{a} and {b} ({year})",
            f"{a} & {b} ({year})",
        ]

    lead = surnames[0]
    return [f"({lead} et al., {year})", f"{lead} et al. ({year})"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a literal author-year citation map from a Zotero collection.")
    parser.add_argument("--db", required=True, type=Path, help="Path to zotero.sqlite")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--collection-id", type=int)
    group.add_argument("--collection-name")
    parser.add_argument("--out", required=True, type=Path, help="Output JSON file")
    parser.add_argument(
        "--unresolved-out",
        type=Path,
        help="Optional JSON report for ambiguous or skipped items",
    )
    args = parser.parse_args()

    items = load_collection_items(args.db.expanduser(), args.collection_id, args.collection_name)
    token_to_keys: dict[str, list[str]] = defaultdict(list)
    skipped: list[dict] = []

    for item in items:
        tokens = generate_tokens(item)
        if not tokens:
            skipped.append(
                {"key": item["key"], "title": item["title"], "reason": "missing author or year"}
            )
            continue
        for token in tokens:
            token_to_keys[token].append(item["key"])

    mapping: dict[str, str | list[str]] = {}
    ambiguous: dict[str, list[str]] = {}
    for token, keys in sorted(token_to_keys.items()):
        unique_keys = sorted(set(keys))
        if len(unique_keys) == 1:
            mapping[token] = unique_keys[0]
        else:
            ambiguous[token] = unique_keys

    args.out.expanduser().write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {
        "path": str(args.out.expanduser().resolve()),
        "count": len(mapping),
        "ambiguous_tokens": len(ambiguous),
        "skipped_items": len(skipped),
    }
    if args.unresolved_out:
        report = {"ambiguous": ambiguous, "skipped": skipped}
        args.unresolved_out.expanduser().write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        result["unresolved_report"] = str(args.unresolved_out.expanduser().resolve())
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
