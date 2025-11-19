"""
챗봇 및 시스템 설정 모델
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class ChatbotConfig(SQLModel, table=True):
    """
    챗봇 실행 설정

    단일 레코드로 관리되며 selected_model 값에 따라
    OpenAI 또는 로컬(Qwen) LLM을 선택한다.
    """

    __tablename__ = "chatbot_config"

    id: Optional[int] = Field(default=1, primary_key=True)
    selected_model: str = Field(
        default="openai", description="선택된 모델 ID (openai | qwen_local)"
    )
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI 모델명")
    qwen_model: str = Field(
        default="qwen2.5-7b-instruct", description="로컬 Qwen 모델 식별자"
    )
    qwen_api_base: Optional[str] = Field(
        default=None,
        description="로컬 Qwen OpenAI 호환 엔드포인트 (예: http://localhost:8001/v1)",
    )
    qwen_api_key: Optional[str] = Field(
        default=None, description="로컬 Qwen 엔드포인트 접근 토큰"
    )
    temperature: float = Field(default=0.2, description="디폴트 temperature")
    max_tokens: int = Field(default=800, description="최대 토큰 수")
    top_k: int = Field(default=6, description="RAG 검색 시 반환할 상위 청크 수")
    response_style: str = Field(
        default="structured", description="structured | narrative 등 응답 포맷"
    )
    verbosity: str = Field(
        default="concise", description="concise | detailed 등 응답 길이 제어"
    )
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def update_timestamp(self) -> None:
        """구성 변경 시 타임스탬프 갱신."""
        self.updated_at = datetime.utcnow()


