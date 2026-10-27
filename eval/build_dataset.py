"""Build the research-paper corpus the eval runs against.

Reads every PDF in ``dataset/raw/``, extracts it with the **production**
extractor (``backend/app/services/extractor.extract_blocks`` -> the same code
path an upload takes, OCR fallback included), lightly cleans the text, and
writes one markdown file per paper to ``dataset/`` plus ``dataset/manifest.csv``
(the provenance record the report and presentation cite).

Bibliographic metadata (short_name, title, authors, year) comes from the checked-in
``dataset/sources.csv`` keyed by arXiv id; PDFs are expected to be named
``<arxiv_id>.pdf``. ``--download`` fetches any missing PDFs from arxiv.org by
id (a fixed, curated list — not scraping).

Idempotent: re-running overwrites the same files with the same content.

    python build_dataset.py            # build from dataset/raw/*.pdf
    python build_dataset.py --download # fetch missing PDFs first
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import re
import sys
import time
import unicodedata
import urllib.request

_BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.services.extractor import (  # noqa: E402
    blocks_to_text,
    count_words,
    extract_blocks,
    page_count,
)

EVAL_DIR = pathlib.Path(__file__).resolve().parent
DATASET_DIR = EVAL_DIR / "dataset"
RAW_DIR = DATASET_DIR / "raw"
SOURCES_CSV = DATASET_DIR / "sources.csv"
MANIFEST_CSV = DATASET_DIR / "manifest.csv"

# "3 Method", "3.2 Dense Retrieval", "A.1 Details" style section headings.
_NUMBERED_HEADING = re.compile(r"^(?:[A-Z]|\d{1,2})(?:\.\d{1,2}){0,2}\.?\s+[A-Z][A-Za-z0-9\-:,&()/' ]{2,70}$")
_PLAIN_HEADING = re.compile(
    r"^(abstract|introduction|related work|background|conclusions?|discussion|"
    r"limitations|acknowledg(?:e)?ments|references|appendix(?:\s+[A-Z])?|"
    r"experiments|results|methods?|evaluation|analysis)$",
    re.IGNORECASE,
)
_PAGE_NUMBER_ONLY = re.compile(r"^\d{1,3}$")
_SECTION_NUMBER = re.compile(r"^(?:[1-9]|1[0-2]|[A-D])(?:\.\d{1,2}){0,2}\.?$")


def slugify(name: str) -> str:
    """Stable doc_id: lower-case slug of the paper's short title."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def is_heading(line: str) -> bool:
    line = line.strip()
    if not line or len(line.split()) > 10 or line.endswith("."):
        return False
    if _PLAIN_HEADING.match(line):
        return True
    return bool(_NUMBERED_HEADING.match(line)) and any(c.islower() for c in line)


def clean_page(text: str) -> list[tuple[bool, str]]:
    """Turn one page of raw PyMuPDF text into (is_heading, text) paragraphs.

    Hard-wrapped lines are joined into paragraphs and line-end hyphenation is
    undone, so the sentence splitter sees real sentences. Headings are kept as
    their own paragraphs.
    """
    text = unicodedata.normalize("NFKC", text)  # ligatures (ﬁ -> fi), odd spaces
    out: list[tuple[bool, str]] = []
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append((False, re.sub(r"\s+", " ", " ".join(para)).strip()))
            para.clear()

    lines = text.splitlines()
    # PyMuPDF often emits "3" and "Method" as two lines; re-join section numbers
    # with the title line that follows them.
    merged: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if _SECTION_NUMBER.match(line) and nxt and is_heading(f"{line} {nxt}"):
            merged.append(f"{line} {nxt}")
            i += 2
            continue
        merged.append(line)
        i += 1

    for raw in merged:
        line = raw.strip()
        if not line or _PAGE_NUMBER_ONLY.match(line):
            flush()
            continue
        if is_heading(line):
            flush()
            out.append((True, line))
            continue
        if para and para[-1].endswith("-") and line[:1].islower():
            para[-1] = para[-1][:-1] + line  # undo line-end hyphenation
        else:
            para.append(line)
    flush()
    return [(h, t) for h, t in out if t]


def build_markdown(title: str, blocks: list[dict]) -> str:
    """Render extractor blocks as markdown: ``# title``, page markers, headings.

    References are dropped (up to an appendix heading, if any): they are
    bibliographic noise that would otherwise dominate lexical matching.
    """
    lines = [f"# {title}", ""]
    in_references = False
    for block in blocks:
        page_lines: list[str] = []
        for heading, text in clean_page(block["text"]):
            if heading:
                if _PLAIN_HEADING.match(text) and text.lower() == "references":
                    in_references = True
                    continue
                if in_references and re.match(r"^(appendix|[A-Z](\.\d)?\s)", text):
                    in_references = False
                if in_references:
                    continue
                page_lines.append(f"## {text}")
            elif not in_references:
                page_lines.append(text)
        if page_lines:
            lines.append(f"<!-- page: {block.get('page', 1)} -->")
            lines.append("")
            for pl in page_lines:
                lines.append(pl)
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def download_missing(sources: list[dict]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for src in sources:
        target = RAW_DIR / f"{src['arxiv_id']}.pdf"
        if target.exists() and target.stat().st_size > 0:
            continue
        url = f"https://arxiv.org/pdf/{src['arxiv_id']}"
        print(f"downloading {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (course project; PaperTrail)"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            target.write_bytes(resp.read())
        time.sleep(3)  # be polite to arxiv.org


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--download", action="store_true", help="fetch missing PDFs by arXiv id first")
    args = parser.parse_args()

    with SOURCES_CSV.open(encoding="utf-8", newline="") as f:
        sources = list(csv.DictReader(f))
    if args.download:
        download_missing(sources)

    pdfs = sorted(RAW_DIR.glob("*.pdf")) if RAW_DIR.exists() else []
    if not pdfs:
        print(f"No PDFs in {RAW_DIR}. Drop the corpus PDFs there (named <arxiv_id>.pdf) or pass --download.")
        return 1

    by_id = {s["arxiv_id"]: s for s in sources}
    rows: list[dict] = []
    for pdf in pdfs:
        meta = by_id.get(pdf.stem)
        if meta is None:
            print(f"skipping {pdf.name}: not listed in sources.csv")
            continue
        blocks = extract_blocks(pdf.read_bytes(), "pdf")  # production extractor
        raw_text = blocks_to_text(blocks)
        doc_id = slugify(meta["short_name"])
        md = build_markdown(meta["title"], blocks)
        (DATASET_DIR / f"{doc_id}.md").write_text(md, encoding="utf-8")
        rows.append(
            {
                "doc_id": doc_id,
                "title": meta["title"],
                "authors": meta["authors"],
                "year": meta["year"],
                "arxiv_id_or_url": f"https://arxiv.org/abs/{meta['arxiv_id']}",
                "n_words": count_words(raw_text),
                "n_pages": page_count(blocks),
                "source_pdf": f"raw/{pdf.name}",
            }
        )

    rows.sort(key=lambda r: r["doc_id"])
    fields = ["doc_id", "title", "authors", "year", "arxiv_id_or_url", "n_words", "n_pages", "source_pdf"]
    with MANIFEST_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{'doc_id':<58} {'year':<5} {'words':>7} {'pages':>5}")
    for r in rows:
        print(f"{r['doc_id']:<58} {r['year']:<5} {r['n_words']:>7} {r['n_pages']:>5}")
    total = sum(r["n_words"] for r in rows)
    print(f"{len(rows)} documents, {total} words, wrote {MANIFEST_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
