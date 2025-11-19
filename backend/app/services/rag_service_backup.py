"""
RAG (Retrieval-Augmented Generation) 챗봇 서비스
간단한 OpenAI API 직접 호출 방식
"""
from typing import List, Dict, Optional
import requests
import json
from datetime import datetime
from sqlmodel import Session, select
from sqlalchemy import text

from app.config import settings
from app.models.document import Document, DocumentChunk
from app.models.mentor import ChatHistory
from .title_lexicon import LEXICON, title_candidates, DOC_TYPE_PRIORITIES

class RAGService:
    """RAG 챗봇 서비스 클래스"""
    
    def __init__(self, session: Session):
        self.session = session
        self.api_key = settings.OPENAI_API_KEY  # 환경변수에서 로드
        self.base_url = "https://api.openai.com/v1"
        
        # 텍스트 분할 설정
        self.chunk_size = 1000
        self.chunk_overlap = 200
        
        # 온보딩 관련 키워드 (긍정)
        self.onboarding_keywords = [
            "인사", "근태", "복리후생", "연차", "시스템", "결재", "계좌", "전산", "보안", "코드", "교육",
            "은행", "업무", "규정", "대출", "예금", "적금", "외환", "송금", "환전", "고객", "창구",
            "매뉴얼", "절차", "네트워크", "데이터", "보고서", "회의", "미팅", "프로젝트", "팀", "부서", "조직"
        ]
        
        # 불용어 (부정) - 정말 쓸데없는 질문들만
        self.stopwords = [
            "밥", "식사", "먹었", "배고파", "배불러", "날씨", "비", "눈", "맑", "흐림",
            "심심", "재미", "놀", "영화", "드라마", "노래", "음악", "게임", "축구", "야구",
            "사랑", "좋아해", "싫어해", "여자친구", "남자친구", "연애", "결혼", "아이",
            "주식", "투자", "로또", "복권", "도박", "술", "담배", "취미", "여행",
            "쇼핑", "옷", "화장", "운동", "헬스", "다이어트", "건강", "병", "약", "의사",
            "아이돌", "연예인", "배우", "가수", "정치", "선거", "뉴스", "시사"
        ]
    
    def _is_onboarding_related(self, query: str) -> bool:
        """
        질문이 온보딩 관련인지 사전 필터링 (라이트 버전)
        """
        query_lower = query.lower().strip()
        
        # 간단한 인사는 먼저 허용 (온보딩 튜터로서 정중한 응답)
        greetings = ["안녕", "안녕하세요", "하이", "hi", "hello", "반갑"]
        if any(greeting in query_lower for greeting in greetings):
            return True
        
        # 온보딩 관련 키워드 포함 여부 확인 (짧은 질문도 허용)
        for keyword in self.onboarding_keywords:
            if keyword in query_lower:
                return True
        
        # 명백한 불용어만 필터링 (정확한 단어 매칭)
        explicit_stopwords = ["밥", "식사", "먹었", "날씨", "비", "눈", "영화", "드라마", 
                             "사랑", "여자친구", "남자친구", "주식", "투자", "로또", 
                             "아이돌", "연예인", "정치", "선거", "뉴스"]
        
        # 정확한 단어 매칭으로만 필터링
        for stopword in explicit_stopwords:
            if stopword == query_lower.strip():
                return False
        
        # 나머지는 모두 허용 (GPT가 온보딩 관련 여부 판단)
        return True
    
    def _split_text(self, text: str) -> List[str]:
        """텍스트를 청크로 분할"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # 마지막 청크가 아니고 중복이 필요한 경우
            if end < len(text) and self.chunk_overlap > 0:
                # 단어 경계에서 자르기
                while end > start and text[end] not in ' \n\t':
                    end -= 1
                if end == start:  # 단어가 너무 긴 경우
                    end = start + self.chunk_size
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # 다음 청크 시작점 (중복 제외)
            start = end - self.chunk_overlap if end < len(text) else end
        
        return chunks
    
    def _get_embedding(self, text: str) -> List[float]:
        """텍스트의 임베딩 벡터 생성"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "text-embedding-ada-002",
                "input": text
            }
            
            response = requests.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["data"][0]["embedding"]
            else:
                print(f"Embedding API error: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"Embedding error: {e}")
            return []

    async def index_document(self, document_id: int, content: str) -> bool:
        """
        문서를 청크로 분할하고 임베딩 생성
        Args:
            document_id: 문서 ID
            content: 문서 내용
        Returns:
            bool: 성공 여부
        """
        try:
            # 텍스트 분할
            chunks = self._split_text(content)
            
            # 기존 청크 삭제
            existing_chunks = self.session.exec(
                select(DocumentChunk).where(DocumentChunk.document_id == document_id)
            ).all()
            for chunk in existing_chunks:
                self.session.delete(chunk)
            
            # 새 청크 생성 및 임베딩
            for i, chunk_text in enumerate(chunks):
                embedding = self._get_embedding(chunk_text)
                if embedding:
                    chunk = DocumentChunk(
                        document_id=document_id,
                        chunk_index=i,
                        content=chunk_text,
                        embedding=embedding
                    )
                    self.session.add(chunk)
            
            # 문서 인덱싱 상태 업데이트
            document = self.session.get(Document, document_id)
            if document:
                document.is_indexed = True
            
            self.session.commit()
            return True
            
        except Exception as e:
            print(f"Indexing error: {e}")
            self.session.rollback()
            return False

    async def similarity_search(self, query: str, k: int = 5) -> List[Dict]:
        """
        유사도 검색으로 관련 문서 청크 찾기
        Args:
            query: 검색 쿼리
            k: 반환할 결과 수
        Returns:
            List[Dict]: 관련 문서 청크들
        """
        try:
            # 간단한 텍스트 검색 (벡터 검색 완전 제거)
            sql = text("""
                SELECT 
                    dc.content,
                    dc.chunk_index,
                    d.title,
                    d.category,
                    d.id as document_id,
                    0.9 as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE d.is_indexed = true AND d.category = 'RAG'
                AND (dc.content ILIKE :query OR d.title ILIKE :query)
                ORDER BY d.upload_date DESC
                LIMIT :k
            """)
            
            print(f"텍스트 검색 쿼리: {query}")
            
            result = self.session.execute(sql, {"query": f"%{query}%", "k": k})
            
            results = []
            for row in result:
                results.append({
                    "content": row.content,
                    "title": row.title,
                    "category": row.category,
                    "document_id": row.document_id,
                    "chunk_index": row.chunk_index,
                    "similarity": float(row.similarity)
                })
            
            print(f"Found {len(results)} relevant chunks for query: {query[:50]}...")
            return results
            
        except Exception as e:
            print(f"Similarity search error: {e}")
            # 트랜잭션 롤백 및 새 세션 시작
            try:
                self.session.rollback()
                self.session.close()
                # 새 세션 생성
                from app.database import get_session
                self.session = next(get_session())
            except Exception as rollback_error:
                print(f"Rollback error: {rollback_error}")
                # 완전히 새 세션으로 교체
                try:
                    from app.database import get_session
                    self.session = next(get_session())
                except Exception:
                pass
            return []
    
    def _extract_keywords(self, question: str) -> List[str]:
        """질문에서 키워드 추출"""
        # 대출 관련 키워드 매핑
        loan_keywords = {
            "대출": ["대출", "가계대출", "주택담보대출", "전월세보증금대출", "기업대출"],
            "상품": ["상품", "상품설명서", "상품안내"],
            "고객": ["고객", "70대", "연령", "나이"],
            "추천": ["추천", "상담", "문의"],
            "금리": ["금리", "이자", "수수료"],
            "약관": ["약관", "기본약관", "특약"],
            "양식": ["양식", "서식", "신청서", "위임장", "확인서"]
        }
        
        keywords = []
        question_lower = question.lower()
        
        for category, words in loan_keywords.items():
            for word in words:
                if word in question_lower:
                    keywords.extend(words)
                    break
        
        # 중복 제거하고 상위 3개만 반환
        return list(set(keywords))[:3]
    
    def _call_gpt(self, prompt: str) -> str:
        """GPT API 직접 호출"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                print(f"GPT API error: {response.status_code} - {response.text}")
                return "죄송합니다. 답변 생성 중 오류가 발생했습니다."
                
        except Exception as e:
            print(f"GPT API call error: {e}")
            return "죄송합니다. 답변 생성 중 오류가 발생했습니다."
    
    async def generate_answer(
        self,
        question: str,
        user_id: int,
        context_docs: Optional[List[Dict]] = None
    ) -> Dict:
        """
        질문에 대한 답변 생성 (하이브리드 RAG + GPT)
        1. 먼저 RAG로 업로드된 문서에서 답변 시도
        2. 답변 품질이 낮으면 GPT API로 폴백
        Args:
            question: 사용자 질문
            user_id: 사용자 ID
            context_docs: 컨텍스트 문서 (없으면 자동 검색)
        Returns:
            Dict: 답변 및 메타데이터
        """
        start_time = datetime.utcnow()
        
        # 0단계: 사전 필터링 - 정말 명백한 불용어만 차단
        if not self._is_onboarding_related(question):
            # 사전 필터링에서 걸린 질문도 GPT가 자연스럽게 처리하도록 허용
            # (너무 딱딱한 응답 대신 GPT가 상황에 맞게 응답)
            pass
        
        # 은행 온보딩 관련 키워드 확인 (수신/여신/외환 파트)
        onboarding_keywords = {
            "수신": ["예금", "적금", "통장", "계좌", "입금", "출금", "이자", "금리", "수신", "예금자보호", "신규개설", "통장발급", "비밀번호", "인증서"],
            "여신": ["대출", "신용", "담보", "여신", "dsr", "dti", "ltv", "연체", "신용등급", "한도", "신용평가", "담보심사", "상환관리", "마이너스통장", "대출심사"],
            "외환": ["송금", "환전", "외환", "해외송금", "환율", "tt매도", "tt매입", "무역결제", "외화예금", "송금수수료", "외화계좌", "해외송금한도", "환차익"]
        }
        
        question_lower = question.strip().lower()
        
        # 어떤 파트와 관련된 질문인지 확인
        detected_part = None
        for part, keywords in onboarding_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                detected_part = part
                break
        
        # 이전에는 온보딩 관련 키워드가 없으면 RAG를 건너뛰었으나,
        # 이제는 모든 질문에 대해 RAG를 우선 시도한다.
        
        # 1단계: 의도 분류 및 부드러운 라우팅
        if context_docs is None:
            print(f"RAG 검색 시작: '{question}'")
            
            # 의도 분류
            intent_result = self._classify_intent(question)
            print(f"의도 분류: {intent_result}")
            
            # 인사말 처리 (거절이 아닌 환영 가이드)
            if self._is_greeting(question):
                print("인사말 감지 - 환영 가이드")
                return {
                    "answer": "안녕하세요! 🐻 AI 하리보입니다!\n\n필요한 업무를 알려주세요:\n• '위임장 양식 다운로드'\n• '이의신청서 제출 방법'\n• '주택담보대출 필수서류'\n• 'CD 수익률 문의'\n\n어떤 도움이 필요하신가요? 🐼",
                    "sources": [],
                    "response_time": 0.0,
                    "answer_type": "guide",
                    "mode": "GUIDE",
                    "doc_type": "general",
                    "citations": [],
                    "next_actions": ["위임장 양식", "이의신청서", "대출 상품", "예금 상품"],
                    "confidence": 1.0,
                    "notes": "인사말로 분류됨"
                }
            
            # 잡담 처리 (인사말이 아닌 진짜 잡담)
            if intent_result["intent"] == "chitchat":
                print("잡담 감지 - 정중 거절")
                return {
                    "answer": "업무 관련 질문 위주로 도와드려요. 어떤 업무가 어려우신가요? 🐻",
                    "sources": [],
                    "response_time": 0.0,
                    "answer_type": "refusal",
                    "mode": "REFUSAL",
                    "doc_type": "general",
                    "citations": [],
                    "next_actions": [],
                    "confidence": 0.0,
                    "notes": "잡담으로 분류됨"
                }
            
            # 쿼리 확장 (동의어, 키워드 추가)
            expanded_queries = self._expand_query(question)
            
            # 양식/서식 전용 확장 추가
            if intent_result["intent"] == "onboarding" or len(question.strip()) <= 4:
                form_queries = self._expand_forms_query(question)
                expanded_queries.extend(form_queries)
                print(f"양식 확장 쿼리 추가: {form_queries}")
            
            print(f"최종 확장된 쿼리: {expanded_queries}")
            
            # 타이틀 게이팅을 통한 검색 (우선)
            context_docs = self._title_gated_search(question, intent_result["intent"], k=20)
            
            # 타이틀 게이팅 결과가 부족하면 일반 검색으로 보완
            if len(context_docs) < 5:
                print("타이틀 게이팅 결과 부족 - 일반 검색으로 보완")
                additional_docs = await self.similarity_search(question, k=15)
                # 중복 제거
                existing_ids = {doc['id'] for doc in context_docs}
                for doc in additional_docs:
                    if doc['id'] not in existing_ids:
                        context_docs.append(doc)
            
            print(f"최종 RAG 검색 결과: {len(context_docs)}개 문서")
            for i, doc in enumerate(context_docs):
                print(f"  {i+1}. {doc['title']} (유사도: {doc.get('similarity', 0):.3f})")
            
            # 신뢰도 기반 필터링 (부드러운 라우팅)
            if context_docs:
                # 상위 5개 문서의 평균 유사도 계산
                top5_similarity = sum(doc.get('similarity', 0) for doc in context_docs[:5]) / min(5, len(context_docs))
                print(f"상위 5개 문서 평균 유사도: {top5_similarity:.3f}")
                
                # 동적 임계값 적용
                conf_cut, rerank_cut = self._get_dynamic_threshold(question)
                print(f"동적 임계값: conf_cut={conf_cut}, rerank_cut={rerank_cut}")
                
                # 부드러운 라우팅 규칙
                if top5_similarity >= conf_cut:
                    # RAG 사용 (온보딩/은행일반 구분만 출력 문구에 반영)
                    threshold = max(0.3, context_docs[0].get('similarity', 0) * 0.7)
                    context_docs = [doc for doc in context_docs if doc.get('similarity', 0) >= threshold]
                    print(f"RAG 모드 - 필터링 후: {len(context_docs)}개 문서 (임계값: {threshold:.3f})")
                else:
                    # 신뢰도 부족 - GPT 백업으로 적극 전환
                    print(f"신뢰도 부족 ({top5_similarity:.3f} < {conf_cut}) - GPT 백업으로 전환")
                    context_docs = []
        
        # 컨텍스트 구성 (제목에서 "RAG - " 제거)
        context = "\n\n".join([
            f"[{doc['title'].replace('RAG - ', '')}]\n{doc['content']}"
            for doc in context_docs
        ])
        
        # 온보딩 교육용 RAG 답변 생성 (파트 감지되면 설명 포함)
        part_info = {
            "수신": "고객이 은행에 돈을 맡기는 업무 (예금, 적금 등)",
            "여신": "고객에게 돈을 빌려주는 업무 (대출, 신용평가 등)", 
            "외환": "외국 돈을 사고팔거나 송금하는 업무"
        }

        part_header = ""
        if detected_part:
            part_header = f"현재 {detected_part} 파트 교육 중이며, {part_info[detected_part]}에 대해 설명하고 있습니다. 🐼\n\n"

        # 의도에 따른 모드 결정
        intent_result = self._classify_intent(question)
        mode = "RAG" if context_docs else "GENERAL"
        
        # 문서 타입 분류 및 우선순위
        doc_type_priority = self._get_doc_type_priority(intent_result["intent"])
        primary_doc_type = "mixed"
        if context_docs:
            # 가장 많이 나타나는 문서 타입 결정
            doc_types = [self._classify_doc_type(doc["title"], doc.get("content", "")) for doc in context_docs]
            primary_doc_type = max(set(doc_types), key=doc_types.count) if doc_types else "general"
        
        if mode == "RAG":
            # 문서 타입별 답변 템플릿 가져오기
            answer_template = self._get_doc_type_template(primary_doc_type)
            
            # RAG 모드 프롬프트
            rag_prompt = (
                "당신은 '은행 온보딩+일반 금융' RAG 어시스턴트입니다. 🐻\n"
                f"{part_header}"
                "다음 검색 컨텍스트를 기반으로 답변하세요:\n\n"
                f"{context}\n\n"
                f"질문: {question}\n"
                f"의도: {intent_result['intent']} / 우선 문서타입: {doc_type_priority}\n"
                f"주요 문서타입: {primary_doc_type}\n\n"
                "답변 요구사항:\n"
                "- 신입사원이 이해하기 쉽게 친절하고 상세하게 답변하세요\n"
                "- 자연스러운 문단으로 구성하여 길게 설명하세요 (불릿 포인트나 단계별 나열 금지)\n"
                "- 핵심 정보를 먼저 제시하고, 세부사항을 포함한 완전한 설명을 제공하세요\n"
                "- 문단과 문단 사이는 자연스럽게 연결하여 흐름 있게 작성하세요\n"
                "- 한국어로 친근하게 답변하세요 (🐻 이모티콘은 답변 시작에만 사용)\n"
                "- AI 하리보로서 신입사원을 도와주는 마음으로 답변하세요\n"
                "- 문서 내용이 있으면 반드시 문서 내용을 우선 활용하고, 문서 내용에 없는 부분만 일반적인 은행 업무 지식으로 보완하세요\n"
                "- 질문과 관련 없는 내용은 답변에 포함하지 마세요\n"
                "- 질문의 핵심 키워드와 직접 관련된 내용만 답변하세요\n"
                "- 문장을 충분히 길게 작성하여 상세한 설명을 제공하세요\n"
                "- 각 문단은 5-7문장으로 구성하여 충분한 정보를 제공하세요\n"
                "- 상품 추천 관련 질문에는 구체적인 상품명과 특징을 포함하여 답변하세요\n"
                "- 연령대별 고객 특성을 고려한 맞춤형 상품 추천을 제공하세요\n"
                "- 대출 상품의 경우 금리, 한도, 상환조건 등 구체적인 정보를 포함하세요\n"
                "- 대출 상담 질문에는 실제 대출 상품을 추천하고, 알림 서비스나 기타 서비스는 추천하지 마세요\n"
                "- 답변을 자연스러운 문단으로 구성하여 길고 상세하게 작성하세요\n"
                "- 대출 상품 추천 시에는 구체적인 상품명(가계대출, 주택담보대출, 전월세보증금대출 등)을 명시하세요\n"
                "- 70대 고객에게는 연령대에 맞는 대출 상품을 구체적으로 추천하세요\n"
                "- 대출 상담 질문에는 반드시 구체적인 대출 상품명을 추천하고, 단계별 설명이나 일반적인 조언은 피하세요\n"
                "- 고객에게 직접적인 대출 상품 추천을 제공하세요\n\n"
                f"답변 형식 (문서타입: {primary_doc_type}):\n{answer_template}\n"
                "다음 JSON 형식으로만 출력하라:\n"
                "{\n"
                '  "mode": "RAG",\n'
                f'  "doc_type": "{primary_doc_type}",\n'
                '  "answer": "핵심 답변 내용",\n'
                '  "citations": [\n'
                '    {"doc_title": "문서제목", "section": "섹션", "page": 0, "clause_id": ""}\n'
                '  ],\n'
                '  "next_actions": ["지점 예약", "필요서류 확인", "다운로드 링크 열기"],\n'
                '  "confidence": 0.8,\n'
                '  "notes": "선택: 가정/제약/추가확인 안내"\n'
                "}\n\n"
                "답변:"
            )
        else:
            # GENERAL 모드 프롬프트
            rag_prompt = (
                "당신은 은행 일반 상담 도우미입니다. 🐻\n"
                f"질문: {question}\n\n"
                "답변 요구사항:\n"
                "- 신입사원이 이해하기 쉽게 친절하고 상세하게 답변하세요\n"
                "- 자연스러운 문단으로 구성하여 길게 설명하세요 (불릿 포인트나 단계별 나열 금지)\n"
                "- 핵심 정보를 먼저 제시하고, 세부사항을 포함한 완전한 설명을 제공하세요\n"
                "- 문단과 문단 사이는 자연스럽게 연결하여 흐름 있게 작성하세요\n"
                "- 한국어로 친근하게 답변하세요 (🐻 이모티콘은 답변 시작에만 사용)\n"
                "- AI 하리보로서 신입사원을 도와주는 마음으로 답변하세요\n"
                "- 은행 업무에 관련된 실용적인 조언을 포함하세요\n"
                "- 문장을 충분히 길게 작성하여 상세한 설명을 제공하세요\n"
                "- 각 문단은 5-7문장으로 구성하여 충분한 정보를 제공하세요\n"
                "- 상품 추천 관련 질문에는 구체적인 상품명과 특징을 포함하여 답변하세요\n"
                "- 연령대별 고객 특성을 고려한 맞춤형 상품 추천을 제공하세요\n"
                "- 대출 상품의 경우 금리, 한도, 상환조건 등 구체적인 정보를 포함하세요\n"
                "- 대출 상담 질문에는 실제 대출 상품을 추천하고, 알림 서비스나 기타 서비스는 추천하지 마세요\n"
                "- 답변을 자연스러운 문단으로 구성하여 길고 상세하게 작성하세요\n"
                "- 대출 상품 추천 시에는 구체적인 상품명(가계대출, 주택담보대출, 전월세보증금대출 등)을 명시하세요\n"
                "- 70대 고객에게는 연령대에 맞는 대출 상품을 구체적으로 추천하세요\n"
                "- 대출 상담 질문에는 반드시 구체적인 대출 상품명을 추천하고, 단계별 설명이나 일반적인 조언은 피하세요\n"
                "- 고객에게 직접적인 대출 상품 추천을 제공하세요\n"
                "- 정책/내규처럼 지점·시기별로 달라질 수 있는 내용은 '일반적 기준'으로만 설명하고, 확인 절차/준비 서류/문의 경로를 함께 안내한다\n"
                "- 온보딩 문맥과 연결될 수 있으면 추가로 '관련 온보딩 항목'을 제시한다\n"
                "- 가능한 한 다음 행동(상담 예약/필요 서류/메뉴 경로)을 제안한다\n\n"
                "다음 JSON 형식으로만 출력하라:\n"
                "{\n"
                '  "mode": "GENERAL",\n'
                '  "answer": "일반 정보 답변",\n'
                '  "citations": [],\n'
                '  "confidence": 0.6,\n'
                '  "notes": "일반 정보 - 지점별 상이 가능"\n'
                "}\n\n"
                "답변:"
            )
        
        # RAG 답변 생성
        rag_answer = self._call_gpt(rag_prompt)
        
        # JSON 응답 파싱 시도
        try:
            import json
            # JSON 응답에서 답변 추출
            if rag_answer.strip().startswith('{'):
                json_response = json.loads(rag_answer)
                final_answer = json_response.get("answer", rag_answer)
                answer_mode = json_response.get("mode", mode)
                answer_doc_type = json_response.get("doc_type", primary_doc_type)
                citations = json_response.get("citations", [])
                next_actions = json_response.get("next_actions", [])
                confidence = json_response.get("confidence", 0.8)
                notes = json_response.get("notes", "")
            else:
                # JSON이 아닌 경우 기존 로직 사용
                final_answer = rag_answer
                answer_mode = mode
                answer_doc_type = primary_doc_type
                citations = []
                next_actions = []
                confidence = 0.8
                notes = ""
        except:
            # JSON 파싱 실패 시 기존 로직 사용
            final_answer = rag_answer
            answer_mode = mode
            answer_doc_type = primary_doc_type
            citations = []
            next_actions = []
            confidence = 0.8
            notes = ""
        
        # 답변 품질 평가 (중요 단어 필터링 포함)
        is_rag_adequate = self._evaluate_answer_quality(final_answer, context_docs, question)
        
        if is_rag_adequate and context_docs:
            # RAG 답변이 적절하면 그대로 사용
            # 고품질 문서만 참고자료로 사용 (임계값 낮춤)
            high_quality_docs = [doc for doc in context_docs if doc.get('similarity', 0) >= 0.50]
            
            answer_type = "rag"
            context_docs = high_quality_docs  # 고품질 문서만 전달
        else:
            # RAG 답변이 부적절하거나 문서가 없으면 GPT 백업 (적극 활용)
            print("RAG 실패 - GPT 백업으로 전환 (적극 활용)")
            gpt_answer = await self._generate_gpt_fallback(question, context_docs)
            final_answer = gpt_answer
            answer_type = "gpt_backup"
            answer_mode = "GENERAL"
            
            # GPT 백업용 관련 문서 추천
            related_docs = self._get_related_documents_for_gpt(question)
            if related_docs:
                # GPT 백업 시에도 sources 정보 포함
                context_docs = [{"title": doc, "content": "", "similarity": 0.5} for doc in related_docs[:3]]
                citations = [{"doc_title": doc, "section": "", "page": 0, "clause_id": ""} for doc in related_docs[:3]]
            else:
                context_docs = []
                citations = []
            confidence = 0.6
            notes = "GPT 백업 답변"
        
        # 응답 시간 계산
        response_time = (datetime.utcnow() - start_time).total_seconds()
        
        # 대화 기록 저장 (안전한 트랜잭션)
        try:
            chat_history = ChatHistory(
                user_id=user_id,
                user_message=question,
                bot_response=final_answer,
                source_documents=json.dumps([
                    {"title": doc["title"], "category": doc["category"], "type": answer_type}
                    for doc in context_docs
                ], ensure_ascii=False),
                response_time=response_time
            )
            self.session.add(chat_history)
            self.session.commit()
        except Exception as e:
            print(f"Chat history save error: {e}")
            self.session.rollback()
        
        return {
            "answer": final_answer,
            "sources": context_docs,
            "response_time": response_time,
            "answer_type": answer_type,
            "mode": answer_mode,
            "doc_type": answer_doc_type,
            "citations": citations,
            "next_actions": next_actions,
            "confidence": confidence,
            "notes": notes
        }
    
    def _evaluate_answer_quality(self, answer: str, context_docs: List[Dict], question: str = "") -> bool:
        """
        RAG 답변의 품질 평가 (중요 단어 필터링 포함)
        Args:
            answer: 생성된 답변
            context_docs: 참고 문서들
            question: 원본 질문
        Returns:
            bool: 답변이 적절한지 여부
        """
        if not answer or len(answer.strip()) < 20:
            print("Answer too short")
            return False

        # 컨텍스트 문서가 없으면 RAG 답변으로 부적절 (하지만 GPT 백업 허용)
        if not context_docs or len(context_docs) == 0:
            print("No context documents found - GPT 백업 허용")
            return True  # GPT 백업을 허용하도록 True로 변경

        # 중요 단어 필터링 - 질문의 핵심 키워드가 문서에 있는지 확인
        if question:
            question_lower = question.lower()
            # 질문에서 중요한 키워드 추출 (2글자 이상)
            important_keywords = [word for word in question_lower.split() if len(word) >= 2]
            
            # 문서 내용에 중요한 키워드가 포함되어 있는지 확인
            has_important_keywords = False
            for doc in context_docs:
                doc_content_lower = doc.get('content', '').lower()
                if any(keyword in doc_content_lower for keyword in important_keywords):
                    has_important_keywords = True
                    break
            
            if not has_important_keywords:
                print("No important keywords found in RAG documents - GPT 백업 허용")
                return True  # GPT 백업을 허용하도록 True로 변경
        
        # 부정적인 지표들
        negative_indicators = [
            "찾을 수 없습니다",
            "정보를 찾을 수 없습니다",
            "제공된 자료에서",
            "모르겠습니다",
            "알 수 없습니다",
            "cannot find",
            "not found",
            "no information",
            "unable to find"
        ]
        
        answer_lower = answer.lower()
        for indicator in negative_indicators:
            if indicator in answer_lower:
                print(f"Negative indicator found: {indicator} - GPT 백업에서는 허용")
                return True  # GPT 백업에서는 허용
        
        # 유사도 임계값을 대폭 완화하여 더 많은 문서를 허용
        if context_docs and all(doc.get('similarity', 0) < 0.20 for doc in context_docs):
            print("All documents have low similarity - GPT 백업 허용")
            return True  # GPT 백업 허용

        # 관련성 높은 문서가 있는지 확인 (임계값 대폭 완화)
        high_quality_docs = [doc for doc in context_docs if doc.get('similarity', 0) >= 0.20]
        if not high_quality_docs:
            print("No high-quality relevant documents found - GPT 백업 허용")
            return True  # GPT 백업 허용

        print(f"Answer quality check passed. High-quality docs: {len(high_quality_docs)}")
        return True
    
    async def _generate_gpt_fallback(self, question: str, context_docs: List[Dict]) -> str:
        """
        온보딩 교육용 GPT 폴백 답변 생성
        """
        # 간단한 인사 처리
        if any(greeting in question.lower() for greeting in ["안녕", "안녕하세요", "하이", "hi", "hello"]):
            return "안녕하세요! 🐻 저는 AI 하리보예요! 🐼 하경은행 신입사원 온보딩을 도와드립니다. 수신(예금), 여신(대출), 외환(환전·송금) 파트 중 궁금한 업무가 있으시면 언제든 물어보세요! 🐻‍❄️"
        
        # GPT 백업용 시스템 프롬프트 (RAG 실패 시) - 적극적 활용
        system_prompt = """당신은 '은행 신입사원 온보딩 도우미'입니다. 🐻

RAG 시스템에서 관련 자료를 찾지 못했을 때도 가능한 한 도움이 되는 답변을 제공하세요.

다음 사항을 반드시 명시하세요:
1. 정책은 지점/시기별로 상이할 수 있음을 알리기
2. 추가 확인 절차/담당 부서를 안내하기
3. "온보딩 관련 질문만 답변합니다" 같은 거절 메시지는 절대 사용하지 마세요
4. 답변 마지막에 관련 자료실 문서를 추천하세요

온보딩 관련 질문에 대해서는 다음 형식으로 답변하세요:
- ① 핵심 개념 요약 (한 문단) 🐻
- ② 실제 현장 예시 (구체적인 상황이나 숫자 포함) 🐼
- ③ 실무 유의사항 (주의할 점이나 팁) 🐻‍❄️
- ④ 관련 자료실 문서 추천 (예: "자료실에서 '위임장 양식'을 검색해보세요")

답변할 때는 항상 곰 이모티콘(🐻, 🐼, 🐻‍❄️)을 적절히 사용하여 친근하고 귀여운 느낌을 주세요.
답변은 친근하고 도움이 되는 톤으로 작성하세요."""
        
        gpt_prompt = f"""{system_prompt}

질문: {question}

답변:"""
        
        # GPT로 답변 생성
        gpt_answer = self._call_gpt(gpt_prompt)
        
        return gpt_answer
    
    def _get_related_documents_for_gpt(self, question: str) -> List[str]:
        """
        GPT 백업용 관련 문서 추천
        """
        query_lower = question.lower()
        related_docs = []
        
        # 질문 키워드 기반 문서 추천
        doc_recommendations = {
            "위임장": ["위임장(개인여신)", "위임장(금결원+대출이동시스템)", "위임장+(전월세대출+심사용)"],
            "이의신청": ["이의신청서", "이의제기신청서", "피해구제신청서"],
            "신청서": ["민원접수양식", "제증명의뢰서", "자료열람요구서"],
            "약관": ["예금거래기본약관", "전세지킴보증약관", "전자금융거래기본약관"],
            "대출": ["가계대출상품설명서", "기업대출상품설명서", "전월세보증금대출+상품설명서"],
            "예금": ["거치식예금약관", "적립식예금약관", "입출금이자유로운예금_약관"],
            "보증": ["신용보증서", "신용보증약정서", "보증채무이행청구서"],
            "만기": ["대출만기안내", "대출만기경과안내"],
            "계좌": ["채권자계좌신고서", "증권계좌개설서비스+설명서"],
            "상황표": ["수신거래상황표", "여신거래상황표"],
            "확인서": ["잔존채무확인서", "이자계산내역서"],
            "안내": ["고객권리안내문", "대출만기안내"],
            "특약": ["비과세종합저축특약"],
            "통지서": ["신용보증부실통지서"],
            "서비스": ["계좌통합관리서비스+이용약관", "증권계좌개설서비스_이용약관"]
        }
        
        # 키워드 매칭으로 관련 문서 추천
        for keyword, docs in doc_recommendations.items():
            if keyword in query_lower:
                related_docs.extend(docs)
        
        # 중복 제거
        return list(set(related_docs))
    
    def _classify_intent(self, query: str) -> dict:
        """
        의도 분류 - 온보딩/은행일반/잡담 구분
        """
        query_lower = query.lower()
        
        # 온보딩 관련 키워드 (높은 가중치) - 확장
        onboarding_keywords = {
            "온보딩": 1.0, "신입사원": 1.0, "교육": 0.9, "훈련": 0.9,
            "내규": 0.9, "규정": 0.8, "매뉴얼": 0.8, "절차": 0.8,
            "시스템": 0.7, "업무": 0.7, "프로세스": 0.7, "가이드": 0.7,
            "심사": 0.6, "서류": 0.6, "보류": 0.6, "승인": 0.6,
            "위임장": 0.8, "신청서": 0.8, "이의제기": 0.8, "신청": 0.7,
            "양식": 0.7, "서식": 0.7, "약관": 0.7, "계약서": 0.7,
            "보증서": 0.7, "증명서": 0.7, "확인서": 0.7, "동의서": 0.7
        }
        
        # 은행 일반 키워드 (중간 가중치)
        bank_general_keywords = {
            "대출": 0.8, "예금": 0.8, "적금": 0.8, "통장": 0.7,
            "계좌": 0.7, "이자": 0.7, "금리": 0.7, "수익률": 0.7,
            "송금": 0.6, "이체": 0.6, "환전": 0.6, "외환": 0.6,
            "카드": 0.6, "보험": 0.5, "투자": 0.5, "펀드": 0.5
        }
        
        # 잡담 키워드 (낮은 가중치)
        chitchat_keywords = {
            "밥": 0.3, "먹었": 0.3, "날씨": 0.2, "영화": 0.2,
            "음악": 0.2, "게임": 0.2, "연애": 0.1, "주식": 0.1,
            "안녕": 0.4, "하이": 0.4, "hello": 0.4
        }
        
        # 점수 계산
        onboarding_score = sum(weight for keyword, weight in onboarding_keywords.items() 
                              if keyword in query_lower)
        bank_general_score = sum(weight for keyword, weight in bank_general_keywords.items() 
                                if keyword in query_lower)
        chitchat_score = sum(weight for keyword, weight in chitchat_keywords.items() 
                            if keyword in query_lower)
        
        # 정규화 (0-1 범위)
        total_score = onboarding_score + bank_general_score + chitchat_score
        if total_score > 0:
            onboarding_score /= total_score
            bank_general_score /= total_score
            chitchat_score /= total_score
        
        # 의도 결정 (임계값 완화)
        if chitchat_score > 0.4:  # 잡담 임계값 높임
            intent = "chitchat"
        elif onboarding_score > 0.2 or bank_general_score > 0.2:  # 온보딩/은행일반 임계값 낮춤
            if onboarding_score >= bank_general_score:
                intent = "onboarding"
            else:
                intent = "bank_general"
        else:
            intent = "unknown"
        
        return {
            "intent": intent,
            "onboarding_score": onboarding_score,
            "bank_general_score": bank_general_score,
            "chitchat_score": chitchat_score
        }
    
    def _expand_query(self, query: str) -> List[str]:
        """
        쿼리 확장 - 동의어, 키워드 추가
        """
        query_lower = query.lower()
        expanded_queries = [query]
        
        # 은행 업무 동의어 매핑
        synonyms = {
            "대출": ["여신", "신용", "보증", "대환", "보증금"],
            "예금": ["수신", "적금", "통장", "계좌", "입금"],
            "송금": ["이체", "환전", "외환", "해외송금"],
            "심사": ["심의", "검토", "평가", "승인"],
            "서류": ["문서", "증빙", "자료", "서류"],
            "보류": ["중단", "지연", "연기", "보류"],
            "피해": ["손실", "사기", "피해구제", "구제"],
            "수익률": ["이자", "금리", "수익", "이율"],
            "cd": ["예금증서", "정기예금", "cd수익률"]
        }
        
        # 동의어로 쿼리 확장
        for original, synonyms_list in synonyms.items():
            if original in query_lower:
                for synonym in synonyms_list:
                    expanded_query = query_lower.replace(original, synonym)
                    if expanded_query not in expanded_queries:
                        expanded_queries.append(expanded_query)
        
        return expanded_queries
    
    def _title_gated_search(self, question: str, intent: str, k: int = 20) -> List[Dict]:
        """
        타이틀 게이팅을 통한 검색
        짧은 질의나 폼 키워드가 포함된 경우 제목 후보를 먼저 필터링
        """
        # 짧은 질의 또는 폼 키워드 감지
        short = len(question.strip()) <= 6
        form_keywords = ["약관", "양식", "서식", "신청서", "설명서", "위임장", "확인서", "동의서"]
        has_form_keyword = any(kw in question for kw in form_keywords)
        
        title_shortlist = []
        if short or has_form_keyword:
            title_shortlist = title_candidates(question, LEXICON)
            print(f"타이틀 게이팅 후보: {title_shortlist}")
        
        # doc_type 우선순위
        doc_type_prior = DOC_TYPE_PRIORITIES.get(intent, [])
        print(f"doc_type 우선순위: {doc_type_prior}")
        
        # 검색 쿼리 구성
        query = f"""
        SELECT d.id, d.title, d.category, d.description, d.file_path, d.upload_date,
               dc.content, dc.chunk_index, dc.metadata
        FROM documents d
        JOIN document_chunks dc ON d.id = dc.document_id
        WHERE d.is_indexed = true
        """
        
        # 타이틀 필터링
        if title_shortlist:
            title_conditions = " OR ".join([f"d.title LIKE '%{title}%'" for title in title_shortlist])
            query += f" AND ({title_conditions})"
        
        # doc_type 필터링
        if doc_type_prior:
            type_conditions = " OR ".join([f"d.category = '{cat}'" for cat in doc_type_prior])
            query += f" AND ({type_conditions})"
        
        query += f" ORDER BY d.upload_date DESC LIMIT {k * 3}"
        
        try:
            result = self.session.execute(text(query))
            rows = result.fetchall()
            
            documents = []
            for row in rows:
                doc = {
                    'id': row[0],
                    'title': row[1],
                    'category': row[2],
                    'description': row[3],
                    'file_path': row[4],
                    'upload_date': row[5],
                    'content': row[6],
                    'chunk_index': row[7],
                    'metadata': row[8] if row[8] else {},
                    'similarity': 0.8 if title_shortlist and any(title in row[1] for title in title_shortlist) else 0.5
                }
                documents.append(doc)
            
            print(f"타이틀 게이팅 검색 결과: {len(documents)}개")
            return documents[:k]
            
        except Exception as e:
            print(f"타이틀 게이팅 검색 오류: {e}")
            return []
    
    def _get_dynamic_threshold(self, query: str) -> tuple[float, float]:
        """
        동적 임계값 - 대폭 완화하여 GPT 백업 적극 활용
        """
        if len(query.strip()) <= 4:  # '위임장', '약관' 등
            return (0.05, 0.30)  # 매우 낮은 임계값으로 통과율 대폭↑
        return (0.10, 0.40)  # 일반 질의도 낮은 임계값
    
    def _is_greeting(self, query: str) -> bool:
        """
        인사말 감지 - 짧은 인사만
        """
        greeting_words = {"안녕", "안녕하세요", "ㅎㅇ", "hi", "hello", "하이"}
        return query.strip().lower() in greeting_words
    
    def _get_doc_type_template(self, doc_type: str) -> str:
        """
        문서 타입별 답변 템플릿
        """
        templates = {
            "form": """
다운로드 경로: [파일 경로]
필수 항목: [작성해야 할 필수 사항들]
작성 요령: [형식, 길이, 주의사항]
제출 채널: [제출 방법 및 경로]
제출 기한: [기한이 있다면]
문의처: [관련 부서 연락처]
""",
            "terms": """
핵심 요약: [약관의 주요 내용]
예외·주의: [특별히 주의할 점들]
정확 인용: [문서명·섹션·페이지·조항]
시행일: [약관 시행일]
""",
            "product_brochure": """
대상: [상품 이용 대상]
한도: [대출/예금 한도]
금리: [적용 금리]
수수료: [관련 수수료]
필수서류: [신청 시 필요 서류]
주의사항: [중요한 주의점]
버전/시행일: [상품 설명서 버전]
""",
            "regulation": """
조문 요약: [법령의 주요 내용]
해석 포인트: [중요한 해석 사항]
시행일: [법령 시행일]
상위-하위 규정: [관련 법령 관계]
""",
            "manual": """
서비스 개요: [서비스 주요 내용]
이용 방법: [서비스 이용 절차]
주의사항: [이용 시 주의점]
문의처: [서비스 관련 문의처]
"""
        }
        return templates.get(doc_type, "일반 안내: [문서 내용 요약]")
    
    def _expand_forms_query(self, query: str) -> list:
        """
        양식/서식 전용 쿼리 확장
        """
        query_lower = query.lower()
        expanded_queries = [query]
        
        # 양식/서식 별칭 사전
        form_aliases = {
            "위임장": ["위임장 양식", "위임장 서식", "위임장 다운로드", "위임장 제출", "위임장 작성방법"],
            "이의신청서": ["이의신청서 양식", "이의신청서 서식", "이의신청서 제출", "이의신청 사유서", "이의신청 절차"],
            "신청서": ["신청서 양식", "신청서 서식", "신청서 다운로드", "신청서 제출", "신청서 작성방법"],
            "보증서": ["보증서 양식", "보증서 서식", "보증서 다운로드", "보증서 제출"],
            "증명서": ["증명서 양식", "증명서 서식", "증명서 발급", "증명서 신청"],
            "확인서": ["확인서 양식", "확인서 서식", "확인서 발급", "확인서 신청"],
            "동의서": ["동의서 양식", "동의서 서식", "동의서 작성", "동의서 제출"]
        }
        
        # 별칭으로 쿼리 확장
        for original, aliases in form_aliases.items():
            if original in query_lower:
                expanded_queries.extend(aliases)
        
        return expanded_queries
    
    def _classify_doc_type(self, title: str, content: str = "") -> str:
        """
        문서 타입 분류 - form, product_brochure, terms, regulation, faq, manual
        """
        title_lower = title.lower()
        content_lower = content.lower()
        
        # 양식/서식 (form)
        if any(keyword in title_lower for keyword in ["신청서", "해지서", "변경서", "동의서", "위임장", "보증서", "증명서", "확인서", "양식", "서식"]):
            return "form"
        
        # 상품설명서 (product_brochure)
        if any(keyword in title_lower for keyword in ["상품설명서", "상품안내", "상품가이드", "상품소개", "상품"]):
            return "product_brochure"
        
        # 약관/내규 (terms)
        if any(keyword in title_lower for keyword in ["약관", "내규", "규정", "정책", "기본약관", "거래약관"]):
            return "terms"
        
        # 법규/감독규정 (regulation)
        if any(keyword in title_lower for keyword in ["법", "시행령", "감독규정", "법규", "법령"]):
            return "regulation"
        
        # FAQ/공지 (faq)
        if any(keyword in title_lower for keyword in ["faq", "공지", "안내", "문의", "질문", "답변"]):
            return "faq"
        
        # 업무매뉴얼/시스템 (manual)
        if any(keyword in title_lower for keyword in ["매뉴얼", "가이드", "사용법", "시스템", "업무", "절차"]):
            return "manual"
        
        # 기본값
        return "general"
    
    def _get_doc_type_priority(self, intent: str) -> list:
        """
        의도별 우선 문서 타입 리스트
        """
        priority_map = {
            "onboarding": ["form", "terms", "manual", "faq", "regulation", "product_brochure"],
            "bank_general": ["product_brochure", "faq", "terms", "form", "manual", "regulation"],
            "unknown": ["faq", "product_brochure", "terms", "form", "manual", "regulation"]
        }
        return priority_map.get(intent, ["faq", "product_brochure", "terms", "form", "manual", "regulation"])
    
    def _get_answer_template(self, doc_type: str) -> str:
        """
        문서 타입별 답변 템플릿
        """
        templates = {
            "form": """
• 필수 필드: [필수 항목들]
• 작성 규칙: [형식/길이 제한]
• 제출 경로: [제출 방법]
• 다운로드: [링크 또는 위치]
• 주의사항: [특별한 요구사항]
""",
            "product_brochure": """
• 상품 대상: [대상 고객]
• 한도/금리: [수치 정보]
• 수수료: [수수료 구조]
• 필수서류: [제출 서류]
• 예외조건: [주의사항]
• 유의사항: [중요 안내]
""",
            "terms": """
• 핵심 내용: [주요 조항 요약]
• 예외/주의: [특별 규정]
• 유효기간: [시행일/만료일]
• 개정사항: [최근 변경내용]
• 관련조항: [연관 규정]
""",
            "regulation": """
• 법적 근거: [관련 법령]
• 시행일: [효력 발생일]
• 적용범위: [대상/예외]
• 위반시 조치: [제재 내용]
• 최신 개정: [변경사항]
""",
            "faq": """
• 질문 요약: [핵심 내용]
• 답변: [상세 설명]
• 절차: [단계별 안내]
• 관련 문서: [참고 자료]
• 문의처: [담당 부서/연락처]
""",
            "manual": """
• 단계별 절차: [1→2→3 순서]
• 화면 경로: [메뉴 위치]
• 주의사항: [오류 방지]
• 문제해결: [오류코드-해결책]
• 추가 도움: [지원 방법]
"""
        }
        return templates.get(doc_type, """
• 핵심 내용: [주요 정보]
• 상세 설명: [구체적 내용]
• 주의사항: [중요 안내]
• 관련 정보: [추가 자료]
""")

    async def generate_rag_answer(self, question: str) -> Dict:
        """
        RAG 답변 생성 메서드
        """
        try:
            # 유사도 검색으로 관련 문서 찾기
            try:
                similar_docs = await self.similarity_search(question, k=5)
                print(f"RAG 검색 결과: {len(similar_docs)}개 문서 발견")
                
                # 검색 결과가 없으면 키워드 기반 검색 시도
                if not similar_docs:
                    print("키워드 기반 검색 시도...")
                    keywords = self._extract_keywords(question)
                    for keyword in keywords:
                        similar_docs = await self.similarity_search(keyword, k=3)
                        if similar_docs:
                            print(f"키워드 '{keyword}'로 {len(similar_docs)}개 문서 발견")
                            break
                            
            except Exception as e:
                print(f"RAG 검색 오류: {e}")
                similar_docs = []
            
            if not similar_docs:
                # 관련 문서가 없으면 일반 GPT 답변
                print("관련 문서 없음 - 일반 GPT 답변 생성")
                answer = self._call_gpt(f"질문: {question}\n\n은행 업무에 관련된 답변을 해주세요.")
                return {
                    "answer": answer,
                    "sources": [],
                    "response_time": 0.0
                }
            
            # 컨텍스트 구성
            context = "\n\n".join([
                f"[{doc['title']}]\n{doc['content']}"
                for doc in similar_docs
            ])
            
            # RAG 프롬프트
            prompt = f"""
당신은 은행 온보딩 어시스턴트입니다. 🐻

다음 검색 컨텍스트를 기반으로 답변하세요:

{context}

질문: {question}

답변 요구사항:
- 신입사원이 이해하기 쉽게 친절하고 상세하게 답변하세요
- 자연스러운 문단으로 구성하여 길게 설명하세요 (불릿 포인트나 단계별 나열 금지)
- 핵심 정보를 먼저 제시하고, 세부사항을 포함한 완전한 설명을 제공하세요
- 문단과 문단 사이는 자연스럽게 연결하여 흐름 있게 작성하세요
- 한국어로 친근하게 답변하세요 (🐻 이모티콘은 답변 시작에만 사용)
- AI 하리보로서 신입사원을 도와주는 마음으로 답변하세요
- 문서 내용이 있으면 반드시 문서 내용을 우선 활용하고, 문서 내용에 없는 부분만 일반적인 은행 업무 지식으로 보완하세요
- 질문과 관련 없는 내용은 답변에 포함하지 마세요
- 질문의 핵심 키워드와 직접 관련된 내용만 답변하세요
- 문장을 충분히 길게 작성하여 상세한 설명을 제공하세요
- 각 문단은 5-7문장으로 구성하여 충분한 정보를 제공하세요
- 상품 추천 관련 질문에는 구체적인 상품명과 특징을 포함하여 답변하세요
- 연령대별 고객 특성을 고려한 맞춤형 상품 추천을 제공하세요
- 대출 상품의 경우 금리, 한도, 상환조건 등 구체적인 정보를 포함하세요
- 대출 상담 질문에는 실제 대출 상품을 추천하고, 알림 서비스나 기타 서비스는 추천하지 마세요
- 답변을 자연스러운 문단으로 구성하여 길고 상세하게 작성하세요
- 대출 상품 추천 시에는 구체적인 상품명(가계대출, 주택담보대출, 전월세보증금대출 등)을 명시하세요
- 70대 고객에게는 연령대에 맞는 대출 상품을 구체적으로 추천하세요
- 대출 상담 질문에는 반드시 구체적인 대출 상품명을 추천하고, 단계별 설명이나 일반적인 조언은 피하세요
- 고객에게 직접적인 대출 상품 추천을 제공하세요

답변:
"""
            
            answer = self._call_gpt(prompt)
            
            # 참고자료 구성
            sources = [
                {
                    "title": doc["title"],
                    "content": doc["content"][:200] + "..." if len(doc["content"]) > 200 else doc["content"]
                }
                for doc in similar_docs
            ]
            
            # 참고자료를 답변에 추가
            if sources:
                answer += "\n\n참고 자료:\n"
                for source in sources:
                    answer += f"\n• {source['title']}"
            
            return {
                "answer": answer,
                "sources": sources,
                "response_time": 0.0
            }
            
        except Exception as e:
            print(f"Generate RAG answer error: {e}")
            return {
                "answer": "앗, 잠깐만요! 🐻\n일시적인 오류가 발생했어요.\n잠시 후 다시 시도해주세요.",
                "sources": [],
                "response_time": 0.0
            }

    async def process_query(self, question: str) -> Dict:
        """
        쿼리 처리 메인 메서드
        """
        try:
            # RAG 답변 생성
            result = await self.generate_rag_answer(question)
            
            return {
                "answer": result["answer"],
                "sources": result.get("sources", []),
                "response_time": result.get("response_time", 0.0)
            }
            
        except Exception as e:
            print(f"Process query error: {e}")
            return {
                "answer": "앗, 잠깐만요! 🐻\n일시적인 오류가 발생했어요.\n잠시 후 다시 시도해주세요.",
                "sources": [],
                "response_time": 0.0
            }