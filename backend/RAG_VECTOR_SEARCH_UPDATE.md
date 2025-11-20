# RAG 벡터 검색 기반 지식 역량 평가 업데이트

## 📋 변경 개요

시뮬레이션의 **지식 역량 평가(상품 정확성 평가)**가 이제 **RAG 벡터 검색**을 우선적으로 사용하도록 변경되었습니다.

## ✅ 변경 사항

### 1. `verify_fact_accuracy()` 메서드 수정

**파일**: `backend/app/services/product_knowledge_service.py`

**변경 전**:
- `search_by_keyword()` 사용 (내부적으로 벡터 검색 시도하지만 명시적이지 않음)
- 벡터 검색 실패 여부를 명확히 알 수 없음

**변경 후**:
- **벡터 검색 우선 사용**: `search_by_vector_similarity()` 직접 호출
- 벡터 검색 실패 시에만 키워드 검색으로 fallback
- 검증 방법(verification_method)에 벡터 검색 사용 여부 명시

### 2. 검증 프로세스

```
1단계: RAG 벡터 검색 시도
  ↓
  ✅ 성공 → 벡터 검색 결과 사용 (유사도 0.5 이상)
  ↓
  ❌ 실패 → 키워드 검색으로 fallback
  ↓
2단계: 유사도 계산
  - 벡터 검색 결과: 이미 포함된 similarity 사용 (코사인 유사도)
  - 키워드 검색 결과: _semantic_similarity()로 계산
  ↓
3단계: 숫자 정확도 검증
  ↓
4단계: LLM 검증 (선택)
```

### 3. 검증 방법(verification_method) 업데이트

**새로운 검증 방법**:
- `vector_semantic`: 벡터 검색 사용 + 임베딩 유사도
- `vector_keyword`: 벡터 검색 사용 + SequenceMatcher 유사도
- `semantic`: 키워드 검색 사용 + 임베딩 유사도
- `keyword`: 키워드 검색 사용 + SequenceMatcher 유사도
- `llm`: LLM 검증 성공 (벡터 검색 기반일 수 있음)

## 🔍 코드 변경 상세

### 변경된 부분

```python
# 변경 전 (line 1106-1112)
relevant_chunks = self.search_by_keyword(
    query=claim,
    category=category,
    product_codes=[product_code] if product_code != "UNKNOWN" else None,
    top_k=3
)

# 변경 후 (line 1106-1140)
# 🎯 RAG 검색: 벡터 검색을 우선 사용 (pgvector 기반)
relevant_chunks = None
verification_method_base = "keyword"

# 1단계: 벡터 검색 시도 (RAG 검색)
if self.use_vector_search:
    vector_chunks = self.search_by_vector_similarity(
        query=claim,
        category=category,
        product_codes=[product_code] if product_code != "UNKNOWN" else None,
        top_k=3,
        similarity_threshold=0.5
    )
    
    if vector_chunks:
        relevant_chunks = vector_chunks
        verification_method_base = "vector"
        print(f"✅ 벡터 검색 성공: {len(vector_chunks)}개 청크 발견")

# 2단계: 벡터 검색 실패 시 키워드 검색 (fallback)
if not relevant_chunks:
    relevant_chunks = self.search_by_keyword(...)
```

### 유사도 계산 개선

```python
# 벡터 검색 결과에는 이미 similarity가 포함되어 있음
if verification_method_base == "vector" and "similarity" in best_chunk:
    # 벡터 검색 결과의 유사도 사용 (이미 코사인 유사도로 계산됨)
    similarity_score = float(best_chunk.get("similarity", 0.0))
else:
    # 키워드 검색 결과인 경우 유사도 계산
    similarity_score = self._semantic_similarity(claim, best_chunk_text)
```

## 📊 테스트 결과

### 벡터 검색 성공 사례
- ✅ "연회비는 국내전용 10,000원" → 유사도 0.904
- ✅ "정기예금 금리는 연 5.0%" → 유사도 0.823
- ✅ "6개월, 12개월, 24개월, 36개월" → 유사도 0.875

### 벡터 검색 → 키워드 검색 Fallback
- ⚠️ 카테고리 필터링으로 인해 벡터 검색 결과 없음
- → 키워드 검색으로 자동 fallback

## 🎯 영향 범위

### 영향받는 기능
1. **시뮬레이션 지식 역량 평가**
   - `batch_verify_conversation()` → `verify_fact_accuracy()` 호출
   - 모든 상품 정보 검증이 벡터 검색 우선 사용

2. **검증 방법 통계**
   - `verification_methods`에 `vector_semantic`, `vector_keyword` 추가
   - 벡터 검색 사용 여부를 명확히 추적 가능

### 영향받지 않는 기능
- 키워드 검색은 여전히 fallback으로 작동
- LLM 검증은 기존과 동일하게 작동

## 🔧 설정 및 요구사항

### 필수 조건
1. ✅ **pgvector 확장**: 이미 활성화됨
2. ✅ **상품 데이터 인덱싱**: 446개 청크 인덱싱 완료
3. ✅ **벡터 검색 활성화**: `ProductKnowledgeService` 초기화 시 `session` 전달

### 성능 최적화 (선택사항)
```sql
-- 벡터 인덱스 생성 (검색 속도 향상)
CREATE INDEX ON product_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

## 📝 사용 예시

### 시뮬레이션 평가에서의 사용

```python
# RAGSimulationService에서 자동으로 사용됨
knowledge_verification_result = self.product_knowledge_service.batch_verify_conversation(
    conversation_history,
    use_llm=True
)

# 결과에 벡터 검색 사용 여부 포함
verification_methods = knowledge_verification_result['verification_methods']
# 예: {'vector_semantic': 5, 'llm': 3, 'keyword': 2}
```

## ✅ 확인 사항

- [x] 벡터 검색이 우선적으로 사용됨
- [x] 벡터 검색 실패 시 키워드 검색으로 fallback
- [x] 검증 방법에 벡터 검색 사용 여부 표시
- [x] 기존 기능과 호환성 유지

## 🚀 다음 단계

1. **성능 모니터링**: 벡터 검색 사용률 추적
2. **임계값 튜닝**: `similarity_threshold` 조정 (현재 0.5)
3. **벡터 인덱스 생성**: 대량 데이터 처리 시 성능 향상

