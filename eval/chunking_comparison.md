# Chunking ablation — boundary strategy vs. chunk size

PaperTrail ships two chunkers (`backend/app/ingestion.py`):

* **character** (`chunk_blocks`): fixed windows of 800 characters with 150 characters of overlap. A window can start or end mid-sentence.
* **sentence** (`chunk_blocks_semantic`): whole sentences accumulated up to `chunk_size` "tokens" (4 characters each) with a two-sentence overlap, so a boundary never falls inside a sentence. Its production default is 800 tokens ≈ **3,200 characters**.

## Why there are two ablations

The first version of this comparison (on the previous, self-referential corpus) put these two chunkers side by side at their production defaults. That comparison confounds **boundary strategy** with **chunk size**: the sentence chunker's chunks were roughly four times longer, so any difference could be due to either. This version reports both:

* **3.3a — uncontrolled** (the original comparison, kept for continuity): `character` vs `sentence` at production defaults.
* **3.3b — size-controlled**: `character` vs `sentence800`, where the sentence chunker is capped at `chunk_size=200` (≈800 characters, `ingestion.CHUNK_SIZE // ingestion.CHARS_PER_TOKEN`). Chunk size is held approximately constant, so the difference isolates *where chunk boundaries fall*. The mean/median sizes below show how close the match is; the sentence chunker cannot match character windows exactly because it never splits a sentence.

## Chunk statistics (research-paper corpus)

<!-- BEGIN:chunk_stats -->
| Chunker | # chunks | mean chars | median chars |
|---|---|---|---|
| `character` | 1087 | 796 | 800 |
| `sentence` | 257 | 2981 | 3124 |
| `sentence800` | 1568 | 699 | 727 |
<!-- END:chunk_stats -->

## 3.3a Uncontrolled comparison (size-confounded)

<!-- BEGIN:cmp_chunk_uncontrolled -->
### 3.3a Chunking ablation — UNCONTROLLED (the original, size-confounded comparison)

A = character windows (~800 chars); B = production sentence chunker at its default size (~3,000 chars). Boundary strategy and chunk size differ at once, so differences cannot be attributed to boundary alignment alone.

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) |
|---|---|---|---|
| _not run_ | _not run_ | — | — |

_The configurations for this comparison were not part of this run._

`*` = the paired-bootstrap 95% interval excludes 0.
<!-- END:cmp_chunk_uncontrolled -->

## 3.3b Size-controlled comparison (boundary strategy isolated)

<!-- BEGIN:cmp_chunk_controlled -->
### 3.3b Chunking ablation — SIZE-CONTROLLED (boundary strategy isolated)

A = character windows (~800 chars); B = sentence-boundary chunks capped at ~800 chars (`chunk_blocks_semantic(chunk_size=200)`). Chunk size is held (approximately) constant, so any difference is due to where chunk boundaries fall.

| A | B | Δ Evidence Recall@5 (B−A) | Δ Doc Recall@5 (B−A) |
|---|---|---|---|
| `character__dense__hf` | `sentence800__dense__hf` | +0.0% [-14.5%, +14.5%] | -2.6% [-9.2%, +2.6%] |
| `character__hybrid__hf` | `sentence800__hybrid__hf` | +6.6% [-3.9%, +18.4%] | +0.0% [-3.9%, +3.9%] |

`*` = the paired-bootstrap 95% interval excludes 0.
<!-- END:cmp_chunk_controlled -->

## How to read this

* Differences whose paired-bootstrap interval includes 0 are not distinguishable from noise at this test-set size (≈38 answerable questions per configuration).
* If the uncontrolled gap is larger than the controlled one, the difference is mostly attributable to chunk *size* (larger chunks bundle more text per retrieved slot, which can help recall but dilutes the passage handed to the generator and coarsens page/section attribution); the remainder is attributable to boundary alignment.
* Section hit (Retrieval table in `REPORT.md`) is expected to be worse for large chunks because a chunk carries only the heading of the section it *starts* in.
* A chunk-size effect is also entangled with the embedding model: the HF model sees only the first 256 word-pieces of each chunk, which is why it is only evaluated on the ≈800-character chunkers.
