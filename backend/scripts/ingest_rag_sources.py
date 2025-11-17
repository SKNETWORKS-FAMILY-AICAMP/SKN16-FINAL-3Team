"""
사전 생성된 JSONL RAG 소스를 데이터베이스에 인덱싱

Usage:
    python -m backend.scripts.ingest_rag_sources \
        --base-path backend/data/rag_sources \
        --uploaded-by 1
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlmodel import Session, select

from app.database import engine
from app.models.document import Document
from app.services.rag_indexer import index_document_from_chunks


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG JSONL 소스 인덱싱")
    parser.add_argument(
        "--base-path",
        default="backend/data/rag_sources",
        help="JSONL 소스가 위치한 루트 디렉토리",
    )
    parser.add_argument(
        "--uploaded-by",
        type=int,
        default=1,
        help="Document.uploaded_by 에 기록할 사용자 ID",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 쓰지 않고 어떤 문서가 처리될지 출력만 합니다.",
    )
    return parser.parse_args()


def infer_title_and_category(record: Dict, fallback: str) -> Tuple[str, str]:
    if "law_name" in record:
        return record["law_name"], "bank_law"
    if "product" in record:
        return record["product"], "product"
    if "title" in record:
        return record["title"], "general"
    return fallback, "general"


def build_metadata(record: Dict) -> Dict:
    exclude_keys = {"text"}
    return {k: v for k, v in record.items() if k not in exclude_keys}


async def ingest_file(
    session: Session,
    path: Path,
    uploaded_by: int,
    dry_run: bool = False,
) -> None:
    if not path.exists():
        print(f"[WARN] 파일을 찾을 수 없습니다: {path}")
        return

    chunk_texts: List[str] = []
    chunk_meta: List[Dict] = []
    doc_title: Optional[str] = None
    source_category = "general"

    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            text = record.get("text")
            if not text:
                question = record.get("question", "")
                answer = record.get("answer", "")
                if question or answer:
                    text_parts = []
                    if question:
                        text_parts.append(f"Q: {question}")
                    if answer:
                        text_parts.append(f"A: {answer}")
                    text = "\n".join(text_parts).strip()
            if not text:
                continue

            title_candidate, inferred_category = infer_title_and_category(record, path.stem)
            if not doc_title:
                doc_title = title_candidate
                source_category = inferred_category

            chunk_texts.append(text)
            chunk_meta.append(build_metadata(record))

    if not chunk_texts:
        print(f"[WARN] 청크가 비어 있어 건너뜁니다: {path.name}")
        return

    doc_title = doc_title or path.stem
    file_size = path.stat().st_size if path.exists() else sum(len(c) for c in chunk_texts)

    # 기존 문서 찾기
    document = session.exec(
        select(Document).where(Document.title == doc_title, Document.category == "RAG")
    ).first()

    description = f"source={source_category}, file={path.name}"

    if document:
        document.file_path = str(path)
        document.file_type = path.suffix or ".jsonl"
        document.file_size = file_size
        document.description = description
        document.uploaded_by = uploaded_by
        document.is_indexed = False
        print(f"[INFO] 기존 문서 업데이트: {doc_title}")
    else:
        document = Document(
            title=doc_title,
            category="RAG",
            file_path=str(path),
            file_type=path.suffix or ".jsonl",
            file_size=file_size,
            description=description,
            uploaded_by=uploaded_by,
            is_indexed=False,
        )
        session.add(document)
        session.commit()
        session.refresh(document)
        print(f"[INFO] 새 문서 생성: {doc_title}")

    if dry_run:
        print(f"  - dry-run: {len(chunk_texts)} chunks 준비됨")
        return

    await index_document_from_chunks(
        session,
        document,
        chunk_texts,
        metadata_list=chunk_meta,
    )
    print(f"  -> {len(chunk_texts)}개의 청크 인덱싱 완료")


async def main() -> None:
    args = parse_arguments()
    base_path = Path(args.base_path)
    if not base_path.exists():
        raise FileNotFoundError(f"Base path not found: {base_path}")

    jsonl_files = list(base_path.rglob("*.jsonl"))
    if not jsonl_files:
        print(f"[WARN] {base_path} 아래에서 JSONL 파일을 찾지 못했습니다.")
        return

    print(f"[INFO] 총 {len(jsonl_files)}개의 JSONL 파일을 처리합니다.")

    with Session(engine) as session:
        for file_path in jsonl_files:
            print(f"[INFO] 처리 중: {file_path}")
            await ingest_file(session, file_path, uploaded_by=args.uploaded_by, dry_run=args.dry_run)

    print("[INFO] 인덱싱 작업이 완료되었습니다.")


if __name__ == "__main__":
    asyncio.run(main())



