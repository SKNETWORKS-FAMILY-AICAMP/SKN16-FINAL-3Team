# RAG 기반 지식 역량 평가 시스템 - 전체 흐름

## 📋 목차
1. [시스템 개요](#시스템-개요)
2. [평가 흐름 전체 개요](#평가-흐름-전체-개요)
3. [상세 단계별 설명](#상세-단계별-설명)
4. [핵심 컴포넌트 설명](#핵심-컴포넌트-설명)
5. [점수 산정 기준](#점수-산정-기준)

---

## 시스템 개요

### 목적
은행 직원의 상품 지식 역량을 자동으로 평가하는 시스템

### 주요 특징
- **LLM 기반 사실 추출**: 정규식 패턴 없이 다양한 표현 자동 처리
- **카테고리 기반 평가**: 고객 질문 맥락을 고려한 공정한 평가
- **명확한 점수 기준**: 100점 만점, 명확한 비율 기반 계산

---

## 평가 흐름 전체 개요

```
[직원 발화]
    ↓
[1단계] LLM 기반 사실 추출
    ↓
[2단계] 제품 코드 & 카테고리 추출
    ↓
[3단계] 카테고리 기반 키워드 필터링
    ↓
[4단계] RAG 상품 데이터 매칭
    ↓
[5단계] 점수 계산
    ↓
[평가 결과]
```

---

## 상세 단계별 설명

### 🎯 1단계: 직원 발화 입력

**입력:**
```
직원: "프리미엄 신용카드의 연회비는 연 10만원이고, 한도는 최대 5천만원까지 가능합니다"
```

**처리 위치:**
- `rag_simulation_service.py` → `_evaluate_rag_integration()`
- 함수 호출: `generate_comprehensive_feedback()` → 각 발화별 평가

---

### 🎯 2단계: LLM 기반 사실 추출

**함수:** `ProductKnowledgeService.extract_product_facts_from_conversation()`

**처리 과정:**

```
[2-1] LLM 호출 (GPT-4o-mini)
  입력: 직원 발화 전체
  프롬프트: 카테고리별 정보 추출 요청
  ↓
[2-2] LLM 응답 파싱
  JSON 형식:
  {
    "facts": [
      {
        "category": "수수료",
        "claim": "연회비는 연 10만원",
        "value": "100000",
        "unit": "원"
      },
      {
        "category": "한도",
        "claim": "한도는 최대 5천만원까지",
        "value": "50000000",
        "unit": "원"
      }
    ]
  }
  ↓
[2-3] Fact 객체 변환
  [
    {
      "claim": "연회비는 연 10만원",
      "category": "수수료",
      "matched_value": "100000",
      "product_codes": ["CRD-CRE"]
    },
    {
      "claim": "한도는 최대 5천만원까지",
      "category": "한도",
      "matched_value": "50000000",
      "product_codes": ["CRD-CRE"]
    }
  ]
```

**핵심 기능:**
- ✅ **한국어 금액 단위 자동 인식**: "10만원" → "100000"
- ✅ **다양한 표현 처리**: "연 2.5%", "연이율 2.5퍼센트" 등
- ✅ **카테고리 자동 분류**: 금리, 한도, 수수료 등
- ✅ **Fallback**: LLM 실패 시 정규식으로 자동 전환

**코드 위치:**
- `product_knowledge_service.py` → `_extract_facts_with_llm()`

---

### 🎯 3단계: 제품 코드 & 카테고리 수집

**함수:** `_evaluate_rag_integration()`

**처리 과정:**

```
추출된 facts 순회
  ↓
extracted_product_codes = {"CRD-CRE"}  # 제품 코드 수집
extracted_categories = {"수수료", "한도"}  # 카테고리 수집
extracted_claims = ["연회비는 연 10만원", "한도는 최대 5천만원까지"]  # Claim 수집
```

**핵심 결과:**
- `extracted_product_codes`: 언급된 제품 코드들
- `extracted_categories`: 언급된 정보 카테고리들
- `extracted_claims`: 추출된 정보 문구들

---

### 🎯 4단계: 점수 계산 (keyword_score)

**함수:** `_evaluate_rag_integration()`

**계산 방식:**
```python
if extracted_claims:
    keyword_score = 50  # Claim 추출 성공
else:
    keyword_score = 0   # Claim 추출 실패
```

**점수 기준:**
- ✅ Claim이 1개 이상 추출됨 → **50점**
- ❌ Claim 추출 실패 → **0점**

---

### 🎯 5단계: 카테고리 기반 키워드 필터링

**함수:** `_filter_info_keywords_by_categories()`

**처리 과정:**

```
[5-1] info_keywords 로드
  product_keywords_cache.json → "CRD-CRE"의 info_keywords
  전체 키워드: ["1.0%", "2.0%", "10,000원", "30,000원", "100만원", 
               "5,000만원", "포인트", "할인", "연회비", ...] (25개)
  ↓
[5-2] 카테고리 키워드 확인
  category_config.json → subsection_keywords
  "수수료" → ["수수료", "연회비", "중도상환", "중도해지"]
  "한도" → ["한도", "신용한도", "최대", "최소"]
  ↓
[5-3] 필터링
  직원이 추출한 카테고리: {"수수료", "한도"}
  → "수수료" 관련: ["10,000원", "30,000원", "연회비"] (3개)
  → "한도" 관련: ["100만원", "5,000만원"] (2개)
  → 필터링된 키워드: ["10,000원", "30,000원", "연회비", "100만원", "5,000만원"] (5개)
  ↓
[5-4] 평가 대상 결정
  카테고리 필터링 성공 → 필터링된 키워드만 평가
  (전체 25개 대신 5개만 평가 → 공정한 평가)
```

**핵심 로직:**
1. `category_config.json`의 `subsection_keywords`로 카테고리 키워드 확인
2. `info_keywords`에서 해당 키워드가 포함된 항목만 필터링
3. 예: "연회비" 키워드가 있으면 → "수수료" 카테고리 관련 키워드만 추출

**매칭 규칙:**
- 정확 일치: "연회비" == "연회비" ✅
- 부분 포함: "포인트적립"에 "포인트" 포함 → "혜택" 카테고리 ✅
- 수치 포함: "10,000원"은 발화에 "연회비"가 함께 있으면 포함 ✅

**코드 위치:**
- `rag_simulation_service.py` → `_filter_info_keywords_by_categories()`

---

### 🎯 6단계: RAG 상품 데이터 매칭

**함수:** `_evaluate_rag_integration()`

**처리 과정:**

```
[6-1] 상품 데이터 로드
  CRD-CRE.jsonl 파일에서 청크 로드
  ↓
[6-2] 키워드 매칭
  발화: "연회비는 연 10만원"
  필터링된 키워드: ["10,000원", "30,000원", "연회비", "100만원", "5,000만원"]
  발견된 키워드: ["10만원" (또는 "100000원"), "연회비"] (2개)
  ↓
[6-3] 근거 추출
  상품 데이터에서 관련 청크 찾기
  → "연회비" 관련 청크 추출
  → "10만원" 관련 청크 추출
```

**핵심 결과:**
- `found_product_keywords`: 발화에서 발견된 키워드들
- `product_evidence`: 상품 데이터에서 찾은 근거 청크들

---

### 🎯 7단계: 점수 계산 (rag_product_info_score)

**함수:** `_evaluate_rag_integration()`

**계산 방식:**

```python
# 카테고리 필터링된 경우
if category_filtered_keywords:
    relevant_keywords = category_filtered_keywords  # 필터링된 키워드만 평가
else:
    relevant_keywords = all_relevant_keywords  # 전체 키워드 평가

found_product_keywords = [kw for kw in relevant_keywords if kw in text]
coverage_rate = len(found_product_keywords) / len(relevant_keywords)
product_score = coverage_rate * 50
```

**점수 계산 예시:**

| 상황 | 평가 대상 키워드 | 발견된 키워드 | 계산 | 점수 |
|------|----------------|-------------|------|------|
| 카테고리 필터링 성공 | 5개 (수수료+한도) | 2개 | (2/5) * 50 | **20점** |
| 카테고리 필터링 실패 | 25개 (전체) | 1개 | (1/25) * 50 | **2점** |
| 카테고리 필터링 성공 | 3개 (수수료만) | 3개 | (3/3) * 50 | **50점** |

**핵심 개선:**
- ✅ 고객이 "연회비"만 물어봤을 때 → "수수료" 카테고리만 평가
- ✅ 전체 25개 대신 관련된 5개만 평가 → 공정한 점수

---

### 🎯 8단계: 최종 점수 계산

**함수:** `_evaluate_rag_integration()`

**계산 방식:**

```python
total_score = keyword_score + product_score
# keyword_score: 50점 (claim 추출 여부)
# product_score: 50점 (카테고리 기반 키워드 매칭)
```

**예시:**
```
발화: "연회비는 연 10만원입니다"

[4단계] keyword_score = 50점 (claim 추출됨)
[7단계] product_score = 20점 (필터링된 키워드 5개 중 2개 발견)

total_score = 50 + 20 = 70점 ✅
```

**이전 방식 (비교):**
```
발화: "연회비는 연 10만원입니다"

[4단계] keyword_score = 50점
[7단계] product_score = 2점 (전체 25개 중 1개 발견)

total_score = 50 + 2 = 52점 ❌ (부당함)
```

---

### 🎯 9단계: 종합 평가

**함수:** `generate_comprehensive_feedback()`

**평가 항목:**
1. **지식 (Knowledge)**: 상품 정보 정확성
   - RAG 연동 평가 결과 사용
   - 점수: 0~100점

2. **기술 (Skill)**: 상담 프로세스 + 목표 달성도
   - 목표 달성 분석: `analyze_goal_achievement()`
   - 점수: 0~100점

3. **친절도 (Kindness)**: 예의와 배려
   - LLM 기반 평가
   - 점수: 0~100점

4. **전달력 (Clarity)**: 명확성과 자신감
   - LLM 기반 평가
   - 점수: 0~100점

**최종 결과:**
```json
{
  "scores": {
    "knowledge": 70,
    "skill": 85,
    "kindness": 90,
    "clarity": 80
  },
  "total_score": 81.25,
  "feedback": {
    "knowledge": "연회비 정보를 정확히 제공했으나, 추가 정보 부족",
    "skill": "목표 달성도 우수, 상담 프로세스 준수",
    ...
  }
}
```

---

## 핵심 컴포넌트 설명

### 1. `category_config.json`

**위치:** `backend/data/category_config.json`

**역할:**
- 카테고리와 관련 키워드 정의
- `subsection_keywords`: 카테고리별 키워드 목록
- `category_patterns`: 정규식 패턴 (fallback용)

**예시:**
```json
{
  "subsection_keywords": {
    "수수료": ["수수료", "연회비", "중도상환", "중도해지"],
    "한도": ["한도", "신용한도", "최대", "최소"]
  }
}
```

**사용 위치:**
- `_filter_info_keywords_by_categories()`: 카테고리 키워드 매칭

---

### 2. `product_keywords_cache.json`

**위치:** `backend/data/product_keywords_cache.json`

**역할:**
- 제품별 키워드 캐시
- `product_keywords`: 제품명 키워드
- `categories`: 제품의 주요 카테고리
- `info_keywords`: 제품의 핵심 정보 키워드

**예시:**
```json
{
  "CRD-CRE": {
    "product_keywords": ["CRD-CRE", "하경 프리미엄 신용카드", ...],
    "categories": ["신용등급", "한도", "연회비", "혜택"],
    "info_keywords": ["1.0%", "10,000원", "100만원", "5,000만원", "포인트", ...]
  }
}
```

**사용 위치:**
- `_get_product_info_keywords()`: 제품별 info_keywords 로드
- `_filter_info_keywords_by_categories()`: 필터링 대상 키워드

---

### 3. `ProductKnowledgeService`

**위치:** `backend/app/services/product_knowledge_service.py`

**주요 함수:**

#### `extract_product_facts_from_conversation()`
- LLM 기반 사실 추출 (기본)
- 정규식 기반 추출 (fallback)
- 한국어 금액 단위 자동 인식

#### `verify_fact_accuracy()`
- 추출된 사실의 정확성 검증
- RAG 상품 데이터와 비교
- LLM 기반 검증 (선택)

---

### 4. `RAGSimulationService`

**위치:** `backend/app/services/rag_simulation_service.py`

**주요 함수:**

#### `_evaluate_rag_integration()`
- RAG 연동 평가 메인 함수
- 점수 계산 (keyword_score + product_score)

#### `_filter_info_keywords_by_categories()`
- 카테고리 기반 키워드 필터링
- 고객 질문 맥락 고려

#### `generate_comprehensive_feedback()`
- 종합 평가 및 피드백 생성
- 4가지 역량 평가 (지식, 기술, 친절도, 전달력)

---

## 점수 산정 기준

### 총점: 100점

#### 1. keyword_score (50점)
- **기준**: Claim 추출 여부
- **계산**: 
  - Claim 1개 이상 추출 → **50점**
  - Claim 추출 실패 → **0점**

#### 2. rag_product_info_score (50점)
- **기준**: 평가 대상 키워드 대비 발견 비율
- **계산**:
  ```
  product_score = (발견된 키워드 수 / 평가 대상 키워드 수) * 50
  ```
- **평가 대상 키워드 결정**:
  - 카테고리 필터링 성공 → 필터링된 키워드만 평가
  - 카테고리 필터링 실패 → 전체 키워드 평가

### 점수 계산 예시

#### 예시 1: 카테고리 필터링 성공
```
발화: "연회비는 연 10만원입니다"

[사실 추출]
- category: "수수료"
- claim: "연회비는 연 10만원"
- value: "100000"

[키워드 필터링]
- 전체 키워드: 25개
- 필터링된 키워드: 3개 (수수료 관련)
- 발견된 키워드: 2개 ("10만원", "연회비")

[점수 계산]
- keyword_score: 50점 (claim 추출됨)
- product_score: (2/3) * 50 = 33.3점
- total_score: 50 + 33.3 = 83.3점 ✅
```

#### 예시 2: 카테고리 필터링 실패
```
발화: "연회비는 연 10만원입니다"

[사실 추출]
- category: "수수료"
- claim: "연회비는 연 10만원"

[키워드 필터링]
- 필터링 시도 → 매칭 실패
- 전체 키워드 사용: 25개
- 발견된 키워드: 1개 ("10만원")

[점수 계산]
- keyword_score: 50점
- product_score: (1/25) * 50 = 2점
- total_score: 50 + 2 = 52점 (낮은 점수)
```

---

## 주요 개선 사항 요약

### ✅ 1. LLM 기반 사실 추출
- **이전**: 정규식 패턴 의존 (패턴 추가 필요)
- **개선**: LLM이 다양한 표현 자동 처리
- **효과**: "10만원" = "100000원" 자동 인식

### ✅ 2. 카테고리 기반 평가
- **이전**: 전체 키워드 대비 비율 (부당함)
- **개선**: 카테고리별 관련 키워드만 평가
- **효과**: 고객 질문 맥락 고려, 공정한 평가

### ✅ 3. 점수 기준 명확화
- **이전**: 기본점수 30점 (임의적)
- **개선**: 명확한 비율 기반 계산
- **효과**: 평가 기준 투명성 향상

---

## 데이터 흐름 다이어그램

```
[직원 발화]
    ↓
[ProductKnowledgeService]
    ├─→ LLM 호출 (GPT-4o-mini)
    │   └─→ Fact 추출 (category, claim, value)
    │
    └─→ [Fallback] 정규식 패턴 매칭
            └─→ category_patterns 사용
    ↓
[Fact 수집]
    ├─→ extracted_product_codes
    ├─→ extracted_categories
    └─→ extracted_claims
    ↓
[RAGSimulationService]
    ├─→ keyword_score 계산 (50점)
    │   └─→ extracted_claims 존재 여부
    │
    ├─→ 카테고리 기반 필터링
    │   ├─→ category_config.json 로드
    │   ├─→ product_keywords_cache.json 로드
    │   └─→ _filter_info_keywords_by_categories()
    │
    ├─→ product_score 계산 (50점)
    │   └─→ (발견된 키워드 / 평가 대상 키워드) * 50
    │
    └─→ total_score = keyword_score + product_score
    ↓
[평가 결과]
    └─→ generate_comprehensive_feedback()
            └─→ 종합 평가 및 피드백 생성
```

---

## 핵심 파일 구조

```
backend/
├── data/
│   ├── category_config.json           # 카테고리 키워드 정의
│   ├── product_keywords_cache.json    # 제품별 키워드 캐시
│   └── rag_sources/
│       └── products/
│           └── hakyung/
│               └── CRD-CRE.jsonl      # 상품 데이터
│
└── app/
    └── services/
        ├── product_knowledge_service.py    # 사실 추출 & 검증
        └── rag_simulation_service.py       # RAG 평가 & 피드백
```

---

## 요약

### 전체 흐름
1. **직원 발화 입력** → 2. **LLM 기반 사실 추출** → 3. **카테고리 기반 필터링** → 4. **점수 계산** → 5. **종합 평가**

### 핵심 개선
- ✅ LLM 기반 추출: 다양한 표현 자동 처리
- ✅ 카테고리 기반 평가: 공정한 평가 기준
- ✅ 명확한 점수 기준: 100점 만점, 비율 기반 계산

### 평가 기준
- **keyword_score (50점)**: Claim 추출 여부
- **rag_product_info_score (50점)**: 평가 대상 키워드 대비 발견 비율

