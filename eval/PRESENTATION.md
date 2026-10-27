# Presentation outline — PaperTrail: evidence-grounded QA over an NLP research-paper corpus

Audience: NLP course instructors and classmates. Emphasis: **live, evidence-backed answers** and the NLP methodology — not the web UI, accounts or deployment. Suggested length: 15–18 minutes, 14 slides. Tables below are generated (`python render_docs.py`).

---

### Slide 1 — Title
*PaperTrail — Evidence-Grounded Research-Paper Question Answering over an NLP Corpus using Hybrid RAG.* Category: RAG Bot for a Niche Domain. Team names.

### Slide 2 — The NLP problem
* LLMs answer from parametric memory: fluent, uncited, sometimes wrong — unacceptable for studying research papers.
* Goal: answers **only from retrieved passages**, with inline citations, a grounding check, and an honest "not in the documents" when the corpus has no answer.
* Questions we care about: factual ("what is DPR's best negative scheme?"), multi-hop across papers ("how do REALM and RAG differ in updating the retriever?"), and unanswerable.

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
* Fetched by arXiv id (`dataset/sources.csv`), converted with the *production* PDF extractor, provenance in `manifest.csv`. Papers chosen so questions can span them (RAG ↔ DPR ↔ ColBERT ↔ BEIR ↔ RAGAS).

### Slide 4 — Preprocessing and chunking
* PDF → text (PyMuPDF, OCR fallback) → NFKC normalisation, re-joined hard-wraps, de-hyphenation, heading + page provenance, References removed.
* Two production chunkers: 800-char windows vs sentence-aware chunks (≈3,000 chars by default). Every chunk keeps page + section.
* Per-chunk **importance score** (TF-IDF informativeness + positional prior) is computed once per document.

### Slide 5 — Embeddings: OpenAI vs. Hugging Face
* `text-embedding-3-small` (1536-d, hosted) vs `all-MiniLM-L6-v2` (384-d, local, 256-word-piece window).
* One switch (`embedding_provider`) in the single AI-provider module; HF is opt-in, OpenAI stays the production default.
* Live demo idea: same question, two embedders, compare retrieved chunks.

### Slide 6 — Retrieval: dense vs. hybrid
* Dense: cosine similarity. Hybrid (production): candidates from dense ∪ BM25, min-max normalise each, fuse **0.6·dense + 0.4·BM25**, multiply by **(1 + 0.2·importance)**.
* Why: embeddings capture meaning, BM25 catches exact terms (`MaxSim`, `ISREL`, "BM25 negative"); importance de-emphasises boilerplate.
* The eval reuses `BM25Index`, `score_chunks` and the production weights — not a re-invention.

### Slide 7 — Generation and the hallucination heuristic
* Prompt: answer only from the numbered context, cite `[n]`, say you could not find it otherwise.
* Grounding check = **lexical heuristic**: flags a sentence if fewer than 3 of its key terms appear in any one retrieved chunk. Cheap, no extra model call — but *not* proof of factual grounding. We measure how well it tracks an LLM judge.

### Slide 8 — Evaluation design
<!-- BEGIN:testset_stats -->
46 questions: 27 factual, 11 multi-hop (evidence in two papers), 8 unanswerable (answer deliberately absent from the corpus).
<!-- END:testset_stats -->
* Questions written from the papers, each with verbatim evidence quotes verified mechanically against the corpus; unanswerable questions verified by *absence* of their key terms.
* Metrics: Doc Recall@5, **Evidence Recall@5** / MRR, correctness / faithfulness / relevance (LLM-as-judge + blank manual column), **citation accuracy**, **unanswerable handling**, guard rate. Bootstrap 95% CIs.
* `--require-online`: a submitted run cannot silently fall back to offline hashing embeddings or extractive answers.

### Slide 9 — Results: retrieval
<!-- BEGIN:retrieval -->
Retrieval metrics are computed over the answerable questions (factual + multi-hop). *Evidence Recall@5* is the fraction of gold evidence passages found in some retrieved chunk (the passage-level metric); *Doc Recall@5* only asks whether a chunk from the right paper was retrieved.

| Config | Doc Recall@5 (answerable) | Doc Recall@5 (multi-hop) | Evidence Recall@5 | Evidence MRR | Section hit |
|---|---|---|---|---|---|
| `character__dense__hf` | 88% [80%–95%] | 59% | 41% [26%–55%] | 0.31 | 42% |
| `character__hybrid__hf` | 93% [87%–99%] | 77% | 49% [34%–63%] | 0.41 | 42% |
| `sentence800__dense__hf` | 86% [78%–93%] | 59% | 41% [26%–55%] | 0.29 | 38% |
| `sentence800__hybrid__hf` | 93% [88%–99%] | 77% | 55% [41%–70%] | 0.45 | 47% |
<!-- END:retrieval -->
Talking point: Doc Recall overstates quality — compare it with Evidence Recall.

### Slide 10 — Results: answer quality
<!-- BEGIN:generation -->
_Not generated by the last run. Run `python run_eval.py` (with a valid LLM key in `backend/.env`) and then `python render_docs.py`._
<!-- END:generation -->
Talking points: correctness vs faithfulness; citation accuracy; how often the system correctly says "not in the documents".

### Slide 11 — Controlled comparisons
<!-- BEGIN:cmp_dense_hybrid -->
### 3.1 Dense-only vs. hybrid retrieval

Same chunks, same embeddings; B adds BM25 fusion and the importance boost (production weights 0.6 dense / 0.4 sparse, ×(1+0.2·importance)).

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) |
|---|---|---|---|
| `character__dense__hf` | `character__hybrid__hf` | +7.9% [-6.6%, +22.4%] | +5.3% [+0.0%, +11.8%] |
| `sentence800__dense__hf` | `sentence800__hybrid__hf` | +14.5% [+0.0%, +30.3%] | +7.9% [+1.3%, +15.8%] * |

`*` = the paired-bootstrap 95% interval excludes 0.
<!-- END:cmp_dense_hybrid -->
<!-- BEGIN:cmp_embedding -->
### 3.2 Embedding model: OpenAI vs. Hugging Face MiniLM

Same chunks and retrieval mode; B swaps OpenAI `text-embedding-3-small` for the local `all-MiniLM-L6-v2` (A = OpenAI).

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) |
|---|---|---|---|
| _not run_ | _not run_ | — | — |

_The configurations for this comparison were not part of this run._

`*` = the paired-bootstrap 95% interval excludes 0.
<!-- END:cmp_embedding -->
Read the `*` markers: only intervals excluding 0 are real differences at n≈38.

### Slide 12 — Chunking ablation with the confound fixed
* The original comparison changed boundary strategy *and* chunk size (≈800 vs ≈3,000 chars).
* Fix: cap the sentence chunker at ≈800 chars so only boundary placement differs.
<!-- BEGIN:chunk_stats -->
| Chunker | # chunks | mean chars | median chars |
|---|---|---|---|
| `character` | 1087 | 796 | 800 |
| `sentence` | 257 | 2981 | 3124 |
| `sentence800` | 1568 | 699 | 727 |
<!-- END:chunk_stats -->
<!-- BEGIN:cmp_chunk_uncontrolled -->
### 3.3a Chunking ablation — UNCONTROLLED (the original, size-confounded comparison)

A = character windows (~800 chars); B = production sentence chunker at its default size (~3,000 chars). Boundary strategy and chunk size differ at once, so differences cannot be attributed to boundary alignment alone.

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) |
|---|---|---|---|
| _not run_ | _not run_ | — | — |

_The configurations for this comparison were not part of this run._

`*` = the paired-bootstrap 95% interval excludes 0.
<!-- END:cmp_chunk_uncontrolled -->
<!-- BEGIN:cmp_chunk_controlled -->
### 3.3b Chunking ablation — SIZE-CONTROLLED (boundary strategy isolated)

A = character windows (~800 chars); B = sentence-boundary chunks capped at ~800 chars (`chunk_blocks_semantic(chunk_size=200)`). Chunk size is held (approximately) constant, so any difference is due to where chunk boundaries fall.

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) |
|---|---|---|---|
| `character__dense__hf` | `sentence800__dense__hf` | +0.0% [-14.5%, +14.5%] | -2.6% [-9.2%, +2.6%] |
| `character__hybrid__hf` | `sentence800__hybrid__hf` | +6.6% [-3.9%, +18.4%] | +0.0% [-3.9%, +3.9%] |

`*` = the paired-bootstrap 95% interval excludes 0.
<!-- END:cmp_chunk_controlled -->

### Slide 13 — Failure analysis (worked examples)
Use `REPORT.md` §7 (reproducible from `results/raw_*.csv`):
1. **q19** — right paper, wrong passage: all 5 chunks from ColBERT, none with the MaxSim sentence (Doc Recall 100% vs Evidence Recall 0%).
2. **q25** — cross-paper confusion: the RAG survey restates RAGAS's three aspects and crowds out the original.
3. **q21** — chunk boundaries: character windows miss BEIR's abstract sentence; sentence-aligned chunks retrieve it.
Add one or two generation failures (lowest-correctness rows of `raw_*.csv`) after the LLM run.

### Slide 14 — Limitations and what next
* 46 questions → wide CIs; same-family generator and judge; textual evidence matching is conservative; heuristic heading detection; exact-cosine stand-in for production's approximate dense search.
* Next: second judge model / human `manual_score`, larger held-out question set, cross-encoder re-ranking, query rewriting (HyDE-style) as an extra retrieval arm.
* Live demo: `python ask.py "Why is BERT unsuitable for sentence-pair similarity search?"` — answer + numbered, paged, sectioned citations.
