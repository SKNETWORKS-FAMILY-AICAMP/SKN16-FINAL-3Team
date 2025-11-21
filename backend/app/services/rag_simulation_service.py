"""
RAG 기반 시뮬레이션 서비스
제공된 데이터를 활용한 STT/LLM/TTS 기반 음성 시뮬레이션
"""
import json
import os
import re
import tempfile
import base64
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from sqlmodel import Session, select
import openai
from pathlib import Path

from app.config import settings
from app.models.user import User
from app.services.promptOrchestrator import (
    compose_llm_messages,
    parse_llm_response,
    get_situation_defaults
)
from app.services.banking_normalizer import normalize_text, expand_search_query
from app.services.offtopic_detector import is_on_topic, detect_offtopic_category, generate_pivot_response
from app.services.persona_voice import get_voice_params, build_ssml
from app.services.product_knowledge_service import ProductKnowledgeService

try:
    from app.services.product_keyword_extractor import ProductKeywordExtractor
    KEYWORD_EXTRACTOR_AVAILABLE = True
except ImportError:
    KEYWORD_EXTRACTOR_AVAILABLE = False
    print("⚠️ ProductKeywordExtractor 없음 - 하드코딩된 키워드 사용")


CUSTOMER_STRONG_CLOSINGS = [
    "그럼 이만",
    "그럼 이제 가볼게요",
    "다음에 또 올게요",
    "오늘 도움 많이 됐어요",
    "덕분에 잘 알겠습니다",
    "수고하세요",
    "안녕히 계세요",
    "이제 됐습니다",
    "충분합니다",
]

CUSTOMER_SOFT_CLOSINGS = [
    "감사합니다",
    "네 알겠습니다",
    "네 알겠어요",
    "더 이상 없어요",
    "없습니다",
    "괜찮습니다",
    "이제 됐어요",
    "잘 알겠습니다",
    "질문 없어요",
    "더 이상 질문",
    "충분합니다",
    "이제 됐습니다",
    "이제 끝난 건가요",
    "더 할 건 없죠",
    "그럼 끊을게요",
    "그럼 여기까지",
]

# 종료 트리거 키워드 리스트 (고객 + 신입사원 통합)
END_CONVERSATION_TRIGGERS = [
    # 신입사원 종료 트리거
    "정리해서 말씀드리면",
    "오늘 안내드린 내용은",
    "추가로 도와드릴",
    "다른 문의 없으시면",
    "상담 마무리",
    "상담 여기까지",
    "이제 마무리",
    "모든 절차가 완료",
    "처리 끝났습니다",
    "하실 일은 없습니다",
    "좋은 하루",
    "감사합니다",
    "수고하세요",
    # 고객 종료 트리거
    "질문 없어요",
    "더 이상 질문",
    "충분합니다",
    "이제 됐습니다",
    "이제 끝난 건가요",
    "더 할 건 없죠",
    "그럼 끊을게요",
    "그럼 여기까지",
]

EMPLOYEE_CLOSING_PROMPTS = [
    "더 도와드릴",
    "추가로 필요하신",
    "추가로 궁금하신",
    "또 문의",
    "다른 도움",
    "무엇을 더",
    "더 궁금한",
    "더 필요한",
    "정리해서 말씀드리면",
    "오늘 안내드린 내용은",
    "추가로 도와드릴",
    "다른 문의 없으시면",
    "상담 마무리",
    "상담 여기까지",
    "이제 마무리",
    "모든 절차가 완료",
    "처리 끝났습니다",
    "하실 일은 없습니다",
    "좋은 하루",
    "감사합니다",
    "수고하세요",
    "더 궁금하신 점",
    "더 필요하신 점",
    "더 궁금하신 점 있으세요",
    "더 필요하신 점 있으세요",
    "추가로 도와드릴 부분",
    "다른 문의는 없으신가요",
    "없으시면 상담 마무리",
    "상담은 여기까지",
    "이제 마무리 도와드릴게요",
    "이용해주셔서 감사합니다",
    "언제든 문의 주세요",
    "더 필요하신 점 있으세요",
    "더 궁금하신 점 있으세요"
]


SITUATION_DEFAULTS = {
    "deposit": {
        "id": "deposit",
        "title": "수신 상담",
        "goals": ["고객 요구사항 파악", "적합한 상품 제안", "절차 안내"],
        "required_slots": ["목적", "금액", "기간"],
        "forbidden_claims": ["원금 보장", "수익률 보장"],
        "style_rules": ["수익률은 참고용 예시로만", "실제 수익률은 차등 적용"],
        "disclaimer": "실제 수익률은 상품 조건과 시장 상황에 따라 달라질 수 있습니다."
    },
    "loan": {
        "id": "loan",
        "title": "여신 상담",
        "goals": ["대출 목적 확인", "신용도 파악", "가능한 한도 안내"],
        "required_slots": ["목적", "직업", "소득"],
        "forbidden_claims": ["심사 통과 보장", "확정 금리 보장"],
        "style_rules": ["한도/금리는 심사 결과에 따름", "필요 서류 안내"],
        "disclaimer": "대출 한도 및 금리는 심사 결과에 따라 달라질 수 있습니다."
    },
    "card": {
        "id": "card",
        "title": "카드 상담",
        "goals": ["카드 용도 파악", "적합한 혜택 제안"],
        "required_slots": ["사용 목적", "월 사용 금액"],
        "forbidden_claims": ["승인 보장"],
        "style_rules": ["혜택은 카드 종류별 상이", "연회비 안내"],
        "disclaimer": "카드 승인은 신용평가에 따라 달라질 수 있습니다."
    },
    "fx": {
        "id": "fx",
        "title": "외환/송금 상담",
        "goals": ["송금 목적 확인", "수수료 안내", "절차 설명"],
        "required_slots": ["송금 국가", "금액"],
        "forbidden_claims": ["환율 보장"],
        "style_rules": ["환율은 변동 가능", "추가 서류 확인 필요 여부 안내"],
        "disclaimer": "환율은 환전 시점의 시장 환율이 적용됩니다.",
        "has_product_data": False  # 상품 데이터 없음 - 지식 평가 방식 변경
    }
}


def get_situation_defaults(situation_id: str) -> Dict:
    return SITUATION_DEFAULTS.get(situation_id, SITUATION_DEFAULTS["deposit"])


class RAGSimulationService:
    """RAG 기반 시뮬레이션 서비스"""
    
    def __init__(self, session: Session):
        self.session = session
        # OpenAI 클라이언트 초기화 (API 키가 있을 때만)
        api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=api_key)
            except Exception as e:
                print(f"OpenAI 클라이언트 초기화 실패: {e}")
                self.openai_client = None
        else:
            self.openai_client = None
        
        # 제품 지식 서비스 초기화 (벡터 검색 활성화를 위해 session 전달)
        try:
            self.product_knowledge_service = ProductKnowledgeService(
                use_llm=True,
                session=session  # 벡터 검색 활성화
            )
            print("✅ 제품 지식 검증 서비스 초기화 완료 (벡터 검색 활성화)")
        except Exception as e:
            print(f"⚠️ 제품 지식 서비스 초기화 실패: {e}")
            self.product_knowledge_service = None
        
        # 키워드 추출기 초기화 (하이브리드 접근)
        self.keyword_extractor = None
        if KEYWORD_EXTRACTOR_AVAILABLE:
            try:
                self.keyword_extractor = ProductKeywordExtractor(data_path=self.data_path, use_llm=False)
                print("✅ 키워드 자동 추출기 초기화 완료 (RAG 평가용)")
            except Exception as e:
                print(f"⚠️ 키워드 추출기 초기화 실패: {e}")
        
        # 데이터 파일 경로 설정 (로컬/Docker 환경 모두 지원)
        # Docker 환경: /app/data
        # 로컬 환경: backend/data
        if Path("/app/data").exists():
            self.data_path = Path("/app/data")
        else:
            # 로컬 환경: 현재 파일 기준으로 상대 경로 계산
            current_file = Path(__file__)  # backend/app/services/rag_simulation_service.py
            self.data_path = current_file.parent.parent.parent / "data"  # backend/data
        
        # 데이터 캐시
        self.personas_cache = None
        self.situations_cache = None
        self.product_catalog = None
    
    def load_simulation_data(self):
        """시뮬레이션 데이터 로드"""
        try:
            print(f"📁 데이터 경로 확인: {self.data_path}")
            print(f"📁 디렉토리 존재 여부: {self.data_path.exists()}")
            
            if not self.data_path.exists():
                print(f"❌ 데이터 디렉토리가 존재하지 않습니다: {self.data_path}")
                return
            
            # 페르소나 데이터 로드 (personas_expanded_minified2.json)
            personas_file = self.data_path / "personas_expanded_minified2.json"
            print(f"📄 페르소나 파일 경로: {personas_file}")
            print(f"📄 페르소나 파일 존재 여부: {personas_file.exists()}")
            
            if personas_file.exists():
                with open(personas_file, 'r', encoding='utf-8') as f:
                    personas_data = json.load(f)
                    if 'personas' in personas_data:
                        self.personas_cache = personas_data['personas']
                    else:
                        self.personas_cache = personas_data if isinstance(personas_data, list) else []
                print(f"✅ 페르소나 데이터 로드 완료: {len(self.personas_cache) if self.personas_cache else 0}개")
            else:
                print("❌ 페르소나 파일을 찾을 수 없습니다")
            
            # 상황 데이터 로드 (1hakyung_situations_4categories_50each_with_products.txt)
            situations_file = self.data_path / "1hakyung_situations_4categories_50each_with_products.txt"
            print(f"📄 상황 파일 경로: {situations_file}")
            print(f"📄 상황 파일 존재 여부: {situations_file.exists()}")
            
            if situations_file.exists():
                try:
                    with open(situations_file, 'r', encoding='utf-8') as f:
                        situations_data = json.load(f)
                        if 'situations' in situations_data:
                            # 새로운 파일 구조: situations 배열에서 각 상황의 starter_topics를 평탄화
                            raw_situations = situations_data['situations']
                            self.situations_cache = []
                            
                            # 각 카테고리별 상황을 처리
                            for category_situation in raw_situations:
                                category_id = category_situation.get('id', '')
                                category_title = category_situation.get('title', '')
                                starter_topics = category_situation.get('starter_topics', [])
                                
                                # 각 starter_topic을 개별 상황으로 변환
                                for idx, topic in enumerate(starter_topics):
                                    situation_item = {
                                        'id': f"{category_id}_{idx}",
                                        'category_id': category_id,
                                        'category_title': category_title,
                                        'title': topic.get('title', ''),
                                        'product': topic.get('product'),
                                        'product_code': topic.get('product_code'),
                                        'intent': topic.get('intent', ''),
                                        'is_from_product_manual': topic.get('is_from_product_manual', False),
                                        'goals': topic.get('goals', []),
                                        'starter_topics': [topic]  # 호환성을 위해 유지
                                    }
                                    self.situations_cache.append(situation_item)
                            
                            print(f"✅ 상황 데이터 로드 완료: {len(self.situations_cache)}개 (카테고리 {len(raw_situations)}개에서 변환)")
                        else:
                            self.situations_cache = situations_data if isinstance(situations_data, list) else []
                            print(f"✅ 상황 데이터 로드 완료: {len(self.situations_cache) if self.situations_cache else 0}개")
                except json.JSONDecodeError as e:
                    error_msg = f"상황 파일 JSON 파싱 실패: {situations_file} - {str(e)}"
                    print(f"❌ {error_msg}")
                    raise ValueError(error_msg) from e
                except Exception as e:
                    error_msg = f"상황 파일 로드 실패: {situations_file} - {str(e)}"
                    print(f"❌ {error_msg}")
                    raise RuntimeError(error_msg) from e
            else:
                error_msg = f"상황 파일을 찾을 수 없습니다: {situations_file}"
                print(f"❌ {error_msg}")
                raise FileNotFoundError(error_msg)
            
            # 상품 카탈로그 로드
            catalog_file = self.data_path / "product_catalog.json"
            print(f"📄 카탈로그 파일 경로: {catalog_file}")
            print(f"📄 카탈로그 파일 존재 여부: {catalog_file.exists()}")
            
            if catalog_file.exists():
                with open(catalog_file, 'r', encoding='utf-8') as f:
                    self.product_catalog = json.load(f)
                    print(f"✅ 상품 카탈로그 로드됨: {len(self.product_catalog.get('products', []))}개 상품")
            else:
                print("❌ 상품 카탈로그 파일을 찾을 수 없습니다")
                self.product_catalog = {"products": [], "categories": {}}
            
            print(f"✅ 데이터 로드 완료: 페르소나 {len(self.personas_cache) if self.personas_cache else 0}개, "
                  f"상황 {len(self.situations_cache) if self.situations_cache else 0}개, "
                  f"상품 {len(self.product_catalog.get('products', []))}개")
            
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            # 이미 처리된 예외는 그대로 전달
            print(f"❌ 데이터 로드 실패 (명시적 예외): {e}")
            import traceback
            traceback.print_exc()
            raise
        except Exception as e:
            # 예상치 못한 예외
            error_msg = f"데이터 로드 중 예상치 못한 오류 발생: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(error_msg) from e
    
    def get_personas(self, filters: Optional[Dict] = None) -> List[Dict]:
        """페르소나 목록 조회 (필드명 정규화하여 반환)"""
        if not self.personas_cache:
            print("📊 페르소나 데이터 로딩 중...")
            self.load_simulation_data()
        
        if not self.personas_cache:
            print("❌ 페르소나 데이터가 없습니다.")
            return []
        
        personas = self.personas_cache.copy()
        
        # 필드명 정규화 (personas_expanded_minified2.json 구조에 맞춤)
        normalized_personas = []
        for p in personas:
            normalized = {
                "id": p.get("id", ""),
                "persona_id": p.get("id", ""),  # id를 persona_id로도 사용
                "gender": p.get("gender", ""),
                "age_group": p.get("age_group", ""),
                "occupation": p.get("occupation", ""),
                "type": p.get("customer_style") or p.get("type", ""),  # customer_style -> type
                "customer_style": p.get("customer_style", ""),
                "tone": p.get("speech", {}).get("tone", "neutral") if isinstance(p.get("speech"), dict) else p.get("tone", "neutral"),
                "style": p.get("speech", {}) if isinstance(p.get("speech"), dict) else p.get("style", {}),
                "sample_utterances": p.get("utterance_hints", []) or p.get("sample_utterances", []),
                "utterance_hints": p.get("utterance_hints", []),
                "financial_literacy": p.get("financial_literacy", "중간"),  # 기본값
                "speech": p.get("speech", {})
            }
            normalized_personas.append(normalized)
        
        personas = normalized_personas
        
        if filters:
            # age_group 필터
            if filters.get("age_group"):
                personas = [p for p in personas if p.get("age_group") == filters["age_group"]]
            
            # occupation 필터 - 영어 키워드 매핑
            if filters.get("occupation"):
                occupation_map = {
                    "student": "학생",
                    "employee": "직장인",
                    "self_employed": "자영업자",
                    "retired": "은퇴자",
                    "foreigner": "외국인"
                }
                occupation_keyword = occupation_map.get(filters["occupation"], filters["occupation"])
                personas = [p for p in personas if occupation_keyword in p.get("occupation", "")]
            
            # type 필터 - 영어 키워드 매핑
            if filters.get("type"):
                type_map = {
                    "practical": "실용형",
                    "conservative": "보수형",
                    "angry": "불만형",
                    "positive": "긍정형",
                    "impatient": "급함형"
                }
                type_keyword = type_map.get(filters["type"], filters["type"])
                personas = [p for p in personas if type_keyword in p.get("type", "") or type_keyword in p.get("customer_style", "")]
            
            # gender 필터 - 성별 매핑
            if filters.get("gender"):
                gender_map = {
                    "male": "남성",
                    "female": "여성"
                }
                gender_keyword = gender_map.get(filters["gender"], filters["gender"])
                personas = [p for p in personas if p.get("gender") == gender_keyword]
        
        # 🚨 논리적 필터링: 비현실적인 연령-직업 조합 제외
        # 1. 10대/20대는 은퇴자 제외
        # 2. 10대는 직장인/자영업자 제외 (청소년)
        # 3. 60대 이상은 학생 제외
        personas = [
            p for p in personas 
            if not (
                # 10대/20대와 은퇴자 조합 방지
                ((p.get("age_group") == "10대" or p.get("age_group") == "20대") 
                 and "은퇴자" in p.get("occupation", "")) or
                # 10대와 직장인/자영업자 조합 방지
                (p.get("age_group") == "10대" 
                 and (("직장인" in p.get("occupation", "")) or ("자영업자" in p.get("occupation", "")))) or
                # 60대 이상과 학생 조합 방지
                ((p.get("age_group") == "60대 이상" or p.get("age_group") == "60대이상") 
                 and "학생" in p.get("occupation", ""))
            )
        ]
        
        print(f"✅ 페르소나 {len(personas)}개 반환 (비현실적 조합 제외: 10대/20대-은퇴자, 10대-직장인/자영업자, 60대 이상-학생)")
        return personas
    
    def normalize_user_text(self, text: str, confidence: float = 1.0) -> Dict:
        """사용자 텍스트를 은행 도메인에 맞게 정규화합니다."""
        try:
            result = normalize_text(text, confidence)
            return {
                "original": result.original,
                "normalized": result.normalized,
                "corrections": result.corrections,
                "needs_clarification": result.needs_clarification,
                "extracted_entities": result.extracted_entities
            }
        except Exception as e:
            print(f"❌ 텍스트 정규화 실패: {e}")
            return {
                "original": text,
                "normalized": text,
                "corrections": [],
                "needs_clarification": False,
                "extracted_entities": {}
            }
    
    def match_product_catalog(self, normalized_text: str) -> List[Dict]:
        """정규화된 텍스트로 상품 카탈로그를 매칭합니다."""
        if not self.product_catalog or not self.product_catalog.get("products"):
            return []
        
        matched_products = []
        products = self.product_catalog["products"]
        
        for product in products:
            # 상품명 직접 매칭
            if product["name"] in normalized_text:
                matched_products.append({
                    "product": product["name"],
                    "code": product["code"],
                    "category": product["category"],
                    "category_ko": product["category_ko"],
                    "match_type": "exact_name"
                })
                continue
            
            # 키워드 매칭
            keywords = product.get("keywords", [])
            for keyword in keywords:
                if keyword in normalized_text:
                    matched_products.append({
                        "product": product["name"],
                        "code": product["code"],
                        "category": product["category"],
                        "category_ko": product["category_ko"],
                        "match_type": "keyword",
                        "matched_keyword": keyword
                    })
                    break
        
        return matched_products
    
    def expand_search_query(self, normalized_text: str, catalog_hits: List[Dict] = None) -> List[str]:
        """검색 쿼리를 확장합니다."""
        try:
            return expand_search_query(normalized_text, catalog_hits)
        except Exception as e:
            print(f"❌ 쿼리 확장 실패: {e}")
            return [normalized_text]
    
    def get_business_categories(self) -> List[Dict]:
        """비즈니스 카테고리 목록 조회"""
        if not self.situations_cache:
            self.load_simulation_data()
        
        if not self.situations_cache:
            return []
        
        # 카테고리 추출
        categories = []
        seen_categories = set()
        
        for situation in self.situations_cache:
            title = situation.get('title', '')
            category_id = situation.get('id', '')
            
            # 카테고리 이름 추출 (예: "수신 (예금, 적금, 자동이체)" -> "수신")
            if '(' in title:
                category_name = title.split('(')[0].strip()
            else:
                category_name = title
            
            if category_name not in seen_categories:
                categories.append({
                    "id": category_id,
                    "name": category_name,
                    "title": title
                })
                seen_categories.add(category_name)
        
        return categories
    
    def get_situations(self, filters: Optional[Dict] = None, random_select: bool = True) -> List[Dict]:
        """
        상황 목록 조회
        - filters: 카테고리 필터 (예: {"category": "deposit"})
        - random_select: True면 카테고리별로 40개 중 1개 랜덤 선택, False면 전체 반환
        """
        if not self.situations_cache:
            self.load_simulation_data()
        
        if not self.situations_cache:
            print("⚠️ 상황 데이터가 없습니다.")
            return []
        
        import random
        
        situations = self.situations_cache
        print(f"📊 전체 상황 개수: {len(situations)}")
        
        if filters and filters.get("category"):
            category = filters["category"]
            print(f"🔍 카테고리 필터: {category}")
            
            # 카테고리 매핑 (프론트엔드에서 전달하는 값 -> 실제 카테고리 값)
            category_mapping = {
                "deposit": ["deposit", "수신"],
                "loan": ["loan", "여신"],
                "card": ["card", "카드"],
                "fx": ["foreign_exchange", "외환", "송금", "외환/송금"],
                "foreign_exchange": ["foreign_exchange", "외환", "송금", "외환/송금"],
                "complaint": ["complaint", "민원", "불만", "민원/불만 처리"]
            }
            
            # 매핑된 카테고리 값들 가져오기
            mapped_categories = category_mapping.get(category, [category])
            print(f"📋 매핑된 카테고리: {mapped_categories}")
            
            # 카테고리별로 필터링 (category_id, id, category, title 필드 모두 확인)
            filtered_situations = []
            for s in situations:
                category_id = s.get("category_id", "")
                situation_id = s.get("id", "")
                situation_category = s.get("category", "")
                situation_title = s.get("title", "")
                
                # 카테고리 매칭 확인
                matched = False
                for mapped_cat in mapped_categories:
                    if (category_id == mapped_cat or
                        situation_id == mapped_cat or 
                        situation_category == mapped_cat or 
                        mapped_cat in situation_title or
                        category_id.startswith(mapped_cat) or
                        situation_id.startswith(mapped_cat) or
                        situation_category.startswith(mapped_cat)):
                        matched = True
                        break
                
                if matched:
                    filtered_situations.append(s)
            
            print(f"✅ 필터링된 상황 개수: {len(filtered_situations)}")
            
            if random_select and filtered_situations:
                # 40개 중 1개 랜덤 선택
                random_situation = random.choice(filtered_situations)
                situation_id = random_situation.get('id', 'unknown')
                print(f"🎲 카테고리 '{category}'에서 랜덤 선택: {situation_id} ({len(filtered_situations)}개 중 1개 선택)")
                print(f"📄 선택된 상황: {random_situation.get('title', 'N/A')}")
                return [random_situation]
            else:
                return filtered_situations
        else:
            # 필터가 없으면 전체 반환
            if random_select and situations:
                # 전체 중 1개 랜덤 선택
                random_situation = random.choice(situations)
                situation_id = random_situation.get('id', 'unknown')
                print(f"🎲 전체 상황에서 랜덤 선택: {situation_id} ({len(situations)}개 중 1개 선택)")
                return [random_situation]
            else:
                return situations
    
    def _get_test_scenario_data(self, scenario_type: str) -> Dict:
        """시나리오 타입에 따른 테스트 시나리오 데이터 반환"""
        scenarios = {
            'deposit': {
                "turns": [
                    {"turn": 1, "role": "employee", "expected_text": "안녕하세요 무엇을 도와드릴까요", "product_code": None, "keywords": []},
                    {"turn": 1, "role": "customer", "expected_text": "안녕하세요 정기예금 상품에 대해 알고 싶어요", "product_code": "DEP-MMD", "keywords": ["정기예금", "상품"]},
                    {"turn": 2, "role": "employee", "expected_text": "정기예금은 일정 기간 동안 예치하시면 높은 금리를 받으실 수 있는 상품입니다 가입 금액과 기간에 따라 금리가 달라지며 최소 10만원부터 가입 가능합니다", "product_code": "DEP-MMD", "keywords": ["정기예금", "금리", "가입 금액", "기간", "10만원"]},
                    {"turn": 2, "role": "customer", "expected_text": "MMDA는 어떤 상품인가요? 일반 예금이랑 뭐가 다른가요?", "product_code": "DEP-MMD", "keywords": ["MMDA", "상품", "예금"]},
                    {"turn": 3, "role": "employee", "expected_text": "MMDA는 출금이 자유로운 정기예금 상품입니다 일반 예금보다 금리가 높고 최소 100만원부터 가입 가능하며 잔액에 따라 차등 금리가 적용됩니다", "product_code": "DEP-MMD", "keywords": ["MMDA", "입출금", "금리", "예금", "100만원", "차등", "최소", "가입금액"]},
                    {"turn": 3, "role": "customer", "expected_text": "적금도 궁금한데 이자율이 얼마나 되나요?", "product_code": None, "keywords": ["적금", "이자율"]},
                    {"turn": 4, "role": "employee", "expected_text": "적금은 매월 일정 금액을 납입하시는 상품으로 정기예금보다는 금리가 낮지만 목돈 마련에 좋은 상품입니다 금리는 상품과 납입 기간에 따라 다르며 보통 연 2%에서 3% 수준입니다", "product_code": None, "keywords": ["적금", "금리", "납입", "2%", "3%"]},
                    {"turn": 4, "role": "customer", "expected_text": "자동이체 설정하면 우대금리 받을 수 있나요?", "product_code": None, "keywords": ["자동이체", "우대금리"]},
                    {"turn": 5, "role": "employee", "expected_text": "네 일부 상품은 공과금 자동이체나 급여이체 실적이 있는 경우 세전 기준 0.1%에서 0.3% 사이 우대금리가 추가로 적용될 수 있습니다", "product_code": None, "keywords": ["자동이체", "우대금리", "0.1%", "0.3%"]},
                    {"turn": 5, "role": "customer", "expected_text": "네 감사합니다.", "product_code": None, "keywords": []},
                    {"turn": 6, "role": "employee", "expected_text": "감사합니다.", "product_code": None, "keywords": []}
                ]
            },
            'loan': {
                "turns": [
                    {"turn": 1, "role": "employee", "expected_text": "안녕하세요 무엇을 도와드릴까요", "product_code": None, "keywords": []},
                    {"turn": 1, "role": "customer", "expected_text": "주택담보대출을 받고 싶은데요", "product_code": "LON-MTG", "keywords": ["주택담보대출"]},
                    {"turn": 2, "role": "employee", "expected_text": "주택담보대출은 주택을 담보로 제공하여 대출받는 상품입니다 LTV 즉 담보 인정 비율은 일반 지역 70% 투기지역 60%이며 DTI 즉 총 부채 상환 비율은 60%까지 가능합니다", "product_code": "LON-MTG", "keywords": ["주택담보", "LTV", "DTI", "담보인정비율", "70%", "60%", "규제"]},
                    {"turn": 2, "role": "customer", "expected_text": "예금담보대출도 가능한가요? 수취은행이 다른 경우에도 되나요?", "product_code": "LON-DCL", "keywords": ["예금담보대출", "수취은행"]},
                    {"turn": 3, "role": "employee", "expected_text": "예금담보대출은 예금을 담보로 제공하여 초저금리로 대출받는 상품입니다 예금잔액의 95%까지 대출 가능하며 수취은행과 무관하게 본행 예금만 가능합니다", "product_code": "LON-DCL", "keywords": ["예금담보", "수취은행", "담보", "95%", "예금잔액", "초저금리"]},
                    {"turn": 3, "role": "customer", "expected_text": "신용대출 한도는 어떻게 되나요?", "product_code": "LON-CRE", "keywords": ["신용대출", "한도"]},
                    {"turn": 4, "role": "employee", "expected_text": "신용대출 한도는 고객님의 신용점수와 소득에 따라 다르며 일반적으로 연소득의 1.5배에서 2배까지 가능합니다 정확한 한도는 신용조회 후 안내 가능합니다", "product_code": "LON-CRE", "keywords": ["신용대출", "한도", "신용점수", "소득", "1.5배", "2배"]},
                    {"turn": 4, "role": "customer", "expected_text": "상환 방식은 어떤 것들이 있나요?", "product_code": None, "keywords": ["상환 방식"]},
                    {"turn": 5, "role": "employee", "expected_text": "원리금균등, 원금균등, 만기일시상환 방식이 있으며 고객님의 상환 능력과 계획에 따라 선택 가능합니다", "product_code": None, "keywords": ["원리금균등", "원금균등", "만기일시상환"]},
                    {"turn": 5, "role": "customer", "expected_text": "네 감사합니다.", "product_code": None, "keywords": []},
                    {"turn": 6, "role": "employee", "expected_text": "감사합니다.", "product_code": None, "keywords": []}
                ]
            },
            'card': {
                "turns": [
                    {"turn": 1, "role": "employee", "expected_text": "안녕하세요 무엇을 도와드릴까요", "product_code": None, "keywords": []},
                    {"turn": 1, "role": "customer", "expected_text": "신용카드 발급 받고 싶은데요", "product_code": None, "keywords": ["신용카드", "발급"]},
                    {"turn": 2, "role": "employee", "expected_text": "신용카드는 현금 없이 결제하실 수 있는 상품으로 한도 내에서 자유롭게 사용하실 수 있습니다 연회비와 혜택에 따라 다양한 상품이 있습니다", "product_code": None, "keywords": ["신용카드", "결제", "한도", "연회비", "혜택"]},
                    {"turn": 2, "role": "customer", "expected_text": "카드 한도는 얼마나 나오나요?", "product_code": None, "keywords": ["카드", "한도"]},
                    {"turn": 3, "role": "employee", "expected_text": "카드 한도는 고객님의 신용도와 소득에 따라 결정되며 일반적으로 월 소득의 2배에서 3배 수준입니다 정확한 한도는 심사 후 안내 가능합니다", "product_code": None, "keywords": ["카드", "한도", "신용도", "소득", "2배", "3배"]},
                    {"turn": 3, "role": "customer", "expected_text": "체크카드도 발급 가능한가요?", "product_code": None, "keywords": ["체크카드", "발급"]},
                    {"turn": 4, "role": "employee", "expected_text": "네 체크카드는 예금 계좌와 연동되어 계좌 잔액 내에서만 사용 가능한 카드입니다 연회비가 없고 신용카드보다 안전하게 사용하실 수 있습니다", "product_code": None, "keywords": ["체크카드", "예금 계좌", "연동", "연회비"]},
                    {"turn": 4, "role": "customer", "expected_text": "할부 이자율은 어떻게 되나요?", "product_code": None, "keywords": ["할부", "이자율"]},
                    {"turn": 5, "role": "employee", "expected_text": "할부 이자율은 할부 기간과 상품에 따라 다르며 일반적으로 2개월 할부는 무이자 3개월 이상은 연 10%에서 20% 수준입니다", "product_code": None, "keywords": ["할부", "이자율", "무이자", "10%", "20%"]},
                    {"turn": 5, "role": "customer", "expected_text": "네 감사합니다.", "product_code": None, "keywords": []},
                    {"turn": 6, "role": "employee", "expected_text": "감사합니다.", "product_code": None, "keywords": []}               
                ]
            },
            'fx': {
                "turns": [
                    {"turn": 1, "role": "employee", "expected_text": "안녕하세요 무엇을 도와드릴까요", "product_code": None, "keywords": []},
                    {"turn": 1, "role": "customer", "expected_text": "해외로 송금하고 싶은데요", "product_code": None, "keywords": ["해외", "송금"]},
                    {"turn": 2, "role": "employee", "expected_text": "해외송금은 전신환 송금과 전자송금 방식이 있습니다 전신환은 수수료가 낮지만 시간이 오래 걸리고 전자송금은 빠르지만 수수료가 조금 더 높습니다", "product_code": None, "keywords": ["해외송금", "전신환", "전자송금", "수수료"]},
                    {"turn": 2, "role": "customer", "expected_text": "미국으로 1만 달러 보내려면 얼마나 걸리나요?", "product_code": None, "keywords": ["미국", "달러", "송금"]},
                    {"turn": 3, "role": "employee", "expected_text": "전자송금의 경우 당일 또는 익일 도착 가능하며 수수료는 송금 금액과 환율에 따라 다릅니다 1만 달러 기준으로 약 2만원에서 5만원 수준입니다", "product_code": None, "keywords": ["전자송금", "수수료", "환율", "2만원", "5만원"]},
                    {"turn": 3, "role": "customer", "expected_text": "외화예금 계좌도 만들 수 있나요?", "product_code": None, "keywords": ["외화예금", "계좌"]},
                    {"turn": 4, "role": "employee", "expected_text": "네 외화예금 계좌 개설 가능합니다 달러, 유로, 엔화 등 주요 통화로 예금하실 수 있으며 통화별로 금리가 다르게 적용됩니다", "product_code": None, "keywords": ["외화예금", "계좌", "달러", "유로", "엔화", "금리"]},
                    {"turn": 4, "role": "customer", "expected_text": "환전도 여기서 할 수 있나요?", "product_code": None, "keywords": ["환전"]},
                    {"turn": 5, "role": "employee", "expected_text": "네 지점에서 현찰 환전 가능하며 인터넷뱅킹이나 모바일뱅킹에서도 외화예금 계좌로 환전하실 수 있습니다 환율은 실시간으로 변동됩니다", "product_code": None, "keywords": ["환전", "인터넷뱅킹", "모바일뱅킹", "환율"]},
                    {"turn": 5, "role": "customer", "expected_text": "네 감사합니다.", "product_code": None, "keywords": []},
                    {"turn": 6, "role": "employee", "expected_text": "감사합니다.", "product_code": None, "keywords": []}
                ]
            }
        }
        
        return scenarios.get(scenario_type, scenarios['deposit'])  # 기본값: 수신
    
    def start_test_simulation(self, user_id: int, scenario_type: str = 'deposit') -> Dict:
        """테스트 모드 시뮬레이션 시작 - 고정된 시나리오로 STT 성능 및 RAG 연동 테스트"""
        try:
            print(f"🧪 start_test_simulation 시작: user_id={user_id}, scenario_type={scenario_type}")
            # 데이터가 없으면 로드
            if not self.personas_cache or not self.situations_cache:
                print(f"🧪 데이터 캐시가 비어있음 - 로드 시작")
                print(f"🧪   personas_cache: {self.personas_cache is not None}, situations_cache: {self.situations_cache is not None}")
                self.load_simulation_data()
                print(f"🧪 데이터 로드 완료")
                print(f"🧪   personas_cache: {len(self.personas_cache) if self.personas_cache else 0}개")
                print(f"🧪   situations_cache: {len(self.situations_cache) if self.situations_cache else 0}개")
            else:
                print(f"🧪 데이터 캐시가 이미 로드됨")
                print(f"🧪   personas_cache: {len(self.personas_cache) if self.personas_cache else 0}개")
                print(f"🧪   situations_cache: {len(self.situations_cache) if self.situations_cache else 0}개")
            
            # 데이터 로드 검증
            if not self.personas_cache:
                error_msg = "페르소나 데이터를 로드할 수 없습니다. 데이터 파일을 확인해주세요."
                print(f"❌ {error_msg}")
                raise RuntimeError(error_msg)
            if not self.situations_cache:
                error_msg = "상황 데이터를 로드할 수 없습니다. 데이터 파일을 확인해주세요."
                print(f"❌ {error_msg}")
                raise RuntimeError(error_msg)
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            # 이미 처리된 예외는 그대로 전달
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ start_test_simulation 데이터 로드 실패 (명시적 예외): {str(e)}")
            print(f"상세 오류:\n{error_trace}")
            raise
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ start_test_simulation 데이터 로드 실패 (예상치 못한 예외): {str(e)}")
            print(f"상세 오류:\n{error_trace}")
            raise RuntimeError(f"시뮬레이션 데이터 로드 중 오류가 발생했습니다: {str(e)}") from e
        
        # 테스트용 고정 페르소나와 상황
        test_persona = {
            "id": "test_persona_001",
            "name": "테스트 고객",
            "gender": "female",
            "age_group": "40대",
            "occupation": "직장인",
            "type": "긍정형",
            "customer_style": "긍정형",
            "tone": "neutral",
            "speech": {"tone": "neutral", "speed": 1.0},
            "utterance_hints": []
        }
        
        # 시나리오 타입에 따른 제목 및 목표 설정
        scenario_titles = {
            'deposit': '수신 상품 상담 테스트',
            'loan': '여신 상품 상담 테스트',
            'card': '카드 상품 상담 테스트',
            'fx': '외환/송금 서비스 테스트'
        }
        
        test_situation = {
            "id": f"test_situation_{scenario_type}",
            "title": scenario_titles.get(scenario_type, "STT 성능 및 RAG 연동 테스트"),
            "category": "test",
            "goals": [
                "금융 용어 STT 인식 정확도 평가",
                "RAG 상품 데이터 연동 확인",
                "지식 평가 로직 검증"
            ],
            "scenarios": []
        }
        
        # 시나리오 타입에 따른 테스트 시나리오 데이터 가져오기
        print(f"🧪 시나리오 타입: {scenario_type}")
        test_scenario = self._get_test_scenario_data(scenario_type)
        
        # 🧪 시나리오 검증 및 디버깅
        print(f"🧪 ========== start_test_simulation 시나리오 검증 ==========")
        print(f"🧪 요청된 scenario_type: {scenario_type}")
        print(f"🧪 반환된 test_scenario turns 개수: {len(test_scenario.get('turns', []))}")
        if test_scenario.get("turns"):
            first_turn = test_scenario["turns"][0]
            second_turn = test_scenario["turns"][1] if len(test_scenario["turns"]) > 1 else None
            print(f"🧪 첫 번째 턴: role='{first_turn.get('role')}', text='{first_turn.get('expected_text', '')[:50]}...'")
            if second_turn:
                print(f"🧪 두 번째 턴: role='{second_turn.get('role')}', text='{second_turn.get('expected_text', '')[:50]}...'")
        print(f"🧪 ======================================================")
        
        # 테스트 모드: 첫 번째 턴(직원 인사)의 expected_text를 초기 안내 메시지로 사용
        first_turn = test_scenario["turns"][0] if test_scenario.get("turns") else None
        first_employee_text = first_turn.get("expected_text", "") if first_turn and first_turn.get("role") == "employee" else ""
        
        initial_message = {
            "type": "instruction",
            "content": first_employee_text if first_employee_text else "안녕하세요, 무엇을 도와드릴까요?",
            "audio_url": None,
            "instruction": first_employee_text if first_employee_text else "테스트 시나리오를 진행합니다. 화면에 표시된 대사를 정확히 따라 말해주세요."
        }
        
        return {
            "session_id": f"test_session_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "persona": test_persona,
            "situation": test_situation,
            "initial_message": initial_message,
            "test_scenario": test_scenario,
            "is_test_mode": True,
            "conversation_history": []  # 빈 배열로 시작
        }
    
    def start_voice_simulation(self, user_id: int, persona_id: str, situation_id: str, gender: str = 'male') -> Dict:
        """음성 시뮬레이션 시작"""
        try:
            # 데이터가 없으면 로드
            if not self.personas_cache or not self.situations_cache:
                print(f"📊 시뮬레이션 데이터 로딩 시작...")
                self.load_simulation_data()
            
            # 데이터 로드 확인
            if not self.personas_cache:
                error_msg = f"페르소나 데이터를 로드할 수 없습니다. 데이터 파일 경로: {self.data_path}"
                print(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            if not self.situations_cache:
                error_msg = f"상황 데이터를 로드할 수 없습니다. 데이터 파일 경로: {self.data_path}"
                print(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            print(f"✅ 데이터 로드 확인: 페르소나 {len(self.personas_cache)}개, 상황 {len(self.situations_cache)}개")
            
            # 페르소나와 상황 조회
            persona = None
            situation = None
            
            if self.personas_cache:
                # id 필드로 조회 (personas_expanded_minified2.json은 id 필드만 사용)
                persona = next((p for p in self.personas_cache if p.get("id") == persona_id), None)
                print(f"페르소나 조회: {persona_id} -> {persona is not None}")
                if persona:
                    print(f"✅ 페르소나 찾음: {persona.get('id')}, gender={persona.get('gender')}, age_group={persona.get('age_group')}")
                else:
                    # 사용 가능한 페르소나 ID 샘플 출력
                    available_ids = [p.get('id', 'N/A') for p in self.personas_cache[:5]]
                    print(f"⚠️ 페르소나 {persona_id}를 찾지 못함. 사용 가능한 ID 샘플: {available_ids}")
            
            if self.situations_cache:
                situation = next((s for s in self.situations_cache if s.get("id") == situation_id), None)
                print(f"상황 조회: {situation_id} -> {situation is not None}")
                if not situation:
                    # 사용 가능한 상황 ID 샘플 출력
                    available_ids = [s.get('id', 'N/A') for s in self.situations_cache[:5]]
                    print(f"⚠️ 상황 {situation_id}를 찾지 못함. 사용 가능한 ID 샘플: {available_ids}")
            
            # 페르소나를 찾지 못했으면 첫 번째 페르소나 사용
            if not persona and self.personas_cache:
                persona = self.personas_cache[0]
                persona_id_found = persona.get('id', 'Unknown')
                print(f"⚠️ 페르소나 {persona_id}를 찾지 못해 첫 번째 페르소나 사용: {persona_id_found}")
            
            # 상황을 찾지 못했으면 첫 번째 상황 사용
            if not situation and self.situations_cache:
                situation = self.situations_cache[0]
                print(f"⚠️ 상황 {situation_id}를 찾지 못해 첫 번째 상황 사용: {situation.get('id')}")
            
            if not persona:
                error_msg = f"페르소나를 찾을 수 없습니다: {persona_id} (캐시에 {len(self.personas_cache) if self.personas_cache else 0}개 페르소나 존재)"
                print(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            if not situation:
                error_msg = f"상황을 찾을 수 없습니다: {situation_id} (캐시에 {len(self.situations_cache) if self.situations_cache else 0}개 상황 존재)"
                print(f"❌ {error_msg}")
                raise ValueError(error_msg)
        except ValueError as e:
            # ValueError는 그대로 전달 (400 에러로 처리)
            raise
        except Exception as e:
            # 예상치 못한 오류는 상세 로그와 함께 재발생
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ start_voice_simulation 오류 발생: {str(e)}")
            print(f"상세 오류:\n{error_trace}")
            raise RuntimeError(f"시뮬레이션 시작 중 오류가 발생했습니다: {str(e)}") from e
        
        # 성별 정보는 이미 페르소나 데이터에 포함되어 있으므로 추가하지 않음
        
        # 🚨 변경: 첫 시작은 사용자가 직접 말해야 함
        # 안내 메시지만 반환 (실제 대화는 사용자가 말을 시작하면 시작)
        initial_message = {
            "type": "instruction",
            "content": "안녕하세요, 무엇을 도와드릴까요?",
            "audio_url": None,  # 안내 메시지는 TTS 없음
            "instruction": "위 메시지로 시작하세요. 마이크 버튼을 눌러 말을 시작해주세요."
        }
        
        # 초기 고객 메시지는 생성하지 않음 (사용자가 말하면 그때부터 시작)
        initial_customer_message = None
        
        # 페르소나 ID와 필드명 처리 (persona_id 또는 id)
        persona_id_value = persona.get("id", "Unknown")
        # customer_style 필드가 있으면 type으로 사용
        persona_type = persona.get("customer_style") or persona.get("type", "")
        # tone은 speech.tone 또는 tone
        speech_obj = persona.get("speech", {})
        persona_tone = speech_obj.get("tone", "neutral") if isinstance(speech_obj, dict) else persona.get("tone", "neutral")
        
        return {
            "session_id": f"session_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "persona": {
                "id": persona_id_value,
                "persona_id": persona_id_value,
                "name": persona_id_value,
                "gender": persona.get("gender", ""),
                "age_group": persona.get("age_group", ""),
                "occupation": persona.get("occupation", ""),
                "type": persona_type,
                "customer_style": persona.get("customer_style", ""),
                "tone": persona_tone,
                "style": speech_obj if isinstance(speech_obj, dict) else persona.get("style", {}),
                "sample_utterances": persona.get("utterance_hints", []) or persona.get("sample_utterances", []),
                "utterance_hints": persona.get("utterance_hints", []),
                "speech": speech_obj
            },
            "situation": {
                "id": situation["id"],
                "title": situation.get("title", ""),
                "category": situation.get("category", "general"),
                "goals": situation.get("goals", []),
                "scenarios": situation.get("scenarios", [])
            },
            "initial_message": initial_message  # 안내 메시지 ("안녕하세요, 무엇을 도와드릴까요?"로 시작하라는 안내)
        }
    
    def process_voice_interaction(self, session_data: Dict, audio_data: bytes, 
                                user_message: str = "") -> Dict:
        """음성 상호작용 처리"""
        try:
            print(f"음성 상호작용 처리 시작: session_data keys = {list(session_data.keys())}")
            
            # 🧪 테스트 모드 체크 (로깅용으로만 사용, 처리 로직은 일반 모드와 동일)
            is_test_mode = session_data.get("is_test_mode", False)
            has_test_scenario = bool(session_data.get("test_scenario"))
            
            if is_test_mode or has_test_scenario:
                print("🧪 테스트 모드 감지 (일반 모드와 동일하게 처리)")
            else:
                print("✅ 일반 모드로 처리합니다.")
            
            if not session_data or "persona" not in session_data:
                raise ValueError("세션 데이터가 올바르지 않습니다.")
                
            persona = session_data["persona"]
            situation = session_data.get("situation", session_data.get("scenario", {}))
            
            print(f"페르소나: {persona.get('persona_id', persona.get('id', 'Unknown'))}")
            print(f"상황: {situation.get('id', situation.get('scenario_id', 'Unknown'))}")
            
            # 페르소나와 상황 정보를 실제 데이터에서 조회
            persona_id = persona.get('persona_id', persona.get('id', ''))
            situation_id = situation.get('id', situation.get('scenario_id', ''))
            
            # 실제 페르소나와 상황 데이터 조회
            actual_persona = None
            actual_situation = None
            
            if self.personas_cache and persona_id:
                # id 필드로 조회 (personas_expanded_minified2.json은 id 필드만 사용)
                actual_persona = next((p for p in self.personas_cache if p.get("id") == persona_id), None)
                if actual_persona:
                    print(f"✅ 실제 페르소나 데이터 조회 성공: {persona_id}")
                else:
                    print(f"❌ 실제 페르소나 데이터 조회 실패: {persona_id}")
                    print(f"   캐시에 있는 페르소나 ID 샘플: {[p.get('id')[:10] for p in list(self.personas_cache[:5])]}")
            
            if self.situations_cache and situation_id:
                actual_situation = next((s for s in self.situations_cache if s.get("id") == situation_id), None)
                if actual_situation:
                    print(f"실제 상황 데이터 조회 성공: {situation_id}")
                else:
                    print(f"실제 상황 데이터 조회 실패: {situation_id}")
            
            # STT: 음성을 텍스트로 변환 (사용자가 제공한 텍스트가 있으면 우선 사용)
            if not user_message:
                print(f"STT 처리 시작: 오디오 크기 {len(audio_data) if audio_data else 0} bytes")
                transcribed_text = self._speech_to_text(audio_data)
            else:
                print(f"텍스트 입력: '{user_message}'")
                transcribed_text = user_message
            
            print(f"최종 텍스트: '{transcribed_text}'")
            
            # 대화 히스토리 구성 (세션 데이터에서 추출 및 누적) - 먼저 초기화
            conversation_history = session_data.get("conversation_history", [])
            print(f"🧪 테스트 모드: 세션에서 가져온 conversation_history 길이={len(conversation_history)}")
            if conversation_history:
                for idx, msg in enumerate(conversation_history):
                    role = msg.get('role', 'MISSING')
                    text = msg.get('text', '')[:30]
                    print(f"🧪   기존 히스토리 [{idx}]: role='{role}' (type: {type(role).__name__}), text='{text}...'")
                    # 🧪 role 검증: 반드시 'employee' 또는 'customer'여야 함
                    if role not in ['employee', 'customer']:
                        print(f"🧪 ⚠️ 경고: 기존 히스토리 [{idx}]의 role이 잘못됨: '{role}', 올바른 role로 수정 필요")
            
            # 🧪 테스트 모드: 시나리오의 expected_text 사용 (LLM 호출 건너뛰기)
            if is_test_mode or has_test_scenario:
                # 테스트 모드: 시나리오에서 고객 응답 가져오기
                test_scenario = session_data.get("test_scenario", {})
                turns = test_scenario.get("turns", [])
                
                # 🧪 시나리오 검증 및 디버깅
                print(f"🧪 ========== 테스트 모드 시나리오 검증 ==========")
                print(f"🧪 test_scenario 존재 여부: {bool(test_scenario)}")
                print(f"🧪 turns 개수: {len(turns)}")
                if turns:
                    print(f"🧪 첫 번째 턴 정보: role='{turns[0].get('role')}', text='{turns[0].get('expected_text', '')[:50]}...'")
                    if len(turns) > 1:
                        print(f"🧪 두 번째 턴 정보: role='{turns[1].get('role')}', text='{turns[1].get('expected_text', '')[:50]}...'")
                else:
                    print(f"🧪 ⚠️ 경고: turns가 비어있습니다!")
                print(f"🧪 ============================================")
                
                # current_turn_index 초기화 (없으면 0)
                if "current_turn_index" not in session_data:
                    session_data["current_turn_index"] = 0
                current_turn_index = session_data.get("current_turn_index", 0)
                
                print(f"🧪 테스트 모드: current_turn_index={current_turn_index}, 전체 턴 수={len(turns)}")
                print(f"🧪 사용자가 말한 텍스트: '{transcribed_text}'")
                
                # 현재 턴 확인
                if current_turn_index >= len(turns):
                    print(f"🧪 테스트 모드: 모든 턴 완료")
                    customer_response_text = ""
                    next_turn_expected_text = ""
                    next_turn_role = None
                else:
                    current_turn = turns[current_turn_index]
                    current_turn_role = current_turn.get("role")
                    print(f"🧪 테스트 모드: 현재 턴={current_turn_index}, 역할={current_turn_role}, 텍스트={current_turn.get('expected_text', '')[:50]}...")
                    
                    # 현재 턴이 직원 턴인지 확인
                    if current_turn_role == "employee":
                        # 🧪 사용자가 녹음한 직원 발화를 conversation_history에 추가
                        # 중요: 사용자가 실제로 말한 것이므로 항상 추가해야 함
                        # 단, 같은 텍스트가 이미 마지막에 있으면 중복 방지
                        is_duplicate = False
                        if conversation_history:
                            last_msg = conversation_history[-1]
                            if (last_msg.get("role") == "employee" and 
                                last_msg.get("text") == transcribed_text):
                                print(f"🧪 ⚠️ 중복 감지: 마지막 메시지와 동일한 직원 발화, 추가하지 않음")
                                is_duplicate = True
                        
                        if not is_duplicate:
                            # 사용자가 실제로 녹음한 직원 발화를 conversation_history에 추가
                            # 🧪 중요: role은 반드시 'employee' 문자열이어야 함
                            new_employee_msg = {
                                "role": "employee",  # 문자열 'employee'
                                "text": transcribed_text,
                                "timestamp": datetime.now().isoformat()
                            }
                            conversation_history.append(new_employee_msg)
                            print(f"🧪 테스트 모드: 사용자 녹음 직원 발화를 conversation_history에 추가")
                            print(f"🧪   추가된 메시지: role='{new_employee_msg['role']}' (type: {type(new_employee_msg['role']).__name__}), text='{transcribed_text[:50]}...'")
                            print(f"🧪   conversation_history 현재 길이: {len(conversation_history)}")
                            # 마지막 메시지 확인
                            if conversation_history:
                                last_msg = conversation_history[-1]
                                print(f"🧪   마지막 메시지 확인: role='{last_msg.get('role')}', text='{last_msg.get('text', '')[:30]}...'")
                        else:
                            print(f"🧪 테스트 모드: 중복된 직원 발화이므로 추가하지 않음")
                        
                        # 🧪 다음 턴(고객)의 expected_text 가져오기
                        # 직원이 말한 후에는 반드시 고객 응답이 자동으로 나와야 함
                        next_turn_index = current_turn_index + 1
                        print(f"🧪 테스트 모드: 다음 턴 인덱스 계산 - current_turn_index={current_turn_index}, next_turn_index={next_turn_index}, 전체 턴 수={len(turns)}")
                        if next_turn_index < len(turns):
                            next_turn = turns[next_turn_index]
                            next_turn_role = next_turn.get("role")
                            print(f"🧪 테스트 모드: 다음 턴 정보 - 인덱스={next_turn_index}, role='{next_turn_role}', expected_text='{next_turn.get('expected_text', '')[:50]}...'")
                            if next_turn_role == "customer":
                                # 🧪 고객 응답을 자동으로 가져옴
                                customer_response_text = next_turn.get("expected_text", "")
                                print(f"🧪 ✅ 테스트 모드: 시나리오에서 고객 응답 가져옴 (턴 {next_turn_index}): '{customer_response_text}'")
                                print(f"🧪 ✅ 고객 응답 길이: {len(customer_response_text)}자")
                                
                                # 🧪 그 다음 턴(직원)의 expected_text 가져오기 (사용자가 다음에 말할 내용)
                                next_next_turn_index = next_turn_index + 1
                                if next_next_turn_index < len(turns):
                                    next_next_turn = turns[next_next_turn_index]
                                    if next_next_turn.get("role") == "employee":
                                        next_turn_expected_text = next_next_turn.get("expected_text", "")
                                        next_turn_role = "employee"
                                        # current_turn_index 업데이트 (다음 직원 턴으로 이동)
                                        session_data["current_turn_index"] = next_next_turn_index
                                        print(f"🧪 테스트 모드: 다음 직원 턴 expected_text (턴 {next_next_turn_index}): {next_turn_expected_text[:50]}...")
                                    else:
                                        # 다음 턴도 고객이면 (이상한 경우)
                                        next_turn_role = "customer"
                                        session_data["current_turn_index"] = next_next_turn_index
                                else:
                                    # 모든 턴 완료
                                    next_turn_role = None
                                    next_turn_expected_text = ""
                                    session_data["current_turn_index"] = next_next_turn_index
                            else:
                                # 다음 턴도 직원이면 고객 응답 없음 (이상한 경우)
                                print(f"🧪 ⚠️ 경고: 다음 턴({next_turn_index})도 직원입니다. 고객 응답이 없습니다.")
                                customer_response_text = ""
                                next_turn_expected_text = next_turn.get("expected_text", "")
                                next_turn_role = "employee"
                                session_data["current_turn_index"] = next_turn_index
                        else:
                            # 모든 턴 완료
                            print(f"🧪 테스트 모드: 모든 턴 완료 (다음 턴 인덱스 {next_turn_index} >= 전체 턴 수 {len(turns)})")
                            customer_response_text = ""
                            next_turn_expected_text = ""
                            next_turn_role = None
                    else:
                        # 현재 턴이 고객 턴이면 (이상한 경우, 로그만 남기고 처리)
                        print(f"🧪 ⚠️ 경고: 현재 턴이 고객 턴입니다. 직원이 말해야 하는데 고객 턴이 나왔습니다.")
                        customer_response_text = ""
                        next_turn_expected_text = ""
                        next_turn_role = None
                
                # 변수 초기화 (위에서 설정되지 않은 경우)
                if 'customer_response_text' not in locals():
                    customer_response_text = ""
                if 'next_turn_expected_text' not in locals():
                    next_turn_expected_text = ""
                if 'next_turn_role' not in locals():
                    next_turn_role = None
                
                # 🧪 고객 응답이 있으면 히스토리에 추가 및 TTS 생성
                print(f"🧪 ========== 고객 응답 처리 시작 ==========")
                print(f"🧪 customer_response_text 존재 여부: {bool(customer_response_text)}")
                if customer_response_text:
                    print(f"🧪 customer_response_text 내용: '{customer_response_text}'")
                    # 🧪 중복 체크: 같은 고객 응답이 이미 conversation_history에 있는지 확인
                    is_customer_duplicate = False
                    for existing_msg in conversation_history:
                        if existing_msg.get("role") == "customer" and existing_msg.get("text") == customer_response_text:
                            print(f"🧪 ⚠️ 중복 감지: 같은 고객 응답이 이미 conversation_history에 있음, 추가하지 않음")
                            is_customer_duplicate = True
                            break
                    
                    if not is_customer_duplicate:
                        # 🧪 중요: role은 반드시 'customer' 문자열이어야 함
                        new_customer_msg = {
                            "role": "customer",  # 문자열 'customer'
                            "text": customer_response_text,
                            "timestamp": datetime.now().isoformat()
                        }
                        conversation_history.append(new_customer_msg)
                        print(f"🧪 ✅ 테스트 모드: 고객 응답을 conversation_history에 자동 추가")
                        print(f"🧪   추가된 메시지: role='{new_customer_msg['role']}' (type: {type(new_customer_msg['role']).__name__}), text='{customer_response_text}'")
                        print(f"🧪   conversation_history 현재 길이={len(conversation_history)}")
                        # 전체 conversation_history 확인 (role 아이콘 포함)
                        print(f"🧪   conversation_history 전체 내용:")
                        for idx, msg in enumerate(conversation_history):
                            role_icon = "🔵" if msg.get('role') == 'employee' else "🟢"
                            print(f"🧪     [{idx}] {role_icon} role='{msg.get('role')}', text='{msg.get('text', '')[:50]}...'")
                        
                        # TTS: 고객 응답을 음성으로 변환
                        print(f"🧪 테스트 모드: 고객 응답 TTS 처리 시작 - '{customer_response_text[:30]}...'")
                        response_persona = actual_persona if actual_persona else persona
                        customer_audio = self._text_to_speech(customer_response_text, response_persona)
                        print(f"🧪 ✅ 테스트 모드: TTS 완료 - 오디오 길이 {len(customer_audio) if customer_audio else 0} bytes")
                        if customer_audio:
                            print(f"🧪 ✅ customer_audio 생성 성공 - 프론트엔드로 전송 예정")
                        else:
                            print(f"🧪 ❌ customer_audio 생성 실패")
                    else:
                        print(f"🧪 테스트 모드: 중복된 고객 응답이므로 추가하지 않음")
                        customer_audio = None
                else:
                    # 🧪 고객 응답이 없으면 TTS도 없음
                    print(f"🧪 ❌ 테스트 모드: 고객 응답이 없습니다 (customer_response_text가 비어있음)")
                    print(f"🧪 ❌ 이는 시나리오에서 다음 턴을 찾지 못했거나, 다음 턴이 customer가 아니라는 의미입니다.")
                    customer_audio = None
                print(f"🧪 ========== 고객 응답 처리 완료 ==========")
                
                # 응답 평가
                evaluation = self._evaluate_user_response(transcribed_text, actual_persona or persona, actual_situation or situation)
                
                # 🧪 RAG 평가 생성 (테스트 모드)
                # session_data에서 rag_evaluations 가져오기 (없으면 초기화)
                rag_evaluations = session_data.get("rag_evaluations", [])
                
                # 현재 턴 정보 가져오기
                current_turn = turns[current_turn_index] if current_turn_index < len(turns) else None
                current_turn_role = current_turn.get("role") if current_turn else None
                
                # 직원 발화인 경우 RAG 평가 생성
                if current_turn_role == "employee":
                    expected_product_code = current_turn.get("product_code") if current_turn else None
                    expected_keywords = current_turn.get("keywords", []) if current_turn else []
                    
                    # RAG 연동 평가
                    rag_eval = self._evaluate_rag_integration(
                        transcribed_text,
                        expected_product_code,
                        expected_keywords
                    )
                    # RAG 평가 결과 누적 저장
                    rag_evaluations.append({
                        "turn_index": current_turn_index,
                        "role": "employee",
                        "expected_product_code": expected_product_code,
                        "evaluation": rag_eval
                    })
                    print(f"🧪 ✅ 직원 발화 RAG 평가 생성: {rag_eval['score']:.1f}점 (턴 {current_turn_index})")
                    print(f"🧪   - 키워드 점수: {rag_eval.get('keyword_score', 0):.1f}점")
                    print(f"🧪   - RAG 상품 정보 점수: {rag_eval.get('rag_product_info_score', 0):.1f}점")
                    
                    # session_data에 저장
                    session_data["rag_evaluations"] = rag_evaluations
                
                # 고객 응답이 자동 생성된 경우 고객 발화 RAG 평가도 생성
                if customer_response_text:
                    # 다음 턴(고객) 정보 가져오기
                    next_turn_index_for_customer = current_turn_index + 1
                    if next_turn_index_for_customer < len(turns):
                        next_turn = turns[next_turn_index_for_customer]
                        if next_turn.get("role") == "customer":
                            expected_product_code_customer = next_turn.get("product_code")
                            expected_keywords_customer = next_turn.get("keywords", [])
                            
                            # 고객 발화 RAG 평가 생성 (일반 모드와 동일한 평가 로직 사용)
                            rag_eval_customer = self._evaluate_rag_integration(
                                customer_response_text,
                                expected_product_code_customer,
                                expected_keywords_customer,
                                role="customer"
                            )
                            # RAG 평가 결과 누적 저장
                            rag_evaluations.append({
                                "turn_index": next_turn_index_for_customer,
                                "role": "customer",
                                "expected_product_code": expected_product_code_customer,
                                "evaluation": rag_eval_customer
                            })
                            print(f"🧪 ✅ 고객 발화 RAG 평가 생성: {rag_eval_customer['score']:.1f}점 (턴 {next_turn_index_for_customer})")
                            
                            # session_data에 저장
                            session_data["rag_evaluations"] = rag_evaluations
                
                # RAG 평가 종합 결과 생성
                rag_summary = self._summarize_rag_evaluations(rag_evaluations) if rag_evaluations else None
                
                # 종료 신호 체크 (모든 턴 완료 시)
                end_signal = False
                if session_data.get("current_turn_index", 0) >= len(turns):
                    end_signal = True
                    print(f"🧪 테스트 모드: 모든 턴 완료 - 종료 신호 설정")
                
                # conversation_history를 세션 데이터에 저장 (다음 요청에서 사용)
                session_data["conversation_history"] = conversation_history
                
                # conversation_history 디버깅
                print(f"🧪 테스트 모드: conversation_history 최종 상태 ({len(conversation_history)}개 메시지):")
                for idx, msg in enumerate(conversation_history):
                    print(f"🧪   [{idx}] role={msg.get('role')}, text={msg.get('text', '')[:50]}...")
                
                # 응답에 포함할 conversation_history 복사 (role 확인 및 강제 검증)
                response_history = []
                print(f"🧪 테스트 모드: response_history 생성 시작, conversation_history 길이={len(conversation_history)}")
                for idx, msg in enumerate(conversation_history):
                    # role이 명확하게 설정되어 있는지 확인
                    role = msg.get('role', '')
                    text = msg.get('text', '')
                    
                    print(f"🧪   원본 메시지 [{idx}]: role='{role}' (type: {type(role).__name__}), text='{text[:30]}...'")
                    
                    # 🧪 role 검증 및 수정
                    if role not in ['employee', 'customer']:
                        print(f"🧪 ⚠️ 경고 [{idx}]: 잘못된 role 값 '{role}' (type: {type(role).__name__}), text='{text[:30]}...'")
                        # 🧪 role이 없거나 잘못된 경우, conversation_history의 순서와 시나리오를 기반으로 추정
                        # 하지만 이건 임시 방편이고, 실제로는 role이 올바르게 설정되어야 함
                        # 시나리오를 확인하여 올바른 role 추정 시도
                        test_scenario = session_data.get("test_scenario", {})
                        turns = test_scenario.get("turns", [])
                        # 현재 인덱스에 해당하는 턴을 찾아서 role 추정
                        if idx < len(turns):
                            estimated_role = turns[idx].get("role", "customer")
                            print(f"🧪   시나리오 기반 role 추정: '{estimated_role}'")
                            role = estimated_role if estimated_role in ['employee', 'customer'] else 'customer'
                        else:
                            role = 'customer'  # 기본값
                        print(f"🧪   최종 role: '{role}'")
                    
                    # 🧪 role이 올바른지 최종 확인
                    if role not in ['employee', 'customer']:
                        print(f"🧪 ❌ 심각한 오류 [{idx}]: role이 여전히 잘못됨 '{role}', 강제로 'customer'로 설정")
                        role = 'customer'
                    
                    print(f"🧪   response_history에 추가: role='{role}', text='{text[:30]}...'")
                    
                    response_history.append({
                        "role": role,  # 🧪 명확하게 'employee' 또는 'customer'
                        "text": text,
                        "timestamp": msg.get('timestamp', datetime.now().isoformat())
                    })
                
                print(f"🧪 테스트 모드: response_history 생성 완료, 길이={len(response_history)}")
                for idx, msg in enumerate(response_history):
                    print(f"🧪   최종 response_history [{idx}]: role='{msg.get('role')}', text='{msg.get('text', '')[:30]}...'")
                
                result = {
                    "transcribed_text": transcribed_text,
                    "customer_response": customer_response_text,
                    "customer_audio": customer_audio,
                    "feedback": evaluation,
                    "followups": [],
                    "safety_notes": "",
                    "conversation_phase": "ongoing",
                    "session_score": self._calculate_session_score(session_data),
                    "conversation_history": response_history,  # 🧪 role이 명확하게 설정된 히스토리
                    "end_signal": end_signal,
                    "end_message": "테스트 시나리오가 완료되었습니다." if end_signal else None,
                    "offtopic_count": 0,
                    "is_test_mode": True,
                    "current_turn_index": session_data.get("current_turn_index", 0),
                    "next_turn_expected_text": next_turn_expected_text,
                    "next_turn_role": next_turn_role,
                    "rag_evaluations": rag_evaluations,  # 🧪 RAG 평가 결과 포함
                    "rag_summary": rag_summary  # 🧪 RAG 평가 종합 결과 포함
                }
                
                print(f"🧪 테스트 모드: 음성 상호작용 처리 완료 - conversation_history {len(response_history)}개 메시지 반환")
                print(f"🧪 응답 conversation_history role 확인:")
                for idx, msg in enumerate(response_history):
                    print(f"🧪   [{idx}] role='{msg.get('role')}', text='{msg.get('text', '')[:30]}...'")
                return result
            
            # 일반 모드 및 테스트 모드: LLM 사용 (테스트 모드도 일반 모드와 동일하게 처리)
            # STT에서 이미 정규화가 완료되었으므로 추가 처리 불필요
            normalized_text = transcribed_text
            corrections = []  # 이미 STT에서 처리됨
            needs_clarification = False  # 이미 STT에서 처리됨
            
            # 테스트 모드 관련 변수 초기화 (일반 모드에서도 사용)
            next_turn_expected_text = ""
            next_turn_role = None
            
            # 2. 상품 카탈로그 매칭
            print("📋 상품 카탈로그 매칭 시작")
            catalog_hits = self.match_product_catalog(normalized_text)
            print(f"카탈로그 매칭 결과: {len(catalog_hits)}개")
            for hit in catalog_hits:
                print(f"  - {hit['product']} ({hit['category_ko']})")
            
            # 3. RAG 검색 쿼리 확장
            print("🔍 RAG 검색 쿼리 확장")
            expanded_queries = self.expand_search_query(normalized_text, catalog_hits)
            print(f"확장된 쿼리: {expanded_queries}")
            
            # 고객 응답 생성 (프롬프트 오케스트레이터 사용)
            print("고객 응답 생성 시작")
            
            # 실제 페르소나와 상황 데이터 사용
            response_persona = actual_persona if actual_persona else persona
            response_situation = actual_situation if actual_situation else situation
            
            # 상황 정보 추출 (또는 기본값 사용)
            final_situation = response_situation
            if not final_situation or not final_situation.get('id'):
                # 기본값 사용
                final_situation = get_situation_defaults('deposit')
            else:
                # 상황 기본 구조 확보
                final_situation = {
                    'id': final_situation.get('id', 'deposit'),
                    'title': final_situation.get('title', '상담'),
                    'goals': final_situation.get('goals', ['고객 요구사항 파악', '핵심 정보 안내']),
                    'required_slots': final_situation.get('required_slots', []),
                    'forbidden_claims': final_situation.get('forbidden_claims', []),
                    'style_rules': final_situation.get('style_rules', ['숫자는 예시로만', '확인 후 안내']),
                    'disclaimer': final_situation.get('disclaimer', '실제 조건은 정책에 따라 달라질 수 있습니다.')
                }
            
            # 🚨 변경: 첫 메시지 처리 (안내 메시지는 히스토리에 추가하지 않음)
            # 사용자가 실제로 말을 시작하면 그때부터 대화 시작
            is_first_message = len(conversation_history) == 0
            
            # 🔥 이탈 감지 및 피벗 처리
            offtopic_count = session_data.get("offtopic_count", 0)
            is_offtopic = False
            
            # 첫 메시지가 아닌 경우에만 이탈 감지 (인사말은 허용)
            if not is_first_message:
                is_offtopic = not is_on_topic(transcribed_text)
                if is_offtopic:
                    offtopic_count += 1
                    print(f"⚠️ 이탈 감지 (횟수: {offtopic_count}): '{transcribed_text}'")
                else:
                    # 온토픽으로 돌아오면 카운터 리셋
                    if offtopic_count > 0:
                        print(f"✅ 온토픽으로 복귀")
                    offtopic_count = 0
            else:
                # 첫 메시지도 이탈 감지 (인사말 제외)
                is_offtopic = not is_on_topic(transcribed_text)
                if is_offtopic:
                    offtopic_count = 1
                    print(f"⚠️ 첫 메시지 이탈 감지: '{transcribed_text}'")
            
            # 이탈이 감지된 경우 에러 메시지만 반환 (대화에는 추가하지 않음)
            if is_offtopic and offtopic_count >= 1:
                # 4회 이상 이탈 시 세션 종료 (3번까지는 허용)
                if offtopic_count >= 4:
                    result = {
                        "transcribed_text": transcribed_text,
                        "customer_response": "",
                        "customer_audio": None,
                        "feedback": "이탈이 4회 이상 발생하여 세션이 종료되었습니다.",
                        "conversation_phase": "abandoned",
                        "session_score": 0,
                        "conversation_history": conversation_history,
                        "end_signal": True,
                        "offtopic_count": offtopic_count,
                        "error": "업무 맥락을 벗어난 발화가 반복되어 세션이 종료되었습니다."
                    }
                    
                    print(f"🔚 세션 종료: 이탈 {offtopic_count}회")
                    return result
                
                # 1-3회 이탈: 에러 메시지만 반환 (사용자 메시지는 대화에 추가) + 점수 감점
                # 사용자 발화는 히스토리에 추가 (프론트엔드에서 처리하도록)
                conversation_history.append({
                    "role": "employee", 
                    "text": transcribed_text,
                    "timestamp": datetime.now().isoformat()
                })
                
                current_score = self._calculate_session_score(session_data)
                penalty = offtopic_count * 5  # 이탈 1회당 5점 감점
                penalized_score = max(0, current_score - penalty)
                
                result = {
                    "transcribed_text": transcribed_text,
                    "customer_response": "",
                    "customer_audio": None,
                    "feedback": "",
                    "conversation_phase": "ongoing",
                    "session_score": penalized_score,
                    "conversation_history": conversation_history,  # 사용자 발화 포함
                    "end_signal": False,
                    "offtopic_count": offtopic_count,
                    "error": "은행 신입사원 온보딩입니다. 관련된 답변만 하십시오."
                }
                
                print(f"⚠️ 이탈 감지 (이탈 {offtopic_count}회) - 점수 감점: {penalty}점 (현재 점수: {penalized_score})")
                return result
            
            # 정상 진행: 온토픽으로 돌아왔으므로 이탈 카운터 리셋
            if not is_offtopic:
                offtopic_count = 0
            
            # 현재 직원 발화를 히스토리에 추가
            conversation_history.append({
                "role": "employee", 
                "text": transcribed_text,
                "timestamp": datetime.now().isoformat()
            })
            
            # 세션 데이터에 이탈 카운터 업데이트
            session_data["offtopic_count"] = offtopic_count
            
            print(f"대화 히스토리: {len(conversation_history)}턴")
            for i, msg in enumerate(conversation_history[-4:]):
                print(f"  {i+1}. {msg.get('role', 'unknown')}: {msg.get('text', '')[:50]}...")
            
            # 달성된 목표 정보 추출 (세션 데이터에서)
            achieved_goals = session_data.get("achieved_goals", [])  # 프론트엔드에서 분석한 결과
            achieved_goal_indices = (
                achieved_goals if isinstance(achieved_goals, list) else []
            )
            
            # 고객 감정형 추출 (페르소나 또는 세션 데이터에서)
            customer_emotion = response_persona.get("type", "긍정형") if response_persona else "긍정형"
            if "customer_emotion" in session_data:
                customer_emotion = session_data["customer_emotion"]
            
            # 최근 직원 질문 추출 (대화 히스토리에서)
            last_employee_questions = []
            for msg in conversation_history[-5:]:  # 최근 5턴만 확인
                if msg.get("role") == "employee":
                    text = msg.get("text", "")
                    if "?" in text or "질문" in text or "문의" in text:
                        last_employee_questions.append(text)

            # 🔚 직원 발화에서 종료 트리거 감지
            employee_has_closing_trigger = any(
                trigger in transcribed_text for trigger in END_CONVERSATION_TRIGGERS
            )
            
            if employee_has_closing_trigger:
                # 직원이 종료 신호를 보냈으면 고객도 자연스럽게 종료 응답
                customer_response_text = "네, 알겠습니다. 감사합니다!"
                end_signal = True
                print(f"🔚 직원 종료 트리거 감지 - 고객 종료 응답으로 변경")
                
                # 고객 응답을 히스토리에 추가
                conversation_history.append({
                    "role": "customer",
                    "text": customer_response_text,
                    "timestamp": datetime.now().isoformat()
                })
                
                # TTS: 고객 응답을 음성으로 변환
                print(f"TTS 처리 시작")
                customer_audio = self._text_to_speech(customer_response_text, response_persona)
                print(f"TTS 완료: 오디오 길이 {len(customer_audio) if customer_audio else 0}")
                
                result = {
                    "transcribed_text": transcribed_text,
                    "customer_response": customer_response_text,
                    "customer_audio": customer_audio,
                    "feedback": "",
                    "followups": [],
                    "safety_notes": "",
                    "conversation_phase": "ongoing",
                    "session_score": self._calculate_session_score(session_data),
                    "conversation_history": conversation_history,
                    "end_signal": end_signal,
                    "end_message": "대화가 자연스럽게 마무리되었습니다. 피드백을 확인하시겠습니까?",
                    "offtopic_count": offtopic_count
                }
                
                print("음성 상호작용 처리 완료 (종료 트리거 감지)")
                return result

            # 프롬프트 오케스트레이터로 메시지 구성
            messages = compose_llm_messages(
                persona=response_persona,
                situation=final_situation,
                user_text=normalized_text,  # 정규화된 텍스트 사용
                rag_hits=[],  # TODO: RAG 검색 결과 추가
                history=conversation_history[-10:],  # 최근 10턴까지 포함 (더 많은 맥락)
                extras={
                    "userText_raw": transcribed_text,  # 원본 텍스트
                    "corrections": corrections,  # 교정 정보
                    "catalogHits": catalog_hits,  # 카탈로그 매칭 결과
                    "needs_clarification": needs_clarification,  # 재확인 필요 여부
                    "expanded_queries": expanded_queries,  # 확장된 검색 쿼리
                    "achieved_goals": achieved_goals,  # 달성된 목표 인덱스 리스트
                    "customer_emotion": customer_emotion,  # 고객 감정형
                    "last_employee_questions": last_employee_questions,  # 최근 직원 질문 목록
                    "stuck_counter": session_data.get("stuck_counter", 0),  # 반복 카운터
                    "should_close": session_data.get("should_close", False)  # 종료 신호
                }
            )

            # OpenAI API 호출
            if not self.openai_client:
                raise RuntimeError("OpenAI 클라이언트가 초기화되지 않았습니다.")
            
            llm_response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.2,
                max_tokens=500
            )

            # 일반 모드: LLM 사용
            content = llm_response.choices[0].message.content
            parsed = parse_llm_response(content)

            print(f"고객 응답 (script): '{parsed.get('script', '')}'")

            # 고객 응답 텍스트 추출
            customer_response_text = parsed.get('script', '')
            if not customer_response_text:
                customer_response_text = "네, 알겠습니다."

            print(f"고객 응답: '{customer_response_text}'")
            
            # 고객 응답을 히스토리에 추가
            conversation_history.append({
                "role": "customer",
                "text": customer_response_text,
                "timestamp": datetime.now().isoformat()
            })
            
            # TTS: 고객 응답을 음성으로 변환
            print(f"TTS 처리 시작")
            customer_audio = self._text_to_speech(customer_response_text, response_persona)
            print(f"TTS 완료: 오디오 길이 {len(customer_audio) if customer_audio else 0}")
            
            # 응답 평가
            evaluation = self._evaluate_user_response(transcribed_text, actual_persona or persona, actual_situation or situation)
            
            # 종료 신호 (세션 데이터 플래그 및 자동 판단)
            auto_should_close = self._should_close_session(
                session_data=session_data,
                conversation_history=conversation_history,
                final_situation=final_situation,
                achieved_goal_indices=achieved_goal_indices,
                customer_response_text=customer_response_text,
                employee_latest_text=transcribed_text,
            )
            if auto_should_close:
                session_data["should_close"] = True

            should_close_flag = session_data.get("should_close", False)
            end_signal = bool(should_close_flag)
            
            # 종료 신호가 감지되면 사용자에게 안내할 메시지 생성
            end_message = None
            if end_signal:
                if auto_should_close:
                    end_message = "대화가 자연스럽게 마무리되었습니다. 피드백을 확인하시겠습니까?"
                else:
                    end_message = "시뮬레이션을 종료할 수 있습니다. 상단의 '피드백 보기' 버튼을 클릭하세요."
            
            result = {
                "transcribed_text": transcribed_text,
                "customer_response": customer_response_text,
                "customer_audio": customer_audio,
                "feedback": evaluation,
                "followups": [],
                "safety_notes": "",
                "conversation_phase": "ongoing",
                "session_score": self._calculate_session_score(session_data),
                "conversation_history": conversation_history,  # 업데이트된 히스토리 포함
                "end_signal": end_signal,  # LLM이 판단한 종료 신호 (문맥 기반)
                "end_message": end_message,  # 종료 안내 메시지
                "offtopic_count": offtopic_count,  # 이탈 카운터 포함
                "is_test_mode": is_test_mode or has_test_scenario,  # 🧪 테스트 모드 플래그
                "current_turn_index": session_data.get("current_turn_index", 0),  # 🧪 테스트 모드: 현재 턴 인덱스
                "next_turn_expected_text": next_turn_expected_text,  # 🧪 테스트 모드: 다음 턴 expected_text
                "next_turn_role": next_turn_role  # 🧪 테스트 모드: 다음 턴 역할
            }
            
            print("음성 상호작용 처리 완료")
            return result
            
        except Exception as e:
            print(f"음성 상호작용 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _normalize_percentage_text(self, text: str) -> str:
        """STT 결과에서 "퍼센트"를 "%"로 변환합니다."""
        import re
        # "퍼센트" 또는 "프로"를 "%"로 변환
        # 숫자 뒤에 오는 경우: "4퍼센트" → "4%", "6에서 8퍼센트" → "6에서 8%"
        text = re.sub(r'(\d+(?:\.\d+)?)\s*퍼센트', r'\1%', text)
        text = re.sub(r'(\d+(?:\.\d+)?)\s*프로', r'\1%', text)
        # 단독으로 사용되는 경우: "퍼센트" → "%" (드물지만)
        text = re.sub(r'\b퍼센트\b', '%', text)
        text = re.sub(r'\b프로\b', '%', text)
        return text
    
    def _speech_to_text(self, audio_data: bytes) -> str:
        """하이브리드 STT: whisper 기본 + gpt-4o-transcribe 보정용"""
        if not self.openai_client:
            return "OpenAI API 키가 설정되지 않았습니다."
            
        if not audio_data:
            return "오디오 데이터가 없습니다."

        try:
            # 임시 파일로 저장
            audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
            audio_file.write(audio_data)
            audio_file.close()
            
            print(f"STT 처리: 오디오 파일 크기 {len(audio_data)} bytes")
            
            # 1단계: whisper-1로 기본 인식
            print("🎤 1단계: whisper-1 기본 인식")
            with open(audio_file.name, "rb") as f:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="ko"
                )
            
            initial_text = transcript.text
            print(f"초기 인식 결과: '{initial_text}'")
            
            # 1.5단계: "퍼센트" → "%" 변환 (STT 후처리)
            initial_text = self._normalize_percentage_text(initial_text)
            print(f"퍼센트 변환 후: '{initial_text}'")
            
            # 2단계: 의미 보정으로 품질 평가
            normalize_result = self.normalize_user_text(initial_text, confidence=0.8)
            corrections = normalize_result["corrections"]
            needs_clarification = normalize_result["needs_clarification"]
            
            print(f"교정 횟수: {len(corrections)}")
            print(f"재확인 필요: {needs_clarification}")
            
            # 3단계: 품질이 낮으면 gpt-4o-transcribe로 재인식
            should_reprocess = (
                len(corrections) >= 2 or  # 교정이 2개 이상
                needs_clarification or   # 재확인 필요
                len(initial_text) < 3     # 너무 짧은 텍스트
            )
            
            if should_reprocess:
                print("🔄 2단계: gpt-4o-transcribe 재인식 (품질 개선)")
                with open(audio_file.name, "rb") as f:
                    enhanced_transcript = self.openai_client.audio.transcriptions.create(
                        model="gpt-4o-transcribe",
                        file=f,
                        language="ko"
                    )
                
                enhanced_text = enhanced_transcript.text
                print(f"개선된 인식 결과: '{enhanced_text}'")
                
                # 1.5단계: "퍼센트" → "%" 변환 (STT 후처리)
                enhanced_text = self._normalize_percentage_text(enhanced_text)
                print(f"퍼센트 변환 후: '{enhanced_text}'")
                
                # 개선된 결과로 다시 정규화
                final_normalize = self.normalize_user_text(enhanced_text, confidence=0.9)
                final_text = final_normalize["normalized"]
                
                print(f"최종 정규화: '{final_text}'")
                os.unlink(audio_file.name)
                return final_text
            else:
                print("✅ whisper-1 결과 사용 (품질 양호)")
                os.unlink(audio_file.name)
                return normalize_result["normalized"]
            
        except Exception as e:
            print(f"STT 오류: {e}")
            import traceback
            traceback.print_exc()
            return "음성 인식에 실패했습니다."
    
    def _text_to_speech(self, text: str, persona: Dict) -> str:
        """텍스트를 음성으로 변환 (TTS) - gpt-4o-mini-tts 사용"""
        if not self.openai_client:
            print("TTS 오류: OpenAI 클라이언트가 초기화되지 않았습니다.")
            return ""
            
        if not text:
            print("TTS 오류: 변환할 텍스트가 없습니다.")
            return ""
            
        try:
            print(f"TTS 시작: '{text[:50]}...'")

            # 페르소나 기반 파라미터 산출
            params = get_voice_params(persona)
            print(f"TTS 파라미터: {params}")

            # OpenAI TTS API 호출 (gpt-4o-mini-tts 모델 사용, 기본 파라미터만)
            response = self.openai_client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice=params["voice"],
                speed=params["rate"],  # speed 파라미터 사용
                input=text  # SSML 대신 일반 텍스트 사용
            )

            audio_data = response.content
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            print(f"TTS 성공: {len(audio_data)} bytes")

            return f"data:audio/mpeg;base64,{audio_base64}"
            
        except Exception as e:
            print(f"TTS 오류: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ❌ Dead Code 제거됨 (총 300+ 줄):
    # - _get_voice_characteristics() → persona_voice.get_voice_params() 사용
    # - _generate_initial_customer_message() → 호출 없음
    # - _generate_customer_response_with_rag() → promptOrchestrator 사용
    # - _get_rag_context() → 위 메서드에서만 사용
    # - _extract_persona_traits() → 위 메서드에서만 사용
    # - _determine_conversation_phase() → 위 메서드에서만 사용
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def _evaluate_user_response(self, user_message: str, persona: Dict, situation: Dict) -> str:
        """사용자 응답 평가"""
        scenarios = situation.get('scenarios', [])
        
        if not scenarios:
            return "평가 기준이 없습니다."
        
        # 시나리오를 문자열로 변환
        scenarios_text = "\n".join([
            f"- {scenario}"
            for scenario in scenarios
        ])
        
        prompt = f"""
        은행 직원의 응답: "{user_message}"
        
        고객 정보:
        - 고객 타입: {persona.get('customer_style') or persona.get('type', '')}
        - 금융 이해도: {persona.get('financial_literacy', '중간')}
        - 톤: {persona.get('speech', {}).get('tone', 'neutral') if isinstance(persona.get('speech'), dict) else persona.get('tone', 'neutral')}
        
        시나리오:
        {scenarios_text}
        
        이 응답이 고객에게 적절했는지 평가하고, 개선점이 있다면 피드백을 제공해주세요.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"응답 평가 오류: {e}")
            return "응답 평가를 완료할 수 없습니다."
    
    def _calculate_session_score(self, session_data: Dict) -> float:
        """세션 점수 계산 (임시 구현)"""
        # 실제로는 대화 기록을 기반으로 점수를 계산해야 함
        return 75.0
    
    def _should_close_session(
        self,
        session_data: Dict,
        conversation_history: List[Dict],
        final_situation: Dict,
        achieved_goal_indices: List[int],
        customer_response_text: str,
        employee_latest_text: str,
    ) -> bool:
        """
        대화 종료 여부 자동 판단.
        
        종료 신호는 다음 요소들의 조합으로 판단한다.
          1. 직원의 마무리 질문 + 고객의 종료성 응답
          2. 상담 목표 달성 + 고객의 짧은 확인/감사 응답
          3. 충분한 턴 수 경과 + 고객의 종료성 응답
        """
        if not conversation_history:
            return False

        # 이미 종료 신호가 충분히 누적되었다면 그대로 유지
        closing_counter = session_data.get("closing_signal_counter", 0)
        if session_data.get("should_close"):
            return True

        customer_lower = (customer_response_text or "").strip().lower()
        employee_lower = (employee_latest_text or "").strip().lower()

        # 조건 1: 직원 마무리 질문 + 고객 종료 응답
        employee_closing_prompt = any(phrase in employee_lower for phrase in EMPLOYEE_CLOSING_PROMPTS)
        customer_strong_closing = any(phrase in customer_lower for phrase in CUSTOMER_STRONG_CLOSINGS)
        customer_soft_closing = any(phrase in customer_lower for phrase in CUSTOMER_SOFT_CLOSINGS)

        closing_pair = employee_closing_prompt and (customer_strong_closing or customer_soft_closing)

        # 조건 2: 목표 달성 여부
        goals = final_situation.get("goals") or []
        goals_met = bool(goals) and len(achieved_goal_indices) >= len(goals)

        # 조건 3: 충분한 턴 수 + 짧은 확인 응답
        employee_turns = sum(1 for msg in conversation_history if msg.get("role") == "employee")
        customer_turns = sum(1 for msg in conversation_history if msg.get("role") == "customer")
        conversation_long_enough = employee_turns >= 6 and customer_turns >= 6

        short_ack = (
            customer_response_text
            and len(customer_response_text) <= 25
            and "?" not in customer_response_text
            and (customer_soft_closing or "네" in customer_lower or "예" in customer_lower)
        )

        strong_signal = (
            (closing_pair and customer_strong_closing)
            or (customer_strong_closing and (goals_met or conversation_long_enough))
        )

        medium_signal = (
            closing_pair
            or (goals_met and short_ack)
            or (conversation_long_enough and (customer_soft_closing or customer_strong_closing))
        )

        if strong_signal:
            closing_counter = max(closing_counter, 1) + 1  # 강한 신호는 즉시 2 이상으로 상승
        elif medium_signal:
            closing_counter = min(closing_counter + 1, 3)
        else:
            closing_counter = max(closing_counter - 1, 0)

        session_data["closing_signal_counter"] = closing_counter

        # 강한 종료 신호이거나, 종료 신호가 누적되면 종료
        return strong_signal or closing_counter >= 2

    def generate_comprehensive_feedback(self, conversation_history: List[Dict], 
                                      persona: Dict, situation: Dict,
                                      saved_achieved_goals: Optional[Dict] = None) -> Dict:
        """
        4가지 역량 기반 종합 평가 및 피드백 생성
        - 지식 (Knowledge): 상품/서비스에 대한 정확성과 전문성
        - 기술 (Skill): 상담 프로세스 준수 + 목표 달성도
        - 친절도 (Kindness): 예의와 배려
        - 전달력 (Clarity + Confidence): 명확성과 자신감을 통합한 정보 전달 역량
        """
        try:
            # 직원 발화만 추출 (평가 대상)
            employee_utterances = [
                msg['text'] for msg in conversation_history 
                if msg.get('role') == 'employee'
            ]
            
            if not employee_utterances:
                return self._get_default_feedback()
            
            # 전체 대화 컨텍스트
            conversation_context = "\n".join([
                f"{'고객' if msg.get('role') == 'customer' else '직원'}: {msg.get('text', '')}"
                for msg in conversation_history
            ])
            
            # 🎯 목표 달성 분석 (턴별 추적 포함)
            goals = situation.get('goals', [])
            achieved_goal_indices = []
            turn_tracking = {}
            goal_achievement_rate = 1.0  # 기본값: 목표가 없으면 100%
            
            # 🚨 중요: DB에 저장된 목표 달성 정보 우선 사용 (프론트엔드가 실시간으로 체크한 정보)
            if saved_achieved_goals:
                print(f"✅ DB에 저장된 목표 달성 정보 사용 (프론트엔드에서 체크한 정보)")
                achieved_goal_indices = saved_achieved_goals.get('achieved_indices', [])
                achievement_times = saved_achieved_goals.get('achievement_times', {})
                
                # achievement_times를 turn_tracking 형식으로 변환
                # 대화 히스토리에서 실제 발화 찾기
                for goal_idx_str, time_info in achievement_times.items():
                    goal_idx = int(goal_idx_str)
                    turn_num = time_info.get("turn", 0)
                    
                    # 대화 히스토리에서 해당 턴의 직원 발화 찾기
                    actual_evidence = None
                    if conversation_history and turn_num > 0:
                        # 직원 발화에 턴 번호 붙이기
                        employee_turn_count = 0
                        for msg in conversation_history:
                            role = msg.get("role", "")
                            text = msg.get("text", "")
                            if role in ["employee", "user"]:
                                employee_turn_count += 1
                                if employee_turn_count == turn_num:
                                    actual_evidence = text.strip()
                                    break
                    
                    # 실제 발화를 찾았으면 사용, 없으면 기본 메시지
                    if actual_evidence:
                        turn_tracking[goal_idx] = {
                            "turn": turn_num,
                            "evidence": actual_evidence[:300]  # 최대 300자
                        }
                        print(f"  ✓ 목표 {goal_idx} → 턴 {turn_num}: 실제 발화 발견 ({len(actual_evidence)}자)")
                    else:
                        # 실제 발화를 찾지 못했으면, 저장된 evidence가 있는지 확인
                        saved_evidence = time_info.get("evidence")
                        if saved_evidence and saved_evidence != f"{goal_idx}번 목표를 {turn_num}번째 턴에서 달성":
                            # 저장된 실제 발화가 있으면 사용
                            turn_tracking[goal_idx] = {
                                "turn": turn_num,
                                "evidence": saved_evidence[:300]
                            }
                            print(f"  ✓ 목표 {goal_idx} → 턴 {turn_num}: 저장된 발화 사용")
                        else:
                            # 발화를 찾지 못한 경우, GPT로 발화 찾기 시도
                            try:
                                if goals and goal_idx < len(goals):
                                    goal_text = goals[goal_idx]
                                    # 직원 발화만 추출
                                    employee_utterances = []
                                    employee_turn = 0
                                    for msg in conversation_history:
                                        if msg.get("role") in ["employee", "user"]:
                                            employee_turn += 1
                                            text = msg.get("text", "").strip()
                                            if text:
                                                employee_utterances.append(f"턴 {employee_turn}: {text}")
                                    
                                    if employee_utterances:
                                        employee_conversation = "\n".join(employee_utterances)
                                        tracking_prompt = f"""다음은 은행 직원의 발화입니다.
"{goal_text}" 목표가 달성된 발화를 찾아주세요.

직원 발화:
{employee_conversation}

목표: {goal_text}

**중요 평가 기준**: 
1. **직원이 실제로 구체적인 정보를 제공한 발화를 찾으세요**
   - 단순히 주제를 언급하는 것이 아니라, 목표를 실질적으로 달성한 발화여야 합니다
   
2. **목표 텍스트의 구체적 키워드 확인**:
   - 목표에 인용부호("")로 강조된 구체적 항목이 있으면, 그 항목들이 실제로 언급되었는지 확인
   - 예: 목표에 "\"기본구조·금리\""가 있으면 → 기본구조와 금리 둘 다 다룬 발화인지 확인
   - 예: 목표에 "\"금리, 한도, 우대조건, 수수료 등\""이 있으면 → 최소 2개 이상 언급된 발화인지 확인
   - 목표 텍스트에 나열된 구체적 항목(예: "소득, 거래 패턴 등")이 최소 1개 이상 언급되었는지 확인
   
3. **목표가 요구하는 행동 확인**:
   - "파악한다" → 고객의 의도/상황을 이해하고 확인하는 대화
   - "설명하고/이해시키는" → 구체적인 내용(수치, 절차, 조건 등) 포함
   - "안내하는" → 실제 방법이나 단계 제시
   - "고려한다/설명해" → 명시적인 경고나 정보 전달
   - "정리해 주고" → 다음 단계나 필요 사항 명확히 정리
   
4. **턴 {turn_num} 근처의 발화를 우선적으로 확인하세요**

출력 형식:
발화내용 (직원이 한 말만 출력, 턴 번호 제외)

예: 현재 달러 환율은 1,300원이며, 환전 수수료는 2%입니다.

찾을 수 없으면 "없음"이라고만 출력하세요."""
                                        
                                        tracking_response = self.openai_client.chat.completions.create(
                                            model="gpt-4o-mini",
                                            messages=[{"role": "user", "content": tracking_prompt}],
                                            max_tokens=200,
                                            temperature=0.2
                                        )
                                        
                                        tracking_result = tracking_response.choices[0].message.content.strip()
                                        
                                        if tracking_result and tracking_result.lower() not in ["없음", "none"]:
                                            # "턴 X:" 같은 접두사 제거
                                            evidence = tracking_result
                                            if ":" in evidence and evidence.split(":")[0].strip().isdigit():
                                                evidence = ":".join(evidence.split(":")[1:]).strip()
                                            
                                            turn_tracking[goal_idx] = {
                                                "turn": turn_num,
                                                "evidence": evidence[:300]
                                            }
                                            print(f"  ✓ 목표 {goal_idx} → 턴 {turn_num}: GPT로 발화 찾기 성공")
                                        else:
                                            turn_tracking[goal_idx] = {
                                                "turn": turn_num,
                                                "evidence": None  # 발화를 찾지 못함
                                            }
                                            print(f"  ⚠️ 목표 {goal_idx} → 턴 {turn_num}: 발화 찾기 실패")
                            except Exception as e:
                                print(f"  ⚠️ 목표 {goal_idx} 발화 찾기 오류: {e}")
                                turn_tracking[goal_idx] = {
                                    "turn": turn_num,
                                    "evidence": None
                                }
                
                if goals:
                    goal_achievement_rate = len(achieved_goal_indices) / len(goals)
                    print(f"📊 목표 달성률: {len(achieved_goal_indices)}/{len(goals)} ({goal_achievement_rate*100:.1f}%)")
                    print(f"📅 달성 시점 정보: {len(turn_tracking)}개 목표 (실제 발화 포함: {sum(1 for v in turn_tracking.values() if v.get('evidence'))}개)")
            elif goals:
                # DB에 정보가 없으면 새로 분석 (fallback)
                print(f"⚠️ DB에 저장된 목표 달성 정보 없음 - 새로 분석합니다 (총 {len(goals)}개 목표)")
                # 🔍 2단계: 턴별 추적 정보 포함
                detailed_result = self.analyze_goal_achievement(conversation_history, goals, return_detailed=True)
                
                if isinstance(detailed_result, dict):
                    achieved_goal_indices = detailed_result.get('achieved_indices', [])
                    turn_tracking = detailed_result.get('turn_tracking', {})
                else:
                    # 하위 호환성 (기본 모드)
                    achieved_goal_indices = detailed_result
                    turn_tracking = {}
                
                goal_achievement_rate = len(achieved_goal_indices) / len(goals)
                print(f"✅ 목표 달성률: {len(achieved_goal_indices)}/{len(goals)} ({goal_achievement_rate*100:.1f}%)")
                if turn_tracking:
                    print(f"📍 턴별 추적 정보: {len(turn_tracking)}개 목표에 대한 증거 확보")
            
            # 달성/미달성 목표 정보
            achieved_goals_text = ""
            if goals:
                achieved_goals = [goals[i] for i in achieved_goal_indices]
                unachieved_goals = [goals[i] for i in range(len(goals)) if i not in achieved_goal_indices]
                achieved_goals_text = f"""
달성된 목표: {', '.join(achieved_goals) if achieved_goals else '없음'}
미달성 목표: {', '.join(unachieved_goals) if unachieved_goals else '없음'}
"""
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 🔍 1단계: 제품 지식 정확도 자동 검증 (Product Knowledge Verification)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            product_accuracy_info = ""
            knowledge_verification_result = None
            
            # 상황별 제품 데이터 존재 여부 확인
            situation_id = situation.get('id', '')
            has_product_data = situation.get('has_product_data', True)  # 기본값: True
            
            # 외환/송금 상담은 상품 데이터가 없으므로 제품 검증 스킵
            if situation_id == 'fx':
                has_product_data = False
                print("ℹ️ 외환/송금 상담: 상품 데이터 없음 - 제품 검증 스킵, LLM 기반 지식 평가만 수행")
            
            if self.product_knowledge_service and has_product_data:
                try:
                    print("🔍 제품 지식 정확도 자동 검증 시작...")
                    knowledge_verification_result = self.product_knowledge_service.batch_verify_conversation(
                        conversation_history,
                        use_llm=True  # LLM 검증 포함
                    )
                    
                    accuracy_rate = knowledge_verification_result['accuracy_rate']
                    total_claims = knowledge_verification_result['total_claims']
                    accurate_claims = knowledge_verification_result['accurate_claims']
                    inaccurate_claims = knowledge_verification_result['inaccurate_claims']
                    
                    print(f"  ✓ 제품 정보 검증 완료: {accurate_claims}/{total_claims} 정확 ({accuracy_rate:.1%})")
                    
                    # 오류 상세 정보 및 LLM reasoning 수집
                    errors_detail = []
                    accurate_details = []  # 정확한 정보 목록 추가
                    llm_reasonings = []  # LLM reasoning 수집 (피드백 생성에 활용)
                    
                    for v in knowledge_verification_result.get('verifications', []):
                        # claim과 full_utterance를 함께 표시하여 문맥 제공
                        claim_display = v.claim
                        if hasattr(v, 'full_utterance') and v.full_utterance:
                            # full_utterance에서 claim이 포함된 부분을 강조
                            if v.claim in v.full_utterance:
                                claim_display = f"'{v.claim}' (대화: ...{v.full_utterance[max(0, v.full_utterance.find(v.claim)-20):min(len(v.full_utterance), v.full_utterance.find(v.claim)+len(v.claim)+20)]}...)"
                        
                        if not v.is_accurate:
                            errors_detail.append(f"• {claim_display} → 실제: {v.ground_truth[:80]}...")
                        else:
                            # 정확한 정보도 수집 (피드백에서 잘한 점으로 언급)
                            accurate_details.append(f"• {claim_display} (정확함)")
                        
                        # LLM reasoning이 있으면 수집 (피드백 생성에 활용)
                        if hasattr(v, 'llm_reasoning') and v.llm_reasoning:
                            llm_reasonings.append(f"• {v.claim}: {v.llm_reasoning}")
                    
                    # LLM 프롬프트에 포함할 정확도 정보
                    if total_claims > 0:
                        reasoning_section = ""
                        if llm_reasonings:
                            reasoning_section = f"""
💡 **검증 상세 분석 (LLM reasoning):**
{chr(10).join(llm_reasonings[:5])}  # 상위 5개만 표시
"""
                        
                        accurate_section = ""
                        if accurate_details:
                            accurate_section = f"""
✅ **정확한 정보 목록 (반드시 잘한 점에 언급):**
{chr(10).join(accurate_details[:5])}  # 상위 5개만 표시

⚠️ **위 정확한 정보 목록의 claim은 모두 정확한 정보입니다.**
⚠️ **위 목록에 있는 claim은 개선점에 절대 포함하지 마세요.**
⚠️ **위 목록에 있는 claim은 잘한 점에만 구체적으로 언급하세요.**
"""
                        
                        errors_section = ""
                        if errors_detail:
                            errors_section = f"""
⚠️ **부정확한 정보 목록 (개선점에만 언급):**
{chr(10).join(errors_detail[:5])}  # 상위 5개만 표시

⚠️ **위 부정확한 정보 목록의 claim만 개선점에 언급하세요.**
⚠️ **위 목록에 없는 claim은 개선점에 포함하지 마세요.**
⚠️ **정확한 정보 목록에 있는 claim과 부정확한 정보 목록에 있는 claim이 겹치면 안 됩니다.**
"""
                        else:
                            errors_section = """
⚠️ **부정확한 정보: 없음**
→ 개선점 섹션은 생략하거나 "제공한 모든 상품 정보가 정확합니다"와 같이 간단히 언급하세요.
"""
                        
                        product_accuracy_info = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **제품 지식 자동 검증 결과** (객관적 데이터 - 반드시 정확히 반영하세요)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 총 제품 정보 언급: {total_claims}개
- 정확한 정보: {accurate_claims}개
- 부정확한 정보: {inaccurate_claims}개
- 정확도: {accuracy_rate:.1%}
- 검증 방법: {knowledge_verification_result.get('verification_methods', {})}

{accurate_section}
{errors_section}
{reasoning_section}
💡 **지식 점수 평가 및 피드백 작성 가이드:**
- 정확도 {accuracy_rate:.1%} → 기본 점수 {int(accuracy_rate * 100)}점 (오류는 이미 정확도에 반영됨)
- ⚠️ 오류 개수는 점수 계산에 사용하지 말고, 피드백 작성 시에만 참고하세요
- ⚠️ 불확실한 표현("같아요", "모르겠" 등)은 전달력(자신감) 평가에서 다루므로 지식 점수에는 반영하지 않습니다
- ⚠️ **표현의 명확성(단위 명시 등)은 전달력에서 평가하므로, 지식 피드백에서는 상품 정보의 정확성만 언급하세요**

🚨 **중요 규칙 (반드시 준수):**
1. **정확한 정보 목록에 있는 claim은 반드시 잘한 점에만 언급하고, 개선점에 절대 포함하지 마세요.**
2. **부정확한 정보 목록에 있는 claim만 개선점에 언급하세요.**
3. **같은 claim이 잘한 점과 개선점에 동시에 나타나면 안 됩니다. (모순 금지)**
4. **실제 대화 내용을 정확히 참조하세요. 대화에서 "100만원"이라고 정확히 말했다면, "최소 100"이라는 오류로 인식하지 마세요.**
5. **제품 지식 자동 검증 결과가 정확한 정보로 판단했다면, 그것을 신뢰하고 잘한 점에 언급하세요.**
"""
                    else:
                        product_accuracy_info = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **제품 지식 자동 검증 결과**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 구체적인 제품 정보 언급 없음 (금리, 한도 등 수치 정보 부재)
- 지식 점수는 일반적인 설명의 질로만 평가
"""
                
                except Exception as e:
                    print(f"⚠️ 제품 지식 검증 실패: {e}")
                    product_accuracy_info = ""
            
            elif not has_product_data:
                # 외환/송금 상담 등 상품 데이터가 없는 경우
                product_accuracy_info = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **지식 평가 방식** (상품 데이터 없음)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 제품별 정확도 검증 불가 (상품 데이터 파일 없음)
- 지식 점수는 다음 기준으로 평가:
  ✓ 절차 설명의 정확성 (송금 절차, 수수료 안내 등)
  ✓ 일반적인 금융 지식의 정확성
  ✓ 금융 규정 및 정책 이해도
  ✓ 고객 질문에 대한 적절한 답변 제공
- 구체적인 수치 정보(환율, 수수료 등)의 정확성은 LLM이 일반 지식으로 평가
"""
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 2단계: LLM을 사용하여 5가지 역량 종합 평가 (최종적으로 4가지로 통합)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            evaluation_prompt = f"""
당신은 은행 신입행원 응대 시뮬레이션 평가 전문가입니다.
다음 대화를 분석하여 5가지 역량을 **구체적이고 실용적으로** 평가하고 피드백을 제공하세요.
(참고: 명확성과 자신감은 최종 결과에서 전달력으로 통합됩니다)

{product_accuracy_info}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 **평가 지표 및 상세 기준**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1️⃣ 지식 (Knowledge, 0-100점)** ⚠️ 위 검증 결과 반영 필수
- 목적: 은행 상품(여신/수신 등) 또는 업무 절차에 대한 설명이 **정확한가** (상품 정보의 정확성)
- 평가 기준:
  ✓ 상품 정보(금리, 한도, 조건 등) 제공의 정확성 (상품 데이터 있는 경우)
    - 실제 상품 데이터와 일치하는가? (예: 금리 2.15%가 맞는가?)
    - 수치나 조건이 정확한가? (예: 최소 가입금액 100만원이 맞는가?)
  ✓ 업무 절차(송금 절차, 수수료 안내 등) 설명의 정확성 (상품 데이터 없는 경우)
  ✓ 일반적인 금융 지식 및 규정 이해도
  ✗ 잘못된 정보나 오류 발견 시 감점
  ⚠️ **표현의 명확성은 전달력 평가에서 다루므로 지식에서는 평가하지 않음**
    - 예: "최소 100" → "최소 100만원" (명확성 문제) → 전달력에서 평가
    - 예: "금리 3.5%" → "실제로는 2.15%" (정확성 문제) → 지식에서 평가
  ⚠️ 불확실한 표현("~같아요", "~보이는데요")은 전달력(자신감) 평가에서 다루므로 지식 점수에는 반영하지 않음
- 피드백 작성 시: 
  ✓ **상품 정보의 정확성**에만 집중하여 피드백 작성
  ✓ **위 제품 지식 자동 검증 결과의 "정확한 정보" 목록에 있는 claim만 잘한 점에 구체적으로 언급**
  ✓ **위 제품 지식 자동 검증 결과의 "부정확한 정보" 목록에 있는 claim만 개선점에 구체적으로 언급**
  ✓ **같은 claim이 잘한 점과 개선점에 동시에 나타나면 안 됩니다. (모순 금지)**
  ✓ 부정확한 정보는 정확한 정보와 함께 제시 (예: **"금리 3.5%"** → **"실제로는 2.15%"**)
  ✓ 위 제품 지식 자동 검증 결과의 LLM reasoning을 활용하여 구체적으로 설명
  ✗ 표현의 명확성(단위 명시, 용어 평이성 등)은 전달력에서 다루므로 지식 피드백에서 언급하지 않음
  🚨 **중요: 실제 대화 내용을 정확히 참조하세요. 대화에서 정확히 말한 내용을 오류로 인식하지 마세요**
  🚨 **중요: 제품 지식 자동 검증 결과가 정확하다고 판단한 정보는 반드시 잘한 점에만 언급하고, 개선점에 절대 포함하지 마세요**
  ⚠️ **점수가 100점이면 모든 정보가 정확하다는 의미입니다. 이 경우 개선점 섹션은 생략하거나 "제공한 모든 상품 정보가 정확합니다"와 같이 간단히 언급하세요**
- ⚠️ **위 제품 지식 자동 검증 결과가 있으면 점수에 반영하세요 (없으면 LLM이 일반 지식으로 평가)**

**2️⃣ 기술 (Skill, 0-100점)**
- 목적: 응대 절차가 체계적이며 목표를 달성했는가
- 평가 기준:
  ✓ 대화 흐름: 인사 → 요구파악 → 정보제공 → 마무리 순서
  ✓ 목표 달성도: {len(achieved_goal_indices)}/{len(goals) if goals else 0}개 달성 ({goal_achievement_rate*100:.0f}%)
  ✓ 고객 니즈 파악을 위한 적절한 질문 사용
  ✓ 피드백 루프: 요약 및 추가 확인 여부
  ✓ 고객의 추가 질문에 대비한 정보 제공
  ✓ **고객 성격 유형에 맞는 적절한 대응**: 불만형은 공감 후 해결책 제시, 급함형은 빠르고 간결한 안내, 긍정형은 친절한 안내
  ✓ **목표별 구체적 요구사항 달성 여부**: 목표 텍스트에 명시된 구체적 키워드(인용부호 내 항목, 나열된 항목 등)가 실제로 다뤄졌는지 확인
- 피드백 작성 시: 
  ✓ 어떤 절차를 잘 따랐는지 구체적으로 언급
  ✓ 달성한 목표와 미달성한 목표를 명시 (목표 텍스트를 그대로 인용)
  ✓ 미달성한 목표의 경우, 목표 텍스트에 명시된 구체적 요구사항(예: "\"기본구조·금리\"", "\"금리, 한도, 우대조건, 수수료 등\"") 중 어떤 것이 누락되었는지 구체적으로 언급
  ✓ 목표 달성률이 낮은 경우, 어떤 목표를 놓쳤는지와 개선 방안 제시 (목표 텍스트의 구체적 키워드 참조)
  ✓ **고객 성격 유형에 맞는 대응 여부 평가** (불만형: 공감→해결책, 급함형: 빠른 처리, 긍정형: 친절한 안내)
  ✓ 예: "대화 흐름은 체계적이었지만, '고객의 문의 의도와 현재 금융 상황(소득, 거래 패턴 등)을 정확히 파악한다' 목표를 달성하지 못했습니다. 고객에게 소득이나 거래 패턴을 먼저 물어보는 것이 좋습니다."
  ✓ 예: "'기본구조·금리'와 관련된 조건을 안내하는 목표는 달성했지만, '금리, 한도, 우대조건, 수수료 등' 중 우대조건과 수수료에 대한 구체적 안내가 부족했습니다."
  ✓ 예: "급함형 고객에게는 불필요한 설명을 줄이고 핵심만 간결하게 전달하는 것이 좋습니다."

**3️⃣ 명확성 (Clarity, 0-100점)**
- 목적: 명확하고 이해하기 쉬운 언어를 사용했는가
- 평가 기준:
  ✓ 문장 구조: 간결하고 명료한 문장 (100자 이내 권장)
  ✓ 논리성: 논리적 연결어 사용, 구체적 정보 제공
  ✓ 용어 평이성: KB 권장 - 전문용어보다 쉬운 말 사용
     예: "거치기간" → "이자만 내는 기간"
         "언택트" → "비대면"
         "LTV" → "담보인정비율"
         "복리" → "이자에 이자가 붙는 방식"
         "초저금리" → "아주 낮은 금리"
  ✓ 숫자 표현의 명확성: "최소 100" → "최소 100만원" (단위 명시)
  ✗ 너무 긴 문장이나 복잡한 표현 감점
  ✗ 모호한 숫자 표현 감점
- 피드백 작성 시: 
  ✓ 어떤 설명이 명확했는지 구체적으로 언급
  ✓ 모호했던 표현은 Before → After 형식으로 제안
  ✓ 예: "'최소 100' → '최소 100만원'으로 명확히 표현하세요"
  ✓ 예: "'초저금리' → '아주 낮은 금리'로 쉽게 설명하세요"

**4️⃣ 친절도 (Kindness, 0-100점)**
- 목적: 고객 중심의 배려 있는 언어를 사용했는가
- 평가 기준:
  ✓ 긍정 표현: "감사합니다", "도와드리겠습니다", "안내해 드리겠습니다"
  ✓ 정중한 어투: "~해주세요", "~드리겠습니다"
  ✓ 고객 선택권 존중: "~하시면 더 편리할 수 있습니다" (강제 느낌 없음)
  ✓ 고객의 불편/불만에 대한 공감 및 사과: "불편을 드려 죄송합니다", "기다려주셔서 감사합니다"
  ✓ 고객의 반복 질문에 대한 인내심: 같은 질문을 다시 물어봐도 친절하게 응대
  ✓ 고객의 결정 존중: "선택은 고객님께서 하시면 됩니다", "원하시는 방식으로 진행하시면 됩니다"
  ✓ 추가 도움 제공 의지: "추가로 궁금한 점 있으시면 언제든지 문의해 주세요", "다른 도움이 필요하시면 말씀해 주세요"
  ✓ 고객의 시간 존중: "시간 내주셔서 감사합니다", "빠르게 처리해 드리겠습니다"
  ✓ 고객의 상황에 맞는 배려: 고객의 금융 이해도나 상황을 고려한 설명
  ✓ 고객의 감정 상태 파악 및 적절한 대응: 고객이 답답하거나 걱정스러워할 때 공감 표현
  ✗ 부정 표현 감점: "안 됩니다", "불가능합니다", "모르겠어요"
  ✗ 명령형/무뚝뚝한 표현 감점
  ✗ 고객 선택 제한하는 표현: "더 빠르고 정확합니다" → "더 편리할 수 있습니다"
  ✗ 고객의 불만을 무시하거나 경시하는 표현
  ✗ 반복 질문에 짜증 내거나 불편해하는 표현

**⚠️ 고객 성격 유형별 특별 평가 기준:**
- **불만형 고객**: 불만 표현에 적절히 공감하고 사과했는지, 해결책을 제시했는지 평가
  ✓ 예: "불편을 드려 죄송합니다", "빠르게 해결해 드리겠습니다"
  ✗ 불만을 무시하거나 방어적인 태도 감점
- **급함형 고객**: 빠른 응답과 효율적인 안내를 했는지, 시간을 존중했는지 평가
  ✓ 예: "바로 처리해 드리겠습니다", "간단히 설명드리겠습니다"
  ✗ 불필요하게 장황한 설명이나 지연 감점
- **긍정형 고객**: 기본적인 친절도 평가 (위 일반 기준 적용)

- 피드백 작성 시: 
  ✓ 친절했던 표현을 구체적으로 인용하여 칭찬
  ✓ 개선이 필요한 표현은 Before → After 형식으로 제시
  ✓ 고객의 불편/불만에 대한 대응 여부 평가
  ✓ 고객의 반복 질문이나 추가 질문에 대한 인내심 평가
  ✓ **고객 성격 유형에 맞는 적절한 대응 여부 평가** (불만형: 공감/사과, 급함형: 빠른 응답, 긍정형: 기본 친절도)
  ✓ 예: "'더 빠르고 정확합니다' → '더 편리할 수 있습니다'로 바꾸면 고객 선택권을 존중하는 표현이 됩니다"
  ✓ 예: "고객이 답답해하실 때 '불편을 드려 죄송합니다' 같은 공감 표현을 사용하면 더 친절합니다"
  ✓ 예: "급함형 고객에게는 '바로 처리해 드리겠습니다'처럼 빠른 응답을 강조하면 좋습니다"

**5️⃣ 자신감 (Confidence, 0-100점)** - 전달력 평가의 일부
- 목적: 불확실한 어투 없이 확신 있게 안내했는가
- 평가 기준:
  ✓ 단정형 어미: "합니다", "됩니다", "가능합니다", "맞습니다"
  ✓ 확정적 표현: "~입니다", "~됩니다", "~가능합니다"
  ✗ 모호 표현 감점: "~같아요", "~일 수도 있어요", "~보이는데요"
  ✗ 불확실한 표현 감점: "확실하진 않지만", "아마도", "모르겠지만"
  ⚠️ 부정확한 정보를 확신 있게 말한 경우도 감점 (지식 평가와 연계)
- 피드백 작성 시: 
  ✓ 자신감 있었던 부분을 구체적으로 인용하여 칭찬
  ✓ 불확실해 보였던 표현은 Before → After 형식으로 제안
  ✓ 예: "'~같아요' → '~입니다'로 바꾸면 더 확신 있게 들립니다"
  ✓ 지식 평가에서 언급한 부정확한 정보를 확신 있게 말한 경우도 언급

**💡 전달력 (Clarity + Confidence, 0-100점)**
- 명확성과 자신감을 종합하여 정보 전달 역량을 평가
- 피드백 작성 시 [명확성]과 [자신감]을 별도 문단으로 구분하여 작성
- 각 문단에서 잘한 점과 개선점을 구체적으로 제시
- 중복 제거: 지식 평가에서 이미 언급한 오류는 간단히 참조만 하고, 전달력 관점에서만 평가
- 구체적인 예시와 개선 방안 포함

**피드백 작성 형식:**
```
[명확성]
문장이 간결하고 명확했습니다. 복잡한 금융용어를 쉽게 풀어서 설명한 점이 좋았습니다. 
다만 지식 평가에서 언급한 "최소 100" 표현은 "최소 100만원"으로 명확히 설명하는 것이 좋습니다. 
"초저금리" 대신 "아주 낮은 금리" 같은 쉬운 표현을 사용하면 고객이 더 쉽게 이해할 수 있습니다.

[자신감]
대부분의 정보를 확신 있게 전달했습니다. "가능합니다", "됩니다" 같은 확정적 표현을 잘 사용했습니다. 
다만 "~같아요", "~보이는데요" 같은 불확실한 표현이 일부 있어 아쉬웠습니다. 
지식 평가에서 언급한 부정확한 정보를 확신 있게 말한 부분도 자신감 측면에서 개선이 필요합니다.
```

**⚠️ 중복 제거 가이드:**
- 지식 평가에서 이미 상세히 다룬 오류(예: "최소 100")는 전달력에서 간단히 참조만
- 예: "지식 평가에서 언급한 '최소 100' 표현은 명확성 측면에서도 개선이 필요합니다"
- 같은 오류를 여러 역량에서 반복 설명하지 말고, 각 역량의 관점에서만 평가

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 **평가 대상 정보**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**고객 정보:**
- 고객 유형: {persona.get('type', '일반')}
- 금융 이해도: {persona.get('financial_literacy', '보통')}
- 연령대: {persona.get('age_group', '')}
- 직업: {persona.get('occupation', '')}

**상담 상황:**
- 제목: {situation.get('title', '')}
- 카테고리: {situation.get('category', '')}
- 설정된 목표: {', '.join(goals) if goals else '없음'}
- 목표 달성 현황: {len(achieved_goal_indices)}/{len(goals) if goals else 0}개 달성 ({goal_achievement_rate*100:.0f}%)
{achieved_goals_text}

**대화 내용:**
{conversation_context}

⚠️ **중요: 대화 내용을 정확히 참조하세요**
- 실제 대화에서 직원이 정확히 말한 내용을 그대로 인용하세요
- 예: 대화에서 "100만원"이라고 정확히 말했다면, "최소 100"이라는 오류로 인식하지 마세요
- 제품 지식 자동 검증 결과와 실제 대화 내용을 대조하여 정확히 평가하세요

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 **피드백 작성 가이드**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

각 지표별 피드백은 **마크다운 형식**으로 작성하세요. 가독성을 높이기 위해 다음 형식을 사용하세요:

**피드백 작성 형식:**
1. **잘한 점** 섹션: `**잘한 점**` 제목 사용 (필수)
   - 구체적인 예시를 `**볼드**`로 강조
   - 예: `**"감사합니다"**, **"도와드리겠습니다"** 같은 정중한 표현을 잘 사용했습니다.`
   
2. **개선점** 섹션: `**개선점**` 제목 사용 (개선할 점이 있을 때만 작성)
   - Before → After 형식: `**"최소 100"** → **"최소 100만원"**` (양쪽 모두 볼드)
   - 중요 키워드는 `**볼드**`로 강조
   - ⚠️ **점수가 100점이거나 개선할 점이 없으면 개선점 섹션을 생략하거나 "현재 제공한 정보는 모두 정확합니다"와 같이 간단히 언급하세요**
   
3. **구체적인 예시**: 대화에서 실제로 사용한 표현을 `**따옴표와 볼드**`로 인용
   - 예: `**"거치기간"**이라는 용어 대신 **"이자만 내는 기간"**으로 설명하면 좋습니다.`

4. **실용적 조언**: 다음 시뮬레이션에서 바로 적용 가능한 팁

**마크다운 사용 가이드:**
- 중요 키워드: `**키워드**` (볼드)
- 인용 표현: `**"표현"**` (따옴표 + 볼드)
- Before → After: `**"Before"** → **"After"**`
- 섹션 제목: `**잘한 점**`, `**개선점**`
- 리스트: `- 항목` (필요시)

**중복 제거 원칙:**
- 같은 오류를 여러 역량에서 반복하지 않기
- 지식 평가에서 상세히 다룬 오류는 다른 역량에서 간단히 참조만
- 예: 지식에서 "최소 100" 오류를 상세히 설명했다면, 전달력에서는 "지식 평가에서 언급한 **'최소 100'** 표현은..." 형식으로 참조

**피드백 예시 (마크다운 형식):**
```
**잘한 점**
**"금리 2.15%"**를 명확히 제시하여 좋았습니다. **"~입니다."**, **"~됩니다."** 같은 확정적 표현을 잘 사용했습니다.

**개선점**
**"거치기간"**이라는 용어 대신 **"이자만 내는 기간"**으로 설명하면 고객이 더 쉽게 이해할 수 있습니다. **"최소 100"** → **"최소 100만원"**으로 명확히 표현하세요.
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 **출력 형식 (JSON)**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

다음 JSON 형식으로 응답하세요:
{{
    "knowledge": {{
        "score": <0-100 점수>,
        "feedback": "<마크다운 형식, **잘한 점** 섹션은 필수, **개선점** 섹션은 개선할 점이 있을 때만 작성. **상품 정보의 정확성**에만 집중하여 피드백 작성. 🚨 **중요: 위 제품 지식 자동 검증 결과의 '정확한 정보 목록'에 있는 claim만 잘한 점에 언급하고, '부정확한 정보 목록'에 있는 claim만 개선점에 언급하세요. 같은 claim이 잘한 점과 개선점에 동시에 나타나면 안 됩니다 (모순 금지).** 구체적 예시는 **볼드**로 강조. 부정확한 정보는 정확한 정보와 함께 제시 (예: **'금리 3.5%'** → **'실제로는 2.15%'**). 제품 지식 자동 검증 결과의 LLM reasoning 활용. ⚠️ 표현의 명확성(단위 명시, 용어 평이성)은 전달력에서 다루므로 지식 피드백에서 언급하지 않음. ⚠️ 점수가 100점이면 모든 정보가 정확하다는 의미이므로 개선점 섹션은 생략하거나 '제공한 모든 상품 정보가 정확합니다'와 같이 간단히 언급>"
    }},
    "skill": {{
        "score": <0-100 점수>,
        "feedback": "<마크다운 형식, **잘한 점**과 **개선점** 섹션으로 구분. 대화 흐름과 목표 달성도 평가, 구체적 개선 제안. 달성한 목표와 미달성한 목표를 명시하고, 미달성 목표에 대한 개선 방안 제시>"
    }},
    "clarity": {{
        "score": <0-100 점수>,
        "feedback": "<마크다운 형식, **잘한 점**과 **개선점** 섹션으로 구분. 문장 구조와 용어 사용 평가, 쉬운 표현 제안. 모호한 표현은 Before → After 형식으로 제안 (예: **'최소 100'** → **'최소 100만원'**)>"
    }},
    "kindness": {{
        "score": <0-100 점수>,
        "feedback": "<마크다운 형식, **잘한 점**과 **개선점** 섹션으로 구분. 친절한 표현 사례와 개선 필요 표현 지적. Before → After 형식으로 제안 (예: **'더 빠르고 정확합니다'** → **'더 편리할 수 있습니다'**)>"
    }},
    "confidence": {{
        "score": <0-100 점수>,
        "feedback": "<마크다운 형식, **잘한 점**과 **개선점** 섹션으로 구분. 자신감 있는 어투와 불확실한 표현 비교. Before → After 형식으로 제안 (예: **'~같아요'** → **'~입니다'**). 지식 평가에서 언급한 부정확한 정보를 확신 있게 말한 경우도 언급>"
    }},
    "clarity_confidence": {{
        "score": <(clarity + confidence) / 2, 0-100 점수>,
        "feedback": "<마크다운 형식, 반드시 **[명확성]**과 **[자신감]**을 별도 문단으로 구분하여 작성. 각 문단에서 **잘한 점**과 **개선점**을 구체적으로 제시. 지식 평가에서 이미 상세히 다룬 오류는 간단히 참조만 하고 전달력 관점에서만 평가 (예: '지식 평가에서 언급한 **최소 100** 표현은...'). 구체적인 예시와 Before → After 형식의 개선 방안 포함. 중복 설명 지양>"
    }},
    "summary": "<2-3문장, 전반적인 강점과 핵심 개선점 요약>",
    "improvements": "<3-4개 항목, 다음 시뮬레이션에서 즉시 적용 가능한 구체적 실천 방안>"
}}
"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": evaluation_prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            
            # JSON 파싱
            content = response.choices[0].message.content
            # JSON 블록 추출 (```json ... ``` 형식 처리)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            evaluation = json.loads(content)
            
            print(f"📈 기술 점수: {evaluation['skill']['score']}점 (상담 프로세스 + 목표 달성도 종합 평가)")
            
            # 🎯 역량 통합: 5가지 → 4가지
            # 친절도만 사용 (공감도 제거)
            kindness_score = evaluation['kindness']['score']
            kindness_feedback = evaluation['kindness']['feedback']

            # 전달력 = (명확성 + 자신감) / 2
            # GPT가 clarity_confidence를 생성했으면 사용, 없으면 평균 계산
            if 'clarity_confidence' in evaluation:
                clarity_confidence_score = evaluation['clarity_confidence']['score']
                clarity_confidence_feedback = evaluation['clarity_confidence']['feedback']
            else:
                # Fallback: 명확성과 자신감의 평균
                clarity_confidence_score = round((evaluation['clarity']['score'] + evaluation['confidence']['score']) / 2)
                # 명확성과 자신감 피드백을 자연스럽게 통합
                clarity_feedback = evaluation['clarity']['feedback']
                confidence_feedback = evaluation['confidence']['feedback']
                clarity_confidence_feedback = f"{clarity_feedback} {confidence_feedback}".replace("  ", " ").strip()
                if len(clarity_confidence_feedback) > 300:
                    clarity_confidence_feedback = clarity_confidence_feedback[:300] + "..."

            # 종합 점수 계산
            overall_score = (
                evaluation['knowledge']['score'] * 0.25 +
                evaluation['skill']['score'] * 0.25 +
                kindness_score * 0.25 +
                clarity_confidence_score * 0.25
            )
            
            # 등급 산정
            if overall_score >= 90:
                grade = 'A'
                performance_level = '탁월한 성과'
            elif overall_score >= 80:
                grade = 'B'
                performance_level = '우수한 성과'
            elif overall_score >= 70:
                grade = 'C'
                performance_level = '양호한 성과'
            elif overall_score >= 60:
                grade = 'D'
                performance_level = '보통 수준'
            else:
                grade = 'F'
                performance_level = '개선 필요'
            
            return {
                "overallScore": round(overall_score, 1),
                "grade": grade,
                "performanceLevel": performance_level,
                "summary": evaluation.get('summary', '평가를 완료했습니다.'),
                "competencies": [
                    {"name": "지식", "score": evaluation['knowledge']['score'], "maxScore": 100},
                    {"name": "기술", "score": evaluation['skill']['score'], "maxScore": 100},
                    {"name": "친절도", "score": kindness_score, "maxScore": 100},
                    {"name": "전달력", "score": clarity_confidence_score, "maxScore": 100}
                ],
                "detailedFeedback": {
                    "knowledge": evaluation['knowledge'],
                    "skill": evaluation['skill'],
                    "kindness": {
                        "score": kindness_score,
                        "feedback": kindness_feedback
                    },
                    "clarity_confidence": {
                        "score": clarity_confidence_score,
                        "feedback": clarity_confidence_feedback
                    },
                    # 하위 호환성을 위해 기존 필드도 유지 (deprecated)
                    "clarity": evaluation['clarity'],
                    "confidence": evaluation['confidence'],
                    # 공감도는 제거되었지만 하위 호환성을 위해 빈 값 제공
                    "empathy": evaluation.get('empathy', {"score": 0, "feedback": "평가되지 않음"})
                },
                "improvements": evaluation.get('improvements', '지속적인 연습을 통해 개선하세요.'),
                "goalAchievement": {  # 🎯 목표 달성 정보 추가
                    "total": len(goals) if goals else 0,
                    "achieved": len(achieved_goal_indices),
                    "rate": goal_achievement_rate,
                    "goals": [
                        {
                            "text": goals[i],
                            "achieved": i in achieved_goal_indices,
                            # 🔍 3단계: 달성 증거 포함
                            "turn": turn_tracking.get(i, {}).get("turn") if i in achieved_goal_indices else None,
                            "evidence": turn_tracking.get(i, {}).get("evidence") if i in achieved_goal_indices else None
                        }
                        for i in range(len(goals))
                    ] if goals else []
                }
            }
            
        except Exception as e:
            print(f"❌ 종합 피드백 생성 실패: {e}")
            import traceback
            traceback.print_exc()
            return self._get_default_feedback()
    
    def _get_default_feedback(self) -> Dict:
        """기본 피드백 (오류 발생 시)"""
        # 통합된 4가지 역량으로 반환
        return {
            "overallScore": 70.0,
            "grade": "C",
            "performanceLevel": "양호한 성과",
            "summary": "시뮬레이션을 완료했습니다. 더 많은 연습을 통해 역량을 향상시켜보세요.",
            "competencies": [
                {"name": "지식", "score": 70, "maxScore": 100},
                {"name": "기술", "score": 70, "maxScore": 100},
                {"name": "친절도", "score": 70, "maxScore": 100},
                {"name": "전달력", "score": 70, "maxScore": 100}
            ],
            "detailedFeedback": {
                "knowledge": {"score": 70, "feedback": "기본적인 지식은 갖추고 있습니다."},
                "skill": {"score": 70, "feedback": "상담 흐름을 잘 따르고 있습니다."},
                "kindness": {
                    "score": 70,
                    "feedback": "친절한 응대를 하고 있습니다."
                },
                "clarity_confidence": {
                    "score": 70,
                    "feedback": "설명이 대체로 명확하고 자신감 있는 어투를 유지하세요."
                },
                # 하위 호환성을 위해 기존 필드도 유지 (deprecated)
                "empathy": {"score": 70, "feedback": "고객에게 공감하는 태도를 보입니다."},
                "clarity": {"score": 70, "feedback": "설명이 대체로 명확합니다."},
                "confidence": {"score": 70, "feedback": "자신감있는 어투를 유지하세요."}
            },
            "improvements": "지속적인 연습을 통해 역량을 향상시켜보세요."
        }
    
    def analyze_goal_achievement(
        self,
        conversation_history: List[Dict],
        goals: List[str],
        return_detailed: bool = False
    ) -> List[int] | Dict:
        """
        대화 내용을 분석하여 달성된 목표 인덱스 리스트 반환
        
        Args:
            conversation_history: 대화 히스토리 (예: [{"role": "user", "text": "..."}, ...])
            goals: 목표 목록 (예: ["고객의 요구사항 파악", "적절한 상품 추천", ...])
            return_detailed: True면 턴별 추적 정보 포함 (2단계용)
        
        Returns:
            기본: 달성된 목표의 인덱스 리스트 (예: [0, 2])
            상세: {
                "achieved_indices": [0, 2],
                "turn_tracking": {
                    0: {"turn": 3, "evidence": "..."},
                    2: {"turn": 5, "evidence": "..."}
                }
            }
        """
        if not self.openai_client:
            print("⚠️ OpenAI 클라이언트가 초기화되지 않았습니다.")
            return []
        
        if not goals or not conversation_history:
            return []
        
        # 전체 대화 내용 추출 (고객과 직원 모두 포함)
        conversation_parts = []
        for msg in conversation_history:
            role = msg.get("role", "")
            text = msg.get("text", "")
            if role == "user":
                conversation_parts.append(f"직원: {text}")
            elif role == "customer":
                conversation_parts.append(f"고객: {text}")
        
        if not conversation_parts:
            return []
        
        # 대화 내용 요약 (전체 맥락 포함)
        conversation_text = "\n".join(conversation_parts)
        
        # 목표 목록 문자열 생성
        goals_text = "\n".join([
            f"{i}. {goal}"
            for i, goal in enumerate(goals)
        ])
        
        # LLM 프롬프트 구성
        prompt = f"""당신은 은행 직원의 고객 상담 대화를 평가하는 전문가입니다.

다음은 은행 직원과 고객의 전체 대화 내용입니다:
---
{conversation_text}
---

다음은 이 상담에서 달성해야 하는 목표 목록입니다:
---
{goals_text}
---

위 대화 내용을 자세히 분석하여, 각 목표가 달성되었는지 판단해주세요.

**판단 기준 (매우 중요):**

1. **구체성 요구**: 목표는 "실질적인 정보 제공"이 있을 때만 달성으로 인정
   - ❌ 나쁜 예: "환율에 대해 설명드리겠습니다" (실제 설명 없음)
   - ✅ 좋은 예: "현재 달러 환율은 1,300원이며, 환전 수수료는 2%입니다"

2. **정보의 충실성**: 모호하거나 불완전한 답변은 미달성
   - ❌ "이러이러합니다", "그렇습니다", "확인해보겠습니다" (구체적 정보 없음)
   - ❌ "송금 절차는 복잡합니다" (절차 내용 설명 없음)
   - ✅ "송금은 1) 신청서 작성 2) 신분증 제시 3) 송금 완료 순으로 진행됩니다"

3. **목표 텍스트의 구체적 키워드 활용** (🚨 새 형식 특화):
   - 목표 텍스트에 인용부호("")로 강조된 구체적 항목이 있으면, 그 항목들을 모두 다뤘는지 확인
   - 예: 목표에 "\"기본구조·금리\""가 있으면 → 기본구조와 금리 둘 다 다뤘는지 확인
   - 예: 목표에 "\"금리, 한도, 우대조건, 수수료 등\""이 있으면 → 최소 2개 이상 다뤘는지 확인
   - 목표 텍스트에 나열된 구체적 항목(예: "소득, 거래 패턴 등")이 있으면, 최소 1개 이상 언급되었는지 확인
   - 목표가 요구하는 행동 동사(예: "파악한다", "설명하고", "안내하는", "정리해 주고")가 실제로 수행되었는지 확인

4. **목표 키워드 확인**:
   - "파악한다": 고객의 의도/상황을 이해하고 확인하는 대화가 있어야 함 (질문-답변 형식)
   - "설명하고/이해시키는": 구체적인 내용(수치, 절차, 조건 등)이 포함되어야 함
   - "안내하는": 실제 방법이나 단계가 제시되어야 함
   - "고려한다/설명해": 명시적인 경고나 정보 전달이 있어야 함
   - "정리해 주고": 다음 단계나 필요 사항을 명확히 정리해야 함

5. **직원 발화만 평가**: 고객이 말한 내용은 달성 근거가 될 수 없음
   - 직원이 실제로 해당 정보를 제공했는지만 확인
   - 고객의 질문에 대한 직원의 답변으로 달성 판단

6. **엄격한 평가**: 의심스러우면 미달성으로 판단
   - 목표가 요구하는 것의 70% 이상을 충족해야 달성으로 인정
   - 단순히 주제를 언급하는 것만으로는 부족
   - 목표 텍스트에 명시된 구체적 항목들이 모두 다뤄지지 않았으면 미달성

**판단 프로세스:**
각 목표에 대해:
1) 목표 텍스트에서 구체적인 키워드와 요구사항 추출 (인용부호 내 항목, 나열된 항목, 행동 동사)
2) 직원 발화에서 관련 키워드와 정보 찾기
3) 목표에 명시된 구체적 항목들이 다뤄졌는지 확인
4) 목표가 요구하는 행동(파악/설명/안내 등)이 실제로 수행되었는지 확인
5) 목표가 요구하는 수준의 70% 이상을 충족하는지 판단
6) 충족하면 달성, 아니면 미달성

**출력 형식:**
달성된 목표 번호만 쉼표로 구분하여 출력하세요. 예를 들어, 0번과 2번 목표가 달성되었다면:
0,2

달성된 목표가 하나도 없다면:
없음

달성된 목표 번호만 출력하세요. 추가 설명이나 다른 텍스트는 포함하지 마세요."""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.3  # 일관된 평가를 위해 낮은 temperature 사용
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 결과 파싱
            if result_text.lower() in ["없음", "none", "없습니다", ""]:
                return []
            
            # 쉼표로 구분된 숫자들 추출
            achieved_indices = []
            for part in result_text.split(","):
                part = part.strip()
                try:
                    index = int(part)
                    if 0 <= index < len(goals):
                        achieved_indices.append(index)
                except ValueError:
                    continue
            
            # 기본 모드: 인덱스만 반환
            if not return_detailed:
                return achieved_indices
            
            # 🔍 2단계: 턴별 추적 분석
            turn_tracking = {}
            
            if achieved_indices:
                print(f"\n🔍 턴별 추적 분석 시작 (달성된 목표: {len(achieved_indices)}개)")
                
                for goal_idx in achieved_indices:
                    goal_text = goals[goal_idx]
                    
                    # 🔍 직원 발화에 턴 번호 붙이기
                    employee_utterances_with_turn = []
                    turn_number = 0
                    for msg in conversation_history:
                        turn_number += 1
                        if msg.get('role') in ['employee', 'user']:
                            text = msg.get('text', '')
                            employee_utterances_with_turn.append(f"턴 {turn_number} [직원]: {text}")
                    
                    employee_conversation = "\n".join(employee_utterances_with_turn)
                    
                    # 각 달성된 목표에 대해 어느 턴에서 달성되었는지 GPT에게 물어보기
                    tracking_prompt = f"""다음은 은행 신입사원(직원)의 발화만 추출한 대화입니다.
"{goal_text}" 목표가 달성된 턴을 찾아주세요.

직원 발화:
{employee_conversation}

목표: {goal_text}

**중요 평가 기준**: 
1. **직원이 실제로 구체적인 정보를 제공한 발화를 찾으세요**
   - 단순히 주제를 언급하는 것이 아니라, 목표를 실질적으로 달성한 발화여야 합니다
   
2. **목표 텍스트의 구체적 키워드 확인**:
   - 목표에 인용부호("")로 강조된 구체적 항목이 있으면, 그 항목들이 실제로 언급되었는지 확인
   - 예: 목표에 "\"기본구조·금리\""가 있으면 → 기본구조와 금리 둘 다 다룬 발화인지 확인
   - 예: 목표에 "\"금리, 한도, 우대조건, 수수료 등\""이 있으면 → 최소 2개 이상 언급된 발화인지 확인
   - 목표 텍스트에 나열된 구체적 항목(예: "소득, 거래 패턴 등")이 최소 1개 이상 언급되었는지 확인
   
3. **목표가 요구하는 행동 확인**:
   - "파악한다" → 고객의 의도/상황을 이해하고 확인하는 대화
   - "설명하고/이해시키는" → 구체적인 내용(수치, 절차, 조건 등) 포함
   - "안내하는" → 실제 방법이나 단계 제시
   - "고려한다/설명해" → 명시적인 경고나 정보 전달
   - "정리해 주고" → 다음 단계나 필요 사항 명확히 정리
   
4. **여러 턴에서 달성되었다면 가장 명확한 턴을 선택하세요**

출력 형식:
턴번호: 발화내용 (직원이 한 말)

예: 5: 현재 달러 환율은 1,300원이며, 환전 수수료는 2%입니다.

찾을 수 없으면 "없음"이라고만 출력하세요."""
                    
                    try:
                        tracking_response = self.openai_client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": tracking_prompt}],
                            max_tokens=200,
                            temperature=0.2
                        )
                        
                        tracking_result = tracking_response.choices[0].message.content.strip()
                        
                        if tracking_result and tracking_result.lower() not in ["없음", "none"]:
                            # "3: 발화내용" 형식 파싱
                            if ":" in tracking_result:
                                parts = tracking_result.split(":", 1)
                                try:
                                    turn_num = int(parts[0].strip())
                                    evidence = parts[1].strip()
                                    
                                    # 증거가 직원 발화인지 재확인 (고객 발화 제외)
                                    # "고객:", "저는", "제가" 등이 포함되면 의심
                                    evidence_lower = evidence.lower()
                                    if any(word in evidence_lower for word in ['고객:', '고객님이', '저는', '제가', '나는', '내가']):
                                        print(f"  ⚠️ 목표 {goal_idx} → 턴 {turn_num}: 고객 발화로 의심됨, 재확인 필요")
                                        # 그래도 저장은 함 (사용자가 판단할 수 있도록)
                                    
                                    turn_tracking[goal_idx] = {
                                        "turn": turn_num,
                                        "evidence": evidence[:200]  # 최대 200자로 증가
                                    }
                                    print(f"  ✓ 목표 {goal_idx} '{goal_text[:30]}...' → 턴 {turn_num}에서 달성")
                                except Exception as parse_error:
                                    print(f"  ⚠️ 목표 {goal_idx} 파싱 실패: {parse_error}")
                                    print(f"     응답: {tracking_result}")
                        else:
                            print(f"  ⚠️ 목표 {goal_idx} '{goal_text[:30]}...' → 증거 찾기 실패 (GPT 응답: {tracking_result})")
                        
                    except Exception as e:
                        print(f"  ⚠️ 목표 {goal_idx} 추적 API 호출 실패: {e}")
            
            return {
                "achieved_indices": achieved_indices,
                "turn_tracking": turn_tracking
            }
            
        except Exception as e:
            print(f"목표 달성 분석 오류: {e}")
            import traceback
            traceback.print_exc()
            if return_detailed:
                return {"achieved_indices": [], "turn_tracking": {}}
            return []
    
    def _process_test_mode_interaction(self, session_data: Dict, audio_data: bytes, user_message: str = "") -> Dict:
        """테스트 모드 음성 상호작용 처리 - 고정 시나리오만 사용, 고객 응답 자동 생성 안 함"""
        print("🧪 ===== 테스트 모드 처리 시작 =====")
        
        test_scenario = session_data.get("test_scenario", {})
        turns = test_scenario.get("turns", [])
        current_turn_index = session_data.get("current_turn_index", 0)
        conversation_history = session_data.get("conversation_history", [])
        stt_evaluations = session_data.get("stt_evaluations", [])
        
        print(f"🧪 현재 턴 인덱스: {current_turn_index}, 전체 턴 수: {len(turns)}")
        
        if current_turn_index >= len(turns):
            # 모든 턴 완료 - 일반 모드와 동일한 지식 평가 수행
            print(f"🧪 ===== 테스트 모드 완료 =====")
            print(f"🧪 STT 평가: {len(stt_evaluations)}개")
            
            # STT 평가 결과
            stt_evaluation_result = self._evaluate_stt_performance(stt_evaluations)
            
            # 🔍 일반 모드와 동일한 지식 평가 로직 수행
            knowledge_verification_result = None
            knowledge_evaluation_result = None
            product_accuracy_info = ""
            
            # 직원 발화만 필터링 (일반 모드와 동일)
            employee_utterances = [
                msg for msg in conversation_history 
                if msg.get("role") == "employee"
            ]
            
            # 상황 정보 가져오기 (일반 모드와 동일한 방식)
            situation = session_data.get("situation", {})
            situation_id = situation.get('id', '')
            has_product_data = situation.get('has_product_data', True)
            
            # 외환/송금 상담은 상품 데이터가 없으므로 제품 검증 스킵
            if situation_id == 'fx':
                has_product_data = False
                print("🧪 ℹ️ 외환/송금 상담: 상품 데이터 없음 - 제품 검증 스킵")
            
            if self.product_knowledge_service and has_product_data and employee_utterances:
                try:
                    print("🧪 🔍 제품 지식 정확도 자동 검증 시작 (일반 모드와 동일한 로직)...")
                    knowledge_verification_result = self.product_knowledge_service.batch_verify_conversation(
                        employee_utterances,
                        use_llm=True  # LLM 검증 포함
                    )
                    
                    accuracy_rate = knowledge_verification_result['accuracy_rate']
                    total_claims = knowledge_verification_result['total_claims']
                    accurate_claims = knowledge_verification_result['accurate_claims']
                    inaccurate_claims = knowledge_verification_result['inaccurate_claims']
                    
                    print(f"🧪   ✓ 제품 정보 검증 완료: {accurate_claims}/{total_claims} 정확 ({accuracy_rate:.1%})")
                    
                    # 일반 모드와 동일한 방식으로 product_accuracy_info 생성
                    errors_detail = []
                    accurate_details = []
                    llm_reasonings = []
                    
                    for v in knowledge_verification_result.get('verifications', []):
                        claim_display = v.claim
                        if hasattr(v, 'full_utterance') and v.full_utterance:
                            if v.claim in v.full_utterance:
                                claim_display = f"'{v.claim}' (대화: ...{v.full_utterance[max(0, v.full_utterance.find(v.claim)-20):min(len(v.full_utterance), v.full_utterance.find(v.claim)+len(v.claim)+20)]}...)"
                        
                        if not v.is_accurate:
                            errors_detail.append(f"• {claim_display} → 실제: {v.ground_truth[:80]}...")
                        else:
                            accurate_details.append(f"• {claim_display} (정확함)")
                        
                        if hasattr(v, 'llm_reasoning') and v.llm_reasoning:
                            llm_reasonings.append(f"• {v.claim}: {v.llm_reasoning}")
                    
                    if total_claims > 0:
                        reasoning_section = ""
                        if llm_reasonings:
                            reasoning_section = f"""
💡 **검증 상세 분석 (LLM reasoning):**
{chr(10).join(llm_reasonings[:5])}
"""
                        
                        accurate_section = ""
                        if accurate_details:
                            accurate_section = f"""
✅ **정확한 정보 목록 (반드시 잘한 점에 언급):**
{chr(10).join(accurate_details[:5])}

⚠️ **위 정확한 정보 목록의 claim은 모두 정확한 정보입니다.**
⚠️ **위 목록에 있는 claim은 개선점에 절대 포함하지 마세요.**
⚠️ **위 목록에 있는 claim은 잘한 점에만 구체적으로 언급하세요.**
"""
                        
                        errors_section = ""
                        if errors_detail:
                            errors_section = f"""
⚠️ **부정확한 정보 목록 (개선점에만 언급):**
{chr(10).join(errors_detail[:5])}

⚠️ **위 부정확한 정보 목록의 claim만 개선점에 언급하세요.**
⚠️ **위 목록에 없는 claim은 개선점에 포함하지 마세요.**
⚠️ **정확한 정보 목록에 있는 claim과 부정확한 정보 목록에 있는 claim이 겹치면 안 됩니다.**
"""
                        else:
                            errors_section = """
⚠️ **부정확한 정보: 없음**
→ 개선점 섹션은 생략하거나 "제공한 모든 상품 정보가 정확합니다"와 같이 간단히 언급하세요.
"""
                        
                        product_accuracy_info = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **제품 지식 자동 검증 결과** (객관적 데이터 - 반드시 정확히 반영하세요)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 총 제품 정보 언급: {total_claims}개
- 정확한 정보: {accurate_claims}개
- 부정확한 정보: {inaccurate_claims}개
- 정확도: {accuracy_rate:.1%}
- 검증 방법: {knowledge_verification_result.get('verification_methods', {})}

{accurate_section}
{errors_section}
{reasoning_section}
💡 **지식 점수 평가 및 피드백 작성 가이드:**
- 정확도 {accuracy_rate:.1%} → 기본 점수 {int(accuracy_rate * 100)}점 (오류는 이미 정확도에 반영됨)
- ⚠️ 오류 개수는 점수 계산에 사용하지 말고, 피드백 작성 시에만 참고하세요
- ⚠️ 불확실한 표현("같아요", "모르겠" 등)은 전달력(자신감) 평가에서 다루므로 지식 점수에는 반영하지 않습니다
- ⚠️ **표현의 명확성(단위 명시 등)은 전달력에서 평가하므로, 지식 피드백에서는 상품 정보의 정확성만 언급하세요**

🚨 **중요 규칙 (반드시 준수):**
1. **정확한 정보 목록에 있는 claim은 반드시 잘한 점에만 언급하고, 개선점에 절대 포함하지 마세요.**
2. **부정확한 정보 목록에 있는 claim만 개선점에 언급하세요.**
3. **같은 claim이 잘한 점과 개선점에 동시에 나타나면 안 됩니다. (모순 금지)**
4. **실제 대화 내용을 정확히 참조하세요. 대화에서 "100만원"이라고 정확히 말했다면, "최소 100"이라는 오류로 인식하지 마세요.**
5. **제품 지식 자동 검증 결과가 정확한 정보로 판단했다면, 그것을 신뢰하고 잘한 점에 언급하세요.**
"""
                    else:
                        product_accuracy_info = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **제품 지식 자동 검증 결과**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 구체적인 제품 정보 언급 없음 (금리, 한도 등 수치 정보 부재)
- 지식 점수는 일반적인 설명의 질로만 평가
"""
                    
                    # 일반 모드와 동일한 방식으로 지식 평가서 생성 (검증용)
                    # 실제로는 LLM을 호출하지 않고 검증 결과만 반환하지만,
                    # 일반 모드와 동일한 구조로 평가서 항목 생성 가능 여부 확인
                    knowledge_evaluation_result = {
                        "accuracy_rate": accuracy_rate,
                        "knowledge_score": int(accuracy_rate * 100),  # 일반 모드와 동일한 점수 산정
                        "total_claims": total_claims,
                        "accurate_claims": accurate_claims,
                        "inaccurate_claims": inaccurate_claims,
                        "product_accuracy_info": product_accuracy_info,
                        "verifications": knowledge_verification_result.get('verifications', [])
                    }
                    
                    # 🆕 각 turn의 RAG 평가 결과에 해당 turn의 claim 검증 결과 매핑
                    rag_evaluations = session_data.get("rag_evaluations", [])
                    if rag_evaluations and knowledge_verification_result:
                        # 각 RAG 평가 결과에 해당 turn의 발화 텍스트로 claim 검증 결과 필터링
                        for rag_eval in rag_evaluations:
                            if rag_eval.get("role") != "employee":
                                continue
                                
                            turn_index = rag_eval.get("turn_index")
                            # 해당 turn의 발화 텍스트 찾기
                            turn_text = None
                            test_scenario = session_data.get("test_scenario", {})
                            turns = test_scenario.get("turns", [])
                            if turn_index < len(turns):
                                # 실제 발화는 conversation_history에서 찾기
                                employee_utterance_count = 0
                                for msg in conversation_history:
                                    if msg.get("role") == "employee":
                                        if employee_utterance_count == turn_index:
                                            turn_text = msg.get("text", "")
                                            break
                                        employee_utterance_count += 1
                            
                            if turn_text:
                                # 해당 turn의 발화 텍스트와 일치하는 claim 검증 결과 필터링
                                turn_verifications = []
                                for v in knowledge_verification_result.get('verifications', []):
                                    full_utterance = getattr(v, 'full_utterance', None) or getattr(v, 'utterance', None)
                                    if full_utterance and turn_text in full_utterance:
                                        turn_verifications.append(v)
                                
                                if turn_verifications:
                                    # 해당 turn의 claim 검증 결과를 RAG 평가 결과에 추가
                                    rag_eval["evaluation"]["claim_verifications"] = [
                                        {
                                            "claim": v.claim,
                                            "is_accurate": v.is_accurate,
                                            "ground_truth": getattr(v, 'ground_truth', None),
                                            "similarity": getattr(v, 'similarity', None),
                                            "verification_method": getattr(v, 'verification_method', None),
                                            "llm_reasoning": getattr(v, 'llm_reasoning', None)
                                        }
                                        for v in turn_verifications
                                    ]
                                    print(f"🧪 ✅ 턴 {turn_index}의 RAG 평가에 {len(turn_verifications)}개 claim 검증 결과 추가")
                                else:
                                    print(f"🧪 ⚠️ 턴 {turn_index}의 발화에서 claim 검증 결과를 찾지 못했습니다.")
                    
                except Exception as e:
                    print(f"🧪 ⚠️ 제품 지식 검증 실패: {e}")
                    import traceback
                    traceback.print_exc()
                    product_accuracy_info = ""
            
            elif not has_product_data:
                # 외환/송금 상담 등 상품 데이터가 없는 경우
                product_accuracy_info = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **지식 평가 방식** (상품 데이터 없음)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 제품별 정확도 검증 불가 (상품 데이터 파일 없음)
- 지식 점수는 다음 기준으로 평가:
  ✓ 절차 설명의 정확성 (송금 절차, 수수료 안내 등)
  ✓ 일반적인 금융 지식의 정확성
  ✓ 금융 규정 및 정책 이해도
  ✓ 고객 질문에 대한 적절한 답변 제공
- 구체적인 수치 정보(환율, 수수료 등)의 정확성은 LLM이 일반 지식으로 평가
"""
            
            return {
                "transcribed_text": "",
                "customer_response": "",
                "customer_audio": None,
                "feedback": "테스트 시나리오가 완료되었습니다.",
                "conversation_phase": "completed",
                "session_score": 0,
                "conversation_history": conversation_history,
                "end_signal": True,
                "stt_evaluation": stt_evaluation_result,  # 턴별 STT 평가 결과
                "knowledge_verification_result": knowledge_verification_result,  # 일반 모드와 동일한 검증 결과
                "knowledge_evaluation_result": knowledge_evaluation_result,  # 지식 평가서 항목 (검증용)
                "product_accuracy_info": product_accuracy_info,  # LLM 프롬프트용 정보 (일반 모드와 동일)
                "test_completed": True
            }
        
        current_turn = turns[current_turn_index]
        print(f"🧪 현재 턴: {current_turn.get('role')} - {current_turn.get('expected_text', '')[:50]}...")
        
        # STT 처리
        if not user_message:
            transcribed_text = self._speech_to_text(audio_data) if audio_data else ""
        else:
            transcribed_text = user_message
        
        print(f"🧪 ===== 테스트 모드 턴 처리 시작 ======")
        print(f"🧪 current_turn_index: {current_turn_index}")
        print(f"🧪 current_turn role: {current_turn.get('role')}")
        print(f"🧪 current_turn expected_text: {current_turn.get('expected_text', '')[:50]}...")
        print(f"🧪 STT 결과: {transcribed_text}")
        print(f"🧪 conversation_history 현재 길이: {len(conversation_history)}")
        
        # STT 평가 (고객 발화인 경우)
        if current_turn["role"] == "customer":
            expected_text = current_turn.get("expected_text", "")
            expected_product_code = current_turn.get("product_code")
            expected_keywords = current_turn.get("keywords", [])
            
            # 1. STT 평가 (금융 용어 인식 정확도)
            stt_eval = self._evaluate_single_stt(transcribed_text, expected_text, expected_keywords)
            stt_evaluations.append(stt_eval)
            
            # 2. 고객 발화는 STT 평가만 수행 (지식 평가는 대화 종료 후 직원 발화만 평가)
            # 테스트 모드 목적: STT 검증 + 지식 파트 점수 산정 로직 검증
            # 지식 평가는 일반 모드와 동일하게 대화 종료 후 batch_verify_conversation()으로 수행
            
            # 🧪 테스트 모드: 고객 발화는 정해진 스크립트로 자동 생성
            # STT로 받은 텍스트는 평가용으로만 사용하고, 실제 고객 응답은 expected_text 사용
            customer_response_text = expected_text  # 정해진 고객 응답 사용
            
            # 고객 발화를 히스토리에 추가 (정해진 스크립트 사용)
            conversation_history.append({
                "role": "customer",
                "text": customer_response_text,  # 정해진 스크립트 사용
                "timestamp": datetime.now().isoformat()
            })
            
            # 고객 응답을 TTS로 변환
            print(f"🧪 고객 응답 TTS 생성: {customer_response_text[:50]}...")
            # 세션 데이터에서 persona 가져오기
            persona = session_data.get("persona", {})
            customer_audio = self._text_to_speech(customer_response_text, persona)
            print(f"🧪 고객 응답 TTS 완료")
            
            # 다음 턴으로 이동 (직원 응답은 사용자가 따라 말해야 함)
            next_turn_index = current_turn_index + 1
            if next_turn_index < len(turns):
                next_turn = turns[next_turn_index]
                if next_turn["role"] == "employee":
                    # 테스트 모드에서는 직원 응답을 자동 생성하지 않고, 사용자가 따라 말하도록 함
                    # 다음 턴의 expected_text를 반환하여 프론트엔드에 표시
                    next_expected_text = next_turn.get("expected_text", "")
                    print(f"🧪 고객 발화 완료. 다음 턴(직원): {next_expected_text[:50]}...")
                    print(f"🧪 고객 응답은 정해진 스크립트로 자동 생성됨")
                    
                    print(f"🧪 ✅ 고객 발화 처리 완료")
                    return {
                        "transcribed_text": transcribed_text,  # STT 결과 (평가용)
                        "customer_response": customer_response_text,  # 🧪 정해진 고객 응답
                        "customer_audio": customer_audio,  # 🧪 고객 응답 TTS
                        "feedback": f"STT 정확도: {stt_eval['accuracy']:.1f}%",
                        "conversation_phase": "ongoing",
                        "session_score": 0,
                        "conversation_history": conversation_history,
                        "current_turn_index": next_turn_index,  # 다음 턴(직원 응답)으로 이동
                        "stt_evaluations": stt_evaluations,
                        "stt_evaluation": stt_eval,
                        "next_turn_expected_text": next_expected_text,  # 다음 턴의 기대 텍스트 (직원 응답)
                        "next_turn_role": "employee",  # 다음 턴 역할
                        "is_test_mode": True  # 🧪 테스트 모드 플래그 명시
                    }
        
        # 직원 발화인 경우 (STT 평가 + RAG 연동 평가)
        if current_turn["role"] == "employee":
            expected_text = current_turn.get("expected_text", "")
            expected_product_code = current_turn.get("product_code")
            expected_keywords = current_turn.get("keywords", [])
            
            # 1. STT 평가 (직원 발화의 금융 용어 인식 정확도)
            stt_eval = self._evaluate_single_stt(transcribed_text, expected_text, expected_keywords)
            stt_evaluations.append(stt_eval)
            
            # 2. 직원 발화는 STT 평가만 수행 (지식 평가는 대화 종료 후 일괄 수행)
            # 테스트 모드 목적: STT 검증 + 지식 파트 점수 산정 로직 검증
            # 지식 평가는 일반 모드와 동일하게 대화 종료 후 batch_verify_conversation()으로 수행
            
            # 🧪 직원 발화를 conversation_history에 추가 (프론트엔드에서도 동일하게 표시되도록)
            # 중요: 프론트엔드에서 role='user'로 표시되므로, 여기서는 'employee'로 저장
            conversation_history.append({
                "role": "employee",
                "text": transcribed_text,
                "timestamp": datetime.now().isoformat()
            })
            print(f"🧪 직원 발화를 conversation_history에 추가: {transcribed_text[:50]}...")
            print(f"🧪 conversation_history 길이: {len(conversation_history)}")
            
            # 다음 턴으로 이동
            next_turn_index = current_turn_index + 1
            next_turn_expected_text = ""
            customer_response_text = ""
            customer_audio = None
            
            # 🧪 테스트 모드: 다음 턴이 고객이면 자동으로 고객 응답 생성
            if next_turn_index < len(turns):
                next_turn = turns[next_turn_index]
                if next_turn.get("role") == "customer":
                    # 고객 응답 자동 생성
                    customer_response_text = next_turn.get("expected_text", "")
                    print(f"🧪 직원 발화 완료. 다음 턴(고객) 자동 생성: {customer_response_text[:50]}...")
                    
                    # 고객 응답을 히스토리에 추가
                    conversation_history.append({
                        "role": "customer",
                        "text": customer_response_text,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # 고객 응답 TTS 생성
                    persona = session_data.get("persona", {})
                    customer_audio = self._text_to_speech(customer_response_text, persona)
                    print(f"🧪 고객 응답 TTS 완료")
                    
                    # 그 다음 턴(직원)의 expected_text 가져오기
                    next_next_turn_index = next_turn_index + 1
                    if next_next_turn_index < len(turns):
                        next_next_turn = turns[next_next_turn_index]
                        if next_next_turn.get("role") == "employee":
                            next_turn_expected_text = next_next_turn.get("expected_text", "")
                            next_turn_index = next_next_turn_index  # 직원 턴으로 이동
                elif next_turn.get("role") == "employee":
                    next_turn_expected_text = next_turn.get("expected_text", "")
            
            # 🧪 테스트 모드: 모든 턴이 끝난 후에만 종료 트리거 체크
            # 다음 턴이 없고 (모든 테스트 대화 완료), 직원 발화에 종료 트리거가 있으면 종료
            all_turns_completed = next_turn_index >= len(turns)
            employee_has_closing_trigger = any(
                trigger in transcribed_text for trigger in END_CONVERSATION_TRIGGERS
            )
            
            if all_turns_completed and employee_has_closing_trigger:
                # 모든 테스트 대화가 끝나고 종료 트리거가 감지되면 종료
                # 일반 모드와 동일한 지식 평가 수행 (위의 if current_turn_index >= len(turns) 블록과 동일)
                print(f"🧪 테스트 모드: 모든 턴 완료 + 종료 트리거 감지 - 시뮬레이션 종료")
                # 지식 평가는 위의 if current_turn_index >= len(turns) 블록에서 수행되므로
                # 여기서는 단순히 종료 신호만 반환 (실제로는 위 블록이 먼저 실행됨)
                return {
                    "transcribed_text": transcribed_text,
                    "customer_response": "",
                    "customer_audio": None,
                    "feedback": "테스트 시나리오가 완료되었습니다.",
                    "conversation_phase": "completed",
                    "session_score": 0,
                    "conversation_history": conversation_history,
                    "end_signal": True,
                    "stt_evaluation": self._evaluate_stt_performance(stt_evaluations),
                    "test_completed": True
                }
            
            print(f"🧪 직원 발화 완료. 다음 턴: {next_turn_expected_text[:50] if next_turn_expected_text else '없음'}...")
            if customer_response_text:
                print(f"🧪 고객 응답 자동 생성됨: {customer_response_text[:50]}...")
            else:
                print(f"🧪 customer_response는 빈 문자열로 반환 (다음 턴이 직원)")
            
            print(f"🧪 ✅ 직원 발화 처리 완료")
            
            # 다음 턴 역할 결정
            next_role = None
            if next_turn_index < len(turns):
                next_role = turns[next_turn_index].get("role")
            
            return {
                "transcribed_text": transcribed_text,
                "customer_response": customer_response_text,  # 🧪 다음 턴이 고객이면 자동 생성, 아니면 빈 문자열
                "customer_audio": customer_audio,  # 🧪 다음 턴이 고객이면 TTS 생성, 아니면 None
                "feedback": f"STT 정확도: {stt_eval['accuracy']:.1f}%",
                "conversation_phase": "ongoing",
                "session_score": 0,
                "conversation_history": conversation_history,
                "current_turn_index": next_turn_index,
                "stt_evaluations": stt_evaluations,
                "stt_evaluation": stt_eval,
                "next_turn_expected_text": next_turn_expected_text,  # 다음 턴의 기대 텍스트 (직원 응답)
                "next_turn_role": next_role,  # 다음 턴 역할
                "is_test_mode": True,  # 🧪 테스트 모드 플래그 명시
                "end_signal": False  # 테스트 대화가 모두 끝나지 않았으면 종료 안 함
            }
        
        return {
            "transcribed_text": transcribed_text,
            "customer_response": "",
            "customer_audio": None,
            "feedback": "처리 완료",
            "conversation_phase": "ongoing",
            "session_score": 0,
            "conversation_history": conversation_history
        }
    
    def _evaluate_single_stt(self, transcribed: str, expected: str, keywords: List[str]) -> Dict:
        """단일 STT 결과 평가"""
        from difflib import SequenceMatcher
        accuracy = SequenceMatcher(None, transcribed, expected).ratio() * 100
        
        recognized_keywords = [kw for kw in keywords if kw in transcribed]
        keyword_recognition_rate = (len(recognized_keywords) / len(keywords) * 100) if keywords else 100
        
        return {
            "transcribed": transcribed,
            "expected": expected,
            "accuracy": accuracy,
            "keyword_recognition_rate": keyword_recognition_rate,
            "recognized_keywords": recognized_keywords,
            "missing_keywords": [kw for kw in keywords if kw not in transcribed]
        }
    
    def _evaluate_stt_performance(self, stt_evaluations: List[Dict]) -> Dict:
        """전체 STT 성능 평가"""
        if not stt_evaluations:
            return {
                "overall_accuracy": 0,
                "average_keyword_recognition": 0,
                "total_evaluations": 0
            }
        
        avg_accuracy = sum(eval["accuracy"] for eval in stt_evaluations) / len(stt_evaluations)
        avg_keyword_recognition = sum(eval["keyword_recognition_rate"] for eval in stt_evaluations) / len(stt_evaluations)
        
        return {
            "overall_accuracy": avg_accuracy,
            "average_keyword_recognition": avg_keyword_recognition,
            "total_evaluations": len(stt_evaluations),
            "detailed_evaluations": stt_evaluations
        }
    
    def _generate_test_employee_response(self, turn: Dict, customer_text: str, conversation_history: List[Dict]) -> str:
        """테스트 모드 직원 응답 생성 (RAG 활용)"""
        product_code = turn.get("product_code")
        expected_keywords = turn.get("keywords", [])
        
        if product_code:
            # RAG를 통한 상품 정보 검색
            try:
                product_info = self._search_product_info(product_code)
                if product_info:
                    return f"{product_info.get('summary', '')} {product_info.get('details', '')}"
            except Exception as e:
                print(f"RAG 검색 오류: {e}")
        
        return "네, 알겠습니다. 관련 정보를 안내해드리겠습니다."
    
    def _search_product_info(self, product_code: str) -> Optional[Dict]:
        """상품 정보 검색 (RAG)"""
        product_mapping = {
            "DEP-MMD": {
                "summary": "MMDA는 입출금이 자유로우면서도 높은 금리를 받을 수 있는 예금상품입니다.",
                "details": "최소 100만원부터 가입 가능하며, 잔액에 따라 차등 금리가 적용됩니다."
            },
            "LON-MTG": {
                "summary": "주택담보대출은 주택을 담보로 제공하여 대출받는 상품입니다.",
                "details": "LTV(담보인정비율)는 일반지역 70%, DTI(총부채상환비율)는 60%까지 가능합니다."
            },
            "LON-DCL": {
                "summary": "예금담보대출은 예금을 담보로 제공하여 초저금리로 대출받는 상품입니다.",
                "details": "예금잔액의 95%까지 대출 가능하며, 수취은행과 무관하게 본행 예금만 가능합니다."
            }
        }
        return product_mapping.get(product_code)
    
    def _load_product_data(self, product_code: str) -> List[Dict]:
        """상품 코드에 해당하는 실제 상품 데이터 로드"""
        try:
            product_file = self.data_path / "rag_sources" / "products" / "hakyung" / f"{product_code}.jsonl"
            if not product_file.exists():
                print(f"⚠️ 상품 데이터 파일을 찾을 수 없습니다: {product_file}")
                return []
            
            product_data = []
            with open(product_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            product_data.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            
            print(f"✅ 상품 데이터 로드 완료: {product_code} ({len(product_data)}개 청크)")
            return product_data
        except Exception as e:
            print(f"❌ 상품 데이터 로드 실패: {e}")
            return []
    
    def _extract_product_evidence(self, product_code: str, text: str, product_data: List[Dict]) -> Dict:
        """
        상품 데이터에서 평가 근거 추출
        
        **개선: 벡터 검색 및 유사도 판별 추가**
        - ProductKnowledgeService의 search_by_keyword() 사용
        - 의미적 유사도 계산 (임베딩 기반)
        - 유사도 점수 기반 정렬
        
        **프로세스:**
        1. ProductKnowledgeService로 벡터 검색 수행
        2. 유사도 점수 계산
        3. 유사도 높은 순으로 정렬
        4. 관련 청크 반환
        """
        evidence = {
            "matched_chunks": [],
            "key_information": [],
            "missing_information": [],
            "similarity_scores": []  # 유사도 점수 추가
        }
        
        if not product_data:
            return evidence
        
        # 🎯 ProductKnowledgeService 사용 (벡터 검색 우선, 실패 시 키워드 fallback)
        if self.product_knowledge_service:
            try:
                # 1단계: 벡터 검색 우선 수행 (pgvector 사용)
                relevant_chunks = self.product_knowledge_service.search_by_vector_similarity(
                    query=text,
                    category=None,
                    product_codes=[product_code],
                    top_k=5,
                    similarity_threshold=0.5
                )
                
                # 벡터 검색 결과 확인
                if not relevant_chunks:
                    # 벡터 검색 결과가 아예 없음
                    print(f"⚠️ 벡터 검색 결과 없음 (빈 리스트 반환), 키워드 매칭으로 fallback")
                    fallback_evidence = self._extract_product_evidence_keyword_fallback(product_code, text, product_data)
                    fallback_evidence["error"] = "vector_no_results"
                    fallback_evidence["error_detail"] = "벡터 검색 결과가 없습니다. 키워드 매칭 fallback 사용됨."
                    print(f"  📝 fallback 결과: {len(fallback_evidence.get('matched_chunks', []))}개 청크 발견")
                    return fallback_evidence
                
                # 2단계: 근거 청크 구성
                similarity_threshold = 0.5  # 유사도 임계값
                
                for chunk in relevant_chunks:
                    chunk_text = chunk.get("text") or chunk.get("content", "")
                    if not chunk_text:
                        continue
                    
                    # 벡터 검색 결과에 similarity가 있으면 사용
                    similarity = chunk.get("similarity")
                    if similarity is None:
                        # similarity가 없으면 계산
                        similarity = self.product_knowledge_service._semantic_similarity(
                            text,  # 직원 발화
                            chunk_text  # 상품 데이터 청크
                        )
                    
                    # 유사도 임계값 이상만 근거로 사용
                    if similarity >= similarity_threshold:
                        evidence["matched_chunks"].append({
                            "subsection_title": chunk.get("subsection_title", ""),
                            "text": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                            "breadcrumb": chunk.get("breadcrumb", ""),
                            "similarity": round(similarity, 3)  # 유사도 점수 추가
                        })
                        evidence["similarity_scores"].append(similarity)
                
                # 벡터 검색 결과가 있는 경우
                if evidence["similarity_scores"]:
                    avg_similarity = sum(evidence["similarity_scores"]) / len(evidence["similarity_scores"])
                    print(f"✅ 벡터 검색 완료: {len(evidence['matched_chunks'])}개 청크 발견 (평균 유사도: {avg_similarity:.3f})")
                    
                    # 키워드 정보도 함께 제공 (참고용)
                    key_info_keywords = self._get_key_info_keywords()
                    relevant_keywords = key_info_keywords.get(product_code, [])
                    found_keywords_in_text = [kw for kw in relevant_keywords if kw in text]
                    missing_keywords = [kw for kw in relevant_keywords if kw not in text]
                    
                    evidence["key_information"] = found_keywords_in_text
                    evidence["missing_information"] = missing_keywords
                    
                    return evidence
                else:
                    # 벡터 검색 결과가 없으면 키워드 매칭으로 fallback
                    print(f"⚠️ 벡터 검색 결과 없음: 유사도 임계값({similarity_threshold}) 미달, 키워드 매칭으로 fallback")
                    fallback_evidence = self._extract_product_evidence_keyword_fallback(product_code, text, product_data)
                    # 벡터 검색 실패 정보 추가
                    fallback_evidence["error"] = "vector_no_results"
                    fallback_evidence["error_detail"] = f"벡터 검색 결과가 없거나 유사도 임계값({similarity_threshold}) 미달. 키워드 매칭 fallback 사용됨."
                    print(f"  📝 fallback 결과: {len(fallback_evidence.get('matched_chunks', []))}개 청크 발견")
                    return fallback_evidence
                
            except Exception as e:
                print(f"⚠️ 벡터 검색 실패, 키워드 매칭으로 fallback: {e}")
                import traceback
                traceback.print_exc()
                # Fallback: 기존 키워드 매칭 로직
                fallback_evidence = self._extract_product_evidence_keyword_fallback(product_code, text, product_data)
                # 벡터 검색 실패 정보 추가
                fallback_evidence["error"] = "vector_search_error"
                fallback_evidence["error_detail"] = f"벡터 검색 중 오류 발생: {str(e)}. 키워드 매칭 fallback 사용됨."
                print(f"  📝 fallback 결과: {len(fallback_evidence.get('matched_chunks', []))}개 청크 발견")
                return fallback_evidence
        
        # ProductKnowledgeService 없으면 기존 로직 사용
        return self._extract_product_evidence_keyword_fallback(product_code, text, product_data)
    
    def _extract_product_evidence_keyword_fallback(self, product_code: str, text: str, product_data: List[Dict]) -> Dict:
        """키워드 매칭 기반 근거 추출 (fallback)"""
        evidence = {
            "matched_chunks": [],
            "key_information": [],
            "missing_information": []
        }
        
        if not product_data:
            return evidence
        
        # 상품별 핵심 정보 키워드
        key_info_keywords = self._get_key_info_keywords()
        relevant_keywords = key_info_keywords.get(product_code, [])
        
        # 텍스트에서 찾은 키워드
        found_keywords_in_text = [kw for kw in relevant_keywords if kw in text]
        missing_keywords = [kw for kw in relevant_keywords if kw not in text]
        
        # 상품 데이터에서 관련 청크 찾기 (단순 키워드 매칭)
        for chunk in product_data:
            chunk_text = chunk.get("text", "")
            for keyword in found_keywords_in_text:
                if keyword in chunk_text:
                    evidence["matched_chunks"].append({
                        "subsection_title": chunk.get("subsection_title", ""),
                        "text": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                        "breadcrumb": chunk.get("breadcrumb", "")
                    })
                    break
        
        evidence["key_information"] = found_keywords_in_text
        evidence["missing_information"] = missing_keywords
        
        return evidence
    
    def _evaluate_rag_integration(self, text: str, expected_product_code: Optional[str], expected_keywords: List[str], role: str = "employee") -> Dict:
        """
        RAG 연동 평가 - 피드백 생성과 동일한 batch_verify_conversation() 로직 사용
        
        🎯 유지보수 관점에서 피드백 생성과 동일한 로직을 사용하여:
        - 테스트 결과가 실제 피드백과 일치
        - 하나의 로직만 수정하면 둘 다 적용
        - claim 단위 검증으로 벡터 검색 실패 시에도 정확성 평가 가능
        
        Args:
            text: 평가할 발화 텍스트 (고객 또는 직원)
            expected_product_code: 참고용 예상 제품 코드 (테스트 시나리오)
            expected_keywords: STT 인식률 확인용 키워드 (테스트 시나리오)
            role: 발화 역할 ("employee" 또는 "customer"), 기본값은 "employee"
        """
        score = 0
        max_score = 100
        
        # 변수 초기화
        keyword_score = 0
        product_score = 0
        product_evidence = None
        extracted_product_codes = set()
        extracted_categories = set()
        extracted_claims = []
        claim_verifications = []
        
        # 🎯 피드백 생성과 동일한 로직: batch_verify_conversation() 사용
        if self.product_knowledge_service:
            # 대화 히스토리 구성
            conversation = [{"role": role, "text": text}]
            
            # 1. 키워드 매칭 점수 (50점) - STT 인식률 확인용
            if expected_keywords:
                found_keywords = [kw for kw in expected_keywords if kw in text]
                keyword_score = (len(found_keywords) / len(expected_keywords)) * 50 if expected_keywords else 0
                missing_keywords = [kw for kw in expected_keywords if kw not in text]
            else:
                found_keywords = []
                missing_keywords = []
            
            # 2. RAG 상품 정보 정확도 검증 (50점) - batch_verify_conversation() 사용
            try:
                # 피드백 생성과 동일한 방식으로 claim 추출 및 검증
                verification_result = self.product_knowledge_service.batch_verify_conversation(
                    conversation,
                    use_llm=True  # LLM 검증 포함
                )
                
                # 검증 결과에서 정보 추출
                total_claims = verification_result.get('total_claims', 0)
                accurate_claims = verification_result.get('accurate_claims', 0)
                accuracy_rate = verification_result.get('accuracy_rate', 0.0)
                verifications = verification_result.get('verifications', [])
                
                # 추출된 제품 코드 및 카테고리 수집
                for v in verifications:
                    if hasattr(v, 'product_code') and v.product_code:
                        extracted_product_codes.add(v.product_code)
                    if hasattr(v, 'category') and v.category:
                        extracted_categories.add(v.category)
                    if hasattr(v, 'claim') and v.claim:
                        extracted_claims.append(v.claim)
                
                # RAG 상품 정보 점수: 검증 정확도 기반 (50점 만점)
                product_score = accuracy_rate * 50
                
                # claim 검증 결과 수집 (프론트엔드 표시용)
                claim_verifications = [
                    {
                        "claim": v.claim,
                        "is_accurate": v.is_accurate,
                        "ground_truth": getattr(v, 'ground_truth', None),
                        "similarity": getattr(v, 'similarity', None),
                        "verification_method": getattr(v, 'verification_method', None),
                        "llm_reasoning": getattr(v, 'llm_reasoning', None)
                    }
                    for v in verifications
                ]
                
                # 벡터 검색 결과 수집 (product_evidence 구성)
                # 각 claim의 검증 과정에서 사용된 벡터 검색 결과 수집
                matched_chunks = []
                similarity_scores = []
                all_vector_chunks = set()  # 중복 제거용
                
                for v in verifications:
                    # verify_fact_accuracy에서 사용된 벡터 검색 결과를 재구성
                    # (실제로는 verification 객체에 포함되어 있지 않으므로, 
                    #  각 claim에 대해 다시 벡터 검색 수행하여 결과 수집)
                    if hasattr(v, 'claim') and v.claim:
                        vector_results = self.product_knowledge_service.search_by_vector_similarity(
                            query=v.claim,
                            category=None,
                            product_codes=[getattr(v, 'product_code')] if hasattr(v, 'product_code') and getattr(v, 'product_code') else None,
                            top_k=3,
                            similarity_threshold=0.5
                        )
                        
                        for chunk in vector_results[:3]:  # Top 3만 수집
                            chunk_text = chunk.get("text") or chunk.get("content", "")
                            chunk_id = f"{chunk.get('subsection_title', '')}_{chunk_text[:50]}"
                            
                            if chunk_id not in all_vector_chunks and chunk_text:
                                all_vector_chunks.add(chunk_id)
                                similarity = chunk.get("similarity", 0.0)
                                
                                matched_chunks.append({
                                    "subsection_title": chunk.get("subsection_title", ""),
                                    "text": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                                    "breadcrumb": chunk.get("breadcrumb", ""),
                                    "similarity": round(similarity, 3)
                                })
                                similarity_scores.append(similarity)
                
                # product_evidence 구성
                product_evidence = {
                    "matched_chunks": matched_chunks[:5],  # 최대 5개만 표시
                    "similarity_scores": similarity_scores[:5],
                    "key_information": extracted_claims,  # 추출된 claim 목록
                    "missing_information": []  # claim 검증 결과에서 정확하지 않은 claim은 missing_information에 포함할 수 있음
                }
                
                # 벡터 검색 실패 여부 확인
                if not matched_chunks:
                    product_evidence["error"] = "vector_no_results"
                    product_evidence["error_detail"] = "벡터 검색 결과가 없거나 유사도 임계값(0.5) 미달. claim 단위 검증은 LLM으로 수행됨."
                
                print(f"✅ RAG 평가 완료: {total_claims}개 claim, {accurate_claims}개 정확 ({accuracy_rate:.1%})")
                
            except Exception as e:
                print(f"⚠️ RAG 평가 실패: {e}")
                import traceback
                traceback.print_exc()
                product_score = 0
                product_evidence = {
                    "error": "evaluation_error",
                    "error_detail": f"RAG 평가 중 오류 발생: {str(e)}"
                }
            
            # 3. 총점 계산
            total_score = keyword_score + product_score
            
            # 4. 결과 반환 (피드백과 동일한 형식 유지)
            return {
                "score": total_score,
                "max_score": max_score,
                "keyword_score": keyword_score,
                "rag_product_info_score": product_score,
                "expected_product_code": expected_product_code,  # 참고용
                "extracted_product_code": list(extracted_product_codes)[0] if extracted_product_codes else None,  # 자동 추출된 제품 코드
                "extracted_product_codes": list(extracted_product_codes),  # 모든 추출된 제품 코드
                "extracted_categories": list(extracted_categories),  # 자동 추출된 카테고리
                "found_keywords": found_keywords,  # STT 인식된 키워드 (expected_keywords 기반)
                "expected_keywords": expected_keywords,  # 참고용 (테스트 시나리오)
                "missing_keywords": missing_keywords,  # STT 미인식 키워드
                "rag_info_keywords_found": extracted_claims,  # 추출된 claim 목록
                "claim_verifications": claim_verifications,  # 🆕 claim 검증 결과 (피드백과 동일)
                "product_evidence": product_evidence,  # 벡터 검색 결과 및 근거
                "extraction_method": "batch_verify_conversation"  # 피드백과 동일한 방법
            }
        else:
            # ProductKnowledgeService 없으면 기본값 반환
            return {
                "score": 0,
                "max_score": max_score,
                "keyword_score": 0,
                "rag_product_info_score": 0,
                "expected_product_code": expected_product_code,
                "extracted_product_code": None,
                "extracted_product_codes": [],
                "extracted_categories": [],
                "found_keywords": [],
                "expected_keywords": expected_keywords,
                "missing_keywords": expected_keywords if expected_keywords else [],
                "rag_info_keywords_found": [],
                "claim_verifications": [],
                "product_evidence": None,
                "extraction_method": "none"
            }
    
    def _filter_info_keywords_by_categories(self, info_keywords: List[str], categories: set, text: str = "") -> List[str]:
        """
        카테고리 기반으로 info_keywords 필터링
        
        **매칭 원리:**
        1. category_config.json의 subsection_keywords를 사용하여 카테고리와 관련된 키워드 확인
        2. info_keywords에서 해당 키워드가 포함된 항목만 필터링
        3. 예: "수수료" 카테고리 → subsection_keywords["수수료"] = ["수수료", "연회비", "중도상환", ...]
           → info_keywords에서 "연회비", "10,000원" 등이 포함된 키워드만 추출
        
        **명확한 매칭 규칙:**
        - info_keywords의 용어가 subsection_keywords의 키워드와 정확히 일치하거나
        - info_keywords의 용어에 subsection_keywords의 키워드가 포함되어 있으면 해당 카테고리로 분류
        - 예: "연회비" 키워드가 있으면 → "수수료" 카테고리
        - 예: "10,000원"은 숫자 제거 후 "원"만 남으므로 단독으로는 매칭 어려움
          → 하지만 직원 발화에 "연회비"가 함께 있으면 수수료 카테고리로 추출됨
        
        Args:
            info_keywords: 전체 info_keywords 리스트
            categories: 추출된 카테고리 집합 (예: {"수수료", "한도"})
            text: 직원 발화 텍스트 (카테고리 매칭 확인용, 선택적)
        
        Returns:
            필터링된 info_keywords 리스트 (빈 리스트면 카테고리와 관련된 키워드 없음)
        """
        if not categories or not info_keywords:
            return []
        
        # category_config.json 로드
        category_config_path = self.data_path / "category_config.json"
        if not category_config_path.exists():
            # category_config가 없으면 전체 키워드 반환 (하위 호환)
            return info_keywords
        
        try:
            with open(category_config_path, 'r', encoding='utf-8') as f:
                category_config = json.load(f)
            
            subsection_keywords = category_config.get("subsection_keywords", {})
        except Exception as e:
            print(f"⚠️ category_config 로드 실패: {e}")
            return info_keywords
        
        # 각 카테고리와 관련된 키워드 수집
        # 예: categories = {"수수료"} → subsection_keywords["수수료"] = ["수수료", "연회비", "중도상환", "중도해지"]
        category_related_keywords = set()
        for category in categories:
            if category in subsection_keywords:
                category_keywords = subsection_keywords[category]
                category_related_keywords.update(category_keywords)
        
        if not category_related_keywords:
            # 카테고리 키워드가 없으면 전체 반환
            return info_keywords
        
        # info_keywords에서 카테고리 관련 키워드가 포함된 것만 필터링
        filtered_keywords = []
        text_lower = text.lower() if text else ""
        
        for kw in info_keywords:
            kw_lower = kw.lower()
            
            # 방법 1: info_keywords의 용어가 subsection_keywords와 직접 매칭
            # 예: info_keywords에 "연회비"가 있으면 → "수수료" 카테고리 키워드와 매칭
            for cat_kw in category_related_keywords:
                cat_kw_lower = cat_kw.lower()
                # 정확 일치
                if kw_lower == cat_kw_lower:
                    filtered_keywords.append(kw)
                    break
                # 부분 포함 (카테고리 키워드가 info_keywords에 포함되거나 그 반대)
                if cat_kw_lower in kw_lower or kw_lower in cat_kw_lower:
                    filtered_keywords.append(kw)
                    break
            
            # 방법 2: 숫자 포함 키워드의 경우 (예: "10,000원", "1.0%")
            # 숫자 제거 후 남은 부분이 카테고리 키워드와 매칭되는지 확인
            if kw not in filtered_keywords:
                kw_without_numbers = re.sub(r'[\d,\.]+', '', kw_lower).strip()
                # 남은 부분이 의미 있는 단어인지 확인 (최소 2글자 이상)
                if len(kw_without_numbers) >= 2:
                    for cat_kw in category_related_keywords:
                        cat_kw_lower = cat_kw.lower()
                        if cat_kw_lower in kw_without_numbers or kw_without_numbers in cat_kw_lower:
                            filtered_keywords.append(kw)
                            break
            
            # 방법 3: 직원 발화에 카테고리 키워드가 있고, info_keywords의 수치/용어가 함께 언급된 경우
            # 예: 발화에 "연회비"가 있고 info_keywords에 "10,000원"이 있으면 → 수수료 카테고리
            if text and kw not in filtered_keywords:
                # info_keywords가 수치만 있는 경우 (예: "10,000원", "1.0%")
                if re.match(r'^[\d,\.%원]+$', kw):
                    # 발화에 해당 카테고리 키워드가 언급되어 있으면 포함
                    for cat_kw in category_related_keywords:
                        if cat_kw.lower() in text_lower:
                            filtered_keywords.append(kw)
                            break
        
        # 필터링된 키워드가 없으면 빈 리스트 반환 (전체 키워드 사용하지 않음)
        return filtered_keywords
    
    def _get_key_info_keywords(self) -> Dict[str, List[str]]:
        """상품 데이터 근거 추출용 키워드 가져오기 (캐시 우선, 없으면 하드코딩)"""
        if self.keyword_extractor:
            cached_keywords = {}
            # 캐시에서 모든 제품 키워드 가져오기
            cache = self.keyword_extractor.cache
            for product_code, keywords_data in cache.items():
                if keywords_data and keywords_data.get("info_keywords"):
                    cached_keywords[product_code] = keywords_data["info_keywords"]
            
            if cached_keywords:
                return cached_keywords
        
        # 하드코딩된 키워드 (fallback)
        return {
            "DEP-MMD": ["MMDA", "입출금", "금리", "예금", "100만원", "차등", "최소", "가입금액"],
            "LON-MTG": ["주택담보", "LTV", "DTI", "DSR", "담보인정비율", "70%", "60%", "규제"],
            "LON-DCL": ["예금담보", "수취은행", "담보", "95%", "예금잔액", "초저금리"]
        }
    
    def _get_product_keywords_map(self) -> Dict[str, List[str]]:
        """고객 발화 평가용 키워드 가져오기 (캐시 우선, 없으면 하드코딩)"""
        if self.keyword_extractor:
            cached_keywords = {}
            # 캐시에서 모든 제품 키워드 가져오기
            cache = self.keyword_extractor.cache
            for product_code, keywords_data in cache.items():
                if keywords_data and keywords_data.get("product_keywords"):
                    # product_keywords를 사용하되, 추가 키워드도 포함
                    cached_keywords[product_code] = keywords_data["product_keywords"].copy()
                    # info_keywords에서 일부 추가 (제품 특성 키워드)
                    if keywords_data.get("info_keywords"):
                        # 제품 특성 키워드만 추가 (수치 제외)
                        product_specific = [kw for kw in keywords_data["info_keywords"] 
                                         if not kw.replace("%", "").replace(",", "").replace("원", "").isdigit()
                                         and kw not in cached_keywords[product_code]]
                        cached_keywords[product_code].extend(product_specific)
            
            if cached_keywords:
                return cached_keywords
        
        # 하드코딩된 키워드 (fallback)
        return {
            "DEP-MMD": ["MMDA", "엠엠디에이", "입출금", "예금", "적금"],
            "LON-MTG": ["주택담보", "주택담보대출", "LTV", "DTI", "DSR", "담보"],
            "LON-DCL": ["예금담보", "예금담보대출", "수취은행", "담보"]
        }
    
    def _get_product_info_keywords(self) -> Dict[str, List[str]]:
        """RAG 평가용 제품 정보 키워드 가져오기 (캐시 우선, 없으면 하드코딩)"""
        if self.keyword_extractor:
            cached_keywords = {}
            # 캐시에서 모든 제품 키워드 가져오기
            cache = self.keyword_extractor.cache
            for product_code, keywords_data in cache.items():
                if keywords_data and keywords_data.get("info_keywords"):
                    cached_keywords[product_code] = keywords_data["info_keywords"]
            
            if cached_keywords:
                return cached_keywords
        
        # 하드코딩된 키워드 (fallback)
        return {
            "DEP-MMD": ["MMDA", "입출금", "금리", "예금", "100만원", "차등"],
            "LON-MTG": ["주택담보", "LTV", "DTI", "DSR", "담보인정비율", "70%", "60%"],
            "LON-DCL": ["예금담보", "수취은행", "담보", "95%", "예금잔액"]
        }
    
    def _summarize_rag_evaluations(self, rag_evaluations: List[Dict]) -> Dict:
        """RAG 평가 결과 종합"""
        if not rag_evaluations:
            return {
                "total_evaluations": 0,
                "average_score": 0,
                "employee_evaluations": [],
                "customer_evaluations": []
            }
        
        employee_evals = [e for e in rag_evaluations if e.get("role") == "employee"]
        customer_evals = [e for e in rag_evaluations if e.get("role") == "customer"]
        
        all_scores = [e["evaluation"]["score"] for e in rag_evaluations]
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        
        return {
            "total_evaluations": len(rag_evaluations),
            "average_score": avg_score,
            "employee_count": len(employee_evals),
            "customer_count": len(customer_evals),
            "employee_average": sum(e["evaluation"]["score"] for e in employee_evals) / len(employee_evals) if employee_evals else 0,
            "customer_average": sum(e["evaluation"]["score"] for e in customer_evals) / len(customer_evals) if customer_evals else 0,
            "employee_evaluations": employee_evals,
            "customer_evaluations": customer_evals
        }
