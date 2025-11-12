"""
RAG 인덱싱 서비스
"""
from __future__ import annotations

import json
from typing import Iterable, List, Optional

from sqlmodel import Session, select

from app.models.document import Document, DocumentChunk
from .embedding_service import embed_texts


def _split_text(
    text: str,
    *,
    chunk_size: int = 900,
    overlap: int = 150,
) -> List[str]:
    """
    단순 문자 기반 청킹.

    PDF/TXT 업로드 시 사용하며 이미 청크가 생성된 JSONL을 다룰 때는
    chunk_size를 조정하거나 직접 청크 텍스트를 넘길 수 있다.
    """
    if not text:
        return []

    lines = text.splitlines()
    normalized = [line.strip() for line in lines if line.strip()]
    joined = "\n".join(normalized)

    chunks: List[str] = []
    start = 0
    length = len(joined)

    while start < length:
        end = min(start + chunk_size, length)
        chunk = joined[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < length else end
        if start < 0:
            start = 0

    return chunks


async def index_document_from_text(
    session: Session,
    document: Document,
    content: str,
    *,
    metadata: Optional[dict] = None,
    chunk_size: int = 900,
    overlap: int = 150,
) -> None:
    """단일 문서를 청크로 분할하고 임베딩을 저장"""
    chunks = _split_text(content, chunk_size=chunk_size, overlap=overlap)
    await index_document_from_chunks(session, document, chunks, metadata=metadata)


async def index_document_from_chunks(
    session: Session,
    document: Document,
    chunks: Iterable[str],
    *,
    metadata: Optional[dict] = None,
    metadata_list: Optional[List[Optional[dict]]] = None,
) -> None:
    """이미 나뉘어진 청크 리스트를 사용하여 인덱싱"""
    chunk_list = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]
    if not chunk_list:
        return

    embeddings = await embed_texts(chunk_list)

    existing = session.exec(
        select(DocumentChunk).where(DocumentChunk.document_id == document.id)
    ).all()
    for row in existing:
        session.delete(row)

    if metadata_list and len(metadata_list) != len(chunk_list):
        raise ValueError("metadata_list 길이는 청크 수와 동일해야 합니다.")

    for idx, (chunk_text, embedding) in enumerate(zip(chunk_list, embeddings)):
        chunk_meta = (
            metadata_list[idx]
            if metadata_list is not None
            else metadata
        )
        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=idx,
            content=chunk_text,
            embedding=embedding,
            chunk_metadata=json.dumps(chunk_meta, ensure_ascii=False)
            if chunk_meta
            else None,
        )
        session.add(chunk)

    document.is_indexed = True
    session.add(document)
    session.commit()


