"""Verify ``testset.json`` against the extracted corpus.

Every answerable question carries ``evidence``: verbatim quotes from the
papers (one per supporting document). This script checks that each quote
really occurs in the corresponding ``dataset/<doc_id>.md`` and fills in
``source_section`` / ``source_page`` from where the first quote sits. For
``unanswerable`` questions it checks that every ``absent_terms`` entry occurs
nowhere in the corpus, i.e. the question truly cannot be answered from it.

Exits non-zero if anything fails, so it can gate the eval. Run with ``--write``
to persist the filled-in section/page fields back into ``testset.json``.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import sys
import unicodedata

EVAL_DIR = pathlib.Path(__file__).resolve().parent
DATASET_DIR = EVAL_DIR / "dataset"
TESTSET = EVAL_DIR / "testset.json"

_PAGE = re.compile(r"<!-- page: (\d+) -->")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("−", "-").replace("‐", "-").replace("‑", "-")
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"[“”]", '"', text)
    return re.sub(r"\s+", " ", text).strip().lower()


class Doc:
    """A document flattened to one normalized string, with heading/page offsets."""

    def __init__(self, path: pathlib.Path) -> None:
        self.text = ""
        self.markers: list[tuple[int, str, str]] = []  # (offset, kind, value)
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            m = _PAGE.match(line)
            if m:
                self.markers.append((len(self.text), "page", m.group(1)))
                continue
            if line.startswith("## "):
                self.markers.append((len(self.text), "section", line[3:].strip()))
                self.text += norm(line[3:]) + " "
                continue
            if line.startswith("# "):
                continue
            self.text += norm(line) + " "

    def locate(self, quote: str) -> tuple[str, str] | None:
        """Return (section, page) of the quote, or None if it is absent."""
        pos = self.text.find(norm(quote))
        if pos < 0:
            return None
        section, page = "", "1"
        for off, kind, value in self.markers:
            if off > pos:
                break
            if kind == "section":
                section = value
            else:
                page = value
        return section, page


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write section/page back to testset.json")
    args = parser.parse_args()

    manifest_ids = {r["doc_id"] for r in csv.DictReader((DATASET_DIR / "manifest.csv").open(encoding="utf-8"))}
    docs = {p.stem: Doc(p) for p in DATASET_DIR.glob("*.md") if p.stem in manifest_ids}
    items = json.loads(TESTSET.read_text(encoding="utf-8"))
    errors: list[str] = []
    counts: dict[str, int] = {}
    seen_ids: set[str] = set()

    for item in items:
        qid = item["id"]
        if qid in seen_ids:
            errors.append(f"{qid}: duplicate id")
        seen_ids.add(qid)
        counts[item["type"]] = counts.get(item["type"], 0) + 1

        if item["type"] == "unanswerable":
            for term in item.get("absent_terms", []):
                hits = [d for d, doc in docs.items() if re.search(r"(?<!\w)" + re.escape(norm(term)) + r"(?!\w)", doc.text)]
                if hits:
                    errors.append(f"{qid}: absent term {term!r} appears in {hits}")
            if not item.get("absent_terms"):
                errors.append(f"{qid}: unanswerable item needs absent_terms")
            continue

        first = True
        for ev in item["evidence"]:
            doc = docs.get(ev["document"])
            if doc is None:
                errors.append(f"{qid}: unknown document {ev['document']!r}")
                continue
            loc = doc.locate(ev["quote"])
            if loc is None:
                errors.append(f"{qid}: quote not found in {ev['document']}: {ev['quote'][:70]!r}")
                continue
            ev["section"], ev["page"] = loc
            if first:
                item["source_document"] = ev["document"]
                item["source_section"], item["source_page"] = loc
                first = False
        item["source_documents"] = [ev["document"] for ev in item["evidence"]]

    print(f"{len(items)} questions: {counts}")
    if errors:
        print("FAILED:")
        for e in errors:
            print("  -", e)
        return 1
    if args.write:
        TESTSET.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {TESTSET}")
    print("all evidence quotes and absence checks verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
