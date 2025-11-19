# 테스트 모드 RAG 테스트 결과 섹션 형식

## 📋 개요

테스트 모드에서 대화 종료 시 반환되는 RAG 테스트 결과 섹션의 구조입니다.

## 🔄 반환 구조

### 전체 응답 구조

```json
{
  "transcribed_text": "",
  "customer_response": "",
  "customer_audio": null,
  "feedback": "테스트 시나리오가 완료되었습니다.",
  "conversation_phase": "completed",
  "session_score": 0,
  "conversation_history": [...],
  "end_signal": true,
  "stt_evaluation": {...},  // 턴별 STT 평가 결과
  "knowledge_verification_result": {...},  // 일반 모드와 동일한 검증 결과
  "knowledge_evaluation_result": {...},  // 지식 평가서 항목 (검증용)
  "product_accuracy_info": "...",  // LLM 프롬프트용 정보 (일반 모드와 동일)
  "test_completed": true
}
```

---

## 📊 1. STT 평가 결과 (`stt_evaluation`)

### 구조
```json
{
  "overall_accuracy": 92.5,  // 전체 평균 정확도 (%)
  "average_keyword_recognition": 88.0,  // 평균 키워드 인식률 (%)
  "total_evaluations": 10,  // 총 평가 수
  "detailed_evaluations": [
    {
      "transcribed": "신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다",
      "expected": "신용대출 한도는 고객님의 신용점수와 소득에 따라 다르며 일반적으로 연소득의 1.5배에서 2배까지 가능합니다",
      "accuracy": 85.2,  // 텍스트 유사도 (%)
      "keyword_recognition_rate": 90.0,  // 키워드 인식률 (%)
      "recognized_keywords": ["신용대출", "한도", "1.5배", "2배"],
      "missing_keywords": ["신용점수", "소득"]
    },
    ...
  ]
}
```

### 용도
- **STT 검증**: 음성 인식 정확도 확인
- **키워드 인식률**: 금융 용어 인식 성능 확인
- **오타율 분석**: 누락된 키워드로 오타율 파악

---

## 🔍 2. 지식 검증 결과 (`knowledge_verification_result`)

### 구조
```json
{
  "facts": [
    {
      "claim": "신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다",
      "full_utterance": "신용대출 한도는 고객님의 신용점수와 소득에 따라 다르며 일반적으로 연소득의 1.5배에서 2배까지 가능합니다",
      "product_codes": ["LON-CRE"],
      "category": "한도",
      "matched_value": "1.5배"
    },
    ...
  ],
  "verifications": [
    {
      "claim": "신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다",
      "ground_truth": "신용대출 한도는 연소득의 1.5배~2배까지 가능합니다",
      "is_accurate": true,  // 정확성 여부
      "similarity_score": 0.95,  // 의미적 유사도 (0.0~1.0)
      "product_code": "LON-CRE",
      "category": "한도",
      "verification_method": "llm",  // 최종 판단에 사용된 방법: "llm", "semantic", "keyword"
      "llm_reasoning": "사용자 주장과 제품 지식 베이스 정보가 의미적으로 동일합니다. '1.5배에서 2배'와 '1.5배~2배'는 동일한 의미입니다.",
      "full_utterance": "신용대출 한도는 고객님의 신용점수와 소득에 따라 다르며 일반적으로 연소득의 1.5배에서 2배까지 가능합니다"
    },
    {
      "claim": "금리는 연 3.5%입니다",
      "ground_truth": "신용대출 기본금리는 연 2.15%입니다",
      "is_accurate": false,  // 부정확
      "similarity_score": 0.45,
      "product_code": "LON-CRE",
      "category": "금리",
      "verification_method": "llm",
      "llm_reasoning": "사용자가 말한 금리(3.5%)와 실제 제품 금리(2.15%)가 다릅니다. 부정확한 정보입니다.",
      "full_utterance": "신용대출 금리는 연 3.5%입니다"
    },
    ...
  ],
  "accuracy_rate": 0.85,  // 정확도 (85%)
  "total_claims": 10,  // 총 사실 수
  "accurate_claims": 8,  // 정확한 사실 수
  "inaccurate_claims": 2,  // 부정확한 사실 수
  "details": {
    "by_category": {
      "금리": {"total": 3, "accurate": 2, "accuracy_rate": 0.67},
      "한도": {"total": 4, "accurate": 4, "accuracy_rate": 1.0},
      "기간": {"total": 3, "accurate": 2, "accuracy_rate": 0.67}
    },
    "by_product": {
      "LON-CRE": {"total": 10, "accurate": 8, "accuracy_rate": 0.8},
      "LON-MTG": {"total": 5, "accurate": 5, "accuracy_rate": 1.0}
    }
  },
  "verification_methods": {
    "llm": 8,  // LLM 검증 사용 횟수
    "semantic": 2,  // 의미적 유사도 검증 사용 횟수
    "keyword": 0  // 키워드 매칭 검증 사용 횟수
  }
}
```

### 검증 방법 (`verification_method`) 설명

**중요**: `verification_method`는 **최종 판단에 사용된 방법**을 나타냅니다.

검증 프로세스:
1. **1단계 (항상 수행)**: Keyword Matching + Semantic Similarity
   - 키워드 기반 청크 검색
   - 의미적 유사도 계산
   - 숫자 정확도 비교
   - 휴리스틱 정확도 판단 (`is_accurate_heuristic`)

2. **2단계 (선택적)**: LLM Verification
   - `use_llm=True`이고 LLM이 성공하면 → LLM 결과를 최종 판단으로 사용
   - LLM이 없거나 실패하면 → 1단계의 휴리스틱 결과를 최종 판단으로 사용

**`verification_method` 값**:
- `"llm"`: LLM 검증이 성공하여 LLM 결과를 최종 판단으로 사용한 경우
- `"semantic"`: LLM이 없거나 실패하여 휴리스틱 결과를 사용했고, 임베딩 기반 유사도를 사용한 경우
- `"keyword"`: LLM이 없거나 실패하여 휴리스틱 결과를 사용했고, SequenceMatcher 기반 유사도를 사용한 경우

**예시**:
```python
# LLM이 성공한 경우
verification_method = "llm"  # LLM이 최종 판단

# LLM이 없거나 실패한 경우
if use_embedding:
    verification_method = "semantic"  # 임베딩 기반 유사도로 최종 판단
else:
    verification_method = "keyword"  # SequenceMatcher로 최종 판단
```

### 용도
- **지식 검증 로직 확인**: `batch_verify_conversation()` 정상 동작 확인
- **검증 단계 확인**: 1단계(키워드+의미적 유사도)는 항상 수행, 2단계(LLM)는 선택적
- **최종 판단 방법 확인**: 어떤 방법으로 최종 판단했는지 확인
- **정확도 계산 확인**: `accuracy_rate = accurate_claims / total_claims`
- **카테고리별/제품별 정확도 분석**: 어떤 카테고리나 제품에서 오류가 많은지 확인

---

## 📝 3. 지식 평가서 항목 (`knowledge_evaluation_result`)

### 구조
```json
{
  "accuracy_rate": 0.85,  // 정확도 (85%)
  "knowledge_score": 85,  // 지식 점수 (일반 모드와 동일한 점수 산정)
  "total_claims": 10,  // 총 사실 수
  "accurate_claims": 8,  // 정확한 사실 수
  "inaccurate_claims": 2,  // 부정확한 사실 수
  "product_accuracy_info": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🔍 **제품 지식 자동 검증 결과** (객관적 데이터 - 반드시 정확히 반영하세요)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n- 총 제품 정보 언급: 10개\n- 정확한 정보: 8개\n- 부정확한 정보: 2개\n- 정확도: 85.0%\n- 검증 방법: {'llm': 8, 'semantic': 2}\n\n✅ **정확한 정보 목록 (반드시 잘한 점에 언급):**\n• '신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다' (정확함)\n• '최소 가입금액은 100만원입니다' (정확함)\n...\n\n⚠️ **부정확한 정보 목록 (개선점에만 언급):**\n• '금리는 연 3.5%입니다' → 실제: 신용대출 기본금리는 연 2.15%입니다\n• '한도는 최대 5천만원입니다' → 실제: 신용대출 한도는 연소득의 1.5배~2배까지 가능합니다\n...\n\n💡 **검증 상세 분석 (LLM reasoning):**\n• 신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다: 사용자 주장과 제품 지식 베이스 정보가 의미적으로 동일합니다.\n• 금리는 연 3.5%입니다: 사용자가 말한 금리(3.5%)와 실제 제품 금리(2.15%)가 다릅니다. 부정확한 정보입니다.\n...\n\n💡 **지식 점수 평가 및 피드백 작성 가이드:**\n- 정확도 85.0% → 기본 점수 85점 (오류는 이미 정확도에 반영됨)\n- ⚠️ 오류 개수는 점수 계산에 사용하지 말고, 피드백 작성 시에만 참고하세요\n- ⚠️ 불확실한 표현(\"같아요\", \"모르겠\" 등)은 전달력(자신감) 평가에서 다루므로 지식 점수에는 반영하지 않습니다\n- ⚠️ **표현의 명확성(단위 명시 등)은 전달력에서 평가하므로, 지식 피드백에서는 상품 정보의 정확성만 언급하세요**\n\n🚨 **중요 규칙 (반드시 준수):**\n1. **정확한 정보 목록에 있는 claim은 반드시 잘한 점에만 언급하고, 개선점에 절대 포함하지 마세요.**\n2. **부정확한 정보 목록에 있는 claim만 개선점에 언급하세요.**\n3. **같은 claim이 잘한 점과 개선점에 동시에 나타나면 안 됩니다. (모순 금지)**\n4. **실제 대화 내용을 정확히 참조하세요. 대화에서 \"100만원\"이라고 정확히 말했다면, \"최소 100\"이라는 오류로 인식하지 마세요.**\n5. **제품 지식 자동 검증 결과가 정확한 정보로 판단했다면, 그것을 신뢰하고 잘한 점에 언급하세요.**\n",
  "verifications": [...]  // knowledge_verification_result의 verifications와 동일
}
```

### 용도
- **지식 평가서 항목 생성 검증**: 일반 모드와 동일한 구조로 평가서 항목 생성 가능 여부 확인
- **점수 산정 검증**: `knowledge_score = accuracy_rate * 100` 확인
- **LLM 프롬프트 검증**: `product_accuracy_info`가 일반 모드와 동일한 형식인지 확인

---

## 📄 4. LLM 프롬프트용 정보 (`product_accuracy_info`)

### 구조 (마크다운 형식 문자열)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **제품 지식 자동 검증 결과** (객관적 데이터 - 반드시 정확히 반영하세요)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 총 제품 정보 언급: 10개
- 정확한 정보: 8개
- 부정확한 정보: 2개
- 정확도: 85.0%
- 검증 방법: {'llm': 8, 'semantic': 2}

✅ **정확한 정보 목록 (반드시 잘한 점에 언급):**
• '신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다' (정확함)
• '최소 가입금액은 100만원입니다' (정확함)
• '기본금리는 연 2.15%입니다' (정확함)
• '상환기간은 최대 5년입니다' (정확함)
• '신용등급에 따라 금리가 달라집니다' (정확함)

⚠️ **위 정확한 정보 목록의 claim은 모두 정확한 정보입니다.**
⚠️ **위 목록에 있는 claim은 개선점에 절대 포함하지 마세요.**
⚠️ **위 목록에 있는 claim은 잘한 점에만 구체적으로 언급하세요.**

⚠️ **부정확한 정보 목록 (개선점에만 언급):**
• '금리는 연 3.5%입니다' → 실제: 신용대출 기본금리는 연 2.15%입니다
• '한도는 최대 5천만원입니다' → 실제: 신용대출 한도는 연소득의 1.5배~2배까지 가능합니다

⚠️ **위 부정확한 정보 목록의 claim만 개선점에 언급하세요.**
⚠️ **위 목록에 없는 claim은 개선점에 포함하지 마세요.**
⚠️ **정확한 정보 목록에 있는 claim과 부정확한 정보 목록에 있는 claim이 겹치면 안 됩니다.**

💡 **검증 상세 분석 (LLM reasoning):**
• 신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다: 사용자 주장과 제품 지식 베이스 정보가 의미적으로 동일합니다.
• 금리는 연 3.5%입니다: 사용자가 말한 금리(3.5%)와 실제 제품 금리(2.15%)가 다릅니다. 부정확한 정보입니다.
• 최소 가입금액은 100만원입니다: 사용자 주장과 제품 지식 베이스 정보가 일치합니다.
• 한도는 최대 5천만원입니다: 사용자가 말한 한도(5천만원)는 실제 제품 한도(연소득의 1.5배~2배)와 다릅니다. 부정확한 정보입니다.
• 기본금리는 연 2.15%입니다: 사용자 주장과 제품 지식 베이스 정보가 정확히 일치합니다.

💡 **지식 점수 평가 및 피드백 작성 가이드:**
- 정확도 85.0% → 기본 점수 85점 (오류는 이미 정확도에 반영됨)
- ⚠️ 오류 개수는 점수 계산에 사용하지 말고, 피드백 작성 시에만 참고하세요
- ⚠️ 불확실한 표현("같아요", "모르겠" 등)은 전달력(자신감) 평가에서 다루므로 지식 점수에는 반영하지 않습니다
- ⚠️ **표현의 명확성(단위 명시 등)은 전달력에서 평가하므로, 지식 피드백에서는 상품 정보의 정확성만 언급하세요**

🚨 **중요 규칙 (반드시 준수):**
1. **정확한 정보 목록에 있는 claim은 반드시 잘한 점에만 언급하고, 개선점에 절대 포함하지 마세요.**
2. **부정확한 정보 목록에 있는 claim만 개선점에 언급하세요.**
3. **같은 claim이 잘한 점과 개선점에 동시에 나타나면 안 됩니다. (모순 금지)**
4. **실제 대화 내용을 정확히 참조하세요. 대화에서 "100만원"이라고 정확히 말했다면, "최소 100"이라는 오류로 인식하지 마세요.**
5. **제품 지식 자동 검증 결과가 정확한 정보로 판단했다면, 그것을 신뢰하고 잘한 점에 언급하세요.**
```

### 용도
- **LLM 프롬프트 검증**: 일반 모드와 동일한 형식으로 LLM 프롬프트에 포함 가능한지 확인
- **평가서 생성 검증**: 이 정보를 기반으로 일반 모드와 동일한 방식으로 평가서 생성 가능한지 확인

---

## 📊 전체 결과 예시

### 성공 케이스 (제품 정보 정확)

```json
{
  "stt_evaluation": {
    "overall_accuracy": 95.0,
    "average_keyword_recognition": 92.0,
    "total_evaluations": 8
  },
  "knowledge_verification_result": {
    "accuracy_rate": 1.0,  // 100% 정확
    "total_claims": 5,
    "accurate_claims": 5,
    "inaccurate_claims": 0,
    "verifications": [
      {
        "claim": "신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다",
        "is_accurate": true,
        "verification_method": "llm",
        "llm_reasoning": "정확한 정보입니다."
      },
      ...
    ]
  },
  "knowledge_evaluation_result": {
    "accuracy_rate": 1.0,
    "knowledge_score": 100,  // 만점
    "total_claims": 5,
    "accurate_claims": 5,
    "inaccurate_claims": 0
  },
  "product_accuracy_info": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🔍 **제품 지식 자동 검증 결과**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n- 총 제품 정보 언급: 5개\n- 정확한 정보: 5개\n- 부정확한 정보: 0개\n- 정확도: 100.0%\n\n✅ **정확한 정보 목록:**\n• '신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다' (정확함)\n...\n\n⚠️ **부정확한 정보: 없음**\n→ 개선점 섹션은 생략하거나 \"제공한 모든 상품 정보가 정확합니다\"와 같이 간단히 언급하세요.\n..."
}
```

### 오류 케이스 (제품 정보 부정확)

```json
{
  "stt_evaluation": {
    "overall_accuracy": 90.0,
    "average_keyword_recognition": 85.0,
    "total_evaluations": 8
  },
  "knowledge_verification_result": {
    "accuracy_rate": 0.6,  // 60% 정확
    "total_claims": 10,
    "accurate_claims": 6,
    "inaccurate_claims": 4,
    "verifications": [
      {
        "claim": "금리는 연 3.5%입니다",
        "is_accurate": false,
        "ground_truth": "신용대출 기본금리는 연 2.15%입니다",
        "verification_method": "llm",
        "llm_reasoning": "사용자가 말한 금리(3.5%)와 실제 제품 금리(2.15%)가 다릅니다."
      },
      ...
    ]
  },
  "knowledge_evaluation_result": {
    "accuracy_rate": 0.6,
    "knowledge_score": 60,  // 60점
    "total_claims": 10,
    "accurate_claims": 6,
    "inaccurate_claims": 4
  },
  "product_accuracy_info": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🔍 **제품 지식 자동 검증 결과**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n- 총 제품 정보 언급: 10개\n- 정확한 정보: 6개\n- 부정확한 정보: 4개\n- 정확도: 60.0%\n\n✅ **정확한 정보 목록:**\n• '신용대출 한도는 연소득의 1.5배에서 2배까지 가능합니다' (정확함)\n...\n\n⚠️ **부정확한 정보 목록:**\n• '금리는 연 3.5%입니다' → 실제: 신용대출 기본금리는 연 2.15%입니다\n• '한도는 최대 5천만원입니다' → 실제: 신용대출 한도는 연소득의 1.5배~2배까지 가능합니다\n...\n..."
}
```

---

## 🔍 검증 가능 항목

### 1. STT 검증
- ✅ 턴별 STT 정확도 확인
- ✅ 키워드 인식률 확인
- ✅ 누락된 키워드로 오타율 파악

### 2. 지식 파트 점수 산정 로직 검증
- ✅ `batch_verify_conversation()` 정상 동작 확인
- ✅ 3단계 검증 수행 확인 (키워드 → 의미적 유사도 → LLM)
- ✅ 정확도 계산 확인: `accuracy_rate = accurate_claims / total_claims`
- ✅ 지식 점수 산정 확인: `knowledge_score = accuracy_rate * 100`
- ✅ 카테고리별/제품별 정확도 분석

### 3. 평가서 항목 생성 검증
- ✅ `product_accuracy_info` 형식 확인 (일반 모드와 동일)
- ✅ 정확한 정보/부정확한 정보 목록 확인
- ✅ LLM 프롬프트에 포함 가능한 구조 확인
- ✅ 일반 모드와 동일한 방식으로 평가서 생성 가능 여부 확인

---

## 📌 주요 특징

1. **일반 모드와 동일한 로직**: `batch_verify_conversation()` 사용
2. **정확도 기반 점수**: `knowledge_score = accuracy_rate * 100`
3. **상세한 검증 정보**: 각 사실에 대한 검증 결과와 LLM reasoning 포함
4. **카테고리별/제품별 분석**: 어떤 영역에서 오류가 많은지 파악 가능
5. **평가서 생성 준비**: `product_accuracy_info`로 일반 모드와 동일한 평가서 생성 가능

---

## 💡 활용 방법

### 프론트엔드에서 표시 예시

```typescript
// STT 평가 결과
<div>
  <h3>STT 평가 결과</h3>
  <p>전체 정확도: {stt_evaluation.overall_accuracy}%</p>
  <p>키워드 인식률: {stt_evaluation.average_keyword_recognition}%</p>
</div>

// 지식 평가 결과
<div>
  <h3>지식 평가 결과</h3>
  <p>정확도: {knowledge_evaluation_result.accuracy_rate * 100}%</p>
  <p>지식 점수: {knowledge_evaluation_result.knowledge_score}점</p>
  <p>정확한 정보: {knowledge_evaluation_result.accurate_claims}개</p>
  <p>부정확한 정보: {knowledge_evaluation_result.inaccurate_claims}개</p>
  
  <h4>정확한 정보</h4>
  <ul>
    {knowledge_verification_result.verifications
      .filter(v => v.is_accurate)
      .map(v => <li>{v.claim}</li>)
    }
  </ul>
  
  <h4>부정확한 정보</h4>
  <ul>
    {knowledge_verification_result.verifications
      .filter(v => !v.is_accurate)
      .map(v => (
        <li>
          {v.claim} → 실제: {v.ground_truth}
          <br />
          <small>이유: {v.llm_reasoning}</small>
        </li>
      ))
    }
  </ul>
</div>
```

---

## ✅ 결론

테스트 모드의 RAG 테스트 결과는 다음과 같이 구성됩니다:

1. **STT 평가**: 턴별 음성 인식 정확도
2. **지식 검증 결과**: 일반 모드와 동일한 `batch_verify_conversation()` 결과
3. **지식 평가서 항목**: 검증용 평가서 구조
4. **LLM 프롬프트 정보**: 일반 모드와 동일한 형식의 프롬프트 정보

이를 통해 **STT 검증**과 **지식 파트 점수 산정 로직 검증**을 모두 수행할 수 있습니다.

