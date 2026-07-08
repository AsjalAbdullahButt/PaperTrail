"""Visual-intelligence data builders: mind map and timeline.

The mind map turns a stored query + its sources into a node/edge graph (query
-> chunk edges weighted by relevance; chunk <-> chunk edges by embedding
similarity). The timeline extracts dated events from a document's highlights via
the LLM and caches the result so repeat views don't re-call the model.
"""
from __future__ import annotations

import json
import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import llm
from ..models import Chunk, ChunkCoverage  # noqa: F401  (Chunk used below)

logger = logging.getLogger("papertrail.visuals")

CHUNK_EDGE_THRESHOLD = 0.65


def _cosine(a: list[float], b: list[float]) -> float:
    import numpy as np

    va, vb = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def build_mindmap(db: Session, question: str, sources: list[dict]) -> dict:
    """Build ``{"nodes","edges"}`` from a query and its stored source snapshot."""
    label_q = question.strip()[:50]
    nodes = [{"id": "q", "label": label_q, "type": "query"}]
    edges: list[dict] = []

    chunk_ids = [s["chunk_id"] for s in sources if s.get("chunk_id")]
    if not chunk_ids:
        return {"nodes": nodes, "edges": edges}

    # Fetch chunk text + embeddings for chunk<->chunk similarity edges.
    rows = {
        r.id: r
        for r in db.execute(
            select(Chunk.id, Chunk.content, Chunk.embedding).where(Chunk.id.in_(chunk_ids))
        ).all()
    }

    for s in sources:
        cid = s.get("chunk_id")
        if not cid or cid not in rows:
            continue
        heading = s.get("section_heading")
        text = rows[cid].content
        label = (heading or text[:60]).strip()
        nodes.append(
            {
                "id": cid,
                "label": label,
                "type": "chunk",
                "document": s.get("document_name"),
                "importance": s.get("importance_score"),
            }
        )
        edges.append({"source": "q", "target": cid, "weight": float(s.get("ranked_score", 0.0))})

    # Chunk <-> chunk edges by embedding cosine similarity.
    ids = [cid for cid in chunk_ids if cid in rows]
    embeddings = {cid: json.loads(rows[cid].embedding) for cid in ids}
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            if len(embeddings[a]) != len(embeddings[b]):
                continue
            sim = _cosine(embeddings[a], embeddings[b])
            if sim > CHUNK_EDGE_THRESHOLD:
                edges.append({"source": a, "target": b, "weight": round(sim, 4)})

    return {"nodes": nodes, "edges": edges}


_TIMELINE_SYSTEM = (
    "You extract dated events from text. Return ONLY a JSON array of objects "
    '{"date": "YYYY or YYYY-MM", "event": "short description", "chunk_index": int}. '
    "If there are no dated events, return []."
)


def extract_timeline(highlights: list[dict]) -> list[dict]:
    """Extract dated events from a document's highlights via the LLM.

    Returns ``[]`` when offline or when no dates are found; never raises.
    """
    if not highlights:
        return []
    lines = "\n".join(
        f"(chunk {h.get('chunk_index', 0)}) {h.get('text', '')[:200]}"
        for h in highlights[:20]
    )
    prompt = f"Text passages:\n{lines}\n\nExtract dated events as JSON:"
    try:
        raw = llm.complete_text(prompt, system=_TIMELINE_SYSTEM, temperature=0.1)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Timeline extraction failed: %s", exc)
        return []
    return _parse_events(raw)


def _parse_events(raw: str) -> list[dict]:
    if not raw:
        return []
    candidates = [raw]
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if m:
        candidates.append(m.group(0))
    for text in candidates:
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, list):
            events = []
            for item in data:
                if isinstance(item, dict) and item.get("date") and item.get("event"):
                    events.append(
                        {
                            "date": str(item["date"])[:20],
                            "event": str(item["event"])[:500],
                            "chunk_index": int(item.get("chunk_index", 0) or 0),
                        }
                    )
            return events
    return []
