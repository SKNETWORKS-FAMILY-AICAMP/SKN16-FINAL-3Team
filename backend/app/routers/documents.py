"""
자료실 API 라우터
문서 업로드, 다운로드, 관리
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from typing import List, Optional
from pathlib import Path
import aiofiles

from app.database import get_session
from app.models.user import User
from app.models.document import Document, DocumentCreate, DocumentRead
from app.utils.auth import get_current_user, get_current_active_admin
from app.utils.file_handler import save_upload_file, delete_file, get_file_size_str
from app.services.rag_indexer import index_document_from_text
from app.config import settings

try:
    from scripts.ingest_rag_sources import ingest_file  # type: ignore
except ImportError:
    ingest_file = None

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentRead)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form(...),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """
    문서 업로드 (관리자만 가능)
    - 파일 저장
    - 메타데이터 저장
    - RAG 인덱싱
    """
    try:
        # 파일 저장
        file_path, file_size = await save_upload_file(
            file,
            category,
            settings.UPLOAD_DIR
        )
        
        # 문서 메타데이터 저장
        document = Document(
            title=title,
            category=category,
            file_path=file_path,
            file_type=Path(file.filename).suffix.lower(),
            file_size=file_size,
            description=description,
            uploaded_by=current_user.id
        )
        
        session.add(document)
        session.commit()
        session.refresh(document)
        
        # RAG 인덱싱 (백그라운드 작업으로 처리하는 것이 좋지만, 여기서는 동기적으로 처리)
        # PDF, TXT 파일만 인덱싱
        if document.file_type in ['.pdf', '.txt']:
            try:
                content = await _extract_text_from_file(file_path, document.file_type)
                await index_document_from_text(session, document, content)
            except Exception as e:
                print(f"Indexing error: {e}")
                # 인덱싱 실패해도 문서는 저장됨
        
        return document
    
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.get("/", response_model=List[DocumentRead])
async def get_documents(
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 500,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    문서 목록 조회
    - 카테고리별 필터링 가능
    - RAG 카테고리 문서는 RAG 탭에서만 조회 가능
    """
    statement = select(Document)
    
    if category:
        # 특정 카테고리만 조회
        statement = statement.where(Document.category == category)
    else:
        # 카테고리가 없으면 RAG 제외하고 조회
        statement = statement.where(Document.category != "RAG")
    
    statement = statement.offset(skip).limit(limit).order_by(Document.title.asc())
    documents = session.exec(statement).all()
    
    return documents


@router.get("/recent", response_model=List[DocumentRead])
async def get_recent_documents(
    limit: int = 3,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    최근 업로드된 문서 조회 (홈페이지용)
    - RAG 카테고리 제외
    - 최신 업로드 순으로 정렬
    """
    statement = (
        select(Document)
        .where(Document.category != "RAG")
        .order_by(Document.upload_date.desc())
        .limit(limit)
    )
    
    documents = session.exec(statement).all()
    return documents


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """문서 상세 정보 조회"""
    statement = select(Document).where(Document.id == document_id)
    document = session.exec(statement).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return document


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    문서 다운로드
    - 다운로드 횟수 증가
    """
    statement = select(Document).where(Document.id == document_id)
    document = session.exec(statement).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    file_path = Path(document.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # 다운로드 횟수 증가
    document.download_count += 1
    session.add(document)
    session.commit()
    
    return FileResponse(
        path=file_path,
        filename=f"{document.title}{document.file_type}",
        media_type="application/octet-stream"
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """
    문서 삭제 (관리자만 가능)
    - 파일 삭제
    - 메타데이터 삭제
    - 관련 청크 삭제
    """
    from app.models.document import DocumentChunk
    
    statement = select(Document).where(Document.id == document_id)
    document = session.exec(statement).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 파일 삭제
    delete_file(document.file_path)
    
    # 관련 청크 삭제
    chunk_statement = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
    chunks = session.exec(chunk_statement).all()
    for chunk in chunks:
        session.delete(chunk)
    
    # 청크 삭제 커밋
    session.commit()
    
    # 문서 삭제
    session.delete(document)
    session.commit()
    
    return {"message": "Document deleted successfully"}


@router.post("/upload-multiple", response_model=List[DocumentRead])
async def upload_multiple_documents(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    다중 문서 업로드 (RAG 전용)
    - TXT 파일만 허용
    - 자동으로 RAG 카테고리로 저장
    - 즉시 인덱싱
    """
    uploaded_documents = []
    
    for file in files:
        try:
            # TXT 파일만 허용
            if not file.filename.endswith('.txt'):
                continue
            
            # 파일 저장
            file_path, file_size = await save_upload_file(
                file,
                "RAG",
                settings.UPLOAD_DIR
            )
            
            # 문서 메타데이터 저장
            document = Document(
                title=Path(file.filename).stem,  # 확장자 제외한 파일명
                category="RAG",
                file_path=file_path,
                file_type=".txt",
                file_size=file_size,
                description="RAG 시스템용 문서",
                uploaded_by=current_user.id
            )
            
            session.add(document)
            session.flush()  # ID 생성을 위해 flush
            
            # RAG 인덱싱
            try:
                content = await _extract_text_from_file(file_path, ".txt")
                await index_document_from_text(session, document, content)
            except Exception as e:
                print(f"Indexing error for {file.filename}: {e}")
            
            uploaded_documents.append(document)
            
        except Exception as e:
            print(f"Upload error for {file.filename}: {e}")
            continue
    
    session.commit()
    
    return uploaded_documents


@router.post("/upload-bulk", response_model=List[DocumentRead])
async def upload_documents_bulk(
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """
    관리자 전용 다중 문서 업로드
    - 여러 파일을 한 번에 업로드
    - 제목은 파일명(확장자 제외)으로 자동 설정
    - 동일 카테고리로 저장
    """
    uploaded_documents: List[Document] = []

    for file in files:
        try:
            file_path, file_size = await save_upload_file(
                file,
                category,
                settings.UPLOAD_DIR
            )

            document = Document(
                title=Path(file.filename).stem,
                category=category,
                file_path=file_path,
                file_type=Path(file.filename).suffix.lower(),
                file_size=file_size,
                description=description,
                uploaded_by=current_user.id
            )
            session.add(document)
            uploaded_documents.append(document)
        except Exception as e:
            print(f"Bulk upload error for {file.filename}: {e}")
            continue

    session.commit()

    # 새로 생성된 문서에 대해 refresh
    for doc in uploaded_documents:
        session.refresh(doc)

    return uploaded_documents


@router.post("/reindex-rag")
async def reindex_rag_documents(
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """
    RAG 문서 동기화 (backend/data/rag_sources 기반)
    """
    if ingest_file is None:
        raise HTTPException(
            status_code=500,
            detail="ingest_rag_sources 모듈을 불러올 수 없습니다."
        )

    try:
        # 우선 순위별 후보 경로
        candidates = [
            Path("/app/data/rag_sources"),  # Docker 컨테이너
        ]

        backend_root = Path(__file__).resolve().parents[2]  # backend/
        candidates.append(backend_root / "data" / "rag_sources")

        workspace_root = Path.cwd()
        candidates.append(workspace_root / "backend" / "data" / "rag_sources")

        rag_data_path = next((path for path in candidates if path.exists()), None)

        if rag_data_path is None:
            raise HTTPException(
                status_code=404,
                detail="RAG 데이터 폴더(rag_sources)를 찾을 수 없습니다."
            )

        jsonl_files = list(rag_data_path.rglob("*.jsonl"))

        if not jsonl_files:
            return {
                "message": "처리할 JSONL 파일이 없습니다.",
                "total_files_scanned": 0,
                "processed_count": 0,
            }

        processed_count = 0
        for file_path in jsonl_files:
            await ingest_file(session, file_path, uploaded_by=current_user.id, dry_run=False)
            processed_count += 1

        return {
            "message": "RAG 데이터 동기화 완료",
            "total_files_scanned": len(jsonl_files),
            "processed_count": processed_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Reindex error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reindex RAG documents: {str(e)}"
        )


@router.get("/categories/list")
async def get_categories(
    current_user: User = Depends(get_current_user)
):
    """문서 카테고리 목록 (RAG 제외)"""
    return {
        "categories": [
            "금융영업",
            "상품개발 및 운용",
            "신용분석 및 리스크관리",
            "외환",
            "은행지식 및 관련법률",
            "하경은행",
        ]
    }


@router.post("/sync-filesystem")
async def sync_filesystem_with_database(
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """
    파일 시스템과 데이터베이스 동기화
    - 존재하지 않는 파일의 DB 레코드 삭제
    - 파일은 있지만 DB에 없는 경우는 무시 (수동으로 처리 필요)
    """
    try:
        # 모든 문서 조회
        statement = select(Document)
        documents = session.exec(statement).all()
        
        deleted_count = 0
        missing_files = []
        
        for document in documents:
            file_path = Path(document.file_path)
            
            # 파일이 존재하지 않으면 DB에서 삭제
            if not file_path.exists():
                print(f"File not found, deleting DB record: {document.file_path}")
                
                # 관련 청크 삭제
                from app.models.document import DocumentChunk
                chunk_statement = select(DocumentChunk).where(DocumentChunk.document_id == document.id)
                chunks = session.exec(chunk_statement).all()
                for chunk in chunks:
                    session.delete(chunk)
                
                # 문서 삭제
                session.delete(document)
                deleted_count += 1
            else:
                missing_files.append({
                    "id": document.id,
                    "title": document.title,
                    "file_path": document.file_path,
                    "exists": True
                })
        
        session.commit()
        
        return {
            "message": "파일 시스템과 데이터베이스 동기화 완료",
            "total_documents_checked": len(documents),
            "deleted_records": deleted_count,
            "remaining_documents": len(missing_files)
        }
        
    except Exception as e:
        print(f"Sync error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync filesystem with database: {str(e)}"
        )


async def _extract_text_from_file(file_path: str, file_type: str) -> str:
    """
    파일에서 텍스트 추출
    """
    if file_type == '.txt':
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            return await f.read()
    
    elif file_type == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

