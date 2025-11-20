"""
RAG 문서 일괄 임포트 스크립트
backend/data/rag 폴더의 모든 JSON 파일을 데이터베이스에 업로드하고 인덱싱합니다.
"""
import asyncio
import json
from pathlib import Path
from sqlmodel import Session, select
from app.database import engine
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import embed_text

async def import_rag_documents():
    """RAG 문서들을 데이터베이스에 임포트"""
    
    rag_data_path = Path("/app/data/rag_sources")
    
    if not rag_data_path.exists():
        print(f"❌ RAG 데이터 폴더를 찾을 수 없습니다: {rag_data_path}")
        return
    
    # 모든 하위 폴더에서 JSONL 파일 찾기
    json_files = list(rag_data_path.glob("**/*.jsonl"))
    print(f"📁 {len(json_files)}개의 JSONL 파일을 발견했습니다.")
    
    with Session(engine) as session:
        imported_count = 0
        skipped_count = 0
        error_count = 0
        
        for json_file in json_files:
            try:
                # JSONL 파일 읽기 (각 줄이 JSON 객체)
                all_content = []
                title = json_file.stem  # 파일명을 제목으로 사용
                
                with open(json_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                data = json.loads(line)
                                # content 필드가 있으면 추가
                                if 'content' in data:
                                    all_content.append(data['content'])
                                # text 필드가 있으면 추가
                                elif 'text' in data:
                                    all_content.append(data['text'])
                                # 전체 JSON을 문자열로 추가
                                else:
                                    all_content.append(json.dumps(data, ensure_ascii=False))
                            except json.JSONDecodeError:
                                continue
                
                content = '\n\n'.join(all_content)
                
                if not content:
                    print(f"⚠️ {json_file.name}: 내용이 비어있습니다.")
                    skipped_count += 1
                    continue
                
                # 이미 존재하는지 확인
                existing = session.exec(
                    select(Document).where(Document.title == title)
                ).first()
                
                if existing:
                    print(f"⏭️ {title}: 이미 존재합니다.")
                    skipped_count += 1
                    continue
                
                # 문서 생성
                document = Document(
                    title=title,
                    category="RAG",
                    file_path=str(json_file),
                    file_type=".json",
                    file_size=json_file.stat().st_size,
                    description=f"은행 업무 관련 문서 - {title}",
                    uploaded_by=1  # admin user
                )
                session.add(document)
                session.commit()
                session.refresh(document)
                
                # 청킹 및 임베딩
                chunk_size = 500
                overlap = 50
                chunks = []
                
                # 텍스트를 청크로 분할
                for i in range(0, len(content), chunk_size - overlap):
                    chunk_text = content[i:i + chunk_size]
                    if chunk_text.strip():
                        chunks.append(chunk_text)
                
                print(f"📄 {title}: {len(chunks)}개의 청크로 분할")
                
                # 각 청크에 대해 임베딩 생성
                for idx, chunk_text in enumerate(chunks):
                    try:
                        # 임베딩 생성
                        embedding = await embed_text(chunk_text)
                        
                        # DocumentChunk 생성
                        chunk = DocumentChunk(
                            document_id=document.id,
                            content=chunk_text,
                            chunk_index=idx,
                            embedding=embedding,
                            chunk_metadata={"source": "json_import"}
                        )
                        session.add(chunk)
                    except Exception as e:
                        print(f"  ❌ 청크 {idx} 임베딩 오류: {e}")
                        error_count += 1
                
                session.commit()
                imported_count += 1
                print(f"✅ {title}: 완료")
                
            except Exception as e:
                print(f"❌ {json_file.name}: {e}")
                error_count += 1
                session.rollback()
        
        print(f"\n{'='*60}")
        print(f"✅ 임포트 완료: {imported_count}개")
        print(f"⏭️ 건너뜀: {skipped_count}개")
        print(f"❌ 오류: {error_count}개")
        print(f"{'='*60}")

if __name__ == "__main__":
    print("🚀 RAG 문서 임포트를 시작합니다...\n")
    asyncio.run(import_rag_documents())

