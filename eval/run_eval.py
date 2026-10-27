"""Evaluation harness for PaperTrail's RAG pipeline over the NLP-paper corpus.

A *configuration* is (chunker, retrieval mode, embedder), e.g.
``character__hybrid__hf``. For every question in ``testset.json`` and every
configuration this script:

1. retrieves the top-k chunks (dense cosine, or the production hybrid fusion);
2. scores retrieval against the gold evidence: document recall@k, evidence
   recall@k (does a retrieved chunk actually contain the supporting quote?),
   evidence MRR, and section hit;
3. (unless ``--no-generate``) generates an answer with ``llm.generate_answer``
   and scores it: LLM-as-judge correctness / faithfulness / relevance /
   abstention, citation accuracy (do the cited [n] passages contain the
   evidence?), and the lexical hallucination guard's unsupported-sentence rate.

Outputs: ``results/raw_<config>.csv`` per configuration, ``results/summary.md``
with every table (generated, never hand-edited), and ``results/run_meta.json``.

``--require-online`` (default ON) aborts if the run would silently degrade to
the offline hashing embedder or the offline extractive answerer: a submitted
run must use real embeddings and a real LLM.

    python run_eval.py                         # full grid, with generation + judge
    python run_eval.py --no-generate           # retrieval metrics only
    python run_eval.py --configs character__hybrid__hf --limit 5
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import logging
import pathlib
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field

import numpy as np

import pipeline as p
from app.config import settings
from app.services.hallucination_guard import check_answer

EVAL_DIR = pathlib.Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"
TOP_K = 5

# --- the experiment grid ---------------------------------------------------- #
CHUNKERS = ["character", "sentence", "sentence800"]
MODES = ["dense", "hybrid"]
# HF MiniLM truncates at 256 word-pieces (~1,000 chars), so it is only paired
# with ~800-char chunkers; pairing it with the ~3,000-char sentence chunker
# would silently embed only the first third of each chunk.
EMBEDDERS_FOR = {"character": ["openai", "hf"], "sentence": ["openai"], "sentence800": ["openai", "hf"]}
ALL_CONFIGS = [f"{c}__{m}__{e}" for c in CHUNKERS for m in MODES for e in EMBEDDERS_FOR[c]]

_JUDGE_SYSTEM = (
    "You are a strict evaluator of a retrieval-augmented QA system. You are given a question, a "
    "reference answer, the retrieved context passages that were given to the answering model, and the "
    "model's generated answer. Score the generated answer on:\n"
    "- correctness (1-5): agreement with the reference answer (5 = fully correct and complete, 3 = "
    "partially correct, 1 = wrong, contradicts the reference, or says the information was not found "
    "when the reference contains it). If the reference says the question is NOT answerable from the "
    "corpus, give 5 only if the answer clearly says the documents do not contain it, else 1.\n"
    "- faithfulness (1-5): is every claim in the answer supported by the retrieved context "
    "(1 = mostly unsupported / hallucinated, 5 = fully grounded)? An answer that only states the "
    "information is not in the documents is fully faithful (5).\n"
    "- relevance (1-5): does the answer address the question asked (1 = off-topic, 5 = directly "
    "and completely)?\n"
    "- abstained (true/false): does the answer say it could not find / the documents do not contain "
    "the requested information, rather than asserting an answer?\n"
    'Respond with ONLY a JSON object: {"correctness": <int>, "faithfulness": <int>, "relevance": <int>, '
    '"abstained": <true|false>, "rationale": "<one sentence>"}. No markdown, no other text.'
)

_ABSTAIN_RE = re.compile(
    r"(could not find|couldn't find|cannot find|can't find|not (?:found|mentioned|stated|provided|contained)|"
    r"(?:do(?:es)? not|don't|doesn't) (?:contain|mention|provide|include|specify|state|say)|"
    r"no (?:relevant )?information|not (?:in|present in|covered in) the (?:provided )?(?:documents|context|passages))",
    re.IGNORECASE,
)
_CITE_RE = re.compile(r"\[(\d+)\]")


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #
@dataclass
class Row:
    config: str
    id: str
    type: str
    question: str
    expected_answer: str
    source_documents: str
    retrieved_chunk_ids: str
    retrieved_doc_ids: str
    doc_recall: float | None = None          # fraction of expected docs in top-k
    evidence_recall: float | None = None     # fraction of evidence quotes found in a retrieved chunk
    evidence_mrr: float | None = None        # 1/rank of first chunk containing any evidence
    section_hit: float | None = None
    generated_answer: str = ""
    correctness: int | None = None
    faithfulness: int | None = None
    relevance: int | None = None
    abstained_judge: bool | None = None
    abstained_regex: bool | None = None
    abstain_correct: float | None = None     # unanswerable only: judge says abstained
    n_citations: int | None = None
    n_correct_citations: int | None = None
    guard_unsupported_frac: float | None = None
    judge_rationale: str = ""
    manual_score: str = ""                   # left blank for the human grader


@dataclass
class RunMeta:
    started: str = ""
    chat_model: str = ""
    judge_model: str = ""
    openai_embedding_model: str = ""
    hf_embedding_model: str = ""
    top_k: int = TOP_K
    n_questions: int = 0
    generation: bool = True
    llm_fallback_warnings: int = 0
    judge_parse_failures: int = 0
    notes: list[str] = field(default_factory=list)


class _WarningCounter(logging.Handler):
    """Counts production llm.py fallback warnings so a run can report (or fail on) them."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        self.count += 1


# --------------------------------------------------------------------------- #
# Gold-evidence matching
# --------------------------------------------------------------------------- #
def _norm_tokens(text: str) -> list[str]:
    import unicodedata

    text = unicodedata.normalize("NFKC", text).replace("−", "-").lower()
    return re.findall(r"[a-z0-9]+", text)


def chunk_contains(chunk_text: str, quote: str, threshold: float = 0.85) -> bool:
    """True if the chunk contains the evidence quote (token-level, tolerant of
    whitespace/hyphenation noise): exact token-sequence match, or >= threshold
    of the quote's tokens present."""
    q = _norm_tokens(quote)
    c = _norm_tokens(chunk_text)
    if not q:
        return False
    joined_c = " ".join(c)
    if " ".join(q) in joined_c:
        return True
    cset = set(c)
    return sum(t in cset for t in q) / len(q) >= threshold and len(q) >= 6


def supports(chunk: p.Chunk, ev: dict) -> bool:
    """A chunk supports an evidence entry if it comes from the right paper and
    contains the gold quote, or any of the entry's ``any_of`` phrases (the same
    fact stated elsewhere in the paper, e.g. abstract and introduction)."""
    if chunk.doc_id != ev["document"]:
        return False
    if chunk_contains(chunk.text, ev["quote"]):
        return True
    joined = " ".join(_norm_tokens(chunk.text))
    return any(f" {_phrase(ph)} " in f" {joined} " for ph in ev.get("any_of", []))


def _phrase(text: str) -> str:
    return " ".join(_norm_tokens(text))


def _doc_evidence(item: dict) -> list[dict]:
    return item.get("evidence", [])


# --------------------------------------------------------------------------- #
# Judge / generation with disk caching
# --------------------------------------------------------------------------- #
class LLMCache:
    """Disk cache for generations and judgements, so an interrupted run resumes
    and repeated runs are cheap. Keyed by model + full prompt content."""

    def __init__(self, name: str) -> None:
        p.CACHE_DIR.mkdir(exist_ok=True)
        self.path = p.CACHE_DIR / f"{name}.json"
        self.data: dict[str, str] = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    @staticmethod
    def key(*parts: str) -> str:
        return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()

    def get_or_compute(self, key: str, fn) -> str:
        if key not in self.data:
            self.data[key] = fn()
            self.path.write_text(json.dumps(self.data), encoding="utf-8")
        return self.data[key]


def _chat_model_name() -> str:
    if settings.openai_ready:
        return f"openai:{settings.openai_chat_model}"
    if settings.groq_ready:
        return f"groq:{settings.groq_chat_model}"
    return "offline"


def _retry(fn, *, attempts: int = 4, what: str = "LLM call"):
    last = ""
    for i in range(attempts):
        out = fn()
        if out and not out.startswith("[offline mode]"):
            return out
        last = out
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"{what} kept returning an empty/offline response ({last[:80]!r}); check API keys and rate limits.")


def generate_answer(cache: LLMCache, question: str, retrieved: list[p.Retrieved]) -> str:
    key = cache.key(_chat_model_name(), "gen", question, *[r.chunk.text for r in retrieved])
    return cache.get_or_compute(key, lambda: _retry(lambda: p.generate(question, retrieved), what="Answer generation"))


def judge(cache: LLMCache, meta: RunMeta, item: dict, retrieved: list[p.Retrieved], answer: str) -> dict:
    context = "\n\n".join(f"[{i + 1}] {r.chunk.text}" for i, r in enumerate(retrieved))
    prompt = (
        f"Question: {item['question']}\n\nReference answer: {item['expected_answer']}\n\n"
        f"Retrieved context:\n{context}\n\nGenerated answer:\n{answer}"
    )
    key = cache.key(_chat_model_name(), "judge", prompt)

    def call() -> str:
        return _retry(lambda: p.llm.complete_text(prompt, system=_JUDGE_SYSTEM, temperature=0.0), what="Judge call")

    for attempt in range(2):
        raw = cache.get_or_compute(key, call)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        try:
            data = json.loads(m.group(0)) if m else None
        except json.JSONDecodeError:
            data = None
        if data and all(k in data for k in ("correctness", "faithfulness", "relevance", "abstained")):
            return data
        cache.data.pop(key, None)  # force a fresh call on the retry
    meta.judge_parse_failures += 1
    return {}


# --------------------------------------------------------------------------- #
# Per-question scoring
# --------------------------------------------------------------------------- #
def score_retrieval(item: dict, retrieved: list[p.Retrieved], row: Row) -> None:
    expected_docs = list(dict.fromkeys(item["source_documents"]))
    got_docs = {r.chunk.doc_id for r in retrieved}
    row.doc_recall = sum(d in got_docs for d in expected_docs) / len(expected_docs)

    evidences = _doc_evidence(item)
    hit_flags = []
    first_rank = None
    for ev in evidences:
        found = False
        for rank, r in enumerate(retrieved, start=1):
            if supports(r.chunk, ev):
                found = True
                first_rank = rank if first_rank is None else min(first_rank, rank)
                break
        hit_flags.append(found)
    row.evidence_recall = sum(hit_flags) / len(hit_flags)
    row.evidence_mrr = 1.0 / first_rank if first_rank else 0.0

    sec_hits = [
        any(
            r.chunk.doc_id == ev["document"]
            and r.chunk.section_heading
            and r.chunk.section_heading.strip().lower() == ev.get("section", "").strip().lower()
            for r in retrieved
        )
        for ev in evidences
    ]
    row.section_hit = sum(sec_hits) / len(sec_hits)


def score_generation(
    item: dict, retrieved: list[p.Retrieved], answer: str, row: Row, cache: LLMCache, meta: RunMeta
) -> None:
    row.generated_answer = answer
    verdict = judge(cache, meta, item, retrieved, answer)
    if verdict:
        row.correctness = int(verdict["correctness"])
        row.faithfulness = int(verdict["faithfulness"])
        row.relevance = int(verdict["relevance"])
        row.abstained_judge = bool(verdict["abstained"])
        row.judge_rationale = str(verdict.get("rationale", ""))
    row.abstained_regex = bool(_ABSTAIN_RE.search(answer))

    if item["type"] == "unanswerable":
        if row.abstained_judge is not None:
            row.abstain_correct = 1.0 if row.abstained_judge else 0.0
        return

    # Citation accuracy: does each cited passage [n] contain gold evidence?
    cited = sorted({int(n) for n in _CITE_RE.findall(answer) if 1 <= int(n) <= len(retrieved)})
    row.n_citations = len(cited)
    row.n_correct_citations = sum(
        any(
            supports(retrieved[n - 1].chunk, ev) for ev in _doc_evidence(item)
        )
        for n in cited
    )
    guard = check_answer(answer, [{"chunk_id": r.chunk.chunk_id, "text": r.chunk.text} for r in retrieved])
    row.guard_unsupported_frac = (sum(not g["supported"] for g in guard) / len(guard)) if guard else 0.0


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def _vals(rows: list[Row], attr: str, types: tuple[str, ...] | None = None) -> list[float]:
    return [
        float(getattr(r, attr))
        for r in rows
        if getattr(r, attr) is not None and (types is None or r.type in types)
    ]


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def bootstrap_ci(xs: list[float], n: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    arr = np.asarray(xs, dtype=float)
    means = rng.choice(arr, size=(n, len(arr)), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired_diff(a: list[Row], b: list[Row], attr: str, types: tuple[str, ...]) -> tuple[float, float, float, int] | None:
    """Mean(b - a) over questions both configs scored, with a paired-bootstrap 95% CI."""
    by_a = {r.id: getattr(r, attr) for r in a if r.type in types and getattr(r, attr) is not None}
    diffs = [float(getattr(r, attr)) - float(by_a[r.id]) for r in b if r.id in by_a and getattr(r, attr) is not None]
    if len(diffs) < 5:
        return None
    lo, hi = bootstrap_ci(diffs)
    return sum(diffs) / len(diffs), lo, hi, len(diffs)


ANSWERABLE = ("factual", "multi_hop")


def _fmt(x: float | None, pct: bool = False, nd: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x:.0%}" if pct else f"{x:.{nd}f}"


def _ci(xs: list[float], pct: bool = False) -> str:
    if len(xs) < 5:
        return _fmt(_mean(xs), pct)
    lo, hi = bootstrap_ci(xs)
    m = sum(xs) / len(xs)
    return f"{m:.0%} [{lo:.0%}–{hi:.0%}]" if pct else f"{m:.2f} [{lo:.2f}–{hi:.2f}]"


def retrieval_table(results: dict[str, list[Row]], configs: list[str]) -> list[str]:
    lines = [
        "| Config | Doc Recall@5 (answerable) | Doc Recall@5 (multi-hop) | Evidence Recall@5 | Evidence MRR | Section hit |",
        "|---|---|---|---|---|---|",
    ]
    for c in configs:
        rows = results[c]
        lines.append(
            f"| `{c}` | {_ci(_vals(rows, 'doc_recall', ANSWERABLE), True)} | "
            f"{_fmt(_mean(_vals(rows, 'doc_recall', ('multi_hop',))), True)} | "
            f"{_ci(_vals(rows, 'evidence_recall', ANSWERABLE), True)} | "
            f"{_fmt(_mean(_vals(rows, 'evidence_mrr', ANSWERABLE)))} | "
            f"{_fmt(_mean(_vals(rows, 'section_hit', ANSWERABLE)), True)} |"
        )
    return lines


def generation_table(results: dict[str, list[Row]], configs: list[str]) -> list[str]:
    lines = [
        "| Config | Correctness (1-5) | Faithfulness (1-5) | Relevance (1-5) | Citation accuracy | Citation coverage | Unanswerable handling | Guard unsupported-sentence rate |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in configs:
        rows = results[c]
        cites = sum(r.n_citations or 0 for r in rows if r.type in ANSWERABLE)
        correct = sum(r.n_correct_citations or 0 for r in rows if r.type in ANSWERABLE)
        answered = [r for r in rows if r.type in ANSWERABLE and r.n_citations is not None]
        coverage = sum(1 for r in answered if r.n_citations) / len(answered) if answered else None
        unans = _vals(rows, "abstain_correct", ("unanswerable",))
        lines.append(
            f"| `{c}` | {_ci(_vals(rows, 'correctness', ANSWERABLE))} | "
            f"{_fmt(_mean(_vals(rows, 'faithfulness', ANSWERABLE)))} | "
            f"{_fmt(_mean(_vals(rows, 'relevance', ANSWERABLE)))} | "
            f"{_fmt(correct / cites if cites else None, True)} ({correct}/{cites}) | "
            f"{_fmt(coverage, True)} | "
            f"{_fmt(_mean(unans), True)} ({int(sum(unans))}/{len(unans)}) | "
            f"{_fmt(_mean(_vals(rows, 'guard_unsupported_frac', ANSWERABLE)), True)} |"
        )
    return lines


def comparison_block(
    title: str, note: str, pairs: list[tuple[str, str]], results: dict[str, list[Row]], generation: bool
) -> list[str]:
    """One comparison: for each (A, B) pair, B - A with a paired-bootstrap 95% CI."""
    metrics = [("evidence_recall", "Evidence Recall@5", ANSWERABLE), ("doc_recall", "Doc Recall@5", ANSWERABLE)]
    if generation:
        metrics += [("correctness", "Correctness (1-5)", ANSWERABLE), ("faithfulness", "Faithfulness (1-5)", ANSWERABLE)]
    lines = [f"### {title}", "", note, "", "| A | B | " + " | ".join(f"Δ {m[1]} (B−A)" for m in metrics) + " |",
             "|---|---|" + "---|" * len(metrics)]
    shown = 0
    for a, b in pairs:
        if a not in results or b not in results:
            continue
        shown += 1
        cells = []
        for attr, _, types in metrics:
            d = paired_diff(results[a], results[b], attr, types)
            if d is None:
                cells.append("—")
            else:
                mean, lo, hi, n = d
                sig = " *" if lo > 0 or hi < 0 else ""
                unit = f"{mean:+.1%} [{lo:+.1%}, {hi:+.1%}]" if "recall" in attr else f"{mean:+.2f} [{lo:+.2f}, {hi:+.2f}]"
                cells.append(unit + sig)
        lines.append(f"| `{a}` | `{b}` | " + " | ".join(cells) + " |")
    if not shown:
        lines.append("| _not run_ | _not run_ | " + " | ".join("—" for _ in metrics) + " |")
        lines += ["", "_The configurations for this comparison were not part of this run._"]
    lines += ["", "`*` = the paired-bootstrap 95% interval excludes 0.", ""]
    return lines


def write_summary(results: dict[str, list[Row]], meta: RunMeta, testset: list[dict]) -> pathlib.Path:
    """Write ``summary.md`` plus one snippet file per table under ``results/tables/``
    (``render_docs.py`` injects those snippets into REPORT.md / PRESENTATION.md)."""
    configs = list(results)
    types = {t: sum(1 for i in testset if i["type"] == t) for t in ("factual", "multi_hop", "unanswerable")}
    tables: dict[str, list[str]] = {}

    head = ["# Evaluation Summary", "",
            f"_Generated by `eval/run_eval.py` on {meta.started}. Every number below is computed from the per-question "
            "`raw_<config>.csv` files; nothing is hand-edited._", "",
            f"- Questions: {meta.n_questions} ({types['factual']} factual, {types['multi_hop']} multi-hop, "
            f"{types['unanswerable']} unanswerable); top-k = {meta.top_k}.",
            f"- Embeddings: OpenAI `{meta.openai_embedding_model}` (1536-d) vs Hugging Face `{meta.hf_embedding_model}` (384-d).",
            f"- Configurations evaluated in this run: {len(configs)}."]
    if meta.generation:
        head += [f"- Generator + judge: `{meta.chat_model}` (same model for both; see limitations in REPORT.md).",
                 f"- Production-fallback warnings during the run: {meta.llm_fallback_warnings}; "
                 f"unparseable judge outputs: {meta.judge_parse_failures}."]
    else:
        head += ["- **Retrieval-only run** (`--no-generate`): answer-quality metrics (correctness, faithfulness, "
                 "relevance, citation accuracy, unanswerable handling) were not computed in this run."]
    head += ["- Intervals in brackets are bootstrap 95% CIs over questions.", ""]
    tables["run_info"] = head[2:]

    tables["retrieval"] = [
        "Retrieval metrics are computed over the answerable questions (factual + multi-hop). *Evidence Recall@5* is "
        "the fraction of gold evidence passages found in some retrieved chunk (the passage-level metric); "
        "*Doc Recall@5* only asks whether a chunk from the right paper was retrieved.", "",
    ] + retrieval_table(results, configs)

    if meta.generation:
        tables["generation"] = [
            "Correctness / faithfulness / relevance are LLM-as-judge scores on answerable questions. Citation accuracy "
            "= fraction of cited `[n]` passages that contain gold evidence; coverage = fraction of answers citing at "
            "least one passage. Unanswerable handling = fraction of unanswerable questions where the system abstained "
            "(judge verdict). The guard column is the lexical hallucination heuristic's flagged-sentence rate.", "",
        ] + generation_table(results, configs)

    def cmp(name: str, *args) -> None:
        tables[name] = comparison_block(*args, results, meta.generation)

    cmp("cmp_dense_hybrid", "3.1 Dense-only vs. hybrid retrieval",
        "Same chunks, same embeddings; B adds BM25 fusion and the importance boost (production weights 0.6 dense / 0.4 sparse, ×(1+0.2·importance)).",
        [(f"{c}__dense__{e}", f"{c}__hybrid__{e}") for c in CHUNKERS for e in EMBEDDERS_FOR[c]])
    cmp("cmp_embedding", "3.2 Embedding model: OpenAI vs. Hugging Face MiniLM",
        "Same chunks and retrieval mode; B swaps OpenAI `text-embedding-3-small` for the local `all-MiniLM-L6-v2` (A = OpenAI).",
        [(f"{c}__{m}__openai", f"{c}__{m}__hf") for c in ("character", "sentence800") for m in MODES])
    cmp("cmp_chunk_uncontrolled", "3.3a Chunking ablation — UNCONTROLLED (the original, size-confounded comparison)",
        "A = character windows (~800 chars); B = production sentence chunker at its default size (~3,000 chars). "
        "Boundary strategy and chunk size differ at once, so differences cannot be attributed to boundary alignment alone.",
        [(f"character__{m}__openai", f"sentence__{m}__openai") for m in MODES])
    cmp("cmp_chunk_controlled", "3.3b Chunking ablation — SIZE-CONTROLLED (boundary strategy isolated)",
        "A = character windows (~800 chars); B = sentence-boundary chunks capped at ~800 chars "
        "(`chunk_blocks_semantic(chunk_size=200)`). Chunk size is held (approximately) constant, so any difference is due to "
        "where chunk boundaries fall.",
        [(f"character__{m}__{e}", f"sentence800__{m}__{e}") for m in MODES for e in ("openai", "hf")])

    stats = ["| Chunker | # chunks | mean chars | median chars |", "|---|---|---|---|"]
    docs = p.load_documents()
    for s in CHUNKERS:
        sizes = [len(c.text) for c in p.chunk(docs, s)]
        stats.append(f"| `{s}` | {len(sizes)} | {statistics.mean(sizes):.0f} | {statistics.median(sizes):.0f} |")
    tables["chunk_stats"] = stats

    if meta.generation:
        allrows = [r for rs in results.values() for r in rs]
        both = [r for r in allrows if r.abstained_judge is not None and r.abstained_regex is not None]
        agree = sum(r.abstained_judge == r.abstained_regex for r in both) / len(both) if both else None
        pairs = [(r.guard_unsupported_frac, r.faithfulness) for r in allrows
                 if r.guard_unsupported_frac is not None and r.faithfulness is not None]
        corr = None
        if len(pairs) > 5 and np.std([a for a, _ in pairs]) > 0 and np.std([b for _, b in pairs]) > 0:
            corr = float(np.corrcoef([a for a, _ in pairs], [b for _, b in pairs])[0, 1])
        tables["sanity"] = [
            f"- LLM-judge abstention verdict agrees with a regex abstention heuristic on {_fmt(agree, True)} of {len(both)} answers.",
            f"- Pearson correlation between the hallucination guard's unsupported-sentence rate and the judge's faithfulness score: "
            f"{_fmt(corr)} (n={len(pairs)}). A strongly negative value means the lexical guard tracks the judge; the guard is a "
            "heuristic, not a proof of grounding."]

    tdir = RESULTS_DIR / "tables"
    tdir.mkdir(exist_ok=True)
    for stale in tdir.glob("*.md"):
        stale.unlink()
    for name, lines in tables.items():
        (tdir / f"{name}.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    body = head + ["## 1. Retrieval quality", ""] + tables["retrieval"] + [""]
    if "generation" in tables:
        body += ["## 2. Answer quality", ""] + tables["generation"] + [""]
    body += ["## 3. Controlled comparisons", ""]
    for name in ("cmp_dense_hybrid", "cmp_embedding", "cmp_chunk_uncontrolled", "cmp_chunk_controlled"):
        body += tables[name]
    body += ["### Chunk statistics", ""] + tables["chunk_stats"] + [""]
    if "sanity" in tables:
        body += ["## 4. Metric sanity checks", ""] + tables["sanity"] + [""]

    out = RESULTS_DIR / "summary.md"
    out.write_text("\n".join(body), encoding="utf-8")
    return out


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def preflight(configs: list[str], generate: bool, require_online: bool) -> None:
    if not require_online:
        print("WARNING: --no-require-online: offline fallbacks are NOT blocked; do not report these numbers.")
        return
    errors = []
    embedders = {c.split("__")[2] for c in configs}
    if "openai" in embedders and not settings.openai_ready:
        errors.append("OpenAI embeddings requested but OPENAI_API_KEY is missing/placeholder in backend/.env.")
    if "hf" in embedders:
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            errors.append("HF embeddings requested but sentence-transformers is not installed (pip install -r backend/requirements-dev.txt).")
    if generate and not (settings.openai_ready or settings.groq_ready):
        errors.append("No LLM configured: set OPENAI_API_KEY (sk-...) or GROQ_API_KEY (gsk_...) in backend/.env, "
                      "or pass --no-generate for a retrieval-only run.")
    if errors:
        print("Refusing to run (--require-online):")
        for e in errors:
            print("  -", e)
        sys.exit(2)


def write_csv(config: str, rows: list[Row]) -> None:
    path = RESULTS_DIR / f"raw_{config}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))


def run_config(config: str, documents, testset, generate: bool, cache: LLMCache, meta: RunMeta, indexes: dict) -> list[Row]:
    chunker, mode, embedder = config.split("__")
    if (chunker, embedder) not in indexes:
        print(f"  building index {chunker}/{embedder} ...", flush=True)
        indexes[(chunker, embedder)] = p.build_index(chunker, documents, embedder)
    index = indexes[(chunker, embedder)]
    rows: list[Row] = []
    for n, item in enumerate(testset, start=1):
        retrieved = p.retrieve(item["question"], index, mode=mode, k=TOP_K)
        row = Row(
            config=config, id=item["id"], type=item["type"], question=item["question"],
            expected_answer=item["expected_answer"], source_documents="; ".join(item["source_documents"]),
            retrieved_chunk_ids="; ".join(r.chunk.chunk_id for r in retrieved),
            retrieved_doc_ids="; ".join(r.chunk.doc_id for r in retrieved),
        )
        if item["type"] in ANSWERABLE:
            score_retrieval(item, retrieved, row)
        if generate:
            answer = generate_answer(cache, item["question"], retrieved)
            score_generation(item, retrieved, answer, row, cache, meta)
        rows.append(row)
        if generate and n % 10 == 0:
            print(f"    {n}/{len(testset)}", flush=True)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--configs", nargs="*", default=ALL_CONFIGS, help=f"subset of: {', '.join(ALL_CONFIGS)}")
    ap.add_argument("--no-generate", action="store_true", help="retrieval metrics only (no LLM answers/judging)")
    ap.add_argument("--require-online", action=argparse.BooleanOptionalAction, default=True,
                    help="abort instead of falling back to offline embeddings/answers (default: on)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N questions (debugging)")
    args = ap.parse_args()

    generate = not args.no_generate
    bad = [c for c in args.configs if c not in ALL_CONFIGS]
    if bad:
        ap.error(f"unknown config(s): {bad}")
    preflight(args.configs, generate, args.require_online)

    RESULTS_DIR.mkdir(exist_ok=True)
    testset = json.loads((EVAL_DIR / "testset.json").read_text(encoding="utf-8"))
    if args.limit:
        testset = testset[: args.limit]
    documents = p.load_documents()

    counter = _WarningCounter()
    logging.getLogger("papertrail.llm").addHandler(counter)
    meta = RunMeta(
        started=dt.datetime.now().strftime("%Y-%m-%d %H:%M"), chat_model=_chat_model_name() if generate else "",
        judge_model=_chat_model_name() if generate else "", openai_embedding_model=settings.openai_embedding_model,
        hf_embedding_model=settings.hf_embedding_model, n_questions=len(testset), generation=generate,
    )
    cache = LLMCache("llm_outputs")

    results: dict[str, list[Row]] = {}
    indexes: dict = {}
    for config in args.configs:
        print(f"Config {config}", flush=True)
        results[config] = run_config(config, documents, testset, generate, cache, meta, indexes)
        write_csv(config, results[config])

    meta.llm_fallback_warnings = counter.count
    if args.require_online and generate and counter.count:
        print(f"WARNING: {counter.count} production fallback warning(s) were logged during generation; see summary.")
    summary = write_summary(results, meta, testset)
    (RESULTS_DIR / "run_meta.json").write_text(json.dumps(asdict(meta), indent=2), encoding="utf-8")
    print(f"Wrote {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
