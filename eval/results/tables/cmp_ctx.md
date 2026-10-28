### 3.5 Contextual chunk headers

A = hybrid retrieval over plain chunks; B = identical chunks whose *embedded* text is prefixed with `<paper title> | <section>` (display text and BM25 unchanged).

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) | Δ Correctness (1-5) (B−A) | Δ Faithfulness (1-5) (B−A) |
|---|---|---|---|---|---|
| `character__hybrid__hf` | `character_ctx__hybrid__hf` | +3.9% [-2.6%, +13.2%] | -2.6% [-7.9%, +2.6%] | — | — |
| `character__hybrid__bge` | `character_ctx__hybrid__bge` | +6.6% [+0.0%, +14.5%] | -1.3% [-6.6%, +2.6%] | — | — |
| `sentence800__hybrid__hf` | `sentence800_ctx__hybrid__hf` | +0.0% [-11.8%, +11.8%] | -3.9% [-9.2%, +1.3%] | — | — |
| `sentence800__hybrid__bge` | `sentence800_ctx__hybrid__bge` | +2.6% [-6.6%, +13.2%] | -2.6% [-6.6%, +0.0%] | — | — |

`*` = the paired-bootstrap 95% interval excludes 0.
