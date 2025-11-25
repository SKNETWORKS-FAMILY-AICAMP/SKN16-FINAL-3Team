# 상품 데이터 인덱싱 필수 가이드

## ⚠️ 중요: 새 환경에서 필수 작업

**다른 컴퓨터에서 깃 풀 후 테스트 모드를 실행하기 전에 반드시 상품 데이터 인덱싱을 실행해야 합니다.**

## 문제 원인

- `product_chunks` 테이블에 데이터가 없으면 벡터 검색이 작동하지 않습니다
- 상품 근거 데이터를 찾을 수 없어 테스트 모드에서 오류가 발생합니다
- 인덱싱은 **수동으로 실행**해야 합니다 (자동 실행되지 않음)

## 해결 방법

### 1. 인덱싱 스크립트 실행

```bash
# 프로젝트 루트에서
cd backend
python scripts/index_product_data.py
```

### 2. 실행 결과 확인

성공 시 다음과 같은 메시지가 출력됩니다:

```
✅ 인덱싱 완료!
📊 인덱싱 결과:
  - CRD-CRE: 20개 청크
  - DEP-TIM: 15개 청크
  - 총합: 35개 청크
```

### 3. 데이터베이스 확인 (선택)

인덱싱이 제대로 되었는지 확인:

```sql
-- 전체 청크 개수 확인
SELECT COUNT(*) FROM product_chunks;

-- 상품별 청크 개수 확인
SELECT product_code, COUNT(*) 
FROM product_chunks 
GROUP BY product_code;
```

## 사전 요구사항

1. **PostgreSQL + pgvector** 실행 중
2. **데이터베이스 연결 설정** 완료 (`DATABASE_URL`)
3. **OpenAI API Key** 설정 (`OPENAI_API_KEY`) - 임베딩 생성에 필요
4. **상품 데이터 파일** 존재 (`backend/data/rag_sources/products/hakyung/*.jsonl`)

## 특정 상품만 인덱싱

```bash
# 특정 상품만 인덱싱
python scripts/index_product_data.py --product-code CRD-CRE
```

## 재인덱싱 (기존 데이터 삭제 후 재생성)

```bash
# 전체 재인덱싱
python scripts/index_product_data.py --force

# 특정 상품 재인덱싱
python scripts/index_product_data.py --product-code CRD-CRE --force
```

## 예상 소요 시간

- **소규모** (1개 상품, ~20개 청크): 약 1-2분
- **중규모** (10개 상품, ~200개 청크): 약 10-15분
- **대규모** (50개 상품, ~1000개 청크): 약 1-2시간

## 문제 해결

### 인덱싱이 실패하는 경우

1. **데이터베이스 연결 확인**
   ```bash
   # 환경 변수 확인
   echo $DATABASE_URL
   ```

2. **JSONL 파일 확인**
   ```bash
   ls backend/data/rag_sources/products/hakyung/*.jsonl
   ```

3. **OpenAI API Key 확인**
   ```bash
   echo $OPENAI_API_KEY
   ```

### 벡터 검색이 여전히 작동하지 않는 경우

1. **인덱싱 완료 여부 확인**
   ```sql
   SELECT COUNT(*) FROM product_chunks WHERE embedding IS NOT NULL;
   ```

2. **애플리케이션 재시작**
   - 인덱싱 후 백엔드 서버를 재시작하세요

3. **로그 확인**
   - 백엔드 로그에서 `🔍 [벡터 검색]` 메시지 확인

## 참고 문서

- `backend/scripts/README_PRODUCT_INDEXING.md` - 상세 인덱싱 가이드
- `PRODUCT_CHUNKS_TABLE_GUIDE.md` - 테이블 구조 및 SQL 쿼리 가이드

