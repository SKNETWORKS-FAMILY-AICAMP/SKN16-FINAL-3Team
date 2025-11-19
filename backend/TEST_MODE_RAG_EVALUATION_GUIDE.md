# 🧪 테스트 모드 RAG 평가 가이드

## 📌 개요

테스트 모드에서는 고정된 시나리오를 사용하여 STT 성능과 RAG 연동을 평가합니다. 각 턴에는 **예상 텍스트**, **product_code**, **keywords**가 미리 정의되어 있어, 실제 발화와 비교하여 평가합니다.

**⚠️ 중요**: 
- **테스트 모드**: RAG 평가 수행 (예상 키워드/제품 코드와 비교)
- **일반 모드**: 제품 지식 정확도 검증 수행 (자동 추출된 키워드/제품 코드로 검증)
  - 일반 모드에서도 지식 역량 평가를 위해 상품 정확성을 평가해야 하므로, `ProductKnowledgeService`가 자동으로 제품 코드와 키워드를 추출합니다.

---

## 🔍 1. product_code와 keywords 추출 방법

### 1.0 "예상 키워드"란?

**예상 키워드(expected_keywords)**는 테스트 시나리오에 미리 정의된 키워드 배열입니다. 이것은 "이 턴에서 사용자가 말해야 할 핵심 키워드"를 의미합니다.

**예시**:
```python
# 테스트 시나리오 턴 4 (직원 발화)
{
    "turn": 4,
    "role": "employee",
    "expected_text": "신용대출 한도는 고객님의 신용점수와 소득에 따라 다르며 일반적으로 연소득의 1.5배에서 2배까지 가능합니다",
    "product_code": "LON-CRE",
    "keywords": ["신용대출", "한도", "신용점수", "소득", "1.5배", "2배"]  # ← 이것이 "예상 키워드"
}
```

**키워드 매칭 과정**:
1. 테스트 시나리오에서 `keywords` 배열 추출 → 이것이 `expected_keywords`
2. 사용자가 실제로 말한 내용을 STT로 변환 → 이것이 `transcribed_text` (또는 `employee_text`)
3. `expected_keywords` 중 `transcribed_text`에 포함된 키워드 찾기
4. 포함된 비율로 점수 계산

### 1.1 테스트 시나리오 데이터 구조

테스트 시나리오는 `_get_test_scenario_data()` 메서드에서 정의되며, 각 턴은 다음과 같은 구조를 가집니다:

```python
{
    "turn": 5,  # 턴 번호
    "role": "employee",  # 역할 (employee/customer)
    "expected_text": "신용대출 한도는 고객님의 신용점수와 소득에 따라 다르며...",
    "product_code": "LON-CRE",  # 제품 코드 (None일 수 있음)
    "keywords": ["신용대출", "한도", "신용점수", "소득", "1.5배", "2배"]  # 키워드 배열
}
```

### 1.2 추출 과정

**코드 위치**: `backend/app/services/rag_simulation_service.py`

#### 단계 1: 테스트 시나리오 로드
```python
# start_test_simulation() 메서드에서
test_scenario = self._get_test_scenario_data(scenario_type)
turns = test_scenario.get("turns", [])
```

#### 단계 2: 각 턴에서 product_code와 keywords 추출
```python
# _process_test_mode_interaction() 메서드에서
current_turn = turns[current_turn_index]

# 직원 발화인 경우
if current_turn["role"] == "employee":
    expected_product_code = current_turn.get("product_code")  # 예: "LON-CRE"
    expected_keywords = current_turn.get("keywords", [])  # 예: ["신용대출", "한도", ...]
    
    # RAG 평가 수행
    rag_eval = self._evaluate_rag_integration(
        transcribed_text,  # 실제 발화 텍스트
        expected_product_code,  # 예상 제품 코드
        expected_keywords  # 예상 키워드
    )

# 고객 발화인 경우
if current_turn["role"] == "customer":
    expected_product_code = current_turn.get("product_code")
    expected_keywords = current_turn.get("keywords", [])
    
    # 고객 발화 RAG 평가 (상품 코드 추출 정확도)
    rag_eval_customer = self._evaluate_customer_rag_integration(
        transcribed_text,
        expected_product_code,
        expected_keywords
    )
```

### 1.3 product_code와 keywords의 의미

#### product_code
- **의미**: 해당 턴에서 언급되어야 할 제품 코드
- **예시**: 
  - `"LON-CRE"`: 신용대출
  - `"LON-MTG"`: 주택담보대출
  - `"DEP-MMD"`: MMDA 예금
  - `None`: 특정 제품이 아닌 일반적인 대화

#### keywords
- **의미**: 해당 턴에서 반드시 포함되어야 할 핵심 키워드 (예상 키워드)
- **정의 위치**: 테스트 시나리오의 각 턴에 미리 정의됨
- **예시**: 
  ```python
  {
      "turn": 4,
      "role": "employee",
      "expected_text": "신용대출 한도는 고객님의 신용점수와 소득에 따라...",
      "product_code": "LON-CRE",
      "keywords": ["신용대출", "한도", "신용점수", "소득", "1.5배", "2배"]  # ← 예상 키워드
  }
  ```
- **용도**: 
  - **STT 평가**: 금융 용어 인식 정확도 측정 (STT가 이 키워드들을 잘 인식했는지)
  - **RAG 평가**: 제품 정보 포함 여부 확인 (사용자가 이 키워드들을 발화에 포함했는지)

---

## 📊 2. RAG 평가 해석 방법

### 2.1 RAG 평가 구조

RAG 평가 결과는 `rag_evaluations` 배열에 저장되며, 각 평가 항목은 다음과 같은 구조를 가집니다:

```python
{
    "turn_index": 5,  # 턴 번호
    "role": "employee",  # 역할
    "expected_product_code": "LON-CRE",  # 예상 제품 코드
    "evaluation": {
        "score": 85.5,  # 총점 (0-100)
        "max_score": 100,
        "keyword_score": 45.0,  # 키워드 매칭 점수 (50점 만점)
        "rag_product_info_score": 40.5,  # RAG 상품 정보 점수 (50점 만점)
        "found_keywords": ["신용대출", "한도", "신용점수", "소득"],  # 찾은 키워드
        "missing_keywords": ["1.5배", "2배"],  # 누락된 키워드
        "rag_info_keywords_found": ["신용대출", "한도", "소득"],  # RAG 정보 키워드
        "product_evidence": {  # 상품 데이터 근거
            "matched_chunks": [...],
            "key_information": [...],
            "missing_information": [...]
        }
    }
}
```

### 2.2 평가 점수 계산 방식

#### ⚠️ 중요: 키워드 매칭의 두 가지 용도

같은 `keywords` 배열이 **두 가지 다른 평가**에 사용됩니다:

1. **STT 평가** (`_evaluate_single_stt`): 음성 인식 정확도 측정
   - `keyword_recognition_rate`: STT가 금융 용어를 얼마나 잘 인식했는지 (0-100%)
   - `recognized_keywords`: STT가 인식한 키워드 목록
   - `missing_keywords`: STT가 인식하지 못한 키워드 목록
   - **목적**: 음성 인식 시스템의 성능 평가 (STT 성능 검증, 오타율 측정)
   - **지표로 사용 가능**: 
     - ✅ STT 성능 검증 지표
     - ✅ 금융 용어 인식 정확도
     - ✅ 오타율 측정 (누락된 키워드 = 오타/인식 실패)

2. **RAG 평가** (`_evaluate_rag_integration`): RAG 정보 포함 여부 확인
   - `keyword_score`: RAG 평가의 일부 (0-50점)
   - `found_keywords`: 발화에 포함된 키워드 목록
   - `missing_keywords`: 발화에 누락된 키워드 목록
   - **목적**: RAG에서 가져온 정보가 발화에 포함되었는지 확인 (사용자 응답 품질 평가)

**차이점**:
- **STT 평가**: 음성 → 텍스트 변환 정확도 (STT 시스템 평가)
  - 예: "신용대출"을 "신용 대출"로 인식 → STT 오타/인식 실패
- **RAG 평가**: 텍스트에 정보 포함 여부 (사용자 응답 품질 평가)
  - 예: "신용대출" 키워드를 발화에 포함했는지 → 사용자가 정보를 잘 전달했는지

**공통점**:
- 둘 다 같은 `keywords` 배열을 사용하여 키워드 매칭을 수행
- 둘 다 `found_keywords`와 `missing_keywords`를 반환
- **키워드 매칭 결과는 STT 성능 검증 지표로 활용 가능**

#### 직원 발화 RAG 평가 (`_evaluate_rag_integration`)

**총점 100점 = 키워드 점수(50점) + RAG 상품 정보 점수(50점)**

1. **키워드 매칭 (50점)** - RAG 평가용
   
   **매칭 대상**:
   - **예상 키워드** (`expected_keywords`): 테스트 시나리오에 미리 정의된 키워드 배열
   - **실제 발화** (`employee_text`): 사용자가 말한 내용을 STT로 변환한 텍스트
   
   **매칭 과정**:
   ```python
   # 예상 키워드 (테스트 시나리오에서 정의)
   expected_keywords = ["신용대출", "한도", "신용점수", "소득", "1.5배", "2배"]
   
   # 실제 발화 (사용자가 말한 내용)
   employee_text = "신용대출 한도는 고객님의 신용점수와 소득에 따라 다르며 일반적으로 연소득의 1.5배에서 2배까지 가능합니다"
   
   # 키워드 매칭: expected_keywords 중 employee_text에 포함된 것 찾기
   found_keywords = [kw for kw in expected_keywords if kw in employee_text]
   # 결과: ["신용대출", "한도", "신용점수", "소득", "1.5배", "2배"] → 6개 모두 찾음!
   
   # 점수 계산
   keyword_score = (len(found_keywords) / len(expected_keywords) * 50)
   # = (6 / 6 * 50) = 50점 (만점)
   ```
   
   **구체적 예시**:
   - **예상 키워드**: `["신용대출", "한도", "신용점수", "소득", "1.5배", "2배"]` (6개)
   - **실제 발화**: "신용대출 한도는 신용점수와 소득에 따라 다릅니다" (4개 찾음)
   - **찾은 키워드**: `["신용대출", "한도", "신용점수", "소득"]` (4개)
   - **누락된 키워드**: `["1.5배", "2배"]` (2개)
   - **점수**: (4 / 6 * 50) = **33.3점**
   
   **의미**: 테스트 시나리오에서 요구한 키워드 중 실제 발화에 몇 개나 포함되어 있는지 확인
   - **주의**: 이것은 RAG 평가 점수이며, STT 점수가 아닙니다!

2. **RAG 상품 정보 포함 여부 (50점)**
   ```python
   # 상품별 핵심 정보 키워드
   product_info_keywords = {
       "LON-CRE": ["신용대출", "한도", "신용점수", "소득", "1.5배", "2배"],
       "LON-MTG": ["주택담보", "LTV", "DTI", "DSR", "담보인정비율", "70%", "60%"],
       ...
   }
   relevant_keywords = product_info_keywords.get(expected_product_code, [])
   found_product_keywords = [kw for kw in relevant_keywords if kw in employee_text]
   product_score = (len(found_product_keywords) / len(relevant_keywords) * 50) if relevant_keywords else 50
   ```
   - 상품별 핵심 정보 키워드가 실제 발화에 포함된 비율
   - 예: 6개 중 4개 찾음 → 33.3점

#### 고객 발화 RAG 평가 (`_evaluate_customer_rag_integration`)

**총점 100점 = 키워드 점수(50점) + 상품 코드 추출 정확도(50점)**

1. **키워드 매칭 (50점)** - RAG 평가용
   - 직원 발화와 동일한 방식
   - **주의**: 이것은 RAG 평가 점수이며, STT 점수가 아닙니다!
   
2. **상품 코드 추출 정확도 (50점)**
   ```python
   # 고객 발화에서 상품 관련 키워드 추출
   product_keywords_map = {
       "LON-CRE": ["신용대출", "신용대출한도", "한도"],
       "LON-MTG": ["주택담보", "주택담보대출", "LTV", "DTI"],
       ...
   }
   relevant_keywords = product_keywords_map.get(expected_product_code, [])
   found_product_keywords = [kw for kw in relevant_keywords if kw in customer_text]
   product_score = (len(found_product_keywords) / len(relevant_keywords) * 50) if relevant_keywords else 50
   ```

### 2.3 RAG 평가 종합 결과 (`rag_summary`)

```python
{
    "total_evaluations": 10,  # 전체 평가 수
    "average_score": 82.5,  # 평균 점수
    "employee_count": 5,  # 직원 발화 평가 수
    "customer_count": 5,  # 고객 발화 평가 수
    "employee_average": 85.0,  # 직원 발화 평균 점수
    "customer_average": 80.0,  # 고객 발화 평균 점수
    "employee_evaluations": [...],  # 직원 발화 평가 상세
    "customer_evaluations": [...]  # 고객 발화 평가 상세
}
```

---

## 📋 3. 평가서에서 RAG 테스트 해석하기

### 3.1 평가서 구조

평가서는 `SimulationFeedback` 테이블에 저장되며, 테스트 모드인 경우 다음 필드가 포함됩니다:

- `is_test_mode`: `True` (테스트 모드 여부)
- `rag_evaluations`: JSON 문자열 (모든 RAG 평가 결과)
- `rag_summary`: JSON 문자열 (RAG 평가 종합 결과)
- `stt_evaluations`: JSON 문자열 (STT 평가 결과) - 별도로 저장됨

### 3.0 STT 평가 vs RAG 평가 구분

**STT 평가** (`stt_evaluation`):
- 목적: 음성 인식 정확도 측정 (STT 성능 검증)
- 평가 항목:
  - `accuracy`: 전체 텍스트 유사도 (0-100%)
  - `keyword_recognition_rate`: 키워드 인식률 (0-100%) ← **STT 성능 검증 지표**
  - `recognized_keywords`: 인식된 키워드 목록
  - `missing_keywords`: 누락된 키워드 목록 ← **오타율/인식 실패 지표**
- **지표로 사용 가능**:
  - ✅ STT 성능 검증: `keyword_recognition_rate`로 금융 용어 인식 정확도 측정
  - ✅ 오타율 측정: `missing_keywords`로 인식 실패한 키워드 확인
  - ✅ 금융 용어별 인식률: 특정 용어(예: "LTV", "DTI")의 인식 정확도 추적

**RAG 평가** (`rag_evaluation`):
- 목적: RAG 정보 포함 여부 확인
- 평가 항목:
  - `score`: 총점 (0-100점)
  - `keyword_score`: 키워드 매칭 점수 (0-50점)
  - `rag_product_info_score`: RAG 상품 정보 점수 (0-50점)
  - `found_keywords`: 찾은 키워드 목록
  - `missing_keywords`: 누락된 키워드 목록

**차이점**:
- **STT 평가**: STT 시스템이 음성을 얼마나 정확히 텍스트로 변환했는지
- **RAG 평가**: 사용자가 RAG 정보를 얼마나 잘 포함해서 말했는지

### 3.2 평가서 조회 API

**엔드포인트**: `GET /rag-simulation/feedback/{feedback_id}`

**응답 예시**:
```json
{
    "success": true,
    "feedback": {
        "overallScore": 85.5,
        "grade": "B",
        "rag_evaluations": [
            {
                "turn_index": 5,
                "role": "employee",
                "expected_product_code": "LON-CRE",
                "evaluation": {
                    "score": 85.5,
                    "keyword_score": 45.0,
                    "rag_product_info_score": 40.5,
                    "found_keywords": ["신용대출", "한도", "신용점수", "소득"],
                    "missing_keywords": ["1.5배", "2배"],
                    "rag_info_keywords_found": ["신용대출", "한도", "소득"]
                }
            },
            ...
        ],
        "rag_summary": {
            "total_evaluations": 10,
            "average_score": 82.5,
            "employee_average": 85.0,
            "customer_average": 80.0
        }
    }
}
```

### 3.3 RAG 평가 해석 가이드

#### ✅ 좋은 평가 (80점 이상)
- **키워드 점수**: 40점 이상 (예상 키워드의 80% 이상 포함)
- **RAG 상품 정보 점수**: 40점 이상 (상품별 핵심 정보의 80% 이상 포함)
- **의미**: RAG에서 가져온 상품 정보를 정확하게 전달했음

#### ⚠️ 개선 필요 (60-80점)
- **키워드 점수**: 30-40점 (예상 키워드의 60-80% 포함)
- **RAG 상품 정보 점수**: 30-40점 (상품별 핵심 정보의 60-80% 포함)
- **의미**: 일부 정보는 전달했으나, 중요한 키워드나 상품 정보가 누락됨
- **개선 방안**: 
  - `missing_keywords` 확인하여 누락된 키워드 추가
  - `missing_information` 확인하여 누락된 상품 정보 추가

#### ❌ 개선 필요 (60점 미만)
- **키워드 점수**: 30점 미만 (예상 키워드의 60% 미만 포함)
- **RAG 상품 정보 점수**: 30점 미만 (상품별 핵심 정보의 60% 미만 포함)
- **의미**: RAG 정보를 충분히 활용하지 못했거나, 잘못된 정보를 제공했음
- **개선 방안**:
  - RAG 검색 결과를 더 자세히 확인
  - 상품별 핵심 정보를 모두 포함하도록 발화 구성

### 3.4 실제 해석 예시

#### 예시 1: 직원 발화 평가 (턴 5)
```json
{
    "turn_index": 5,
    "role": "employee",
    "expected_product_code": "LON-CRE",
    "evaluation": {
        "score": 85.5,
        "keyword_score": 45.0,  // 4개 중 3.6개 찾음 (90%)
        "rag_product_info_score": 40.5,  // 6개 중 4.86개 찾음 (81%)
        "found_keywords": ["신용대출", "한도", "신용점수", "소득"],
        "missing_keywords": ["1.5배", "2배"],
        "rag_info_keywords_found": ["신용대출", "한도", "소득"]
    }
}
```

**해석**:
- ✅ **키워드 점수 45점**: 예상 키워드 4개 중 4개 모두 포함 (100%)
- ⚠️ **RAG 상품 정보 점수 40.5점**: 상품별 핵심 정보 6개 중 약 5개 포함 (83%)
- ⚠️ **누락된 키워드**: "1.5배", "2배" (구체적인 수치 정보)
- **개선 제안**: "연소득의 1.5배에서 2배까지"와 같이 구체적인 수치를 포함하면 점수가 더 높아짐

#### 예시 2: 고객 발화 평가 (턴 5)
```json
{
    "turn_index": 5,
    "role": "customer",
    "expected_product_code": "LON-CRE",
    "evaluation": {
        "score": 75.0,
        "keyword_score": 50.0,  // 2개 모두 찾음 (100%)
        "product_extraction_score": 25.0,  // 상품 관련 키워드 4개 중 2개 찾음 (50%)
        "found_keywords": ["신용대출", "한도"],
        "missing_keywords": []
    }
}
```

**해석**:
- ✅ **키워드 점수 50점**: 예상 키워드 2개 모두 포함 (100%)
- ⚠️ **상품 코드 추출 점수 25점**: 상품 관련 키워드 4개 중 2개만 포함 (50%)
- **의미**: 고객이 "신용대출 한도"를 언급했지만, STT가 상품 코드를 정확히 추출하지 못했을 수 있음

---

## 🔧 4. 코드 참고 위치

### 주요 메서드

1. **테스트 시나리오 로드**: `_get_test_scenario_data()` (라인 562)
2. **테스트 모드 처리**: `_process_test_mode_interaction()` (라인 2789)
3. **직원 발화 RAG 평가**: `_evaluate_rag_integration()` (라인 3255)
4. **고객 발화 RAG 평가**: `_evaluate_customer_rag_integration()` (라인 3207)
5. **RAG 평가 종합**: `_summarize_rag_evaluations()` (라인 3298)

### 데이터 파일 위치

- **상품 데이터**: `backend/data/rag_sources/products/hakyung/{product_code}.jsonl`
  - 예: `LON-CRE.jsonl`, `LON-MTG.jsonl`, `DEP-MMD.jsonl`

### RAG 평가 키워드 목록 위치

RAG 평가에서 사용하는 키워드 목록은 **코드 내부에 하드코딩**되어 있습니다:

1. **직원 발화 RAG 평가** (`_evaluate_rag_integration`)
   - **위치**: `backend/app/services/rag_simulation_service.py` 라인 3272-3276
   - **변수명**: `product_info_keywords`
   - **용도**: RAG 상품 정보 포함 여부 평가 (50점)
   ```python
   product_info_keywords = {
       "DEP-MMD": ["MMDA", "입출금", "금리", "예금", "100만원", "차등"],
       "LON-MTG": ["주택담보", "LTV", "DTI", "DSR", "담보인정비율", "70%", "60%"],
       "LON-DCL": ["예금담보", "수취은행", "담보", "95%", "예금잔액"]
   }
   ```

2. **고객 발화 RAG 평가** (`_evaluate_customer_rag_integration`)
   - **위치**: `backend/app/services/rag_simulation_service.py` 라인 3224-3228
   - **변수명**: `product_keywords_map`
   - **용도**: 상품 코드 추출 정확도 평가 (50점)
   ```python
   product_keywords_map = {
       "DEP-MMD": ["MMDA", "엠엠디에이", "입출금", "예금", "적금"],
       "LON-MTG": ["주택담보", "주택담보대출", "LTV", "DTI", "DSR", "담보"],
       "LON-DCL": ["예금담보", "예금담보대출", "수취은행", "담보"]
   }
   ```

3. **상품 데이터 근거 추출** (`_extract_product_evidence`)
   - **위치**: `backend/app/services/rag_simulation_service.py` 라인 3177-3181
   - **변수명**: `key_info_keywords`
   - **용도**: 상품 데이터에서 평가 근거 추출
   ```python
   key_info_keywords = {
       "DEP-MMD": ["MMDA", "입출금", "금리", "예금", "100만원", "차등", "최소", "가입금액"],
       "LON-MTG": ["주택담보", "LTV", "DTI", "DSR", "담보인정비율", "70%", "60%", "규제"],
       "LON-DCL": ["예금담보", "수취은행", "담보", "95%", "예금잔액", "초저금리"]
   }
   ```

**⚠️ 중요**: 
- **이 키워드 목록들은 코드에 하드코딩되어 있습니다.** 개발자가 실제 상품 데이터(`backend/data/rag_sources/products/hakyung/*.jsonl`)를 분석하여 수동으로 정의한 것입니다.
- 예를 들어, `LON-MTG.jsonl` 파일을 보면 실제로 LTV, DTI, DSR 정보가 포함되어 있어, 이를 기반으로 키워드를 선정한 것으로 보입니다.
- 새로운 상품을 추가하거나 키워드를 수정하려면 코드를 직접 수정해야 합니다.
- 각 상품별로 키워드 목록이 다르므로, 상품 추가 시 해당 상품의 키워드 목록도 함께 추가해야 합니다.
- **한 문장에 모든 키워드를 포함할 필요는 없습니다.** 직원 발화 전체(`employee_text`)에서 키워드를 찾으므로, 여러 문장에 걸쳐 설명해도 됩니다.

### 4.3 하드코딩된 항목 목록

현재 코드에 하드코딩되어 있는 항목들:

1. **제품별 키워드 매핑** (`product_keywords`)
   - 위치: `backend/app/services/product_knowledge_service.py` 라인 404-427
   - 용도: 일반 모드에서 제품 코드 자동 감지

2. **상품별 중요 정보 카테고리** (`product_category_priority`)
   - 위치: `backend/app/services/product_knowledge_service.py` 라인 430-453
   - 용도: 일반 모드에서 정보 카테고리 우선순위 결정

3. **정보 카테고리 패턴** (`category_patterns`)
   - 위치: `backend/app/services/product_knowledge_service.py` 라인 456-475
   - 용도: 일반 모드에서 정규식 패턴으로 정보 추출

4. **RAG 평가용 제품 정보 키워드** (`product_info_keywords`)
   - 위치: `backend/app/services/rag_simulation_service.py` 라인 3272-3276
   - 용도: 테스트 모드 RAG 평가 (직원 발화)

5. **고객 발화 평가용 키워드** (`product_keywords_map`)
   - 위치: `backend/app/services/rag_simulation_service.py` 라인 3224-3228
   - 용도: 테스트 모드 RAG 평가 (고객 발화)

6. **상품 데이터 근거 추출용 키워드** (`key_info_keywords`)
   - 위치: `backend/app/services/rag_simulation_service.py` 라인 3177-3181
   - 용도: 상품 데이터에서 평가 근거 추출

### 4.4 자동화 가능성

**현재 상태**: 모든 키워드와 패턴이 하드코딩되어 있어, 새 상품 추가 시 수동으로 코드를 수정해야 합니다.

**자동화 방법 제안**:

#### 방법 1: 제품 데이터 파일에서 자동 추출

**장점**:
- 제품 데이터(`*.jsonl`)의 `subsection_title`을 분석하여 카테고리 자동 추출
- 제품명, 상품 코드에서 키워드 자동 생성
- 새 상품 추가 시 자동으로 키워드 생성

**구현 예시**:
```python
def auto_extract_categories_from_product_data(product_code: str) -> List[str]:
    """제품 데이터에서 카테고리 자동 추출"""
    chunks = load_product_chunks(product_code)
    categories = set()
    
    # subsection_title에서 카테고리 추출
    for chunk in chunks:
        subsection = chunk.get("subsection_title", "")
        # "대출 금리" → "금리"
        # "대출 한도" → "한도"
        # "LTV" → "LTV"
        if "금리" in subsection or "이자율" in subsection:
            categories.add("금리")
        if "한도" in subsection:
            categories.add("한도")
        # ... 패턴 매칭
    
    return list(categories)
```

#### 방법 2: LLM 기반 자동 생성

**장점**:
- 제품 데이터를 LLM에 제공하여 핵심 키워드 자동 추출
- 컨텍스트를 이해하여 더 정확한 키워드 생성

**구현 예시**:
```python
def generate_keywords_with_llm(product_code: str, product_data: List[Dict]) -> Dict:
    """LLM을 사용하여 키워드 자동 생성"""
    prompt = f"""
    제품 코드: {product_code}
    제품 데이터: {product_data}
    
    위 제품의 핵심 정보를 나타내는 키워드 목록을 생성하세요.
    - 제품명 관련 키워드
    - 주요 정보 카테고리 (금리, 한도, 기간 등)
    - 핵심 수치 정보 (예: "70%", "100만원")
    """
    # LLM 호출하여 키워드 생성
    return llm_response
```

#### 방법 3: 통계적 방법 (TF-IDF, 키워드 빈도)

**장점**:
- 제품 데이터에서 자주 언급되는 용어를 통계적으로 추출
- 객관적이고 재현 가능

**구현 예시**:
```python
def extract_keywords_by_frequency(product_code: str, top_n: int = 10) -> List[str]:
    """제품 데이터에서 빈도 기반 키워드 추출"""
    chunks = load_product_chunks(product_code)
    all_text = " ".join([chunk.get("text", "") for chunk in chunks])
    
    # TF-IDF 또는 단어 빈도 분석
    keywords = analyze_word_frequency(all_text, top_n)
    return keywords
```

#### 방법 4: 하이브리드 접근 (권장)

**구현 전략**:
1. **초기 생성**: 제품 데이터 파일에서 자동 추출
2. **검증 및 보정**: LLM을 사용하여 키워드 품질 검증
3. **수동 검토**: 생성된 키워드를 개발자가 검토하고 수정
4. **캐싱**: 검증된 키워드를 JSON 파일로 저장하여 재사용

**예시 구조**:
```json
// backend/data/product_keywords_cache.json
{
  "LON-MTG": {
    "product_keywords": ["주택담보대출", "주택담보", "주택 담보 대출"],
    "categories": ["금리", "한도", "기간", "LTV", "DTI", "DSR", "상환방식"],
    "info_keywords": ["주택담보", "LTV", "DTI", "DSR", "담보인정비율", "70%", "60%"],
    "auto_generated": true,
    "last_updated": "2025-01-15"
  }
}
```

**자동화 구현 시 고려사항**:
- ✅ 제품 데이터 파일이 구조화되어 있어 자동 추출 가능
- ⚠️ 정규식 패턴은 수동 정의가 필요할 수 있음 (언어 패턴이 복잡함)
- ⚠️ 키워드 품질 검증이 필요 (노이즈 제거)
- ⚠️ 기존 하드코딩된 키워드와의 호환성 유지 필요

---

## 🔄 6. 테스트 모드 vs 일반 모드 비교

### 6.1 제품 코드와 키워드 추출 방식

| 구분 | 테스트 모드 | 일반 모드 |
|------|------------|----------|
| **제품 코드 추출** | 테스트 시나리오에서 미리 정의 | `ProductKnowledgeService`가 자동 추출 |
| **키워드 추출** | 테스트 시나리오에서 미리 정의 | `ProductKnowledgeService`가 자동 추출 |
| **평가 방식** | RAG 평가 (예상값과 비교) | 제품 지식 정확도 검증 (RAG 데이터와 비교) |
| **평가 목적** | RAG 연동 평가 (50점) | 지식 역량 평가 (상품 정확성) |

### 6.2 일반 모드에서의 제품 코드/키워드 추출

일반 모드에서는 **`ProductKnowledgeService.extract_product_facts_from_conversation()`** 메서드가 자동으로 추출합니다:

#### 1. 제품 코드 자동 감지

**위치**: `backend/app/services/product_knowledge_service.py` 라인 404-427

```python
# 제품별 키워드 매핑 (자동 감지용)
product_keywords = {
    "DEP-TIM": ["정기예금", "정기 예금", "만기예금"],
    "DEP-MMD": ["입출금자유", "자유통장", "입출금 통장", "MMDA", "MMA"],
    "LON-MTG": ["주택담보대출", "주택담보", "주택 담보 대출"],
    "LON-CRE": ["신용대출", "무담보대출", "직장인 대출"],
    "LON-DCL": ["예금담보대출", "예금담보"],
    ...
}

# 직원 발화에서 제품 감지
for product_code, keywords in product_keywords.items():
    if any(keyword in utterance for keyword in keywords):
        mentioned_products.append(product_code)
```

**예시**:
- 직원 발화: "신용대출 한도는..."
- 자동 감지: `product_code = "LON-CRE"` (또는 "LON-UNS")

#### 2. 정보 카테고리 자동 추출

**위치**: `backend/app/services/product_knowledge_service.py` 라인 456-475

```python
# 정보 카테고리 패턴 (정규식)
category_patterns = {
    "금리": [r"금리\s*(?:는|:)?\s*([\d\.]+)%?", r"이자율?\s*([\d\.]+)%?", ...],
    "한도": [r"한도\s*(?:는|:)?\s*([\d,]+)원?", r"최대\s*([\d,]+)원?", ...],
    "가입금액": [r"가입금액\s*(?:은|는)?\s*([\d,]+)원?", r"최소\s*가입\s*([\d,]+)원?", ...],
    "LTV": [r"LTV\s*(?:는|:)?\s*([\d]+)%?", r"담보인정비율\s*(?:은|는)?\s*([\d]+)%?", ...],
    ...
}
```

**⚠️ 중요**:
- **정보 카테고리 패턴도 코드에 하드코딩되어 있습니다.** 개발자가 실제 상품 데이터를 분석하여 수동으로 정의한 것입니다.
- **상품별 중요 정보 카테고리** (`product_category_priority`, 라인 430-453)도 하드코딩되어 있습니다:
  ```python
  "LON-MTG": ["금리", "한도", "기간", "LTV", "DTI", "DSR", "상환방식", "우대금리", "필요서류"]
  ```
- 실제 `LON-MTG.jsonl` 데이터를 보면 이러한 정보들이 실제로 존재합니다.
- **한 문장에 모든 정보를 포함할 필요는 없습니다.** 직원 발화 전체에서 정보를 추출하므로, 여러 문장에 걸쳐 설명해도 됩니다.

**예시**:
- 직원 발화: "신용대출 한도는 고객님의 신용점수와 소득에 따라 다르며 일반적으로 연소득의 1.5배에서 2배까지 가능합니다"
- 자동 추출:
  - `product_code`: "LON-CRE" (또는 "LON-UNS")
  - `category`: "한도"
  - `claim`: "한도는 ... 1.5배에서 2배까지"
  - `keywords`: ["신용대출", "한도", "신용점수", "소득", "1.5배", "2배"] (claim에서 자동 추출)

#### 3. 제품 지식 정확도 검증

**위치**: `backend/app/services/rag_simulation_service.py` 라인 2029

```python
# 일반 모드: 제품 지식 정확도 자동 검증
knowledge_verification_result = self.product_knowledge_service.batch_verify_conversation(
    conversation_history,
    use_llm=True  # LLM 검증 포함
)
```

**검증 과정**:
1. **사실 추출**: `extract_product_facts_from_conversation()` - 제품 코드, 카테고리, claim 자동 추출
2. **사실 검증**: `verify_fact_accuracy()` - RAG 데이터와 비교하여 정확성 검증
3. **정확도 계산**: 정확한 정보 개수 / 전체 정보 개수

**결과 예시**:
```python
{
    "accuracy_rate": 0.85,  # 85% 정확도
    "total_claims": 10,
    "accurate_claims": 8,
    "inaccurate_claims": 2,
    "verifications": [
        {
            "claim": "신용대출 한도는 연소득의 1.5배에서 2배까지",
            "product_code": "LON-CRE",
            "category": "한도",
            "is_accurate": True,
            "ground_truth": "신용대출 한도는 연소득의 1.5배~2배까지 가능",
            "similarity_score": 0.92
        },
        ...
    ]
}
```

### 6.3 테스트 모드 vs 일반 모드 비교 요약

| 항목 | 테스트 모드 | 일반 모드 |
|------|------------|----------|
| **제품 코드** | 테스트 시나리오에서 정의 | 자동 추출 (제품 키워드 매핑) |
| **키워드** | 테스트 시나리오에서 정의 | 자동 추출 (정규식 패턴) |
| **평가 방식** | RAG 평가 (예상값과 비교) | 제품 지식 정확도 검증 (RAG 데이터와 비교) |
| **평가 결과** | `rag_evaluations`, `rag_summary` | `knowledge_verification_result` (지식 점수에 반영) |
| **평가 목적** | RAG 연동 평가 (50점) | 지식 역량 평가 (상품 정확성) |

### 6.4 일반 모드에서의 평가 흐름

```
일반 모드 대화
    ↓
직원 발화: "신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다"
    ↓
[ProductKnowledgeService]
1. 제품 코드 자동 감지: "신용대출" → "LON-CRE"
2. 카테고리 자동 추출: "한도" (정규식 패턴 매칭)
3. Claim 추출: "한도는 ... 1.5배에서 2배까지"
    ↓
[RAG 데이터 검색]
- product_code: "LON-CRE"
- category: "한도"
- RAG 데이터에서 관련 청크 검색
    ↓
[정확성 검증]
- Claim vs RAG 데이터 비교
- 숫자 정확도 검증 (1.5배, 2배)
- 의미적 유사도 계산
- LLM 검증 (선택)
    ↓
[지식 점수 반영]
- 정확도 85% → 지식 점수 85점 (기본)
- GPT-4 피드백 생성 시 정확도 정보 포함
```

---

## 💡 5. 실전 팁

### 5.1 키워드 선택 가이드

- **핵심 용어 우선**: 제품명, 주요 기능, 수치 정보
- **금융 용어 포함**: STT 평가를 위해 전문 용어 포함
  - **STT 성능 검증**: 금융 용어 인식 정확도 측정에 활용
  - **오타율 측정**: 누락된 키워드로 인식 실패율 확인
- **구체적 수치**: "1.5배", "2배", "70%", "60%" 등
  - **STT 성능 검증**: 숫자와 단위 인식 정확도 측정에 활용

### 5.4 키워드 매칭을 STT 성능 검증 지표로 활용하기

**키워드 매칭 결과는 STT 성능 검증 지표로 활용할 수 있습니다:**

1. **키워드 인식률 (`keyword_recognition_rate`)**
   ```python
   # STT 평가 결과
   {
       "keyword_recognition_rate": 83.3,  # 6개 중 5개 인식 = 83.3%
       "recognized_keywords": ["신용대출", "한도", "신용점수", "소득", "1.5배"],
       "missing_keywords": ["2배"]  # STT가 인식하지 못한 키워드
   }
   ```
   - **의미**: STT가 금융 용어를 얼마나 정확히 인식했는지
   - **활용**: STT 성능 개선 지표, 금융 용어별 인식률 추적

2. **누락된 키워드 분석**
   - `missing_keywords`를 분석하여 STT가 자주 인식 실패하는 용어 파악
   - 예: "LTV", "DTI" 같은 약어가 자주 누락되면 → STT 모델 개선 필요

3. **오타율 측정**
   - 전체 키워드 대비 누락된 키워드 비율 = 오타율/인식 실패율
   - 예: 6개 중 1개 누락 = 16.7% 오타율

### 5.2 product_code 설정 가이드

- **특정 제품 언급 시**: 해당 제품 코드 설정 (예: "LON-CRE")
- **일반적인 대화**: `None` 설정
- **여러 제품 언급**: 가장 중요한 제품 코드 하나만 설정

### 5.3 RAG 평가 개선 방법

1. **키워드 점수 개선**: `missing_keywords` 확인하여 누락된 키워드 추가
2. **RAG 상품 정보 점수 개선**: `missing_information` 확인하여 누락된 상품 정보 추가
3. **상품 데이터 확인**: `backend/data/rag_sources/products/hakyung/` 디렉토리에서 실제 상품 데이터 확인

---

## 📚 관련 문서

- [지식 평가 가이드](./KNOWLEDGE_EVALUATION_GUIDE.md)
- [시뮬레이션 역량 평가 가이드](./SIMULATION_COMPETENCY_EVALUATION_GUIDE.md)
- [RAG 디버그 체크리스트](./RAG_DEBUG_CHECKLIST.md)

