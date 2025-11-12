"""
임베딩 서비스
"""
from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import List

from openai import AsyncOpenAI

from app.config import settings


class EmbeddingService:
    """
    OpenAI 임베딩 서비스 래퍼

    현재 text-embedding-ada-002 (1536차원) 기준으로 구성되어 있으며
    필요 시 다른 제공자로 확장할 수 있도록 분리하였다.
    """

    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY 환경 변수가 설정되어 있지 않습니다.")

        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._model = "text-embedding-ada-002"

    async def embed_query(self, query: str) -> List[float]:
        """단일 쿼리 임베딩"""
        response = await self._client.embeddings.create(
            model=self._model,
            input=query,
        )
        return response.data[0].embedding

    async def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        """다중 청크 임베딩"""
        if not chunks:
            return []

        response = await self._client.embeddings.create(
            model=self._model,
            input=chunks,
        )
        return [item.embedding for item in response.data]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """싱글톤 형태로 EmbeddingService 제공"""
    return EmbeddingService()


async def embed_text(text: str) -> List[float]:
    """단일 텍스트 임베딩 (편의 함수)"""
    service = get_embedding_service()
    return await service.embed_query(text)


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """다중 텍스트 임베딩 (편의 함수)"""
    if not texts:
        return []
    service = get_embedding_service()
    # OpenAI API는 비동기 호출을 지원하므로 그대로 사용
    return await service.embed_chunks(texts)


def embed_text_sync(text: str) -> List[float]:
    """동기 코드에서 임베딩을 사용해야 할 때 (예: 스크립트)"""
    return asyncio.run(embed_text(text))


def embed_texts_sync(texts: List[str]) -> List[List[float]]:
    """동기 코드에서 다중 임베딩 사용"""
    return asyncio.run(embed_texts(texts))


