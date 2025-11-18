"""
RAG 기반 시뮬레이션 서비스
제공된 데이터를 활용한 STT/LLM/TTS 기반 음성 시뮬레이션
"""
import json
import os
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
    "더 궁금하신",
    "더 필요하신"
    "더 궁금하신 점",
    "더 필요하신 점",
    "더 궁금하신 점 있으세요?",
    "더 필요하신 점 있으세요?",
    "더 궁금하신 점 있으세요?",
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
        
        # 제품 지식 서비스 초기화
        try:
            self.product_knowledge_service = ProductKnowledgeService(use_llm=True)
            print("✅ 제품 지식 검증 서비스 초기화 완료")
        except Exception as e:
            print(f"⚠️ 제품 지식 서비스 초기화 실패: {e}")
            self.product_knowledge_service = None
        
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
            
            # 상황 데이터 로드 (situations_expanded_40each_minified2.json)
            situations_file = self.data_path / "situations_expanded_40each_minified2.json"
            print(f"📄 상황 파일 경로: {situations_file}")
            print(f"📄 상황 파일 존재 여부: {situations_file.exists()}")
            
            if situations_file.exists():
                with open(situations_file, 'r', encoding='utf-8') as f:
                    situations_data = json.load(f)
                    if 'situations' in situations_data:
                        self.situations_cache = situations_data['situations']
                    else:
                        self.situations_cache = situations_data if isinstance(situations_data, list) else []
                print(f"✅ 상황 데이터 로드 완료: {len(self.situations_cache) if self.situations_cache else 0}개")
            else:
                print("❌ 상황 파일을 찾을 수 없습니다")
            
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
            
        except Exception as e:
            print(f"❌ 데이터 로드 실패: {e}")
            import traceback
            traceback.print_exc()
    
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
            
            # 카테고리별로 필터링 (id, category, title 필드 모두 확인)
            filtered_situations = []
            for s in situations:
                situation_id = s.get("id", "")
                situation_category = s.get("category", "")
                situation_title = s.get("title", "")
                
                # 카테고리 매칭 확인
                matched = False
                for mapped_cat in mapped_categories:
                    if (situation_id == mapped_cat or 
                        situation_category == mapped_cat or 
                        mapped_cat in situation_title or
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
    
    def start_test_simulation(self, user_id: int) -> Dict:
        """테스트 모드 시뮬레이션 시작 - 고정된 시나리오로 STT 성능 및 RAG 연동 테스트"""
        # 데이터가 없으면 로드
        if not self.personas_cache or not self.situations_cache:
            self.load_simulation_data()
        
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
        
        test_situation = {
            "id": "test_situation_001",
            "title": "STT 성능 및 RAG 연동 테스트",
            "category": "test",
            "goals": [
                "금융 용어 STT 인식 정확도 평가",
                "RAG 상품 데이터 연동 확인",
                "지식 평가 로직 검증"
            ],
            "scenarios": []
        }
        
        # 테스트 시나리오 데이터 (고정된 발화)
        # 첫 번째 턴은 직원 인사로 시작
        test_scenario = {
            "turns": [
                {
                    "turn": 0,
                    "role": "employee",
                    "expected_text": "안녕하세요, 무엇을 도와드릴까요?",
                    "expected_response_type": "greeting",
                    "keywords": ["안녕하세요", "도와드릴까요"],
                    "product_code": None
                },
                {
                    "turn": 1,
                    "role": "customer",
                    "expected_text": "안녕하세요, MMDA 상품에 대해 문의하고 싶어요.",
                    "keywords": ["MMDA", "상품", "문의"],
                    "product_code": "DEP-MMD"
                },
                {
                    "turn": 2,
                    "role": "employee",
                    "expected_text": "MMDA는 입출금이 자유로우면서도 높은 금리를 받을 수 있는 예금상품입니다. 최소 100만원부터 가입 가능하며, 잔액에 따라 차등 금리가 적용됩니다.",
                    "expected_response_type": "product_info",
                    "product_code": "DEP-MMD",
                    "keywords": ["MMDA", "입출금", "금리", "예금", "100만원", "차등"]
                },
                {
                    "turn": 3,
                    "role": "customer",
                    "expected_text": "주택담보대출을 받으려고 하는데 LTV와 DTI 규제가 어떻게 되나요?",
                    "keywords": ["주택담보대출", "LTV", "DTI", "규제"],
                    "product_code": "LON-MTG"
                },
                {
                    "turn": 4,
                    "role": "employee",
                    "expected_text": "주택담보대출은 주택을 담보로 제공하여 대출받는 상품입니다. LTV 즉 담보인정비율은 일반지역 70%, DTI 즉 총부채상환비율은 60%까지 가능합니다.",
                    "expected_response_type": "product_info",
                    "product_code": "LON-MTG",
                    "keywords": ["주택담보", "LTV", "DTI", "DSR", "담보인정비율", "70%", "60%"]
                },
                {
                    "turn": 5,
                    "role": "customer",
                    "expected_text": "예금담보대출도 가능한가요? 수취은행이 다른 경우에도 되나요?",
                    "keywords": ["예금담보대출", "수취은행"],
                    "product_code": "LON-DCL"
                },
                {
                    "turn": 6,
                    "role": "employee",
                    "expected_text": "예금담보대출은 예금을 담보로 제공하여 초저금리로 대출받는 상품입니다. 예금잔액의 95%까지 대출 가능하며, 수취은행과 무관하게 본행 예금만 가능합니다.",
                    "expected_response_type": "product_info",
                    "product_code": "LON-DCL",
                    "keywords": ["예금담보", "수취은행", "담보", "95%", "예금잔액"]
                },
                {
                    "turn": 7,
                    "role": "customer",
                    "expected_text": "중개인을 통해서도 대출 신청이 가능한가요?",
                    "keywords": ["중개인"],
                    "product_code": None
                },
                {
                    "turn": 8,
                    "role": "employee",
                    "expected_text": "중개인을 통한 대출 신청도 가능합니다. 다만 직접 방문하시거나 온라인으로 신청하시는 것이 더 빠르고 정확합니다.",
                    "expected_response_type": "general_info",
                    "keywords": ["중개인", "대출", "신청"]
                }
            ]
        }
        
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
            "is_test_mode": True
        }
    
    def start_voice_simulation(self, user_id: int, persona_id: str, situation_id: str, gender: str = 'male') -> Dict:
        """음성 시뮬레이션 시작"""
        # 데이터가 없으면 로드
        if not self.personas_cache or not self.situations_cache:
            self.load_simulation_data()
        
        # 페르소나와 상황 조회
        persona = None
        situation = None
        
        if self.personas_cache:
            # id 필드로 조회 (personas_expanded_minified2.json은 id 필드만 사용)
            persona = next((p for p in self.personas_cache if p.get("id") == persona_id), None)
            print(f"페르소나 조회: {persona_id} -> {persona is not None}")
            if persona:
                print(f"✅ 페르소나 찾음: {persona.get('id')}, gender={persona.get('gender')}, age_group={persona.get('age_group')}")
            
        if self.situations_cache:
            situation = next((s for s in self.situations_cache if s.get("id") == situation_id), None)
            print(f"상황 조회: {situation_id} -> {situation is not None}")
        
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
            raise ValueError(f"페르소나를 찾을 수 없습니다: {persona_id}")
        
        if not situation:
            raise ValueError(f"상황을 찾을 수 없습니다: {situation_id}")
        
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
            
            # 🧪 테스트 모드 체크 (우선순위 최상위)
            is_test_mode = session_data.get("is_test_mode", False)
            has_test_scenario = bool(session_data.get("test_scenario"))
            
            print(f"🧪 테스트 모드 체크: is_test_mode={is_test_mode}, has_test_scenario={has_test_scenario}")
            
            if is_test_mode or has_test_scenario:
                print("🧪 테스트 모드로 처리합니다. 고정 시나리오만 사용합니다.")
                return self._process_test_mode_interaction(session_data, audio_data, user_message)
            
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
            
            # STT에서 이미 정규화가 완료되었으므로 추가 처리 불필요
            normalized_text = transcribed_text
            corrections = []  # 이미 STT에서 처리됨
            needs_clarification = False  # 이미 STT에서 처리됨
            
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
            
            # 대화 히스토리 구성 (세션 데이터에서 추출 및 누적)
            conversation_history = session_data.get("conversation_history", [])
            
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

            # LLM 응답 파싱
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
                "offtopic_count": offtopic_count  # 이탈 카운터 포함
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

**중요**: 
- 직원이 실제로 구체적인 정보를 제공한 발화를 찾으세요
- 단순히 주제를 언급하는 것이 아니라, 목표를 실질적으로 달성한 발화여야 합니다
- 턴 {turn_num} 근처의 발화를 우선적으로 확인하세요

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
                    llm_reasonings = []  # LLM reasoning 수집 (피드백 생성에 활용)
                    
                    for v in knowledge_verification_result.get('verifications', []):
                        if not v.is_accurate:
                            errors_detail.append(f"'{v.claim}' (실제: {v.ground_truth[:50]}...)")
                        
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
                        
                        product_accuracy_info = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **제품 지식 자동 검증 결과** (객관적 데이터)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 총 제품 정보 언급: {total_claims}개
- 정확한 정보: {accurate_claims}개
- 부정확한 정보: {inaccurate_claims}개
- 정확도: {accuracy_rate:.1%}
- 검증 방법: {knowledge_verification_result.get('verification_methods', {})}

⚠️ **발견된 오류:**
{chr(10).join(errors_detail[:3]) if errors_detail else '없음'}
{reasoning_section}
💡 **지식 점수 평가 시 위 검증 결과를 반드시 반영하세요:**
- 정확도 {accuracy_rate:.1%} → 기본 점수 {int(accuracy_rate * 100)}점 (오류는 이미 정확도에 반영됨)
- ⚠️ 오류 개수는 점수 계산에 사용하지 말고, 피드백 작성 시에만 참고하세요
- ⚠️ 불확실한 표현("같아요", "모르겠" 등)은 전달력(자신감) 평가에서 다루므로 지식 점수에는 반영하지 않습니다
- 💡 위 LLM reasoning을 참고하여 피드백에서 구체적으로 어떤 정보가 정확했고/부정확했는지 설명하세요
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
- 목적: 은행 상품(여신/수신 등) 또는 업무 절차에 대한 설명이 정확한가
- 평가 기준:
  ✓ 상품 정보(금리, 한도, 조건 등) 제공의 정확성 (상품 데이터 있는 경우)
  ✓ 업무 절차(송금 절차, 수수료 안내 등) 설명의 정확성 (상품 데이터 없는 경우)
  ✓ 구체적인 수치나 조건을 명확히 제시했는가
  ✓ 일반적인 금융 지식 및 규정 이해도
  ✗ 잘못된 정보나 오류 발견 시 감점
  ⚠️ 불확실한 표현("~같아요", "~보이는데요")은 전달력(자신감) 평가에서 다루므로 지식 점수에는 반영하지 않음
- 피드백 작성 시: 
  ✓ 어떤 정보를 정확히/부정확하게 전달했는지 구체적으로 언급
  ✓ 부정확한 정보는 정확한 정보와 함께 제시 (예: "3.5%" → "실제로는 2.15%")
  ✓ 위 제품 지식 자동 검증 결과의 LLM reasoning을 활용하여 구체적으로 설명
- ⚠️ **위 제품 지식 자동 검증 결과가 있으면 점수에 반영하세요 (없으면 LLM이 일반 지식으로 평가)**

**2️⃣ 기술 (Skill, 0-100점)**
- 목적: 응대 절차가 체계적이며 목표를 달성했는가
- 평가 기준:
  ✓ 대화 흐름: 인사 → 요구파악 → 정보제공 → 마무리 순서
  ✓ 목표 달성도: {len(achieved_goal_indices)}/{len(goals) if goals else 0}개 달성 ({goal_achievement_rate*100:.0f}%)
  ✓ 고객 니즈 파악을 위한 적절한 질문 사용
  ✓ 피드백 루프: 요약 및 추가 확인 여부
  ✓ 고객의 추가 질문에 대비한 정보 제공
- 피드백 작성 시: 
  ✓ 어떤 절차를 잘 따랐는지 구체적으로 언급
  ✓ 달성한 목표와 미달성한 목표를 명시
  ✓ 목표 달성률이 낮은 경우, 어떤 목표를 놓쳤는지와 개선 방안 제시
  ✓ 예: "대화 흐름은 체계적이었지만, '송금 목적 확인' 목표를 달성하지 못했습니다. 고객에게 송금 목적을 먼저 물어보는 것이 좋습니다."

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
  ✗ 부정 표현 감점: "안 됩니다", "불가능합니다", "모르겠어요"
  ✗ 명령형/무뚝뚝한 표현 감점
  ✗ 고객 선택 제한하는 표현: "더 빠르고 정확합니다" → "더 편리할 수 있습니다"
- 피드백 작성 시: 
  ✓ 친절했던 표현을 구체적으로 인용하여 칭찬
  ✓ 개선이 필요한 표현은 Before → After 형식으로 제시
  ✓ 예: "'더 빠르고 정확합니다' → '더 편리할 수 있습니다'로 바꾸면 고객 선택권을 존중하는 표현이 됩니다"

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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 **피드백 작성 가이드**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

각 지표별 피드백은 반드시 다음을 포함하세요:
1. **구체적인 예시**: 대화에서 실제로 사용한 표현을 인용 (따옴표 사용)
2. **잘한 점**: 긍정적인 부분을 먼저 언급
3. **개선점**: 구체적으로 어떻게 개선할지 제안 (Before → After 형식)
4. **실용적 조언**: 다음 시뮬레이션에서 바로 적용 가능한 팁

**중복 제거 원칙:**
- 같은 오류를 여러 역량에서 반복하지 않기
- 지식 평가에서 상세히 다룬 오류는 다른 역량에서 간단히 참조만
- 예: 지식에서 "최소 100" 오류를 상세히 설명했다면, 전달력에서는 "지식 평가에서 언급한 '최소 100' 표현은..." 형식으로 참조

**피드백 예시:**
- ✅ 좋은 피드백: "금리 2.15%를 명확히 제시하여 좋았습니다. 다만 '거치기간'이라는 용어 대신 '이자만 내는 기간'으로 설명하면 고객이 더 쉽게 이해할 수 있습니다. '~입니다.', '~됩니다.' 같은 확정적 표현을 잘 사용했습니다."
- ❌ 나쁜 피드백: "설명이 부족합니다." (구체적이지 않음)
- ✅ 개선 예시 포함: "'최소 100' → '최소 100만원'으로 명확히 표현하세요"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 **출력 형식 (JSON)**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

다음 JSON 형식으로 응답하세요:
{{
    "knowledge": {{
        "score": <0-100 점수>,
        "feedback": "<3-4문장, 구체적 예시 포함, 잘한 점과 개선점 모두 언급. 부정확한 정보는 정확한 정보와 함께 제시 (예: '3.5%' → '실제로는 2.15%'). 제품 지식 자동 검증 결과의 LLM reasoning 활용>"
    }},
    "skill": {{
        "score": <0-100 점수>,
        "feedback": "<3-4문장, 대화 흐름과 목표 달성도 평가, 구체적 개선 제안. 달성한 목표와 미달성한 목표를 명시하고, 미달성 목표에 대한 개선 방안 제시>"
    }},
    "clarity": {{
        "score": <0-100 점수>,
        "feedback": "<3-4문장, 문장 구조와 용어 사용 평가, 쉬운 표현 제안. 모호한 표현은 Before → After 형식으로 제안 (예: '최소 100' → '최소 100만원')>"
    }},
    "kindness": {{
        "score": <0-100 점수>,
        "feedback": "<3-4문장, 친절한 표현 사례와 개선 필요 표현 지적. Before → After 형식으로 제안 (예: '더 빠르고 정확합니다' → '더 편리할 수 있습니다')>"
    }},
    "confidence": {{
        "score": <0-100 점수>,
        "feedback": "<3-4문장, 자신감 있는 어투와 불확실한 표현 비교. Before → After 형식으로 제안 (예: '~같아요' → '~입니다'). 지식 평가에서 언급한 부정확한 정보를 확신 있게 말한 경우도 언급>"
    }},
    "clarity_confidence": {{
        "score": <(clarity + confidence) / 2, 0-100 점수>,
        "feedback": "<5-6문장, 반드시 [명확성]과 [자신감]을 별도 문단으로 구분하여 작성. 각 문단에서 잘한 점과 개선점을 구체적으로 제시. 지식 평가에서 이미 상세히 다룬 오류는 간단히 참조만 하고 전달력 관점에서만 평가 (예: '지식 평가에서 언급한 최소 100 표현은...'). 구체적인 예시와 Before → After 형식의 개선 방안 포함. 중복 설명 지양>"
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

            # 종합 점수 계산 (4가지 역량의 평균)
            scores = [
                evaluation['knowledge']['score'],
                evaluation['skill']['score'],
                kindness_score,
                clarity_confidence_score
            ]
            overall_score = sum(scores) / len(scores)
            
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

3. **목표 키워드 확인**:
   - "설명" 목표: 구체적인 내용(수치, 절차, 조건 등)이 포함되어야 함
   - "안내" 목표: 실제 방법이나 단계가 제시되어야 함
   - "고지" 목표: 명시적인 경고나 정보 전달이 있어야 함
   - "파악" 목표: 고객의 의도를 이해하고 확인하는 대화가 있어야 함

4. **직원 발화만 평가**: 고객이 말한 내용은 달성 근거가 될 수 없음
   - 직원이 실제로 해당 정보를 제공했는지만 확인

5. **엄격한 평가**: 의심스러우면 미달성으로 판단
   - 목표가 요구하는 것의 70% 이상을 충족해야 달성으로 인정
   - 단순히 주제를 언급하는 것만으로는 부족

**판단 프로세스:**
각 목표에 대해:
1) 직원 발화에서 관련 키워드 찾기
2) 구체적인 정보가 포함되어 있는지 확인
3) 목표가 요구하는 수준을 충족하는지 판단
4) 충족하면 달성, 아니면 미달성

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

**중요**: 
- 직원이 실제로 구체적인 정보를 제공한 발화를 찾으세요
- 단순히 주제를 언급하는 것이 아니라, 목표를 실질적으로 달성한 발화여야 합니다
- 여러 턴에서 달성되었다면 가장 명확한 턴을 선택하세요

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
        rag_evaluations = session_data.get("rag_evaluations", [])  # 🧪 RAG 평가 결과 누적
        
        print(f"🧪 현재 턴 인덱스: {current_turn_index}, 전체 턴 수: {len(turns)}")
        
        if current_turn_index >= len(turns):
            # 모든 턴 완료 - RAG 평가 종합 결과 생성
            rag_summary = self._summarize_rag_evaluations(rag_evaluations)
            print(f"🧪 ===== 테스트 모드 완료 =====")
            print(f"🧪 STT 평가: {len(stt_evaluations)}개")
            print(f"🧪 RAG 평가: {len(rag_evaluations)}개")
            print(f"🧪 RAG 평균 점수: {rag_summary.get('average_score', 0):.1f}점")
            
            return {
                "transcribed_text": "",
                "customer_response": "",
                "customer_audio": None,
                "feedback": "테스트 시나리오가 완료되었습니다.",
                "conversation_phase": "completed",
                "session_score": 0,
                "conversation_history": conversation_history,
                "end_signal": True,
                "stt_evaluation": self._evaluate_stt_performance(stt_evaluations),
                "rag_evaluations": rag_evaluations,  # 🧪 모든 RAG 평가 결과
                "rag_summary": rag_summary,  # 🧪 RAG 평가 종합 결과
                "test_completed": True
            }
        
        current_turn = turns[current_turn_index]
        print(f"🧪 현재 턴: {current_turn.get('role')} - {current_turn.get('expected_text', '')[:50]}...")
        print(f"🧪 현재까지 RAG 평가 결과 수: {len(rag_evaluations)}개")
        if rag_evaluations:
            print(f"🧪   - 마지막 RAG 평가: {rag_evaluations[-1].get('role')} 턴 {rag_evaluations[-1].get('turn_index')}, 점수: {rag_evaluations[-1].get('evaluation', {}).get('score', 0):.1f}점")
        
        # STT 처리
        if not user_message:
            transcribed_text = self._speech_to_text(audio_data) if audio_data else ""
        else:
            transcribed_text = user_message
        
        print(f"🧪 STT 결과: {transcribed_text}")
        
        # STT 평가 (고객 발화인 경우)
        if current_turn["role"] == "customer":
            expected_text = current_turn.get("expected_text", "")
            expected_product_code = current_turn.get("product_code")
            expected_keywords = current_turn.get("keywords", [])
            
            # 1. STT 평가 (금융 용어 인식 정확도)
            stt_eval = self._evaluate_single_stt(transcribed_text, expected_text, expected_keywords)
            stt_evaluations.append(stt_eval)
            
            # 2. RAG 연동 평가 (고객 발화에서 상품 코드 추출 및 매칭)
            # 고객 발화를 분석해서 어떤 상품을 문의하는지 파악
            rag_eval_customer = self._evaluate_customer_rag_integration(
                transcribed_text,
                expected_product_code,
                expected_keywords
            )
            # 🧪 RAG 평가 결과 누적 저장
            rag_evaluations.append({
                "turn_index": current_turn_index,
                "role": "customer",
                "expected_product_code": expected_product_code,
                "evaluation": rag_eval_customer
            })
            print(f"🧪 고객 발화 RAG 평가: {rag_eval_customer['score']:.1f}점 (상품: {expected_product_code})")
            
            # 🧪 현재까지의 RAG 평가 종합 결과 생성 (매 턴마다)
            current_rag_summary = self._summarize_rag_evaluations(rag_evaluations)
            
            # 고객 발화를 히스토리에 추가
            conversation_history.append({
                "role": "customer",
                "text": transcribed_text,
                "timestamp": datetime.now().isoformat()
            })
            
            # 다음 턴으로 이동 (직원 응답은 사용자가 따라 말해야 함)
            next_turn_index = current_turn_index + 1
            if next_turn_index < len(turns):
                next_turn = turns[next_turn_index]
                if next_turn["role"] == "employee":
                    # 테스트 모드에서는 직원 응답을 자동 생성하지 않고, 사용자가 따라 말하도록 함
                    # 다음 턴의 expected_text를 반환하여 프론트엔드에 표시
                    next_expected_text = next_turn.get("expected_text", "")
                    print(f"🧪 고객 발화 완료. 다음 턴(직원): {next_expected_text[:50]}...")
                    print(f"🧪 customer_response는 빈 문자열로 반환 (자동 생성 안 함)")
                    
                    print(f"🧪 ✅ 고객 발화 처리 완료 - RAG 평가 결과 {len(rag_evaluations)}개 포함")
                    return {
                        "transcribed_text": transcribed_text,
                        "customer_response": "",  # 🧪 테스트 모드: 절대 고객 응답 자동 생성 안 함
                        "customer_audio": None,  # 🧪 테스트 모드: 절대 고객 음성 생성 안 함
                        "feedback": f"STT 정확도: {stt_eval['accuracy']:.1f}% | 고객 발화 RAG 매칭: {rag_eval_customer['score']:.1f}점",
                        "conversation_phase": "ongoing",
                        "session_score": 0,
                        "conversation_history": conversation_history,
                        "current_turn_index": next_turn_index,  # 다음 턴(직원 응답)으로 이동
                        "stt_evaluations": stt_evaluations,
                        "rag_evaluations": rag_evaluations,  # 🧪 RAG 평가 결과 누적
                        "rag_summary": current_rag_summary,  # 🧪 현재까지의 RAG 평가 종합 결과
                        "stt_evaluation": stt_eval,
                        "rag_evaluation_customer": rag_eval_customer,
                        "next_turn_expected_text": next_expected_text,  # 다음 턴의 기대 텍스트
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
            
            # 2. RAG 연동 평가 (직원 응답이 RAG 정보를 정확히 포함했는지)
            rag_eval = self._evaluate_rag_integration(
                transcribed_text, 
                expected_product_code,
                expected_keywords
            )
            # 🧪 RAG 평가 결과 누적 저장
            rag_evaluations.append({
                "turn_index": current_turn_index,
                "role": "employee",
                "expected_product_code": expected_product_code,
                "evaluation": rag_eval
            })
            print(f"🧪 직원 발화 RAG 평가: {rag_eval['score']:.1f}점 (상품: {expected_product_code})")
            print(f"🧪   - 키워드 점수: {rag_eval['keyword_score']:.1f}점")
            print(f"🧪   - RAG 상품 정보 점수: {rag_eval['rag_product_info_score']:.1f}점")
            print(f"🧪   - 찾은 키워드: {rag_eval['found_keywords']}")
            print(f"🧪   - 누락된 키워드: {rag_eval['missing_keywords']}")
            if rag_eval.get('rag_info_keywords_found'):
                print(f"🧪   - RAG 정보 키워드: {rag_eval['rag_info_keywords_found']}")
            
            conversation_history.append({
                "role": "employee",
                "text": transcribed_text,
                "timestamp": datetime.now().isoformat()
            })
            
            # 다음 턴으로 이동 (고객 발화가 있으면 표시)
            next_turn_index = current_turn_index + 1
            next_turn_expected_text = ""
            if next_turn_index < len(turns):
                next_turn = turns[next_turn_index]
                if next_turn.get("role") == "customer":
                    next_turn_expected_text = next_turn.get("expected_text", "")
            
            # 🧪 현재까지의 RAG 평가 종합 결과 생성 (매 턴마다)
            current_rag_summary = self._summarize_rag_evaluations(rag_evaluations)
            
            print(f"🧪 직원 발화 완료. 다음 턴(고객): {next_turn_expected_text[:50] if next_turn_expected_text else '없음'}...")
            print(f"🧪 customer_response는 빈 문자열로 반환 (자동 생성 안 함)")
            
            print(f"🧪 ✅ 직원 발화 처리 완료 - RAG 평가 결과 {len(rag_evaluations)}개 포함")
            return {
                "transcribed_text": transcribed_text,
                "customer_response": "",  # 🧪 테스트 모드: 절대 고객 응답 자동 생성 안 함
                "customer_audio": None,  # 🧪 테스트 모드: 절대 고객 음성 생성 안 함
                "feedback": f"STT 정확도: {stt_eval['accuracy']:.1f}% | RAG 연동 평가: {rag_eval['score']:.1f}점",
                "conversation_phase": "ongoing",
                "session_score": 0,
                "conversation_history": conversation_history,
                "current_turn_index": next_turn_index,
                "stt_evaluations": stt_evaluations,
                "rag_evaluations": rag_evaluations,  # 🧪 RAG 평가 결과 누적
                "rag_summary": current_rag_summary,  # 🧪 현재까지의 RAG 평가 종합 결과
                "stt_evaluation": stt_eval,
                "rag_evaluation": rag_eval,
                "next_turn_expected_text": next_turn_expected_text,  # 다음 턴(고객 발화)의 기대 텍스트
                "next_turn_role": "customer" if next_turn_expected_text else None,  # 다음 턴 역할
                "is_test_mode": True  # 🧪 테스트 모드 플래그 명시
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
        """상품 데이터에서 평가 근거 추출"""
        evidence = {
            "matched_chunks": [],
            "key_information": [],
            "missing_information": []
        }
        
        if not product_data:
            return evidence
        
        # 상품별 핵심 정보 키워드
        key_info_keywords = {
            "DEP-MMD": ["MMDA", "입출금", "금리", "예금", "100만원", "차등", "최소", "가입금액"],
            "LON-MTG": ["주택담보", "LTV", "DTI", "DSR", "담보인정비율", "70%", "60%", "규제"],
            "LON-DCL": ["예금담보", "수취은행", "담보", "95%", "예금잔액", "초저금리"]
        }
        
        relevant_keywords = key_info_keywords.get(product_code, [])
        
        # 텍스트에서 찾은 키워드
        found_keywords_in_text = [kw for kw in relevant_keywords if kw in text]
        missing_keywords = [kw for kw in relevant_keywords if kw not in text]
        
        # 상품 데이터에서 관련 청크 찾기
        for chunk in product_data:
            chunk_text = chunk.get("text", "")
            # 텍스트나 청크에서 키워드가 발견되면 근거로 추가
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
    
    def _evaluate_customer_rag_integration(self, customer_text: str, expected_product_code: Optional[str], expected_keywords: List[str]) -> Dict:
        """고객 발화의 RAG 연동 평가 - 상품 코드 추출 및 키워드 매칭"""
        score = 0
        max_score = 100
        
        # 1. 키워드 매칭 (50점)
        found_keywords = [kw for kw in expected_keywords if kw in customer_text]
        keyword_score = (len(found_keywords) / len(expected_keywords) * 50) if expected_keywords else 50
        
        # 2. 상품 코드 추출 정확도 (50점)
        product_score = 0
        product_evidence = None
        if expected_product_code:
            # 실제 상품 데이터 로드
            product_data = self._load_product_data(expected_product_code)
            
            # 고객 발화에서 상품 관련 키워드 추출
            product_keywords_map = {
                "DEP-MMD": ["MMDA", "엠엠디에이", "입출금", "예금", "적금"],
                "LON-MTG": ["주택담보", "주택담보대출", "LTV", "DTI", "DSR", "담보"],
                "LON-DCL": ["예금담보", "예금담보대출", "수취은행", "담보"]
            }
            relevant_keywords = product_keywords_map.get(expected_product_code, [])
            found_product_keywords = [kw for kw in relevant_keywords if kw in customer_text]
            
            # 상품 코드 추출 정확도 계산
            if found_product_keywords:
                product_score = (len(found_product_keywords) / len(relevant_keywords) * 50) if relevant_keywords else 50
            else:
                product_score = 0
            
            # 상품 데이터에서 근거 추출
            product_evidence = self._extract_product_evidence(expected_product_code, customer_text, product_data)
        
        total_score = keyword_score + product_score
        
        return {
            "score": total_score,
            "max_score": max_score,
            "keyword_score": keyword_score,
            "product_extraction_score": product_score,
            "expected_product_code": expected_product_code,  # 🧪 평가 결과에 포함
            "found_keywords": found_keywords,
            "missing_keywords": [kw for kw in expected_keywords if kw not in customer_text],
            "extracted_product_keywords": found_product_keywords if expected_product_code else [],
            "product_evidence": product_evidence  # 🧪 상품 데이터 근거
        }
    
    def _evaluate_rag_integration(self, employee_text: str, expected_product_code: Optional[str], expected_keywords: List[str]) -> Dict:
        """직원 응답의 RAG 연동 평가 - RAG에서 가져온 상품 정보가 정확한지 확인"""
        score = 0
        max_score = 100
        
        # 1. 키워드 매칭 (50점)
        found_keywords = [kw for kw in expected_keywords if kw in employee_text]
        keyword_score = (len(found_keywords) / len(expected_keywords) * 50) if expected_keywords else 50
        
        # 2. RAG 상품 정보 포함 여부 (50점)
        product_score = 0
        product_evidence = None
        if expected_product_code:
            # 실제 상품 데이터 로드
            product_data = self._load_product_data(expected_product_code)
            
            # RAG에서 가져와야 할 상품별 핵심 정보 키워드
            product_info_keywords = {
                "DEP-MMD": ["MMDA", "입출금", "금리", "예금", "100만원", "차등"],
                "LON-MTG": ["주택담보", "LTV", "DTI", "DSR", "담보인정비율", "70%", "60%"],
                "LON-DCL": ["예금담보", "수취은행", "담보", "95%", "예금잔액"]
            }
            relevant_keywords = product_info_keywords.get(expected_product_code, [])
            found_product_keywords = [kw for kw in relevant_keywords if kw in employee_text]
            product_score = (len(found_product_keywords) / len(relevant_keywords) * 50) if relevant_keywords else 50
            
            # 상품 데이터에서 근거 추출
            product_evidence = self._extract_product_evidence(expected_product_code, employee_text, product_data)
        
        total_score = keyword_score + product_score
        
        return {
            "score": total_score,
            "max_score": max_score,
            "keyword_score": keyword_score,
            "rag_product_info_score": product_score,
            "expected_product_code": expected_product_code,  # 🧪 평가 결과에 포함
            "found_keywords": found_keywords,
            "missing_keywords": [kw for kw in expected_keywords if kw not in employee_text],
            "rag_info_keywords_found": found_product_keywords if expected_product_code else [],
            "product_evidence": product_evidence  # 🧪 상품 데이터 근거
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
