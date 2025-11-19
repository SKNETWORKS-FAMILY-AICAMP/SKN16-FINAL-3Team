# 테스트 모드 코드 구조 분석

## 📋 테스트 모드의 목적

1. **STT 검증**: 음성 인식 정확도 검증
2. **지식 파트 점수 산정 로직 검증**: 평가서 세부 역량 중 지식 파트의 점수 산정 로직 검증

## 🔍 현재 구조 분석

### 일반 모드의 지식 파트 점수 산정 로직

```python
# 1단계: 제품 지식 정확도 자동 검증
knowledge_verification_result = self.product_knowledge_service.batch_verify_conversation(
    conversation_history,  # 전체 대화를 한 번에 처리
    use_llm=True
)

# 결과 구조
{
    "accuracy_rate": 0.85,  # 정확도 (85%)
    "total_claims": 10,     # 총 사실 수
    "accurate_claims": 8,   # 정확한 사실 수
    "inaccurate_claims": 2, # 부정확한 사실 수
    "verifications": [      # 각 사실의 검증 결과
        {
            "claim": "금리는 연 2.5%입니다",
            "is_accurate": True,
            "verification_method": "llm",  # 3단계 검증 (키워드 → 의미적 유사도 → LLM)
            "llm_reasoning": "..."
        },
        ...
    ]
}

# 2단계: LLM 평가 프롬프트에 정확도 정보 포함
evaluation_prompt = f"""
...
정확도: {accuracy_rate:.1%}
정확한 정보 목록: ...
부정확한 정보 목록: ...
...
"""

# 3단계: LLM이 정확도를 기반으로 지식 점수 산정
# 정확도 85% → 기본 점수 85점 (오류는 이미 정확도에 반영됨)
```

**핵심 특징:**
- `batch_verify_conversation()`: 전체 대화를 한 번에 처리
- `verify_fact_accuracy()`: 각 사실에 대해 3단계 검증 수행
  1. Keyword Matching
  2. Semantic Similarity
  3. LLM Verification
- `accuracy_rate`: 정확한 사실 수 / 총 사실 수
- 지식 점수 = `accuracy_rate * 100` (기본값)

### 테스트 모드의 현재 구조

```python
# 각 턴마다 개별 평가
for turn in turns:
    # 1. STT 평가
    stt_eval = self._evaluate_single_stt(...)
    
    # 2. RAG 평가
    rag_eval = self._evaluate_rag_integration(
        transcribed_text,
        expected_product_code,
        expected_keywords,
        role="employee"
    )
    # 결과: 점수 (0-100점), 키워드 점수, RAG 정보 점수
```

**현재 평가 로직 (`_evaluate_rag_integration`):**
```python
# 1. 사실 추출만 수행
facts = self.product_knowledge_service.extract_product_facts_from_conversation(
    [{"role": role, "text": text}]
)

# 2. 점수 계산 (검증 없이)
# - 키워드 점수 (50점): claim이 있으면 50점
# - RAG 정보 점수 (50점): 캐시된 키워드와 비교
```

## ❌ 문제점

### 1. **핵심 검증 로직 누락**
- ❌ `batch_verify_conversation()`을 사용하지 않음
- ❌ `verify_fact_accuracy()`의 3단계 검증을 수행하지 않음
- ❌ 정확도(`accuracy_rate`)를 계산하지 않음

### 2. **점수 산정 방식 불일치**
- 일반 모드: `accuracy_rate * 100` (정확한 사실 수 / 총 사실 수)
- 테스트 모드: 키워드 점수(50점) + RAG 정보 점수(50점) = 100점 만점
- **완전히 다른 점수 산정 방식**

### 3. **평가 시점 불일치**
- 일반 모드: 전체 대화 종료 후 일괄 평가
- 테스트 모드: 각 턴마다 개별 평가

### 4. **검증 단계 누락**
- 일반 모드: 3단계 검증 (키워드 → 의미적 유사도 → LLM)
- 테스트 모드: 사실 추출만 수행, 검증 없음

## ✅ 개선 방안

### 옵션 1: 테스트 모드에서도 `batch_verify_conversation()` 사용 (권장)

```python
def _process_test_mode_interaction(self, session_data: Dict, ...):
    # 각 턴마다 STT 평가
    stt_eval = self._evaluate_single_stt(...)
    
    # 대화 종료 시: 일반 모드와 동일한 지식 평가 수행
    if current_turn_index >= len(turns):
        # 일반 모드와 동일한 로직
        knowledge_verification_result = self.product_knowledge_service.batch_verify_conversation(
            conversation_history,  # 전체 대화
            use_llm=True
        )
        
        # 정확도 기반 지식 점수 계산
        accuracy_rate = knowledge_verification_result['accuracy_rate']
        knowledge_score = accuracy_rate * 100
        
        return {
            "stt_evaluation": self._evaluate_stt_performance(stt_evaluations),
            "knowledge_verification_result": knowledge_verification_result,
            "knowledge_score": knowledge_score,
            "accuracy_rate": accuracy_rate
        }
```

**장점:**
- ✅ 일반 모드와 동일한 로직 사용
- ✅ 3단계 검증 수행
- ✅ 정확도 기반 점수 산정
- ✅ 테스트 모드의 목적(지식 파트 점수 산정 로직 검증) 달성

**단점:**
- ⚠️ 턴별 실시간 평가 불가 (대화 종료 후 평가)
- ⚠️ 고객 발화도 평가에 포함됨 (일반 모드는 직원 발화만)

### 옵션 2: 턴별로 `verify_fact_accuracy()` 호출

```python
def _evaluate_rag_integration(self, text: str, ...):
    # 사실 추출
    facts = self.product_knowledge_service.extract_product_facts_from_conversation(...)
    
    # 각 사실에 대해 검증 수행 (일반 모드와 동일)
    verified_facts = []
    for fact in facts:
        for product_code in fact.get("product_codes", []):
            verification = self.product_knowledge_service.verify_fact_accuracy(
                claim=fact["claim"],
                product_code=product_code,
                category=fact["category"],
                use_llm=True
            )
            verified_facts.append(verification)
    
    # 정확도 계산
    accurate_count = sum(1 for v in verified_facts if v.is_accurate)
    accuracy_rate = accurate_count / len(verified_facts) if verified_facts else 0
    
    # 지식 점수 = 정확도 * 100
    knowledge_score = accuracy_rate * 100
    
    return {
        "score": knowledge_score,
        "accuracy_rate": accuracy_rate,
        "total_claims": len(verified_facts),
        "accurate_claims": accurate_count,
        "verifications": verified_facts
    }
```

**장점:**
- ✅ 턴별 실시간 평가 가능
- ✅ 일반 모드와 동일한 검증 로직 사용
- ✅ 정확도 기반 점수 산정

**단점:**
- ⚠️ 턴별로 개별 평가하므로 전체 대화 맥락 반영 어려움
- ⚠️ `batch_verify_conversation()`의 최적화 로직 누락

### 옵션 3: 하이브리드 접근

```python
# 턴별로 사실 추출 및 누적
# 대화 종료 시: batch_verify_conversation()으로 일괄 검증
```

## 🎯 권장 사항

**옵션 1 (대화 종료 후 일괄 평가)을 권장합니다.**

**이유:**
1. **테스트 모드의 목적**: 지식 파트 점수 산정 로직 검증
   - 일반 모드와 동일한 로직을 사용해야 검증 의미가 있음
2. **일반 모드와의 일관성**: `batch_verify_conversation()` 사용
   - 실제 운영 환경과 동일한 조건에서 테스트
3. **정확도 기반 점수**: `accuracy_rate * 100`
   - 현재 테스트 모드의 점수 산정 방식과 다르지만, 일반 모드와 일치

**구현 시 고려사항:**
- STT 평가는 턴별로 수행 (목적: STT 검증)
- 지식 평가는 대화 종료 후 일괄 수행 (목적: 지식 파트 점수 산정 로직 검증)
- 직원 발화만 평가 (일반 모드와 동일)

## 📊 비교표

| 항목 | 일반 모드 | 현재 테스트 모드 | 개선된 테스트 모드 (옵션 1) |
|------|----------|----------------|------------------------|
| **평가 시점** | 대화 종료 후 | 각 턴마다 | 대화 종료 후 |
| **평가 대상** | 직원 발화만 | 고객/직원 모두 | 직원 발화만 |
| **검증 방법** | `batch_verify_conversation()` | 사실 추출만 | `batch_verify_conversation()` |
| **검증 단계** | 3단계 (키워드→의미→LLM) | 없음 | 3단계 (키워드→의미→LLM) |
| **점수 산정** | `accuracy_rate * 100` | 키워드(50) + RAG(50) | `accuracy_rate * 100` |
| **STT 평가** | 별도 수행 | 턴별 수행 | 턴별 수행 |

## 🔧 구현 예시

```python
def _process_test_mode_interaction(self, session_data: Dict, ...):
    # ... STT 평가 (턴별) ...
    
    if current_turn_index >= len(turns):
        # 대화 종료: 일반 모드와 동일한 지식 평가 수행
        conversation_history = session_data.get("conversation_history", [])
        
        # 직원 발화만 필터링 (일반 모드와 동일)
        employee_utterances = [
            msg for msg in conversation_history 
            if msg.get("role") == "employee"
        ]
        
        if self.product_knowledge_service and employee_utterances:
            # 일반 모드와 동일한 로직
            knowledge_verification_result = self.product_knowledge_service.batch_verify_conversation(
                employee_utterances,
                use_llm=True
            )
            
            accuracy_rate = knowledge_verification_result['accuracy_rate']
            knowledge_score = accuracy_rate * 100
            
            return {
                "stt_evaluation": self._evaluate_stt_performance(stt_evaluations),
                "knowledge_verification_result": knowledge_verification_result,
                "knowledge_score": knowledge_score,
                "accuracy_rate": accuracy_rate,
                "test_completed": True
            }
```

## ✅ 결론

**현재 테스트 모드 코드 구조는 목적에 부적합합니다.**

**이유:**
1. 일반 모드의 핵심 로직(`batch_verify_conversation()`)을 사용하지 않음
2. 점수 산정 방식이 일반 모드와 완전히 다름
3. 3단계 검증을 수행하지 않음

**개선 필요:**
- 대화 종료 후 `batch_verify_conversation()` 호출
- 정확도 기반 지식 점수 산정
- 직원 발화만 평가 (일반 모드와 동일)

