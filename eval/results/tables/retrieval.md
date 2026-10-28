Retrieval metrics are computed over the answerable questions (factual + multi-hop). *Evidence Recall@5* is the fraction of gold evidence passages found in some retrieved chunk (the passage-level metric); *Doc Recall@5* only asks whether a chunk from the right paper was retrieved.

| Config | Doc Recall@5 (answerable) | Doc Recall@5 (multi-hop) | Evidence Recall@5 | Evidence MRR | Section hit |
|---|---|---|---|---|---|
| `character__dense__hf` | 88% [80%–95%] | 59% | 41% [26%–55%] | 0.31 | 42% |
| `character__dense__bge` | 86% [76%–93%] | 59% | 50% [37%–64%] | 0.44 | 39% |
| `character__hybrid__hf` | 93% [87%–99%] | 77% | 49% [34%–63%] | 0.41 | 42% |
| `character__hybrid__bge` | 95% [89%–99%] | 82% | 54% [39%–68%] | 0.48 | 45% |
| `sentence__dense__bge` | 89% [82%–96%] | 73% | 64% [50%–78%] | 0.56 | 22% |
| `sentence__hybrid__bge` | 95% [89%–99%] | 82% | 66% [51%–79%] | 0.56 | 28% |
| `sentence800__dense__hf` | 86% [78%–93%] | 59% | 41% [26%–55%] | 0.29 | 38% |
| `sentence800__dense__bge` | 91% [83%–97%] | 77% | 54% [39%–68%] | 0.42 | 47% |
| `sentence800__hybrid__hf` | 93% [88%–99%] | 77% | 55% [41%–70%] | 0.45 | 47% |
| `sentence800__hybrid__bge` | 96% [91%–100%] | 86% | 54% [39%–68%] | 0.48 | 46% |
| `character__hybrid_rerank__hf` | 93% [88%–99%] | 77% | 64% [51%–78%] | 0.54 | 53% |
| `character__hybrid_rerank__bge` | 93% [88%–99%] | 77% | 67% [53%–80%] | 0.54 | 64% |
| `sentence800__hybrid_rerank__hf` | 89% [82%–96%] | 64% | 63% [49%–76%] | 0.57 | 63% |
| `sentence800__hybrid_rerank__bge` | 89% [82%–96%] | 64% | 63% [50%–78%] | 0.56 | 71% |
| `character_ctx__hybrid__hf` | 91% [84%–96%] | 68% | 53% [38%–67%] | 0.41 | 43% |
| `character_ctx__hybrid__bge` | 93% [88%–99%] | 77% | 61% [46%–74%] | 0.47 | 50% |
| `sentence800_ctx__hybrid__hf` | 89% [83%–96%] | 64% | 55% [39%–70%] | 0.44 | 50% |
| `sentence800_ctx__hybrid__bge` | 93% [88%–99%] | 77% | 57% [42%–71%] | 0.47 | 51% |
| `character__hybrid_hyde__bge` | 96% [91%–100%] | 86% | 79% [67%–89%] | 0.66 | 70% |
| `sentence800__hybrid_hyde__bge` | 93% [87%–99%] | 77% | 80% [68%–91%] | 0.63 | 63% |
