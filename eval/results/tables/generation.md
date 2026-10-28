Correctness / faithfulness / relevance are LLM-as-judge scores on answerable questions. Citation accuracy = fraction of cited `[n]` passages that contain gold evidence; coverage = fraction of answers citing at least one passage. Unanswerable handling = fraction of unanswerable questions where the system abstained (judge verdict). The guard column is the lexical hallucination heuristic's flagged-sentence rate.

| Config | Correctness (1-5) | Faithfulness (1-5) | Relevance (1-5) | Citation accuracy | Citation coverage | Unanswerable handling | Guard unsupported-sentence rate |
|---|---|---|---|---|---|---|---|
| `character__dense__hf` | 3.68 [3.11–4.24] | 3.87 | 4.18 | 38% (22/58) | 84% | 88% (7/8) | 12% |
| `character__hybrid__hf` | 4.26 [3.76–4.71] | 4.61 | 4.68 | 38% (24/64) | 92% | 100% (8/8) | 10% |
| `sentence800__hybrid__bge` | 4.32 [3.79–4.79] | 4.76 | 4.55 | 47% (36/76) | 95% | 88% (7/8) | 8% |
| `sentence800__hybrid_rerank__bge` | 4.34 [3.84–4.79] | 4.58 | 4.55 | 48% (38/80) | 92% | 100% (8/8) | 13% |
