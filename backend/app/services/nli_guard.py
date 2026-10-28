"""Natural-language-inference (entailment) grounding check.

The lexical guard (``hallucination_guard``) flags an answer sentence when it
shares too few key terms with any retrieved chunk. That is cheap but blind to
meaning: a fluent, wrong sentence that reuses source vocabulary passes, and a
correct paraphrase can be flagged. Here each answer sentence is the NLI
*hypothesis* and passages from the retrieved chunks are the *premises*; a
sentence is supported when some premise **entails** it.

To keep it fast on CPU the check is retrieve-then-verify: for every answer
sentence only the few premise windows with the highest lexical overlap are run
through the NLI model, instead of every sentence x every window.

Dependencies (``transformers`` + ``torch``, installed with sentence-transformers)
are imported lazily; ``check_answer_nli`` raises if unavailable and callers fall
back to the lexical guard.
"""
from __future__ import annotations

import logging
import re
import threading

from ..config import settings
from ..ingestion import split_sentences

logger = logging.getLogger("papertrail.nli_guard")

_CITE_RE = re.compile(r"\s*[\[【]\d+[^\]】]*[\]】]")
_MD_RE = re.compile(r"(\*\*|__|`)")
_WORD_RE = re.compile(r"[a-z0-9]+")
_MIN_WORDS = 4
_WINDOW_SENTENCES = 3
_WINDOW_STRIDE = 2
_PREMISES_PER_SENTENCE = 4

_BUNDLE: dict[str, tuple] = {}
_LOCK = threading.Lock()


def available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _load():
    name = settings.nli_model
    with _LOCK:
        bundle = _BUNDLE.get(name)
        if bundle is None:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            tok = AutoTokenizer.from_pretrained(name)
            model = AutoModelForSequenceClassification.from_pretrained(name).eval()
            labels = {int(i): l.lower() for i, l in model.config.id2label.items()}
            idx = {l: i for i, l in labels.items()}
            ent = next(i for l, i in idx.items() if l.startswith("entail"))
            con = next(i for l, i in idx.items() if l.startswith("contra"))
            bundle = _BUNDLE[name] = (tok, model, ent, con)
    return bundle


def answer_sentences(answer: str) -> list[str]:
    """Checkable claim sentences of a markdown answer: headings, citation
    markers, bold markers and bullets removed; very short fragments dropped."""
    out: list[str] = []
    for line in answer.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^[-*•]\s+", "", line)
        line = _MD_RE.sub("", _CITE_RE.sub("", line)).strip()
        for sent in split_sentences(line):
            if len(sent.split()) >= _MIN_WORDS:
                out.append(sent)
    return out


def _windows(text: str) -> list[str]:
    sents = split_sentences(text.replace("\n", " "))
    if not sents:
        return []
    return [" ".join(sents[i:i + _WINDOW_SENTENCES]) for i in range(0, len(sents), _WINDOW_STRIDE)]


def _overlap(a: set[str], b: str) -> float:
    toks = set(_WORD_RE.findall(b.lower()))
    return len(a & toks) / (len(a) or 1)


def check_answer_nli(answer: str, chunks: list[dict]) -> list[dict]:
    """Per-sentence entailment verdicts.

    Returns ``[{"sentence","supported","entailment","contradiction","label",
    "source_chunk_id"}]``. ``entailment`` is the best entailment probability over
    the candidate premises; ``supported`` is ``entailment >= nli_entailment_threshold``.
    """
    import torch

    sentences = answer_sentences(answer)
    if not sentences:
        return []
    tok, model, ent_i, con_i = _load()

    premises: list[tuple[str | None, str]] = []
    for c in chunks:
        for w in _windows(c.get("text", "")):
            premises.append((c.get("chunk_id"), w))

    pairs: list[tuple[int, str | None, str, str]] = []  # (sentence idx, chunk id, premise, hypothesis)
    for si, sent in enumerate(sentences):
        sent_toks = set(_WORD_RE.findall(sent.lower()))
        ranked = sorted(premises, key=lambda p: _overlap(sent_toks, p[1]), reverse=True)
        for cid, prem in ranked[:_PREMISES_PER_SENTENCE]:
            pairs.append((si, cid, prem, sent))

    best: dict[int, dict] = {}
    if pairs:
        with torch.no_grad():
            for start in range(0, len(pairs), 16):
                batch = pairs[start:start + 16]
                enc = tok([p[2] for p in batch], [p[3] for p in batch], truncation="only_first",
                          max_length=512, padding=True, return_tensors="pt")
                probs = torch.softmax(model(**enc).logits, dim=-1)
                for (si, cid, _, _), pr in zip(batch, probs):
                    ent, con = float(pr[ent_i]), float(pr[con_i])
                    if si not in best or ent > best[si]["entailment"]:
                        best[si] = {"entailment": ent, "contradiction": con, "source_chunk_id": cid}

    thr = settings.nli_entailment_threshold
    results = []
    for si, sent in enumerate(sentences):
        b = best.get(si, {"entailment": 0.0, "contradiction": 0.0, "source_chunk_id": None})
        supported = b["entailment"] >= thr
        if supported:
            label = "entailed"
        elif b["contradiction"] > b["entailment"] and b["contradiction"] >= 0.5:
            label = "contradicted"
        else:
            label = "neutral"
        results.append({
            "sentence": sent,
            "supported": supported,
            "entailment": round(b["entailment"], 4),
            "contradiction": round(b["contradiction"], 4),
            "label": label,
            "source_chunk_id": b["source_chunk_id"] if supported else None,
        })
    return results
