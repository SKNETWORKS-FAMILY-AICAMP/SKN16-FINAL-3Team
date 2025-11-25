# LLM 기반 Product Code 추출 테스트 가이드

## 개요

기본적으로 product_code 추출은 **키워드 매칭** 방식을 사용합니다. LLM 기반 추출로 테스트하려면 설정을 변경해야 합니다.

## 두 가지 추출 방식 비교

### 1. 키워드 매칭 (기본)
- **방식**: 하드코딩된 키워드 목록과 발화 텍스트를 비교
- **장점**: 빠른 처리 속도, API 비용 없음
- **단점**: 새로운 표현이나 문맥 이해 제한적
- **예시**: "주택담보대출" → `LON-MTG` 매칭

### 2. LLM 기반 추출 (테스트)
- **방식**: GPT-4o-mini가 발화를 분석하여 제품 코드 추출
- **장점**: 문맥 이해, 다양한 표현 처리, 자동 카테고리 분류
- **단점**: API 비용 발생, 처리 시간 증가
- **예시**: "집 담보로 돈 빌리는 상품" → `LON-MTG` 추출

## LLM 추출 활성화 방법

### 방법 1: 환경 변수 설정 (권장)

`.env` 파일에 추가:
```bash
USE_LLM_EXTRACTION=true
```

### 방법 2: 코드에서 직접 설정

`backend/app/config.py`:
```python
USE_LLM_EXTRACTION: bool = True  # False → True로 변경
```

### 방법 3: 테스트 모드에서만 활성화

`backend/app/services/rag_simulation_service.py`의 `_evaluate_rag_integration` 메서드에서:
```python
use_llm_extraction = True  # 강제로 LLM 추출 사용
```

## 테스트 방법

### 1. 환경 변수 설정
```bash
# .env 파일
USE_LLM_EXTRACTION=true
OPENAI_API_KEY=your-api-key-here
```

### 2. 백엔드 재시작
```bash
# Docker 사용 시
docker-compose restart backend

# 로컬 실행 시
# 백엔드 서버 재시작
```

### 3. 테스트 모드 실행
- 관리자 대시보드 → 테스트 평가서
- 시뮬레이션 실행
- 평가 결과에서 `extraction_method` 확인

### 4. 결과 확인

**키워드 매칭 사용 시:**
```json
{
  "extraction_method": "keyword",
  "extracted_product_codes": ["LON-MTG"]
}
```

**LLM 추출 사용 시:**
```json
{
  "extraction_method": "llm",
  "extracted_product_codes": ["LON-MTG"],
  "extracted_categories": ["금리", "한도", "LTV"]
}
```

## LLM 추출 동작 방식

1. **발화 분석**: GPT-4o-mini가 직원 발화를 분석
2. **제품 감지**: 키워드 매핑을 참고하여 언급된 제품 감지
3. **Claim 추출**: 제품 관련 정보(금리, 한도 등)를 claim으로 추출
4. **카테고리 분류**: 자동으로 카테고리 분류 (금리, 한도, 수수료 등)
5. **JSON 반환**: 구조화된 JSON 형식으로 반환

## LLM 추출 프롬프트 예시

```python
prompt = f"""다음은 은행 직원의 발화입니다. 제품 관련 정보(금리, 한도, 수수료, 기간 등)를 추출해주세요.

**발화:**
주택담보대출은 주택을 담보로 제공하여 대출받는 상품입니다. 
금리는 연 3.5%부터 시작하며, 최대 1억원까지 대출 가능합니다.

**추출할 카테고리:**
금리, 한도, 기간, LTV, DTI, DSR, 상환방식, 우대금리, 필요서류

**출력 형식 (JSON):**
{{
  "facts": [
    {{
      "category": "금리",
      "claim": "연 3.5%부터 시작",
      "value": "3.5",
      "unit": "%"
    }},
    {{
      "category": "한도",
      "claim": "최대 1억원까지 대출 가능",
      "value": "100000000",
      "unit": "원"
    }}
  ]
}}
"""
```

## 성능 비교

### 키워드 매칭
- **처리 시간**: ~10ms
- **API 비용**: 없음
- **정확도**: 키워드가 명확할 때 높음

### LLM 추출
- **처리 시간**: ~500-1000ms (API 호출)
- **API 비용**: GPT-4o-mini 기준 약 $0.15/1M tokens
- **정확도**: 문맥 이해로 다양한 표현 처리 가능

## 주의사항

1. **OpenAI API Key 필수**: LLM 추출을 사용하려면 `OPENAI_API_KEY`가 설정되어 있어야 합니다.
2. **API 비용**: LLM 추출은 API 호출이 발생하므로 비용이 발생합니다.
3. **처리 시간**: LLM 추출은 키워드 매칭보다 느립니다.
4. **Fallback**: LLM 추출 실패 시 자동으로 키워드 매칭으로 fallback됩니다.

## 문제 해결

### LLM 추출이 작동하지 않는 경우

1. **OpenAI API Key 확인**
   ```bash
   echo $OPENAI_API_KEY
   # 또는 .env 파일 확인
   ```

2. **설정 확인**
   ```python
   # backend/app/config.py
   USE_LLM_EXTRACTION: bool = True
   ```

3. **로그 확인**
   - 백엔드 로그에서 "✅ LLM 기반 추출 완료" 메시지 확인
   - "⚠️ LLM 추출 실패" 메시지가 있으면 오류 원인 확인

4. **Fallback 확인**
   - LLM 추출 실패 시 자동으로 키워드 매칭으로 전환됨
   - 로그에서 "정규식 기반 추출 (fallback)" 메시지 확인

## 테스트 케이스

### 테스트 1: 명확한 키워드
**발화**: "주택담보대출 상품에 대해 알려드리겠습니다."
- 키워드 매칭: ✅ `LON-MTG` 추출
- LLM 추출: ✅ `LON-MTG` 추출

### 테스트 2: 다양한 표현
**발화**: "집을 담보로 돈을 빌릴 수 있는 상품이 있습니다."
- 키워드 매칭: ❌ 매칭 실패 (키워드 없음)
- LLM 추출: ✅ `LON-MTG` 추출 (문맥 이해)

### 테스트 3: 복합 정보
**발화**: "이 상품은 금리가 연 3.5%이고, 최대 1억원까지 가능합니다."
- 키워드 매칭: ⚠️ 제품 코드 추출 어려움
- LLM 추출: ✅ 제품 코드 + 카테고리 + 값 추출

