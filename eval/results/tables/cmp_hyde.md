### 3.6 HyDE query expansion

A = hybrid retrieval on the raw question; B = the dense side embeds an LLM-written hypothetical answer passage (BM25 sees question + passage).

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) | Δ Correctness (1-5) (B−A) | Δ Faithfulness (1-5) (B−A) |
|---|---|---|---|---|---|
| `character__hybrid__bge` | `character__hybrid_hyde__bge` | +25.0% [+9.2%, +40.8%] * | +1.3% [+0.0%, +3.9%] | — | — |
| `sentence800__hybrid__bge` | `sentence800__hybrid_hyde__bge` | +26.3% [+13.2%, +40.8%] * | -2.6% [-7.9%, +2.6%] | — | — |

`*` = the paired-bootstrap 95% interval excludes 0.
