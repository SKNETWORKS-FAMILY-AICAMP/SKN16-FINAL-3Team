# `subsection_title` 매칭을 최우선으로 둔 이유

## 📊 실제 데이터 구조 분석

### JSONL 파일의 구조

각 제품 데이터는 다음과 같은 구조화된 필드를 가집니다:

```json
{
  "id": "CRD-CRE-P04-S01-C001",
  "product_code": "CRD-CRE",
  "part_title": "신용한도 및 결제",
  "subsection_title": "신용한도 (신용등급별)",  // ← 구조화된 섹션 제목
  "text": "PART 4. 신용한도 및 결제 > 신용한도 (신용등급별)\n▣ 신용한도 (신용등급별)\n- 1~2등급: 최대 1억원\n- 3~4등급: 최대 5,000만원\n- 5~6등급: 최대 3,000만원"
}
```

### `subsection_title` 예시

실제 데이터에서 `subsection_title`은 다음과 같이 구조화되어 있습니다:

| subsection_title | 의미 | 카테고리 매칭 |
|------------------|------|--------------|
| `"이자율"` | 이자율 정보 | `"금리"` 카테고리 |
| `"신용한도 (신용등급별)"` | 한도 정보 | `"한도"` 카테고리 |
| `"연회비"` | 연회비 정보 | `"수수료"` 카테고리 |
| `"포인트 적립"` | 포인트 정보 | `"혜택"` 카테고리 |
| `"가입금액"` | 가입금액 정보 | `"가입금액"` 카테고리 |

## 🎯 `subsection_title` 매칭을 최우선으로 둔 이유

### 1. **구조화된 정보 검색의 정확도**

`subsection_title`은 문서의 **구조화된 섹션 제목**입니다. 이는 본문(`text`)보다 훨씬 **명확하고 정확한 정보의 위치**를 나타냅니다.

**예시**:
- 질문: "신용대출 한도가 얼마인가요?"
- 카테고리: `"한도"`
- 매칭 과정:
  1. `subsection_title`에서 "한도" 키워드 검색
  2. `"신용한도 (신용등급별)"` subsection_title 발견 → **즉시 정확한 청크 찾음**
  3. 본문 전체를 검색할 필요 없음

### 2. **카테고리 기반 구조화된 매칭**

코드에서 카테고리와 `subsection_title`을 매칭하는 로직:

```python
# 카테고리 → 키워드 매핑
category_mapping = {
    "금리": ["금리", "이자율", "기본금리", "우대금리", ...],
    "한도": ["한도", "신용한도", ...],
    "수수료": ["수수료", "연회비", ...],
}

# subsection_title에서 카테고리 키워드 검색
if category and self._category_matches_subsection(category, subsection):
    score = 1.0  # 최고 점수
```

**장점**:
- `"이자율"` subsection_title → `"금리"` 카테고리 자동 매칭
- `"연회비"` subsection_title → `"수수료"` 카테고리 자동 매칭
- 구조화된 정보를 빠르게 찾을 수 있음

### 3. **성능 최적화**

본문 전체를 검색하는 것보다 구조화된 제목을 매칭하는 것이 **훨씬 빠릅니다**:

```python
# ❌ 느린 방법: 본문 전체 검색
for chunk in chunks:
    if query in chunk["text"]:  # 전체 텍스트 검색 (느림)
        ...

# ✅ 빠른 방법: subsection_title 우선 매칭
for chunk in chunks:
    if category_matches_subsection(category, chunk["subsection_title"]):  # 제목만 검색 (빠름)
        score = 1.0  # 즉시 최고 점수
```

### 4. **노이즈 제거**

본문에는 다양한 정보가 섞여 있을 수 있지만, `subsection_title`은 **해당 섹션의 핵심 주제**를 명확히 나타냅니다.

**예시**:
- 본문: "신용대출 한도는 연소득의 1.5배~2배까지 가능합니다. 또한 금리는 연 2.15%입니다."
  - "한도"와 "금리"가 모두 포함되어 혼란 가능
- `subsection_title`: `"신용한도 (신용등급별)"`
  - 명확하게 "한도" 정보만 다루는 섹션임을 나타냄

### 5. **검색 정확도 향상**

`subsection_title` 매칭 시 **score = 1.0** (최고 점수)을 부여하여, 다른 검색 방법보다 우선순위를 확보합니다:

```python
# === 1단계: 카테고리 기반 subsection_title 매칭 (최우선) ===
if category and self._category_matches_subsection(category, subsection):
    score = 1.0  # 최고 점수
    match_type = "category_subsection"

# === 2단계: 전체 쿼리 포함 여부 확인 ===
elif query_lower in chunk_text_lower:
    score = self._calculate_relevance_score(...)  # 0.0~1.0 사이 점수
    match_type = "full_query"

# === 3단계: 키워드 부분 매칭 ===
else:
    score = match_ratio * 0.7  # 최대 0.7점
    match_type = "partial_keyword"
```

## 📈 실제 검색 시나리오

### 시나리오 1: "신용대출 한도가 얼마인가요?"

```python
# 입력
query = "신용대출 한도가 얼마인가요?"
category = "한도"  # extract_product_facts_from_conversation에서 추출
product_code = "LON-CRE"

# 검색 과정
1. search_by_keyword(query="신용대출 한도가 얼마인가요?", category="한도", product_codes=["LON-CRE"])
2. LON-CRE 제품의 모든 청크 순회
3. 각 청크의 subsection_title 확인:
   - "이자율" → "한도" 카테고리와 매칭 안 됨
   - "신용한도 (신용등급별)" → "한도" 카테고리와 매칭! ✅
   - score = 1.0 (최고 점수)
   - 즉시 해당 청크 반환
```

### 시나리오 2: "금리는 얼마인가요?"

```python
# 입력
query = "금리는 얼마인가요?"
category = "금리"
product_code = "LON-CRE"

# 검색 과정
1. search_by_keyword(query="금리는 얼마인가요?", category="금리", product_codes=["LON-CRE"])
2. LON-CRE 제품의 모든 청크 순회
3. 각 청크의 subsection_title 확인:
   - "이자율" → "금리" 카테고리와 매칭! ✅ (이자율 = 금리)
   - score = 1.0 (최고 점수)
   - 즉시 해당 청크 반환
```

## 🔍 코드에서의 구현

### `search_by_keyword` 함수의 우선순위

```python
def search_by_keyword(self, query, category=None, product_codes=None, top_k=5):
    for product_code, chunks in search_space.items():
        for chunk in chunks:
            chunk_text = chunk.get("text", "")
            subsection = chunk.get("subsection_title", "")  # ← 구조화된 제목
            
            # === 1단계: 카테고리 기반 subsection_title 매칭 (최우선) ===
            if category and self._category_matches_subsection(category, subsection):
                score = 1.0  # 최고 점수
                match_type = "category_subsection"
            
            # === 2단계: 전체 쿼리 포함 여부 확인 ===
            elif query_lower in chunk_text_lower or query_lower in subsection_lower:
                score = self._calculate_relevance_score(...)
                match_type = "full_query"
            
            # === 3단계: 키워드 부분 매칭 ===
            else:
                score = match_ratio * 0.7  # 최대 0.7점
                match_type = "partial_keyword"
```

### `_category_matches_subsection` 함수

```python
def _category_matches_subsection(self, category: str, subsection_title: str) -> bool:
    """카테고리가 subsection_title과 매칭되는지 확인"""
    keywords = self._get_category_keywords_for_subsection(category)
    # 예: category="금리" → keywords=["금리", "이자율", "기본금리", ...]
    
    subsection_lower = subsection_title.lower()
    # 키워드 중 하나라도 subsection_title에 포함되면 매칭
    return any(keyword.lower() in subsection_lower for keyword in keywords)
```

## ✅ 요약

`subsection_title` 매칭을 최우선으로 둔 이유:

1. **구조화된 정보**: `subsection_title`은 문서의 구조화된 섹션 제목으로, 본문보다 정확한 정보 위치를 나타냄
2. **카테고리 기반 매칭**: 카테고리와 `subsection_title`을 매칭하여 정확한 정보를 빠르게 찾을 수 있음
3. **성능 최적화**: 본문 전체 검색보다 구조화된 제목 매칭이 훨씬 빠름
4. **노이즈 제거**: 본문의 혼란스러운 정보보다 명확한 섹션 제목을 우선 사용
5. **검색 정확도**: `subsection_title` 매칭 시 최고 점수(1.0)를 부여하여 우선순위 확보

**결론**: `subsection_title`은 구조화된 문서의 **메타데이터**이므로, 이를 우선적으로 활용하면 더 정확하고 빠른 검색이 가능합니다.

