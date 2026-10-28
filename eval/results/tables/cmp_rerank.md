### 3.4 Cross-encoder re-ranking

A = hybrid retrieval; B = the same hybrid top-20 re-scored by `cross-encoder/ms-marco-MiniLM-L-6-v2` and cut to the top 5.

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) | Δ Correctness (1-5) (B−A) | Δ Faithfulness (1-5) (B−A) |
|---|---|---|---|---|---|
| `character__hybrid__hf` | `character__hybrid_rerank__hf` | +15.8% [+6.5%, +27.6%] * | +0.0% [-3.9%, +3.9%] | — | — |
| `character__hybrid__bge` | `character__hybrid_rerank__bge` | +13.2% [+0.0%, +27.6%] | -1.3% [-5.3%, +2.6%] | — | — |
| `sentence800__hybrid__hf` | `sentence800__hybrid_rerank__hf` | +7.9% [-3.9%, +19.7%] | -3.9% [-9.2%, +0.0%] | — | — |
| `sentence800__hybrid__bge` | `sentence800__hybrid_rerank__bge` | +9.2% [-2.6%, +22.4%] | -6.6% [-14.5%, -1.3%] * | +0.03 [-0.47, +0.50] | -0.18 [-0.55, +0.13] |

`*` = the paired-bootstrap 95% interval excludes 0.
