# Evaluation Summary

| Strategy | Doc-level hit rate | Section-level hit rate | Avg faithfulness | Avg relevance |
|---|---|---|---|---|
| character | 19/20 (95%) | 13/20 (65%) | n/a | n/a |
| sentence | 18/20 (90%) | 5/20 (25%) | n/a | n/a |

## Questions where strategies disagreed on the doc-level hit

- **q05** — What does PaperTrail fall back to for approximate nearest neighbor search if the usearch library is unavailable?
  - `character` hit=True, retrieved docs: 03-hybrid-retrieval; 04-llm-provider-and-generation-modes; 04-llm-provider-and-generation-modes; 05-multihop-and-hallucination-guard; 02-ingestion-and-chunking
  - `sentence` hit=False, retrieved docs: 04-llm-provider-and-generation-modes; 01-architecture-overview; 09-observability-and-backups; 06-authentication-and-sessions; 07-deployment-topology
