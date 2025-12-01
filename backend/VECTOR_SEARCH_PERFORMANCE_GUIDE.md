# 벡터 검색 성능 향상 가이드

## 📌 개요

벡터 검색 성능을 향상시키기 위한 다양한 방법들을 정리했습니다.

## 🚀 1. pgvector 인덱스 생성 (가장 중요!)

### 현재 상태
- **인덱스 없음**: 전체 테이블 스캔으로 인해 느림
- **인덱스 생성 필요**: HNSW 또는 IVFFlat 인덱스 생성

### 인덱스 생성 방법

```bash
# HNSW 인덱스 생성 (권장, 빠른 검색)
python scripts/create_vector_index.py --index-type hnsw

# IVFFlat 인덱스 생성 (적은 메모리)
python scripts/create_vector_index.py --index-type ivfflat

# 기존 인덱스 재생성
python scripts/create_vector_index.py --index-type hnsw --force

# 인덱스 상태 확인
python scripts/create_vector_index.py --check
```

### 인덱스 타입 비교

| 타입 | 속도 | 메모리 | 정확도 | 권장 사용 |
|------|------|--------|--------|----------|
| **HNSW** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **권장** (대부분의 경우) |
| IVFFlat | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 메모리가 제한적인 경우 |

### HNSW 인덱스 파라미터 튜닝

```sql
-- 기본값 (권장)
CREATE INDEX product_chunks_embedding_hnsw_idx
ON product_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 더 빠른 검색 (정확도 약간 감소)
WITH (m = 16, ef_construction = 32);

-- 더 정확한 검색 (속도 약간 감소)
WITH (m = 32, ef_construction = 128);
```

**파라미터 설명:**
- `m`: 각 노드의 최대 연결 수 (기본값: 16)
  - 높을수록: 정확도 ↑, 인덱스 크기 ↑, 검색 속도 ↓
  - 낮을수록: 정확도 ↓, 인덱스 크기 ↓, 검색 속도 ↑
- `ef_construction`: 인덱스 생성 시 탐색 범위 (기본값: 64)
  - 높을수록: 정확도 ↑, 인덱스 생성 시간 ↑
  - 낮을수록: 정확도 ↓, 인덱스 생성 시간 ↓

## 🔧 2. 쿼리 최적화

### 현재 쿼리 개선 사항

#### 2.1. 인덱스 힌트 사용

```python
# 현재: 인덱스 사용 여부 불확실
sql_query_str = f"""
    SELECT ...
    FROM product_chunks pc
    WHERE ...
    ORDER BY pc.embedding <=> :query_embedding
    LIMIT :top_k
"""

# 개선: 인덱스 사용 강제 (HNSW 인덱스 생성 후)
# PostgreSQL은 자동으로 인덱스를 사용하지만, 
# 쿼리 플랜을 확인하여 인덱스 사용 여부 확인 필요
```

#### 2.2. WHERE 절 최적화

```python
# 현재: 여러 필터 조건
where_conditions = [
    "pc.embedding IS NOT NULL",
    f"pc.product_code IN ({placeholders})",
    f"({keyword_conditions})"  # ILIKE 사용
]

# 개선: 인덱스가 있는 컬럼 우선 필터링
# product_code는 이미 인덱스가 있으므로 먼저 필터링
# ILIKE는 인덱스를 사용하지 않으므로 나중에 필터링
```

#### 2.3. LIMIT 최적화

```python
# 현재: LIMIT :top_k (기본값: 5)
# 개선: 필요한 만큼만 가져오기 (이미 최적화됨)
```

## 📊 3. 임베딩 캐싱

### 현재 상태
- 임베딩 캐싱 없음: 매번 OpenAI API 호출

### 개선 방안

```python
# 임베딩 캐시 추가 (이미 embedding_cache 있지만 활용 안 함)
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cached_embedding(text: str) -> List[float]:
    """임베딩 캐싱"""
    return embed_text_sync(text)

# 사용
query_embedding = get_cached_embedding(query)
```

**효과:**
- 동일한 쿼리 반복 시 API 호출 없음
- 검색 속도 향상 (API 호출 시간 절약)

## 🎯 4. 유사도 임계값 조정

### 현재 설정
- `.env` 또는 환경 변수 `RAG_VECTOR_SIMILARITY_THRESHOLD` 로 제어 (기본 0.45)
- 코드 내부에서는 `settings.RAG_VECTOR_SIMILARITY_THRESHOLD` 값을 사용

### 최적화 가이드

| 임계값 | 결과 수 | 정확도 | 속도 | 권장 사용 |
|--------|---------|--------|------|----------|
| 0.55 | 적음 | 매우 높음 | 빠름 | 숫자 정확도가 중요한 경우 |
| 0.45 | 보통 | 높음 | 보통 | **현재 기본값 (정확도 우선)** |
| 0.30 | 많음 | 중간 | 약간 느림 | 넓은 범위 검색 필요 시 |

**조정 방법:**
```env
# .env 예시
RAG_VECTOR_SIMILARITY_THRESHOLD=0.45
```

```python
# 코드에서 동적으로 변경하려면
service.similarity_threshold = 0.5  # 정확도 우선
service.similarity_threshold = 0.3  # 범위 우선
```

## 🔍 5. 쿼리 최적화 (SQL 레벨)

### 5.1. EXPLAIN ANALYZE로 성능 확인

```sql
EXPLAIN ANALYZE
SELECT 
    pc.id,
    pc.product_code,
    pc.content,
    1 - (pc.embedding <=> '[0.123, -0.456, ...]'::vector) AS similarity
FROM product_chunks pc
WHERE pc.embedding IS NOT NULL
  AND pc.product_code IN ('LON-MTG')
  AND 1 - (pc.embedding <=> '[0.123, -0.456, ...]'::vector) >= 0.45
ORDER BY pc.embedding <=> '[0.123, -0.456, ...]'::vector
LIMIT 5;
```

**확인 사항:**
- `Index Scan` 사용 여부 (인덱스 사용)
- `Seq Scan` 사용 여부 (전체 스캔, 느림)
- 실행 시간

### 5.2. 인덱스 사용 강제

```sql
-- 인덱스만 사용 (전체 스캔 방지)
SET enable_seqscan = off;

-- 쿼리 실행

-- 원래대로 복구
SET enable_seqscan = on;
```

## 📈 6. 데이터베이스 통계 업데이트

```sql
-- 테이블 통계 업데이트 (쿼리 플래너 최적화)
ANALYZE product_chunks;

-- 전체 데이터베이스 통계 업데이트
ANALYZE;
```

**실행 시점:**
- 인덱스 생성 후
- 대량 데이터 삽입/수정 후
- 주기적으로 (예: 매일)

## 🚀 7. 병렬 처리

### 현재 상태
- 단일 쿼리 실행

### 개선 방안

```python
# 여러 상품 코드를 병렬로 검색
from concurrent.futures import ThreadPoolExecutor

def search_multiple_products(product_codes: List[str], query: str):
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(
                self.search_by_vector_similarity,
                query=query,
                product_codes=[code],
                top_k=3
            )
            for code in product_codes
        ]
        results = [f.result() for f in futures]
    return results
```

## 💾 8. 메모리 최적화

### PostgreSQL 설정

```sql
-- shared_buffers 증가 (캐시 크기)
-- postgresql.conf에서 설정
shared_buffers = 256MB  # 기본값: 128MB

-- work_mem 증가 (정렬/해시 작업용)
work_mem = 16MB  # 기본값: 4MB
```

## 📝 9. 모니터링 및 성능 측정

### 쿼리 성능 측정

```python
import time

start_time = time.time()
results = self.search_by_vector_similarity(query, product_codes, top_k=5)
elapsed = time.time() - start_time

print(f"⏱️ 벡터 검색 시간: {elapsed:.3f}초")
print(f"📊 결과 수: {len(results)}")
```

### 인덱스 사용 확인

```sql
-- 인덱스 사용 통계
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,  -- 인덱스 스캔 횟수
    idx_tup_read,  -- 읽은 튜플 수
    idx_tup_fetch  -- 가져온 튜플 수
FROM pg_stat_user_indexes
WHERE tablename = 'product_chunks'
ORDER BY idx_scan DESC;
```

## 🎯 10. 종합 최적화 체크리스트

### 즉시 적용 가능
- [ ] **HNSW 인덱스 생성** (가장 중요!)
- [ ] 테이블 통계 업데이트 (ANALYZE)
- [ ] 임베딩 캐싱 활성화
- [ ] 유사도 임계값 조정 (필요 시)

### 중기 개선
- [ ] 쿼리 플랜 분석 및 최적화
- [ ] PostgreSQL 메모리 설정 조정
- [ ] 병렬 처리 구현

### 장기 개선
- [ ] 임베딩 모델 업그레이드 (text-embedding-3-large 등)
- [ ] 청크 크기 최적화
- [ ] 하이브리드 검색 (벡터 + 키워드)

## 📚 참고 자료

- [pgvector 공식 문서](https://github.com/pgvector/pgvector)
- [HNSW 알고리즘 설명](https://arxiv.org/abs/1603.09320)
- [PostgreSQL 성능 튜닝](https://www.postgresql.org/docs/current/performance-tips.html)

