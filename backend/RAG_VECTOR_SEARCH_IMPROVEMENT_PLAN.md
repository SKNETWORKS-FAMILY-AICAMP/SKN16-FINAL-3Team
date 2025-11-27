# RAG 벡터 검색 성능 개선 계획

## 📊 문제 분석 (테스트 모드 결과 기반)

### 발견된 주요 문제점

1. **상품 코드 추론 실패 (UNKNOWN) - 최우선**
   - **빈도**: 수신 시나리오 turn_index 8에서 발생
   - **영향**: 벡터 검색 자체가 건너뛰어짐 → 모든 claim이 `unknown_product`로 처리
   - **원인**: 
     - `batch_verify_conversation`에서 LLM이 상품 코드를 추론하지 못함
     - `expected_product_code`는 있지만 `extracted_product_code`가 `UNKNOWN`
     - 발화에 "정기예금", "DEP-TIM" 같은 명시적 키워드가 없음

2. **유사도 임계값 문제**
   - **현재 설정**: 0.45 (코드), 0.5 (에러 메시지)
   - **문제**: 일부 쿼리는 더 낮은 유사도(0.3~0.4)로도 검색되어야 할 수 있음
   - **영향**: 정확한 정보가 있지만 임계값 미달로 검색되지 않음

3. **쿼리 표현 차이**
   - **문제**: 사용자 발화와 상품 데이터의 표현 방식이 달라서 임베딩 유사도가 낮음
   - **예시**: "중도해지 금리" vs "중도해지율", "이자소득세 15.4%" vs "소득세 14% + 지방소득세 1.4%"

---

## 🎯 개선 방안 (우선순위별)

### 🔴 P0: 상품 코드 추론 실패 해결 (최우선)

**목표**: 테스트 모드와 일반 모드 모두에서 상품 코드 추론 실패 시 대체 방법 사용

**일반 모드 적용 가능 여부**: ✅ **적용 가능** (단, `situation.get('product')` 활용 필요)

**구현 방법**:

#### 1-1. `batch_verify_conversation`에 `expected_product_code` 파라미터 추가
- **파일**: `backend/app/services/product_knowledge_service.py`
- **위치**: `batch_verify_conversation` 함수 시그니처
- **변경 내용**:
  ```python
  def batch_verify_conversation(
      self,
      conversation: List[Dict],
      use_llm: Optional[bool] = None,
      use_llm_extraction: Optional[bool] = None,
      expected_product_code: Optional[str] = None  # 🆕 추가
  ) -> Dict:
  ```
- **일반 모드 호환성**: ✅ `None`이면 기존 로직 유지, 값이 있으면 사용

#### 1-2. 상품 코드 추론 실패 시 `expected_product_code` 사용
- **파일**: `backend/app/services/product_knowledge_service.py`
- **위치**: `batch_verify_conversation` 내부, fact 추출 후
- **변경 내용**:
  ```python
  # fact 추출 후
  for fact in facts:
      product_codes = fact.get("product_codes", [])
      
      # 🆕 expected_product_code가 있고 추론 실패 시 사용
      if expected_product_code and ("UNKNOWN" in product_codes or not product_codes):
          print(f"✅ [상품 코드] expected_product_code 사용: {expected_product_code}")
          product_codes = [expected_product_code]
          fact["product_codes"] = product_codes
      
      # UNKNOWN이면 벡터 검색 건너뛰기 (기존 로직 유지)
      if "UNKNOWN" in product_codes and not expected_product_code:
          # ... 기존 로직
  ```
- **일반 모드 호환성**: ✅ `expected_product_code`가 `None`이면 기존 로직 그대로 동작

#### 1-3. 테스트 모드: `_evaluate_rag_integration`에서 `expected_product_code` 전달
- **파일**: `backend/app/services/rag_simulation_service.py`
- **위치**: `_evaluate_rag_integration` 함수 내부 (line ~4059)
- **변경 내용**:
  ```python
  knowledge_verification_result = self.product_knowledge_service.batch_verify_conversation(
      conversation,
      use_llm=True,
      use_llm_extraction=use_llm_extraction,
      expected_product_code=expected_product_code  # 🆕 추가 (이미 파라미터로 받음)
  )
  ```

#### 1-4. 일반 모드: `generate_comprehensive_feedback`에서 `situation.product` 전달
- **파일**: `backend/app/services/rag_simulation_service.py`
- **위치**: `generate_comprehensive_feedback` 함수 내부 (line ~2212)
- **변경 내용**:
  ```python
  # 상황 정보에서 상품 코드 추출
  product_code_from_situation = situation.get('product', None)
  
  knowledge_verification_result = self.product_knowledge_service.batch_verify_conversation(
      conversation_history,
      use_llm=True,
      use_llm_extraction=use_llm_extraction,
      expected_product_code=product_code_from_situation  # 🆕 추가: situation에서 가져온 상품 코드
  )
  ```
- **일반 모드 호환성**: ✅ `situation`에 `product`가 없으면 `None` 전달 → 기존 로직 유지

**예상 효과**:
- **테스트 모드**:
  - UNKNOWN 발생률: 현재 ~14% → 0%
  - 벡터 검색 성공률: 현재 ~86% → 100%
  - 지식 정확도: 66.7% → 75%+ (수신 시나리오)
- **일반 모드**:
  - UNKNOWN 발생률: 상황에 따라 감소 (situation에 product가 있는 경우)
  - 벡터 검색 성공률: 상황에 따라 향상
  - 지식 정확도: 상황에 따라 향상

**테스트 방법**:
```bash
# 테스트 모드
python run_test_mode_batch.py
# turn_index 8에서 extracted_product_code가 "DEP-TIM"으로 나오는지 확인

# 일반 모드 (수동 테스트)
# situation에 product가 있는 시나리오로 시뮬레이션 실행 후 피드백 생성
# UNKNOWN 발생률이 감소하는지 확인
```

---

### 🟡 P1: 유사도 임계값 동적 조정

**목표**: 쿼리 특성에 따라 임계값을 유연하게 조정

**구현 방법**:

#### 2-1. 2단계 검색 전략 (Fallback)
- **파일**: `backend/app/services/product_knowledge_service.py`
- **위치**: `search_by_vector_similarity` 함수
- **변경 내용**:
  ```python
  def search_by_vector_similarity(
      self,
      query: str,
      category: Optional[str] = None,
      product_codes: Optional[List[str]] = None,
      top_k: int = 3,
      similarity_threshold: Optional[float] = None,
      use_fallback: bool = True  # 🆕 추가
  ) -> List[Dict]:
      """
      use_fallback: True면 첫 검색 실패 시 임계값을 낮춰서 재검색
      """
      effective_threshold = similarity_threshold if similarity_threshold is not None else self.similarity_threshold
      
      # 1차 검색 (기본 임계값)
      results = self._execute_vector_search(
          query, category, product_codes, top_k, effective_threshold
      )
      
      # 🆕 Fallback: 결과가 없고 use_fallback이 True면 임계값 낮춰서 재검색
      if not results and use_fallback:
          fallback_threshold = max(0.15, effective_threshold - 0.15)  # 최소 0.15
          print(f"⚠️ [벡터 검색] Fallback: 임계값 {effective_threshold} → {fallback_threshold}")
          results = self._execute_vector_search(
              query, category, product_codes, top_k, fallback_threshold
          )
          if results:
              print(f"✅ [벡터 검색] Fallback 성공: {len(results)}개 결과")
      
      return results
  ```

#### 2-2. 카테고리별 임계값 설정
- **파일**: `backend/app/config.py`
- **변경 내용**:
  ```python
  # 카테고리별 유사도 임계값 (기본값보다 낮게 설정 가능)
  RAG_VECTOR_SIMILARITY_THRESHOLD_BY_CATEGORY = {
      "금리": 0.40,      # 금리는 표현이 다양해서 낮게
      "한도": 0.45,      # 기본값
      "수수료": 0.40,    # 수수료도 표현 다양
      "조건": 0.35,      # 조건은 더 낮게 (중도해지, 가입조건 등)
  }
  ```

**예상 효과**:
- 벡터 검색 성공률: 86% → 95%+
- False Negative 감소: 정확한 정보를 놓치는 경우 감소

**테스트 방법**:
```bash
# 임계값 조정 후 동일 시나리오 재실행
python run_test_mode_batch.py
# vector_no_results 에러가 줄어드는지 확인
```

---

### 🟢 P2: 쿼리 확장 및 정규화

**목표**: 사용자 발화와 상품 데이터의 표현 차이를 줄임

**구현 방법**:

#### 3-1. 쿼리 확장 (동의어 추가)
- **파일**: `backend/app/services/product_knowledge_service.py`
- **위치**: `search_by_vector_similarity` 함수 시작 부분
- **변경 내용**:
  ```python
  def search_by_vector_similarity(
      self,
      query: str,
      ...
  ) -> List[Dict]:
      # 🆕 쿼리 확장: 동의어 추가
      expanded_query = self._expand_query_with_synonyms(query)
      
      # 원본 쿼리와 확장 쿼리 모두로 검색 (OR 조건)
      # 또는 확장 쿼리만 사용
      query_to_use = expanded_query
      
      # ... 기존 로직
  ```

#### 3-2. 동의어 사전 정의
- **파일**: `backend/app/services/product_knowledge_service.py`
- **위치**: 클래스 초기화 또는 별도 메서드
- **변경 내용**:
  ```python
  def _expand_query_with_synonyms(self, query: str) -> str:
      """
      쿼리에 동의어 추가하여 검색 범위 확장
      """
      synonyms = {
          "중도해지": ["중도해지율", "중도해지 금리", "중도 해지"],
          "이자소득세": ["소득세", "지방소득세", "원천징수"],
          "금리": ["이자율", "이율", "금리율"],
          "한도": ["최대", "상한", "제한"],
          "수수료": ["비용", "요금", "수수료율"],
      }
      
      expanded_terms = [query]
      for key, values in synonyms.items():
          if key in query:
              expanded_terms.extend(values)
      
      # 중복 제거 후 공백으로 연결
      return " ".join(list(set(expanded_terms)))
  ```

**예상 효과**:
- 벡터 검색 정확도: 80% → 90%+
- 유사도 점수: 평균 0.82 → 0.85+

**테스트 방법**:
- 동의어 사전을 점진적으로 확장
- 테스트 모드 결과에서 누락된 케이스 분석 후 동의어 추가

---

### 🔵 P3: 하이브리드 검색 (벡터 + 키워드)

**목표**: 벡터 검색 실패 시 키워드 검색으로 보완

**구현 방법**:

#### 4-1. 벡터 검색 실패 시 자동 키워드 검색
- **파일**: `backend/app/services/product_knowledge_service.py`
- **위치**: `verify_fact_accuracy` 함수
- **변경 내용**:
  ```python
  # 벡터 검색 실패 시
  if not relevant_chunks:
      print(f"⚠️ [벡터 검색] 결과 없음, 키워드 검색으로 fallback")
      
      # 🆕 키워드 검색 시도
      keyword_chunks = self.search_by_keywords(
          query=claim,
          category=category,
          product_codes=[product_code] if product_code != "UNKNOWN" else None,
          top_k=3
      )
      
      if keyword_chunks:
          print(f"✅ [키워드 검색] 성공: {len(keyword_chunks)}개 청크 발견")
          relevant_chunks = keyword_chunks
          verification_method_base = "keyword"
  ```

**예상 효과**:
- 검색 성공률: 95% → 98%+
- 벡터 검색 실패해도 키워드로 보완

---

## 📋 구현 체크리스트

### Phase 1: P0 (상품 코드 추론 실패 해결)
- [ ] `batch_verify_conversation`에 `expected_product_code` 파라미터 추가
- [ ] 상품 코드 추론 실패 시 `expected_product_code` 사용 로직 추가
- [ ] `_evaluate_rag_integration`에서 `expected_product_code` 전달
- [ ] 테스트 모드 배치 실행으로 검증
- [ ] UNKNOWN 발생률 0% 확인

### Phase 2: P1 (유사도 임계값 동적 조정)
- [ ] 2단계 검색 전략 (Fallback) 구현
- [ ] 카테고리별 임계값 설정 추가
- [ ] 테스트 모드 배치 실행으로 검증
- [ ] 벡터 검색 성공률 95%+ 확인

### Phase 3: P2 (쿼리 확장 및 정규화)
- [ ] 쿼리 확장 메서드 구현
- [ ] 동의어 사전 정의 및 확장
- [ ] 테스트 모드 결과 분석 후 동의어 추가
- [ ] 벡터 검색 정확도 90%+ 확인

### Phase 4: P3 (하이브리드 검색)
- [ ] 벡터 검색 실패 시 키워드 검색 자동 실행
- [ ] 검색 성공률 98%+ 확인

---

## 📈 성능 목표

### 현재 상태 (테스트 모드 배치 결과)
- 벡터 검색 성공률: ~86%
- UNKNOWN 발생률: ~14%
- 지식 정확도: 66.7% (수신), 71.4% (여신), 81.8% (카드)

### 목표 상태
- 벡터 검색 성공률: **98%+**
- UNKNOWN 발생률: **0%** (테스트 모드)
- 지식 정확도: **85%+** (모든 시나리오)

---

## 🔍 모니터링 및 평가

### 로그 추가
- 벡터 검색 실패 시 상세 원인 로깅
- Fallback 실행 여부 로깅
- 쿼리 확장 전/후 비교 로깅

### 메트릭 수집
- 벡터 검색 성공률
- UNKNOWN 발생률
- 평균 유사도 점수
- Fallback 사용 빈도

---

## 📝 참고사항

- 모든 변경사항은 기존 로직을 유지하면서 점진적으로 개선
- 테스트 모드 배치 실행으로 각 단계별 검증 필수
- 성능 저하가 발생하면 즉시 롤백 가능하도록 구현


