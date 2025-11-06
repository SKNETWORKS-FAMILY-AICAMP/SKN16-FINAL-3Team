"""
프롬프트 오케스트레이터
페르소나 + 시츄에이션 + 대화 히스토리 + RAG 기반 자연스러운 고객 응답 생성
"""
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime


def compose_llm_messages(
    persona: Dict,
    situation: Dict,
    user_text: str,
    rag_hits: Optional[List[Dict]] = None,
    history: Optional[List[Dict]] = None,
    extras: Optional[Dict] = None
) -> List[Dict]:
    """
    페르소나와 시츄에이션에 맞춘 LLM 메시지 구성
    
    Args:
        persona: 페르소나 정보 (persona_id, gender, age_group, occupation, type, tone, style 등)
        situation: 상황 정보 (id, title, goals, required_slots, forbidden_claims, style_rules 등)
        user_text: 사용자 발화 (정규화된 텍스트)
        rag_hits: RAG 검색 결과 (doc_id, title, snippet)
        history: 대화 히스토리 (최근 4턴)
        extras: 추가 정보 (userText_raw, corrections, catalogHits, needs_clarification 등)
    
    Returns:
        OpenAI API에 전달할 messages 리스트
    """
    rag_hits = rag_hits or []
    history = (history or [])[-10:]  # 최근 10턴까지 (더 많은 맥락)
    extras = extras or {}
    
    # 의미보정 정보 추출
    user_text_raw = extras.get("userText_raw", user_text)
    corrections = extras.get("corrections", [])
    catalog_hits = extras.get("catalogHits", [])
    needs_clarification = extras.get("needs_clarification", False)
    achieved_goals = extras.get("achieved_goals", [])  # 달성된 목표 인덱스 리스트
    customer_emotion = extras.get("customer_emotion", persona.get("type", "긍정형"))  # 페르소나 타입 또는 기본값
    stuck_counter = extras.get("stuck_counter", 0)
    should_close = extras.get("should_close", False)
    last_employee_questions = extras.get("last_employee_questions", [])
    urgency = (customer_emotion == "급함형")
    
    # System 프롬프트
    system = f"""
🎭 당신은 실제 은행을 방문한 고객입니다. 지금 신입사원(은행 직원)과 상담 중이며, 현실적이고 감정이 느껴지는 대화를 하세요.

[고객 역할 가이드]
- 당신은 '은행 고객'입니다. 궁금한 점을 묻거나 의견을 말하는 입장입니다.
- 완벽한 문장보다는 **사람처럼 말하세요.**
  - 추임새 예시: "음…", "그렇군요.", "아, 알겠어요.", "그럼 어떻게 해야 해요?"
- 감정형에 따라 말투를 다르게 하세요:
  - 😡 **불만형**: 짜증·불만 ("왜 이렇게 오래 걸려요?", "그럼 제 돈은요?")
  - 😰 **급함형**: 서두름 ("지금 바로 가능할까요?", "빨리 처리돼야 하는데요.")
  - 😊 **긍정형**: 밝음 ("좋네요!", "감사합니다!", "그럼 바로 할게요.")
  - 😔 **불안형**: 걱정 ("이거 손해보는 건 아니죠?", "조금 어렵네요.")
  - 😏 **의심형**: 신뢰 부족 ("그게 진짜 그런가요?", "다른 은행은 안 그렇던데요?")

[대화 흐름 원칙]
1. **직원이 질문하면 먼저 질문에 답하세요.** 그 후 필요하면 추가로 1가지만 물어보세요.
2. 신입사원의 설명에 자연스럽게 반응하고, 1~3문장 이내로 대화하세요.
3. 한 번에 한 가지 핵심 질문만 하세요.
4. 이미 충분히 설명받은 내용은 "네, 알겠습니다", "좋아요" 등으로 마무리하세요.
5. 신입사원이 해결책을 주면, 감정이 섞인 반응을 하세요.
   예: "아 다행이에요!", "아, 그럼 그렇게 해주세요."
6. 대화가 3~5턴 이상 진행되면 자연스럽게 마무리하세요.
   예: "그럼 그렇게 진행할게요.", "오늘 도움 많이 됐어요."

[급함형 특별 규칙]
- 급함형이면 간결하게 답하고, 즉시 실행 가능한 경로를 선호하세요.
- 긴 설명보다는 "지금 바로", "빨리", "오늘" 같은 표현을 사용하세요.

[감정 유지 규칙]
- 감정형이 대화 도중 바뀌지 않습니다. 예: 불만형이면 끝까지 불만형 톤 유지.
- 단, 해결안이 명확해지면 톤이 약간 누그러져도 됩니다.

[반복 방지 - 🚨 매우 중요!]
- 같은 질문을 반복하지 마세요. 최근 2턴 내에 한 질문은 절대 다시 하지 마세요.
- 직원이 이미 답변한 내용에 대해 "그럼 ~는 거죠?" 같은 재확인 질문도 하지 마세요.
- 직원이 "네 맞습니다", "네 맞아요" 등으로 확인했다면 더 이상 질문하지 말고 "네, 알겠습니다", "감사합니다" 같은 간단한 응답으로 마무리하세요.

[현재 고객 감정형]
지금 고객은 "{customer_emotion}" 상태입니다.
이 감정에 맞는 말투와 어조를 사용하세요.
특히 급함형이면 간결하고 즉시 실행 가능한 경로를 선호하는 반응을 하세요.

[주의사항]
- 같은 질문을 반복하지 마세요.
- 대화 주제를 갑자기 바꾸지 마세요.
- 은행 상담과 무관한 주제는 절대 하지 마세요.
""".strip()

    # Developer 프롬프트 (출력 형식) - 간소화
    developer = """
다음 JSON만 출력한다. 설명이나 문장은 절대 추가하지 마라.

{
 "script": "<고객 발화 (자연스럽고 감정이 느껴지는 한국어 문장 1~3개)>",
 "followups": ["<추가로 물어볼 0~1개의 질문>"],
 "customer_emotion": "<불만형|급함형|긍정형|불안형|의심형>",
 "next_action": "<ask|confirm|end>",
 "end_signal": true|false,
 "safety_notes": "",
 "grounding": ["<참고한 doc_id들. 없으면 빈 배열>"]
}

[필드 설명]
- script: 고객이 실제로 말할 내용 (1~3문장, 자연스럽고 감정 표현 포함)
- followups: 추가 질문 (0~1개, 없으면 빈 배열)
- customer_emotion: 현재 고객 감정 상태
- next_action: 다음 행동 (ask=추가 질문, confirm=확인/마무리, end=대화 종료)
- end_signal: 대화 종료 신호 (true면 마무리)
- safety_notes: 안전 관련 참고사항 (필요시)
- grounding: 참고한 RAG 문서 ID 목록
""".strip()

    # User 프롬프트 (런타임 데이터)
    user_parts = [
        f"[은행 직원 발화]\n{user_text}\n",
        f"[선택된 페르소나]\n{persona.get('gender', '')}, {persona.get('age_group', '')}, {persona.get('occupation', '')}, 고객타입={persona.get('type', '')}, tone={persona.get('tone', '')}, style={json.dumps(persona.get('style', {}))}\n",
        f"[선택된 시츄에이션]\nid={situation.get('id', '')}, goals={json.dumps(situation.get('goals', []))}, required_slots={json.dumps(situation.get('required_slots', []))}, forbidden_claims={json.dumps(situation.get('forbidden_claims', []))}, style_rules={json.dumps(situation.get('style_rules', []))}, disclaimer=\"{situation.get('disclaimer', '')}\"\n",
    ]
    
    # 목표 달성 상태 추가
    all_goals = situation.get('goals', [])
    if all_goals:
        achieved_goal_texts = []
        remaining_goal_texts = []
        for i, goal in enumerate(all_goals):
            if i in achieved_goals:
                achieved_goal_texts.append(f"- [✅ 달성] {goal}")
            else:
                remaining_goal_texts.append(f"- [⏳ 미달성] {goal}")
        
        user_parts.append("[🎯 상담 목표 달성 현황]\n")
        if achieved_goal_texts:
            user_parts.append("달성된 목표:\n" + "\n".join(achieved_goal_texts) + "\n")
        if remaining_goal_texts:
            user_parts.append("미달성 목표 (이제 이 목표들에 집중하세요):\n" + "\n".join(remaining_goal_texts) + "\n")
        
        user_parts.append("""
[목표 기반 대화 가이드]
1. 달성된 목표(✅)에 대해서는 이미 충분히 논의했으므로 더 이상 자세히 묻지 마세요
2. 미달성 목표(⏳)에 집중하여 자연스럽게 질문하세요
3. 🚨 매우 중요: 현재 대화 맥락과 자연스럽게 연결되는 방식으로 질문하세요!
   * 현재 대화 주제(예: 카드 분실/재발급)와 관련 없는 질문은 하지 마세요!
   * 쌩뚱맞게 주제를 바꾸지 마세요!
   * 예시: 카드 분실 상황에서 "새 카드를 받으면 바로 사용할 수 있나요?" (자연스러움) ✅
   * 예시: 카드 분실 상황에서 "카드 한도는 어떻게 되나요?" (부자연스러움) ❌
   * 현재 대화 주제를 자연스럽게 이어가면서, 그 맥락 안에서 목표와 관련된 질문을 하세요
4. 🚨 매우 중요: 대부분의 목표가 달성되었거나 (달성률 50% 이상) 충분히 질문을 했다면:
   * 추가로 1-2개 질문만 하고 자연스럽게 마무리하세요!
   * 계속 질문을 남발하지 마세요!
   * 직원이 설명한 내용에 대해 "그럼 ~는 거죠?", "그럼 ~가 되는 건가요?" 같은 재확인 질문은 절대 하지 마세요!
   * 직원이 "네 맞습니다", "네 맞아요" 등으로 확인했다면 더 이상 질문하지 말고 "네, 알겠습니다", "감사합니다" 같은 간단한 응답으로 마무리하세요!
5. 모든 목표가 달성되면 자연스럽게 마무리하세요 ("좋아요", "알겠습니다", "감사합니다")
6. 목표를 달성하기 위한 다음 단계로 대화를 이어가세요
        """.strip())
    
    user_parts.append("""
[대화 단계별 가이드]
- 첫 대화: 인사 + 목적 ('안녕하세요. 예금 상품 알아보러 왔어요')
- 2번째 이후: 직원 말에 직접 반응 ('그 상품들 이자율이 어떻게 되나요?')
- 진행 중: 더 구체적인 질문 ('기간은 얼마나 되나요?', '최소 금액이 있나요?')
- 직원 처리 중: 직원이 "잠시만", "기다려주세요", "확인해보겠습니다" 등 처리 중/대기 요청을 하면:
  * 새로운 질문을 하지 마세요!
  * "네", "알겠습니다", "네, 기다리겠습니다" 같은 짧은 응답만 하세요!
- 마무리: 결정이나 추가 문의 ('좀 더 생각해볼게요', '신청하려면 어떻게 하나요?', '감사합니다')
- 🚨 마무리 시점 판단 (매우 중요!):
  * 대부분의 목표가 달성되었거나 (달성률 50% 이상)
  * 대화가 충분히 진행되었거나 (4턴 이상)
  * 모든 목표가 달성되었으면
  → 추가로 1-2개 질문만 하고 자연스럽게 마무리하세요! 질문을 계속 남발하지 마세요!
  → 직원이 이미 설명한 내용에 대해 "그럼 ~는 거죠?", "그럼 ~가 되는 건가요?" 같은 재확인 질문은 절대 하지 마세요!
  → 직원이 "네 맞습니다", "네 맞아요" 등으로 확인했다면 더 이상 질문하지 말고 "네, 알겠습니다", "감사합니다" 같은 간단한 응답으로 마무리하세요!
""".strip())
    
    # 의미보정 정보 추가
    if corrections:
        correction_lines = [f"- '{corr[0]}' → '{corr[1]}' ({corr[2]})" for corr in corrections]
        user_parts.append(f"[🔧 음성인식 교정 정보]\n" + "\n".join(correction_lines) + "\n")
    
    if catalog_hits:
        catalog_lines = [f"- {hit['product']} ({hit['category_ko']}) - {hit.get('match_type', '')}" for hit in catalog_hits]
        user_parts.append(f"[📋 매칭된 상품]\n" + "\n".join(catalog_lines) + "\n")
    
    if needs_clarification:
        user_parts.append("[⚠️ 재확인 필요] 음성인식 신뢰도가 낮거나 교정이 많아 재확인 질문을 포함하세요.\n")
    
    # 대화 히스토리 - 매우 중요!
    if history:
        hist_lines = []
        last_employee_questions = []
        stuck_counter = 0
        should_close = False
        urgency = False
        for i, item in enumerate(history):
            role = item.get('role', 'unknown')
            text = item.get('text', '')
            # 역할 표시: customer -> 고객, employee -> 직원
            role_display = "고객" if role == "customer" else "직원"
            hist_lines.append(f"{i+1}. {role_display}: {text}")
            
            if role == "employee":
                last_employee_questions.append(text)
                if last_employee_questions[-2:] == last_employee_questions[-2:]: # 최근 두 질문이 동일한지 확인
                    stuck_counter += 1
                else:
                    stuck_counter = 0
                
                if text.lower().startswith("네 맞습니다") or text.lower().startswith("네 맞아요") or text.lower().startswith("네 감사합니다") or text.lower().startswith("알겠습니다") or text.lower().startswith("네"):
                    should_close = True
                    break
                if text.lower().startswith("네 맞습니다") or text.lower().startswith("네 맞아요") or text.lower().startswith("네 감사합니다") or text.lower().startswith("알겠습니다") or text.lower().startswith("네"):
                    urgency = True
                    break
        
        user_parts.append(f"[🔥 최근 대화 히스토리 ({len(history)}턴)]\n" + "\n".join(hist_lines) + "\n")
        
        # 반복 방지 가드
        if last_employee_questions:
            user_parts.append(f"[🚨 최근 직원 질문 기록] 다음 질문들과 동일한 질문을 하지 마세요: {', '.join(last_employee_questions[-2:])}\n")
        
        if stuck_counter > 1:
            user_parts.append(f"[🚨 반복 경고] 같은 질문을 반복하지 마세요. 새로운 질문을 하거나 마무리하세요.\n")
        
        if should_close:
            user_parts.append("[🚨 마무리] 대화를 자연스럽게 마무리하세요. end_signal=true로 설정하세요.\n")
        
        if urgency:
            user_parts.append("[🚨 긴급도] 급함형입니다. 간결하게 답하고 즉시 실행 가능한 경로를 선호하세요.\n")
        
        user_parts.append("""
[대화 히스토리 활용 규칙]
- 이미 나온 질문은 반복하지 마세요.
- 직원이 이미 설명한 내용은 확인만 하고, 새로운 주제로 넘어가지 마세요.
- 직원이 "잠시만", "기다려주세요" 등 처리 중이면 "네, 알겠습니다" 같은 짧은 응답만 하세요.
- 직원이 "네 맞습니다" 등으로 확인했다면 더 이상 질문하지 말고 마무리하세요.
""".strip())
    else:
        user_parts.append("[대화 히스토리 없음 - 첫 대화입니다]\n")
    
    # RAG 검색 결과
    if rag_hits:
        rag_lines = [f"({i+1}) [{hit.get('doc_id', '')}] {hit.get('title', '')}: {hit.get('snippet', '')}" 
                    for i, hit in enumerate(rag_hits)]
        user_parts.append(f"[사실 근거(RAG 스니펫, 0~{len(rag_hits)}개)]\n" + "\n".join(rag_lines))
    
    user = "\n".join(user_parts).strip()
    
    # System + Developer 프롬프트를 하나로 합침
    system_full = f"{system}\n\n{developer}"
    
    messages = [
        {"role": "system", "content": system_full},
        {"role": "user", "content": user}
    ]
    
    return messages


def parse_llm_response(content: str) -> Dict:
    """
    LLM 응답을 파싱하여 {script, followups, customer_emotion, next_action, end_signal, safety_notes, grounding} 반환
    """
    try:
        # JSON 추출 (```json``` 블록 제거)
        content_clean = content.strip()
        if content_clean.startswith("```"):
            content_clean = content_clean.split("```")[1]
            if content_clean.startswith("json"):
                content_clean = content_clean[4:]
        content_clean = content_clean.strip()
        
        parsed = json.loads(content_clean)
        return {
            "script": parsed.get("script", ""),
            "followups": parsed.get("followups", []),
            "customer_emotion": parsed.get("customer_emotion", "긍정형"),
            "next_action": parsed.get("next_action", "ask"),
            "end_signal": parsed.get("end_signal", False),
            "safety_notes": parsed.get("safety_notes", ""),
            "grounding": parsed.get("grounding", [])
        }
    except json.JSONDecodeError as e:
        print(f"LLM 응답 파싱 실패: {e}")
        print(f"응답 내용: {content[:200]}")
        # 폴백: 첫 번째 문단을 script로 사용
        first_line = content.split('\n')[0].strip()
        return {
            "script": first_line if first_line else "네, 이해했습니다.",
            "followups": [],
            "customer_emotion": "긍정형",
            "next_action": "ask",
            "end_signal": False,
            "safety_notes": "",
            "grounding": []
        }


def to_ssml(script: str, age_group: str) -> str:
    """
    script를 SSML로 변환 (나이대별 속도/음성 조정)
    """
    rate_map = {
        "20s": "1.05",
        "30s": "1.0",
        "40s": "0.95",
        "50s": "0.90",
        "60s 이상": "0.85"
    }
    pitch_map = {
        "20s": "+1st",
        "30s": "0st",
        "40s": "-1st",
        "50s": "-1st",
        "60s 이상": "-2st"
    }
    
    rate = rate_map.get(age_group, "1.0")
    pitch = pitch_map.get(age_group, "0st")
    
    # 줄바꿈을 pause로 변환
    script_cleaned = script.replace('\n', '<break time="200ms"/>')
    
    return f'<speak><prosody rate="{rate}" pitch="{pitch}">{script_cleaned}</prosody></speak>'


def get_situation_defaults(situation_id: str) -> Dict:
    """
    시츄에이션 기본값 반환
    """
    defaults = {
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
            "disclaimer": "환율은 환전 시점의 시장 환율이 적용됩니다."
        },
        "digital": {
            "id": "digital",
            "title": "디지털 뱅킹 상담",
            "goals": ["문제 파악", "해결 방법 안내", "FAQ 제공"],
            "required_slots": ["문제 유형", "기기 종류"],
            "forbidden_claims": ["해결 보장"],
            "style_rules": ["단계별 안내", "스크린샷 추천"],
            "disclaimer": "문제가 지속되면 고객센터로 문의해주세요."
        },
        "complaint": {
            "id": "complaint",
            "title": "민원 처리",
            "goals": ["문제 상황 파악", "공감", "해결 방안 제시"],
            "required_slots": ["문제 내용", "발생 시점"],
            "forbidden_claims": ["빠른 해결 보장"],
            "style_rules": ["공감 표현 우선", "상세 기록 필요"],
            "disclaimer": "민원은 처리 절차에 따라 시간이 소요될 수 있습니다."
        }
    }
    
    return defaults.get(situation_id, defaults["deposit"])

