# 문맥 기반 상품 코드 추출 개선 가이드

## 개선 사항

### 1. 여러 상품을 한 번에 검색 (성능 향상)

**이전 방식:**
- 각 상품 코드마다 개별 벡터 검색 수행
- 예: `["LON-MTG", "LON-UNS"]` → 2번 검색

**개선된 방식:**
- 여러 상품 코드를 한 번에 검색
- 예: `["LON-MTG", "LON-UNS"]` → 1번 검색 (SQL: `WHERE product_code IN ('LON-MTG', 'LON-UNS')`)

**효과:**
- 검색 횟수 감소로 성능 향상
- 여러 상품 데이터를 한 번에 비교 가능

### 2. 대화 문맥 기반 상품 코드 추출

**문제 상황:**
```
[고객 1]: 정기예금에 대해 알고 싶어요
[직원 1]: 정기예금은 만기까지 이자를 받을 수 있는 상품입니다
[고객 2]: 금리는 어떻게 되나요?
[직원 2]: 금리는 연 2.5%입니다  ← 상품명 없이 금리만 언급
```

**이전 방식:**
- 현재 발화("금리는 연 2.5%입니다")만 분석
- 상품명이 없어서 `product_code` 추출 실패 → `UNKNOWN`

**개선된 방식:**
- 대화 히스토리 전체를 분석
- 이전 대화에서 언급된 "정기예금"을 참고하여 추론
- `product_code = "DEP-TIM"` 정확히 추출

## 구현 세부사항

### 1. 문맥 추적 메서드

```python
def _extract_products_from_conversation_context(
    self, 
    conversation: List[Dict], 
    product_keywords: Dict[str, List[str]]
) -> List[str]:
    """대화 히스토리에서 언급된 상품 코드 추출"""
    mentioned_products = []
    all_text = " ".join([msg.get("text", "") for msg in conversation])
    
    for product_code, keywords in product_keywords.items():
        if any(keyword in all_text for keyword in keywords):
            if product_code not in mentioned_products:
                mentioned_products.append(product_code)
    
    return mentioned_products
```

### 2. LLM 프롬프트 개선

**대화 히스토리 포함:**
```
**대화 히스토리 (문맥 참고용):**
[고객 1]: 정기예금에 대해 알고 싶어요
[직원 1]: 정기예금은 만기까지 이자를 받을 수 있는 상품입니다
[고객 2]: 금리는 어떻게 되나요?
[직원 2]: 금리는 연 2.5%입니다

**⚠️ 중요: 문맥 기반 상품 추론**
- 대화 히스토리에서 언급된 상품을 확인하세요
- 현재 발화에 상품명이 없어도 이전 대화에서 언급된 상품을 참고하세요
```

**출력 형식:**
```json
{
  "facts": [
    {
      "category": "금리",
      "claim": "연 2.5%",
      "value": "2.5",
      "unit": "%",
      "inferred_product": "정기예금"  // 문맥에서 추론
    }
  ]
}
```

### 3. 키워드 매칭도 문맥 고려

**이전:**
```python
# 현재 발화만 분석
for utterance in employee_utterances:
    mentioned_products = []
    for product_code, keywords in product_keywords.items():
        if any(keyword in utterance for keyword in keywords):
            mentioned_products.append(product_code)
```

**개선:**
```python
# 대화 히스토리에서 상품 추출
context_mentioned_products = self._extract_products_from_conversation_context(
    conversation, product_keywords
)

# 현재 발화에서 상품 추출
current_mentioned_products = []

# 문맥과 현재 발화 결합
mentioned_products = list(set(context_mentioned_products + current_mentioned_products))
```

### 4. 여러 상품 한 번에 검색

**이전:**
```python
for v in verifications:
    vector_results = search_by_vector_similarity(
        query=v.claim,
        product_codes=[v.product_code]  # 단일 상품만
    )
```

**개선:**
```python
# claim별로 그룹화
fact_groups = {}  # {claim: [product_codes]}
for v in verifications:
    claim = v.claim
    product_code = v.product_code
    if claim not in fact_groups:
        fact_groups[claim] = []
    fact_groups[claim].append(product_code)

# 여러 상품을 한 번에 검색
for claim, product_codes in fact_groups.items():
    vector_results = search_by_vector_similarity(
        query=claim,
        product_codes=product_codes  # 여러 상품 코드 리스트
    )
```

## 동작 예시

### 시나리오 1: 문맥 기반 추론

**대화:**
```
[고객]: 정기예금에 대해 알고 싶어요
[직원]: 정기예금은 만기까지 이자를 받을 수 있는 상품입니다. 금리는 연 2.5%입니다
```

**처리:**
1. 대화 히스토리 분석 → "정기예금" 감지 → `DEP-TIM`
2. 현재 발화 분석 → "금리는 연 2.5%입니다" → 카테고리: "금리"
3. 문맥과 결합 → `product_codes = ["DEP-TIM"]`
4. 벡터 검색 → `DEP-TIM` 상품의 금리 정보 검색

### 시나리오 2: 여러 상품 언급

**대화:**
```
[직원]: 주택담보대출과 신용대출 모두 금리가 연 3%입니다
```

**처리:**
1. 키워드 매칭 → `["LON-MTG", "LON-UNS"]` 감지
2. Fact 생성 → `product_codes = ["LON-MTG", "LON-UNS"]`
3. 각 상품 코드마다 검증 수행
4. 벡터 검색 → `product_codes = ["LON-MTG", "LON-UNS"]` 한 번에 검색

### 시나리오 3: 문맥 기반 + 여러 상품

**대화:**
```
[고객]: 정기예금과 자유적금 둘 다 알고 싶어요
[직원]: 정기예금은 연 2.5%, 자유적금은 연 2.0%입니다
[고객]: 한도는 어떻게 되나요?
[직원]: 최대 1억원까지 가능합니다  ← 상품명 없이 한도만 언급
```

**처리:**
1. 대화 히스토리 분석 → `["DEP-TIM", "SAV-FRE"]` 감지
2. 현재 발화 분석 → "최대 1억원까지 가능합니다" → 카테고리: "한도"
3. 문맥과 결합 → `product_codes = ["DEP-TIM", "SAV-FRE"]`
4. 벡터 검색 → 두 상품 모두 검색하여 비교

## 성능 개선

### 검색 횟수 비교

**이전:**
- 3개 claim × 2개 상품 = 6번 검색

**개선:**
- 3개 claim × 1번 검색 (여러 상품 포함) = 3번 검색

**효과:** 검색 횟수 50% 감소

## 테스트 방법

### 1. 문맥 기반 추론 테스트

```python
conversation = [
    {"role": "customer", "text": "정기예금에 대해 알고 싶어요"},
    {"role": "employee", "text": "금리는 연 2.5%입니다"}  # 상품명 없음
]

facts = service.extract_product_facts_from_conversation(
    conversation,
    use_llm_extraction=True
)

# 예상 결과: product_codes = ["DEP-TIM"]
```

### 2. 여러 상품 테스트

```python
conversation = [
    {"role": "employee", "text": "주택담보대출과 신용대출 모두 금리가 연 3%입니다"}
]

facts = service.extract_product_facts_from_conversation(conversation)

# 예상 결과: 
# fact["product_codes"] = ["LON-MTG", "LON-UNS"]
# 벡터 검색: product_codes = ["LON-MTG", "LON-UNS"] 한 번에 검색
```

## 주의사항

1. **LLM 추출 사용 시:**
   - 대화 히스토리가 길면 최근 10턴만 포함 (토큰 절약)
   - `_format_conversation_for_llm`의 `max_turns` 파라미터로 조정 가능

2. **키워드 매칭:**
   - 대화 히스토리 전체를 스캔하므로 성능에 영향 가능
   - 대화가 매우 길면 최적화 필요

3. **여러 상품 검색:**
   - SQL `IN` 절 사용으로 성능 향상
   - 하지만 상품이 너무 많으면 (10개 이상) 성능 저하 가능

## 향후 개선 가능 사항

1. **대화 히스토리 최적화:**
   - 최근 N턴만 분석 (현재는 전체 분석)
   - 상품 언급 시점만 추적

2. **LLM 추론 정확도 향상:**
   - 상품 키워드 정보를 더 자세히 제공
   - 상품 카탈로그 정보 포함

3. **캐싱:**
   - 대화 히스토리에서 추출한 상품 코드 캐싱
   - 동일 대화에서 반복 추출 방지

