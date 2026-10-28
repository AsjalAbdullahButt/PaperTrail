Per answerable, non-abstained answer: fraction of sentences each method flags as unsupported, compared with the LLM judge's faithfulness score (1-5). A good grounding check has a strongly **negative** rank correlation with faithfulness (more flagged = less faithful). *AUROC* = how well "fraction supported" separates answers the judge rated faithful (>= 4) from the rest. The judge is itself an imperfect reference.

| Method | n answers | Mean flagged-sentence rate | Spearman ρ vs judge faithfulness | AUROC for judge-faithful (≥4) |
|---|---|---|---|---|
| Lexical guard (production heuristic) | 135 | 10% | -0.24 | 0.71 |
| NLI entailment, binary (flagged if P(entail) < 0.5) | 135 | 56% | -0.03 | 0.46 |
| NLI mean entailment probability (continuous; ρ expected **positive**) | 135 | 57% (1 − mean P) | +0.07 | 0.50 |

Judge-faithful answers (≥4): 124/135 — with few low-faithfulness answers the AUROC is noisy.
