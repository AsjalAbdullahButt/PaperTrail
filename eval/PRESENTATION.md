# Presentation outline — PaperTrail: evidence-grounded QA over an NLP research-paper corpus

Audience: NLP course instructors and classmates. Emphasis: **live, evidence-backed answers and the NLP methodology** — not UI/auth features. Suggested length: 18–20 minutes, 17 slides. All tables below are generated (`python render_docs.py`); the live demo uses the web app's "NLP pipeline" switches.

---

### Slide 1 — Title
*PaperTrail — Evidence-Grounded Research-Paper Question Answering over an NLP Corpus using Hybrid RAG.* Category: RAG Bot for a Niche Domain. Team names.

### Slide 2 — The NLP problem
* LLMs answer from parametric memory: fluent, uncited, sometimes wrong — unacceptable for studying papers.
* Goal: answers **only from retrieved passages**, with citations, a per-claim fact-check, and an honest "not in the documents".
* Three question types: factual, multi-hop across papers, and **unanswerable**.

### Slide 3 — The niche dataset and its provenance
<!-- BEGIN:manifest -->
| doc_id | Title | Authors | Year | Words | Pages | Source |
|---|---|---|---|---|---|---|
| `beir` | BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models | Thakur et al. | 2021 | 14,098 | 24 | [2104.08663](https://arxiv.org/abs/2104.08663) |
| `bert` | BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding | Devlin et al. | 2018 | 10,152 | 16 | [1810.04805](https://arxiv.org/abs/1810.04805) |
| `colbert` | ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT | Khattab and Zaharia | 2020 | 9,343 | 10 | [2004.12832](https://arxiv.org/abs/2004.12832) |
| `contriever` | Unsupervised Dense Information Retrieval with Contrastive Learning (Contriever) | Izacard et al. | 2021 | 11,990 | 21 | [2112.09118](https://arxiv.org/abs/2112.09118) |
| `dpr` | Dense Passage Retrieval for Open-Domain Question Answering | Karpukhin et al. | 2020 | 8,878 | 13 | [2004.04906](https://arxiv.org/abs/2004.04906) |
| `hyde` | Precise Zero-Shot Dense Retrieval without Relevance Labels (HyDE) | Gao et al. | 2022 | 6,171 | 11 | [2212.10496](https://arxiv.org/abs/2212.10496) |
| `lost-in-the-middle` | Lost in the Middle: How Language Models Use Long Contexts | Liu et al. | 2023 | 9,766 | 18 | [2307.03172](https://arxiv.org/abs/2307.03172) |
| `rag` | Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | Lewis et al. | 2020 | 9,886 | 19 | [2005.11401](https://arxiv.org/abs/2005.11401) |
| `rag-survey` | Retrieval-Augmented Generation for Large Language Models: A Survey | Gao et al. | 2023 | 15,618 | 21 | [2312.10997](https://arxiv.org/abs/2312.10997) |
| `ragas` | RAGAS: Automated Evaluation of Retrieval Augmented Generation | Es et al. | 2023 | 4,919 | 8 | [2309.15217](https://arxiv.org/abs/2309.15217) |
| `realm` | REALM: Retrieval-Augmented Language Model Pre-Training | Guu et al. | 2020 | 8,064 | 12 | [2002.08909](https://arxiv.org/abs/2002.08909) |
| `self-rag` | Self-RAG: Learning to Retrieve Generate and Critique through Self-Reflection | Asai et al. | 2023 | 16,131 | 30 | [2310.11511](https://arxiv.org/abs/2310.11511) |
| `sentence-bert` | Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks | Reimers and Gurevych | 2019 | 6,667 | 11 | [1908.10084](https://arxiv.org/abs/1908.10084) |
| `transformer` | Attention Is All You Need | Vaswani et al. | 2017 | 6,095 | 15 | [1706.03762](https://arxiv.org/abs/1706.03762) |

**14 papers, 137,778 words, 229 pages** (per paper: 4,919–16,131 words, 8–30 pages).
<!-- END:manifest -->
* Fetched by arXiv id, converted with the *production* PDF extractor; provenance in `manifest.csv`. Papers chosen so questions can span them (RAG ↔ DPR ↔ ColBERT ↔ BEIR ↔ RAGAS).

### Slide 4 — Preprocessing and chunking
* PDF → text (PyMuPDF, OCR fallback) → NFKC, re-joined hard-wraps, de-hyphenation, heading + page provenance, References removed.
* Two production chunkers (800-char windows vs sentence-aware ≈3,000 chars); every chunk keeps page + section; per-chunk **importance** (TF-IDF + position prior).

### Slide 5 — Embeddings: two local Hugging Face models
* `all-MiniLM-L6-v2` (384-d, 256-word-piece window) vs `BAAI/bge-small-en-v1.5` (384-d, 512) — free and local. OpenAI `text-embedding-3-small` stays the production default (supported, not evaluated: no key).
* One switch (`embedding_provider`) in the single AI-provider module.

### Slide 6 — Retrieval: dense vs hybrid
* Hybrid (production): candidates from dense ∪ BM25, min-max normalise, fuse **0.6·dense + 0.4·BM25**, × **(1 + 0.2·importance)**.
* Why: embeddings capture meaning, BM25 catches exact terms; importance de-emphasises boilerplate. The eval imports the production weights.

### Slide 7 — Beyond first-stage retrieval: three advanced stages
* **Cross-encoder re-ranking** (`ms-marco-MiniLM-L-6-v2`): reads question + passage together; applied to the hybrid top-20.
* **HyDE** query expansion: an LLM writes a hypothetical answer passage; retrieval searches with it.
* **Contextual chunk headers**: embed `title | section + chunk`.
* Each is an *independent, one-stage-at-a-time* arm, so every comparison is controlled.

### Slide 8 — Generation, NLI fact-checking and abstention
* Prompt: answer only from the numbered context, cite `[n]`, say so if it's not there.
* **Lexical guard** (default heuristic) vs **NLI guard**: every answer sentence is the *hypothesis*, retrieved passage windows the *premises*; supported iff entailed (`nli-deberta-v3-small`).
* **Abstention**: skip generation when the top passage's score is below a calibrated threshold.

### Slide 9 — Evaluation design
<!-- BEGIN:testset_stats -->
46 questions: 27 factual, 11 multi-hop (evidence in two papers), 8 unanswerable (answer deliberately absent from the corpus).
<!-- END:testset_stats -->
* Verbatim evidence quotes verified mechanically; unanswerable questions verified by *absence*. Metrics: Doc / **Evidence Recall@5**, MRR, correctness / faithfulness / relevance (LLM judge + blank manual column), **citation accuracy**, unanswerable handling, AUROC, κ. Bootstrap CIs; paired comparisons.
* `--require-online`: no silent offline fallback. Generator `gpt-oss-120b`, judge a *different* model.

### Slide 10 — Results: retrieval (all configurations)
<!-- BEGIN:retrieval -->
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
<!-- END:retrieval -->
Talking point: Doc Recall overstates quality — compare with Evidence Recall.

### Slide 11 — Results: answer quality
<!-- BEGIN:generation -->
Correctness / faithfulness / relevance are LLM-as-judge scores on answerable questions. Citation accuracy = fraction of cited `[n]` passages that contain gold evidence; coverage = fraction of answers citing at least one passage. Unanswerable handling = fraction of unanswerable questions where the system abstained (judge verdict). The guard column is the lexical hallucination heuristic's flagged-sentence rate.

| Config | Correctness (1-5) | Faithfulness (1-5) | Relevance (1-5) | Citation accuracy | Citation coverage | Unanswerable handling | Guard unsupported-sentence rate |
|---|---|---|---|---|---|---|---|
| `character__dense__hf` | 3.68 [3.11–4.24] | 3.87 | 4.18 | 38% (22/58) | 84% | 88% (7/8) | 12% |
| `character__hybrid__hf` | 4.26 [3.76–4.71] | 4.61 | 4.68 | 38% (24/64) | 92% | 100% (8/8) | 10% |
| `sentence800__hybrid__bge` | 4.32 [3.79–4.79] | 4.76 | 4.55 | 47% (36/76) | 95% | 88% (7/8) | 8% |
| `sentence800__hybrid_rerank__bge` | 4.34 [3.84–4.79] | 4.58 | 4.55 | 48% (38/80) | 92% | 100% (8/8) | 13% |
<!-- END:generation -->
Be explicit that only the scored configurations appear (Groq free-tier daily token limits).

### Slide 12 — Controlled comparisons (dense/hybrid, embeddings)
<!-- BEGIN:cmp_dense_hybrid -->
### 3.1 Dense-only vs. hybrid retrieval

Same chunks, same embeddings; B adds BM25 fusion and the importance boost (production weights 0.6 dense / 0.4 sparse, ×(1+0.2·importance)).

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) | Δ Correctness (1-5) (B−A) | Δ Faithfulness (1-5) (B−A) |
|---|---|---|---|---|---|
| `character__dense__hf` | `character__hybrid__hf` | +7.9% [-6.6%, +22.4%] | +5.3% [+0.0%, +11.8%] | +0.58 [-0.03, +1.18] | +0.74 [+0.21, +1.32] * |
| `character__dense__bge` | `character__hybrid__bge` | +3.9% [-2.6%, +13.2%] | +9.2% [+2.6%, +17.1%] * | — | — |
| `sentence__dense__bge` | `sentence__hybrid__bge` | +1.3% [-7.9%, +10.5%] | +5.3% [+0.0%, +11.8%] | — | — |
| `sentence800__dense__hf` | `sentence800__hybrid__hf` | +14.5% [+0.0%, +30.3%] | +7.9% [+1.3%, +15.8%] * | — | — |
| `sentence800__dense__bge` | `sentence800__hybrid__bge` | +0.0% [-9.2%, +9.2%] | +5.3% [+0.0%, +11.8%] | — | — |

`*` = the paired-bootstrap 95% interval excludes 0.
<!-- END:cmp_dense_hybrid -->
<!-- BEGIN:cmp_embedding -->
### 3.2 Embedding model: MiniLM vs. BGE-small

Same chunks and retrieval mode; A = `all-MiniLM-L6-v2` (384-d, 256 word-piece window), B = `BAAI/bge-small-en-v1.5` (384-d, 512 word-piece window). Both are local Hugging Face models run through `llm.embed_texts(provider=hf)`.

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) | Δ Correctness (1-5) (B−A) | Δ Faithfulness (1-5) (B−A) |
|---|---|---|---|---|---|
| `character__dense__hf` | `character__dense__bge` | +9.2% [-2.6%, +21.1%] | -2.6% [-10.5%, +3.9%] | — | — |
| `character__hybrid__hf` | `character__hybrid__bge` | +5.3% [-3.9%, +15.8%] | +1.3% [-2.6%, +5.3%] | — | — |
| `sentence800__dense__hf` | `sentence800__dense__bge` | +13.2% [-1.3%, +28.9%] | +5.3% [+1.3%, +10.5%] * | — | — |
| `sentence800__hybrid__hf` | `sentence800__hybrid__bge` | -1.3% [-9.2%, +5.3%] | +2.6% [+0.0%, +6.6%] | — | — |

`*` = the paired-bootstrap 95% interval excludes 0.
<!-- END:cmp_embedding -->
Read the `*` markers: only intervals excluding 0 are real differences at n≈38.

### Slide 13 — The advanced stages, one at a time
<!-- BEGIN:cmp_rerank -->
### 3.4 Cross-encoder re-ranking

A = hybrid retrieval; B = the same hybrid top-20 re-scored by `cross-encoder/ms-marco-MiniLM-L-6-v2` and cut to the top 5.

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) | Δ Correctness (1-5) (B−A) | Δ Faithfulness (1-5) (B−A) |
|---|---|---|---|---|---|
| `character__hybrid__hf` | `character__hybrid_rerank__hf` | +15.8% [+6.5%, +27.6%] * | +0.0% [-3.9%, +3.9%] | — | — |
| `character__hybrid__bge` | `character__hybrid_rerank__bge` | +13.2% [+0.0%, +27.6%] | -1.3% [-5.3%, +2.6%] | — | — |
| `sentence800__hybrid__hf` | `sentence800__hybrid_rerank__hf` | +7.9% [-3.9%, +19.7%] | -3.9% [-9.2%, +0.0%] | — | — |
| `sentence800__hybrid__bge` | `sentence800__hybrid_rerank__bge` | +9.2% [-2.6%, +22.4%] | -6.6% [-14.5%, -1.3%] * | +0.03 [-0.47, +0.50] | -0.18 [-0.55, +0.13] |

`*` = the paired-bootstrap 95% interval excludes 0.
<!-- END:cmp_rerank -->
<!-- BEGIN:cmp_hyde -->
### 3.6 HyDE query expansion

A = hybrid retrieval on the raw question; B = the dense side embeds an LLM-written hypothetical answer passage (BM25 sees question + passage).

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) | Δ Correctness (1-5) (B−A) | Δ Faithfulness (1-5) (B−A) |
|---|---|---|---|---|---|
| `character__hybrid__bge` | `character__hybrid_hyde__bge` | +25.0% [+9.2%, +40.8%] * | +1.3% [+0.0%, +3.9%] | — | — |
| `sentence800__hybrid__bge` | `sentence800__hybrid_hyde__bge` | +26.3% [+13.2%, +40.8%] * | -2.6% [-7.9%, +2.6%] | — | — |

`*` = the paired-bootstrap 95% interval excludes 0.
<!-- END:cmp_hyde -->
<!-- BEGIN:cmp_ctx -->
### 3.5 Contextual chunk headers

A = hybrid retrieval over plain chunks; B = identical chunks whose *embedded* text is prefixed with `<paper title> | <section>` (display text and BM25 unchanged).

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) | Δ Correctness (1-5) (B−A) | Δ Faithfulness (1-5) (B−A) |
|---|---|---|---|---|---|
| `character__hybrid__hf` | `character_ctx__hybrid__hf` | +3.9% [-2.6%, +13.2%] | -2.6% [-7.9%, +2.6%] | — | — |
| `character__hybrid__bge` | `character_ctx__hybrid__bge` | +6.6% [+0.0%, +14.5%] | -1.3% [-6.6%, +2.6%] | — | — |
| `sentence800__hybrid__hf` | `sentence800_ctx__hybrid__hf` | +0.0% [-11.8%, +11.8%] | -3.9% [-9.2%, +1.3%] | — | — |
| `sentence800__hybrid__bge` | `sentence800_ctx__hybrid__bge` | +2.6% [-6.6%, +13.2%] | -2.6% [-6.6%, +0.0%] | — | — |

`*` = the paired-bootstrap 95% interval excludes 0.
<!-- END:cmp_ctx -->
* Re-ranking: better passages, but can lose the second paper in multi-hop questions. HyDE: biggest gain — **caveat: the LLM has memorised these famous papers**. Context headers: an honest null result.

### Slide 14 — Chunking ablation with the confound fixed
* The original comparison changed boundary strategy *and* size. Fix: cap the sentence chunker at ≈800 chars so only boundary placement differs.
<!-- BEGIN:chunk_stats -->
| Chunker | # chunks | mean chars | median chars |
|---|---|---|---|
| `character` | 1087 | 796 | 800 |
| `sentence` | 257 | 2981 | 3124 |
| `sentence800` | 1568 | 699 | 727 |
<!-- END:chunk_stats -->
<!-- BEGIN:cmp_chunk_uncontrolled -->
### 3.3a Chunking ablation — UNCONTROLLED (the original, size-confounded comparison)

A = character windows (~800 chars); B = production sentence chunker at its default size (~3,000 chars); embedder BGE-small. (BGE's 512-word-piece window covers only the first ~2,000 characters of a ~3,000-character chunk.) Boundary strategy and chunk size differ at once, so differences cannot be attributed to boundary alignment alone.

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) | Δ Correctness (1-5) (B−A) | Δ Faithfulness (1-5) (B−A) |
|---|---|---|---|---|---|
| `character__dense__bge` | `sentence__dense__bge` | +14.5% [+2.6%, +27.6%] * | +3.9% [-1.3%, +9.2%] | — | — |
| `character__hybrid__bge` | `sentence__hybrid__bge` | +11.8% [-2.6%, +27.6%] | +0.0% [-5.3%, +5.3%] | — | — |

`*` = the paired-bootstrap 95% interval excludes 0.
<!-- END:cmp_chunk_uncontrolled -->
<!-- BEGIN:cmp_chunk_controlled -->
### 3.3b Chunking ablation — SIZE-CONTROLLED (boundary strategy isolated)

A = character windows (~800 chars); B = sentence-boundary chunks capped at ~800 chars (`chunk_blocks_semantic(chunk_size=200)`). Chunk size is held (approximately) constant, so any difference is due to where chunk boundaries fall.

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) | Δ Correctness (1-5) (B−A) | Δ Faithfulness (1-5) (B−A) |
|---|---|---|---|---|---|
| `character__dense__hf` | `sentence800__dense__hf` | +0.0% [-14.5%, +14.5%] | -2.6% [-9.2%, +2.6%] | — | — |
| `character__dense__bge` | `sentence800__dense__bge` | +3.9% [-7.9%, +15.8%] | +5.3% [+1.3%, +10.5%] * | — | — |
| `character__hybrid__hf` | `sentence800__hybrid__hf` | +6.6% [-3.9%, +18.4%] | +0.0% [-3.9%, +3.9%] | — | — |
| `character__hybrid__bge` | `sentence800__hybrid__bge` | +0.0% [-7.9%, +7.9%] | +1.3% [+0.0%, +3.9%] | — | — |

`*` = the paired-bootstrap 95% interval excludes 0.
<!-- END:cmp_chunk_controlled -->

### Slide 15 — Abstention, NLI grounding and judge validation
<!-- BEGIN:abstention -->
Positive class = *answerable*. AUROC is the probability that an answerable question's top-passage signal exceeds an unanswerable one's (0.5 = chance). The threshold maximises Youden's J on all 46 questions; *LOO accuracy* re-picks the threshold without each question in turn and classifies that question with it, which removes the optimism of tuning and testing on the same data. With only 8 unanswerable questions, intervals are wide.

| Config | Signal | AUROC [95% CI] | Threshold | Unanswerable caught | Answerable wrongly abstained | LOO accuracy |
|---|---|---|---|---|---|---|
| `character__dense__hf` | top dense cosine | 0.81 [0.63–0.95] | 0.625 | 7/8 | 9/38 | 74% |
| `character__dense__bge` | top dense cosine | 0.87 [0.74–0.97] | 0.794 | 7/8 | 6/38 | 83% |
| `character__hybrid__hf` | top dense cosine | 0.76 [0.55–0.92] | 0.589 | 7/8 | 12/38 | 70% |
| `character__hybrid__bge` | top dense cosine | 0.91 [0.81–0.98] | 0.794 | 8/8 | 7/38 | 83% |
| `sentence__dense__bge` | top dense cosine | 0.85 [0.66–0.97] | 0.775 | 7/8 | 7/38 | 78% |
| `sentence__hybrid__bge` | top dense cosine | 0.89 [0.77–0.97] | 0.774 | 8/8 | 10/38 | 76% |
| `sentence800__dense__hf` | top dense cosine | 0.81 [0.57–0.97] | 0.621 | 7/8 | 6/38 | 80% |
| `sentence800__dense__bge` | top dense cosine | 0.90 [0.78–0.99] | 0.797 | 7/8 | 4/38 | 85% |
| `sentence800__hybrid__hf` | top dense cosine | 0.81 [0.57–0.97] | 0.556 | 7/8 | 6/38 | 80% |
| `sentence800__hybrid__bge` | top dense cosine | 0.96 [0.89–1.00] | 0.770 | 8/8 | 3/38 | 91% |
| `character__hybrid_rerank__hf` | top dense cosine | 0.81 [0.67–0.92] | 0.588 | 8/8 | 14/38 | 65% |
| `character__hybrid_rerank__hf` | re-ranker probability | 0.87 [0.67–0.99] | 0.984 | 7/8 | 6/38 | 80% |
| `character__hybrid_rerank__bge` | top dense cosine | 0.86 [0.74–0.95] | 0.791 | 8/8 | 11/38 | 72% |
| `character__hybrid_rerank__bge` | re-ranker probability | 0.87 [0.67–0.99] | 0.984 | 7/8 | 6/38 | 80% |
| `sentence800__hybrid_rerank__hf` | top dense cosine | 0.78 [0.62–0.91] | 0.547 | 7/8 | 12/38 | 70% |
| `sentence800__hybrid_rerank__hf` | re-ranker probability | 0.86 [0.64–0.99] | 0.988 | 7/8 | 6/38 | 80% |
| `sentence800__hybrid_rerank__bge` | top dense cosine | 0.83 [0.69–0.93] | 0.788 | 7/8 | 10/38 | 72% |
| `sentence800__hybrid_rerank__bge` | re-ranker probability | 0.86 [0.64–0.99] | 0.988 | 7/8 | 6/38 | 80% |
| `character_ctx__hybrid__hf` | top dense cosine | 0.79 [0.60–0.93] | 0.613 | 7/8 | 14/38 | 63% |
| `character_ctx__hybrid__bge` | top dense cosine | 0.90 [0.78–0.98] | 0.748 | 6/8 | 2/38 | 80% |
| `sentence800_ctx__hybrid__hf` | top dense cosine | 0.75 [0.56–0.90] | 0.622 | 7/8 | 16/38 | 57% |
| `sentence800_ctx__hybrid__bge` | top dense cosine | 0.88 [0.74–0.97] | 0.762 | 6/8 | 4/38 | 85% |
| `character__hybrid_hyde__bge` | top dense cosine | 0.77 [0.54–0.96] | 0.833 | 5/8 | 4/38 | 72% |
| `sentence800__hybrid_hyde__bge` | top dense cosine | 0.80 [0.63–0.94] | 0.821 | 5/8 | 4/38 | 85% |
| `character__dense__hf` | LLM self-abstention (no threshold) | — | — | 7/8 | 7/38 | — |
| `character__hybrid__hf` | LLM self-abstention (no threshold) | — | — | 8/8 | 3/38 | — |
| `sentence800__hybrid__bge` | LLM self-abstention (no threshold) | — | — | 7/8 | 4/38 | — |
| `sentence800__hybrid_rerank__bge` | LLM self-abstention (no threshold) | — | — | 8/8 | 3/38 | — |

The hybrid *fused* score is deliberately not offered as a signal: it is min-max normalised per query, so the top passage scores ≈1 whatever the question (AUROC 0.47–0.72 across the hybrid configurations; for dense-only retrieval it equals the cosine). Thresholds are specific to the embedding model, because cosine scales differ between models.
<!-- END:abstention -->
<!-- BEGIN:nli_grounding -->
Per answerable, non-abstained answer: fraction of sentences each method flags as unsupported, compared with the LLM judge's faithfulness score (1-5). A good grounding check has a strongly **negative** rank correlation with faithfulness (more flagged = less faithful). *AUROC* = how well "fraction supported" separates answers the judge rated faithful (>= 4) from the rest. The judge is itself an imperfect reference.

| Method | n answers | Mean flagged-sentence rate | Spearman ρ vs judge faithfulness | AUROC for judge-faithful (≥4) |
|---|---|---|---|---|
| Lexical guard (production heuristic) | 135 | 10% | -0.24 | 0.71 |
| NLI entailment, binary (flagged if P(entail) < 0.5) | 135 | 56% | -0.03 | 0.46 |
| NLI mean entailment probability (continuous; ρ expected **positive**) | 135 | 57% (1 − mean P) | +0.07 | 0.50 |

Judge-faithful answers (≥4): 124/135 — with few low-faithfulness answers the AUROC is noisy.
<!-- END:nli_grounding -->
<!-- BEGIN:judge_agreement -->
24 answers were sampled (stratified: half judged correct (≥4), half not) from the scored configurations and re-judged by a second, different model. `results/judge_validation.csv` also has a blank `human_correctness` column (1-5, same rubric) for a human grader; the human rows below fill in once it is completed.

| Pair | n | Exact agreement | Within ±1 | Spearman ρ | Quadratic-weighted κ |
|---|---|---|---|---|---|
| Judge 1 vs Judge 2 (correctness) | 24 | 75% | 88% | +0.93 | +0.87 |
| Judge 1 vs human | 0 (pending human labels) | — | — | — | — |
| Judge 2 vs human | 0 (pending human labels) | — | — | — | — |
<!-- END:judge_agreement -->

Talking points: the top dense cosine / re-ranker probability predict "not in the documents" (a calibrated threshold *matches* the generator's own abstention but skips the LLM call); **NLI grounding is a negative result** (the small NLI model over-flags technical paraphrase and does not track the judge, while the lexical guard correlates modestly); two judges from different families agree (κ ≈ 0.87) but **human agreement is still pending**.

### Slide 16 — Failure analysis (worked examples) and taxonomy
Use `REPORT.md` §8: **q19** right paper / wrong passage (fixed by HyDE, not by re-ranking); **q25** cross-paper confusion (fixed by re-ranking); **q38** multi-hop (made worse by re-ranking).
<!-- BEGIN:failure_taxonomy -->
Each answerable question is assigned to exactly one bucket, from the per-question CSVs (evidence recall, judge correctness, abstention, citation accuracy). Unanswerable questions are reported separately.

| Config | Answer judged correct (≥4) | Wrong: no gold evidence retrieved (retrieval failure) | Wrong although gold evidence was retrieved (generation / reading failure) | Wrong: abstained on an answerable question | Correct answer but its citations point at passages without the evidence | Unanswerable: hallucinated an answer |
|---|---|---|---|---|---|---|
| `character__dense__hf` | 15 (39%) | 4 (11%) | 3 (8%) | 7 (18%) | 9 (24%) | 1/8 |
| `character__hybrid__hf` | 19 (50%) | 3 (8%) | 1 (3%) | 3 (8%) | 12 (32%) | 0/8 |
| `sentence800__hybrid__bge` | 22 (58%) | 2 (5%) | 2 (5%) | 3 (8%) | 9 (24%) | 1/8 |
| `sentence800__hybrid_rerank__bge` | 25 (66%) | 3 (8%) | 1 (3%) | 3 (8%) | 6 (16%) | 0/8 |
<!-- END:failure_taxonomy -->

### Slide 17 — Live demo, limitations, next steps
* **Demo (web app):** upload a paper → ask → toggle *Re-rank*, *HyDE*, *NLI grounding*, *Abstain if unsure*; open a source card's score chips (Dense / BM25 / Importance / Re-rank); open *Claim-by-claim grounding*; ask an off-topic question to see the abstention banner. CLI: `python ask.py "…"`.
* **Limitations:** 46 questions → wide CIs (abstention rests on 8 unanswerable ones); answer quality scored for only some configurations; same-family judge; HyDE inflated by memorisation; thresholds are embedding-specific.
* **Next:** a larger / scientific-text NLI model, human labels for the judge-validation sheet, a held-out private corpus the LLM has never seen, larger test set, a second judge family.
