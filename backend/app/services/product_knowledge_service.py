"""
제품 지식 베이스 서비스 (Product Knowledge Base Service)

products/*.jsonl 파일을 로드하여 제품 정보 검색 및 검증 기능 제공
- 키워드 기반 검색
- 의미적 유사도 계산
- LLM 기반 사실 검증 (선택)

용어 정리:
- Product Knowledge Base: 제품 정보 저장소 (JSONL 파일)
- RAG (Retrieval-Augmented Generation): 검색 증강 생성 (별도 시스템)
- Knowledge Verification: 제품 지식 검증 프로세스
"""
import json
import re
import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.config import settings

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("⚠️ NumPy 없음 - 임베딩 유사도 계산 시 SequenceMatcher 사용")

try:
    from app.services.embedding_service import embed_text_sync
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    print("⚠️ EmbeddingService 없음 - 임베딩 유사도 비활성화")


# ProductChunk는 딕셔너리로 표현 (유연한 필드 지원)
# 필수 필드: id, product_code, text, breadcrumb
# 선택 필드: chunking, legal_references 등


@dataclass
class ProductFactCheck:
    """제품 정보 팩트 체크 결과"""
    claim: str  # 사용자가 말한 내용
    ground_truth: str  # Knowledge Base에서 찾은 정답
    is_accurate: bool  # 정확성 여부
    similarity_score: float  # 유사도 점수 (0-1)
    product_code: str
    category: str  # 금리, 한도, 조건 등
    verification_method: str = "keyword"  # keyword, semantic, llm
    llm_reasoning: Optional[str] = None  # LLM 검증 이유 (선택)
    full_utterance: Optional[str] = None  # 전체 발화 (문맥 보존)


class ProductKnowledgeService:
    """
    제품 지식 베이스 서비스 (Product Knowledge Base Service)
    
    제품 정보를 로드하고 검증하는 서비스
    - Keyword-based Search: 키워드 매칭
    - Semantic Similarity: 의미적 유사도
    - LLM Verification: GPT 기반 사실 검증 (선택)
    """
    
    def __init__(self, data_path: Optional[Path] = None, use_llm: bool = True):
        """
        초기화
        
        Args:
            data_path: 데이터 디렉토리 경로 (기본: backend/data)
            use_llm: LLM 기반 검증 사용 여부 (기본: True)
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
        self.product_knowledge: Dict[str, List[Dict]] = {}  # ProductChunk를 Dict로 변경
        self.product_catalog = None
        
        # LLM 설정
        self.use_llm = use_llm and OPENAI_AVAILABLE
        self.openai_client = None
        
        if self.use_llm:
            api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
            if api_key:
                try:
                    self.openai_client = OpenAI(api_key=api_key)
                    print("✅ LLM 검증 활성화 (GPT-4 사용)")
                except Exception as e:
                    print(f"⚠️ OpenAI 초기화 실패: {e}")
                    self.use_llm = False
            else:
                print("⚠️ OPENAI_API_KEY 없음 - LLM 검증 비활성화")
                self.use_llm = False
        
        # 임베딩 기반 Semantic 유사도 설정
        self.use_embedding = EMBEDDING_AVAILABLE and NUMPY_AVAILABLE
        self.embedding_cache: Dict[str, List[float]] = {}  # 임베딩 캐시 (성능 최적화)
        
        if self.use_embedding:
            print("✅ 임베딩 기반 Semantic 유사도 활성화")
        else:
            print("⚠️ 임베딩 비활성화 - SequenceMatcher 사용")
        
        # 초기 로드
        self._load_all_products()
        self._load_product_catalog()
    
    def _load_all_products(self):
        """모든 제품 jsonl 파일 로드"""
        if not self.products_dir.exists():
            print(f"⚠️ 제품 디렉토리 없음: {self.products_dir}")
            return
        
        print(f"📦 제품 지식 로드 시작: {self.products_dir}")
        
        for jsonl_file in self.products_dir.glob("*.jsonl"):
            product_code = jsonl_file.stem  # CRD-CRE, DEP-TIM 등
            chunks = []
            
            try:
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():  # 빈 줄 건너뛰기
                            data = json.loads(line.strip())
                            chunks.append(data)  # 딕셔너리 그대로 저장
                
                self.product_knowledge[product_code] = chunks
                print(f"  ✓ {product_code}: {len(chunks)}개 청크")
            
            except Exception as e:
                print(f"  ✗ {product_code} 로드 실패: {e}")
        
        print(f"✅ 총 {len(self.product_knowledge)}개 제품 로드 완료")
    
    def _load_product_catalog(self):
        """제품 카탈로그 로드"""
        catalog_path = self.data_path / "product_catalog.json"
        
        if not catalog_path.exists():
            print(f"⚠️ 제품 카탈로그 없음: {catalog_path}")
            return
        
        try:
            with open(catalog_path, 'r', encoding='utf-8') as f:
                self.product_catalog = json.load(f)
            print(f"✅ 제품 카탈로그 로드: {len(self.product_catalog.get('products', []))}개")
        except Exception as e:
            print(f"❌ 제품 카탈로그 로드 실패: {e}")
    
    def _get_category_keywords_for_subsection(self, category: str) -> List[str]:
        """
        카테고리 → subsection_title 매칭 키워드 반환
        
        Args:
            category: 정보 카테고리 (예: "금리", "한도", "가입금액")
        
        Returns:
            subsection_title에서 매칭할 키워드 리스트
        """
        category_mapping = {
            "금리": ["금리", "이자율", "기본금리", "우대금리", "최고금리", "적용금리"],
            "한도": ["한도", "신용한도", "최대", "최소", "한도"],
            "가입금액": ["가입금액", "가입 금액", "최소", "최대", "납입금액", "납입 금액"],
            "기간": ["기간", "만기", "계약기간", "거치기간", "가입 기간", "계약 기간"],
            "우대금리": ["우대금리", "우대 금리", "우대"],
            "수수료": ["수수료", "연회비", "수수료", "중도상환", "중도해지"],
            "혜택": ["혜택", "할인", "포인트", "적립", "서비스"],
            "이자지급": ["이자지급", "이자 지급", "이자 계산", "이자 계산 및 지급"],
            "예금자보호": ["예금자보호", "예금자 보호", "보호"],
            "필요서류": ["필요서류", "필요 서류", "서류"],
            "상환방식": ["상환방식", "상환 방식", "원리금", "원금"],
            "신용등급": ["신용등급", "신용 등급", "등급"],
            "LTV": ["LTV", "담보인정비율", "담보 인정 비율"],
            "DTI": ["DTI", "총부채상환비율"],
            "DSR": ["DSR", "총부채원리금상환비율"],
            "환율": ["환율", "환전", "외환"],
        }
        return category_mapping.get(category, [category])  # 기본값: 카테고리 자체
    
    def _category_matches_subsection(self, category: str, subsection_title: str) -> bool:
        """
        카테고리가 subsection_title과 매칭되는지 확인
        
        Args:
            category: 정보 카테고리
            subsection_title: 청크의 subsection_title
        
        Returns:
            매칭 여부
        """
        if not subsection_title:
            return False
        
        keywords = self._get_category_keywords_for_subsection(category)
        subsection_lower = subsection_title.lower()
        
        # 키워드 중 하나라도 subsection_title에 포함되면 매칭
        return any(keyword.lower() in subsection_lower for keyword in keywords)
    
    def search_by_keyword(
        self, 
        query: str,
        category: Optional[str] = None,  # 카테고리 추가
        product_codes: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[Dict]:
        """
        키워드 기반 제품 정보 검색 (구조화된 필드 활용 개선 버전)
        
        개선 사항:
        - 카테고리 기반 subsection_title 우선 매칭
        - 쿼리를 키워드로 분리하여 부분 매칭 지원
        - 숫자와 텍스트를 분리하여 검색
        - 여러 키워드 매칭 시 관련도 점수 증가
        
        Args:
            query: 검색 쿼리 (예: "금리 연 2.15%")
            category: 정보 카테고리 (예: "금리", "한도", "가입금액") - 구조화된 매칭에 사용
            product_codes: 검색할 제품 코드 리스트 (None이면 전체)
            top_k: 반환할 최대 결과 수
        
        Returns:
            관련 제품 청크 리스트 (관련도 점수 높은 순)
        """
        results = []
        query_lower = query.lower()
        
        # 검색 대상 필터링
        search_space = (
            {k: v for k, v in self.product_knowledge.items() if k in product_codes}
            if product_codes
            else self.product_knowledge
        )
        
        # 쿼리를 키워드로 분리 (숫자, 카테고리, 주요 단어)
        query_keywords = self._extract_search_keywords(query)
        
        for product_code, chunks in search_space.items():
            for chunk in chunks:
                # 텍스트 매칭
                chunk_text = chunk.get("text", "")
                subsection = chunk.get("subsection_title", "")
                part_title = chunk.get("part_title", "")
                chunk_text_lower = chunk_text.lower()
                subsection_lower = subsection.lower()
                part_title_lower = part_title.lower()
                
                score = 0.0
                match_type = None
                
                # === 1단계: 카테고리 기반 subsection_title 매칭 (최우선) ===
                if category and self._category_matches_subsection(category, subsection):
                    # 카테고리 매칭: 매우 높은 우선순위
                    score = 1.0
                    match_type = "category_subsection"
                    
                    # 추가 점수: 쿼리 키워드도 매칭되면
                    matched_query_keywords = sum(1 for kw in query_keywords if kw in chunk_text_lower or kw in subsection_lower)
                    if matched_query_keywords > 0:
                        score = min(1.0, score + 0.1 * (matched_query_keywords / len(query_keywords)))
                
                # === 2단계: 전체 쿼리 포함 여부 확인 ===
                elif query_lower in chunk_text_lower or query_lower in subsection_lower:
                    score = self._calculate_relevance_score(query, chunk_text)
                    match_type = "full_query"
                
                # === 3단계: 키워드 부분 매칭 ===
                else:
                    matched_keywords = []
                    for keyword in query_keywords:
                        if keyword in chunk_text_lower or keyword in subsection_lower or keyword in part_title_lower:
                            matched_keywords.append(keyword)
                    
                    if matched_keywords:
                        match_ratio = len(matched_keywords) / len(query_keywords) if query_keywords else 0
                        # 최소 50% 이상 매칭되어야 함 (또는 숫자가 포함되어야 함)
                        has_number = any(char.isdigit() for char in query)
                        if match_ratio >= 0.5 or (has_number and any(char.isdigit() for kw in matched_keywords for char in kw)):
                            # 관련도 점수: 매칭 비율 기반
                            score = match_ratio * 0.7  # 부분 매칭은 최대 0.7점
                            match_type = "partial_keyword"
                            
                            # 숫자가 정확히 매칭되면 추가 점수
                            if has_number:
                                query_numbers = self._extract_numbers(query)
                                chunk_numbers = self._extract_numbers(chunk_text)
                                if query_numbers and chunk_numbers:
                                    # 숫자가 일치하면 추가 점수
                                    if any(qn in cn for qn in query_numbers for cn in chunk_numbers):
                                        score = min(0.9, score + 0.2)
                
                # 점수가 있는 경우에만 결과에 추가
                if score > 0:
                    results.append((score, chunk))
        
        # RAG 데이터가 없고 product_codes가 지정된 경우, product_catalog에서 fallback 검색
        if not results and product_codes and self.product_catalog:
            for product_code in product_codes:
                product_info = self._get_product_from_catalog(product_code)
                if product_info:
                    # product_catalog 정보를 청크 형식으로 변환
                    catalog_chunk = {
                        "text": self._format_catalog_as_text(product_info),
                        "product": product_info.get("name", ""),
                        "product_code": product_code,
                        "subsection_title": "",
                        "source": "product_catalog"
                    }
                    score = self._calculate_relevance_score(query, catalog_chunk["text"])
                    results.append((score, catalog_chunk))
        
        # 점수순 정렬 후 상위 k개 반환
        results.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in results[:top_k]]
    
    def _get_product_from_catalog(self, product_code: str) -> Optional[Dict]:
        """product_catalog에서 제품 정보 가져오기"""
        if not self.product_catalog:
            return None
        
        products = self.product_catalog.get("products", [])
        for product in products:
            if product.get("code") == product_code:
                return product
        return None
    
    def _format_catalog_as_text(self, product_info: Dict) -> str:
        """product_catalog 정보를 텍스트로 포맷팅"""
        parts = []
        
        if product_info.get("name"):
            parts.append(f"제품명: {product_info['name']}")
        
        if product_info.get("description"):
            parts.append(f"설명: {product_info['description']}")
        
        if product_info.get("features"):
            features = ", ".join(product_info["features"])
            parts.append(f"주요 특징: {features}")
        
        if product_info.get("keywords"):
            keywords = ", ".join(product_info["keywords"])
            parts.append(f"관련 키워드: {keywords}")
        
        return " ".join(parts)
    
    def _calculate_relevance_score(self, query: str, text: str) -> float:
        """간단한 관련도 점수 계산"""
        query_lower = query.lower()
        text_lower = text.lower()
        
        # 완전 일치
        if query_lower == text_lower:
            return 1.0
        
        # 포함 여부
        if query_lower in text_lower:
            return 0.8
        
        # SequenceMatcher 유사도
        return SequenceMatcher(None, query_lower, text_lower).ratio()
    
    def extract_product_facts_from_conversation(
        self, 
        conversation: List[Dict]
    ) -> List[Dict]:
        """
        대화에서 제품 관련 사실(Fact) 추출
        
        Args:
            conversation: [{"role": "employee"|"customer", "text": "..."}]
        
        Returns:
            [
                {
                    "claim": "정기예금 금리는 연 2.5%입니다",
                    "product_code": "DEP-TIM",
                    "category": "금리",
                    "keywords": ["정기예금", "금리", "2.5%"]
                }
            ]
        """
        facts = []
        employee_utterances = [msg["text"] for msg in conversation if msg.get("role") == "employee"]
        
        # 제품별 키워드 매핑 (총 15개 상품, DOC-GDE 제외)
        product_keywords = {
            # 예금 상품
            "DEP-TIM": ["정기예금", "정기 예금", "만기예금"],
            "DEP-FLX": ["자유적금", "자유 적금"],
            "DEP-MMD": ["입출금자유", "자유통장", "입출금 통장", "MMDA", "MMA"],
            # 적금 상품
            "SAV-FIX": ["정기적금", "정기 적금"],
            "SAV-FRE": ["자유적금", "자유 적금"],  # DEP-FLX와 유사하지만 별도 상품
            # 카드 상품
            "CRD-CRE": ["신용카드", "프리미엄 카드", "신용 카드"],
            "CRD-DEB": ["체크카드", "체크 카드"],
            "CRD-YTH": ["청년카드", "청년 카드", "청년"],
            # 대출 상품
            "LON-MTG": ["주택담보대출", "주택담보", "주택 담보 대출"],
            "LON-STU": ["학자금대출", "학자금", "학생 대출"],
            "LON-DCL": ["신용대출", "무담보대출", "직장인 대출", "예금담보대출"],
            "LON-JNS": ["전세자금대출", "전세자금", "전세 대출", "전세"],
            "LON-ODL": ["마이너스통장", "마이너스 통장", "마통"],
            "LON-UNS": ["신용대출", "무담보대출"],  # LON-DCL과 유사하지만 별도 상품
            "LON-YHP": ["청년희망대출", "청년희망", "청년 대출", "청년희망"],
            # 외환 상품 (현재 파일 없음, 향후 추가 가능)
            # "FX001": ["외환", "외환상품", "환전", "외화거래"],
            # "FX002": ["송금", "송금서비스", "해외송금", "해외 송금", "해외송금서비스"],
        }
        
        # 상품별 중요 정보 카테고리 (우선순위 높은 정보만 추출)
        product_category_priority = {
            # 예금 상품
            "DEP-MMD": ["금리", "가입금액", "우대금리", "이자지급", "예금자보호", "한도"],  # 입출금 자유는 키워드로만
            "DEP-TIM": ["금리", "기간", "가입금액", "우대금리", "이자지급", "예금자보호"],
            "DEP-FLX": ["금리", "가입금액", "우대금리", "기간", "이자지급", "예금자보호"],
            # 적금 상품
            "SAV-FRE": ["금리", "가입금액", "우대금리", "기간", "이자지급", "예금자보호"],
            "SAV-FIX": ["금리", "가입금액", "우대금리", "기간", "이자지급", "예금자보호"],
            # 대출 상품
            "LON-MTG": ["금리", "한도", "기간", "LTV", "DTI", "DSR", "상환방식", "우대금리", "필요서류"],
            "LON-DCL": ["금리", "한도", "기간", "상환방식", "가입금액"],  # 예금잔액의 95%
            "LON-STU": ["금리", "한도", "기간", "조건", "필요서류"],
            "LON-UNS": ["금리", "한도", "기간", "신용등급", "필요서류"],
            "LON-JNS": ["금리", "한도", "기간", "LTV", "상환방식", "필요서류"],  # 전세자금대출
            "LON-ODL": ["금리", "한도", "이자지급", "수수료"],  # 마이너스통장
            "LON-YHP": ["금리", "한도", "기간", "조건", "필요서류"],  # 청년희망대출
            # 카드 상품
            "CRD-CRE": ["한도", "수수료", "혜택", "신용등급", "이자지급"],  # 연회비, 할인율 등
            "CRD-DEB": ["한도", "수수료", "혜택"],
            "CRD-YTH": ["한도", "수수료", "혜택", "조건"],  # 청년카드
            # 외환 상품 (현재 파일 없음, 향후 추가 가능)
            # "FX001": ["환율", "수수료", "한도"],
            # "FX002": ["환율", "수수료", "한도"],
        }
        
        # 정보 카테고리 패턴
        category_patterns = {
            "금리": [r"금리\s*(?:는|:)?\s*([\d\.]+)%?", r"이자율?\s*([\d\.]+)%?", r"연\s*([\d\.]+)%"],
            "한도": [r"한도\s*(?:는|:)?\s*([\d,]+)원?", r"최대\s*([\d,]+)원?", r"([\d,]+)만원까지", r"최소\s*([\d,]+)원?"],
            "기간": [r"기간\s*(?:은|는)?\s*([\d]+)(?:개월|년)", r"만기\s*([\d]+)(?:개월|년)", r"거치기간\s*([\d]+)(?:개월|년)?"],
            "조건": [r"조건\s*(?:은|는)?", r"자격\s*(?:은|는)?", r"대상\s*(?:은|는)?"],
            "수수료": [r"수수료\s*([\d,]+)원?", r"수수료\s*면제", r"무료", r"수수료\s*([\d]+)원대", r"수수료\s*([\d]+)원\s*대", r"중도상환\s*수수료", r"중도해지\s*수수료"],
            "환율": [r"환율\s*(?:은|는)?\s*([\d,\.]+)", r"환율\s*우대\s*([\d\.]+)%?", r"우대율\s*([\d\.]+)%?", r"([\d\.]+)%\s*우대", r"환율\s*([\d\.]+)%"],
            "혜택": [r"혜택", r"할인", r"포인트", r"적립"],
            # 추가된 핵심 정보 패턴
            "우대금리": [r"우대금리\s*(?:는|:)?\s*([\d\.]+)%?", r"우대\s*([\d\.]+)%?p?", r"최대\s*([\d\.]+)%?p?\s*추가", r"최대\s*([\d\.]+)%?p?\s*차감", r"([\d\.]+)%?p?\s*우대"],
            "LTV": [r"LTV\s*(?:는|:)?\s*([\d]+)%?", r"담보인정비율\s*(?:은|는)?\s*([\d]+)%?", r"담보\s*인정\s*비율\s*([\d]+)%?"],
            "DTI": [r"DTI\s*(?:는|:)?\s*([\d]+)%?", r"총부채상환비율\s*(?:은|는)?\s*([\d]+)%?"],
            "DSR": [r"DSR\s*(?:는|:)?\s*([\d]+)%?", r"총부채원리금상환비율\s*(?:은|는)?\s*([\d]+)%?"],
            "상환방식": [r"상환\s*방식", r"원리금균등", r"원금균등", r"체증식", r"거치식", r"원리금\s*균등", r"원금\s*균등"],
            "신용등급": [r"신용등급\s*(?:은|는)?\s*([\d]+)\s*등급", r"([\d]+)\s*등급", r"신용\s*등급\s*([\d]+)"],
            "이자지급": [r"이자\s*지급", r"매월\s*이자", r"만기\s*이자", r"이자소득세\s*([\d\.]+)%?", r"이자\s*납부"],
            "예금자보호": [r"예금자보호", r"보호한도\s*([\d,]+)원?", r"([\d,]+)원\s*보호", r"5천만원\s*보호"],
            "필요서류": [r"필요\s*서류", r"등기부등본", r"감정평가서", r"소득증빙", r"재직증명서", r"신분증"],
            "가입금액": [r"가입금액\s*(?:은|는)?\s*([\d,]+)원?", r"최소\s*가입\s*([\d,]+)원?", r"([\d,]+)만원\s*부터"],
        }
        
        for utterance in employee_utterances:
            # 언급된 제품 감지
            mentioned_products = []
            for product_code, keywords in product_keywords.items():
                if any(keyword in utterance for keyword in keywords):
                    mentioned_products.append(product_code)
            
            # 상품별 우선순위 카테고리 결정
            # 언급된 상품이 있으면 해당 상품의 우선 카테고리만, 없으면 모든 카테고리 검사
            categories_to_check = set()
            if mentioned_products:
                for product_code in mentioned_products:
                    if product_code in product_category_priority:
                        categories_to_check.update(product_category_priority[product_code])
            else:
                # 상품이 감지되지 않으면 모든 카테고리 검사
                categories_to_check = set(category_patterns.keys())
            
            # 정보 카테고리 추출 (우선순위 카테고리만)
            for category in categories_to_check:
                if category not in category_patterns:
                    continue
                patterns = category_patterns[category]
                for pattern in patterns:
                    matches = re.finditer(pattern, utterance)
                    for match in matches:
                        # claim 추출: 매칭된 부분의 앞뒤 문맥을 포함하여 더 정확한 claim 생성
                        matched_text = match.group(0)
                        match_start = match.start()
                        match_end = match.end()
                        
                        # 앞뒤로 최대 10글자씩 포함하여 문맥 보존
                        context_start = max(0, match_start - 10)
                        context_end = min(len(utterance), match_end + 10)
                        claim_with_context = utterance[context_start:context_end].strip()
                        
                        # claim은 매칭된 부분을 포함하되, 문맥이 있으면 문맥 포함
                        # 단, 너무 길면 매칭된 부분만 사용
                        if len(claim_with_context) <= 50:
                            claim = claim_with_context
                        else:
                            claim = matched_text
                        
                        fact = {
                            "claim": claim,
                            "full_utterance": utterance,
                            "product_codes": mentioned_products if mentioned_products else ["UNKNOWN"],
                            "category": category,
                            "matched_value": match.group(1) if match.lastindex and match.lastindex >= 1 else None
                        }
                        facts.append(fact)
        
        return facts
    
    def verify_fact_accuracy(
        self, 
        claim: str,
        product_code: str,
        category: str,
        use_llm: Optional[bool] = None
    ) -> ProductFactCheck:
        """
        제품 정보 사실 확인 (3단계 검증)
        
        1. Keyword Matching: 키워드 기반 청크 검색
        2. Semantic Similarity: 의미적 유사도 계산
        3. LLM Verification: GPT 기반 논리적 검증 (선택)
        
        Args:
            claim: 검증할 주장 (예: "금리는 연 2.5%입니다")
            product_code: 제품 코드
            category: 정보 카테고리 (금리, 한도 등)
            use_llm: LLM 검증 사용 여부 (None이면 인스턴스 설정 따름)
        
        Returns:
            팩트 체크 결과
        """
        # LLM 사용 여부 결정
        should_use_llm = use_llm if use_llm is not None else self.use_llm
        
        # full_utterance는 fact에서 가져오기 (batch_verify_conversation에서 전달)
        # 여기서는 None으로 설정하고, batch_verify_conversation에서 설정
        full_utterance = getattr(self, '_current_full_utterance', None)
        
        # 해당 제품의 관련 청크 검색 (카테고리 활용)
        relevant_chunks = self.search_by_keyword(
            query=claim,  # claim만 사용 (category는 별도 파라미터로)
            category=category,  # 카테고리를 별도로 전달하여 구조화된 매칭
            product_codes=[product_code] if product_code != "UNKNOWN" else None,
            top_k=3
        )
        
        if not relevant_chunks:
            return ProductFactCheck(
                claim=claim,
                ground_truth="",
                is_accurate=False,
                similarity_score=0.0,
                product_code=product_code,
                category=category,
                verification_method="keyword",
                full_utterance=full_utterance
            )
        
        # === 1단계: Keyword Matching + Semantic Similarity ===
        best_chunk = relevant_chunks[0]
        best_chunk_text = best_chunk.get("text", "")
        similarity_score = self._semantic_similarity(claim, best_chunk_text)
        
        # === 🚨 중요: 숫자 정보 추출 및 정확도 비교 (필수) ===
        claim_numbers = self._extract_numbers(claim)
        truth_numbers = self._extract_numbers(best_chunk_text)
        
        # 숫자 정확도 검증 (숫자가 있으면 반드시 비교)
        numbers_match = True
        if claim_numbers and truth_numbers:
            # 주장과 정답 모두에 숫자가 있는 경우: 정확히 일치해야 함
            # 허용 오차: 0.01 (소수점 둘째 자리까지 정확)
            # 빈 문자열 필터링
            claim_numbers_clean = [n for n in claim_numbers if n.strip()]
            truth_numbers_clean = [n for n in truth_numbers if n.strip()]
            
            if claim_numbers_clean and truth_numbers_clean:
                numbers_match = any(
                    abs(float(claim_num) - float(truth_num)) < 0.01
                    for claim_num in claim_numbers_clean
                    for truth_num in truth_numbers_clean
                )
            else:
                # 숫자가 추출되었지만 빈 문자열인 경우: 비교 불가
                numbers_match = False
        elif claim_numbers and not truth_numbers:
            # 주장에만 숫자가 있고 정답에 없으면: 부정확 (숫자 정보가 잘못되었을 가능성)
            numbers_match = False
        elif not claim_numbers and truth_numbers:
            # 주장에 숫자가 없고 정답에 있으면: 정보 부족 (부정확으로 간주)
            numbers_match = False
        
        # === 초기 정확도 판단 (숫자 정확도 우선) ===
        if claim_numbers or truth_numbers:
            # 숫자가 있는 경우: 숫자 정확도가 최우선
            # 숫자가 다르면 유사도가 높아도 부정확
            is_accurate_heuristic = numbers_match
            if not numbers_match:
                # 숫자가 다르면 유사도 점수도 낮춤 (명확한 오류)
                similarity_score = min(similarity_score, 0.5)
        else:
            # 숫자가 없는 경우: 유사도만으로 판단
            # 임베딩 사용 시: 0.75 이상, SequenceMatcher 사용 시: 0.7 이상
            threshold = 0.75 if self.use_embedding else 0.7
            is_accurate_heuristic = similarity_score >= threshold
        
        # === 2단계: LLM Verification (선택) ===
        if should_use_llm and self.openai_client:
            llm_result = self._verify_with_llm(claim, best_chunk_text, category, product_code)
            
            if llm_result["success"]:
                # LLM 결과 우선 사용
                return ProductFactCheck(
                    claim=claim,
                    ground_truth=best_chunk_text,
                    is_accurate=llm_result["is_accurate"],
                    similarity_score=llm_result["confidence"],
                    product_code=product_code,
                    category=category,
                    verification_method="llm",
                    llm_reasoning=llm_result["reasoning"],
                    full_utterance=full_utterance
                )
        
        # LLM 사용 안 하거나 실패 시 휴리스틱 결과 사용
        return ProductFactCheck(
            claim=claim,
            ground_truth=best_chunk_text,
            is_accurate=is_accurate_heuristic,
            similarity_score=similarity_score,
            product_code=product_code,
            category=category,
            verification_method="semantic" if self.use_embedding else "keyword",
            full_utterance=full_utterance
        )
    
    def _verify_with_llm(
        self, 
        claim: str, 
        ground_truth: str, 
        category: str,
        product_code: str
    ) -> Dict:
        """
        LLM 기반 사실 검증
        
        Args:
            claim: 사용자 주장
            ground_truth: 제품 지식 베이스의 정답
            category: 정보 카테고리
            product_code: 제품 코드
        
        Returns:
            {
                "success": True,
                "is_accurate": True/False,
                "confidence": 0.95,
                "reasoning": "..."
            }
        """
        try:
            prompt = f"""제품 정보 사실 검증을 수행하세요.

**제품 코드:** {product_code}
**카테고리:** {category}

**사용자 주장 (Claim):**
{claim}

**제품 지식 베이스 정보 (Ground Truth):**
{ground_truth}

**검증 지침:**
1. 사용자 주장이 제품 지식 베이스 정보와 일치하는지 확인
2. 숫자 정보(금리, 한도 등)는 정확히 일치해야 함
3. 의미적으로 동일하면 정확하다고 판단
4. 모호하거나 불확실한 표현("같아요", "아마도")은 부정확으로 판단

**출력 형식 (JSON):**
{{
  "is_accurate": true/false,
  "confidence": 0.0~1.0,
  "reasoning": "판단 근거 설명"
}}

JSON으로만 응답하세요."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 은행 제품 정보 검증 전문가입니다. 사용자 주장과 실제 제품 정보를 비교하여 정확성을 판단합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            return {
                "success": True,
                "is_accurate": result.get("is_accurate", False),
                "confidence": result.get("confidence", 0.0),
                "reasoning": result.get("reasoning", "")
            }
            
        except Exception as e:
            print(f"⚠️ LLM 검증 실패: {e}")
            return {
                "success": False,
                "is_accurate": False,
                "confidence": 0.0,
                "reasoning": f"LLM 검증 오류: {str(e)}"
            }
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        코사인 유사도 계산
        
        Args:
            vec1: 첫 번째 벡터 (임베딩 벡터)
            vec2: 두 번째 벡터 (임베딩 벡터)
        
        Returns:
            유사도 점수 (0.0 ~ 1.0)
        
        알고리즘:
            cosine_similarity = (vec1 · vec2) / (||vec1|| × ||vec2||)
        """
        if not NUMPY_AVAILABLE:
            # NumPy 없으면 간단한 계산
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm_a = sum(a * a for a in vec1) ** 0.5
            norm_b = sum(b * b for b in vec2) ** 0.5
        else:
            # NumPy 사용 (더 빠름)
            a = np.array(vec1)
            b = np.array(vec2)
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        similarity = dot_product / (norm_a * norm_b)
        # 임베딩은 보통 0~1 범위이지만, 음수 나올 수 있으므로 클리핑
        return max(0.0, min(1.0, similarity))
    
    def _semantic_similarity_embedding(self, text1: str, text2: str) -> float:
        """
        임베딩 기반 의미적 유사도 계산
        
        Args:
            text1: 첫 번째 텍스트
            text2: 두 번째 텍스트
        
        Returns:
            유사도 점수 (0.0 ~ 1.0)
        
        프로세스:
            1. 텍스트를 임베딩 벡터로 변환 (캐시 활용)
            2. 코사인 유사도 계산
        """
        try:
            # 캐시에서 임베딩 가져오기 (성능 최적화)
            if text1 not in self.embedding_cache:
                self.embedding_cache[text1] = embed_text_sync(text1)
            if text2 not in self.embedding_cache:
                self.embedding_cache[text2] = embed_text_sync(text2)
            
            vec1 = self.embedding_cache[text1]
            vec2 = self.embedding_cache[text2]
            
            # 코사인 유사도 계산
            return self._cosine_similarity(vec1, vec2)
        except Exception as e:
            print(f"⚠️ 임베딩 계산 실패: {e}")
            raise
    
    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """
        의미적 유사도 계산
        
        우선순위:
        1. 임베딩 기반 (가능하면)
        2. SequenceMatcher (fallback)
        
        Args:
            text1: 첫 번째 텍스트
            text2: 두 번째 텍스트
        
        Returns:
            유사도 점수 (0.0 ~ 1.0)
        """
        if self.use_embedding:
            try:
                return self._semantic_similarity_embedding(text1, text2)
            except Exception as e:
                # Fallback: 기존 방식
                print(f"⚠️ 임베딩 실패, SequenceMatcher 사용: {e}")
                return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
        else:
            # 기존 방식 (SequenceMatcher)
            return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _extract_search_keywords(self, query: str) -> List[str]:
        """
        검색 쿼리에서 키워드 추출
        
        예시:
        "금리 연 2.15%" → ["금리", "연", "2.15%", "2.15"]
        "최소 50만원부터" → ["최소", "50만원", "50", "만원", "부터"]
        """
        keywords = []
        query_lower = query.lower()
        
        # 1. 숫자 추출 (소수점 포함)
        numbers = self._extract_numbers(query)
        keywords.extend(numbers)
        
        # 2. 숫자 + 단위 조합 (예: "2.15%", "50만원")
        number_patterns = re.findall(r'[\d,]+\.?\d*[%만원개월년]?', query)
        keywords.extend([p.replace(',', '') for p in number_patterns])
        
        # 3. 주요 단어 추출 (불용어 제외)
        stopwords = {"은", "는", "이", "가", "을", "를", "에", "의", "로", "으로", "와", "과", "도", "만", "부터", "까지", "에서", "에게", "한테", "연", "년"}
        words = re.findall(r'[가-힣]+', query)
        keywords.extend([w for w in words if w not in stopwords and len(w) > 1])
        
        # 4. 카테고리 키워드 (금리, 한도, 기간 등)
        category_keywords = ["금리", "이자율", "한도", "기간", "만기", "가입금액", "수수료", "우대금리", "최고금리", "기본금리"]
        for cat_kw in category_keywords:
            if cat_kw in query:
                keywords.append(cat_kw)
        
        # 중복 제거 및 정리
        keywords = list(set([k.strip() for k in keywords if k.strip()]))
        
        return keywords
    
    def _extract_numbers(self, text: str) -> List[str]:
        """텍스트에서 숫자 추출"""
        # 콤마 포함 숫자, 소수점 숫자 모두 추출
        numbers = re.findall(r'[\d,]+\.?\d*', text)
        # 빈 문자열 제거 및 정리
        cleaned = [num.replace(',', '').strip() for num in numbers if num.strip()]
        return cleaned
    
    def batch_verify_conversation(
        self, 
        conversation: List[Dict],
        use_llm: Optional[bool] = None
    ) -> Dict:
        """
        대화 전체에 대한 제품 지식 정확도 검증
        
        Args:
            conversation: 대화 로그
            use_llm: LLM 검증 사용 여부
        
        Returns:
            {
                "facts": [...],  # 추출된 사실들
                "verifications": [...],  # 검증 결과들
                "accuracy_rate": 0.85,
                "total_claims": 10,
                "accurate_claims": 8,
                "inaccurate_claims": 2,
                "verification_methods": {"llm": 5, "semantic": 3, "keyword": 2}
            }
        """
        # 1. 대화에서 사실 추출
        facts = self.extract_product_facts_from_conversation(conversation)
        
        if not facts:
            return {
                "facts": [],
                "verifications": [],
                "accuracy_rate": 1.0,  # 정보 제공 없으면 오류도 없음
                "total_claims": 0,
                "accurate_claims": 0,
                "inaccurate_claims": 0,
                "details": {
                    "by_category": {},
                    "by_product": {}
                },
                "verification_methods": {}
            }
        
        # 2. 각 사실 검증
        verifications = []
        accurate_count = 0
        method_counts = {}
        
        for fact in facts:
            for product_code in fact["product_codes"]:
                # full_utterance를 임시로 저장하여 verify_fact_accuracy에서 사용
                self._current_full_utterance = fact.get("full_utterance")
                
                verification = self.verify_fact_accuracy(
                    claim=fact["claim"],
                    product_code=product_code,
                    category=fact["category"],
                    use_llm=use_llm
                )
                verifications.append(verification)
                
                # 임시 저장값 제거
                self._current_full_utterance = None
                
                if verification.is_accurate:
                    accurate_count += 1
                
                # 검증 방법 통계
                method = verification.verification_method
                method_counts[method] = method_counts.get(method, 0) + 1
        
        total_claims = len(verifications)
        accuracy_rate = accurate_count / total_claims if total_claims > 0 else 1.0
        
        return {
            "facts": facts,
            "verifications": verifications,
            "accuracy_rate": accuracy_rate,
            "total_claims": total_claims,
            "accurate_claims": accurate_count,
            "inaccurate_claims": total_claims - accurate_count,
            "details": {
                "by_category": self._group_by_category(verifications),
                "by_product": self._group_by_product(verifications)
            },
            "verification_methods": method_counts
        }
    
    def _group_by_category(self, verifications: List[ProductFactCheck]) -> Dict:
        """카테고리별 정확도 통계"""
        stats = {}
        for v in verifications:
            if v.category not in stats:
                stats[v.category] = {"total": 0, "accurate": 0}
            stats[v.category]["total"] += 1
            if v.is_accurate:
                stats[v.category]["accurate"] += 1
        
        # 정확도 비율 추가
        for category in stats:
            total = stats[category]["total"]
            accurate = stats[category]["accurate"]
            stats[category]["accuracy_rate"] = accurate / total if total > 0 else 0
        
        return stats
    
    def _group_by_product(self, verifications: List[ProductFactCheck]) -> Dict:
        """제품별 정확도 통계"""
        stats = {}
        for v in verifications:
            if v.product_code not in stats:
                stats[v.product_code] = {"total": 0, "accurate": 0}
            stats[v.product_code]["total"] += 1
            if v.is_accurate:
                stats[v.product_code]["accurate"] += 1
        
        # 정확도 비율 추가
        for product in stats:
            total = stats[product]["total"]
            accurate = stats[product]["accurate"]
            stats[product]["accuracy_rate"] = accurate / total if total > 0 else 0
        
        return stats
    
    def get_product_info(self, product_code: str) -> Optional[Dict]:
        """특정 제품의 모든 정보 반환"""
        if product_code not in self.product_knowledge:
            return None
        
        chunks = self.product_knowledge[product_code]
        
        return {
            "product_code": product_code,
            "product_name": chunks[0].get("product", "Unknown") if chunks else "Unknown",
            "total_chunks": len(chunks),
            "parts": self._organize_by_parts(chunks)
        }
    
    def _organize_by_parts(self, chunks: List[Dict]) -> Dict:
        """청크를 PART별로 정리"""
        parts = {}
        for chunk in chunks:
            part_no = chunk.get("part_no", 0)
            part_title = chunk.get("part_title", "Unknown")
            part_key = f"PART {part_no}: {part_title}"
            if part_key not in parts:
                parts[part_key] = []
            parts[part_key].append({
                "subsection": chunk.get("subsection_title", ""),
                "text": chunk.get("text", ""),
                "breadcrumb": chunk.get("breadcrumb", "")
            })
        return parts
