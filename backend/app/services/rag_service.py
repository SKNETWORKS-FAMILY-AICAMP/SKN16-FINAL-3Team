"""
RAG 서비스 (벡터 검색 + LLM 선택)
"""
from __future__ import annotations

import json
import time
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, text, or_
from sqlmodel import Session

from pgvector.sqlalchemy import Vector

from app.models import ChatHistory
from app.models.post import Post
from app.models.rag_simulation import RAGSimulationEvaluation, RAGSimulationSession
from sqlmodel import select, func
from .embedding_service import embed_text
from .llm_service import LLMService
from .content_filter_service import ContentFilterService, FilterResult


class RAGService:
    """벡터 검색 기반 RAG 서비스"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.llm_service = LLMService(session)
        self.content_filter = ContentFilterService()
        self._greeting_variants = {
            "안녕",
            "안녕하세요",
            "하이",
            "ㅎㅇ",
            "hello",
            "hi",
            "헬로",
            "안녕하십니까",
            "안녕하시렵니까",
            "안녕하신가",
            "안녕들하십니까",
        }
        self._similarity_threshold = 0.35
    
    def _is_list_query(self, query: str) -> bool:
        """목록형 질문인지 확인 (여러 항목을 묻는 질문)"""
        query_lower = query.lower()
        list_patterns = [
            '뭐있어', '뭐 있어', '뭐뭐', '뭐가', '무엇이', '무엇',
            '어떤', '어떤게', '어떤거', '어떤 것',
            '종류', '목록', '리스트', 
            '전부', '전체', '모두', '다',
            '몇개', '몇 개', '얼마나',
            '있나', '있는지', '있니',
            '알려줘', '알려', '소개', '설명',  # 추가
        ]
        return any(pattern in query_lower for pattern in list_patterns)

    # --- 검색 ---
    async def search_posts(
        self, query: str, top_k: Optional[int] = None
    ) -> List[Dict]:
        """동아리 라운지 게시물 검색"""
        config = self.llm_service.get_config_dict()
        
        # 목록형 질문이면 더 많은 게시물 가져오기
        if top_k is None:
            k = 15 if self._is_list_query(query) else 5
        else:
            k = top_k
        
        print(f"🔍 [게시물 검색] 쿼리: '{query}', 목록형: {self._is_list_query(query)}, 가져올 개수: {k}")
        
        # 쿼리에서 핵심 키워드 추출 (불용어 제거)
        import re
        stopwords = ['뭐', '뭐뭐', '있어', '있나', '있는지', '어떤', '무엇', '어떤게', '어떤거',
                     '알려', '알려줘', '설명', '소개', '종류', '목록', '리스트', '해줘', '?', '!']
        
        keywords = []
        for word in query.split():
            # 특수문자 제거
            word = re.sub(r'[?!.,]', '', word).strip()
            if word and word not in stopwords and len(word) > 1:
                keywords.append(word)
        
        # 키워드가 없으면 원래 쿼리에서 특수문자만 제거
        if keywords:
            search_term = ' '.join(keywords)
        else:
            # 키워드가 하나도 없으면 전체 검색 (불용어만 있는 경우)
            # 예: "뭐있어?" → 전체 게시물 검색
            search_term = query.lower()
            for sw in stopwords:
                search_term = search_term.replace(sw, '')
            search_term = re.sub(r'[?!.,\s]+', '', search_term).strip()
            if not search_term:
                # 완전히 비어있으면 전체 검색
                search_term = ""
        
        print(f"🔍 [키워드 추출] 원본: '{query}' → 검색어: '{search_term}'")
        
        query_pattern = f"%{search_term}%" if search_term else "%"
        
        statement = (
            select(Post)
            .where(
                Post.is_deleted == False,
                or_(
                    Post.title.ilike(query_pattern),
                    Post.content.ilike(query_pattern)
                )
            )
            .order_by(Post.created_at.desc())
            .limit(k)
        )
        
        posts = list(self.session.exec(statement).all())
        
        print(f"📊 [게시물 검색] 검색어: '{search_term}', 결과: {len(posts)}개")
        if posts:
            for idx, post in enumerate(posts, 1):
                print(f"  {idx}. {post.title} (카테고리: {post.category})")
        else:
            print(f"⚠️ [게시물 검색] 검색어 '{search_term}'에 해당하는 게시물이 없습니다.")
            # 전체 게시물 개수 확인
            total_statement = select(Post).where(Post.is_deleted == False)
            total_posts = list(self.session.exec(total_statement).all())
            print(f"ℹ️ [게시물 검색] DB에 총 {len(total_posts)}개의 게시물이 있습니다.")
            if total_posts and len(total_posts) <= 10:
                print(f"ℹ️ [전체 게시물 목록]")
                for idx, p in enumerate(total_posts, 1):
                    print(f"  {idx}. {p.title} (카테고리: {p.category})")
        
        results: List[Dict] = []
        for post in posts:
            # 게시물 내용을 청크로 처리 (전체 내용 사용)
            content = f"제목: {post.title}\n카테고리: {post.category}"
            if post.subcategory:
                content += f" / {post.subcategory}"
            content += f"\n내용: {post.content}"
            
            # 유사도 계산 (키워드 매칭 기반)
            title_lower = post.title.lower()
            content_lower = post.content.lower()
            
            # 검색어 키워드가 제목이나 내용에 포함되는지 확인
            keyword_matches = 0
            for keyword in keywords if keywords else [query.lower()]:
                if keyword in title_lower:
                    keyword_matches += 2  # 제목 매칭은 가중치 2배
                elif keyword in content_lower:
                    keyword_matches += 1
            
            # 유사도 점수 계산
            if keyword_matches >= 2:
                similarity = 0.9
            elif keyword_matches == 1:
                similarity = 0.7
            else:
                similarity = 0.5
            
            results.append({
                "id": f"post_{post.id}",
                "content": content,
                "chunk_index": 0,
                "document_id": post.id,
                "title": f"[동아리 라운지] {post.title}",
                "category": f"게시판/{post.category}",
                "description": f"동아리 라운지 게시물 - {post.category} 카테고리",
                "file_path": f"/posts/{post.id}",
                "metadata": {
                    "post_id": post.id,
                    "post_category": post.category,
                    "post_subcategory": post.subcategory,
                    "view_count": post.view_count,
                    "comment_count": post.comment_count,
                },
                "similarity": similarity,
            })
        
        return results
    
    async def similarity_search(
        self, query: str, top_k: Optional[int] = None
    ) -> List[Dict]:
        config = self.llm_service.get_config_dict()
        k = top_k or config["top_k"] or 6

        query_vector = await embed_text(query)

        sql = text(
            """
                SELECT 
                dc.id,
                    dc.content,
                    dc.chunk_index,
                dc.chunk_metadata,
                d.id AS document_id,
                    d.title,
                    d.category,
                d.description,
                d.file_path,
                1 - (dc.embedding <=> :query_embedding) AS similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> :query_embedding
                LIMIT :k
            """
        )
            
        sql = sql.bindparams(bindparam("query_embedding", type_=Vector(1536)))
        rows = self.session.execute(
            sql, {"query_embedding": query_vector, "k": k}
            ).fetchall()
            
        results: List[Dict] = []
        for row in rows:
            metadata = None
            if row.chunk_metadata:
                try:
                    metadata = json.loads(row.chunk_metadata)
                except json.JSONDecodeError:
                    metadata = None

            results.append(
                {
                    "id": row.id,
                    "content": row.content,
                    "chunk_index": row.chunk_index,
                        "document_id": row.document_id,
                    "title": row.title,
                    "category": row.category,
                    "description": row.description,
                    "file_path": row.file_path,
                    "metadata": metadata,
                    "similarity": float(row.similarity),
                }
            )
        return results
    
    async def hybrid_search(
        self, query: str, top_k: Optional[int] = None, original_query: Optional[str] = None
    ) -> List[Dict]:
        """하이브리드 검색: 문서 + 게시물
        
        Args:
            query: 문서 검색용 쿼리 (확장된 쿼리일 수 있음)
            top_k: 반환할 결과 수
            original_query: 게시물 검색용 원본 쿼리 (쿼리 확장이 있을 때 사용)
        """
        # 문서 검색 (확장된 쿼리 사용)
        doc_results = await self.similarity_search(query, top_k)
        
        # 게시물 검색 (원본 쿼리 사용 - 확장되지 않은 사용자 입력)
        post_query = original_query if original_query else query
        post_results = await self.search_posts(post_query, top_k=3)
        
        # 결과 병합 및 정렬
        all_results = doc_results + post_results
        all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        
        # 상위 k개만 반환
        config = self.llm_service.get_config_dict()
        k = top_k or config["top_k"] or 6
        return all_results[:k]

    # --- 프롬프트 구성 ---
    def _build_system_prompt(self, config: Dict[str, Any]) -> str:
        prompt_parts = [
            "당신은 하경은행 신입 행원을 돕는 RAG 챗봇 AI 하리보입니다. 🐻",
            "항상 한국어로 답변하고, **제공된 컨텍스트를 최우선으로 활용**하세요.",
            "",
            "[최우선 규칙]",
            "**컨텍스트에 관련 정보가 있으면 반드시 그것을 사용하여 답변합니다.**",
            "- 동아리, 모임, 활동에 대한 질문이고 컨텍스트에 게시물이 있으면 → 게시물 내용을 바탕으로 답변",
            "- 은행 업무, 상품, 법규에 대한 질문이고 컨텍스트에 문서가 있으면 → 문서 내용을 바탕으로 답변",
            "- 컨텍스트에 근거가 없거나 정보가 부족할 때만 '추가 확인 필요'라고 명시",
            "",
            "[답변 가능 범위]",
            "다음 주제에 대해 답변할 수 있습니다:",
            "• 은행 업무 (대출, 예금, 계좌, 카드, 상품 등)",
            "• 동아리, 라운지, 모임, 활동 관련 정보",
            "• 은행 규정, 정책, 매뉴얼",
            "• 일정 관리 정보",
            "",
            "[거절 규칙]",
            "다음 경우에만 답변을 거절합니다:",
            "1. 컨텍스트에 정보가 전혀 없고",
            "2. 업무와 무관한 주제 (날씨, 주식, 운세 등)일 때",
            "",
            "**중요: '동아리', '모임', '활동'에 대한 질문은 업무 관련 질문입니다. 컨텍스트에 정보가 있으면 반드시 답변하세요!**",
        ]

        if config.get("response_style") == "structured":
            prompt_parts.append(
                "답변은 제목과 불릿/번호 목록을 포함한 구조화된 형식으로 작성하세요."
            )
        else:
            prompt_parts.append(
                "답변은 자연스러운 문단 형태로 작성하되, 문단마다 하나의 핵심 메시지에 집중하세요."
            )

        if config.get("verbosity") == "concise":
            prompt_parts.append(
                "핵심 정보 위주로 2~3개의 짧은 문단 또는 목록으로 요약하고, 군더더기 표현은 피하세요."
            )
        else:
            prompt_parts.append(
                "필요하다면 배경 설명, 주의사항, 예시를 포함해 상세하게 안내하세요."
            )

        prompt_parts.append(
            "고객 응대 시 도움이 되는 실무 팁이나 후속 조치가 있다면 '실무 메모' 섹션으로 정리하세요."
        )
        prompt_parts.append('\'토스뱅크\'라는 표현이 등장하면 반드시 \'하경은행\'으로 바꿔 말하세요.')

        return "\n".join(prompt_parts)

    def _format_context(self, documents: List[Dict]) -> str:
        blocks: List[str] = []
        for idx, doc in enumerate(documents, start=1):
            header = f"[자료 {idx}] {doc['title']}"
            if doc.get("metadata"):
                meta = doc["metadata"]
                law = meta.get("law_name")
                article = meta.get("article_title")
                breadcrumb = meta.get("breadcrumb")
                summary_parts = [
                    part
                    for part in [law, article, breadcrumb]
                    if isinstance(part, str) and part.strip()
                ]
                if summary_parts:
                    header += " · " + " > ".join(summary_parts[:2])

            block = f"{header}\n{doc['content']}"
            blocks.append(block.strip())
        return "\n\n".join(blocks)

    def _build_user_prompt(
        self, question: str, documents: List[Dict], config: Dict[str, Any]
    ) -> str:
        context = self._format_context(documents)
        style_hint = (
            "주요 항목별로 제목과 불릿 목록을 사용해 구조화하세요."
            if config.get("response_style") == "structured"
            else "자연스러운 문단 흐름으로 설명하되 핵심을 명확히 하세요."
        )
        verbosity_hint = (
            "불필요한 수식어 없이 핵심 정보만 담으세요."
            if config.get("verbosity") == "concise"
            else "필요한 경우 배경 설명과 예시를 덧붙이세요."
        )
        return (
            f"질문:\n{question.strip()}\n\n"
            "참고 자료:\n"
            f"{context}\n\n"
            "답변 지침:\n"
            f"- {style_hint}\n"
            f"- {verbosity_hint}\n"
            "- 컨텍스트와 질문에 근거한 정보만 제공하고, 근거가 없으면 '추가 확인 필요'라고 명시하세요.\n"
            "- 신입 행원이 고객에게 안내할 때 바로 활용할 수 있는 실무 단계나 체크포인트를 포함하세요."
        )

    def _summarize_sources(self, documents: List[Dict]) -> List[Dict]:
        sources: List[Dict] = []
        for doc in documents:
            sources.append(
                {
                    "title": doc["title"],
                    "document_id": doc["document_id"],
                    "chunk_index": doc["chunk_index"],
                    "similarity": round(doc["similarity"], 4),
                    "metadata": doc.get("metadata"),
                }
            )
        return sources

    def _is_simple_greeting(self, text: str) -> bool:
        normalized = re.sub(r"[\s\W_]+", "", text.lower())
        return any(normalized.startswith(variant) for variant in self._greeting_variants)

    def _filter_relevant_documents(self, documents: List[Dict]) -> List[Dict]:
        return [
            doc
            for doc in documents
            if isinstance(doc.get("similarity"), (float, int))
            and doc["similarity"] >= self._similarity_threshold
        ]

    def _is_simulation_report_query(self, question: str) -> bool:
        """시뮬레이션 리포트 관련 질문인지 확인"""
        question_lower = question.lower()
        keywords = [
            "시뮬레이션", "보고서", "리포트", "평가", "성적", "점수", 
            "약점", "weak point", "weakpoint", "개선점", "부족한",
            "내 성적", "나의 성적", "내 점수", "나의 점수",
            "평균", "수준", "등급"
        ]
        return any(keyword in question_lower for keyword in keywords)

    def get_user_simulation_scores(self, user_id: int) -> Optional[Dict]:
        """사용자의 시뮬레이션 평가 성적 조회 및 통계"""
        if not user_id:
            return None
        
        try:
            # 사용자의 모든 평가 결과 조회
            evaluations = self.session.exec(
                select(RAGSimulationEvaluation)
                .where(RAGSimulationEvaluation.user_id == user_id)
                .order_by(RAGSimulationEvaluation.created_at.desc())
            ).all()
            
            if not evaluations:
                return None
            
            # 통계 계산
            total_count = len(evaluations)
            
            # 평균 점수 계산
            avg_scores = {
                "knowledge": sum(e.knowledge_point for e in evaluations) / total_count,
                "skill": sum(e.skill_point for e in evaluations) / total_count,
                "empathy": sum(e.empathy_point for e in evaluations) / total_count,
                "clarity": sum(e.clarity_point for e in evaluations) / total_count,
                "kindness": sum(e.kindness_point for e in evaluations) / total_count,
                "confidence": sum(e.confidence_point for e in evaluations) / total_count,
                "total": sum(e.total_point for e in evaluations) / total_count,
            }
            
            # 최신 평가 결과
            latest = evaluations[0]
            latest_scores = {
                "knowledge": latest.knowledge_point,
                "skill": latest.skill_point,
                "empathy": latest.empathy_point,
                "clarity": latest.clarity_point,
                "kindness": latest.kindness_point,
                "confidence": latest.confidence_point,
                "total": latest.total_point,
                "grade": latest.grade,
            }
            
            # 약점 찾기 (평균이 낮은 순서)
            weak_points = sorted(
                [
                    {"metric": "knowledge", "score": avg_scores["knowledge"], "name": "지식"},
                    {"metric": "skill", "score": avg_scores["skill"], "name": "기술"},
                    {"metric": "empathy", "score": avg_scores["empathy"], "name": "공감도"},
                    {"metric": "clarity", "score": avg_scores["clarity"], "name": "명확성"},
                    {"metric": "kindness", "score": avg_scores["kindness"], "name": "친절도"},
                    {"metric": "confidence", "score": avg_scores["confidence"], "name": "자신감"},
                ],
                key=lambda x: x["score"]
            )[:3]  # 상위 3개 약점
            
            # 각 평가 결과 상세 정보
            evaluation_details = []
            for eval_obj in evaluations[:5]:  # 최근 5개만
                session_info = self.session.get(RAGSimulationSession, eval_obj.session_id)
                detail_json = json.loads(eval_obj.detail_json) if eval_obj.detail_json else {}
                
                evaluation_details.append({
                    "evaluation_id": eval_obj.id,
                    "session_key": session_info.session_key if session_info else None,
                    "scenario_title": session_info.scenario_title if session_info else None,
                    "total_score": eval_obj.total_point,
                    "grade": eval_obj.grade,
                    "scores": {
                        "knowledge": eval_obj.knowledge_point,
                        "skill": eval_obj.skill_point,
                        "empathy": eval_obj.empathy_point,
                        "clarity": eval_obj.clarity_point,
                        "kindness": eval_obj.kindness_point,
                        "confidence": eval_obj.confidence_point,
                    },
                    "reasons": {
                        "knowledge": eval_obj.knowledge_reason,
                        "skill": eval_obj.skill_reason,
                        "empathy": eval_obj.empathy_reason,
                        "clarity": eval_obj.clarity_reason,
                        "kindness": eval_obj.kindness_reason,
                        "confidence": eval_obj.confidence_reason,
                    },
                    "feedback_summary": eval_obj.feedback_summary,
                    "detail_json": detail_json,
                    "created_at": eval_obj.created_at.isoformat(),
                })
            
            return {
                "total_evaluations": total_count,
                "average_scores": avg_scores,
                "latest_scores": latest_scores,
                "weak_points": weak_points,
                "evaluation_history": evaluation_details,
            }
        except Exception as e:
            print(f"사용자 성적 조회 오류: {e}")
            return None

    def _build_general_system_prompt(self, config: Dict[str, Any]) -> str:
        base_prompt = [
            "당신은 하경은행 신입 행원을 돕는 AI 하리보입니다. 🐻",
            "",
            "[응답 규칙]",
            "1. 업무 관련 질문만 답변합니다.",
            "2. 부적절한 질문이나 욕설이 포함된 경우 정중하게 거절합니다.",
            "3. 범위 밖 질문은 '업무 관련 질문만 답변 가능합니다'라고 안내합니다.",
            "4. 인사말에는 자연스럽고 간결하게 응답하되, 업무 범위를 벗어나지 않습니다.",
        ]
        if config.get("verbosity") == "detailed":
            base_prompt.append("상대의 의도를 파악해 부드러운 설명과 제안을 덧붙이되 장황하지 않게 정리하세요.")
        else:
            base_prompt.append("핵심 메시지를 한두 문장으로 명확하게 전달하세요.")
        return "\n".join(base_prompt)

    async def _generate_general_response(
        self, question: str, config: Dict[str, Any], user_id: Optional[int], start_time: float
    ) -> Dict:
        system_prompt = self._build_general_system_prompt(config)
        llm_response = await self.llm_service.generate_response(
            system_prompt=system_prompt,
            user_prompt=question.strip(),
        )
        response_time = time.time() - start_time

        if user_id:
            history = ChatHistory(
                user_id=user_id,
                user_message=question,
                bot_response=llm_response.content,
                source_documents="[]",
                response_time=response_time,
            )
            self.session.add(history)
            self.session.commit()

        return {
            "answer": llm_response.content,
            "sources": [],
            "response_time": round(response_time, 2),
            "model": llm_response.model,
            "provider": llm_response.provider,
        }

    # --- 메인 프로세스 ---
    async def process_query(
        self, question: str, *, user_id: Optional[int] = None
    ) -> Dict:
        start = time.time()
        config = self.llm_service.get_config_dict()
        
        # 1. 내용 필터링 (부적절한 질문/욕설 차단)
        filter_result, reject_message = self.content_filter.filter_content(question)
        
        if filter_result in [FilterResult.PRIVACY_VIOLATION, FilterResult.PROFANITY, FilterResult.OFF_TOPIC]:
            # 개인정보 침해, 욕설, 업무 범위 밖 질문 차단
            response_time = time.time() - start
            if user_id:
                history = ChatHistory(
                    user_id=user_id,
                    user_message=question,
                    bot_response=reject_message,
                    source_documents=json.dumps([], ensure_ascii=False),
                    response_time=response_time,
                )
                self.session.add(history)
                self.session.commit()
            
            return {
                "answer": reject_message,
                "sources": [],
                "response_time": round(response_time, 2),
                "model": "content_filter",
                "provider": "internal",
            }

        if self._is_simple_greeting(question):
            if config.get("verbosity") == "detailed":
                answer = (
                    "안녕하세요! 하경은행 상담 준비를 돕는 AI 하리보입니다. "
                    "어떤 업무를 도와드릴까요?"
                )
            else:
                answer = "안녕하세요! 무엇을 도와드릴까요?"

            provider = config.get("selected_model")
            model_name = (
                config.get("openai_model")
                if provider == "openai"
                else config.get("qwen_model")
            )

            response_time = time.time() - start
            if user_id:
                history = ChatHistory(
                    user_id=user_id,
                    user_message=question,
                    bot_response=answer,
                    source_documents=json.dumps([], ensure_ascii=False),
                    response_time=response_time,
                )
                self.session.add(history)
                self.session.commit()

            return {
                "answer": answer,
                "sources": [],
                "response_time": round(response_time, 2),
                "model": model_name,
                "provider": provider,
            }

        # 시뮬레이션 리포트 관련 질문인지 확인
        if self._is_simulation_report_query(question) and user_id:
            user_scores = self.get_user_simulation_scores(user_id)
            if user_scores:
                # 사용자 성적 데이터가 있으면 분석
                return await self._generate_simulation_report_analysis(
                    question=question,
                    user_scores=user_scores,
                    config=config,
                    user_id=user_id,
                    start_time=start,
                )

        # 동아리/라운지 관련 질문 감지
        question_lower = question.lower()
        
        # 동아리 라운지 관련 키워드 확인
        club_keywords = ["동아리", "클럽", "모임", "동호회", "라운지", "게시판", "게시물"]
        has_club_keyword = any(kw in question_lower for kw in club_keywords)
        
        # 동아리 관련 질문이면 게시물만 검색 (문서 검색 제외)
        if has_club_keyword:
            # 게시물만 검색
            documents = await self.search_posts(question, top_k=5)
            if documents:
                relevant_documents = documents  # 게시물은 이미 관련성 있음
            else:
                # 게시물이 없으면 일반 검색으로 fallback
                documents = await self.hybrid_search(question)
                relevant_documents = self._filter_relevant_documents(documents)
        else:
            # 일반 질문: 하이브리드 검색 (문서 + 게시물)
            documents = await self.hybrid_search(question)
            relevant_documents = self._filter_relevant_documents(documents)

        if not relevant_documents:
            return await self._generate_general_response(
                question=question,
                config=config,
                user_id=user_id,
                start_time=start,
            )

        user_prompt = self._build_user_prompt(question, relevant_documents, config)
        system_prompt = self._build_system_prompt(config)

        llm_response = await self.llm_service.generate_response(
            system_prompt=system_prompt, user_prompt=user_prompt
        )

        response_time = time.time() - start
        sources = self._summarize_sources(relevant_documents)

        if user_id:
            history = ChatHistory(
                user_id=user_id,
                user_message=question,
                bot_response=llm_response.content,
                source_documents=json.dumps(sources, ensure_ascii=False),
                response_time=response_time,
            )
            self.session.add(history)
            self.session.commit()

        return {
            "answer": llm_response.content,
            "sources": sources,
            "response_time": round(response_time, 2),
            "model": llm_response.model,
            "provider": llm_response.provider,
        }

    async def _generate_simulation_report_analysis(
        self,
        question: str,
        user_scores: Dict,
        config: Dict[str, Any],
        user_id: int,
        start_time: float,
    ) -> Dict:
        """시뮬레이션 리포트 분석 답변 생성"""
        # 시뮬레이션 리포트 관련 문서 검색
        documents = await self.similarity_search(question, top_k=3)
        relevant_documents = self._filter_relevant_documents(documents)
        
        # 사용자 성적 요약 생성
        avg_scores = user_scores["average_scores"]
        latest_scores = user_scores["latest_scores"]
        weak_points = user_scores["weak_points"]
        total_count = user_scores["total_evaluations"]
        
        scores_summary = f"""
**평균 성적 (총 {total_count}회 평가):**
- 지식: {avg_scores['knowledge']:.1f}점
- 기술: {avg_scores['skill']:.1f}점
- 공감도: {avg_scores['empathy']:.1f}점
- 명확성: {avg_scores['clarity']:.1f}점
- 친절도: {avg_scores['kindness']:.1f}점
- 자신감: {avg_scores['confidence']:.1f}점
- 총점: {avg_scores['total']:.1f}점

**최신 성적:**
- 총점: {latest_scores['total']}점 (등급: {latest_scores['grade']})

**주요 약점 (평균 점수 기준):**
"""
        for wp in weak_points:
            scores_summary += f"- {wp['name']}: {wp['score']:.1f}점\n"
        
        # 최신 평가의 약점 이유
        if user_scores["evaluation_history"]:
            latest_detail = user_scores["evaluation_history"][0]
            reasons_summary = "\n**최신 평가에서 지적된 개선점:**\n"
            for wp in weak_points:
                metric = wp["metric"]
                reason = latest_detail["reasons"].get(metric)
                if reason:
                    reasons_summary += f"- {wp['name']}: {reason}\n"
            scores_summary += reasons_summary
        
        # LLM 프롬프트 구성
        context_text = ""
        if relevant_documents:
            context_text = self._format_context(relevant_documents)
        
        system_prompt = """당신은 하경은행 신입 행원을 돕는 AI 하리보입니다. 
사용자의 시뮬레이션 평가 성적을 분석하고 약점(weak point)을 찾아 개선 방안을 제시해주세요.
친절하고 격려하는 톤으로 답변하며, 구체적이고 실행 가능한 조언을 제공하세요."""

        user_prompt = f"""질문: {question}

**사용자의 시뮬레이션 평가 성적:**
{scores_summary}

**참고 자료:**
{context_text if context_text else "시뮬레이션 평가 기준 및 개선 방안에 대한 일반적인 가이드라인을 참고하세요."}

위 성적 데이터를 바탕으로 다음을 포함하여 답변해주세요:
1. 주요 약점(weak point) 분석
2. 각 약점에 대한 구체적인 개선 방안
3. 추천 학습 자료나 연습 방법
4. 격려의 메시지

답변은 한국어로 작성하고, 구조화된 형식(제목, 불릿 포인트 등)을 사용하세요."""

        llm_response = await self.llm_service.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        
        response_time = time.time() - start_time
        sources = self._summarize_sources(relevant_documents) if relevant_documents else []
        
        # 대화 기록 저장
        history = ChatHistory(
            user_id=user_id,
            user_message=question,
            bot_response=llm_response.content,
            source_documents=json.dumps(sources, ensure_ascii=False),
            response_time=response_time,
        )
        self.session.add(history)
        self.session.commit()
        
        return {
            "answer": llm_response.content,
            "sources": sources,
            "response_time": round(response_time, 2),
            "model": llm_response.model,
            "provider": llm_response.provider,
        }
