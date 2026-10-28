Positive class = *answerable*. AUROC is the probability that an answerable question's top-passage signal exceeds an unanswerable one's (0.5 = chance). The threshold maximises Youden's J on all 46 questions; *LOO accuracy* re-picks the threshold without each question in turn and classifies that question with it, which removes the optimism of tuning and testing on the same data. With only 8 unanswerable questions, intervals are wide.

| Config | Signal | AUROC [95% CI] | Threshold | Unanswerable caught | Answerable wrongly abstained | LOO accuracy |
|---|---|---|---|---|---|---|
| `character__dense__hf` | top dense cosine | 0.81 [0.63–0.95] | 0.625 | 7/8 | 9/38 | 74% |
| `character__dense__bge` | top dense cosine | 0.87 [0.74–0.97] | 0.794 | 7/8 | 6/38 | 83% |
| `character__hybrid__hf` | top dense cosine | 0.76 [0.55–0.92] | 0.589 | 7/8 | 12/38 | 70% |
| `character__hybrid__bge` | top dense cosine | 0.91 [0.81–0.98] | 0.794 | 8/8 | 7/38 | 83% |
| `sentence__dense__bge` | top dense cosine | 0.85 [0.66–0.97] | 0.775 | 7/8 | 7/38 | 78% |
| `sentence__hybrid__bge` | top dense cosine | 0.89 [0.77–0.97] | 0.774 | 8/8 | 10/38 | 76% |
| `sentence800__dense__hf` | top dense cosine | 0.81 [0.57–0.97] | 0.621 | 7/8 | 6/38 | 80% |
| `sentence800__dense__bge` | top dense cosine | 0.90 [0.78–0.99] | 0.797 | 7/8 | 4/38 | 85% |
| `sentence800__hybrid__hf` | top dense cosine | 0.81 [0.57–0.97] | 0.556 | 7/8 | 6/38 | 80% |
| `sentence800__hybrid__bge` | top dense cosine | 0.96 [0.89–1.00] | 0.770 | 8/8 | 3/38 | 91% |
| `character__hybrid_rerank__hf` | top dense cosine | 0.81 [0.67–0.92] | 0.588 | 8/8 | 14/38 | 65% |
| `character__hybrid_rerank__hf` | re-ranker probability | 0.87 [0.67–0.99] | 0.984 | 7/8 | 6/38 | 80% |
| `character__hybrid_rerank__bge` | top dense cosine | 0.86 [0.74–0.95] | 0.791 | 8/8 | 11/38 | 72% |
| `character__hybrid_rerank__bge` | re-ranker probability | 0.87 [0.67–0.99] | 0.984 | 7/8 | 6/38 | 80% |
| `sentence800__hybrid_rerank__hf` | top dense cosine | 0.78 [0.62–0.91] | 0.547 | 7/8 | 12/38 | 70% |
| `sentence800__hybrid_rerank__hf` | re-ranker probability | 0.86 [0.64–0.99] | 0.988 | 7/8 | 6/38 | 80% |
| `sentence800__hybrid_rerank__bge` | top dense cosine | 0.83 [0.69–0.93] | 0.788 | 7/8 | 10/38 | 72% |
| `sentence800__hybrid_rerank__bge` | re-ranker probability | 0.86 [0.64–0.99] | 0.988 | 7/8 | 6/38 | 80% |
| `character_ctx__hybrid__hf` | top dense cosine | 0.79 [0.60–0.93] | 0.613 | 7/8 | 14/38 | 63% |
| `character_ctx__hybrid__bge` | top dense cosine | 0.90 [0.78–0.98] | 0.748 | 6/8 | 2/38 | 80% |
| `sentence800_ctx__hybrid__hf` | top dense cosine | 0.75 [0.56–0.90] | 0.622 | 7/8 | 16/38 | 57% |
| `sentence800_ctx__hybrid__bge` | top dense cosine | 0.88 [0.74–0.97] | 0.762 | 6/8 | 4/38 | 85% |
| `character__hybrid_hyde__bge` | top dense cosine | 0.77 [0.54–0.96] | 0.833 | 5/8 | 4/38 | 72% |
| `sentence800__hybrid_hyde__bge` | top dense cosine | 0.80 [0.63–0.94] | 0.821 | 5/8 | 4/38 | 85% |
| `character__dense__hf` | LLM self-abstention (no threshold) | — | — | 7/8 | 7/38 | — |
| `character__hybrid__hf` | LLM self-abstention (no threshold) | — | — | 8/8 | 3/38 | — |
| `sentence800__hybrid__bge` | LLM self-abstention (no threshold) | — | — | 7/8 | 4/38 | — |
| `sentence800__hybrid_rerank__bge` | LLM self-abstention (no threshold) | — | — | 8/8 | 3/38 | — |

The hybrid *fused* score is deliberately not offered as a signal: it is min-max normalised per query, so the top passage scores ≈1 whatever the question (AUROC 0.47–0.72 across the hybrid configurations; for dense-only retrieval it equals the cosine). Thresholds are specific to the embedding model, because cosine scales differ between models.
