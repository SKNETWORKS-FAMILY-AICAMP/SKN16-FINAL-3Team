"""
벡터 검색 성능 향상을 위한 pgvector 인덱스 생성 스크립트

사용법:
    python scripts/create_vector_index.py [--index-type hnsw|ivfflat] [--force]

인덱스 타입:
    - hnsw: HNSW 인덱스 (기본값, 빠른 검색, 더 많은 메모리 사용)
    - ivfflat: IVFFlat 인덱스 (적은 메모리, 느린 검색)
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from sqlmodel import Session
from app.database import engine
from app.config import settings
import argparse


def create_hnsw_index(session, force: bool = False):
    """HNSW 인덱스 생성 (빠른 검색, 권장)"""
    index_name = "product_chunks_embedding_hnsw_idx"
    
    try:
        # 기존 인덱스 확인
        result = session.execute(text(f"""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'product_chunks' 
            AND indexname = '{index_name}'
        """))
        
        if result.fetchone():
            if force:
                print(f"🔄 기존 HNSW 인덱스 삭제 중...")
                session.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
                session.commit()
            else:
                print(f"✅ HNSW 인덱스 이미 존재: {index_name}")
                return True
        
        print(f"📦 HNSW 인덱스 생성 중... (시간이 걸릴 수 있습니다)")
        
        # HNSW 인덱스 생성
        # m: 연결 수 (기본값 16, 높을수록 정확하지만 느림)
        # ef_construction: 인덱스 생성 시 탐색 범위 (기본값 64, 높을수록 정확하지만 느림)
        session.execute(text(f"""
            CREATE INDEX {index_name}
            ON product_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """))
        session.commit()
        
        print(f"✅ HNSW 인덱스 생성 완료: {index_name}")
        print(f"   - m = 16: 각 노드의 최대 연결 수")
        print(f"   - ef_construction = 64: 인덱스 생성 시 탐색 범위")
        return True
        
    except Exception as e:
        print(f"❌ HNSW 인덱스 생성 실패: {e}")
        session.rollback()
        return False


def create_ivfflat_index(session, force: bool = False):
    """IVFFlat 인덱스 생성 (적은 메모리, 느린 검색)"""
    index_name = "product_chunks_embedding_ivfflat_idx"
    
    try:
        # 기존 인덱스 확인
        result = session.execute(text(f"""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'product_chunks' 
            AND indexname = '{index_name}'
        """))
        
        if result.fetchone():
            if force:
                print(f"🔄 기존 IVFFlat 인덱스 삭제 중...")
                session.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
                session.commit()
            else:
                print(f"✅ IVFFlat 인덱스 이미 존재: {index_name}")
                return True
        
        # 총 레코드 수 확인 (lists 파라미터 결정용)
        count_result = session.execute(text("SELECT COUNT(*) FROM product_chunks WHERE embedding IS NOT NULL"))
        total_rows = count_result.scalar() or 0
        
        # lists 파라미터: sqrt(총 레코드 수) 정도가 적절
        lists = max(100, int(total_rows ** 0.5))
        lists = min(lists, 1000)  # 최대 1000으로 제한
        
        print(f"📦 IVFFlat 인덱스 생성 중... (총 {total_rows}개 레코드, lists={lists})")
        
        # IVFFlat 인덱스 생성
        session.execute(text(f"""
            CREATE INDEX {index_name}
            ON product_chunks
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = {lists})
        """))
        session.commit()
        
        print(f"✅ IVFFlat 인덱스 생성 완료: {index_name}")
        print(f"   - lists = {lists}: 클러스터 수")
        return True
        
    except Exception as e:
        print(f"❌ IVFFlat 인덱스 생성 실패: {e}")
        session.rollback()
        return False


def check_index_status(session):
    """인덱스 상태 확인"""
    print("\n📊 현재 인덱스 상태:")
    print("=" * 80)
    
    result = session.execute(text("""
        SELECT 
            indexname,
            indexdef
        FROM pg_indexes
        WHERE tablename = 'product_chunks'
        AND indexname LIKE '%embedding%'
        ORDER BY indexname
    """))
    
    indexes = result.fetchall()
    if indexes:
        for idx_name, idx_def in indexes:
            print(f"\n✅ {idx_name}")
            print(f"   {idx_def}")
    else:
        print("⚠️ 벡터 인덱스가 없습니다. 인덱스를 생성하세요.")
    
    # 통계 정보
    stats_result = session.execute(text("""
        SELECT 
            COUNT(*) as total_chunks,
            COUNT(embedding) as chunks_with_embedding,
            pg_size_pretty(pg_total_relation_size('product_chunks')) as table_size
        FROM product_chunks
    """))
    
    stats = stats_result.fetchone()
    if stats:
        total, with_embedding, table_size = stats
        print(f"\n📈 테이블 통계:")
        print(f"   - 총 청크 수: {total}")
        print(f"   - 임베딩 있는 청크: {with_embedding}")
        print(f"   - 테이블 크기: {table_size}")


def main():
    parser = argparse.ArgumentParser(description="벡터 검색 성능 향상을 위한 pgvector 인덱스 생성")
    parser.add_argument(
        "--index-type",
        choices=["hnsw", "ivfflat"],
        default="hnsw",
        help="인덱스 타입 선택 (기본값: hnsw)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="기존 인덱스가 있어도 재생성"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="인덱스 상태만 확인"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🔍 벡터 검색 인덱스 관리")
    print("=" * 80)
    
    with Session(engine) as session:
        if args.check:
            check_index_status(session)
            return
        
        # pgvector 확장 확인
        try:
            session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            session.commit()
            print("✅ pgvector 확장 확인 완료")
        except Exception as e:
            print(f"❌ pgvector 확장 활성화 실패: {e}")
            return
        
        # 인덱스 상태 확인
        check_index_status(session)
        
        # 인덱스 생성
        if args.index_type == "hnsw":
            success = create_hnsw_index(session, force=args.force)
        else:
            success = create_ivfflat_index(session, force=args.force)
        
        if success:
            print("\n" + "=" * 80)
            print("✅ 인덱스 생성 완료!")
            print("=" * 80)
            print("\n💡 성능 향상 팁:")
            print("   1. 인덱스 생성 후 ANALYZE 실행: ANALYZE product_chunks;")
            print("   2. 쿼리 성능 확인: EXPLAIN ANALYZE SELECT ...")
            print("   3. 인덱스 사용 확인: 인덱스가 사용되는지 쿼리 플랜 확인")
            
            # ANALYZE 실행 제안
            try:
                print("\n🔄 테이블 통계 업데이트 중...")
                session.execute(text("ANALYZE product_chunks"))
                session.commit()
                print("✅ 통계 업데이트 완료")
            except Exception as e:
                print(f"⚠️ 통계 업데이트 실패: {e}")


if __name__ == "__main__":
    main()

