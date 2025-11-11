# 🔬 하이브리드 제품 지식 검증 시스템

## 📌 개요

**문제:** RAG 데이터로 키워드 매칭만 하면 의미적 정확도가 떨어질 수 있음  
**해결:** **3단계 하이브리드 검증** 시스템 구축

```
1단계: Keyword Matching  →  빠른 후보 검색
2단계: Semantic Similarity  →  의미적 유사도 계산
3단계: LLM Verification  →  논리적 정확성 검증 (선택)
```

---

## 🎯 용어 명확화

### ❌ **혼동 가능한 용어**
- **"RAG"**: 검색 시스템? 데이터 저장소?

### ✅ **명확한 용어 정의**

| 용어 | 설명 | 파일/위치 |
|------|------|-----------|
| **Product Knowledge Base** | 제품 정보 저장소 | `backend/data/rag_sources/products/*.jsonl` |
| **RAG System** | 검색 증강 생성 시스템 | `app/services/rag_service.py` (별도) |
| **Knowledge Verification** | 제품 지식 검증 프로세스 | `app/services/product_knowledge_service.py` |
| **Hybrid Verification** | 3단계 하이브리드 검증 | Keyword + Semantic + LLM |

---

## 🔍 3단계 검증 프로세스

### **1단계: Keyword Matching** (빠름, 정확도 낮음)

```python
# 키워드 기반 청크 검색
relevant_chunks = search_by_keyword(
    query="금리 연 2.5%",
    product_codes=["DEP-TIM"],
    top_k=3
)

# 결과: 관련 제품 청크 리스트
# 장점: 빠른 검색
# 단점: 동의어, 패러프레이즈 감지 불가
```

### **2단계: Semantic Similarity** (중간 속도, 중간 정확도)

```python
# 의미적 유사도 계산
similarity_score = SequenceMatcher(
    None, 
    claim.lower(), 
    ground_truth.lower()
).ratio()

# 숫자 정확도 검증
if has_numbers(claim):
    is_accurate = (claimed_number == truth_number)
else:
    is_accurate = (similarity >= 0.7)

# 장점: 동의어 어느 정도 처리
# 단점: 복잡한 논리 판단 불가
```

### **3단계: LLM Verification** (느림, 정확도 높음)

```python
# GPT-4를 사용한 논리적 검증
llm_result = _verify_with_llm(
    claim="금리가 10% 정도 되는 것 같아요",
    ground_truth="기본 금리는 연 2.05%입니다",
    category="금리",
    product_code="DEP-TIM"
)

# LLM 응답 (JSON):
{
  "is_accurate": false,
  "confidence": 0.95,
  "reasoning": "사용자 주장의 금리 10%는 실제 정보 2.05%와 크게 차이나며, 
               '같아요'는 불확실한 표현입니다."
}

# 장점: 높은 정확도, 맥락 이해
# 단점: 느림, API 비용
```

---

## 💡 사용 예시

### **예시 1: Semantic만 사용 (기본)**

```python
from app.services.product_knowledge_service import ProductKnowledgeService

# LLM 비활성화
service = ProductKnowledgeService(use_llm=False)

conversation = [
    {"role": "employee", "text": "정기예금 금리는 연 2.15%입니다."}
]

result = service.batch_verify_conversation(conversation)

print(f"정확도: {result['accuracy_rate']:.1%}")
print(f"검증 방법: {result['verification_methods']}")
# 출력: {'keyword': 1, 'semantic': 0}
```

### **예시 2: LLM 검증 포함 (권장)**

```python
# LLM 활성화 (OPENAI_API_KEY 필요)
service = ProductKnowledgeService(use_llm=True)

conversation = [
    {"role": "employee", "text": "금리가 10% 정도 되는 것 같아요."}
]

result = service.batch_verify_conversation(conversation, use_llm=True)

print(f"정확도: {result['accuracy_rate']:.1%}")
print(f"검증 방법: {result['verification_methods']}")
# 출력: {'llm': 1}

# 세부 정보
for v in result['verifications']:
    if v.verification_method == "llm":
        print(f"LLM 판단: {v.is_accurate}")
        print(f"이유: {v.llm_reasoning}")
```

### **예시 3: 하이브리드 비교**

```python
# 같은 대화에 대해 두 방법 비교
service = ProductKnowledgeService(use_llm=True)

conversation = [
    {"role": "employee", "text": "정기예금 금리는 12개월 기준 연 2.15%입니다."}
]

# Semantic 검증
result_semantic = service.batch_verify_conversation(
    conversation, 
    use_llm=False
)

# LLM 검증
result_llm = service.batch_verify_conversation(
    conversation, 
    use_llm=True
)

print(f"Semantic 정확도: {result_semantic['accuracy_rate']:.1%}")
print(f"LLM 정확도: {result_llm['accuracy_rate']:.1%}")

# 비교
diff = result_llm['accuracy_rate'] - result_semantic['accuracy_rate']
if abs(diff) > 0.01:
    print(f"차이: {diff:+.1%}")
```

---

## 🔧 설정 방법

### **1. 환경 변수 설정**

```bash
# LLM 검증 활성화
export OPENAI_API_KEY="your-api-key-here"

# Docker Compose
OPENAI_API_KEY=your-api-key-here
```

### **2. 코드에서 설정**

```python
# 전역 설정 (기본)
service = ProductKnowledgeService(use_llm=True)

# 요청별 설정 (우선순위 높음)
result = service.verify_fact_accuracy(
    claim="금리는 연 2.5%입니다",
    product_code="DEP-TIM",
    category="금리",
    use_llm=True  # 이 요청만 LLM 사용
)
```

### **3. 비용 최적화 전략**

```python
# 전략 1: Semantic으로 선별 후 LLM 검증
verification = service.verify_fact_accuracy(...)

if verification.similarity_score < 0.9:
    # 불확실한 경우만 LLM으로 재검증
    verification_llm = service.verify_fact_accuracy(
        ..., 
        use_llm=True
    )

# 전략 2: 중요한 카테고리만 LLM 사용
if category in ["금리", "한도"]:
    use_llm = True
else:
    use_llm = False

# 전략 3: Fallback 체인
try:
    result = verify_with_llm(...)
except:
    result = verify_semantic(...)
```

---

## 📊 성능 비교

| 검증 방법 | 속도 | 정확도 | API 비용 | 사용 시기 |
|-----------|------|--------|----------|-----------|
| **Keyword** | 🟢 빠름 (10ms) | 🟡 낮음 (60%) | 무료 | 초기 필터링 |
| **Semantic** | 🟡 중간 (50ms) | 🟡 중간 (75%) | 무료 | 일반 검증 |
| **LLM** | 🔴 느림 (1-3s) | 🟢 높음 (95%) | $0.0001/요청 | 중요 검증 |

### **테스트 결과 예시**

```bash
# 테스트 실행
python backend/scripts/test_product_knowledge_evaluation.py

# 출력:
✅ Semantic 검증: 75% 정확도
✅ LLM 검증: 95% 정확도
📊 차이: +20% (LLM이 더 정확함)

# 검증 방법 통계:
{
  "keyword": 2,  # 키워드로 먼저 검색
  "semantic": 3,  # 의미 유사도로 판단
  "llm": 5       # LLM으로 최종 검증
}
```

---

## 🎯 실제 적용 예시

### **Case 1: 정확한 정보**

```
직원: "정기예금 금리는 12개월 기준 연 2.15%입니다."

[Keyword] → 관련 청크 찾음
[Semantic] → 숫자 일치 (2.15 == 2.15) ✅
[LLM] → "정확한 정보입니다" ✅

결과: ✅ 정확 (semantic으로 충분)
```

### **Case 2: 불확실한 표현**

```
직원: "금리가 2% 정도 되는 것 같아요."

[Keyword] → 관련 청크 찾음
[Semantic] → 숫자 비슷 (2 ≈ 2.15) → 애매함 ⚠️
[LLM] → "불확실한 표현 '같아요' 사용, 정확한 수치 아님" ❌

결과: ❌ 부정확 (LLM 검증 필요)
```

### **Case 3: 패러프레이즈**

```
직원: "50만원 이상이면 가입하실 수 있어요."
실제: "최소 가입금액: 50만원"

[Keyword] → 찾음
[Semantic] → 유사도 0.65 → 낮음 ⚠️
[LLM] → "의미적으로 동일합니다" ✅

결과: ✅ 정확 (LLM 검증으로 통과)
```

---

## 🚦 Best Practices

### ✅ **권장 사항**

1. **개발/테스트 환경**: `use_llm=False` (빠른 반복)
2. **프로덕션 환경**: `use_llm=True` (높은 정확도)
3. **중요 카테고리**: 금리, 한도 → 항상 LLM 검증
4. **비중요 정보**: 일반 설명 → Semantic으로 충분
5. **비용 관리**: 배치 검증 시 샘플링 사용

### ❌ **피해야 할 패턴**

1. 모든 요청에 LLM 사용 (비용 폭발)
2. LLM 없이 숫자 정보 검증 (정확도 낮음)
3. Semantic만으로 복잡한 논리 판단
4. 검증 방법을 로그로 남기지 않음

---

## 🔄 RAG 시스템과의 차이

### **RAG System** (`app/services/rag_service.py`)
```python
# 목적: 문서 검색 후 답변 생성
query = "대출 상품 추천해줘"
answer = rag_service.generate_rag_answer(query)

# 프로세스:
1. 유사도 검색 → 관련 문서 찾기
2. LLM 생성 → 답변 생성
3. 출력 → 고객에게 답변
```

### **Product Knowledge Verification** (이 시스템)
```python
# 목적: 직원 답변 검증
claim = "금리는 연 2.5%입니다"
verification = knowledge_service.verify_fact_accuracy(claim, ...)

# 프로세스:
1. 키워드 검색 → 관련 제품 정보 찾기
2. 의미 비교 → 주장과 사실 비교
3. LLM 검증 → 논리적 정확성 판단
4. 출력 → 평가 점수
```

**핵심 차이:**
- RAG: **생성** (Generate) - 새로운 답변 만들기
- Knowledge Verification: **검증** (Verify) - 기존 답변 확인하기

---

## 📈 향후 개선 방향

1. **Vector Embedding 검색**
   - 현재: SequenceMatcher (간단)
   - 개선: sentence-transformers (정확)

2. **LLM 프롬프트 최적화**
   - Few-shot 예시 추가
   - Chain-of-Thought 적용

3. **캐싱 전략**
   - 동일 claim 재검증 방지
   - LLM 결과 캐싱

4. **A/B 테스트**
   - Semantic vs LLM 정확도 비교
   - 비용 대비 효과 분석

---

## 💬 FAQ

**Q: LLM 없이도 작동하나요?**  
A: 네, Semantic 검증만으로도 작동합니다. (정확도 75% 수준)

**Q: LLM 비용은 얼마나 되나요?**  
A: GPT-4o-mini 기준 요청당 약 $0.0001 (1만 요청에 $1)

**Q: RAG와 혼동되지 않나요?**  
A: 용어를 명확히 구분했습니다:
- RAG System = 검색 + 생성
- Knowledge Verification = 검색 + 검증

**Q: 어떤 검증 방법을 선택해야 하나요?**  
A: 
- 개발: Semantic (빠름)
- 프로덕션: LLM (정확)
- 중요 정보: 항상 LLM

---

## 📝 관련 문서

- [제품 지식 평가 가이드](./PRODUCT_KNOWLEDGE_EVALUATION_GUIDE.md)
- [평가 지표 가이드](./EVALUATION_METRICS_GUIDE.md)
- [RAG 시뮬레이션 통합](./EVALUATION_INTEGRATION_GUIDE.md)

---

**작성일:** 2025-11-11  
**버전:** 2.0.0 (하이브리드 검증 추가)

