#!/usr/bin/env python3
"""
학습 자료 초기화 스크립트
learning_materials_for_RAG.txt 파일을 읽어서 RAG 시스템에 인덱싱
"""
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session
from app.database import engine
from app.models.document import Document
from app.services.rag_service import RAGService


def load_learning_materials():
    """학습 자료 텍스트 파일 로드"""
    materials_file = project_root / "data" / "learning_materials_for_RAG.txt"
    
    if not materials_file.exists():
        print(f"❌ 학습 자료 파일을 찾을 수 없습니다: {materials_file}")
        return None
    
    with open(materials_file, 'r', encoding='utf-8') as f:
        return f.read()


def create_learning_document(session: Session, content: str) -> int:
    """학습 자료 문서 생성"""
    print("📚 학습 자료 문서 생성 중...")
    
    # 기존 학습 자료 문서 삭제
    existing_docs = session.exec(
        session.query(Document).where(Document.category == "RAG")
    ).all()
    
    for doc in existing_docs:
        session.delete(doc)
    
    session.commit()
    print(f"✅ {len(existing_docs)}개의 기존 학습 자료 문서 삭제 완료")
    
    # 새 문서 생성
    document = Document(
        title="RAG - 은행 신입사원 연수 학습 자료집",
        category="RAG",
        file_path="learning_materials_for_RAG.txt",
        file_type="txt",
        file_size=len(content.encode('utf-8')),
        description="AI 멘토링 시스템을 위한 RAG 데이터베이스 구축용 학습자료",
        uploaded_by=1,  # 시스템 관리자 ID
        is_indexed=False
    )
    
    session.add(document)
    session.commit()
    session.refresh(document)
    
    print(f"✅ 학습 자료 문서 생성 완료 (ID: {document.id})")
    return document.id


def index_learning_materials(session: Session, document_id: int, content: str):
    """학습 자료를 RAG 시스템에 인덱싱"""
    print("🔍 학습 자료 RAG 인덱싱 중...")
    
    rag_service = RAGService(session)
    
    # 비동기 함수를 동기적으로 실행
    import asyncio
    success = asyncio.run(rag_service.index_document(document_id, content))
    
    if success:
        print("✅ 학습 자료 RAG 인덱싱 완료")
    else:
        print("❌ 학습 자료 RAG 인덱싱 실패")


def main():
    """메인 함수"""
    print("🚀 학습 자료 초기화 시작...")
    
    # 학습 자료 로드
    content = load_learning_materials()
    if not content:
        return
    
    print(f"📊 학습 자료 정보:")
    print(f"  - 파일 크기: {len(content)} 글자")
    print(f"  - 줄 수: {len(content.splitlines())}")
    
    # 데이터베이스 세션 생성
    with Session(engine) as session:
        try:
            # 문서 생성
            document_id = create_learning_document(session, content)
            
            # RAG 인덱싱
            index_learning_materials(session, document_id, content)
            
            print("🎉 학습 자료 초기화 완료!")
            
            # 인덱싱된 문서 확인
            document = session.get(Document, document_id)
            if document and document.is_indexed:
                print(f"📈 문서 '{document.title}'이 RAG 시스템에 성공적으로 인덱싱되었습니다.")
            else:
                print("⚠️ 문서 인덱싱 상태를 확인해주세요.")
                
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            session.rollback()
            raise


if __name__ == "__main__":
    main()

