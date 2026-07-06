"""Document upload / listing / deletion routes."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import llm
from ..database import get_db
from ..ingestion import (
    SUPPORTED_TYPES,
    chunk_text,
    extract_text,
    file_type_from_name,
)
from ..models import Chunk, Document
from ..schemas import DeleteResult, DocumentOut, UploadResult

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResult)
async def upload_document(file: UploadFile, db: Session = Depends(get_db)):
    """Ingest one document: extract -> chunk -> embed -> persist."""
    filename = file.filename or "untitled"
    file_type = file_type_from_name(filename)
    if file_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{file_type}'. Allowed: "
            + ", ".join(sorted(SUPPORTED_TYPES)),
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        text, page_count = extract_text(data, file_type)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not read file: {exc}")

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found in the document.",
        )

    # One embedding per chunk, batched inside llm.embed_texts.
    embeddings = llm.embed_texts(chunks)
    if len(embeddings) != len(chunks):
        raise HTTPException(status_code=500, detail="Embedding count mismatch.")

    document = Document(filename=filename, file_type=file_type, page_count=page_count)
    db.add(document)
    db.flush()  # assign document.id before creating chunk rows

    for idx, (content, embedding) in enumerate(zip(chunks, embeddings)):
        db.add(
            Chunk(
                document_id=document.id,
                chunk_index=idx,
                content=content,
                embedding=json.dumps(embedding),
            )
        )

    db.commit()
    db.refresh(document)

    return UploadResult(
        id=document.id, filename=document.filename, chunks_created=len(chunks)
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    """List all documents, newest first, with their chunk counts."""
    rows = (
        db.execute(
            select(Document, func.count(Chunk.id))
            .outerjoin(Chunk, Chunk.document_id == Document.id)
            .group_by(Document.id)
            .order_by(Document.created_at.desc(), Document.id.desc())
        )
    ).all()

    result: list[DocumentOut] = []
    for doc, count in rows:
        out = DocumentOut.model_validate(doc)
        out.chunk_count = int(count)
        result.append(out)
    return result


@router.delete("/{document_id}", response_model=DeleteResult)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document and (via cascade) all of its chunks."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    db.delete(document)
    db.commit()
    return DeleteResult(id=document_id, deleted=True)
