# 제품 키워드 자동 추출 가이드

## 📌 개요

하이브리드 접근 방식을 사용하여 제품 키워드를 자동으로 추출하고 관리합니다.

**하이브리드 접근 방식**:
1. **제품 데이터 파일에서 자동 추출**: `*.jsonl` 파일의 `subsection_title`과 텍스트를 분석
2. **LLM 검증 및 보정**: GPT-4o-mini를 사용하여 키워드 품질 검증 및 보정
3. **JSON 파일로 캐싱**: 검증된 키워드를 `backend/data/product_keywords_cache.json`에 저장하여 재사용

## 🚀 사용법

### 1. 모든 제품 키워드 추출

```bash
# LLM 검증 포함 (권장)
python scripts/extract_product_keywords.py all

# LLM 검증 없이 (빠른 테스트)
python scripts/extract_product_keywords.py --no-llm all
```

### 2. 특정 제품 키워드 추출

```bash
# LLM 검증 포함
python scripts/extract_product_keywords.py LON-MTG

# LLM 검증 없이
python scripts/extract_product_keywords.py --no-llm LON-MTG
```

### 3. Python 코드에서 직접 사용

```python
from app.services.product_keyword_extractor import ProductKeywordExtractor

# 초기화
extractor = ProductKeywordExtractor(use_llm=True)

# 특정 제품 키워드 추출
keywords = extractor.extract_keywords_for_product("LON-MTG", use_llm=True)

# 모든 제품 키워드 추출
extractor.extract_all_products(use_llm=True)

# 캐시된 키워드 가져오기
keywords = extractor.get_keywords("LON-MTG")
```

## 📁 파일 구조

```
backend/
├── app/services/
│   └── product_keyword_extractor.py  # 자동 추출 서비스
├── data/
│   └── product_keywords_cache.json   # 캐시 파일 (자동 생성)
└── scripts/
    └── extract_product_keywords.py   # CLI 도구
```

## 📊 캐시 파일 형식

```json
{
  "LON-MTG": {
    "product_keywords": ["주택담보대출", "주택담보", "주택 담보 대출"],
    "categories": ["금리", "한도", "기간", "LTV", "DTI", "DSR", "상환방식"],
    "info_keywords": ["주택담보", "LTV", "DTI", "DSR", "담보인정비율", "70%", "60%"],
    "auto_generated": true,
    "last_updated": "2025-01-15T10:30:00",
    "llm_reasoning": "검증 및 보정 이유..."
  }
}
```

## 🔄 기존 코드와의 통합

`ProductKnowledgeService`는 자동으로 캐시된 키워드를 사용합니다:

1. **캐시 우선**: `product_keywords_cache.json`에서 키워드 로드
2. **Fallback**: 캐시가 없으면 하드코딩된 키워드 사용
3. **자동 업데이트**: 새 제품 추가 시 자동으로 키워드 추출

## ⚙️ 설정

### LLM 검증 활성화/비활성화

```python
# LLM 검증 활성화 (기본값)
extractor = ProductKeywordExtractor(use_llm=True)

# LLM 검증 비활성화
extractor = ProductKeywordExtractor(use_llm=False)
```

### 환경 변수

- `OPENAI_API_KEY`: LLM 검증을 위한 OpenAI API 키 (선택)

## 📝 키워드 수동 수정

캐시 파일을 직접 수정하거나 Python 코드로 수정:

```python
extractor = ProductKeywordExtractor()

# 키워드 수동 업데이트
extractor.update_keywords("LON-MTG", {
    "product_keywords": ["주택담보대출", "주택담보"],
    "categories": ["금리", "한도"],
    "info_keywords": ["LTV", "DTI"],
    "auto_generated": False
})
```

## 🔍 추출 로직

### 1. 제품 키워드 추출

- 제품명에서 한글 부분 추출
- 공백 제거 버전 생성
- 주요 단어 조합 생성

### 2. 카테고리 추출

- `subsection_title`에서 카테고리 패턴 매칭
- 텍스트에서 카테고리 키워드 검색

### 3. 정보 키워드 추출

- 카테고리별 핵심 키워드
- 수치 정보 (예: "70%", "100만원")
- 제품 특성 키워드

## ⚠️ 주의사항

1. **캐시 파일 백업**: 수동 수정 전에 백업 권장
2. **LLM 비용**: LLM 검증 사용 시 API 비용 발생
3. **품질 검증**: 자동 추출된 키워드는 수동 검토 권장

## 🐛 문제 해결

### 캐시 파일이 생성되지 않음

```bash
# 데이터 디렉토리 확인
ls -la backend/data/

# 권한 확인
chmod 755 backend/data/
```

### LLM 검증 실패

```bash
# API 키 확인
echo $OPENAI_API_KEY

# LLM 없이 추출
python scripts/extract_product_keywords.py --no-llm all
```

## 📚 참고

- `backend/TEST_MODE_RAG_EVALUATION_GUIDE.md`: RAG 평가 가이드
- `backend/app/services/product_knowledge_service.py`: 제품 지식 서비스
- `backend/data/rag_sources/products/hakyung/`: 제품 데이터 파일

