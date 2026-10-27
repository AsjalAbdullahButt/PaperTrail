### 3.3b Chunking ablation — SIZE-CONTROLLED (boundary strategy isolated)

A = character windows (~800 chars); B = sentence-boundary chunks capped at ~800 chars (`chunk_blocks_semantic(chunk_size=200)`). Chunk size is held (approximately) constant, so any difference is due to where chunk boundaries fall.

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) | Δ Correctness (1-5) (B−A) | Δ Faithfulness (1-5) (B−A) |
|---|---|---|---|---|---|
| `character__dense__hf` | `sentence800__dense__hf` | +0.0% [-14.5%, +14.5%] | -2.6% [-9.2%, +2.6%] | — | — |
| `character__dense__bge` | `sentence800__dense__bge` | +3.9% [-7.9%, +15.8%] | +5.3% [+1.3%, +10.5%] * | — | — |
| `character__hybrid__hf` | `sentence800__hybrid__hf` | +6.6% [-3.9%, +18.4%] | +0.0% [-3.9%, +3.9%] | — | — |
| `character__hybrid__bge` | `sentence800__hybrid__bge` | +0.0% [-7.9%, +7.9%] | +1.3% [+0.0%, +3.9%] | — | — |

`*` = the paired-bootstrap 95% interval excludes 0.
