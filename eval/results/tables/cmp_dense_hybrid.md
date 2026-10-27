### 3.1 Dense-only vs. hybrid retrieval

Same chunks, same embeddings; B adds BM25 fusion and the importance boost (production weights 0.6 dense / 0.4 sparse, ×(1+0.2·importance)).

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) |
|---|---|---|---|
| `character__dense__hf` | `character__hybrid__hf` | +7.9% [-6.6%, +22.4%] | +5.3% [+0.0%, +11.8%] |
| `sentence800__dense__hf` | `sentence800__hybrid__hf` | +14.5% [+0.0%, +30.3%] | +7.9% [+1.3%, +15.8%] * |

`*` = the paired-bootstrap 95% interval excludes 0.
