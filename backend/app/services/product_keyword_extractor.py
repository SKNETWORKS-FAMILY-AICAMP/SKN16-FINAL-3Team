"""
제품 키워드 자동 추출 서비스 (Hybrid Approach)

하이브리드 접근 방식:
1. 제품 데이터 파일에서 자동 추출
2. LLM을 사용하여 검증 및 보정
3. JSON 파일로 캐싱하여 재사용
"""
import json
import os
import re
from typing import Dict, List, Optional, Set
from pathlib import Path
from datetime import datetime

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from app.config import settings


class ProductKeywordExtractor:
    """제품 키워드 자동 추출 및 관리 서비스"""
    
    def __init__(self, data_path: Optional[Path] = None, use_llm: bool = True):
        """
        초기화
        
        Args:
            data_path: 데이터 디렉토리 경로 (기본: backend/data)
            use_llm: LLM 검증 사용 여부 (기본: True)
        """
        if data_path is None:
            # Docker 환경 우선, 없으면 로컬
            if Path("/app/data").exists():
                self.data_path = Path("/app/data")
            else:
                self.data_path = Path(__file__).parent.parent.parent / "data"
        else:
            self.data_path = data_path
        
        self.products_dir = self.data_path / "rag_sources" / "products" / "hakyung"
        self.cache_file = self.data_path / "product_keywords_cache.json"
        
        # LLM 설정
        self.use_llm = use_llm and OPENAI_AVAILABLE
        self.openai_client = None
        
        if self.use_llm:
            api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
            if api_key:
                try:
                    self.openai_client = OpenAI(api_key=api_key)
                    print("✅ LLM 검증 활성화")
                except Exception as e:
                    print(f"⚠️ OpenAI 초기화 실패: {e}")
                    self.use_llm = False
            else:
                print("⚠️ OPENAI_API_KEY 없음 - LLM 검증 비활성화")
                self.use_llm = False
        
        # 캐시 로드
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """캐시 파일 로드"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 캐시 로드 실패: {e}")
        return {}
    
    def _save_cache(self):
        """캐시 파일 저장"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            print(f"✅ 캐시 저장 완료: {self.cache_file}")
        except Exception as e:
            print(f"❌ 캐시 저장 실패: {e}")
    
    def load_product_data(self, product_code: str) -> List[Dict]:
        """제품 데이터 로드"""
        jsonl_file = self.products_dir / f"{product_code}.jsonl"
        if not jsonl_file.exists():
            return []
        
        chunks = []
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        chunks.append(json.loads(line.strip()))
        except Exception as e:
            print(f"❌ 제품 데이터 로드 실패 ({product_code}): {e}")
        
        return chunks
    
    def extract_categories_from_data(self, chunks: List[Dict]) -> Set[str]:
        """제품 데이터에서 카테고리 자동 추출"""
        categories = set()
        
        # 카테고리 매핑 (subsection_title 패턴)
        category_patterns = {
            "금리": ["금리", "이자율", "이자"],
            "한도": ["한도", "최대", "최소"],
            "기간": ["기간", "만기", "거치기간", "계약기간"],
            "조건": ["조건", "자격", "대상"],
            "수수료": ["수수료", "연회비", "중도상환", "중도해지"],
            "우대금리": ["우대금리", "우대"],
            "LTV": ["LTV", "담보인정비율", "담보 인정 비율"],
            "DTI": ["DTI", "총부채상환비율"],
            "DSR": ["DSR", "총부채원리금상환비율"],
            "상환방식": ["상환방식", "상환 방법", "원리금", "원금", "체증식", "거치식"],
            "신용등급": ["신용등급", "등급"],
            "이자지급": ["이자지급", "이자 지급", "이자 납부"],
            "예금자보호": ["예금자보호", "예금자 보호", "보호한도"],
            "필요서류": ["필요서류", "필요 서류", "서류"],
            "가입금액": ["가입금액", "가입 금액", "납입금액"],
            "혜택": ["혜택", "할인", "포인트", "적립"],
            "환율": ["환율", "환전", "외환"],
        }
        
        for chunk in chunks:
            subsection = chunk.get("subsection_title", "")
            text = chunk.get("text", "")
            
            # subsection_title에서 카테고리 추출
            for category, keywords in category_patterns.items():
                if any(kw in subsection for kw in keywords):
                    categories.add(category)
            
            # text에서도 카테고리 추출 (LTV, DTI, DSR 등)
            for category, keywords in category_patterns.items():
                if any(kw in text for kw in keywords):
                    categories.add(category)
        
        return categories
    
    def extract_product_keywords(self, chunks: List[Dict]) -> List[str]:
        """제품명 관련 키워드 추출"""
        keywords = set()
        
        for chunk in chunks:
            # 제품명 추출
            product = chunk.get("product", "")
            product_code = chunk.get("product_code", "")
            
            if product:
                # "하경은행 주택담보대출 (Hakyung Bank Mortgage Loan)" → ["주택담보대출", "주택담보", "주택 담보 대출"]
                # 한글 부분만 추출
                korean_part = product.split("(")[0].strip()
                keywords.add(korean_part)
                
                # 공백 제거 버전
                keywords.add(korean_part.replace(" ", ""))
                
                # 주요 단어 추출
                words = korean_part.split()
                if len(words) > 1:
                    # "주택담보대출" → ["주택담보", "담보대출"]
                    for i in range(len(words) - 1):
                        keywords.add(" ".join(words[i:i+2]))
                        keywords.add("".join(words[i:i+2]))
            
            # subsection_title에서 제품 관련 키워드 추출
            subsection = chunk.get("subsection_title", "")
            if "상품명" in subsection or "상품" in subsection:
                # "상품명: 하경은행 주택담보대출" → "주택담보대출"
                parts = subsection.split(":")
                if len(parts) > 1:
                    product_name = parts[-1].strip()
                    keywords.add(product_name)
        
        return sorted(list(keywords))
    
    def extract_info_keywords(self, chunks: List[Dict], categories: Set[str]) -> List[str]:
        """핵심 정보 키워드 추출 (수치, 주요 용어)"""
        keywords = set()
        
        # 카테고리별 핵심 키워드
        category_keywords = {
            "LTV": ["LTV", "담보인정비율", "70%", "60%", "40%", "30%"],
            "DTI": ["DTI", "총부채상환비율", "60%", "40%", "50%"],
            "DSR": ["DSR", "총부채원리금상환비율", "50%", "60%"],
            "금리": ["금리", "이자율", "%"],
            "한도": ["한도", "최대", "최소", "만원", "억원"],
            "가입금액": ["가입금액", "100만원", "50만원", "최소"],
            "예금자보호": ["예금자보호", "5천만원", "보호한도"],
        }
        
        # 카테고리에 해당하는 키워드 추가
        for category in categories:
            if category in category_keywords:
                keywords.update(category_keywords[category])
        
        # 텍스트에서 수치 추출 (예: "95%", "100만원")
        for chunk in chunks:
            text = chunk.get("text", "")
            
            # 퍼센트 추출
            percentages = re.findall(r'(\d+(?:\.\d+)?%)', text)
            keywords.update(percentages)
            
            # 금액 추출 (예: "100만원", "5천만원")
            amounts = re.findall(r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(만|천|억|조)?\s*원', text)
            for amount in amounts:
                if amount[1]:  # 단위가 있는 경우
                    keywords.add(f"{amount[0]}{amount[1]}원")
        
        # 제품 특성 키워드 추출
        for chunk in chunks:
            subsection = chunk.get("subsection_title", "")
            text = chunk.get("text", "")
            
            # 주요 용어 추출
            important_terms = [
                "MMDA", "MMA", "입출금", "자유통장",
                "주택담보", "담보", "예금담보", "수취은행",
                "초저금리", "예금잔액", "차등", "규제"
            ]
            
            for term in important_terms:
                if term in subsection or term in text:
                    keywords.add(term)
        
        return sorted(list(keywords))
    
    def validate_with_llm(self, product_code: str, extracted_data: Dict) -> Dict:
        """LLM을 사용하여 키워드 검증 및 보정"""
        if not self.use_llm or not self.openai_client:
            return extracted_data
        
        try:
            chunks = self.load_product_data(product_code)
            if not chunks:
                return extracted_data
            
            # 제품 데이터 요약
            product_summary = []
            for chunk in chunks[:10]:  # 상위 10개만
                subsection = chunk.get("subsection_title", "")
                text = chunk.get("text", "")[:200]  # 처음 200자만
                product_summary.append(f"- {subsection}: {text}")
            
            prompt = f"""제품 코드: {product_code}

제품 데이터 요약:
{chr(10).join(product_summary)}

현재 추출된 키워드:
- 제품 키워드: {extracted_data.get('product_keywords', [])}
- 카테고리: {extracted_data.get('categories', [])}
- 정보 키워드: {extracted_data.get('info_keywords', [])}

위 제품의 핵심 정보를 나타내는 키워드를 검증하고 보정하세요.

**지침:**
1. 제품명 관련 키워드: 고객이 말할 수 있는 다양한 표현 포함 (예: "주택담보대출", "주택담보", "주택 담보 대출")
2. 카테고리: 제품의 주요 정보 항목 (금리, 한도, 기간, LTV, DTI, DSR 등)
3. 정보 키워드: 핵심 수치 정보와 주요 용어 (예: "70%", "100만원", "LTV", "담보인정비율")

**출력 형식 (JSON):**
{{
  "product_keywords": ["키워드1", "키워드2", ...],
  "categories": ["카테고리1", "카테고리2", ...],
  "info_keywords": ["키워드1", "키워드2", ...],
  "reasoning": "검증 및 보정 이유"
}}

JSON으로만 응답하세요."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 은행 제품 정보 분석 전문가입니다. 제품 데이터를 분석하여 핵심 키워드를 추출하고 검증합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # LLM 결과로 업데이트
            validated_data = {
                "product_keywords": result.get("product_keywords", extracted_data.get("product_keywords", [])),
                "categories": result.get("categories", extracted_data.get("categories", [])),
                "info_keywords": result.get("info_keywords", extracted_data.get("info_keywords", [])),
                "llm_reasoning": result.get("reasoning", ""),
                "auto_generated": True,
                "last_updated": datetime.now().isoformat()
            }
            
            print(f"✅ LLM 검증 완료: {product_code}")
            return validated_data
            
        except Exception as e:
            print(f"⚠️ LLM 검증 실패 ({product_code}): {e}")
            return extracted_data
    
    def extract_keywords_for_product(self, product_code: str, use_llm: Optional[bool] = None) -> Dict:
        """제품 키워드 자동 추출 (하이브리드 접근)"""
        # 캐시 확인
        if product_code in self.cache:
            cached = self.cache[product_code]
            print(f"📦 캐시에서 로드: {product_code}")
            return cached
        
        # 제품 데이터 로드
        chunks = self.load_product_data(product_code)
        if not chunks:
            print(f"⚠️ 제품 데이터 없음: {product_code}")
            return {}
        
        print(f"🔍 키워드 추출 시작: {product_code}")
        
        # 1단계: 자동 추출
        categories = self.extract_categories_from_data(chunks)
        product_keywords = self.extract_product_keywords(chunks)
        info_keywords = self.extract_info_keywords(chunks, categories)
        
        extracted_data = {
            "product_keywords": product_keywords,
            "categories": sorted(list(categories)),
            "info_keywords": info_keywords,
            "auto_generated": True,
            "last_updated": datetime.now().isoformat()
        }
        
        # 2단계: LLM 검증 (선택)
        should_use_llm = use_llm if use_llm is not None else self.use_llm
        if should_use_llm:
            extracted_data = self.validate_with_llm(product_code, extracted_data)
        
        # 3단계: 캐시 저장
        self.cache[product_code] = extracted_data
        self._save_cache()
        
        print(f"✅ 키워드 추출 완료: {product_code}")
        return extracted_data
    
    def extract_all_products(self, use_llm: Optional[bool] = None):
        """모든 제품에 대해 키워드 추출"""
        if not self.products_dir.exists():
            print(f"❌ 제품 디렉토리 없음: {self.products_dir}")
            return
        
        jsonl_files = list(self.products_dir.glob("*.jsonl"))
        print(f"📦 총 {len(jsonl_files)}개 제품 발견")
        
        for jsonl_file in jsonl_files:
            product_code = jsonl_file.stem
            if product_code == "DOC-GDE":  # 가이드 문서 제외
                continue
            
            self.extract_keywords_for_product(product_code, use_llm)
        
        print(f"✅ 모든 제품 키워드 추출 완료")
    
    def get_keywords(self, product_code: str) -> Dict:
        """캐시된 키워드 가져오기 (없으면 자동 추출)"""
        if product_code in self.cache:
            return self.cache[product_code]
        
        # 자동 추출
        return self.extract_keywords_for_product(product_code)
    
    def update_keywords(self, product_code: str, keywords: Dict):
        """키워드 수동 업데이트"""
        keywords["auto_generated"] = False
        keywords["last_updated"] = datetime.now().isoformat()
        self.cache[product_code] = keywords
        self._save_cache()
        print(f"✅ 키워드 업데이트 완료: {product_code}")


# CLI 도구
if __name__ == "__main__":
    import sys
    
    extractor = ProductKeywordExtractor(use_llm=True)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "all":
            # 모든 제품 추출
            extractor.extract_all_products(use_llm=True)
        else:
            # 특정 제품 추출
            product_code = sys.argv[1]
            result = extractor.extract_keywords_for_product(product_code, use_llm=True)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("사용법:")
        print("  python -m app.services.product_keyword_extractor <product_code>  # 특정 제품")
        print("  python -m app.services.product_keyword_extractor all            # 모든 제품")

