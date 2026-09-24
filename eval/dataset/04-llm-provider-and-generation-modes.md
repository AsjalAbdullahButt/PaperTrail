# The LLM Provider Layer and Generation Modes

## A single module for every AI call

Every embedding call and every chat-completion call in PaperTrail passes through one module, `backend/app/llm.py`. This concentration is deliberate: swapping the underlying AI provider, or adding a new one, should only ever require editing this one file, never touching the routers, services, or database models that call into it.

## Provider fallback order

For embeddings, `embed_texts` first tries OpenAI (using the model configured by `OPENAI_EMBEDDING_MODEL`, which defaults to `text-embedding-3-small`) when a real-looking OpenAI key is configured. If that call raises an exception for any reason, the failure is logged as a warning and PaperTrail falls back to a deterministic offline embedder rather than crashing the ingestion pipeline. Groq does not offer an embeddings endpoint at all, so embeddings only ever come from OpenAI or the offline fallback — never from Groq.

For chat generation, the fallback order has three tiers: OpenAI first (model configured by `OPENAI_CHAT_MODEL`, default `gpt-4o-mini`), then Groq (model configured by `GROQ_CHAT_MODEL`, default `llama-3.3-70b-versatile`, called through Groq's OpenAI-compatible chat endpoint with a custom `base_url`), and finally an offline extractive fallback if neither hosted provider is configured or both fail.

## The offline fallback

The offline embedder is a deterministic hashing-based bag-of-words vectorizer: each lowercased word token in the text is hashed with MD5, mapped into one of 512 fixed dimensions, and added to that dimension with a sign determined by another bit of the same hash, after which the resulting vector is L2-normalized. Because the mapping is deterministic, the same text always produces the same vector, and cosine similarity between two such vectors reflects word overlap — enough to make retrieval meaningfully test the rest of the pipeline without any paid API. The offline generator does not attempt free-form generation at all; in RAG mode it simply returns the single most relevant retrieved passage (truncated to 600 characters if longer), labeled as coming from "offline mode," and in direct mode (no retrieval) it returns a message explaining that no chat model is configured.

## The four query modes

PaperTrail supports four distinct ways of answering a question:

- **RAG mode** — the default. The model is instructed to answer strictly from the numbered context passages it is given, to say explicitly when the answer isn't in the provided context, and to cite sources inline using bracketed numbers like `[1]` and `[2]` that match the numbered passages.
- **Direct mode** — retrieval is skipped entirely; the model answers from its own general knowledge, with the retrieved-context argument ignored.
- **Multi-hop mode** — described in a separate document, this mode chains two retrieval rounds together to answer questions that require connecting facts spread across more than one passage or document.
- **Compare mode** — a multi-document mode where retrieved passages are grouped and labeled by their source document name (rather than flattened into a single undifferentiated context list), so the model can explicitly say how "Document A" and "Document B" agree or disagree, with citation numbers still running globally across all the grouped documents in the order they are presented.

## Shared answer formatting

Every generation path shares the same formatting instructions appended to its system prompt: if an answer covers more than one distinct point, it should be broken into labeled sections using markdown headings (`## Section Name`); **bold** text should be used only around key terms, never around whole sentences; and a `-` bullet list should only be used when the content is genuinely a list of steps or enumerated items, not as a default structural device. The frontend's citation-rendering component parses this same markdown subset back into rendered UI elements, so the model's formatting choices directly become the visual structure of the answer users see.

## Combining an answer with follow-up questions in one call

Generating an answer and generating a set of suggested follow-up questions used to be two separate, sequential model calls. Because a hosted-model round trip costs roughly the same regardless of what is being asked for, PaperTrail now combines both into a single prompt: the model is asked to write the complete answer, then on its own new line write a fixed marker string, followed by a JSON array of exactly four short follow-up questions with no additional prose. This is implemented by `generate_rag_answer_with_followups`, which returns a tuple of `(answer, raw_followups_blob)`; if the model's response doesn't contain the marker (or no hosted provider is configured at all), the follow-ups blob is simply an empty string, which callers already treat as "no follow-ups available."
