# 테스트 모드 RAG 평가 로직 구성

## 📋 개요

테스트 모드 RAG 평가는 **일반 모드와 동일한 자동 추출 로직**을 사용하여 실제 운영 환경과 동일한 조건에서 테스트합니다.

## 🔄 전체 흐름

```
테스트 시나리오 시작
    ↓
_process_test_mode_interaction()
    ↓
각 턴마다:
    ├─ STT 평가 (음성 인식 정확도)
    └─ RAG 평가 (상품 정보 추출 및 검증)
        ├─ 고객 발화: _evaluate_customer_rag_integration()
        └─ 직원 발화: _evaluate_rag_integration()
    ↓
평가 결과 누적 (rag_evaluations)
    ↓
_summarize_rag_evaluations() (종합 결과)
```

## 🏗️ 구성 요소

### 1. 진입점: `_process_test_mode_interaction()`

**위치**: `rag_simulation_service.py:2805`

**역할**:
- 테스트 모드 상호작용 처리의 메인 함수
- 각 턴(고객/직원)을 구분하여 평가 수행
- STT 평가와 RAG 평가를 순차적으로 실행

**처리 흐름**:
```python
# 고객 발화인 경우
if current_turn["role"] == "customer":
    # 1. STT 평가
    stt_eval = self._evaluate_single_stt(...)
    
    # 2. RAG 평가 (고객 발화)
    rag_eval_customer = self._evaluate_customer_rag_integration(
        transcribed_text,
        expected_product_code,  # 참고용
        expected_keywords        # 참고용
    )
    
    # 평가 결과 저장
    rag_evaluations.append({
        "turn_index": current_turn_index,
        "role": "customer",
        "expected_product_code": expected_product_code,
        "evaluation": rag_eval_customer
    })

# 직원 발화인 경우
if current_turn["role"] == "employee":
    # 1. STT 평가
    stt_eval = self._evaluate_single_stt(...)
    
    # 2. RAG 평가 (직원 발화)
    rag_eval = self._evaluate_rag_integration(
        transcribed_text,
        expected_product_code,  # 참고용
        expected_keywords        # 참고용
    )
    
    # 평가 결과 저장
    rag_evaluations.append({
        "turn_index": current_turn_index,
        "role": "employee",
        "expected_product_code": expected_product_code,
        "evaluation": rag_eval
    })
```

---

### 2. 고객 발화 RAG 평가: `_evaluate_customer_rag_integration()`

**위치**: `rag_simulation_service.py:3219`

**역할**:
- 고객 발화에서 상품 코드와 키워드를 자동 추출
- 일반 모드와 동일한 로직 사용

**평가 방식**:

#### 2-1. 자동 추출 (일반 모드와 동일)
```python
# ProductKnowledgeService를 사용하여 자동 추출
conversation = [{"role": "customer", "text": customer_text}]
facts = self.product_knowledge_service.extract_product_facts_from_conversation(conversation)

# 추출된 정보
extracted_product_codes = set()  # 자동 추출된 제품 코드들
extracted_keywords = []          # 자동 추출된 claim들
```

#### 2-2. 점수 계산 (총 100점)

**키워드 점수 (50점)**:
- 자동 추출된 키워드(claim)가 있으면: **50점**
- 없으면: **0점**

**제품 코드 추출 점수 (50점)**:
- `expected_product_code`와 일치: **50점**
- 일치하지 않아도 추출 성공: **25점**
- 추출 실패: **0점**

#### 2-3. 반환 결과
```python
{
    "score": 85.0,                    # 총점
    "max_score": 100,
    "keyword_score": 50,              # 키워드 점수
    "product_extraction_score": 35,   # 제품 코드 추출 점수
    "expected_product_code": "LON-CRE",  # 참고용 (테스트 시나리오)
    "extracted_product_code": "LON-CRE", # 자동 추출된 제품 코드
    "extracted_product_codes": ["LON-CRE"],  # 모든 추출된 제품 코드
    "found_keywords": ["신용대출 한도는..."],  # 자동 추출된 키워드
    "expected_keywords": ["신용대출", "한도"],  # 참고용 (테스트 시나리오)
    "missing_keywords": [],  # 참고용
    "extracted_product_keywords": ["신용대출 한도는..."],
    "product_evidence": {...},  # 상품 데이터 근거
    "extraction_method": "auto_extraction"  # 일반 모드와 동일한 방법
}
```

---

### 3. 직원 발화 RAG 평가: `_evaluate_rag_integration()`

**위치**: `rag_simulation_service.py:3341`

**역할**:
- 직원 발화에서 상품 코드, 카테고리, claim을 자동 추출
- RAG에서 가져온 상품 정보가 정확한지 검증
- 일반 모드와 동일한 로직 사용

**평가 방식**:

#### 3-1. 자동 추출 (일반 모드와 동일)
```python
# ProductKnowledgeService를 사용하여 자동 추출
conversation = [{"role": "employee", "text": employee_text}]
facts = self.product_knowledge_service.extract_product_facts_from_conversation(conversation)

# 추출된 정보
extracted_product_codes = set()  # 자동 추출된 제품 코드들
extracted_categories = set()      # 자동 추출된 카테고리들 (금리, 한도, LTV 등)
extracted_claims = []             # 자동 추출된 claim들
```

#### 3-2. 점수 계산 (총 100점)

**키워드 점수 (50점)**:
- 자동 추출된 claim이 있으면: **50점**
- 없으면: **0점**

**RAG 상품 정보 점수 (50점)**:
- 자동 추출된 제품 코드가 있으면:
  - 캐시된 `product_info_keywords`와 비교
  - 매칭된 키워드 비율에 따라 점수 계산
  - 예: 10개 중 8개 매칭 → 40점 (8/10 * 50)
- 카테고리만 추출되었으면: **25점**
- 추출 실패: **0점**

#### 3-3. 반환 결과
```python
{
    "score": 90.0,                    # 총점
    "max_score": 100,
    "keyword_score": 50,              # 키워드 점수
    "rag_product_info_score": 40,     # RAG 상품 정보 점수
    "expected_product_code": "LON-CRE",  # 참고용 (테스트 시나리오)
    "extracted_product_code": "LON-CRE", # 자동 추출된 제품 코드
    "extracted_product_codes": ["LON-CRE"],  # 모든 추출된 제품 코드
    "extracted_categories": ["금리", "한도", "LTV"],  # 자동 추출된 카테고리
    "found_keywords": ["신용대출 한도는..."],  # 자동 추출된 claim
    "expected_keywords": ["신용대출", "한도"],  # 참고용 (테스트 시나리오)
    "missing_keywords": [],  # 참고용
    "rag_info_keywords_found": ["신용대출 한도는..."],  # 자동 추출된 키워드
    "product_evidence": {...},  # 상품 데이터 근거
    "extraction_method": "auto_extraction"  # 일반 모드와 동일한 방법
}
```

---

### 4. 자동 추출 엔진: `ProductKnowledgeService.extract_product_facts_from_conversation()`

**위치**: `product_knowledge_service.py:396`

**역할**:
- 대화에서 제품 관련 사실(Fact)을 자동 추출
- 일반 모드와 테스트 모드 모두에서 사용

**추출 과정**:

1. **제품 코드 감지**:
   ```python
   # 캐시된 product_keywords 사용 (자동 추출된 키워드)
   product_keywords = self._get_product_keywords()
   
   # 발화에서 제품 키워드 매칭
   for product_code, keywords in product_keywords.items():
       if any(keyword in utterance for keyword in keywords):
           mentioned_products.append(product_code)
   ```

2. **카테고리 추출**:
   ```python
   # 정규식 패턴으로 카테고리 추출
   category_patterns = {
       "금리": [r"금리\s*(?:는|:)?\s*([\d\.]+)%?", ...],
       "한도": [r"한도\s*(?:는|:)?\s*([\d,]+)원?", ...],
       "LTV": [r"LTV\s*(?:는|:)?\s*([\d]+)%?", ...],
       ...
   }
   
   # 우선순위 카테고리만 검사 (캐시된 product_category_priority 사용)
   categories_to_check = product_category_priority.get(product_code, [])
   ```

3. **Claim 생성**:
   ```python
   # 매칭된 부분의 앞뒤 문맥을 포함하여 claim 생성
   claim = utterance[context_start:context_end].strip()
   
   fact = {
       "claim": claim,
       "product_codes": mentioned_products,
       "category": category,
       "matched_value": match.group(1)
   }
   ```

**반환 형식**:
```python
[
    {
        "claim": "신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다",
        "full_utterance": "신용대출 한도는 고객님의 신용점수와 소득에 따라...",
        "product_codes": ["LON-CRE"],
        "category": "한도",
        "matched_value": "1.5배"
    },
    ...
]
```

---

### 5. 종합 결과: `_summarize_rag_evaluations()`

**위치**: `rag_simulation_service.py:3126`

**역할**:
- 모든 RAG 평가 결과를 종합하여 평균 점수 계산
- 직원/고객 턴별 평균 점수 제공

**계산 방식**:
```python
{
    "average_score": 85.5,           # 전체 평균 점수
    "employee_average": 90.0,        # 직원 턴 평균 점수
    "customer_average": 81.0,        # 고객 턴 평균 점수
    "total_evaluations": 10,         # 전체 평가 수
    "employee_count": 5,              # 직원 턴 수
    "customer_count": 5              # 고객 턴 수
}
```

---

## 🔑 핵심 특징

### 1. 일반 모드와 동일한 로직
- 테스트 모드에서도 `ProductKnowledgeService.extract_product_facts_from_conversation()` 사용
- 실제 운영 환경과 동일한 조건에서 테스트 가능

### 2. 자동 추출 우선
- `expected_keywords`와 `expected_product_code`는 **참고용**으로만 사용
- 실제 평가는 **자동 추출된 결과**를 사용

### 3. 캐시된 키워드 활용
- `product_keywords_cache.json`에서 자동 추출된 키워드 사용
- 하드코딩된 키워드보다 정확하고 유지보수 용이

### 4. 이중 평가 구조
- **STT 평가**: 음성 인식 정확도 (별도 평가)
- **RAG 평가**: 상품 정보 추출 및 검증 (이 문서의 주제)

---

## 📊 평가 결과 구조

### 개별 평가 결과 (rag_evaluations)
```python
[
    {
        "turn_index": 0,
        "role": "customer",
        "expected_product_code": "LON-CRE",
        "evaluation": {
            "score": 85.0,
            "keyword_score": 50,
            "product_extraction_score": 35,
            "extracted_product_code": "LON-CRE",
            "extracted_product_codes": ["LON-CRE"],
            "found_keywords": ["신용대출 한도는..."],
            "extraction_method": "auto_extraction"
        }
    },
    {
        "turn_index": 1,
        "role": "employee",
        "expected_product_code": "LON-CRE",
        "evaluation": {
            "score": 90.0,
            "keyword_score": 50,
            "rag_product_info_score": 40,
            "extracted_product_code": "LON-CRE",
            "extracted_categories": ["금리", "한도"],
            "found_keywords": ["신용대출 한도는..."],
            "extraction_method": "auto_extraction"
        }
    },
    ...
]
```

### 종합 결과 (rag_summary)
```python
{
    "average_score": 87.5,
    "employee_average": 90.0,
    "customer_average": 85.0,
    "total_evaluations": 10,
    "employee_count": 5,
    "customer_count": 5
}
```

---

## 🔄 일반 모드와의 차이점

| 항목 | 테스트 모드 | 일반 모드 |
|------|------------|----------|
| **평가 시점** | 매 턴마다 즉시 평가 | 대화 종료 후 일괄 평가 |
| **평가 대상** | 개별 발화 (고객/직원 구분) | 전체 대화 (직원 발화만) |
| **평가 방식** | RAG 평가 (점수화) | 상품 지식 정확도 검증 (3단계) |
| **결과 형식** | 점수 기반 (0-100점) | 사실 검증 결과 (정확/부정확) |
| **자동 추출** | ✅ 동일 (ProductKnowledgeService) | ✅ 동일 (ProductKnowledgeService) |
| **캐시 키워드** | ✅ 사용 | ✅ 사용 |

---

## 💡 사용 예시

### 테스트 모드에서 RAG 평가 확인

```python
# 세션 데이터에서 RAG 평가 결과 가져오기
rag_evaluations = session_data.get("rag_evaluations", [])
rag_summary = session_data.get("rag_summary", {})

# 개별 평가 확인
for eval_result in rag_evaluations:
    turn_index = eval_result["turn_index"]
    role = eval_result["role"]
    evaluation = eval_result["evaluation"]
    
    print(f"턴 {turn_index} ({role}): {evaluation['score']:.1f}점")
    print(f"  - 추출된 제품 코드: {evaluation.get('extracted_product_code')}")
    print(f"  - 예상 제품 코드: {evaluation.get('expected_product_code')}")
    print(f"  - 추출 방법: {evaluation.get('extraction_method')}")

# 종합 결과 확인
print(f"전체 평균: {rag_summary.get('average_score', 0):.1f}점")
print(f"직원 평균: {rag_summary.get('employee_average', 0):.1f}점")
print(f"고객 평균: {rag_summary.get('customer_average', 0):.1f}점")
```

---

## 🎯 요약

1. **테스트 모드 RAG 평가는 일반 모드와 동일한 자동 추출 로직을 사용**
2. **`ProductKnowledgeService.extract_product_facts_from_conversation()`이 핵심 엔진**
3. **캐시된 키워드(`product_keywords_cache.json`)를 활용하여 정확한 평가**
4. **`expected_keywords`와 `expected_product_code`는 참고용으로만 사용**
5. **각 턴마다 즉시 평가하여 실시간 피드백 제공**

