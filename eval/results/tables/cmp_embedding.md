### 3.2 Embedding model: MiniLM vs. BGE-small

Same chunks and retrieval mode; A = `all-MiniLM-L6-v2` (384-d, 256 word-piece window), B = `BAAI/bge-small-en-v1.5` (384-d, 512 word-piece window). Both are local Hugging Face models run through `llm.embed_texts(provider=hf)`.

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) | Δ Correctness (1-5) (B−A) | Δ Faithfulness (1-5) (B−A) |
|---|---|---|---|---|---|
| `character__dense__hf` | `character__dense__bge` | +9.2% [-2.6%, +21.1%] | -2.6% [-10.5%, +3.9%] | — | — |
| `character__hybrid__hf` | `character__hybrid__bge` | +5.3% [-3.9%, +15.8%] | +1.3% [-2.6%, +5.3%] | — | — |
| `sentence800__dense__hf` | `sentence800__dense__bge` | +13.2% [-1.3%, +28.9%] | +5.3% [+1.3%, +10.5%] * | — | — |
| `sentence800__hybrid__hf` | `sentence800__hybrid__bge` | -1.3% [-9.2%, +5.3%] | +2.6% [+0.0%, +6.6%] | — | — |

`*` = the paired-bootstrap 95% interval excludes 0.
