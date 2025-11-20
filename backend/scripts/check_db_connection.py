#!/usr/bin/env python3
"""
데이터베이스 연결 정보 확인 스크립트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session, text
from app.database import engine
from app.config import settings


def check_db_connection():
    """데이터베이스 연결 정보 확인"""
    print("🔍 데이터베이스 연결 정보 확인 중...\n")
    
    # 설정된 DATABASE_URL 확인
    db_url = settings.DATABASE_URL
    print(f"📋 설정된 DATABASE_URL:")
    print(f"   {db_url}\n")
    
    # URL 파싱
    if "localhost" in db_url or "127.0.0.1" in db_url:
        print("📍 연결 위치: 로컬 PostgreSQL")
    elif "postgres:" in db_url:
        print("📍 연결 위치: Docker 컨테이너 (postgres)")
    else:
        print("📍 연결 위치: 원격 서버 또는 기타")
    
    # 실제 연결 테스트 및 데이터베이스 정보 확인
    try:
        with Session(engine) as session:
            # PostgreSQL 버전 확인
            result = session.exec(text("SELECT version()")).first()
            print(f"\n💾 PostgreSQL 버전:")
            print(f"   {result[:100]}...")
            
            # 현재 데이터베이스 이름 확인
            result = session.exec(text("SELECT current_database()")).first()
            db_name = result
            print(f"\n📂 현재 데이터베이스: {db_name}")
            
            # 호스트 정보 확인
            result = session.exec(text("SELECT inet_server_addr(), inet_server_port()")).first()
            host, port = result
            if host:
                print(f"🌐 서버 주소: {host}:{port}")
            else:
                print(f"🌐 서버 주소: 로컬 연결 (Unix socket 또는 localhost)")
            
            # pgvector 확장 확인
            result = session.exec(
                text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            ).first()
            if result:
                print(f"✅ pgvector 확장: 설치됨")
            else:
                print(f"❌ pgvector 확장: 설치되지 않음")
            
            # product_chunks 테이블 확인
            result = session.exec(
                text("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'product_chunks'
                """)
            ).first()
            table_exists = result[0] if isinstance(result, tuple) else result
            if table_exists > 0:
                count_result = session.exec(text("SELECT COUNT(*) FROM product_chunks")).first()
                count = count_result[0] if isinstance(count_result, tuple) else count_result
                print(f"📊 product_chunks 테이블: 존재함 ({count}개 청크)")
            else:
                print(f"❌ product_chunks 테이블: 존재하지 않음")
            
    except Exception as e:
        print(f"❌ 연결 오류: {e}")
        return False
    
    print("\n✅ 확인 완료!")
    return True


if __name__ == "__main__":
    success = check_db_connection()
    sys.exit(0 if success else 1)

