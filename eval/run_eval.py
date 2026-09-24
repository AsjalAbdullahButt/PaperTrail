"""Evaluation harness for the chunking ablation.

For each question in ``testset.json``, for each chunking strategy
('character' vs 'sentence'), this script:

1. Retrieves the top-k chunks for the question against that strategy's index.
2. Records whether the expected source document is among the retrieved
   chunks' source documents (retrieval hit rate) and whether the exact
   expected section is among them (a stricter hit measure).
3. Generates an answer from the retrieved chunks via the same
   ``llm.generate_answer`` production uses.
4. Scores the generated answer with an LLM-as-judge pass (faithfulness +
   relevance, 1-5) and leaves a blank column for the student's manual score.

Outputs, per strategy, a raw per-question CSV under ``results/`` and a single
aggregate ``results/summary.md`` comparing both strategies.

Run from the ``eval/`` directory (or anywhere, since paths are resolved
relative to this file): ``python run_eval.py``
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
from dataclasses import asdict, dataclass

import pipeline as p

EVAL_DIR = pathlib.Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"
TOP_K = 5

_JUDGE_SYSTEM = (
    "You are a strict evaluator of a RAG system's answers. Given a question, "
    "the retrieved context passages actually given to the answering model, and "
    "the model's generated answer, score two things on a 1-5 integer scale: "
    "\n- faithfulness: is every claim in the answer actually supported by the "
    "retrieved context (1 = mostly unsupported/hallucinated, 5 = fully "
    "grounded in the context)?"
    "\n- relevance: does the answer actually address the question asked "
    "(1 = off-topic or non-answer, 5 = directly and completely answers it)?"
    "\nRespond with ONLY a JSON object of the exact form "
    '{"faithfulness": <int 1-5>, "relevance": <int 1-5>, "rationale": "<one sentence>"}. '
    "No markdown, no other text."
)


@dataclass
class QuestionResult:
    id: str
    question: str
    expected_answer: str
    source_document: str
    source_section: str
    strategy: str
    retrieved_chunk_ids: str
    retrieved_doc_ids: str
    doc_hit: bool
    section_hit: bool
    generated_answer: str
    faithfulness: str
    relevance: str
    judge_rationale: str
    manual_score: str = ""  # left blank for the student to fill in


def _load_testset() -> list[dict]:
    return json.loads((EVAL_DIR / "testset.json").read_text(encoding="utf-8"))


def _judge(question: str, context_chunks: list[str], answer: str) -> tuple[str, str, str]:
    """Return (faithfulness, relevance, rationale) as strings.

    In offline mode (no OPENAI_API_KEY/GROQ_API_KEY configured),
    ``llm.complete_text`` returns "" — there is no model to act as a judge,
    so all three fields come back as "n/a (offline)" rather than a fabricated
    score. This is called out explicitly in REPORT.md's limitations section.
    """
    context = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(context_chunks))
    prompt = f"Question: {question}\n\nRetrieved context:\n{context}\n\nGenerated answer:\n{answer}"
    raw = p.llm.complete_text(prompt, system=_JUDGE_SYSTEM, temperature=0.0)
    if not raw:
        return "n/a (offline)", "n/a (offline)", "no chat model configured for judging"
    try:
        data = json.loads(raw)
        return str(data.get("faithfulness", "")), str(data.get("relevance", "")), str(data.get("rationale", ""))
    except json.JSONDecodeError:
        # Best-effort salvage: pull the first two small integers out of the text.
        nums = re.findall(r"\b[1-5]\b", raw)
        f = nums[0] if len(nums) > 0 else ""
        r = nums[1] if len(nums) > 1 else ""
        return f, r, f"unparsed judge output: {raw[:200]}"


def run_strategy(strategy: str, documents: list, testset: list[dict]) -> list[QuestionResult]:
    index = p.build_index(strategy, documents)
    results: list[QuestionResult] = []
    for item in testset:
        retrieved = p.retrieve(item["question"], index, k=TOP_K)
        retrieved_doc_ids = [r.chunk.doc_id for r in retrieved]
        expected_doc = item["source_document"].removesuffix(".md")
        doc_hit = expected_doc in retrieved_doc_ids
        section_hit = any(
            r.chunk.doc_id == expected_doc
            and r.chunk.section_heading
            and r.chunk.section_heading.strip().lower() == item["source_section"].strip().lower()
            for r in retrieved
        )
        answer = p.generate(item["question"], retrieved)
        faithfulness, relevance, rationale = _judge(
            item["question"], [r.chunk.text for r in retrieved], answer
        )
        results.append(
            QuestionResult(
                id=item["id"],
                question=item["question"],
                expected_answer=item["expected_answer"],
                source_document=item["source_document"],
                source_section=item["source_section"],
                strategy=strategy,
                retrieved_chunk_ids="; ".join(r.chunk.chunk_id for r in retrieved),
                retrieved_doc_ids="; ".join(retrieved_doc_ids),
                doc_hit=doc_hit,
                section_hit=section_hit,
                generated_answer=answer,
                faithfulness=faithfulness,
                relevance=relevance,
                judge_rationale=rationale,
            )
        )
    return results


def _write_csv(strategy: str, results: list[QuestionResult]) -> pathlib.Path:
    out_path = RESULTS_DIR / f"raw_{strategy}.csv"
    fieldnames = list(asdict(results[0]).keys())
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))
    return out_path


def _numeric_avg(results: list[QuestionResult], field: str) -> str:
    values = [int(getattr(r, field)) for r in results if getattr(r, field).isdigit()]
    if not values:
        return "n/a"
    return f"{sum(values) / len(values):.2f}"


def _write_summary(all_results: dict[str, list[QuestionResult]]) -> pathlib.Path:
    lines = ["# Evaluation Summary", ""]
    lines.append("| Strategy | Doc-level hit rate | Section-level hit rate | Avg faithfulness | Avg relevance |")
    lines.append("|---|---|---|---|---|")
    for strategy, results in all_results.items():
        n = len(results)
        doc_hits = sum(r.doc_hit for r in results)
        section_hits = sum(r.section_hit for r in results)
        lines.append(
            f"| {strategy} | {doc_hits}/{n} ({doc_hits / n:.0%}) | "
            f"{section_hits}/{n} ({section_hits / n:.0%}) | "
            f"{_numeric_avg(results, 'faithfulness')} | {_numeric_avg(results, 'relevance')} |"
        )
    lines.append("")

    lines.append("## Questions where strategies disagreed on the doc-level hit")
    lines.append("")
    strategies = list(all_results.keys())
    if len(strategies) == 2:
        by_id = {s: {r.id: r for r in all_results[s]} for s in strategies}
        s1, s2 = strategies
        disagreements = [
            qid for qid in by_id[s1]
            if by_id[s1][qid].doc_hit != by_id[s2][qid].doc_hit
        ]
        if not disagreements:
            lines.append("None — both strategies hit or missed the same questions.")
        for qid in disagreements:
            r1, r2 = by_id[s1][qid], by_id[s2][qid]
            lines.append(f"- **{qid}** — {r1.question}")
            lines.append(f"  - `{s1}` hit={r1.doc_hit}, retrieved docs: {r1.retrieved_doc_ids}")
            lines.append(f"  - `{s2}` hit={r2.doc_hit}, retrieved docs: {r2.retrieved_doc_ids}")
    lines.append("")
    out_path = RESULTS_DIR / "summary.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    documents = p.load_documents()
    testset = _load_testset()

    all_results: dict[str, list[QuestionResult]] = {}
    for strategy in ("character", "sentence"):
        print(f"Running strategy: {strategy} ...")
        results = run_strategy(strategy, documents, testset)
        all_results[strategy] = results
        out = _write_csv(strategy, results)
        print(f"  wrote {out}")

    summary_path = _write_summary(all_results)
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
