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
