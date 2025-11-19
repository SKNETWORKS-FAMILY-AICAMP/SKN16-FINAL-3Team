# 검증 방법 (`verification_method`) 정확한 설명

## 🔍 검증 프로세스 흐름

### 전체 흐름

```
시작
  ↓
[1단계: 항상 수행]
  ├─ Keyword Matching: 청크 검색
  ├─ Semantic Similarity: 의미적 유사도 계산
  ├─ 숫자 정확도 비교
  └─ 휴리스틱 정확도 판단 (is_accurate_heuristic)
  ↓
LLM 사용 가능? (use_llm=True && openai_client 존재)
  ├─ YES → [2단계: LLM 검증 수행]
  │         ├─ LLM 성공 → LLM 결과를 최종 판단으로 사용
  │         │             → verification_method = "llm"
  │         └─ LLM 실패 → 1단계 휴리스틱 결과 사용
  │                       → verification_method = "semantic" or "keyword"
  └─ NO → 1단계 휴리스틱 결과 사용
          → verification_method = "semantic" or "keyword"
```

## 📋 상세 설명

### 1단계: 항상 수행되는 검증

```python
# 1. 키워드 기반 청크 검색 (항상 수행)
relevant_chunks = self.search_by_keyword(
    query=claim,
    category=category,
    product_codes=[product_code],
    top_k=3
)

# 2. 의미적 유사도 계산 (항상 수행)
best_chunk = relevant_chunks[0]
best_chunk_text = best_chunk.get("text", "")
similarity_score = self._semantic_similarity(claim, best_chunk_text)

# 3. 숫자 정확도 비교 (항상 수행)
claim_numbers = self._extract_numbers(claim)
truth_numbers = self._extract_numbers(best_chunk_text)
numbers_match = ...  # 숫자 비교 로직

# 4. 휴리스틱 정확도 판단 (항상 수행)
# ⚠️ "휴리스틱" = 규칙 기반 판단 (AI 모델 사용 안 함)
if claim_numbers or truth_numbers:
    is_accurate_heuristic = numbers_match  # 규칙: 숫자 일치 여부
else:
    threshold = 0.75 if self.use_embedding else 0.7
    is_accurate_heuristic = similarity_score >= threshold  # 규칙: 유사도 임계값
```

**결과**: `is_accurate_heuristic` (휴리스틱 정확도 판단 결과)

### 🤔 "휴리스틱 판단"이란?

**"휴리스틱(Heuristic)"** = **규칙 기반 판단**

- **의미**: AI 모델(LLM)을 사용하지 않고, 미리 정의된 규칙으로 정확도를 판단하는 방법
- **규칙 예시**:
  - 숫자가 있으면 → 숫자 일치 여부로 판단 (`numbers_match`)
  - 숫자가 없으면 → 유사도가 임계값(0.75 또는 0.7) 이상이면 정확
- **LLM 판단과의 차이**:
  - 휴리스틱: 규칙 기반 (if-else 로직)
  - LLM: AI 모델 기반 (맥락 이해, 추론)

**즉, "휴리스틱 판단" = 1단계에서 수행하는 규칙 기반 판단**

### 2단계: 선택적 LLM 검증

```python
# LLM 검증 수행 (조건부)
if should_use_llm and self.openai_client:
    llm_result = self._verify_with_llm(claim, best_chunk_text, category, product_code)
    
    if llm_result["success"]:
        # ✅ LLM 성공 → LLM 결과를 최종 판단으로 사용
        return ProductFactCheck(
            is_accurate=llm_result["is_accurate"],  # LLM 판단 결과
            verification_method="llm"  # LLM이 최종 판단
        )
    
    # ❌ LLM 실패 → 1단계 휴리스틱 결과 사용
    # (아래 코드로 계속 진행)

# LLM 없음 또는 실패 → 1단계 휴리스틱 결과 사용
return ProductFactCheck(
    is_accurate=is_accurate_heuristic,  # 1단계 휴리스틱 결과
    verification_method="semantic" if self.use_embedding else "keyword"
)
```

## 🎯 `verification_method` 값의 의미

### `"llm"`인 경우

**의미**: 1단계를 거친 후 LLM 검증까지 완료되었고, LLM 결과를 최종 판단으로 사용

**프로세스**:
1. ✅ 1단계 수행: 키워드 검색 → 유사도 계산 → 휴리스틱 판단
2. ✅ 2단계 수행: LLM 검증 성공
3. ✅ 최종 판단: LLM 결과 사용 (`is_accurate = llm_result["is_accurate"]`)

**예시**:
```python
# 1단계: 휴리스틱 판단 (is_accurate_heuristic = True)
# 2단계: LLM 검증 성공 (llm_result["is_accurate"] = True)
# → verification_method = "llm"
# → is_accurate = True (LLM 결과)
```

### `"semantic"`인 경우

**의미**: 1단계만 수행되었고, 임베딩 기반 유사도로 최종 판단

**프로세스**:
1. ✅ 1단계 수행: 키워드 검색 → 유사도 계산 → 휴리스틱 판단
2. ❌ 2단계 미수행: LLM 없음 또는 실패
3. ✅ 최종 판단: 1단계 휴리스틱 결과 사용 (`is_accurate = is_accurate_heuristic`)

**예시**:
```python
# 1단계: 휴리스틱 판단 (is_accurate_heuristic = True)
# 2단계: LLM 없음 또는 실패
# → verification_method = "semantic" (임베딩 사용)
# → is_accurate = True (휴리스틱 결과)
```

### `"keyword"`인 경우

**의미**: 1단계만 수행되었고, SequenceMatcher 기반 유사도로 최종 판단

**프로세스**:
1. ✅ 1단계 수행: 키워드 검색 → 유사도 계산 → 휴리스틱 판단
2. ❌ 2단계 미수행: LLM 없음 또는 실패
3. ✅ 최종 판단: 1단계 휴리스틱 결과 사용 (`is_accurate = is_accurate_heuristic`)

**예시**:
```python
# 1단계: 휴리스틱 판단 (is_accurate_heuristic = False)
# 2단계: LLM 없음 또는 실패
# → verification_method = "keyword" (SequenceMatcher 사용)
# → is_accurate = False (휴리스틱 결과)
```

## 📊 실제 케이스별 예시

### 케이스 1: LLM 성공 (verification_method = "llm")

```
Claim: "신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다"
Ground Truth: "신용대출 한도는 연소득의 1.5배~2배까지 가능합니다"

[1단계 수행]
  - 키워드 검색: ✅ 관련 청크 발견
  - 유사도 계산: 0.95 (높은 유사도)
  - 숫자 비교: ✅ "1.5배", "2배" 일치
  - 휴리스틱 판단: is_accurate_heuristic = True

[2단계 수행]
  - LLM 검증: ✅ 성공
  - LLM 판단: is_accurate = True
  - LLM reasoning: "의미적으로 동일합니다"

[최종 결과]
  - verification_method = "llm"
  - is_accurate = True (LLM 결과)
  - similarity_score = 0.95 (LLM confidence)
```

### 케이스 2: LLM 없음 (verification_method = "semantic")

```
Claim: "신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다"
Ground Truth: "신용대출 한도는 연소득의 1.5배~2배까지 가능합니다"

[1단계 수행]
  - 키워드 검색: ✅ 관련 청크 발견
  - 유사도 계산: 0.95 (높은 유사도, 임베딩 사용)
  - 숫자 비교: ✅ "1.5배", "2배" 일치
  - 휴리스틱 판단: is_accurate_heuristic = True

[2단계 미수행]
  - LLM 없음 또는 use_llm=False

[최종 결과]
  - verification_method = "semantic" (임베딩 사용)
  - is_accurate = True (휴리스틱 결과)
  - similarity_score = 0.95
```

### 케이스 3: LLM 실패 (verification_method = "semantic")

```
Claim: "금리는 연 3.5%입니다"
Ground Truth: "신용대출 기본금리는 연 2.15%입니다"

[1단계 수행]
  - 키워드 검색: ✅ 관련 청크 발견
  - 유사도 계산: 0.60 (낮은 유사도)
  - 숫자 비교: ❌ "3.5%" ≠ "2.15%"
  - 휴리스틱 판단: is_accurate_heuristic = False

[2단계 수행]
  - LLM 검증: ❌ 실패 (API 오류 등)

[최종 결과]
  - verification_method = "semantic" (LLM 실패로 휴리스틱 사용)
  - is_accurate = False (휴리스틱 결과)
  - similarity_score = 0.60
```

## ✅ 정확한 답변

**질문**: "llm이 최종 판단 방법이면 그건 1단계를 거친 후에 llm 검증까지 됐다는거야?"

**답변**: **네, 맞습니다!**

`verification_method = "llm"`이면:
1. ✅ **1단계를 거쳤습니다**: 키워드 검색 → 유사도 계산 → 휴리스틱 판단
2. ✅ **2단계(LLM 검증)까지 완료되었습니다**: LLM 검증 성공
3. ✅ **최종 판단은 LLM 결과를 사용합니다**: `is_accurate = llm_result["is_accurate"]`

즉, **1단계 + 2단계 모두 수행**된 것입니다.

반면 `verification_method = "semantic"` 또는 `"keyword"`이면:
1. ✅ **1단계만 수행**: 키워드 검색 → 유사도 계산 → 휴리스틱 판단
2. ❌ **2단계 미수행**: LLM 없음 또는 실패
3. ✅ **최종 판단은 1단계 휴리스틱 결과 사용**: `is_accurate = is_accurate_heuristic`

## 📌 요약

| verification_method | 1단계 수행 | 2단계(LLM) 수행 | 최종 판단 기준 |
|---------------------|-----------|----------------|---------------|
| `"llm"` | ✅ 항상 | ✅ 성공 | LLM 결과 |
| `"semantic"` | ✅ 항상 | ❌ 없음/실패 | 휴리스틱 (임베딩) |
| `"keyword"` | ✅ 항상 | ❌ 없음/실패 | 휴리스틱 (SequenceMatcher) |

**핵심**: `verification_method`는 **최종 판단에 사용된 방법**을 나타내며, `"llm"`이면 1단계와 2단계를 모두 거친 것입니다.

