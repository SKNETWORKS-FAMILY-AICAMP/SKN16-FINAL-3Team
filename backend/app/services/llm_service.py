"""
LLM 선택 및 호출 서비스
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from openai import AsyncOpenAI
from sqlmodel import Session
from sqlalchemy import text

from app.config import settings
from app.models import ChatbotConfig


class ChatCompletionError(RuntimeError):
    """LLM 응답 오류"""


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str


class BaseChatClient:
    """LLM 클라이언트 공통 인터페이스"""

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float,
        max_tokens: int,
        model: str,
    ) -> LLMResponse:
        raise NotImplementedError


class OpenAIChatClient(BaseChatClient):
    """OpenAI Chat Completions API"""

    def __init__(self, api_key: Optional[str] = None) -> None:
        key = api_key or settings.OPENAI_API_KEY
        if not key:
            raise RuntimeError("OPENAI_API_KEY 환경 변수가 설정되어 있지 않습니다.")
        self._client = AsyncOpenAI(api_key=key)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float,
        max_tokens: int,
        model: str,
    ) -> LLMResponse:
        response = await self._client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        if not response.choices:
            raise ChatCompletionError("LLM 응답이 비어 있습니다.")

        content = response.choices[0].message.content or ""
        return LLMResponse(content=content.strip(), model=model, provider="openai")


class OpenAICompatibleClient(BaseChatClient):
    """
    OpenAI 호환 엔드포인트용 클라이언트 (예: 로컬 Qwen 서버)
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None) -> None:
        if not base_url:
            raise RuntimeError("OpenAI 호환 엔드포인트 base_url이 필요합니다.")
        self._client = AsyncOpenAI(api_key=api_key or "EMPTY", base_url=base_url)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float,
        max_tokens: int,
        model: str,
    ) -> LLMResponse:
        response = await self._client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        if not response.choices:
            raise ChatCompletionError("LLM 응답이 비어 있습니다.")

        content = response.choices[0].message.content or ""
        return LLMResponse(content=content.strip(), model=model, provider="qwen_local")


class LLMService:
    """DB 설정을 기준으로 LLM을 선택하여 호출"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """필요한 컬럼이 없으면 추가한다."""
        alter_statements = [
            "ALTER TABLE chatbot_config ADD COLUMN IF NOT EXISTS response_style TEXT DEFAULT 'structured'",
            "ALTER TABLE chatbot_config ADD COLUMN IF NOT EXISTS verbosity TEXT DEFAULT 'concise'",
        ]
        for stmt in alter_statements:
            self.session.execute(text(stmt))
        self.session.commit()

    # --- 설정 로딩/생성 ---
    def _load_config(self) -> ChatbotConfig:
        config = self.session.get(ChatbotConfig, 1)
        if not config:
            config = ChatbotConfig()
            self.session.add(config)
            self.session.commit()
            self.session.refresh(config)
        updated = False
        if not getattr(config, "response_style", None):
            config.response_style = "structured"
            updated = True
        if not getattr(config, "verbosity", None):
            config.verbosity = "concise"
            updated = True
        if updated:
            self.session.add(config)
            self.session.commit()
            self.session.refresh(config)
        return config

    def get_config_dict(self) -> Dict[str, Any]:
        config = self._load_config()
        return {
            "id": config.id,
            "selected_model": config.selected_model,
            "openai_model": config.openai_model,
            "qwen_model": config.qwen_model,
            "qwen_api_base": config.qwen_api_base,
            "has_qwen_api_key": bool(config.qwen_api_key),
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_k": config.top_k,
            "updated_at": config.updated_at,
            "response_style": config.response_style,
            "verbosity": config.verbosity,
        }

    def update_config(self, payload: Dict[str, Any]) -> ChatbotConfig:
        config = self._load_config()
        if "selected_model" in payload:
            allowed_models = {"openai", "qwen_local"}
            if payload["selected_model"] not in allowed_models:
                raise ValueError("selected_model must be openai or qwen_local")
        if "response_style" in payload:
            allowed_styles = {"structured", "narrative"}
            if payload["response_style"] not in allowed_styles:
                raise ValueError("response_style must be structured or narrative")
        if "verbosity" in payload:
            allowed_verbosity = {"concise", "detailed"}
            if payload["verbosity"] not in allowed_verbosity:
                raise ValueError("verbosity must be concise or detailed")

        for key, value in payload.items():
            if hasattr(config, key) and value is not None:
                setattr(config, key, value)

        config.update_timestamp()
        self.session.add(config)
        self.session.commit()
        self.session.refresh(config)
        return config

    # --- 응답 생성 ---
    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        override_model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        config = self._load_config()
        provider = config.selected_model
        temp = temperature if temperature is not None else config.temperature
        tokens = max_tokens if max_tokens is not None else config.max_tokens

        if provider == "qwen_local":
            if not config.qwen_api_base:
                raise RuntimeError(
                    "Qwen 로컬 모델이 선택되어 있지만 qwen_api_base가 설정되어 있지 않습니다."
                )
            client: BaseChatClient = OpenAICompatibleClient(
                base_url=config.qwen_api_base,
                api_key=config.qwen_api_key,
            )
            model_name = override_model or config.qwen_model
        else:
            client = OpenAIChatClient()
            model_name = override_model or config.openai_model

        return await client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temp,
            max_tokens=tokens,
            model=model_name,
        )


