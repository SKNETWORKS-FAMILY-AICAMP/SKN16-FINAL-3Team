# product_chunks 테이블 확인 가이드

## 📊 테이블 구조

`product_chunks` 테이블은 상품 데이터 청크와 벡터 임베딩을 저장하는 테이블입니다.

### 컬럼 정보

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| `id` | INTEGER (PK) | 기본 키 |
| `product_code` | VARCHAR | 상품 코드 (예: CRD-CRE, DEP-TIM) |
| `content` | TEXT | 청크 텍스트 내용 |
| `chunk_index` | INTEGER | 상품 내 청크 순서 |
| `embedding` | VECTOR(1536) | OpenAI 임베딩 벡터 (1536 차원) |
| `subsection_title` | VARCHAR | 소섹션 제목 |
| `part_title` | VARCHAR | 파트 제목 |
| `breadcrumb` | VARCHAR | 경로 정보 |
| `chunk_metadata` | TEXT | JSON 형식 메타데이터 |
| `created_at` | TIMESTAMP | 생성 시간 |
| `updated_at` | TIMESTAMP | 수정 시간 |

## 🔌 pgAdmin 연결 정보

### 연결 설정

1. **pgAdmin 실행**
2. **서버 추가** (Add New Server)
   - **General 탭**
     - Name: `Mentor System DB` (원하는 이름)
   - **Connection 탭**
     - Host name/address: `localhost`
     - Port: `5432`
     - Maintenance database: `mentordb`
     - Username: `mentoruser`
     - Password: `mentorpass`
     - Save password 체크

### 테이블 확인 방법

1. pgAdmin에서 서버 연결
2. 트리 구조에서:
   ```
   Servers → Mentor System DB → Databases → mentordb → Schemas → public → Tables → product_chunks
   ```
3. `product_chunks` 테이블 우클릭 → **View/Edit Data** → **All Rows**

## 📝 유용한 SQL 쿼리

### 1. 전체 데이터 개수 확인
```sql
SELECT COUNT(*) as total_chunks FROM product_chunks;
```

### 2. 상품별 청크 개수
```sql
SELECT 
    product_code,
    COUNT(*) as chunk_count
FROM product_chunks
GROUP BY product_code
ORDER BY chunk_count DESC;
```

### 3. 임베딩이 있는 청크 확인
```sql
SELECT 
    product_code,
    COUNT(*) as total_chunks,
    COUNT(embedding) as chunks_with_embedding
FROM product_chunks
GROUP BY product_code;
```

### 4. 특정 상품의 청크 조회 (임베딩 제외)
```sql
SELECT 
    id,
    product_code,
    chunk_index,
    subsection_title,
    part_title,
    breadcrumb,
    LEFT(content, 100) as content_preview,
    created_at
FROM product_chunks
WHERE product_code = 'DEP-TIM'  -- 원하는 상품 코드로 변경
ORDER BY chunk_index
LIMIT 10;
```

### 5. 벡터 검색 테스트 (유사도 검색)
```sql
-- 먼저 쿼리 텍스트를 임베딩으로 변환해야 합니다
-- 이 쿼리는 예시이며, 실제로는 애플리케이션에서 임베딩을 생성한 후 사용합니다

-- 예시: "정기예금"과 유사한 청크 찾기
-- (실제 사용 시에는 임베딩 벡터를 직접 제공해야 함)
SELECT 
    product_code,
    subsection_title,
    LEFT(content, 200) as content_preview,
    1 - (embedding <=> '[임베딩 벡터]') AS similarity
FROM product_chunks
WHERE embedding IS NOT NULL
ORDER BY embedding <=> '[임베딩 벡터]'
LIMIT 5;
```

### 6. 메타데이터 확인
```sql
SELECT 
    product_code,
    chunk_index,
    subsection_title,
    part_title,
    breadcrumb,
    chunk_metadata
FROM product_chunks
WHERE product_code = 'DEP-TIM'
LIMIT 5;
```

### 7. 최근 추가된 청크 확인
```sql
SELECT 
    product_code,
    chunk_index,
    subsection_title,
    LEFT(content, 100) as content_preview,
    created_at
FROM product_chunks
ORDER BY created_at DESC
LIMIT 10;
```

### 8. 임베딩이 없는 청크 확인 (인덱싱 누락 확인)
```sql
SELECT 
    product_code,
    COUNT(*) as missing_embedding_count
FROM product_chunks
WHERE embedding IS NULL
GROUP BY product_code;
```

## 🔍 벡터 검색 확인 팁

pgAdmin에서는 벡터 타입을 직접 조회하기 어렵습니다. 대신:

1. **임베딩 존재 여부 확인**
   ```sql
   SELECT 
       product_code,
       COUNT(*) as total,
       COUNT(embedding) as with_embedding,
       COUNT(*) - COUNT(embedding) as without_embedding
   FROM product_chunks
   GROUP BY product_code;
   ```

2. **애플리케이션 로그 확인**
   - 벡터 검색은 애플리케이션에서 수행되므로, 백엔드 로그에서 검색 결과를 확인할 수 있습니다.
   - 로그에서 `🔍 [벡터 검색]` 메시지를 찾아보세요.

## ⚠️ 주의사항

1. **임베딩 벡터는 매우 큽니다** (1536 차원)
   - 전체 조회 시 성능에 영향을 줄 수 있습니다.
   - 필요한 컬럼만 선택하여 조회하세요.

2. **벡터 검색은 SQL 쿼리로 직접 수행하기 어렵습니다**
   - pgvector 연산자(`<=>`)를 사용하려면 임베딩 벡터가 필요합니다.
   - 실제 검색은 애플리케이션 코드에서 수행됩니다.

3. **데이터 수정 시 주의**
   - `product_chunks` 테이블은 애플리케이션에서 자동으로 관리됩니다.
   - 수동 수정 시 벡터 검색 결과에 영향을 줄 수 있습니다.

## 🛠️ 문제 해결

### 테이블이 보이지 않는 경우

1. **테이블이 생성되었는지 확인**
   ```sql
   SELECT table_name 
   FROM information_schema.tables 
   WHERE table_schema = 'public' 
   AND table_name = 'product_chunks';
   ```

2. **인덱싱이 완료되었는지 확인**
   - 백엔드에서 `index_product_data_to_vector_db()` 메서드를 실행했는지 확인
   - 또는 애플리케이션 시작 시 자동 인덱싱이 수행되었는지 확인

### 데이터가 없는 경우

1. **JSONL 파일 확인**
   - `backend/data/rag_sources/products/hakyung/*.jsonl` 파일이 있는지 확인

2. **수동 인덱싱 실행**
   ```python
   # Python 스크립트로 실행
   from app.services.product_knowledge_service import ProductKnowledgeService
   from app.database import get_session
   
   session = next(get_session())
   service = ProductKnowledgeService(session=session)
   service.index_product_data_to_vector_db()
   ```

