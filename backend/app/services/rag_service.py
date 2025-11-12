"""
RAG 서비스 (벡터 검색 + LLM 선택)
"""
from __future__ import annotations

import json
import time
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, text
from sqlmodel import Session

from pgvector.sqlalchemy import Vector

from app.models import ChatHistory
from .embedding_service import embed_text
from .llm_service import LLMService


class RAGService:
    """벡터 검색 기반 RAG 서비스"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.llm_service = LLMService(session)
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

    # --- 검색 ---
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

    # --- 프롬프트 구성 ---
    def _build_system_prompt(self, config: Dict[str, Any]) -> str:
        prompt_parts = [
            "당신은 하경은행 신입 행원을 돕는 RAG 챗봇 AI 하리보입니다. 🐻",
            "항상 한국어로 답변하고, 제공된 컨텍스트를 최우선으로 활용하세요.",
            "컨텍스트에 근거가 없거나 정보가 부족하면 '추가 확인 필요'라고 명시하고 추측하지 마세요.",
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

    def _build_general_system_prompt(self, config: Dict[str, Any]) -> str:
        base_prompt = [
            "당신은 하경은행 신입 행원을 돕는 AI 하리보입니다. 🐻",
            "일상적인 대화나 인사말에는 자연스럽고 간결하게 응답하세요.",
            "질문이 은행 상품이나 규정과 직접 관련되지 않으면 친근하게 대화하며 필요한 경우 상담을 제안하세요.",
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

        documents = await self.similarity_search(question)
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
