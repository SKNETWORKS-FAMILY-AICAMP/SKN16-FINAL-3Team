# 상품 코드 추론 흐름 설명

## 📋 현재 동작 방식

### 전체 흐름

```
대화 히스토리 (conversation)
    ↓
batch_verify_conversation()
    ↓
extract_product_facts_from_conversation()
    ├─ 각 직원 발화마다 fact 추출
    ├─ 각 fact마다 상품 코드 추론 (개별적으로!)
    │   ├─ LLM 기반 추론 (우선)
    │   ├─ 키워드 매칭 (fallback)
    │   └─ 문맥 기반 추론 (대화 히스토리에서 언급된 상품)
    └─ fact.product_codes = [추론된 상품 코드들]
    ↓
각 fact 검증
    ├─ fact.product_codes에 있는 각 상품 코드마다
    └─ verify_fact_accuracy() 호출
```

### 핵심 포인트

1. **각 fact마다 개별적으로 상품 코드 추론**
   - 첫 번째 fact: "정기예금 금리는 2.15%" → `DEP-TIM` 추론
   - 두 번째 fact: "체크카드 한도는 500만원" → `CRD-DEB` 추론
   - 세 번째 fact: "중도해지 금리..." → 추론 실패 → `UNKNOWN` 또는 fallback

2. **문맥 기반 추론**
   - `_extract_products_from_conversation_context()`: 전체 대화 히스토리에서 언급된 상품 추출
   - 현재 발화에 상품 키워드가 없어도, 이전 대화에서 언급된 상품을 참고

3. **expected_product_code의 역할 (개선 후)**
   - **Fallback으로만 사용**: 각 fact의 상품 코드 추론이 실패했을 때만 사용
   - **전체 대화에 강제 적용하지 않음**: 각 fact마다 개별 추론 후, 실패 시에만 fallback

---

## 🔍 구체적인 예시

### 시나리오: 대화 중 여러 상품 언급

```
턴 1 (직원): "정기예금 금리는 연 2.15%입니다"
  → fact 1: claim="금리는 연 2.15%", product_codes=["DEP-TIM"] ✅

턴 2 (고객): "체크카드는 어떤가요?"

턴 3 (직원): "체크카드 한도는 500만원입니다"
  → fact 2: claim="한도는 500만원", product_codes=["CRD-DEB"] ✅

턴 4 (직원): "정기예금 중도해지 금리는 약정금리보다 낮습니다"
  → fact 3: claim="중도해지 금리...", product_codes=["DEP-TIM"] ✅
  (문맥에서 "정기예금" 언급되어 DEP-TIM 추론)

턴 5 (직원): "이자소득세는 15.4%입니다"
  → fact 4: claim="이자소득세는 15.4%", product_codes=["UNKNOWN"] ❌
  (상품 키워드 없음, 문맥도 불명확)
  → expected_product_code="DEP-TIM"이 있으면 → ["DEP-TIM"] ✅ (fallback)
```

### expected_product_code 적용 시나리오

**테스트 모드**:
- `expected_product_code="DEP-TIM"` 전달
- fact 4에서 추론 실패 → `expected_product_code` 사용 → `["DEP-TIM"]`

**일반 모드**:
- `situation.product="DEP-TIM"` 전달
- fact 4에서 추론 실패 → `situation.product` 사용 → `["DEP-TIM"]`

---

## ⚠️ 주의사항

### 1. expected_product_code는 Fallback일 뿐

```python
# ❌ 잘못된 이해: expected_product_code를 모든 fact에 강제 적용
for fact in facts:
    fact["product_codes"] = [expected_product_code]  # ❌ 이렇게 하면 안 됨!

# ✅ 올바른 이해: 추론 실패 시에만 fallback으로 사용
for fact in facts:
    product_codes = fact.get("product_codes", [])
    
    # 추론 실패 시에만 fallback 사용
    if expected_product_code and ("UNKNOWN" in product_codes or not product_codes):
        product_codes = [expected_product_code]
        fact["product_codes"] = product_codes
```

### 2. 여러 상품이 언급되면 각각 추론됨

- 대화 중 "정기예금"과 "체크카드"가 모두 언급되면
- 각 fact마다 해당하는 상품 코드로 추론됨
- `expected_product_code`는 **추론 실패한 fact에만** 적용

### 3. 문맥 기반 추론의 한계

- 문맥에서 상품을 찾지 못하면 `UNKNOWN`
- 이때 `expected_product_code`가 있으면 fallback으로 사용
- 하지만 **명확히 다른 상품이 언급된 경우**에는 그 상품 코드로 추론됨

---

## 🎯 개선 방안 (P0) 적용 후 동작

### 코드 흐름

```python
def batch_verify_conversation(
    self,
    conversation: List[Dict],
    use_llm: Optional[bool] = None,
    use_llm_extraction: Optional[bool] = None,
    expected_product_code: Optional[str] = None  # 🆕 추가
) -> Dict:
    # 1. 사실 추출 (각 fact마다 상품 코드 추론)
    facts = self.extract_product_facts_from_conversation(
        conversation,
        use_llm_extraction=use_llm_extraction
    )
    
    # 2. 각 fact 검증 전에 expected_product_code 적용 (fallback)
    for fact in facts:
        product_codes = fact.get("product_codes", [])
        
        # 🆕 추론 실패 시에만 expected_product_code 사용
        if expected_product_code and ("UNKNOWN" in product_codes or not product_codes):
            print(f"✅ [상품 코드] expected_product_code 사용: {expected_product_code}")
            product_codes = [expected_product_code]
            fact["product_codes"] = product_codes
        
        # UNKNOWN이면 벡터 검색 건너뛰기 (기존 로직 유지)
        if "UNKNOWN" in product_codes and not expected_product_code:
            # ... 기존 로직
    
    # 3. 각 fact 검증
    for fact in facts:
        for product_code in fact["product_codes"]:
            verification = self.verify_fact_accuracy(...)
            verifications.append(verification)
```

### 동작 예시

**시나리오**: 테스트 모드, `expected_product_code="DEP-TIM"`

```
턴 1: "정기예금 금리는 2.15%"
  → fact 1: product_codes=["DEP-TIM"] (추론 성공)
  → expected_product_code 적용 안 함 (이미 추론됨)

턴 2: "체크카드 한도는 500만원"
  → fact 2: product_codes=["CRD-DEB"] (추론 성공)
  → expected_product_code 적용 안 함 (이미 추론됨)

턴 3: "이자소득세는 15.4%입니다"
  → fact 3: product_codes=["UNKNOWN"] (추론 실패)
  → expected_product_code 적용 → ["DEP-TIM"] ✅
```

---

## 📊 요약

| 상황 | 상품 코드 추론 방식 | expected_product_code 역할 |
|------|------------------|---------------------------|
| **명확한 상품 키워드** | 해당 상품 코드로 추론 | 사용 안 함 |
| **문맥에서 상품 발견** | 문맥 상품 코드로 추론 | 사용 안 함 |
| **추론 실패 (UNKNOWN)** | `expected_product_code` 사용 | **Fallback으로 사용** |
| **여러 상품 언급** | 각 fact마다 개별 추론 | 추론 실패한 fact에만 적용 |

---

## ✅ 결론

1. **각 fact마다 개별적으로 상품 코드 추론**
2. **expected_product_code는 fallback일 뿐** (추론 실패 시에만 사용)
3. **대화 중 여러 상품이 언급되면 각각 추론됨**
4. **처음 전달한 코드를 강제로 사용하지 않음**

따라서 사용자의 걱정은 해소됩니다! 🎉

