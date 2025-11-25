#!/usr/bin/env python3
"""
상품 데이터 pgvector 인덱싱 상태 확인 스크립트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session, select, func
from app.database import engine, init_db
from app.models import ProductChunk


def check_product_indexing():
    """상품 데이터 인덱싱 상태 확인"""
    print("🔍 상품 데이터 pgvector 인덱싱 상태 확인 중...\n")
    
    # 데이터베이스 초기화 (테이블 생성 확인)
    init_db()
    
    with Session(engine) as session:
        try:
            # 전체 청크 수 확인
            total_count = session.exec(
                select(func.count(ProductChunk.id))
            ).one()
            
            print(f"📊 전체 인덱싱된 청크 수: {total_count}개\n")
            
            if total_count == 0:
                print("❌ 인덱싱된 상품 데이터가 없습니다.")
                print("\n💡 인덱싱을 실행하려면:")
                print("   python scripts/index_product_data.py")
                return False
            
            # 상품별 청크 수 확인
            product_counts = session.exec(
                select(
                    ProductChunk.product_code,
                    func.count(ProductChunk.id).label("count")
                ).group_by(ProductChunk.product_code)
                .order_by(func.count(ProductChunk.id).desc())
            ).all()
            
            print("📦 상품별 인덱싱된 청크 수:")
            for product_code, count in product_counts:
                print(f"   - {product_code}: {count}개")
            
            # 임베딩이 없는 청크 확인
            missing_embedding = session.exec(
                select(func.count(ProductChunk.id))
                .where(ProductChunk.embedding.is_(None))
            ).one()
            
            if missing_embedding > 0:
                print(f"\n⚠️ 임베딩이 없는 청크: {missing_embedding}개")
            else:
                print(f"\n✅ 모든 청크에 임베딩이 있습니다.")
            
            # 파일 시스템의 상품 데이터 확인
            products_dir = project_root / "data" / "rag_sources" / "products" / "hakyung"
            if products_dir.exists():
                jsonl_files = list(products_dir.glob("*.jsonl"))
                print(f"\n📁 파일 시스템의 상품 데이터 파일 수: {len(jsonl_files)}개")
                
                indexed_products = {code for code, _ in product_counts}
                file_products = {f.stem for f in jsonl_files}
                
                missing_in_db = file_products - indexed_products
                if missing_in_db:
                    print(f"\n⚠️ 데이터베이스에 인덱싱되지 않은 상품:")
                    for product_code in sorted(missing_in_db):
                        print(f"   - {product_code}")
                else:
                    print(f"\n✅ 모든 상품 파일이 인덱싱되어 있습니다.")
            else:
                print(f"\n⚠️ 상품 데이터 디렉토리를 찾을 수 없습니다: {products_dir}")
            
            print("\n✅ 확인 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = check_product_indexing()
    sys.exit(0 if success else 1)

