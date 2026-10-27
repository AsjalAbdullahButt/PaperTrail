"""Ask the corpus a question from the command line (live-demo helper).

Runs the same pipeline the eval measures — production chunking, embeddings,
hybrid retrieval, production answer generation — and prints the answer with the
numbered passages it cites (paper, page, section). Needs a working LLM key in
backend/.env for the answer; retrieval alone works with ``--retrieval-only``.

    python ask.py "Why is BERT unsuitable for sentence-pair similarity search?"
    python ask.py --embedder hf --mode dense --retrieval-only "What is MaxSim?"
"""
from __future__ import annotations

import argparse
import sys

import pipeline as p
from app.services.hallucination_guard import check_answer


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("question")
    ap.add_argument("--chunker", default="sentence800", choices=list(p.CHUNKERS))
    ap.add_argument("--mode", default="hybrid", choices=["dense", "hybrid"])
    ap.add_argument("--embedder", default="openai", choices=["openai", "hf"])
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--retrieval-only", action="store_true")
    args = ap.parse_args()

    index = p.build_index(args.chunker, p.load_documents(), args.embedder)
    retrieved = p.retrieve(args.question, index, mode=args.mode, k=args.k)

    if not args.retrieval_only:
        answer = p.generate(args.question, retrieved)
        print(f"\n{answer}\n")
        flagged = [g["sentence"] for g in check_answer(
            answer, [{"chunk_id": r.chunk.chunk_id, "text": r.chunk.text} for r in retrieved]) if not g["supported"]]
        if flagged:
            print(f"[lexical grounding heuristic flagged {len(flagged)} sentence(s) with weak overlap to the sources]\n")
    for i, r in enumerate(retrieved, start=1):
        c = r.chunk
        snippet = c.text[:220].replace("\n", " ")
        print(f"[{i}] {c.doc_id}, p.{c.page_number}, sec. {c.section_heading or '—'} (score {r.score:.3f})\n    {snippet}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
