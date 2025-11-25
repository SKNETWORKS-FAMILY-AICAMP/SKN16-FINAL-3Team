"""
환경 설정 자동화 유틸리티
환경 변수, 데이터베이스 연결, 의존성 등을 자동으로 검증하고 설정합니다.
"""
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from sqlmodel import Session, text
from app.database import engine
from app.config import settings


def check_environment() -> Dict[str, Tuple[bool, str]]:
    """
    환경 설정 검증
    
    Returns:
        Dict[str, Tuple[bool, str]]: {항목명: (통과여부, 메시지)}
    """
    results = {}
    
    # 1. 데이터베이스 연결 확인
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        results["database"] = (True, "데이터베이스 연결 성공")
    except Exception as e:
        results["database"] = (False, f"데이터베이스 연결 실패: {str(e)}")
    
    # 2. pgvector 확장 확인
    try:
        with Session(engine) as session:
            result = session.exec(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"))
            exists = result.first()
            if exists:
                results["pgvector"] = (True, "pgvector 확장 활성화됨")
            else:
                # 자동 활성화 시도
                try:
                    session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    session.commit()
                    results["pgvector"] = (True, "pgvector 확장 자동 활성화 완료")
                except Exception as e:
                    results["pgvector"] = (False, f"pgvector 확장 활성화 실패: {str(e)}")
    except Exception as e:
        results["pgvector"] = (False, f"pgvector 확인 실패: {str(e)}")
    
    # 3. OpenAI API Key 확인
    api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    if api_key:
        results["openai_key"] = (True, "OpenAI API Key 설정됨")
    else:
        results["openai_key"] = (False, "OpenAI API Key가 설정되지 않음 (임베딩 기능 제한)")
    
    # 4. 상품 데이터 파일 확인
    data_path = Path(__file__).parent.parent.parent / "data"
    if Path("/app/data").exists():
        data_path = Path("/app/data")
    
    products_dir = data_path / "rag_sources" / "products" / "hakyung"
    if products_dir.exists():
        jsonl_files = list(products_dir.glob("*.jsonl"))
        if jsonl_files:
            results["product_files"] = (True, f"상품 데이터 파일 {len(jsonl_files)}개 발견")
        else:
            results["product_files"] = (False, "상품 데이터 JSONL 파일이 없음")
    else:
        results["product_files"] = (False, f"상품 데이터 디렉토리 없음: {products_dir}")
    
    # 5. product_chunks 테이블 확인
    try:
        with Session(engine) as session:
            result = session.exec(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'product_chunks'
                )
            """))
            exists = result.first()
            if exists:
                # 데이터 개수 확인
                count_result = session.exec(text("SELECT COUNT(*) FROM product_chunks"))
                count = count_result.first()
                if count and count > 0:
                    results["product_chunks_table"] = (True, f"product_chunks 테이블 존재 (데이터 {count}개)")
                else:
                    results["product_chunks_table"] = (True, "product_chunks 테이블 존재 (데이터 없음 - 인덱싱 필요)")
            else:
                results["product_chunks_table"] = (False, "product_chunks 테이블이 없음 (자동 생성됨)")
    except Exception as e:
        results["product_chunks_table"] = (False, f"테이블 확인 실패: {str(e)}")
    
    return results


def auto_setup_environment() -> Dict[str, Tuple[bool, str]]:
    """
    환경 자동 설정
    
    Returns:
        Dict[str, Tuple[bool, str]]: {항목명: (성공여부, 메시지)}
    """
    results = {}
    
    # 1. 데이터베이스 초기화
    try:
        from app.database import init_db
        init_db()
        results["db_init"] = (True, "데이터베이스 초기화 완료")
    except Exception as e:
        results["db_init"] = (False, f"데이터베이스 초기화 실패: {str(e)}")
    
    # 2. pgvector 확장 활성화
    try:
        with Session(engine) as session:
            session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
            session.commit()
            results["pgvector"] = (True, "pgvector 확장 활성화 완료")
    except Exception as e:
        results["pgvector"] = (False, f"pgvector 확장 활성화 실패: {str(e)}")
    
    # 3. .env 파일 생성 (없는 경우)
    env_file = Path(__file__).parent.parent.parent / ".env"
    if not env_file.exists():
        try:
            env_content = f"""# 환경 변수 설정 파일
# 자동 생성됨 - 필요시 수정하세요

# 데이터베이스 연결 (기본값)
DATABASE_URL={settings.DATABASE_URL}

# OpenAI API Key (필수 - 임베딩 기능 사용 시)
# OPENAI_API_KEY=your-api-key-here

# JWT 시크릿 키
SECRET_KEY={settings.SECRET_KEY}

# LangSmith 설정 (선택)
# LANGSMITH_API_KEY=
# LANGSMITH_PROJECT=bank-mentor-system
"""
            env_file.write_text(env_content, encoding="utf-8")
            results["env_file"] = (True, ".env 파일 자동 생성됨 (OPENAI_API_KEY 설정 필요)")
        except Exception as e:
            results["env_file"] = (False, f".env 파일 생성 실패: {str(e)}")
    else:
        results["env_file"] = (True, ".env 파일 이미 존재")
    
    return results


def get_environment_status() -> Dict:
    """
    환경 상태 요약 반환 (API용)
    """
    checks = check_environment()
    auto_setup = auto_setup_environment()
    
    all_passed = all(result[0] for result in checks.values())
    
    return {
        "status": "ready" if all_passed else "needs_setup",
        "checks": {
            **checks,
            **auto_setup
        },
        "summary": {
            "total": len(checks),
            "passed": sum(1 for r in checks.values() if r[0]),
            "failed": sum(1 for r in checks.values() if not r[0])
        }
    }

