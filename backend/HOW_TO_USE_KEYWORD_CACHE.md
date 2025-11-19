# 제품 키워드 캐시 사용 가이드

## 📌 개요

`product_keywords_cache.json` 파일은 모든 제품의 키워드를 자동으로 추출하여 저장한 캐시 파일입니다. 이 파일은 기존 하드코딩된 키워드를 대체하여 사용됩니다.

## 🔄 자동 통합 상태

### ✅ 이미 통합된 부분

1. **`ProductKnowledgeService`** (일반 모드)
   - `_get_product_keywords()`: 제품별 키워드 매핑
   - `_get_product_category_priority()`: 상품별 중요 정보 카테고리
   - **위치**: `backend/app/services/product_knowledge_service.py`

2. **`RAGSimulationService`** (테스트 모드 RAG 평가)
   - `_get_key_info_keywords()`: 상품 데이터 근거 추출용 키워드
   - `_get_product_keywords_map()`: 고객 발화 평가용 키워드
   - `_get_product_info_keywords()`: RAG 평가용 제품 정보 키워드
   - **위치**: `backend/app/services/rag_simulation_service.py`

## 📊 캐시 파일 구조

```json
{
  "LON-MTG": {
    "product_keywords": ["주택담보대출", "주택담보", "주택 담보 대출"],
    "categories": ["금리", "한도", "기간", "LTV", "DTI", "DSR", "상환방식"],
    "info_keywords": ["주택담보", "LTV", "DTI", "DSR", "담보인정비율", "70%", "60%"],
    "auto_generated": true,
    "last_updated": "2025-11-19T15:06:04.960574",
    "llm_reasoning": "검증 및 보정 이유..."
  }
}
```

## 🔍 사용 방법

### 1. 자동 사용 (권장)

캐시 파일이 존재하면 **자동으로 사용**됩니다. 별도 설정이 필요 없습니다.

```python
# ProductKnowledgeService는 자동으로 캐시를 사용
service = ProductKnowledgeService()
# 내부적으로 _get_product_keywords()가 캐시를 우선 사용
```

### 2. 수동으로 키워드 가져오기

```python
from app.services.product_keyword_extractor import ProductKeywordExtractor

extractor = ProductKeywordExtractor()

# 특정 제품 키워드 가져오기
keywords = extractor.get_keywords("LON-MTG")
print(keywords["product_keywords"])  # 제품명 키워드
print(keywords["categories"])        # 카테고리
print(keywords["info_keywords"])     # 정보 키워드
```

### 3. 키워드 수동 수정

```python
extractor = ProductKeywordExtractor()

# 키워드 업데이트
extractor.update_keywords("LON-MTG", {
    "product_keywords": ["주택담보대출", "주택담보"],
    "categories": ["금리", "한도", "LTV"],
    "info_keywords": ["LTV", "DTI", "DSR"],
    "auto_generated": False  # 수동 수정 표시
})
```

## 🔄 동작 원리

### 우선순위

1. **캐시 파일** (`product_keywords_cache.json`) - 최우선
2. **하드코딩된 키워드** - Fallback (캐시가 없을 때)

### 통합 흐름

```
애플리케이션 시작
    ↓
ProductKnowledgeService 초기화
    ↓
ProductKeywordExtractor 초기화
    ↓
캐시 파일 로드 (product_keywords_cache.json)
    ↓
키워드 요청 시
    ↓
캐시에서 키워드 반환 (있으면)
    ↓
캐시 없으면 하드코딩된 키워드 반환
```

## 📝 키워드 업데이트 방법

### 방법 1: 캐시 파일 직접 수정

`backend/data/product_keywords_cache.json` 파일을 직접 편집:

```json
{
  "LON-MTG": {
    "product_keywords": ["주택담보대출", "주택담보", "수정된 키워드"],
    "categories": ["금리", "한도"],
    "info_keywords": ["LTV", "DTI"],
    "auto_generated": false,
    "last_updated": "2025-11-19T16:00:00"
  }
}
```

### 방법 2: Python 코드로 수정

```python
from app.services.product_keyword_extractor import ProductKeywordExtractor

extractor = ProductKeywordExtractor()

# 키워드 업데이트
extractor.update_keywords("LON-MTG", {
    "product_keywords": ["주택담보대출", "주택담보"],
    "categories": ["금리", "한도", "LTV"],
    "info_keywords": ["LTV", "DTI", "DSR"],
    "auto_generated": False
})
```

### 방법 3: 재추출 (LLM 검증 포함)

```bash
# 특정 제품만 재추출
python scripts/extract_product_keywords.py LON-MTG

# 모든 제품 재추출
python scripts/extract_product_keywords.py all
```

## 🎯 각 키워드의 용도

### 1. `product_keywords`
- **용도**: 제품 코드 자동 감지
- **사용 위치**: 
  - `ProductKnowledgeService.extract_product_facts_from_conversation()`
  - 일반 모드에서 직원 발화에서 제품 감지

### 2. `categories`
- **용도**: 정보 카테고리 우선순위 결정
- **사용 위치**:
  - `ProductKnowledgeService.extract_product_facts_from_conversation()`
  - 일반 모드에서 어떤 정보를 추출할지 결정

### 3. `info_keywords`
- **용도**: RAG 평가 및 상품 데이터 근거 추출
- **사용 위치**:
  - `RAGSimulationService._evaluate_rag_integration()` (테스트 모드)
  - `RAGSimulationService._evaluate_customer_rag_integration()` (테스트 모드)
  - `RAGSimulationService._extract_product_evidence()` (테스트 모드)

## ⚠️ 주의사항

1. **캐시 파일 백업**: 수동 수정 전에 백업 권장
2. **JSON 형식 유지**: 파일 수정 시 JSON 형식 유지 필수
3. **인코딩**: UTF-8 인코딩 사용
4. **자동 재생성**: `extract_product_keywords.py` 실행 시 수동 수정 내용이 덮어씌워질 수 있음

## 🔍 문제 해결

### 캐시가 사용되지 않음

1. **캐시 파일 존재 확인**
   ```bash
   ls -la backend/data/product_keywords_cache.json
   ```

2. **키워드 추출기 초기화 확인**
   - 애플리케이션 시작 시 로그 확인
   - "✅ 키워드 자동 추출기 초기화 완료" 메시지 확인

3. **캐시 파일 형식 확인**
   ```python
   import json
   with open('backend/data/product_keywords_cache.json', 'r', encoding='utf-8') as f:
       data = json.load(f)
       print("캐시 파일 정상")
   ```

### 특정 제품 키워드가 없음

```python
# 키워드 재추출
from app.services.product_keyword_extractor import ProductKeywordExtractor

extractor = ProductKeywordExtractor()
extractor.extract_keywords_for_product("LON-MTG", use_llm=True)
```

## 📚 관련 파일

- `backend/app/services/product_keyword_extractor.py`: 키워드 추출 서비스
- `backend/app/services/product_knowledge_service.py`: 제품 지식 서비스 (일반 모드)
- `backend/app/services/rag_simulation_service.py`: RAG 시뮬레이션 서비스 (테스트 모드)
- `backend/scripts/extract_product_keywords.py`: CLI 도구
- `backend/PRODUCT_KEYWORD_AUTO_EXTRACTION.md`: 자동 추출 가이드

