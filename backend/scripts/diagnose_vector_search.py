"""
벡터 검색 실패 원인 진단 스크립트

사용법:
    python backend/scripts/diagnose_vector_search.py
"""
import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import Session, select, text
from app.database import engine
from app.models import ProductChunk
from app.services.product_knowledge_service import ProductKnowledgeService
from app.services.embedding_service import embed_text_sync


def check_database_data(session: Session, product_code: str = "DEP-TIM"):
    """데이터베이스에 인덱싱된 데이터가 있는지 확인"""
    print(f"\n{'='*60}")
    print(f"1. 데이터베이스 데이터 확인 (product_code: {product_code})")
    print(f"{'='*60}")
    
    # 전체 청크 수 확인
    total_chunks = session.exec(select(ProductChunk)).all()
    print(f"  📊 전체 product_chunks 수: {len(total_chunks)}")
    
    # 특정 제품 코드 청크 수 확인
    product_chunks = session.exec(
        select(ProductChunk).where(ProductChunk.product_code == product_code)
    ).all()
    print(f"  📊 {product_code} 청크 수: {len(product_chunks)}")
    
    # embedding이 있는 청크 수 확인
    chunks_with_embedding = session.exec(
        select(ProductChunk).where(
            ProductChunk.product_code == product_code,
            ProductChunk.embedding.isnot(None)
        )
    ).all()
    print(f"  📊 {product_code} embedding 있는 청크 수: {len(chunks_with_embedding)}")
    
    # embedding이 없는 청크 수 확인
    chunks_without_embedding = session.exec(
        select(ProductChunk).where(
            ProductChunk.product_code == product_code,
            ProductChunk.embedding.is_(None)
        )
    ).all()
    print(f"  📊 {product_code} embedding 없는 청크 수: {len(chunks_without_embedding)}")
    
    if len(chunks_with_embedding) == 0:
        print(f"  ❌ 문제: {product_code}에 embedding이 있는 청크가 없습니다!")
        print(f"     → 해결: index_product_data_to_vector_db()를 실행하세요")
        return False
    
    # 샘플 청크 확인
    if chunks_with_embedding:
        sample = chunks_with_embedding[0]
        print(f"\n  📝 샘플 청크:")
        print(f"     - ID: {sample.id}")
        print(f"     - Content (처음 100자): {sample.content[:100]}...")
        print(f"     - Subsection: {sample.subsection_title}")
        if sample.embedding is not None:
            try:
                embedding_dim = len(sample.embedding)
            except (TypeError, AttributeError):
                embedding_dim = "N/A (벡터 타입)"
            print(f"     - Embedding 차원: {embedding_dim}")
        else:
            print(f"     - Embedding 차원: 0 (NULL)")
    
    return True


def check_embedding_service():
    """임베딩 서비스가 정상 작동하는지 확인"""
    print(f"\n{'='*60}")
    print(f"2. 임베딩 서비스 확인")
    print(f"{'='*60}")
    
    test_query = "정기예금 금리는 연 2.15%입니다"
    print(f"  🔍 테스트 쿼리: '{test_query}'")
    
    try:
        embedding = embed_text_sync(test_query)
        if embedding:
            print(f"  ✅ 임베딩 생성 성공 (차원: {len(embedding)})")
            return True
        else:
            print(f"  ❌ 임베딩 생성 실패: None 반환")
            return False
    except Exception as e:
        print(f"  ❌ 임베딩 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vector_search(session: Session, product_code: str = "DEP-TIM"):
    """벡터 검색 테스트"""
    print(f"\n{'='*60}")
    print(f"3. 벡터 검색 테스트 (product_code: {product_code})")
    print(f"{'='*60}")
    
    # ProductKnowledgeService 초기화
    service = ProductKnowledgeService(session=session)
    
    if not service.use_vector_search:
        print(f"  ❌ 벡터 검색 비활성화됨")
        print(f"     → use_vector_search: {service.use_vector_search}")
        return False
    
    print(f"  ✅ 벡터 검색 활성화됨")
    
    # 테스트 쿼리들
    test_queries = [
        "정기예금 금리는 연 2.15%입니다",
        "예금자보호법에 따라 1인당 원리금 합계 5천만원까지 보호됩니다",
        "가입 금액은 최소 50만원부터 가능합니다",
        "12개월 기준 기본 금리는 연 2.15%입니다"
    ]
    
    for query in test_queries:
        print(f"\n  🔍 쿼리: '{query}'")
        
        # 유사도 임계값을 낮춰서 테스트
        for threshold in [0.3, 0.4, 0.5, 0.6]:
            results = service.search_by_vector_similarity(
                query=query,
                product_codes=[product_code],
                top_k=5,
                similarity_threshold=threshold
            )
            
            if results:
                print(f"     ✅ threshold={threshold}: {len(results)}개 결과 (최고 유사도: {results[0].get('similarity', 0):.3f})")
                break
            else:
                print(f"     ❌ threshold={threshold}: 결과 없음")
        
        # 최종 결과 확인
        final_results = service.search_by_vector_similarity(
            query=query,
            product_codes=[product_code],
            top_k=5,
            similarity_threshold=0.5  # 실제 사용하는 값
        )
        
        if not final_results:
            print(f"     ⚠️  실제 사용하는 threshold=0.5에서는 결과 없음!")
            print(f"     💡 해결책: threshold를 낮추거나 인덱싱을 확인하세요")


def check_sql_query(session: Session, product_code: str = "DEP-TIM"):
    """SQL 쿼리 직접 실행하여 확인"""
    print(f"\n{'='*60}")
    print(f"4. SQL 쿼리 직접 실행 테스트")
    print(f"{'='*60}")
    
    # 테스트 쿼리 임베딩 생성
    test_query = "정기예금 금리는 연 2.15%입니다"
    query_embedding = embed_text_sync(test_query)
    
    if not query_embedding:
        print(f"  ❌ 쿼리 임베딩 생성 실패")
        return
    
    print(f"  ✅ 쿼리 임베딩 생성 성공")
    
    # SQL 쿼리 직접 실행
    sql = text("""
        SELECT 
            pc.id,
            pc.product_code,
            pc.content,
            pc.subsection_title,
            1 - (pc.embedding <=> :query_embedding) AS similarity
        FROM product_chunks pc
        WHERE pc.product_code = :product_code
        AND pc.embedding IS NOT NULL
        ORDER BY pc.embedding <=> :query_embedding
        LIMIT 5
    """)
    
    try:
        from pgvector.sqlalchemy import Vector as PgVector
        from sqlalchemy import bindparam
        
        sql = sql.bindparams(
            bindparam("query_embedding", type_=PgVector(1536))
        )
        
        result = session.execute(
            sql,
            {
                "query_embedding": query_embedding,
                "product_code": product_code
            }
        ).fetchall()
        
        print(f"  📊 SQL 쿼리 결과: {len(result)}개")
        
        if result:
            print(f"  ✅ SQL 쿼리 성공!")
            for i, row in enumerate(result[:3], 1):
                print(f"     {i}. 유사도: {row.similarity:.3f}, 제목: {row.subsection_title}")
                print(f"        내용: {row.content[:80]}...")
        else:
            print(f"  ❌ SQL 쿼리 결과 없음")
            print(f"     → 인덱싱이 안 되어 있거나 유사도가 너무 낮을 수 있습니다")
            
            # 유사도 임계값 없이 확인
            sql_no_threshold = text("""
                SELECT 
                    pc.id,
                    pc.product_code,
                    pc.content,
                    pc.subsection_title,
                    1 - (pc.embedding <=> :query_embedding) AS similarity
                FROM product_chunks pc
                WHERE pc.product_code = :product_code
                AND pc.embedding IS NOT NULL
                ORDER BY pc.embedding <=> :query_embedding
                LIMIT 5
            """)
            
            sql_no_threshold = sql_no_threshold.bindparams(
                bindparam("query_embedding", type_=PgVector(1536))
            )
            
            result_no_threshold = session.execute(
                sql_no_threshold,
                {
                    "query_embedding": query_embedding,
                    "product_code": product_code
                }
            ).fetchall()
            
            if result_no_threshold:
                print(f"\n  💡 유사도 임계값 없이 확인: {len(result_no_threshold)}개 결과")
                for i, row in enumerate(result_no_threshold[:3], 1):
                    print(f"     {i}. 유사도: {row.similarity:.3f}, 제목: {row.subsection_title}")
                    print(f"        → threshold를 {row.similarity:.3f} 이하로 낮추면 결과가 나옵니다")
            else:
                print(f"  ❌ 유사도 임계값 없이도 결과 없음 → 인덱싱 문제 가능성 높음")
                
    except Exception as e:
        print(f"  ❌ SQL 쿼리 실행 오류: {e}")
        import traceback
        traceback.print_exc()


def main():
    """메인 진단 함수"""
    print("="*60)
    print("벡터 검색 실패 원인 진단")
    print("="*60)
    
    with Session(engine) as session:
        # 1. 데이터베이스 데이터 확인
        has_data = check_database_data(session, "DEP-TIM")
        
        # 2. 임베딩 서비스 확인
        has_embedding = check_embedding_service()
        
        if not has_data:
            print(f"\n{'='*60}")
            print("❌ 진단 결과: 데이터베이스에 인덱싱된 데이터가 없습니다!")
            print("="*60)
            print("\n해결 방법:")
            print("1. ProductKnowledgeService 인스턴스 생성")
            print("2. index_product_data_to_vector_db() 메서드 호출")
            print("   예: service.index_product_data_to_vector_db(product_code='DEP-TIM')")
            return
        
        if not has_embedding:
            print(f"\n{'='*60}")
            print("❌ 진단 결과: 임베딩 서비스가 정상 작동하지 않습니다!")
            print("="*60)
            print("\n해결 방법:")
            print("1. OPENAI_API_KEY 환경 변수 확인")
            print("2. embedding_service 모듈 확인")
            return
        
        # 3. 벡터 검색 테스트
        test_vector_search(session, "DEP-TIM")
        
        # 4. SQL 쿼리 직접 실행
        check_sql_query(session, "DEP-TIM")
        
        print(f"\n{'='*60}")
        print("진단 완료")
        print("="*60)


if __name__ == "__main__":
    main()

