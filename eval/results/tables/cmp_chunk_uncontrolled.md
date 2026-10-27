### 3.3a Chunking ablation — UNCONTROLLED (the original, size-confounded comparison)

A = character windows (~800 chars); B = production sentence chunker at its default size (~3,000 chars); embedder BGE-small. (BGE's 512-word-piece window covers only the first ~2,000 characters of a ~3,000-character chunk.) Boundary strategy and chunk size differ at once, so differences cannot be attributed to boundary alignment alone.

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) | Δ Correctness (1-5) (B−A) | Δ Faithfulness (1-5) (B−A) |
|---|---|---|---|---|---|
| `character__dense__bge` | `sentence__dense__bge` | +14.5% [+2.6%, +27.6%] * | +3.9% [-1.3%, +9.2%] | — | — |
| `character__hybrid__bge` | `sentence__hybrid__bge` | +11.8% [-2.6%, +27.6%] | +0.0% [-5.3%, +5.3%] | — | — |

`*` = the paired-bootstrap 95% interval excludes 0.
