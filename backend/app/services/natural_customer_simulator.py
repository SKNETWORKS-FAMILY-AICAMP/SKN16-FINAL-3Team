"""
Natural customer utterance generator for bank teller training simulations.

This module reads the same data assets (personas, situations, product catalog)
used by the main simulation service and produces lighter, more conversational
customer turns that still encourage trainees to hit their learning goals.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import openai

from app.config import settings
from app.services.product_knowledge_service import ProductKnowledgeService


class NaturalCustomerSimulator:
    """
    Generate realistic customer utterances that reflect the selected persona,
    situation, and relevant product knowledge without overwhelming prompt rules.
    """

    PERSONA_FILE = "personas_expanded_minified2.json"
    SITUATION_FILE = "situations_expanded_40each_minified2.json"
    CATALOG_FILE = "product_catalog.json"

    def __init__(self, data_path: Optional[Path] = None) -> None:
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        self.client = openai.OpenAI(api_key=api_key)

        self.data_path = self._resolve_data_path(data_path)
        self.personas_by_id: Dict[str, Dict[str, Any]] = {}
        self.situations_by_id: Dict[str, Dict[str, Any]] = {}
        self.product_catalog: Dict[str, Any] = {}
        self.products_by_name: Dict[str, Dict[str, Any]] = {}
        self.products_by_keyword: Dict[str, Dict[str, Any]] = {}
        self.product_knowledge: Dict[str, List[Dict[str, Any]]] = {}
        self.rag_name_index: Dict[str, str] = {}
        self.rag_summary_cache: Dict[str, Optional[str]] = {}

        self._ensure_data_loaded()

        # 제품 지식 로드 (RAG Source)
        self.knowledge_service = ProductKnowledgeService(
            data_path=self.data_path,
            use_llm=False,
        )
        self.product_knowledge = self.knowledge_service.product_knowledge

        if self.knowledge_service.product_catalog:
            self.product_catalog = self.knowledge_service.product_catalog
        elif not self.product_catalog:
            self._load_product_catalog()

        self._build_product_indexes()
        self._build_rag_name_index()

    # --------------------------------------------------------------------- #
    # Public API                                                            #
    # --------------------------------------------------------------------- #

    def generate_first_turn(
        self,
        persona: Dict[str, Any],
        situation: Dict[str, Any],
        goals: Optional[List[str]] = None,
        tone_override: Optional[str] = None,
        max_sentences: int = 3,
        active_topic_index: Optional[int] = 0,
        history: Optional[List[Dict[str, str]]] = None,
        trainee_asked: str = "",
    ) -> str:
        """
        Generate the customer's opening statement.
        """
        goals = goals or situation.get("goals")
        active_topic = self._select_topic(situation, active_topic_index)

        messages = self._compose_messages(
            persona=persona,
            situation=situation,
            history=history or [],
            trainee_asked=trainee_asked,
            goals=goals,
            achieved_goal_indices=None,
            tone_override=tone_override,
            max_sentences=max_sentences,
            active_topic=active_topic,
            is_first_turn=True,
        )

        completion = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.4,
            max_tokens=220,
        )

        return completion.choices[0].message.content.strip()

    def generate_first_turn_by_id(
        self,
        persona_id: str,
        situation_id: str,
        tone_override: Optional[str] = None,
        max_sentences: int = 3,
        active_topic_index: Optional[int] = 0,
    ) -> str:
        """
        Convenience wrapper that loads persona/situation data by ID.
        """
        persona = self.get_persona(persona_id)
        situation = self.get_situation(situation_id)
        if not persona:
            raise ValueError(f"Persona '{persona_id}' not found.")
        if not situation:
            raise ValueError(f"Situation '{situation_id}' not found.")

        return self.generate_first_turn(
            persona=persona,
            situation=situation,
            tone_override=tone_override,
            max_sentences=max_sentences,
            active_topic_index=active_topic_index,
        )

    def generate_follow_up(
        self,
        persona: Dict[str, Any],
        situation: Dict[str, Any],
        trainee_asked: str,
        history: Optional[List[Dict[str, str]]],
        goals: Optional[List[str]] = None,
        achieved_goal_indices: Optional[List[int]] = None,
        tone_override: Optional[str] = None,
        max_sentences: int = 3,
        active_topic_index: Optional[int] = None,
        is_first_turn: bool = False,
    ) -> str:
        """
        Generate the next customer utterance in response to the trainee.
        """
        goals = goals or situation.get("goals")
        active_topic = self._select_topic(situation, active_topic_index)

        messages = self._compose_messages(
            persona=persona,
            situation=situation,
            history=history or [],
            trainee_asked=trainee_asked,
            goals=goals,
            achieved_goal_indices=achieved_goal_indices,
            tone_override=tone_override,
            max_sentences=max_sentences,
            active_topic=active_topic,
            is_first_turn=is_first_turn,
        )

        completion = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.5,
            max_tokens=240,
        )

        return completion.choices[0].message.content.strip()

    def generate_follow_up_by_id(
        self,
        persona_id: str,
        situation_id: str,
        trainee_asked: str,
        history: Optional[List[Dict[str, str]]],
        achieved_goal_indices: Optional[List[int]] = None,
        tone_override: Optional[str] = None,
        max_sentences: int = 3,
        active_topic_index: Optional[int] = None,
    ) -> str:
        persona = self.get_persona(persona_id)
        situation = self.get_situation(situation_id)
        if not persona:
            raise ValueError(f"Persona '{persona_id}' not found.")
        if not situation:
            raise ValueError(f"Situation '{situation_id}' not found.")

        return self.generate_follow_up(
            persona=persona,
            situation=situation,
            trainee_asked=trainee_asked,
            history=history,
            achieved_goal_indices=achieved_goal_indices,
            tone_override=tone_override,
            max_sentences=max_sentences,
            active_topic_index=active_topic_index,
        )

    def get_persona(self, persona_id: str) -> Optional[Dict[str, Any]]:
        return self.personas_by_id.get(persona_id)

    def get_situation(self, situation_id: str) -> Optional[Dict[str, Any]]:
        return self.situations_by_id.get(situation_id)

    # --------------------------------------------------------------------- #
    # Prompt assembly                                                       #
    # --------------------------------------------------------------------- #

    def _compose_messages(
        self,
        persona: Dict[str, Any],
        situation: Dict[str, Any],
        history: List[Dict[str, str]],
        trainee_asked: str,
        goals: Optional[List[str]],
        achieved_goal_indices: Optional[List[int]],
        tone_override: Optional[str],
        max_sentences: int,
        active_topic: Optional[Dict[str, Any]],
        is_first_turn: bool,
    ) -> List[Dict[str, str]]:
        persona_summary = self._summarize_persona(persona, tone_override)
        hint_text = self._format_persona_hints(persona)
        situation_summary = self._summarize_situation(situation)
        topic_text = self._format_topic(active_topic)
        product_text = self._format_products(situation, active_topic)
        goals_text = self._format_goals(goals, achieved_goal_indices)
        history_text = self._format_history(history or [])

        system_prompt = f"""
당신은 은행 창구를 찾은 실제 고객입니다. 한국어 존댓말로 {max_sentences}문장 이내에서 자연스럽게 말하세요.
- 대화 흐름을 끊지 말고, 직전까지의 맥락을 이어가세요.
- 이미 서로 인사했다면 다시 인사를 반복하지 마세요.
- 은행원이 방금 한 질문이나 설명에 먼저 응답한 뒤, 필요하면 짧게 감상이나 추가 궁금증을 붙입니다(필수 아님).
- 목표 달성을 위한 정보가 필요하더라도, 대화상 자연스러운 타이밍에 맞춰 유도하세요.
- 동일한 표현·요청을 반복하지 말고, 새 정보나 결정을 명확히 전달하세요.
- 페르소나 힌트는 참고만 하되 그대로 복사하지 말고, 어울리는 어휘로 변주하세요.
- 직전에 받은 답변을 다시 묻지 말고 인정하거나 다음 단계로 넘어가세요.
- 이미 처리·안내가 끝난 항목은 “네, 알겠습니다” 같이 수용하거나 마무리 발화로 정리하세요.
- 당신은 고객이므로 직원이 사용하는 표현(“어떻게 도와드릴까요?”, “설정해 드릴까요?”, “잠시만 기다려 주세요” 등)은 절대 쓰지 마세요.
""".strip()

        has_history = bool(history and len(history) > 0)

        sections = [
            f"[고객 페르소나]\n{persona_summary}",
            hint_text,
            f"[상황]\n{situation_summary}",
            topic_text,
            product_text,
            goals_text,
        ]

        if history_text:
            sections.append(
                "[직전 대화 요약]\n"
                "아래 흐름을 충분히 읽고, 이미 나온 질문·답변·결정을 반복하지 마세요. 이전 답변은 그대로 인정하고 그 위에서 이어가세요.\n"
                f"{history_text}"
            )

        sections.append(
            f"[은행원 발화]\n{trainee_asked or '신입은행원이 아직 말을 하지 않았습니다.'}"
        )

        guidance_lines = [
            "- 체감이 살아 있는 구어체를 사용하고, 감정 표현은 상황에 맞춰 적절히 드러냅니다.",
            "- 신입 은행원이 정보를 수집하거나 절차를 안내하도록 자연스럽게 요청/응답하세요.",
            "- 은행 업무 범위를 벗어나지 말고, 상황 목표와 연결된 주제에 집중하세요.",
            "- 결정이 필요하면 명확히 선택하고, 추가 질문은 필요할 때만 1개 이내로 던지세요.",
        ]

        if is_first_turn:
            guidance_lines.append("- 첫 발화에서는 방문 목적을 뚜렷하게 밝히고, 필요한 배경을 한두 문장으로 전하세요.")
        elif has_history:
            guidance_lines.extend(
                [
                    "- 이미 합의된 사항이나 완료된 요청은 다시 반복하지 말고 다음 단계로 넘어가세요.",
                    "- 이전 고객 발화를 그대로 재사용하지 말고, 새 표현으로 자연스럽게 이어가세요.",
                    "- 직전 답변을 재질문하지 말고, 필요하면 확인 후 “네, 알겠습니다”처럼 수용하세요.",
                    "- 직원이 신청서 작성, 마무리 안내 등을 하면 감사 인사와 함께 대화를 정리하세요.",
                    "- 고객인 당신이 직원처럼 대신 안내하거나 결정을 묻지 말고(예: “어떻게 설정해 드릴까요?”), 자신의 필요와 선택을 분명히 밝히세요.",
                ]
            )

        sections.append("[작성 지침]\n" + "\n".join(guidance_lines))

        user_prompt = "\n\n".join([section for section in sections if section])

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _summarize_persona(
        self,
        persona: Dict[str, Any],
        tone_override: Optional[str],
    ) -> str:
        tone = (
            tone_override
            or persona.get("tone")
            or persona.get("customer_style")
            or persona.get("speech", {}).get("tone")
            or ""
        )
        description_parts = [
            f"ID: {persona.get('id', '미정')}",
            f"성별: {persona.get('gender', '알 수 없음')}",
            f"연령대: {persona.get('age_group', '알 수 없음')}",
            f"직업: {persona.get('occupation', '알 수 없음')}",
            f"고객 유형: {persona.get('customer_style', persona.get('type', '알 수 없음'))}",
            f"권장 말투: {tone}",
        ]

        literacy = persona.get("financial_literacy")
        if literacy:
            description_parts.append(f"금융 이해도: {literacy}")

        return "\n".join(description_parts)

    @staticmethod
    def _format_persona_hints(persona: Dict[str, Any]) -> str:
        hints = persona.get("utterance_hints") or persona.get("speech", {}).get("examples")
        if not hints:
            return ""

        sample = " / ".join(hints[:3])
        return f"[대화 톤 힌트]\n- 말투 예시: {sample}"

    def _summarize_situation(self, situation: Dict[str, Any]) -> str:
        title = situation.get("title", "일반 상담")
        description = situation.get("description") or situation.get("details") or ""
        lines = [f"분류: {title}", f"코드: {situation.get('id', 'unknown')}"]
        if description:
            lines.append(f"설명: {description}")
        return "\n".join(lines)

    @staticmethod
    def _format_topic(topic: Optional[Dict[str, Any]]) -> str:
        if not topic:
            return ""

        title = topic.get("title", "")
        intent = topic.get("intent", "")
        product = topic.get("product")
        parts = ["[현재 상담 주제]"]
        if title:
            parts.append(f"- 주제: {title}")
        if intent:
            parts.append(f"- 의도: {intent}")
        if product:
            parts.append(f"- 연결 상품: {product}")
        return "\n".join(parts)

    def _format_products(
        self,
        situation: Dict[str, Any],
        active_topic: Optional[Dict[str, Any]],
    ) -> str:
        related_names: List[str] = []

        if active_topic and active_topic.get("product"):
            related_names.append(active_topic["product"])

        for name in situation.get("linked_products") or []:
            if name and name not in related_names:
                related_names.append(name)

        if not related_names:
            return ""

        lines = ["[관련 상품 정보]"]
        for raw_name in related_names[:6]:
            product = self._find_product_entry(raw_name)
            display_name = product.get("name", raw_name) if product else raw_name
            description = product.get("description", "") if product else ""
            features = ", ".join(product.get("features", [])[:3]) if product else ""

            rag_code = self._resolve_rag_code(
                raw_name,
                display_name,
                product.get("code") if product else None,
                active_topic.get("product_code") if active_topic else None,
            )
            rag_summary = self._summarize_rag_product(rag_code) if rag_code else None

            base_line = f"- {display_name}"
            detail_fragments = []
            if description:
                detail_fragments.append(description)
            if features:
                detail_fragments.append(f"주요 특징: {features}")
            if detail_fragments:
                base_line += ": " + " / ".join(detail_fragments)

            lines.append(base_line)

            if rag_summary:
                lines.append(f"  · RAG 핵심: {rag_summary}")
            elif not description:
                lines.append("  · 카탈로그 설명이 부족하니, 일반적인 은행 지식을 바탕으로 안내하세요.")

        return "\n".join(lines)

    @staticmethod
    def _format_goals(goals: Optional[List[str]], achieved: Optional[List[int]]) -> str:
        if not goals:
            return "[훈련 목표] 등록된 목표 없음"

        achieved = achieved or []
        lines = ["[훈련 목표]"]
        for idx, goal in enumerate(goals):
            status = "완료" if idx in achieved else "미완료"
            cue = "→ 은행원이 이 목표를 달성하도록 자연스럽게 유도하세요." if idx not in achieved else ""
            lines.append(f"- ({status}) {goal} {cue}".strip())
        return "\n".join(lines)

    @staticmethod
    def _format_history(history: List[Dict[str, str]]) -> str:
        if not history:
            return ""

        formatted = []
        for turn in history[-6:]:
            role = turn.get("role", "")
            role_label = "고객" if role == "customer" else "은행원"
            text = turn.get("text", "")
            formatted.append(f"{role_label}: {text}")
        return "\n".join(formatted)

    # --------------------------------------------------------------------- #
    # Data loading                                                          #
    # --------------------------------------------------------------------- #

    def _resolve_data_path(self, explicit: Optional[Path]) -> Path:
        if explicit:
            return Path(explicit)

        docker_path = Path("/app/data")
        if docker_path.exists():
            return docker_path

        return Path(__file__).resolve().parent.parent.parent / "data"

    def _ensure_data_loaded(self) -> None:
        if not self.personas_by_id:
            self._load_personas()
        if not self.situations_by_id:
            self._load_situations()
        if not self.product_catalog:
            self._load_product_catalog()
            self._build_product_indexes()

    def _load_personas(self) -> None:
        file_path = self.data_path / self.PERSONA_FILE
        if not file_path.exists():
            raise FileNotFoundError(f"Persona file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        personas = data.get("personas") if isinstance(data, dict) else data
        if not isinstance(personas, list):
            raise ValueError("Persona data is not a list.")

        self.personas_by_id = {p.get("id"): p for p in personas if p.get("id")}

    def _load_situations(self) -> None:
        file_path = self.data_path / self.SITUATION_FILE
        if not file_path.exists():
            raise FileNotFoundError(f"Situation file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        situations = data.get("situations") if isinstance(data, dict) else data
        if not isinstance(situations, list):
            raise ValueError("Situation data is not a list.")

        self.situations_by_id = {s.get("id"): s for s in situations if s.get("id")}

    def _load_product_catalog(self) -> None:
        file_path = self.data_path / self.CATALOG_FILE
        if not file_path.exists():
            raise FileNotFoundError(f"Product catalog file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as fp:
            catalog = json.load(fp)

        self.product_catalog = catalog
        self._build_product_indexes()

    # --------------------------------------------------------------------- #
    # Helpers                                                               #
    # --------------------------------------------------------------------- #

    def _select_topic(
        self,
        situation: Dict[str, Any],
        index: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        topics = situation.get("starter_topics") or []
        if not topics:
            return None

        if index is None:
            return topics[0]

        if index < 0 or index >= len(topics):
            return topics[0]

        return topics[index]

    @staticmethod
    def _normalize_token(value: str) -> str:
        return "".join(value.split()).lower()

    def _find_product_entry(self, name: Optional[str]) -> Optional[Dict[str, Any]]:
        if not name:
            return None

        normalized = self._normalize_token(name)
        if normalized in self.products_by_name:
            return self.products_by_name[normalized]

        if normalized in self.products_by_keyword:
            return self.products_by_keyword[normalized]

        # Fallback: try contains search on keywords
        for keyword, product in self.products_by_keyword.items():
            if normalized and normalized in keyword:
                return product

        return None

    def _build_product_indexes(self) -> None:
        self.products_by_name.clear()
        self.products_by_keyword.clear()

        products = self.product_catalog.get("products", []) if self.product_catalog else []
        for product in products:
            name_key = self._normalize_token(product.get("name", ""))
            if name_key:
                self.products_by_name[name_key] = product

            for keyword in product.get("keywords", []):
                kw_key = self._normalize_token(keyword)
                if kw_key and kw_key not in self.products_by_keyword:
                    self.products_by_keyword[kw_key] = product

    def _build_rag_name_index(self) -> None:
        self.rag_name_index.clear()
        if not self.product_knowledge:
            return

        for code, chunks in self.product_knowledge.items():
            candidates = {code}
            for chunk in chunks:
                product_field = chunk.get("product")
                subsection = chunk.get("subsection_title", "")
                breadcrumb = chunk.get("breadcrumb", "")

                candidates.update(self._split_product_tokens(product_field))
                candidates.update(self._split_product_tokens(subsection))
                candidates.update(self._split_product_tokens(breadcrumb))

            for candidate in candidates:
                normalized = self._normalize_token(candidate)
                if normalized and normalized not in self.rag_name_index:
                    self.rag_name_index[normalized] = code

    @staticmethod
    def _split_product_tokens(value: Optional[str]) -> Sequence[str]:
        if not value:
            return []

        cleaned = (
            value.replace(">", " ")
            .replace("(", " ")
            .replace(")", " ")
            .replace("[", " ")
            .replace("]", " ")
            .replace(":", " ")
        )

        tokens = {value.strip()}
        for part in cleaned.split():
            part = part.strip()
            if len(part) >= 2:
                tokens.add(part)

        return [token for token in tokens if token]

    def _resolve_rag_code(self, *names: Optional[str]) -> Optional[str]:
        for name in names:
            code = self._lookup_rag_code_by_name(name)
            if code:
                return code
        return None

    def _lookup_rag_code_by_name(self, name: Optional[str]) -> Optional[str]:
        if not name:
            return None

        normalized = self._normalize_token(name)
        if normalized in self.rag_name_index:
            return self.rag_name_index[normalized]

        # Fallback: try contains search across keys
        for key, code in self.rag_name_index.items():
            if normalized and normalized in key:
                return code

        return None

    def _summarize_rag_product(self, product_code: Optional[str]) -> Optional[str]:
        if not product_code:
            return None

        if product_code in self.rag_summary_cache:
            return self.rag_summary_cache[product_code]

        chunks = self.product_knowledge.get(product_code)
        if not chunks:
            self.rag_summary_cache[product_code] = None
            return None

        highlights: List[str] = []
        priority_keywords = ["상품 개요", "상품 개념", "가입 조건", "금리 정보", "혜택", "우대금리"]

        # Prioritize chunks with specific breadcrumbs
        for keyword in priority_keywords:
            if len(highlights) >= 3:
                break
            for chunk in chunks:
                if keyword in (chunk.get("breadcrumb", "") or ""):
                    highlights.extend(self._extract_highlights(chunk.get("text", ""), limit=3 - len(highlights)))
                    if len(highlights) >= 3:
                        break

        if not highlights:
            highlights = self._extract_highlights(chunks[0].get("text", ""), limit=3)

        summary = "; ".join(highlights[:3]) if highlights else None
        self.rag_summary_cache[product_code] = summary
        return summary

    @staticmethod
    def _extract_highlights(text: str, limit: int = 3) -> List[str]:
        lines: List[str] = []
        for raw in text.splitlines():
            stripped = raw.strip()
            if not stripped or stripped.upper().startswith("PART "):
                continue

            cleaned = stripped.lstrip("▣-•▶●*-0123456789. ").strip()
            if cleaned:
                lines.append(cleaned)

            if len(lines) >= limit:
                break

        return lines[:limit]



