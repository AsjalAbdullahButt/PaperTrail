Each answerable question is assigned to exactly one bucket, from the per-question CSVs (evidence recall, judge correctness, abstention, citation accuracy). Unanswerable questions are reported separately.

| Config | Answer judged correct (≥4) | Wrong: no gold evidence retrieved (retrieval failure) | Wrong although gold evidence was retrieved (generation / reading failure) | Wrong: abstained on an answerable question | Correct answer but its citations point at passages without the evidence | Unanswerable: hallucinated an answer |
|---|---|---|---|---|---|---|
| `character__dense__hf` | 15 (39%) | 4 (11%) | 3 (8%) | 7 (18%) | 9 (24%) | 1/8 |
| `character__hybrid__hf` | 19 (50%) | 3 (8%) | 1 (3%) | 3 (8%) | 12 (32%) | 0/8 |
| `sentence800__hybrid__bge` | 22 (58%) | 2 (5%) | 2 (5%) | 3 (8%) | 9 (24%) | 1/8 |
| `sentence800__hybrid_rerank__bge` | 25 (66%) | 3 (8%) | 1 (3%) | 3 (8%) | 6 (16%) | 0/8 |
