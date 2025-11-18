# 제품 지식 RAG 기반 평가 시스템 가이드

## 📚 개요

시뮬레이션 평가 시 **제품 지식 정확도**를 자동으로 측정하는 시스템입니다. 
`backend/data/rag_sources/products/` 디렉토리의 상세한 제품 정보를 활용하여 
신입 행원의 답변이 실제 제품 정보와 일치하는지 검증합니다.

---

## 🏗️ 시스템 구조

### 1. **데이터 구조**

```
backend/data/rag_sources/products/hakyung/
├── CRD-CRE.jsonl          # 하경 프리미엄 신용카드 (20개 청크)
├── DEP-TIM.jsonl          # 정기예금 (45개 청크)
├── LON-MTG.jsonl          # 주택담보대출 (32개 청크)
└── ... (총 16개 제품)
```

**JSONL 파일 형식:**
```json
{
  "id": "CRD-CRE-P01-S02-C001",
  "document_id": "CRD-CRE",
  "product": "하경 프리미엄 신용카드",
  "product_code": "CRD-CRE",
  "part_no": 1,
  "part_title": "상품 개요",
  "subsection_title": "개념: 신용한도 내 후불결제",
  "breadcrumb": "PART 1. 상품 개요 > 개념",
  "text": "신용한도 내 후불결제, 다양한 혜택과 포인트 적립",
  "chunking": { "strategy": "structure+size", "max_len": 800 }
}
```

### 2. **핵심 컴포넌트**

#### `ProductKnowledgeService` 
📁 `backend/app/services/product_knowledge_service.py`

- **기능:**
  - 제품 jsonl 파일 로드 및 캐싱
  - 키워드 기반 제품 정보 검색
  - 대화에서 제품 관련 사실(Fact) 추출
  - RAG 기반 사실 검증

- **주요 메서드:**
  ```python
  # 1. 제품 정보 검색
  search_by_keyword(query, product_codes, top_k)
  
  # 2. 대화에서 사실 추출
  extract_product_facts_from_conversation(conversation)
  
  # 3. 사실 검증
  verify_fact_accuracy(claim, product_code, category)
  
  # 4. 대화 전체 검증
  batch_verify_conversation(conversation)
  ```

#### `ScoreMetrics` 
📁 `backend/app/services/score_metrics.py`

- **강화된 `calculate_knowledge_score` 메서드:**
  - RAG 기반 검증 우선 사용
  - Fallback: 휴리스틱 기반 평가
  
- **검증 프로세스:**
  ```
  1. 대화에서 제품 정보 언급 추출 (금리, 한도, 기간 등)
  2. RAG 데이터와 비교하여 정확도 계산
  3. 오류당 15점 감점 적용
  4. 카테고리별/제품별 통계 생성
  ```

#### `EvaluationService` 
📁 `backend/app/services/evaluation_service.py`

- 기존 평가 로직에 자동 통합
- `product_data` 매개변수 불필요 (자동 로드)

---

## 🔬 평가 로직

### **지식 점수 계산 알고리즘**

```python
# 1. 대화에서 제품 정보 추출
facts = extract_product_facts_from_conversation(conversation)

# 2. 각 사실을 RAG 데이터와 비교
for fact in facts:
    verification = verify_fact_accuracy(
        claim=fact['claim'],
        product_code=fact['product_code'],
        category=fact['category']  # 금리, 한도, 기간, 조건 등
    )
    
    # 3. 숫자 정보는 정확히 일치해야 함
    if has_numbers(claim):
        is_accurate = (claimed_number == truth_number)
    else:
        is_accurate = (similarity >= 0.7)

# 4. 점수 계산
base_score = accuracy_rate * 100
final_score = base_score - (errors * 15)  # 오류당 15점 감점
```

### **정보 카테고리 분류**

시스템이 자동으로 감지하는 제품 정보 카테고리:

| 카테고리 | 패턴 예시 | 제품 예시 |
|---------|----------|----------|
| **금리** | `연 2.5%`, `이자율 3.0%` | 정기예금, 대출 |
| **한도** | `최대 10억원`, `500만원까지` | 대출, 적금 |
| **기간** | `12개월`, `3년` | 예금, 대출 |
| **조건** | `만 19세 이상`, `신용등급 1-6` | 카드, 대출 |
| **수수료** | `수수료 면제`, `3,000원` | 카드, 송금 |
| **혜택** | `포인트 1% 적립`, `할인 10%` | 카드 |

---

## 💻 사용 방법

### **1. 시뮬레이션 평가 시 자동 적용**

시뮬레이션 종료 후 평가가 실행될 때 자동으로 제품 지식 검증이 수행됩니다:

```python
from app.services.evaluation_service import EvaluationService

evaluation_service = EvaluationService(session)

# 평가 실행 (제품 지식 자동 검증 포함)
result = await evaluation_service.evaluate_session(
    session_key="session_123",
    use_llm=True  # LLM 평가 + RAG 검증
)

# 결과 확인
print(f"지식 점수: {result['score']['knowledge']['point']}점")
print(f"정확도: {result['score']['knowledge']['reason']}")

# 상세 정보
details = result['detail_feedback']['knowledge_details']
print(f"RAG 검증됨: {details['rag_verified']}")
print(f"정확한 주장: {details['accurate_claims']}/{details['total_claims']}")
print(f"카테고리별 정확도: {details['by_category']}")
```

### **2. 독립적인 제품 지식 서비스 사용**

```python
from app.services.product_knowledge_service import ProductKnowledgeService

service = ProductKnowledgeService()

# 제품 정보 검색
results = service.search_by_keyword("정기예금 금리", top_k=3)
for chunk in results:
    print(f"{chunk['product']}: {chunk['text']}")

# 대화 검증
conversation = [
    {"role": "employee", "text": "정기예금 금리는 연 2.5%입니다."}
]
verification = service.batch_verify_conversation(conversation)
print(f"정확도: {verification['accuracy_rate']:.1%}")
```

---

## 📊 평가 결과 예시

### **Case 1: 정확한 정보 제공**

```python
대화:
- 직원: "정기예금 최소 가입 금액은 50만원이며, 기본 금리는 연 2.05%입니다."
- 직원: "12개월의 경우 2.15%가 적용됩니다."

결과:
✅ 지식 점수: 95점
✅ 정확한 주장: 3/3 (100%)
✅ 카테고리별:
   - 한도: 1/1 (100%)
   - 금리: 2/2 (100%)
```

### **Case 2: 불확실한 표현 사용**

```python
대화:
- 직원: "포인트 적립이 1% 정도 되는 것 같아요."
- 직원: "연회비는 확실하진 않은데 1만원 정도일 거예요."

결과:
⚠️ 지식 점수: 45점
❌ 불확실한 표현 2회 감지
❌ 구체적 수치 검증 불가
```

### **Case 3: 잘못된 정보 제공**

```python
대화:
- 직원: "정기예금 금리는 연 10%입니다."  # 실제: 2.05~2.80%
- 직원: "최소 10원부터 가입 가능합니다."  # 실제: 50만원

결과:
❌ 지식 점수: 0점
❌ 정확한 주장: 0/2 (0%)
❌ 오류:
   - 금리 정보 부정확 (-15점)
   - 한도 정보 부정확 (-15점)
```

---

## 🧪 테스트

### **테스트 스크립트 실행**

```bash
cd backend
python scripts/test_product_knowledge_evaluation.py
```

**테스트 항목:**
1. ✅ 제품 jsonl 파일 로드 (16개 제품, 400+ 청크)
2. ✅ 키워드 검색 기능
3. ✅ 대화에서 사실 추출
4. ✅ 사실 검증 로직
5. ✅ 지식 점수 계산
6. ✅ 카테고리별/제품별 통계

---

## 🔧 설정 및 커스터마이징

### **1. 오류 감점 정도 조정**

```python
# score_metrics.py
error_penalty = inaccurate_claims * 15  # 기본: 오류당 15점
# 더 엄격하게: 20점, 더 관대하게: 10점
```

### **2. 유사도 임계값 조정**

```python
# product_knowledge_service.py
is_accurate = similarity_score >= 0.7  # 기본: 70%
# 더 엄격하게: 0.8, 더 관대하게: 0.6
```

### **3. 새로운 제품 추가**

```bash
# 1. jsonl 파일 생성
backend/data/rag_sources/products/hakyung/NEW-PRODUCT.jsonl

# 2. 자동 로드됨 (재시작 불필요)
# ProductKnowledgeService가 자동으로 감지하여 로드
```

---

## 📈 성능 및 확장성

### **현재 성능**

- **로드 속도:** 16개 제품 (400+ 청크) → ~0.5초
- **검색 속도:** 키워드 검색 → ~0.01초
- **검증 속도:** 대화 전체 검증 → ~0.1초
- **메모리 사용:** ~10MB (캐싱)

### **확장 계획**

1. **벡터 임베딩 검색**
   - 현재: 키워드 기반 (SequenceMatcher)
   - 개선: sentence-transformers 사용하여 의미적 유사도 계산

2. **LLM 기반 검증**
   - 현재: 정규식 + 숫자 비교
   - 개선: GPT-4를 활용한 자연어 일치도 평가

3. **실시간 피드백**
   - 현재: 시뮬레이션 종료 후 평가
   - 개선: 실시간으로 오류 감지 및 알림

---

## 🐛 문제 해결

### **제품이 로드되지 않음**

```bash
# 1. 데이터 디렉토리 확인
ls backend/data/rag_sources/products/hakyung/

# 2. JSONL 파일 형식 검증
python -m json.tool backend/data/rag_sources/products/hakyung/CRD-CRE.jsonl

# 3. 테스트 실행
python backend/scripts/test_product_knowledge_evaluation.py
```

### **검색 결과가 없음**

- 검색어를 더 구체적으로 (예: "금리" → "정기예금 금리")
- 제품 코드로 필터링 (`product_codes=["DEP-TIM"]`)
- 청크 텍스트에 실제 포함된 키워드 사용

### **정확도가 항상 0%**

- 숫자 형식 확인 (쉼표, 공백 등)
- 유사도 임계값 조정 (기본: 0.7)
- 로그 확인: `_calculate_knowledge_score_with_rag` 출력

---

## 📝 관련 파일

| 파일 | 설명 |
|------|------|
| `backend/app/services/product_knowledge_service.py` | 제품 지식 RAG 서비스 |
| `backend/app/services/score_metrics.py` | 평가 지표 계산 (강화됨) |
| `backend/app/services/evaluation_service.py` | 종합 평가 서비스 |
| `backend/scripts/test_product_knowledge_evaluation.py` | 테스트 스크립트 |
| `backend/data/rag_sources/products/hakyung/*.jsonl` | 제품 데이터 |

---

## 🎯 다음 단계

1. ✅ 제품 jsonl 로더 구현
2. ✅ RAG 기반 정확도 검증 로직
3. ✅ 평가 시스템 통합
4. ⏳ 벡터 임베딩 검색 추가 (선택)
5. ⏳ LLM 기반 의미적 검증 (선택)
6. ⏳ 실시간 피드백 시스템 (선택)

---

## 📞 문의

문제가 발생하거나 개선 제안이 있으면 이슈를 등록해주세요.

**작성일:** 2025-11-11
**버전:** 1.0.0

