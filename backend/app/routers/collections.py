"""Collection CRUD and membership routes. All rows are user-scoped and
soft-delete aware (a deleted collection is never returned)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Collection, Document, DocumentCollection, User
from ..schemas import (
    CollectionCreate,
    CollectionDocumentsIn,
    CollectionOut,
    CollectionUpdate,
    DeleteResult,
    DocumentOut,
)

router = APIRouter(prefix="/api/collections", tags=["collections"])


def _get_owned_collection(db: Session, collection_id: str, user: User) -> Collection:
    coll = db.get(Collection, collection_id)
    if coll is None or coll.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Collection not found.")
    if coll.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this collection.")
    return coll


def _owned_document(db: Session, document_id: str, user: User) -> Document:
    doc = db.get(Document, document_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this document.")
    return doc


@router.post("", response_model=CollectionOut, status_code=201)
def create_collection(
    payload: CollectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    coll = Collection(
        user_id=current_user.id, name=payload.name.strip(),
        description=payload.description,
    )
    db.add(coll)
    db.commit()
    db.refresh(coll)
    out = CollectionOut.model_validate(coll)
    out.document_count = 0
    return out


@router.get("", response_model=list[CollectionOut])
def list_collections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(Collection, func.count(DocumentCollection.document_id))
        .outerjoin(
            DocumentCollection,
            DocumentCollection.collection_id == Collection.id,
        )
        .where(Collection.user_id == current_user.id, Collection.deleted_at.is_(None))
        .group_by(Collection.id)
        .order_by(Collection.created_at.desc(), Collection.id.desc())
    ).all()
    result = []
    for coll, count in rows:
        out = CollectionOut.model_validate(coll)
        out.document_count = int(count)
        result.append(out)
    return result


@router.put("/{collection_id}", response_model=CollectionOut)
def update_collection(
    collection_id: str,
    payload: CollectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    coll = _get_owned_collection(db, collection_id, current_user)
    if payload.name is not None:
        coll.name = payload.name.strip()
    if payload.description is not None:
        coll.description = payload.description
    db.commit()
    db.refresh(coll)
    return CollectionOut.model_validate(coll)


@router.delete("/{collection_id}", response_model=DeleteResult)
def delete_collection(
    collection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a collection. Its documents are untouched (only membership
    is dropped implicitly by the collection no longer being returned)."""
    coll = _get_owned_collection(db, collection_id, current_user)
    coll.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return DeleteResult(id=collection_id, deleted=True)


@router.post("/{collection_id}/documents", response_model=CollectionOut)
def add_documents(
    collection_id: str,
    payload: CollectionDocumentsIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    coll = _get_owned_collection(db, collection_id, current_user)
    for doc_id in payload.document_ids:
        _owned_document(db, doc_id, current_user)  # ownership + existence
        exists = db.get(DocumentCollection, {"document_id": doc_id, "collection_id": collection_id})
        if exists is None:
            db.add(DocumentCollection(document_id=doc_id, collection_id=collection_id))
    db.commit()
    count = db.execute(
        select(func.count(DocumentCollection.document_id)).where(
            DocumentCollection.collection_id == collection_id
        )
    ).scalar_one()
    out = CollectionOut.model_validate(coll)
    out.document_count = int(count)
    return out


@router.delete("/{collection_id}/documents/{document_id}", response_model=DeleteResult)
def remove_document(
    collection_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_collection(db, collection_id, current_user)
    link = db.get(DocumentCollection, {"document_id": document_id, "collection_id": collection_id})
    if link is None:
        raise HTTPException(status_code=404, detail="Document is not in this collection.")
    db.delete(link)
    db.commit()
    return DeleteResult(id=document_id, deleted=True)


@router.get("/{collection_id}/documents", response_model=list[DocumentOut])
def list_collection_documents(
    collection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_collection(db, collection_id, current_user)
    from ..models import Chunk

    rows = db.execute(
        select(Document, func.count(Chunk.id))
        .join(DocumentCollection, DocumentCollection.document_id == Document.id)
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .where(
            DocumentCollection.collection_id == collection_id,
            Document.deleted_at.is_(None),
        )
        .group_by(Document.id)
        .order_by(Document.created_at.desc(), Document.id.desc())
    ).all()
    out = []
    for doc, count in rows:
        d = DocumentOut.model_validate(doc)
        d.chunk_count = int(count)
        out.append(d)
    return out
