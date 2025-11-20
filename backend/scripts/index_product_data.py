#!/usr/bin/env python3
"""
상품 데이터 벡터 인덱싱 스크립트
JSONL 파일에서 상품 데이터를 로드하여 pgvector에 인덱싱
"""
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session
from app.database import engine, init_db
from app.services.product_knowledge_service import ProductKnowledgeService


def index_all_products(force_reindex: bool = False):
    """
    모든 상품 데이터를 pgvector에 인덱싱
    
    Args:
        force_reindex: True면 기존 데이터 삭제 후 재인덱싱
    """
    print("🚀 상품 데이터 벡터 인덱싱 시작...")
    print(f"📁 데이터 경로: {project_root / 'data'}")
    
    # 데이터베이스 초기화 (테이블 생성)
    print("\n1️⃣ 데이터베이스 테이블 초기화...")
    init_db()
    print("✅ 데이터베이스 초기화 완료\n")
    
    # ProductKnowledgeService 초기화 (session 전달)
    with Session(engine) as session:
        try:
            print("2️⃣ ProductKnowledgeService 초기화...")
            product_service = ProductKnowledgeService(
                use_llm=True,
                session=session  # 벡터 검색 활성화
            )
            print("✅ ProductKnowledgeService 초기화 완료\n")
            
            # 벡터 검색 가능 여부 확인
            if not product_service.use_vector_search:
                print("⚠️ 벡터 검색이 비활성화되어 있습니다.")
                print("   - SQLModel 및 pgvector가 설치되어 있는지 확인하세요.")
                print("   - 데이터베이스 연결이 정상인지 확인하세요.")
                return False
            
            print("3️⃣ 상품 데이터 벡터 인덱싱...")
            indexed_counts = product_service.index_product_data_to_vector_db(
                product_code=None,  # None이면 전체 상품
                force_reindex=force_reindex
            )
            
            if indexed_counts:
                print(f"\n✅ 인덱싱 완료!")
                print(f"📊 인덱싱 결과:")
                total = sum(indexed_counts.values())
                for product_code, count in indexed_counts.items():
                    print(f"  - {product_code}: {count}개 청크")
                print(f"  - 총합: {total}개 청크")
                
                # 벡터 인덱스 생성 안내
                print(f"\n💡 성능 향상을 위한 벡터 인덱스 생성 (선택사항):")
                print(f"   PostgreSQL에서 다음 SQL을 실행하세요:")
                print(f"   CREATE INDEX ON product_chunks")
                print(f"   USING ivfflat (embedding vector_cosine_ops)")
                print(f"   WITH (lists = 100);")
                
                return True
            else:
                print("⚠️ 인덱싱할 상품 데이터가 없습니다.")
                return False
                
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            session.rollback()
            return False


def index_single_product(product_code: str, force_reindex: bool = False):
    """
    특정 상품만 인덱싱
    
    Args:
        product_code: 상품 코드 (예: "CRD-CRE")
        force_reindex: True면 기존 데이터 삭제 후 재인덱싱
    """
    print(f"🚀 상품 데이터 벡터 인덱싱 시작: {product_code}")
    
    # 데이터베이스 초기화
    init_db()
    
    with Session(engine) as session:
        try:
            product_service = ProductKnowledgeService(
                use_llm=True,
                session=session
            )
            
            if not product_service.use_vector_search:
                print("⚠️ 벡터 검색이 비활성화되어 있습니다.")
                return False
            
            indexed_counts = product_service.index_product_data_to_vector_db(
                product_code=product_code,
                force_reindex=force_reindex
            )
            
            if indexed_counts:
                print(f"✅ {product_code} 인덱싱 완료: {indexed_counts.get(product_code, 0)}개 청크")
                return True
            else:
                print(f"⚠️ {product_code} 인덱싱 실패 또는 데이터 없음")
                return False
                
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            session.rollback()
            return False


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="상품 데이터 벡터 인덱싱")
    parser.add_argument(
        "--product-code",
        type=str,
        help="특정 상품 코드만 인덱싱 (예: CRD-CRE). 생략 시 전체 상품 인덱싱"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="기존 데이터 삭제 후 재인덱싱"
    )
    
    args = parser.parse_args()
    
    if args.product_code:
        # 특정 상품만 인덱싱
        success = index_single_product(args.product_code, force_reindex=args.force)
    else:
        # 전체 상품 인덱싱
        success = index_all_products(force_reindex=args.force)
    
    if success:
        print("\n🎉 상품 데이터 벡터 인덱싱 완료!")
        sys.exit(0)
    else:
        print("\n❌ 상품 데이터 벡터 인덱싱 실패!")
        sys.exit(1)


if __name__ == "__main__":
    main()

