# Document Ingestion and Chunking

## Supported file types

PaperTrail accepts seven upload formats: PDF, DOCX, PPTX, TXT, Markdown, XLSX, and CSV. The set of accepted extensions is kept in a constant, `SUPPORTED_TYPES`, inside `backend/app/ingestion.py`, deliberately mirrored against the actual upload-time validator in `services/extractor.py` so the two never silently drift out of sync.

## Content sniffing

Because a file's extension can lie about its actual content — a renamed binary blob, for instance — PaperTrail performs a best-effort content check before trusting an upload. For PDFs, it checks that the first bytes (after stripping any leading whitespace) begin with the literal signature `%PDF-`. For `.txt` and `.md` files, it rejects any file containing a NUL byte within the first 8 kilobytes (a strong signal of binary content), then tries to decode the file as UTF-8; if that fails, it falls back to a tolerant check requiring at least 85% of the sampled bytes to be printable ASCII or extended-Latin characters.

## Text extraction

Extraction returns a tuple of `(text, page_count)`. For PDFs, PaperTrail uses the `pypdf` library to read each page and concatenates the extracted text with a blank line between pages; `page_count` is the number of pages. For `.txt` and `.md` files, the raw bytes are decoded as UTF-8 with a tolerant `errors="replace"` policy, and `page_count` is `None` because these formats have no page concept.

## Two chunking strategies

PaperTrail implements two distinct chunking strategies, selected by the `chunking_strategy` setting (`"character"` or `"semantic"`, defaulting to `"semantic"` for new deployments). Existing already-stored chunks are never automatically re-chunked or re-embedded when this setting changes, because re-embedding an entire existing corpus has a real API cost — the setting only affects documents uploaded after the change.

### Character-based chunking

The character-based strategy (`chunk_text` / `chunk_blocks`) slides a fixed-width window of `CHUNK_SIZE` characters (default 800) across the normalized document text, advancing by `CHUNK_SIZE - CHUNK_OVERLAP` characters each step, where `CHUNK_OVERLAP` defaults to 150 characters. Each window is stripped of leading/trailing whitespace, and empty windows are dropped. The loop stops once a window reaches the end of the text, so no tiny trailing chunk that is already fully contained in the previous chunk gets emitted. This strategy pays no attention to sentence or paragraph boundaries, so a chunk boundary can fall in the middle of a sentence or even a word.

### Sentence-boundary (semantic) chunking

The semantic strategy (`chunk_blocks_semantic`) first splits the document into individual sentences using `split_sentences`, a regular-expression-based splitter that treats punctuation followed by whitespace as a candidate sentence boundary, then re-merges any split that immediately follows a known abbreviation (such as "Mr.", "Dr.", "U.S.", "e.g.", "approx.", or "Inc.") so that abbreviations don't create false sentence breaks. Whole sentences are then accumulated into a chunk until adding the next sentence would exceed a token budget, approximated as `chunk_size` tokens times `CHARS_PER_TOKEN` (4 characters per token, since no real tokenizer dependency is used) — with the default `chunk_size` of 800 tokens, that budget is roughly 3,200 characters, about four times larger than the character strategy's 800-character window. Consecutive chunks overlap by whole sentences rather than a raw character window — the default overlap is 2 sentences — so a chunk boundary in the semantic strategy never lands mid-sentence.

## Page and section provenance

Both `chunk_blocks` and `chunk_blocks_semantic` operate on provenance-carrying "blocks" (extracted separately, each block tagged with a page number and, where applicable, whether it is a heading) rather than on raw undifferentiated text. Each emitted chunk inherits the page number and the current section heading of the block it starts in — the "current heading" carries forward across body blocks until the next heading block is reached. This is what lets PaperTrail's citations point not just at a document, but at a specific page and section within it.
