"""
RAG 서비스 - 완전 수정 버전
"""
import os
import json
import asyncio
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import openai
from app.database import get_session

class RAGService:
    def __init__(self, session: Session):
        self.session = session
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.chunk_size = 1000
        self.chunk_overlap = 200
        self.onboarding_keywords = [
            "온보딩", "신입사원", "교육", "훈련", "가이드", "매뉴얼", "절차", "프로세스"
        ]
        self.stopwords = ["은", "는", "이", "가", "을", "를", "에", "의", "로", "으로", "와", "과", "도", "만", "부터", "까지", "에서", "에게", "한테"]

    async def similarity_search(self, query: str, k: int = 5) -> List[Dict]:
        """유사도 검색 - 신입사원 온보딩용 개선"""
        try:
            print(f"🔍 RAG 검색 시작: {query}")
            
            # 1. 제목 우선 검색 (정확한 매칭)
            title_query = f"""
                SELECT 
                    dc.content,
                    dc.chunk_index,
                    d.title,
                    d.category,
                    d.id as document_id,
                    1.0 as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE d.is_indexed = true AND d.category = 'RAG'
                AND d.title ILIKE :query
                ORDER BY d.upload_date DESC
                LIMIT :k
            """
            
            result = self.session.execute(
                text(title_query), 
                {"query": f"%{query}%", "k": k}
            ).fetchall()
            
            if result:
                print(f"✅ 제목 매칭으로 {len(result)}개 문서 발견")
                return [
                    {
                        "title": row.title,
                        "content": row.content,
                        "similarity": row.similarity,
                        "document_id": row.document_id,
                        "chunk_index": row.chunk_index
                    }
                    for row in result
                ]
            
            # 2. 키워드별 개별 검색
            keywords = self._extract_keywords(query)
            print(f"🔍 키워드 검색: {keywords}")
            
            for keyword in keywords:
                result = self.session.execute(
                    text(title_query), 
                    {"query": f"%{keyword}%", "k": k}
                ).fetchall()
                
                if result:
                    print(f"✅ 키워드 '{keyword}'로 {len(result)}개 문서 발견")
                    return [
                        {
                            "title": row.title,
                            "content": row.content,
                            "similarity": row.similarity,
                            "document_id": row.document_id,
                            "chunk_index": row.chunk_index
                        }
                        for row in result
                    ]
            
            # 3. 추가 키워드 검색 (대출 관련)
            if any(word in query.lower() for word in ["대출", "상품", "추천", "상담"]):
                loan_keywords = ["가계대출", "주택담보대출", "전월세보증금대출", "개인대출", "신용대출"]
                for loan_keyword in loan_keywords:
                    result = self.session.execute(
                        text(title_query), 
                        {"query": f"%{loan_keyword}%", "k": k}
                    ).fetchall()
                    
                    if result:
                        print(f"✅ 대출 키워드 '{loan_keyword}'로 {len(result)}개 문서 발견")
                        return [
                            {
                                "title": row.title,
                                "content": row.content,
                                "similarity": row.similarity,
                                "document_id": row.document_id,
                                "chunk_index": row.chunk_index
                            }
                            for row in result
                        ]
            
            # 4. 내용 기반 검색 (마지막 시도)
            content_query = f"""
                SELECT 
                    dc.content,
                    dc.chunk_index,
                    d.title,
                    d.category,
                    d.id as document_id,
                    0.8 as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE d.is_indexed = true AND d.category = 'RAG'
                AND dc.content ILIKE :query
                ORDER BY d.upload_date DESC
                LIMIT :k
            """
            
            result = self.session.execute(
                text(content_query), 
                {"query": f"%{query}%", "k": k}
            ).fetchall()
            
            if result:
                print(f"✅ 내용 검색으로 {len(result)}개 문서 발견")
                return [
                    {
                        "title": row.title,
                    "content": row.content,
                        "similarity": row.similarity,
                        "document_id": row.document_id,
                        "chunk_index": row.chunk_index
                    }
                    for row in result
                ]
            
            print(f"❌ 검색 결과 없음: {query}")
            return []
            
        except Exception as e:
            print(f"❌ RAG 검색 오류: {e}")
            return []

    def _extract_keywords(self, question: str) -> List[str]:
        """질문에서 키워드 추출 - 신입사원 온보딩용"""
        # 신입사원이 자주 묻는 키워드들
        onboarding_keywords = {
            "대출": ["대출", "가계대출", "주택담보대출", "전월세보증금대출", "기업대출", "대환대출", "신용대출"],
            "상품": ["상품", "상품설명서", "상품안내"],
            "고객": ["고객", "70대", "연령", "나이"],
            "추천": ["추천", "상담", "문의"],
            "금리": ["금리", "이자", "수수료"],
            "약관": ["약관", "기본약관", "특약", "이용약관"],
            "양식": ["양식", "서식", "신청서", "위임장", "확인서", "해촉증명서", "이의신청서"],
            "증명서": ["증명서", "해촉증명서", "소득증명서", "재직증명서"],
            "신청서": ["신청서", "이의신청서", "대출신청서", "계좌신청서", "피해구제신청서"],
            "약정서": ["약정서", "신용보증약정서", "대출약정서", "대출거래약정서"],
            "동의서": ["동의서", "개인정보동의서", "제3자제공동의서", "개인정보수집동의서"],
            "안내": ["안내", "고객권리안내문", "대출만기안내", "대출만기경과안내"],
            "상황표": ["상황표", "수신거래상황표", "여신거래상황표"],
            "계좌": ["계좌", "증권계좌", "계좌개설", "증권계좌개설", "계좌신청", "계좌통합관리"],
            "증권": ["증권", "증권계좌", "증권계좌개설", "증권서비스", "증권계좌개설서비스"],
            "예금": ["예금", "입출금이자유로운예금", "적립식예금", "거치식예금", "외화예금"],
            "전자금융": ["전자금융", "전자금융거래", "모바일뱅킹", "이체한도", "오픈뱅킹"],
            "보이스피싱": ["보이스피싱", "피해구제", "전기통신금융사기", "피해구제신청서"],
            "신용보증": ["신용보증", "신용보증약정서", "신용보증서", "보증채무이행청구서"],
            "체크카드": ["체크카드", "교통카드", "후불교통카드"],
            "모임통장": ["모임통장", "모임통장서비스"],
            "햇살론": ["햇살론", "햇살론뱅크"],
            "전세지킴": ["전세지킴", "전세지킴보증약관"]
        }
        
        keywords = []
        question_lower = question.lower()
        
        # 질문에서 키워드 찾기
        for category, words in onboarding_keywords.items():
            for word in words:
                if word in question_lower:
                    keywords.extend(words)
                    break
        
        # 중복 제거하고 상위 8개만 반환 (더 많은 키워드로 검색)
        unique_keywords = list(set(keywords))
        print(f"🔍 추출된 키워드: {unique_keywords}")
        return unique_keywords[:8]
    
    def _call_gpt(self, prompt: str) -> str:
        """GPT API 직접 호출"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "당신은 은행 온보딩 어시스턴트입니다. 🐻"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0.7
            }
            
            import requests
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                print(f"OpenAI API error: {response.status_code} - {response.text}")
                return "죄송합니다. 일시적인 오류가 발생했습니다."
                
        except Exception as e:
            print(f"GPT API call error: {e}")
            return "죄송합니다. 일시적인 오류가 발생했습니다."

    async def generate_rag_answer(self, question: str) -> Dict:
        """RAG 답변 생성 메서드 - 완전 수정"""
        try:
            # 유사도 검색으로 관련 문서 찾기
            similar_docs = await self.similarity_search(question, k=5)
            print(f"RAG 검색 결과: {len(similar_docs)}개 문서 발견")
            
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
            
            # AI 하리보 신입사원 온보딩 프롬프트
            prompt = f"""
당신은 AI 하리보입니다. 🐻 신입사원 온보딩을 도와주는 친근한 은행 어시스턴트예요.

다음 검색 컨텍스트를 기반으로 답변하세요:

{context}

질문: {question}

🎯 AI 하리보 답변 가이드라인:
- **신입사원이 고객 상담할 때 바로 활용할 수 있는 실무 정보를 제공하세요**
- **신입사원에게 조언하는 톤으로 답변하세요 (고객에게 직접 말하는 톤이 아님)**
- 자연스러운 문단으로 구성하여 길고 상세하게 설명하세요 (불릿 포인트나 단계별 나열 금지)
- 핵심 정보를 먼저 제시하고, 세부사항을 포함한 완전한 설명을 제공하세요
- 문단과 문단 사이는 자연스럽게 연결하여 흐름 있게 작성하세요
- 한국어로 친근하게 답변하세요 (🐻 이모티콘은 답변 시작에만 사용)
- AI 하리보로서 신입사원을 도와주는 마음으로 답변하세요
- 문서 내용이 있으면 반드시 문서 내용을 우선 활용하고, 문서 내용에 없는 부분만 일반적인 은행 업무 지식으로 보완하세요
- 질문과 관련 없는 내용은 답변에 포함하지 마세요
- 질문의 핵심 키워드와 직접 관련된 내용만 답변하세요
- 문장을 충분히 길게 작성하여 상세한 설명을 제공하세요
- 각 문단은 5-7문장으로 구성하여 충분한 정보를 제공하세요

🏦 상품 추천 관련 질문:
- 구체적인 상품명과 특징을 포함하여 답변하세요
- 연령대별 고객 특성을 고려한 맞춤형 상품 추천을 제공하세요
- 대출 상품의 경우 금리, 한도, 상환조건 등 구체적인 정보를 포함하세요
- 대출 상담 질문에는 실제 대출 상품을 추천하고, 알림 서비스나 기타 서비스는 추천하지 마세요
- 대출 상품 추천 시에는 구체적인 상품명(가계대출, 주택담보대출, 전월세보증금대출 등)을 명시하세요

🚨 **70대 고객 대출 상담 시 필수 규칙:**
- **반드시 개인 대출 상품만 추천: 가계대출, 주택담보대출, 전월세보증금대출, 개인대출, 신용대출**
- **절대 금지: 기업대출, 사장님대환대출, 모바일우대보증대출, 사업자대출, 보증대출, 햇살론 등 모든 기업/사업자용 상품**
- **70대 = 개인 고객으로 간주하고 개인 대출 상품만 추천**
- **사업 운영 여부와 관계없이 70대 고객에게는 개인 대출 상품만 추천**
- **70대 고객에게는 가계대출을 우선적으로 추천하고, 상세한 특징과 장점을 설명하세요**

- 대출 상담 질문에는 반드시 구체적인 개인 대출 상품명을 추천하고, 단계별 설명이나 일반적인 조언은 피하세요
- 고객에게 직접적인 개인 대출 상품 추천을 제공하세요

📋 양식/서류 관련 질문:
- 해촉증명서, 이의신청서, 위임장 등 구체적인 양식명을 명시하세요
- 신청 절차와 필요한 서류를 상세히 안내하세요
- 신입사원이 고객에게 설명할 수 있는 수준으로 작성하세요

⚠️ 주의사항:
- 고객센터 전화번호나 연락처는 절대 포함하지 마세요
- 신입사원이 고객 상담 시 참고할 수 있는 실무 정보를 제공하세요
- 질문과 관련 없는 상품(예: 아이 통장을 노인 대출 상담에서 언급)은 절대 추천하지 마세요
- **중요: 답변에서 "토스뱅크"라는 단어가 나오면 반드시 "하경은행"으로 바꿔서 답변하세요**

답변:
"""
            
            answer = self._call_gpt(prompt)
            
            # 토스뱅크를 하경은행으로 변경
            answer = answer.replace("토스뱅크", "하경은행")
            
            # 참고자료 구성 - 임시로 모든 문서 포함 (디버깅용)
            sources = []
            for doc in similar_docs:
                sources.append({
                    "title": doc["title"],
                    "content": doc["content"][:200] + "..." if len(doc["content"]) > 200 else doc["content"]
                })
            
            # 참고자료를 답변에 추가 (중복 제거)
            if sources:
                # 중복 제거 (title 기준)
                unique_sources = []
                seen_titles = set()
                for source in sources:
                    if source['title'] not in seen_titles:
                        unique_sources.append(source)
                        seen_titles.add(source['title'])
                
                if unique_sources:
                    answer += "\n\n참고 자료:\n"
                    for source in unique_sources:
                        answer += f"\n• {source['title']}"
                
                # sources를 unique_sources로 업데이트
                sources = unique_sources
            
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
        """쿼리 처리 메인 메서드"""
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
