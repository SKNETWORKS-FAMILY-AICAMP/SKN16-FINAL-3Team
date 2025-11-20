# 상품 데이터 벡터 인덱싱 가이드

## 개요

상품 데이터(JSONL 파일)를 pgvector에 임베딩 벡터로 변환하여 저장하는 방법을 안내합니다.

## 사전 요구사항

1. **PostgreSQL + pgvector** 설치 및 실행
2. **데이터베이스 연결 설정** 완료 (`DATABASE_URL` 환경 변수)
3. **OpenAI API Key** 설정 (`OPENAI_API_KEY` 환경 변수)
4. **상품 데이터 파일** 존재 (`backend/data/rag_sources/products/hakyung/*.jsonl`)

## 실행 방법

### 1. 전체 상품 인덱싱

```bash
# 프로젝트 루트에서 실행
cd backend
python scripts/index_product_data.py
```

**기본 동작:**
- 모든 상품 데이터를 pgvector에 인덱싱
- 이미 인덱싱된 청크는 건너뛰기 (중복 방지)

### 2. 특정 상품만 인덱싱

```bash
# 특정 상품 코드만 인덱싱
python scripts/index_product_data.py --product-code CRD-CRE
```

**예시:**
```bash
# 프리미엄 신용카드만 인덱싱
python scripts/index_product_data.py --product-code CRD-CRE

# 정기예금만 인덱싱
python scripts/index_product_data.py --product-code DEP-TIM
```

### 3. 재인덱싱 (기존 데이터 삭제 후 재생성)

```bash
# 전체 상품 재인덱싱
python scripts/index_product_data.py --force

# 특정 상품 재인덱싱
python scripts/index_product_data.py --product-code CRD-CRE --force
```

**주의:** `--force` 옵션은 기존 데이터를 **삭제**하고 처음부터 다시 인덱싱합니다.

## 인덱싱 프로세스

### 단계별 설명

```
[1단계] 데이터베이스 초기화
  - pgvector 확장 활성화
  - ProductChunk 테이블 생성
  
[2단계] 상품 데이터 로드
  - JSONL 파일에서 청크 데이터 읽기
  - 이미 인덱싱된 청크 확인 (중복 체크)
  
[3단계] 임베딩 생성
  - 각 청크 텍스트를 OpenAI 임베딩으로 변환
  - 1536 차원 벡터 생성
  
[4단계] pgvector 저장
  - ProductChunk 테이블에 저장
  - 임베딩 벡터 + 메타데이터 저장
  
[5단계] 완료
  - 인덱싱된 청크 수 출력
  - 성공/실패 상태 반환
```

### 예상 소요 시간

- **소규모** (1개 상품, ~20개 청크): 약 1-2분
- **중규모** (10개 상품, ~200개 청크): 약 10-15분
- **대규모** (50개 상품, ~1000개 청크): 약 1-2시간

**참고:** OpenAI API 호출 속도에 따라 달라질 수 있습니다.

## 성능 최적화: 벡터 인덱스 생성 (선택)

pgvector에 벡터 인덱스를 생성하면 검색 속도가 크게 향상됩니다.

### PostgreSQL에서 실행

```sql
-- 벡터 인덱스 생성 (IVFFlat 사용)
CREATE INDEX ON product_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 인덱스 생성 확인
\d+ product_chunks
```

**주의사항:**
- 인덱스는 상품 데이터가 충분히 인덱싱된 후 생성해야 합니다
- `lists` 값은 데이터 크기에 따라 조정 (일반적으로 100-1000)
- 인덱스 생성 시간: 데이터 크기에 따라 수분~수십분 소요

### 인덱스 타입 설명

- **IVFFlat**: 빠른 근사 검색 (기본값)
- **HNSW**: 더 정확한 검색 (PostgreSQL 13+)

## 인덱싱 상태 확인

### Python 스크립트로 확인

```python
from sqlmodel import Session, select, func
from app.database import engine
from app.models import ProductChunk

with Session(engine) as session:
    # 전체 청크 수
    total = session.exec(
        select(func.count(ProductChunk.id))
    ).one()
    
    # 상품별 청크 수
    product_counts = session.exec(
        select(
            ProductChunk.product_code,
            func.count(ProductChunk.id)
        ).group_by(ProductChunk.product_code)
    ).all()
    
    print(f"총 청크 수: {total}")
    for product_code, count in product_counts:
        print(f"  - {product_code}: {count}개")
```

### PostgreSQL에서 직접 확인

```sql
-- 전체 청크 수
SELECT COUNT(*) FROM product_chunks;

-- 상품별 청크 수
SELECT product_code, COUNT(*) as chunk_count
FROM product_chunks
GROUP BY product_code
ORDER BY chunk_count DESC;

-- 임베딩이 없는 청크 확인
SELECT product_code, COUNT(*) as missing_embedding
FROM product_chunks
WHERE embedding IS NULL
GROUP BY product_code;
```

## 트러블슈팅

### 1. "벡터 검색이 비활성화되어 있습니다"

**원인:**
- SQLModel이나 pgvector가 설치되지 않음
- 데이터베이스 연결 실패

**해결:**
```bash
# 필요한 패키지 설치 확인
pip install sqlmodel pgvector psycopg2-binary

# 데이터베이스 연결 확인
# DATABASE_URL 환경 변수 설정 확인
```

### 2. "임베딩 생성 실패"

**원인:**
- OpenAI API Key가 설정되지 않음
- API 호출 한도 초과
- 네트워크 오류

**해결:**
```bash
# OpenAI API Key 확인
echo $OPENAI_API_KEY

# 환경 변수 설정 (Linux/Mac)
export OPENAI_API_KEY="sk-..."

# 환경 변수 설정 (Windows PowerShell)
$env:OPENAI_API_KEY="sk-..."
```

### 3. "테이블이 없습니다"

**원인:**
- ProductChunk 테이블이 생성되지 않음

**해결:**
```bash
# 데이터베이스 테이블 초기화
python scripts/init_database_tables.py
```

### 4. 인덱싱 속도가 느림

**원인:**
- API 호출 한도 제한
- 네트워크 지연

**해결:**
- 배치 처리로 변경 (현재는 순차 처리)
- API 호출 간 딜레이 추가 (Rate Limiting)

## 자동화: 시스템 설정 스크립트에 추가

`setup_system.py`에 상품 데이터 인덱싱을 추가하려면:

```python
# backend/scripts/setup_system.py에 추가
steps = [
    ("init_database_tables.py", "데이터베이스 테이블 생성"),
    ("init_exam_data.py", "시험 데이터 초기화"),
    ("init_learning_materials.py", "학습 자료 RAG 인덱싱"),
    ("index_product_data.py", "상품 데이터 벡터 인덱싱")  # 추가
]
```

## API 엔드포인트로 인덱싱 (선택)

FastAPI 엔드포인트를 만들어서 API로도 인덱싱할 수 있습니다:

```python
# backend/app/routers/products.py (예시)
@router.post("/index", response_model=Dict)
async def index_products(
    product_code: Optional[str] = None,
    force_reindex: bool = False,
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """상품 데이터 벡터 인덱싱 (관리자만 가능)"""
    product_service = ProductKnowledgeService(session=session)
    indexed_counts = product_service.index_product_data_to_vector_db(
        product_code=product_code,
        force_reindex=force_reindex
    )
    return {"indexed_counts": indexed_counts}
```

## 확인 사항

인덱싱 완료 후 다음을 확인하세요:

1. ✅ **데이터베이스 확인**
   ```sql
   SELECT COUNT(*) FROM product_chunks;
   ```

2. ✅ **벡터 검색 테스트**
   ```python
   from app.services.product_knowledge_service import ProductKnowledgeService
   from app.database import get_session
   
   with next(get_session()) as session:
       service = ProductKnowledgeService(session=session)
       results = service.search_by_vector_similarity(
           query="연회비는 얼마인가요?",
           product_codes=["CRD-CRE"],
           top_k=3
       )
       print(f"검색 결과: {len(results)}개")
   ```

3. ✅ **RAG 평가 테스트**
   - 시뮬레이션 실행 후 벡터 검색 동작 확인

