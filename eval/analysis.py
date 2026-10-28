"""Analyses that go beyond the retrieval/generation grid.

Reads the per-question ``results/raw_<config>.csv`` files (so it re-uses every
cached answer and spends no generation tokens) and writes four tables to
``results/tables/`` (consumed by ``render_docs.py``):

* ``abstention``     - can a retrieval-confidence signal separate answerable from
                       unanswerable questions? AUROC, a threshold, and a
                       leave-one-out check of that threshold.
* ``nli_grounding``  - does an NLI entailment check track the LLM judge's
                       faithfulness score better than the lexical heuristic?
* ``judge_agreement``- how well does a second LLM judge (and, once filled in, a
                       human) agree with the primary judge?
* ``failure_taxonomy``- where do wrong answers come from (retrieval, generation,
                       citation, abstention)?

    python analysis.py                     # everything
    python analysis.py --skip-nli --skip-judge2   # only the free analyses
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

import numpy as np

import pipeline as p
import run_eval as r

EVAL_DIR = pathlib.Path(__file__).resolve().parent
RESULTS = EVAL_DIR / "results"
TABLES = RESULTS / "tables"
SAMPLE_CSV = RESULTS / "judge_validation.csv"
SAMPLE_SIZE = 24


def _load_all() -> dict[str, list[r.Row]]:
    out = {}
    for cfg in r.ALL_KNOWN:
        rows = r.load_rows(cfg)
        if rows:
            out[cfg] = rows
    return out


def _gen_configs(results: dict[str, list[r.Row]]) -> list[str]:
    return [c for c, rows in results.items() if any(x.generated_answer and x.correctness is not None for x in rows)]


def _write(name: str, lines: list[str]) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    (TABLES / f"{name}.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(f"wrote results/tables/{name}.md")


# --------------------------------------------------------------------------- #
# 1. Abstention calibration
# --------------------------------------------------------------------------- #
def auroc(pos: list[float], neg: list[float]) -> float:
    """P(random positive scores higher than random negative); ties count half."""
    if not pos or not neg:
        return float("nan")
    p_, n_ = np.asarray(pos), np.asarray(neg)
    gt = (p_[:, None] > n_[None, :]).mean()
    eq = (p_[:, None] == n_[None, :]).mean()
    return float(gt + 0.5 * eq)


def _boot_auroc(pos: list[float], neg: list[float], n: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    vals = [auroc(list(rng.choice(pos, len(pos))), list(rng.choice(neg, len(neg)))) for _ in range(n)]
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def _best_threshold(ans: list[float], unans: list[float]) -> float:
    """Threshold t (abstain when signal < t) maximising Youden's J =
    P(abstain | unanswerable) - P(abstain | answerable)."""
    cands = sorted(set(ans) | set(unans))
    cands = [(a + b) / 2 for a, b in zip(cands, cands[1:])] or cands
    best_t, best_j = cands[0], -2.0
    for t in cands:
        j = np.mean([x < t for x in unans]) - np.mean([x < t for x in ans])
        if j > best_j:
            best_t, best_j = t, float(j)
    return float(best_t)


def abstention_table(results: dict[str, list[r.Row]]) -> tuple[list[str], dict]:
    lines = [
        "Positive class = *answerable*. AUROC is the probability that an answerable question's top-passage signal exceeds an "
        "unanswerable one's (0.5 = chance). The threshold maximises Youden's J on all 46 questions; *LOO accuracy* re-picks "
        "the threshold without each question in turn and classifies that question with it, which removes the optimism of "
        "tuning and testing on the same data. With only 8 unanswerable questions, intervals are wide.", "",
        "| Config | Signal | AUROC [95% CI] | Threshold | Unanswerable caught | Answerable wrongly abstained | LOO accuracy |",
        "|---|---|---|---|---|---|---|",
    ]
    thresholds: dict[str, dict] = {}
    for cfg, rows in results.items():
        for attr, name in (("sig_dense", "top dense cosine"), ("sig_rerank", "re-ranker probability")):
            ans = [getattr(x, attr) for x in rows if x.type in r.ANSWERABLE and getattr(x, attr) is not None]
            una = [getattr(x, attr) for x in rows if x.type == "unanswerable" and getattr(x, attr) is not None]
            if len(ans) < 10 or len(una) < 4:
                continue
            a = auroc(ans, una)
            lo, hi = _boot_auroc(ans, una)
            t = _best_threshold(ans, una)
            caught = sum(x < t for x in una)
            lost = sum(x < t for x in ans)
            # leave-one-out
            correct = 0
            for i, x in enumerate(ans):
                tt = _best_threshold(ans[:i] + ans[i + 1:], una)
                correct += not (x < tt)
            for i, x in enumerate(una):
                tt = _best_threshold(ans, una[:i] + una[i + 1:])
                correct += x < tt
            loo = correct / (len(ans) + len(una))
            lines.append(f"| `{cfg}` | {name} | {a:.2f} [{lo:.2f}–{hi:.2f}] | {t:.3f} | {caught}/{len(una)} | {lost}/{len(ans)} | {loo:.0%} |")
            thresholds[f"{cfg}|{attr}"] = {"auroc": round(a, 4), "threshold": round(t, 4), "caught": caught, "lost": lost, "loo_accuracy": round(loo, 4)}

    # LLM self-abstention baseline (no retrieval signal): what the generator does on its own.
    base = []
    for cfg in _gen_configs(results):
        rows = results[cfg]
        una = [x for x in rows if x.type == "unanswerable" and x.abstained_judge is not None]
        ans = [x for x in rows if x.type in r.ANSWERABLE and x.abstained_judge is not None]
        if una and ans:
            base.append(f"| `{cfg}` | LLM self-abstention (no threshold) | — | — | {sum(x.abstained_judge for x in una)}/{len(una)} | "
                        f"{sum(x.abstained_judge for x in ans)}/{len(ans)} | — |")
    lines += base
    fused = []
    for cfg, rows in results.items():
        if "__hybrid" not in cfg or "rerank" in cfg:
            continue
        ans = [x.sig_fused for x in rows if x.type in r.ANSWERABLE and x.sig_fused is not None]
        una = [x.sig_fused for x in rows if x.type == "unanswerable" and x.sig_fused is not None]
        if len(ans) >= 10 and len(una) >= 4:
            fused.append(auroc(ans, una))
    if fused:
        lines += ["", f"The hybrid *fused* score is deliberately not offered as a signal: it is min-max normalised per query, so the "
                  f"top passage scores ≈1 whatever the question (AUROC {min(fused):.2f}–{max(fused):.2f} across the hybrid configurations; "
                  "for dense-only retrieval it equals the cosine). Thresholds are specific to the embedding model, because cosine "
                  "scales differ between models."]
    if len(lines) == 6:
        lines.append("| _no configuration has retrieval signals yet_ | | | | | | |")
    return lines, thresholds


# --------------------------------------------------------------------------- #
# 2. NLI vs lexical grounding (against the judge's faithfulness)
# --------------------------------------------------------------------------- #
def _spearman(x: list[float], y: list[float]) -> float:
    if len(x) < 5 or len(set(x)) < 2 or len(set(y)) < 2:
        return float("nan")
    from scipy.stats import spearmanr

    return float(spearmanr(x, y).statistic)


def nli_table(results: dict[str, list[r.Row]]) -> list[str]:
    from app.services import nli_guard

    docs = p.load_documents()
    chunk_maps: dict[str, dict[str, p.Chunk]] = {}
    cache_path = p.CACHE_DIR / "nli.json"
    cache: dict[str, list[dict]] = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    records = []  # (config, nli_unsupported_frac, lexical_unsupported_frac, judge_faith)
    for cfg in _gen_configs(results):
        strategy = cfg.split("__")[0]
        if strategy not in chunk_maps:
            chunk_maps[strategy] = {c.chunk_id: c for c in p.chunk(docs, strategy)}
        for x in results[cfg]:
            if x.type not in r.ANSWERABLE or not x.generated_answer or x.faithfulness is None or x.abstained_judge:
                continue
            ids = [i.strip() for i in x.retrieved_chunk_ids.split(";")]
            chunks = [{"chunk_id": i, "text": chunk_maps[strategy][i].text} for i in ids if i in chunk_maps[strategy]]
            key = r.LLMCache.key(cfg, x.id, x.generated_answer, nli_guard.settings.nli_model)
            if key not in cache:
                cache[key] = nli_guard.check_answer_nli(x.generated_answer, chunks)
                cache_path.write_text(json.dumps(cache), encoding="utf-8")
            verdicts = cache[key]
            if not verdicts:
                continue
            nli_frac = sum(not v["supported"] for v in verdicts) / len(verdicts)
            mean_ent = sum(v["entailment"] for v in verdicts) / len(verdicts)
            records.append((cfg, nli_frac, x.guard_unsupported_frac if x.guard_unsupported_frac is not None else 0.0,
                            float(x.faithfulness), mean_ent))

    lines = [
        "Per answerable, non-abstained answer: fraction of sentences each method flags as unsupported, compared with the LLM "
        "judge's faithfulness score (1-5). A good grounding check has a strongly **negative** rank correlation with "
        "faithfulness (more flagged = less faithful). *AUROC* = how well \"fraction supported\" separates answers the judge "
        "rated faithful (>= 4) from the rest. The judge is itself an imperfect reference.", "",
        "| Method | n answers | Mean flagged-sentence rate | Spearman ρ vs judge faithfulness | AUROC for judge-faithful (≥4) |",
        "|---|---|---|---|---|",
    ]
    if not records:
        lines.append("| _no scored answers available_ | | | | |")
        return lines
    faith = [rec[3] for rec in records]
    faithful = [1 if f >= 4 else 0 for f in faith]
    for name, idx in (("Lexical guard (production heuristic)", 2), ("NLI entailment, binary (flagged if P(entail) < 0.5)", 1)):
        flagged = [rec[idx] for rec in records]
        rho = _spearman(flagged, faith)
        pos = [1 - f for f, y in zip(flagged, faithful) if y == 1]
        neg = [1 - f for f, y in zip(flagged, faithful) if y == 0]
        au = auroc(pos, neg)
        lines.append(f"| {name} | {len(records)} | {np.mean(flagged):.0%} | {rho:+.2f} | {'—' if np.isnan(au) else f'{au:.2f}'} |")
    # Continuous NLI score: mean entailment probability (higher = better supported), so the sign flips.
    ment = [rec[4] for rec in records]
    pos = [m for m, y in zip(ment, faithful) if y == 1]
    neg = [m for m, y in zip(ment, faithful) if y == 0]
    au = auroc(pos, neg)
    lines.append(f"| NLI mean entailment probability (continuous; ρ expected **positive**) | {len(records)} | "
                 f"{np.mean([1 - m for m in ment]):.0%} (1 − mean P) | {_spearman(ment, faith):+.2f} | {'—' if np.isnan(au) else f'{au:.2f}'} |")
    lines += ["", f"Judge-faithful answers (≥4): {sum(faithful)}/{len(faithful)} — with few low-faithfulness answers the AUROC is noisy."]
    return lines


# --------------------------------------------------------------------------- #
# 3. Judge agreement (second judge + human template)
# --------------------------------------------------------------------------- #
def _qwk(a: list[int], b: list[int], lo: int = 1, hi: int = 5) -> float:
    """Quadratic-weighted Cohen's kappa on integer scores."""
    k = hi - lo + 1
    obs = np.zeros((k, k))
    for x, y in zip(a, b):
        obs[x - lo, y - lo] += 1
    if obs.sum() == 0:
        return float("nan")
    w = np.array([[(i - j) ** 2 for j in range(k)] for i in range(k)]) / (k - 1) ** 2
    exp = np.outer(obs.sum(1), obs.sum(0)) / obs.sum()
    den = (w * exp).sum()
    return float("nan") if den == 0 else 1 - (w * obs).sum() / den


def _sample(results: dict[str, list[r.Row]]) -> list[tuple[str, r.Row]]:
    pool = [(cfg, x) for cfg in _gen_configs(results) for x in results[cfg] if x.generated_answer and x.correctness is not None]
    rng = np.random.default_rng(7)
    hi = [t for t in pool if t[1].correctness >= 4]
    lo = [t for t in pool if t[1].correctness <= 3]
    pick = []
    for group in (hi, lo):
        group = sorted(group, key=lambda t: (t[0], t[1].id))
        n = min(len(group), SAMPLE_SIZE // 2)
        pick += [group[i] for i in sorted(rng.choice(len(group), n, replace=False))] if n else []
    return pick


def judge_table(results: dict[str, list[r.Row]], second_model: str, skip_second: bool) -> list[str]:
    sample = _sample(results)
    existing: dict[tuple[str, str], dict] = {}
    if SAMPLE_CSV.exists():
        with SAMPLE_CSV.open(encoding="utf-8", newline="") as f:
            existing = {(row["config"], row["id"]): row for row in csv.DictReader(f)}

    cache = r.LLMCache("llm_outputs")
    meta = r.RunMeta()
    rows_out = []
    for cfg, x in sample:
        prev = existing.get((cfg, x.id), {})
        j2 = prev.get("judge2_correctness", "")
        if not j2 and not skip_second:
            item = {"question": x.question, "expected_answer": x.expected_answer}
            ids = [i.strip() for i in x.retrieved_chunk_ids.split(";")]
            docs = p.load_documents()
            strat = cfg.split("__")[0]
            cmap = {c.chunk_id: c for c in p.chunk(docs, strat)}
            retrieved = [p.Retrieved(chunk=cmap[i], score=0.0) for i in ids if i in cmap]
            r.JUDGE_MODEL = second_model
            try:
                verdict = r.judge(cache, meta, item, retrieved, x.generated_answer)
            finally:
                r.JUDGE_MODEL = ""
            j2 = str(verdict.get("correctness", "")) if verdict else ""
        rows_out.append({
            "config": cfg, "id": x.id, "type": x.type, "question": x.question, "reference_answer": x.expected_answer,
            "generated_answer": x.generated_answer, "judge1_model": x.judge_model, "judge1_correctness": x.correctness,
            "judge2_model": second_model if j2 else "", "judge2_correctness": j2,
            "human_correctness": prev.get("human_correctness", ""),
        })
    if rows_out:
        with SAMPLE_CSV.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
            w.writeheader()
            w.writerows(rows_out)

    def pairs(col_a: str, col_b: str) -> tuple[list[int], list[int]]:
        a, b = [], []
        for row in rows_out:
            if str(row[col_a]).strip().isdigit() and str(row[col_b]).strip().isdigit():
                a.append(int(row[col_a]))
                b.append(int(row[col_b]))
        return a, b

    lines = [
        f"{len(rows_out)} answers were sampled (stratified: half judged correct (≥4), half not) from the scored configurations "
        "and re-judged by a second, different model. `results/judge_validation.csv` also has a blank `human_correctness` column "
        "(1-5, same rubric) for a human grader; the human rows below fill in once it is completed.", "",
        "| Pair | n | Exact agreement | Within ±1 | Spearman ρ | Quadratic-weighted κ |",
        "|---|---|---|---|---|---|",
    ]
    for label, ca, cb in (("Judge 1 vs Judge 2 (correctness)", "judge1_correctness", "judge2_correctness"),
                          ("Judge 1 vs human", "judge1_correctness", "human_correctness"),
                          ("Judge 2 vs human", "judge2_correctness", "human_correctness")):
        a, b = pairs(ca, cb)
        if len(a) < 5:
            lines.append(f"| {label} | {len(a)} | — | — | — | — |" if "human" not in label else f"| {label} | {len(a)} (pending human labels) | — | — | — | — |")
            continue
        exact = np.mean([x == y for x, y in zip(a, b)])
        near = np.mean([abs(x - y) <= 1 for x, y in zip(a, b)])
        lines.append(f"| {label} | {len(a)} | {exact:.0%} | {near:.0%} | {_spearman(a, b):+.2f} | {_qwk(a, b):+.2f} |")
    return lines


# --------------------------------------------------------------------------- #
# 4. Failure taxonomy
# --------------------------------------------------------------------------- #
CATEGORIES = [
    ("correct", "Answer judged correct (≥4)"),
    ("retrieval_miss", "Wrong: no gold evidence retrieved (retrieval failure)"),
    ("generation_error", "Wrong although gold evidence was retrieved (generation / reading failure)"),
    ("wrong_abstention", "Wrong: abstained on an answerable question"),
    ("uncited_or_miscited", "Correct answer but its citations point at passages without the evidence"),
]


def taxonomy_table(results: dict[str, list[r.Row]]) -> list[str]:
    lines = [
        "Each answerable question is assigned to exactly one bucket, from the per-question CSVs "
        "(evidence recall, judge correctness, abstention, citation accuracy). Unanswerable questions are reported separately.", "",
        "| Config | " + " | ".join(label for _, label in CATEGORIES) + " | Unanswerable: hallucinated an answer |",
        "|---|" + "---|" * (len(CATEGORIES) + 1),
    ]
    scored = _gen_configs(results)
    for cfg in scored:
        counts = {k: 0 for k, _ in CATEGORIES}
        n_ans = hallucinated = n_una = 0
        for x in results[cfg]:
            if x.correctness is None:
                continue
            if x.type == "unanswerable":
                n_una += 1
                hallucinated += not bool(x.abstained_judge)
                continue
            n_ans += 1
            retrieved_ok = (x.evidence_recall or 0) > 0
            if x.abstained_judge and x.correctness <= 3:
                counts["wrong_abstention"] += 1
            elif x.correctness >= 4:
                if (x.n_citations or 0) > 0 and (x.n_correct_citations or 0) == 0:
                    counts["uncited_or_miscited"] += 1
                else:
                    counts["correct"] += 1
            elif not retrieved_ok:
                counts["retrieval_miss"] += 1
            else:
                counts["generation_error"] += 1
        cells = " | ".join(f"{counts[k]} ({counts[k] / n_ans:.0%})" if n_ans else "—" for k, _ in CATEGORIES)
        lines.append(f"| `{cfg}` | {cells} | {hallucinated}/{n_una} |")
    if not scored:
        lines.append("| _no scored configuration yet_ |" + " |" * (len(CATEGORIES) + 1))
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--skip-nli", action="store_true", help="skip the NLI model run")
    ap.add_argument("--skip-judge2", action="store_true", help="do not call a second judge model")
    ap.add_argument("--judge2-model", default="qwen/qwen3.8-27b", help="Groq model for the second judge")
    ap.add_argument("--pace", type=float, default=2.0, help="seconds between second-judge calls")
    args = ap.parse_args()
    r.PACE_SECONDS = args.pace

    results = _load_all()
    if not results:
        print("No results/raw_*.csv found; run run_eval.py first.")
        return 1

    lines, thresholds = abstention_table(results)
    _write("abstention", lines)
    (RESULTS / "abstention_thresholds.json").write_text(json.dumps(thresholds, indent=2), encoding="utf-8")
    _write("failure_taxonomy", taxonomy_table(results))
    if not args.skip_nli:
        _write("nli_grounding", nli_table(results))
    _write("judge_agreement", judge_table(results, args.judge2_model, args.skip_judge2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
