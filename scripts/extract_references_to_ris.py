#!/usr/bin/env python3
import argparse
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from difflib import SequenceMatcher
from pathlib import Path


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"


def visible_paragraphs(docx_path: Path) -> list[str]:
    with zipfile.ZipFile(docx_path, "r") as zin:
        root = ET.fromstring(zin.read("word/document.xml"))
    body = root.find(f"{W}body")
    paragraphs: list[str] = []
    for para in body.findall(f"{W}p"):
        parts = []
        for child in list(para):
            if child.tag == f"{W}del":
                continue
            for t in child.iter(f"{W}t"):
                if t.text:
                    parts.append(t.text)
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def extract_reference_section(paragraphs: list[str], heading: str | None) -> list[str]:
    headings = {heading.lower()} if heading else {"references", "reference", "bibliography"}
    start = None
    for i, para in enumerate(paragraphs):
        if para.strip().lower() in headings:
            start = i + 1
            break
    if start is None:
        raise SystemExit("Could not find a reference section heading. Use --heading if needed.")
    refs = [p for p in paragraphs[start:] if p.strip()]
    if not refs:
        raise SystemExit("Reference section was found but no reference paragraphs were extracted.")
    return refs


def find_doi(text: str) -> str | None:
    match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", text, flags=re.I)
    return match.group(1).rstrip(".,;)") if match else None


def get_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Codex Zotero Word Citation Fields Skill/1.0 (crossref validation)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 ]+", " ", text)).strip().lower()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def crossref_lookup(reference: str) -> dict:
    doi = find_doi(reference)
    if doi:
        data = get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")
        return {"source": "doi", "reference": reference, "message": data["message"], "score": 1.0}

    query = urllib.parse.urlencode({"query.bibliographic": reference, "rows": 1})
    data = get_json(f"https://api.crossref.org/works?{query}")
    items = data.get("message", {}).get("items", [])
    if not items:
        return {"source": "search", "reference": reference, "message": None, "score": 0.0}
    item = items[0]
    title = " ".join(item.get("title", []))
    score = max(similarity(reference, title), similarity(reference, item.get("container-title", [""])[0]))
    return {"source": "search", "reference": reference, "message": item, "score": score}


def crossref_to_ris(message: dict) -> str:
    item_type = message.get("type", "")
    ris_type = {
        "journal-article": "JOUR",
        "book": "BOOK",
        "book-chapter": "CHAP",
        "proceedings-article": "CPAPER",
        "report": "RPRT",
    }.get(item_type, "GEN")

    lines = [f"TY  - {ris_type}"]
    for author in message.get("author", []):
        given = author.get("given", "")
        family = author.get("family", "")
        if family or given:
            lines.append(f"AU  - {family}, {given}".rstrip(", "))
    title = " ".join(message.get("title", []))
    if title:
        lines.append(f"TI  - {title}")
    journal = " ".join(message.get("container-title", []))
    if journal:
        lines.append(f"JO  - {journal}")
    year = None
    date_parts = message.get("issued", {}).get("date-parts", [])
    if date_parts and date_parts[0]:
        year = str(date_parts[0][0])
        lines.append(f"PY  - {year}")
    if message.get("volume"):
        lines.append(f"VL  - {message['volume']}")
    if message.get("issue"):
        lines.append(f"IS  - {message['issue']}")
    if message.get("page"):
        lines.append(f"SP  - {message['page']}")
    if message.get("DOI"):
        lines.append(f"DO  - {message['DOI']}")
    if message.get("URL"):
        lines.append(f"UR  - {message['URL']}")
    lines.append("ER  - ")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Word references, validate them against Crossref, and generate RIS.")
    parser.add_argument("--docx", required=True, type=Path, help="Path to the source .docx")
    parser.add_argument("--out-ris", required=True, type=Path, help="Output RIS path")
    parser.add_argument("--out-report", required=True, type=Path, help="Output validation report JSON")
    parser.add_argument("--heading", help="Reference section heading, e.g. References")
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.78,
        help="Minimum similarity score for non-DOI Crossref matches",
    )
    args = parser.parse_args()

    paragraphs = visible_paragraphs(args.docx.expanduser().resolve())
    references = extract_reference_section(paragraphs, args.heading)

    resolved = []
    unresolved = []
    ris_entries = []

    for idx, reference in enumerate(references, start=1):
        result = crossref_lookup(reference)
        message = result["message"]
        if message is None:
            unresolved.append({"index": idx, "reference": reference, "reason": "no_crossref_match"})
            continue
        if result["source"] != "doi" and result["score"] < args.min_score:
            unresolved.append(
                {
                    "index": idx,
                    "reference": reference,
                    "reason": "low_confidence_match",
                    "score": result["score"],
                    "candidate_title": " ".join(message.get("title", [])),
                    "candidate_doi": message.get("DOI"),
                }
            )
            continue

        resolved.append(
            {
                "index": idx,
                "reference": reference,
                "source": result["source"],
                "score": result["score"],
                "title": " ".join(message.get("title", [])),
                "doi": message.get("DOI"),
            }
        )
        ris_entries.append(crossref_to_ris(message))

    args.out_ris.expanduser().write_text("\n\n".join(ris_entries) + ("\n" if ris_entries else ""), encoding="utf-8")
    args.out_report.expanduser().write_text(
        json.dumps(
            {
                "docx": str(args.docx.expanduser().resolve()),
                "references_found": len(references),
                "resolved": resolved,
                "unresolved": unresolved,
                "ris_path": str(args.out_ris.expanduser().resolve()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "references_found": len(references),
                "resolved": len(resolved),
                "unresolved": len(unresolved),
                "ris_path": str(args.out_ris.expanduser().resolve()),
                "report_path": str(args.out_report.expanduser().resolve()),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
