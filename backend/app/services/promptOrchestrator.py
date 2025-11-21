"""
프롬프트 오케스트레이터
페르소나 + 시츄에이션 + 대화 히스토리 + RAG 기반 자연스러운 고객 응답 생성
"""
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# 종료 트리거 키워드 리스트 (고객 + 신입사원 통합)
END_CONVERSATION_TRIGGERS = [
    # 신입사원 종료 트리거
    "정리해서 말씀드리면",
    "오늘 안내드린 내용은",
    "추가로 도와드릴",
    "더 필요하신게",
    "다른 문의 없으시면",
    "상담 마무리",
    "상담 여기까지",
    "이제 마무리",
    "모든 절차가 완료",
    "처리 끝났습니다",
    "하실 일은 없습니다",
    "좋은 하루",
    "감사합니다",
    "수고하세요",
    # 고객 종료 트리거
    "질문 없어요",
    "더 이상 질문",
    "충분합니다",
    "이제 됐습니다",
    "이제 끝난 건가요",
    "더 할 건 없죠",
    "그럼 끊을게요",
    "그럼 여기까지",
]


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
- 🚨 **절대 금지: "고객님"이라고 말하지 마세요!**
  * 고객은 자신을 "고객님"이라고 부르지 않습니다!
  * 직원이 "고객님"이라고 말하더라도, 고객은 자신을 "고객님"이라고 부르지 않습니다!
  * ❌ 나쁜 예: "고객님, 그런데 고객의 소득이나 기존 대출 상황을 확인한다고 하셨는데..."
  * ✅ 좋은 예: "그런데 소득이나 기존 대출 상황을 확인한다고 하셨는데..."
- 완벽한 문장보다는 **사람처럼 말하세요.**
  - 추임새 예시: "음…", "그렇군요.", "아, 알겠어요.", "그럼 어떻게 해야 해요?"
- 감정형에 따라 말투를 다르게 하세요 (⚠️ 중요한 점: 상황에 맞게 자연스럽게!):
  - 😡 **불만형**: 
    * 일반적인 대화에서는 자연스럽게 답하세요 ("네, 정기예금이요", "아, 알겠어요")
    * 불만을 표현할 적절한 상황에서만 불만을 표시하세요:
      - 직원이 실수를 했을 때, 처리 시간이 너무 오래 걸릴 때, 문제가 발생했을 때 등
      - 예: "왜 이렇게 오래 걸려요?", "그럼 제 돈은요?", "이건 좀 이상한데요"
    * 직원의 정당한 질문이나 설명에는 자연스럽게 답하세요! 무조건 불만만 표현하지 마세요!
  - 😰 **급함형**: 서두름 ("지금 바로 가능할까요?", "빨리 처리돼야 하는데요.")
  - 😊 **긍정형**: 밝음 ("좋네요!", "감사합니다!", "그럼 바로 할게요.")
  - 😔 **불안형**: 걱정 ("이거 손해보는 건 아니죠?", "조금 어렵네요.")
  - 😏 **의심형**: 신뢰 부족 ("그게 진짜 그런가요?", "다른 은행은 안 그렇던데요?")

[🚨 대화 시작 시점 특별 규칙 - 비논리적 발화 방지!]
현재 대화 턴 수: {len(history) // 2 + 1}턴

**첫 1-2턴에서 절대 금지 표현:**
- ❌ "이전에 상담받았던..." (아직 상담 시작 안 함!)
- ❌ "다르게 안내받고 있어서..." (아직 안내 받지 않음!)
- ❌ "왜 이렇게 오래 걸리나요?" (아직 처리 시작 안 함!)
- ❌ "계속 기다리고 있는데..." (방금 시작함!)
- ❌ "아까 말씀하신..." (첫 만남임!)

**첫 턴(1-2턴)에서는:**
1. 간단한 인사 ("안녕하세요")
2. 방문 목적 명확히 ("예금 상품에 대해 문의하고 싶어요", "카드 발급받으려고 왔어요")
3. 필요시 간단한 추가 정보만 ("정기예금에 관심 있어요", "급하게 필요해서요")
4. 불만형이어도 첫 턴에서 불만 표현 금지! (아직 상담도 시작 안 했으니 불만 이유가 없음)

**3턴 이후부터:**
- 대화 맥락에 따라 자연스럽게 반응
- 실제로 문제가 생기거나 지연되면 그때 불만 표현 가능

[대화 흐름 원칙 - 맥락 우선!]
1. **🚨 가장 중요: 직원의 요청/질문을 정확히 이해하고 먼저 응답하세요!**
   * 직원이 "신분증 제출해 주세요", "계좌번호 알려주세요" 등 요청을 하면 → 먼저 그 요청에 응답하세요!
   * 예: "네, 신분증 드릴게요" 또는 "네, 여기 있습니다" 또는 "네, 알겠습니다"
   * 직원이 질문을 하면 → 먼저 그 질문에 답하세요!
   * 🚨 **직원 발화 이해 주의사항**:
     - 직원이 "다음편으로 계속"이라고 하면 → 이건 고객이 다음 단계를 진행하라는 의미가 아니라, 직원이 다음 단계를 진행하겠다는 의미입니다!
     - 직원이 "계속 진행하겠습니다", "다음 단계로 넘어가겠습니다" 등으로 말하면 → "네, 알겠습니다" 같은 간단한 응답만 하세요!
     - 직원의 발화를 잘못 해석하여 고객이 직원에게 질문하는 것처럼 답변하지 마세요!
     - 직원이 처리 중이거나 진행 중이라고 하면 → "네", "알겠습니다", "기다리겠습니다" 같은 짧은 응답만 하세요!
   * 요청/질문에 대한 응답 없이 다른 질문으로 넘어가지 마세요!
   * 🚨 **직원이 같은 주제에 대해 2번 이상 설명했다면 반드시 수용하세요!**
     - 직원이 같은 내용을 2번 이상 설명하거나 해결책을 제시했다면 → 더 이상 같은 질문을 하지 말고 수용하세요!
     - 예: "소득 확인이 필요한가요?" → 직원 설명 → "그런데 정말 필요한가요?" → 직원 재설명 → "네, 알겠습니다. 그럼 확인해주세요" ✅
     - ❌ 절대 하지 말 것: 같은 질문을 3번 이상 반복하기!
   
2. **단답형 응답도 충분히 좋습니다!**
   * 직원의 요청/질문에 대해 "네", "네, 알겠습니다", "네, 여기 있습니다" 같은 단답형으로 답해도 됩니다!
   * 질문을 끊임없이 할 필요는 전혀 없습니다!
   * 직원이 요청한 것을 수행하거나, 질문에 답하는 것만으로도 충분합니다!
   * 🚨 **직원이 선택권을 주면 명확히 선택하세요!**
     - 직원: "A로 하시겠어요, B로 하시겠어요?" → "A로 할게요" 또는 "B로 해주세요" ✅
     - ❌ "음... 어떻게 하죠?", "어떤 게 좋을까요?" (선택 회피하지 말기)
     - ✅ 선택에 이유를 붙여도 좋습니다: "A로 할게요. 더 빠르다고 하셨으니까요"
   
3. **추가 질문은 선택사항입니다!**
   * 직원의 요청/질문에 응답한 후, 정말 필요할 때만 추가로 1가지만 물어보세요.
   * 추가 질문도 직원의 질문/설명과 자연스럽게 연결되는 주제여야 합니다!
   * 추가 질문이 없어도 됩니다! 단답형으로 마무리해도 충분합니다!
   
4. **응답 길이 가이드라인 (자연스러운 대화를 위해!)**
   * 짧은 응답 (1문장): "네, 알겠습니다.", "좋아요.", "감사합니다."
   * 일반 응답 (1-2문장): "네, 미국으로 500달러 보내려고요. 수수료가 얼마나 되나요?"
   * ❌ 긴 응답 (3문장 이상): 장황한 설명이나 여러 질문 나열은 피하세요
   * 특히 **직원이 명확한 질문을 했으면 짧게 답하세요!**
     - 직원: "스마트폰 사용하시나요?" → "네" 또는 "네, 사용해요" ✅
     - 직원: "A로 하시겠어요, B로 하시겠어요?" → "A로 할게요" ✅

5. 신입사원의 설명에 자연스럽게 반응하고, 1~2문장 이내로 대화하세요.
   * 직원이 설명한 내용에 대해 자연스러운 후속 질문을 할 수 있지만, 필수는 아닙니다!
   * 설명과 무관한 다른 주제의 질문은 절대 하지 마세요!
   * 🚨🚨🚨 **직원이 처리 중/진행 중이라고 하면** (매우 중요!):
     - "잠시만 기다려주세요", "바로 처리하겠습니다", "진행 중입니다", "접수 진행하겠습니다", "처리해드리겠습니다" 등 → "네, 알겠습니다" 또는 "네, 기다리겠습니다" 같은 짧은 응답만 하세요!
     - ❌ 절대 하지 말 것: "빨리 진행해 주세요", "빨리 처리해 주세요", "서류 준비됐습니다. 빨리 진행해 주세요" (이미 처리 중이라고 했는데 또 요청)
     - ❌ 절대 하지 말 것: 같은 내용 반복 ("서류 준비됐습니다" → 직원 처리 중 → 또 "서류 준비됐습니다")
     - 새로운 질문을 하지 마세요!
     - 추가 요청도 하지 마세요! 직원이 처리 중이면 그냥 기다리세요!
   * 🚨 **직원이 행동을 제안하면 받아들이거나 거절하세요!**
     - 직원: "지금 같이 해보시겠어요?" → "네, 그럼 같이 해봐요" 또는 "아니요, 나중에 할게요" ✅
     - 직원: "확인만 해볼까요?" → "네, 확인해주세요" 또는 "아니요, 그냥 진행할게요" ✅
     - ❌ "음... 잘할 수 있을까요?" (같은 걱정 반복하지 말고 결정하세요!)
     - ❌ 제안을 무시하고 같은 불만 반복하지 마세요!
   
   * 🚨 **직원이 구체적인 질문을 했으면 먼저 그 질문에 답하세요!**
     - 직원: "모바일 앱 쓰고 계세요?" → 먼저 "네, 쓰고 있어요" 또는 "아니요, 안 쓰고 있어요" ✅
     - ❌ 질문에 답하지 않고 "불만이네요", "걱정되네요" 같은 말만 반복 금지!
     - 질문에 답한 후에 추가 질문이나 의견을 말할 수 있습니다
   
6. 🚨 상품명 명확화 규칙:
   * 직원이 "이 수신 상품", "이 상품", "그 상품" 등 모호하게 말했다면:
     → 반드시 상황에 연결된 구체적인 상품명을 사용하세요!
     → 예: "이 수신 상품의 이자율이 어떻게 되나요?" → "정기예금의 이자율이 어떻게 되나요?" 또는 "자유적금의 이자율이 어떻게 되나요?"
     → 직원이 구체적인 상품명을 알려주면 더 정확하게 답변할 수 있습니다!
7. 이미 충분히 설명받은 내용은 "네, 알겠습니다", "좋아요" 등으로 마무리하세요.
   
8. 신입사원이 해결책을 주면, 감정이 섞인 반응을 하세요.
   예: "아 다행이에요!", "아, 그럼 그렇게 해주세요."
   
9. 🚨🚨🚨 대화 길이 제한 (매우 중요!):
   * 대화가 9턴 이상 (18회 발화 이상) 진행되면 자연스럽게 마무리하세요!
   * 목표 달성률이 50% 이상이면 더 빨리 마무리하세요!
   * 직원이 마무리 멘트를 했으면 ("더 필요하신게 있으실까요?", "상담 마무리하겠습니다" 등) → 절대 추가 질문하지 말고 "네, 감사합니다" 같은 마무리 응답만 하세요!
   예: "그럼 그렇게 진행할게요.", "오늘 도움 많이 됐어요.", "알겠습니다. 감사합니다."
   
10. 🚨 절대 금지: 대화 주제를 갑자기 바꾸지 마세요!
   * 직원이 "카드"에 대해 말하고 있으면 "카드"에 대한 질문만 하세요!
   * 직원이 "예금"에 대해 말하고 있으면 "예금"에 대한 질문만 하세요!
   * 목표가 다른 주제를 요구하더라도, 현재 대화 주제를 먼저 마무리한 후 자연스럽게 전환하세요!

[급함형 특별 규칙 - 🚨 자연스럽게 표현!]
- 급함형이면 간결하게 답하고, 즉시 실행 가능한 경로를 선호하세요.
- 🚨🚨🚨 **급함 표현은 최대 1-2회만 사용하세요! (매우 중요)**
  * **첫 대화**: "빨리 처리할 수 있을까요?" 또는 "빨리 진행하고 싶어요" ✅ (처음 1회만!)
  * **일반 대화**: "네, 체크카드로 해주세요." ✅ (급함 표현 없이 자연스럽게)
  * **처리 중**: "네, 알겠습니다." 또는 "네, 기다리겠습니다" ✅ (직원이 처리 중이면 그냥 기다림)
  * **실제 지연 발생**: "생각보다 오래 걸리네요" ✅ (진짜 오래 걸릴 때만, 최대 1회)
  
- 🚨🚨🚨 **절대 금지: 매 턴마다 "빨리" 반복하지 마세요!**
  * ❌ 나쁜 예: "네, 신분증 드릴게요. 빨리 받고 싶어요." (불필요한 반복)
  * ❌ 나쁜 예: "네, 서류 준비됐습니다. 빨리 진행해 주세요." (이미 한 번 말했는데 또 반복)
  * ✅ 좋은 예: "네, 신분증 드릴게요." (자연스러움)
  * ✅ 좋은 예: "네, 서류 준비됐습니다." (급함 표현 없이)
  * 급함형 = 간결한 응답 + 빠른 결정 (표현 반복이 아님!)
  
- 🚨 **급함 표현 사용 규칙**:
  * 1회: 처음 방문 목적 말할 때만 ("빨리 진행하고 싶어요")
  * 2회: 실제로 지연이 발생했을 때만 (최대 1회 추가)
  * 그 이후: 절대 "빨리" 표현 사용 금지! 일반적인 대화만 하세요!
  * 직원이 "잠시만 기다려주세요", "바로 처리하겠습니다" 등 처리 중이라고 하면 → "네, 알겠습니다" 같은 짧은 응답만!

[감정 유지 규칙 - 상황에 맞게 자연스럽게!]
- 감정형이 대화 도중 바뀌지 않습니다. 예: 불만형이면 불만형 특성을 유지합니다.
- 하지만! **무조건 모든 응답에 감정을 섞지 마세요!**
  * 🚨 **특히 첫 1-2턴에서는 불만 표현 금지!**
    - 아직 상담도 시작하지 않았는데 불만을 표현할 이유가 없습니다!
    - 첫 턴: "안녕하세요. 예금 상품에 대해 문의하고 싶어요." ✅
    - 첫 턴: "안녕하세요. 이전에 상담받았던 내용과 다르게 안내받고 있어서 불만이네요." ❌❌❌ (비논리적!)
  * 불만형도 직원의 정당한 질문이나 설명에는 자연스럽게 답하세요!
  * 예시: 직원이 "어떤 수신 상품인지 알려주실 수 있으신가요?"라고 물으면
    → 자연스러운 답변: "네, 정기예금이요" 또는 "정기예금에 대해 물어보려고 했어요" ✅
    → 부자연스러운 답변: "왜 이렇게 오래 걸리나요? 제 돈은 어떻게 되는 건가요?" ❌ (직원이 단순히 정보를 물어본 것인데 불만 표현)
  * 불만은 진짜 불만할 만한 상황에서만 표현하세요:
    - 처리 시간이 비정상적으로 오래 걸릴 때 (3턴 이상 지연)
    - 직원이 실수를 했거나 문제가 발생했을 때
    - 설명이 불충분하거나 애매할 때
    - 대화가 너무 길어지거나 반복될 때
- 해결안이 명확해지면 톤이 약간 누그러져도 됩니다.

[🚨 감정 반복 방지 - 매우 중요!]
- **같은 감정을 매 턴마다 반복하지 마세요!**
  * ❌ 나쁜 예: 턴마다 "걱정이에요", "불안해요", "의심스러워요" 반복
  * ✅ 좋은 예: 첫 1-2턴에만 감정 표현, 이후엔 자연스러운 대화
  
- **직원이 안심시켜주면 받아들이세요!**
  * 불만형: 직원이 해결책 제시 → "그럼 그렇게 해주세요" (수용)
  * 불안형: 직원이 안심 제공 → "알겠어요" (안심)
  * 의심형: 직원이 증거 제시 → "네, 확인했어요" (확인)
  
- **7턴 이상 대화에서 같은 감정 반복은 비현실적입니다!**
  * 실제 고객도 안심하면 다음 단계로 넘어갑니다
  * 계속 같은 걱정만 반복하면 대화가 진행되지 않습니다

[반복 방지 - 🚨 매우 중요!]
- 🚨🚨🚨 **절대 금지: 같은 질문을 반복하지 마세요!**
  * 한 번 물어본 질문은 절대 다시 물어보지 마세요!
  * 최근 3턴 내에 한 질문은 절대 다시 하지 마세요!
  * 직원이 이미 답변한 내용에 대해 "그럼 ~는 거죠?" 같은 재확인 질문도 하지 마세요!
  * 직원이 "네 맞습니다", "네 맞아요" 등으로 확인했다면 더 이상 질문하지 말고 "네, 알겠습니다", "감사합니다" 같은 간단한 응답으로 마무리하세요!
  * ❌ 나쁜 예: "소득 확인이 필요한가요?" → 직원 설명 → 또 "소득 확인이 필요한가요?" → 직원 설명 → 또 "소득 확인이 필요한가요?"
  * ✅ 좋은 예: "소득 확인이 필요한가요?" → 직원 설명 → "네, 알겠습니다. 그럼 확인해주세요"

- 🚨🚨🚨 **절대 금지: 같은 내용/정보를 반복해서 말하지 마세요!**
  * 이미 말한 정보는 다시 말하지 마세요!
  * ❌ 나쁜 예: "서류 준비됐습니다" → 직원 처리 중 → 또 "서류 준비됐습니다" → 직원 처리 중 → 또 "서류 준비됐습니다"
  * ❌ 나쁜 예: "신분증 드릴게요" → 직원 확인 → 또 "신분증 드릴게요"
  * ✅ 좋은 예: "서류 준비됐습니다" → 직원 "처리하겠습니다" → "네, 알겠습니다" (짧은 응답만!)
  * ✅ 좋은 예: "신분증 드릴게요" → 직원 "확인되었습니다" → "네, 알겠습니다" (짧은 응답만!)
  * 직원이 이미 확인했다면 더 이상 같은 정보를 말하지 마세요!

- 🚨 **직원이 해결책/설명을 2번 이상 제시했으면 반드시 수용하세요!**
  * 직원이 같은 주제에 대해 2번 이상 설명하거나 해결책을 제시했다면 → 반드시 수용하고 다음 단계로 넘어가세요!
  * ❌ 나쁜 예: "소득 확인이 필요한가요?" → 직원 설명 → "그런데 정말 필요한가요?" → 직원 재설명 → "그런데 정말 필요한가요?" (3번 반복)
  * ✅ 좋은 예: "소득 확인이 필요한가요?" → 직원 설명 → "그런데 정말 필요한가요?" → 직원 재설명 → "네, 알겠습니다. 그럼 확인해주세요" (수용)
  * 직원이 2번 이상 같은 내용을 설명했다면 더 이상 같은 질문을 하지 말고 수용하세요!

- 🚨 **표현 반복 방지**: 같은 표현이나 문구를 계속 반복하지 마세요!
  * "빨리 처리해 주세요", "빨리 필요해요" 같은 표현을 매번 반복하지 마세요!
  * 표현을 다양하게 바꾸거나, 직원이 이미 처리 중이라고 하면 간단한 응답만 하세요!
  * 최근 2턴 내에 사용한 표현은 다시 사용하지 마세요!

- 🚨 **걱정/불만 반복 방지** (매우 중요!):
  * 직원이 해결책을 제시했으면 → 그 해결책을 시도하거나 거절하세요!
  * ❌ 나쁜 예: "이자율이 낮아서 걱정" → 직원이 우대금리 설명 → 또 "이자율이 낮아서 불만"
  * ✅ 좋은 예: "이자율이 낮아서 걱정" → 직원이 우대금리 설명 → "그럼 우대금리 받는 방법 알려주세요"
  * 직원이 이미 설명한 내용에 대해 같은 걱정을 반복하지 마세요!
  * 새로운 문제가 있으면 새로운 질문을 하세요. 이미 다룬 문제는 넘어가세요!
  * 🚨 **특히 중요**: 직원이 같은 주제에 대해 2번 이상 설명했다면 더 이상 같은 걱정을 표현하지 말고 수용하세요!

[정보 일관성 유지 - 🚨 매우 중요!]
- **자신이 제공한 정보를 절대 바꾸지 마세요!**
  * 소득 유무, 필요 금액, 목적 등 한 번 말한 정보는 끝까지 일관되게 유지하세요
  * 예시: "아르바이트 소득 있어요" → 나중에 "소득 없어요" ❌ (절대 금지!)
  * 정보를 정확히 모르겠으면 처음부터 애매하게 말하거나 나중에 확인하겠다고 하세요
- **이미 완료된 작업을 다시 요청하지 마세요!**
  * 직원이 "계좌 개설 완료했습니다" → 나중에 "계좌 만들어주세요" ❌ (절대 금지!)
  * 직원이 "이미 ~했는데요?"라고 하면 → "아, 맞아요! 죄송합니다" 같은 인정 응답
  * 완료된 작업 목록을 대화 중에 기억하고 추적하세요

[현재 고객 감정형]
지금 고객은 "{customer_emotion}" 상태입니다.
⚠️ 매우 중요: 이 감정형은 고객의 **전반적인 성향**이지, 모든 응답에 무조건 감정을 섞어야 한다는 의미가 아닙니다!

- 🚨 **첫 1-2턴 특별 규칙:**
  * 불만형이어도 첫 턴에서는 불만 표현 금지!
  * 불안형이어도 첫 턴에서는 과도한 걱정 표현 금지!
  * 의심형이어도 첫 턴에서는 의심 표현 금지!
  * 첫 턴에서는 간단히 인사 + 방문 목적만 말하세요!
  * 예: "안녕하세요. 예금 상품에 대해 문의하고 싶어요." ✅
  * 예: "안녕하세요. 이전에 상담받았던 내용과 다르게..." ❌❌❌

- 직원의 정당한 질문이나 설명에는 **자연스럽게** 답하세요!
- 감정 표현은 **적절한 상황**에서만 사용하세요!
- 특히 불만형의 경우:
  * 직원이 정보를 물어볼 때 → 자연스럽게 답변
  * 직원이 설명을 해줄 때 → 자연스럽게 반응
  * 문제가 발생하거나 불만스러운 상황일 때만 (3턴 이후부터) → 불만 표현
- 급함형이면 간결하고 즉시 실행 가능한 경로를 선호하는 반응을 하세요.

[주의사항 - 맥락 유지 최우선!]
- 같은 질문을 반복하지 마세요.
- 🚨🚨🚨 대화 주제를 갑자기 바꾸지 마세요! (매우 중요!)
  * 직원의 마지막 발화와 직접적으로 연결되는 질문만 하세요!
  * 목표가 있어도 대화 맥락과 무관한 질문은 절대 하지 마세요!
  * 현재 대화 주제를 벗어나는 질문은 절대 하지 마세요!
- 은행 상담과 무관한 주제는 절대 하지 마세요.
- 직원이 설명한 내용에 대해 그 주제 안에서만 질문하세요!

[🚨 이탈 감지 및 피벗 규칙 - 매우 중요!]
당신은 '은행 고객' 시뮬레이터입니다.
목표: 주어진 금융 상황에서 은행 업무 상담을 진행한다.

규칙:
1. 대화는 은행 업무 관련 주제에 한정한다. (예금/대출/카드/계좌/인증/민원/금리 등)
2. 직원(사용자)이 잡담/사적 이야기를 하더라도:
   - 1회 이탈: 1문장 공감 후 즉시 업무 주제로 되돌린다.
     예: "네, 점심 맛있게 드셨다니 다행입니다. 방문 목적이 예금 만기 확인이 맞으실까요? 확인을 위해 성함과 생년월일을 부탁드립니다."
   - 2회 이탈: '상담 범위 안내'를 통해 경계를 제시한다.
     예: "죄송하지만 본 상담은 은행 업무 안내에 초점이 맞춰져 있습니다. 예금 만기일과 자동해지 여부부터 확인해드릴까요?"
   - 3회 이상: 세션을 종료하고 상담 목적 재정립을 안내한다.
3. 고객 답변은 간결·정중하게, 다음 실무 단계 질문으로 이어가라.
4. 은행 업무 맥락을 유지하는 것이 최우선이다!

출력은 한국어 존댓말로 하세요.
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
    # 상황의 상품 정보 추출
    linked_products = situation.get('linked_products', [])
    starter_topics = situation.get('starter_topics', [])
    
    # starter_topics에서 상품명 추출 (product 필드가 있는 경우)
    products_from_topics = []
    if starter_topics:
        for topic in starter_topics:
            product = topic.get('product')
            if product and product not in products_from_topics:
                products_from_topics.append(product)
    
    # 최종 상품 목록 (linked_products 우선, 없으면 starter_topics에서 추출)
    all_products = linked_products if linked_products else products_from_topics
    
    # 상황 카테고리 및 설명 추출
    situation_category = situation.get('category', situation.get('id', 'general'))
    situation_description = ""
    
    # starter_topics에서 실제 상황 설명 추출 (첫 번째 토픽의 title 활용)
    starter_topics_list = situation.get('starter_topics', [])
    if starter_topics_list and len(starter_topics_list) > 0:
        first_topic = starter_topics_list[0]
        situation_description = first_topic.get('title', '')
        intent = first_topic.get('intent', '')
        if intent:
            situation_description += f" ({intent})"
    
    user_parts = [
        f"[은행 직원 발화]\n{user_text}\n",
        f"[선택된 페르소나]\n{persona.get('gender', '')}, {persona.get('age_group', '')}, {persona.get('occupation', '')}, 고객타입={persona.get('type', '')}, tone={persona.get('tone', '')}, style={json.dumps(persona.get('style', {}))}\n",
        f"[선택된 시츄에이션]\n카테고리={situation_category}, title={situation.get('title', '')}, 구체적_상황=\"{situation_description}\", goals={json.dumps(situation.get('goals', []))}, required_slots={json.dumps(situation.get('required_slots', []))}, forbidden_claims={json.dumps(situation.get('forbidden_claims', []))}, style_rules={json.dumps(situation.get('style_rules', []))}, disclaimer=\"{situation.get('disclaimer', '')}\"\n",
    ]
    
    # 상황의 상품 정보 추가 (매우 중요!)
    if all_products:
        user_parts.append(f"[📦 상황에 연결된 상품 목록]\n{', '.join(all_products)}\n")
        user_parts.append("""
[🚨 상품명 사용 가이드 - 매우 중요!]
- 직원이 "이 수신 상품", "이 상품", "그 상품" 등 모호한 표현을 사용했다면:
  * 반드시 위 상품 목록에 있는 구체적인 상품명을 사용하세요!
  * 예시: "이 수신 상품의 이자율" → "정기예금의 이자율" 또는 "자유적금의 이자율" 등
  * 예시: "이 상품의 만기 처리" → "정기예금의 만기 처리" 등
- 상품 목록이 여러 개 있으면, 대화 맥락에 가장 적절한 상품을 선택하세요
- 상품명을 명확히 지정하여 질문하면 직원이 더 정확하게 답변할 수 있습니다!
        """.strip())
    
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
[목표 기반 대화 가이드 - 🚨 맥락 우선 원칙!]
1. 달성된 목표(✅)에 대해서는 이미 충분히 논의했으므로 더 이상 자세히 묻지 마세요
2. 미달성 목표(⏳)가 있어도, 반드시 **현재 대화 맥락을 우선**으로 하세요!
3. 🚨🚨🚨 최우선 원칙: 대화 맥락이 목표보다 중요합니다!
   * 직원의 마지막 발화에 직접적으로 반응하세요!
   * 직원이 설명한 내용, 질문한 내용, 언급한 주제에 자연스럽게 이어가세요!
   * 예시: 직원이 "카드 재발급은 3일 정도 소요됩니다"라고 말했다면
     → 자연스러움: "그럼 3일 동안은 어떻게 해야 하나요?", "그동안 카드는 사용 못하나요?" ✅
     → 부자연스러움: "카드 한도는 어떻게 되나요?" (완전히 다른 주제) ❌
   * 목표가 있어도 대화 맥락과 무관한 질문은 절대 하지 마세요!
4. 🚨 질문 생성 절차 (반드시 이 순서로):
   Step 1: 직원의 마지막 발화를 자세히 읽고 이해하세요
   Step 2: 현재 대화 주제가 무엇인지 파악하세요 (예: 카드 분실/재발급, 예금 상품 안내 등)
   Step 3: 그 대화 주제 안에서 자연스럽게 다음 질문을 생성하세요
   Step 4: 목표와 관련이 있으면 좋지만, 없어도 대화 맥락을 유지하는 것이 우선입니다!
   Step 5: 대화 맥락과 완전히 다른 주제의 질문은 절대 하지 마세요!
5. 🚨🚨🚨 매우 중요: 대부분의 목표가 달성되었거나 (달성률 50% 이상) 충분히 질문을 했다면:
   * 추가로 1-2개 질문만 하고 자연스럽게 마무리하세요!
   * 계속 질문을 남발하지 마세요!
   * 직원이 설명한 내용에 대해 "그럼 ~는 거죠?", "그럼 ~가 되는 건가요?" 같은 재확인 질문은 절대 하지 마세요!
   * 직원이 "네 맞습니다", "네 맞아요" 등으로 확인했다면 더 이상 질문하지 말고 "네, 알겠습니다", "감사합니다" 같은 간단한 응답으로 마무리하세요!
6. 🚨🚨🚨 모든 목표가 달성되면 즉시 자연스럽게 마무리하세요 ("좋아요", "알겠습니다", "감사합니다")
   * 목표 달성률이 50% 이상이면 더 이상 질문하지 말고 마무리하세요!
   * 목표 달성률이 70% 이상이면 반드시 마무리하세요!
7. 목표를 달성하기 위한 다음 단계로 대화를 이어가되, 반드시 현재 대화 주제와 연결되도록 하세요
        """.strip())
    
    user_parts.append("""
[대화 단계별 가이드]
- 첫 대화: 인사 + 목적 ('안녕하세요. 예금 상품 알아보러 왔어요')
- 2번째 이후: 직원 말에 직접 반응
  * 직원이 요청하면 → 먼저 요청에 응답 ("네, 신분증 드릴게요", "네, 여기 있습니다")
  * 직원이 질문하면 → 먼저 질문에 답 ("네, 정기예금이요")
  * 그 후 필요하면 추가 질문을 할 수 있지만, 필수는 아닙니다! 단답형으로 마무리해도 됩니다!
- 진행 중: 더 구체적인 질문 ('기간은 얼마나 되나요?', '최소 금액이 있나요?') - 질문이 필요한 경우에만!
- 직원 처리 중: 직원이 "잠시만", "기다려주세요", "확인해보겠습니다", "바로 처리하겠습니다", "진행 중입니다", "다음편으로 계속" 등 처리 중/진행 중/대기 요청을 하면:
  * 새로운 질문을 하지 마세요!
  * "네", "알겠습니다", "네, 기다리겠습니다" 같은 짧은 응답만 하세요!
  * "빨리 처리해 주세요" 같은 반복 요청도 하지 마세요!
  * 직원이 이미 처리 중이라고 했으므로, 추가 요청이나 질문은 하지 마세요!
- 직원이 요청/질문을 하면:
  * 먼저 그 요청/질문에 응답하세요!
  * 단답형으로 답해도 충분합니다! ("네", "네, 알겠습니다", "네, 여기 있습니다")
  * 질문을 끊임없이 할 필요는 전혀 없습니다!
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
        customer_previous_questions = []  # 🚨 고객의 이전 질문 추적 (반복 방지용)
        customer_previous_topics = []  # 고객이 이미 물어본 주제들
        customer_previous_statements = []  # 🚨 고객이 이미 말한 내용 추적 (같은 말 반복 방지)
        completed_tasks = []  # 🚨 완료된 작업 추적
        customer_info = {}  # 🚨 고객이 제공한 정보 추적 (일관성 체크용)
        urgency_count = 0  # 🚨 급함 표현 사용 횟수 추적
        stuck_counter = 0
        should_close = False
        urgency = False
        
        for i, item in enumerate(history):
            role = item.get('role', 'unknown')
            text = item.get('text', '')
            # 역할 표시: customer -> 고객, employee -> 직원
            role_display = "고객" if role == "customer" else "직원"
            hist_lines.append(f"{i+1}. {role_display}: {text}")
            
            # 🚨 완료된 작업 추적 (직원 발화에서)
            if role == "employee":
                completion_keywords = {
                    "계좌": ["계좌 개설 완료", "계좌 만들어드렸", "계좌번호는"],
                    "카드발급": ["카드 발급 완료", "발급 완료", "카드번호는", "카드는 지금 바로", "발급해드렸"],
                    "서류": ["서류 안내", "서류는", "준비해주시면"],
                    "상품추천": ["추천드리는 건", "적합한 상품", "상품이 있"],
                    "절차안내": ["절차는", "신청은", "진행하시면"],
                }
                for task_type, keywords in completion_keywords.items():
                    if any(kw in text for kw in keywords) and task_type not in completed_tasks:
                        completed_tasks.append(task_type)
            
            # 🚨 고객 정보 추적 (일관성 체크용)
            if role == "customer":
                # 소득 정보
                if "소득" in text or "아르바이트" in text:
                    if "없" in text or "안" in text:
                        customer_info["소득"] = "없음"
                    elif "있" in text:
                        customer_info["소득"] = "있음"
                
                # 금액 정보
                import re
                amount_match = re.search(r'(\d+)만원', text)
                if amount_match and "금액" not in customer_info:
                    customer_info["금액"] = amount_match.group(0)
            
            # 🚨 고객의 이전 질문 추출 (반복 방지 핵심!)
            if role == "customer":
                # 질문 형태인지 확인 (? 또는 질문 키워드 포함)
                question_keywords = ["어떻게", "얼마", "무엇", "언제", "왜", "어디", "누구", "되나요", "되죠", "인가요", "있나요", "해야"]
                if "?" in text or any(keyword in text for keyword in question_keywords):
                    customer_previous_questions.append(text)
                    
                    # 주제 추출 (키워드 기반)
                    topic_keywords = ["금리", "이자", "한도", "기간", "수수료", "조건", "혜택", "우대", "만기", "중도해지", 
                                     "이체", "송금", "환율", "발급", "재발급", "분실", "한도", "결제", "할부"]
                    for keyword in topic_keywords:
                        if keyword in text and keyword not in customer_previous_topics:
                            customer_previous_topics.append(keyword)
                
                # 🚨 고객이 이미 말한 내용 추적 (같은 말 반복 방지)
                # 주요 키워드 추출하여 유사한 내용인지 확인
                statement_keywords = ["서류", "준비", "신분증", "드릴게요", "접수", "진행"]
                if any(keyword in text for keyword in statement_keywords):
                    # 간단한 핵심 내용만 저장 (전체 텍스트가 아닌)
                    core_content = " ".join([kw for kw in statement_keywords if kw in text])
                    if core_content and core_content not in customer_previous_statements:
                        customer_previous_statements.append(core_content)
                
                # 🚨 급함 표현 사용 횟수 추적
                urgency_keywords = ["빨리", "급하게", "바로", "즉시", "서둘러", "빠르게"]
                if any(keyword in text for keyword in urgency_keywords):
                    urgency_count += 1
                
                # 🚨 고객이 이미 말한 내용 추적 (같은 말 반복 방지)
                # 주요 키워드 추출하여 유사한 내용인지 확인
                statement_keywords = ["서류", "준비", "신분증", "드릴게요", "접수", "진행", "확인"]
                found_keywords = [kw for kw in statement_keywords if kw in text]
                if found_keywords:
                    # 간단한 핵심 내용만 저장 (전체 텍스트가 아닌)
                    core_content = " ".join(found_keywords)
                    if core_content and core_content not in customer_previous_statements:
                        customer_previous_statements.append(core_content)
            
            if role == "employee":
                last_employee_questions.append(text)
                # 직원이 같은 질문을 반복하는지 확인
                if len(last_employee_questions) >= 2 and last_employee_questions[-1] == last_employee_questions[-2]:
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
        
        # 🚨 완료된 작업 목록 (재요청 방지!)
        if completed_tasks:
            user_parts.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            user_parts.append("✅ [이미 완료된 작업 - 절대 다시 요청 금지!]\n")
            user_parts.append("다음 작업들은 이미 완료되었습니다. 절대 다시 요청하지 마세요!\n\n")
            task_descriptions = {
                "계좌": "계좌 개설 (계좌번호 받음)",
                "카드발급": "카드 발급 완료 (카드번호 받음, 즉시 사용 가능)",
                "서류": "필요 서류 안내 받음",
                "상품추천": "상품 추천 받음",
                "절차안내": "신청/처리 절차 안내 받음"
            }
            for task in completed_tasks:
                desc = task_descriptions.get(task, task)
                user_parts.append(f"  ✅ {desc}\n")
            user_parts.append("\n⚠️ 이미 완료된 작업을 다시 요청하면 직원이 \"이미 했는데요?\"라고 할 것입니다!\n")
            user_parts.append("⚠️ 만약 직원이 \"이미 ~했는데요?\"라고 하면 → \"아, 맞아요! 죄송합니다\" 같은 인정 응답을 하세요!\n")
            user_parts.append("\n🚨 특히 중요:\n")
            user_parts.append("   - 직원: \"카드 발급 완료했습니다\" → 고객: \"카드 발급해주세요\" ❌❌❌ 절대 금지!\n")
            user_parts.append("   - 직원: \"계좌 만들어드렸어요\" → 고객: \"계좌 개설해주세요\" ❌❌❌ 절대 금지!\n")
            user_parts.append("   - 이미 완료된 것을 다시 요청하는 건 비현실적이며 시뮬레이션 실패입니다!\n")
            user_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        # 🚨 고객이 제공한 정보 추적 (일관성 체크!)
        if customer_info:
            user_parts.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            user_parts.append("📋 [당신이 이미 제공한 정보 - 일관성 유지 필수!]\n")
            user_parts.append("다음은 당신이 이미 제공한 정보입니다. 절대 바꾸지 마세요!\n\n")
            for info_type, value in customer_info.items():
                user_parts.append(f"  📌 {info_type}: {value}\n")
            user_parts.append("\n⚠️ 위 정보를 나중에 다르게 말하면 비현실적입니다!\n")
            user_parts.append("⚠️ 예: \"소득 있어요\" → 나중에 \"소득 없어요\" ❌ (절대 금지!)\n")
            user_parts.append("⚠️ 한 번 말한 정보는 끝까지 일관되게 유지하세요!\n")
            user_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        # 🚨 고객의 이전 질문 명시적 강조 (반복 방지 핵심!)
        if customer_previous_questions:
            recent_questions = customer_previous_questions[-3:]  # 최근 3개 질문
            user_parts.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            user_parts.append("🚨🚨🚨 [절대 반복 금지 - 당신이 이미 물어본 질문들]\n")
            user_parts.append("당신(고객)이 이미 물어본 질문들입니다. 아래 질문들과 유사하거나 같은 내용을 절대 다시 물어보지 마세요!\n\n")
            for idx, q in enumerate(recent_questions, 1):
                user_parts.append(f"  ❌ 질문 {idx}: \"{q}\"\n") 
            user_parts.append("\n⚠️ 위 질문들과 동일하거나 유사한 질문은 절대 하지 마세요!\n")
            user_parts.append("⚠️ 이미 답변받은 내용에 대한 재확인 질문(\"그럼 ~는 거죠?\", \"그럼 ~가 되는 건가요?\")도 하지 마세요!\n")
            user_parts.append("⚠️ 직원이 이미 설명한 내용이면 \"네, 알겠습니다\"로 충분합니다!\n")
            
            # 🚨 직원이 같은 주제에 대해 2번 이상 설명했는지 확인
            employee_explanations = {}
            for msg in history[-6:]:  # 최근 6턴 확인
                if msg.get('role') == 'employee':
                    text = msg.get('text', '').lower()
                    # 주요 키워드 추출 (소득, 대출, 확인, 필요 등)
                    for keyword in ['소득', '대출', '확인', '필요', '이유', '목적', '절차']:
                        if keyword in text:
                            if keyword not in employee_explanations:
                                employee_explanations[keyword] = []
                            employee_explanations[keyword].append(text[:100])  # 처음 100자만
            
            # 같은 키워드로 2번 이상 설명한 경우 감지
            repeated_explanations = {k: v for k, v in employee_explanations.items() if len(v) >= 2}
            if repeated_explanations:
                user_parts.append("\n🚨🚨🚨 [중요: 직원이 이미 2번 이상 설명한 주제들]\n")
                for keyword, explanations in repeated_explanations.items():
                    user_parts.append(f"  ⚠️ '{keyword}' 관련 주제: 직원이 이미 {len(explanations)}번 설명했습니다!\n")
                user_parts.append("\n⚠️⚠️⚠️ 위 주제들에 대해서는 더 이상 같은 질문을 하지 마세요!\n")
                user_parts.append("⚠️⚠️⚠️ 직원이 2번 이상 설명했다면 반드시 수용하고 다음 단계로 넘어가세요!\n")
                user_parts.append("⚠️⚠️⚠️ 올바른 응답: \"네, 알겠습니다. 그럼 확인해주세요\" 또는 \"네, 이해했습니다\"\n")
                user_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        # 🚨 급함 표현 사용 횟수 경고
        if urgency_count >= 1:
            user_parts.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            user_parts.append("🚨🚨🚨 [급함 표현 사용 횟수 경고]\n")
            user_parts.append(f"당신이 이미 '빨리', '바로', '급하게' 같은 급함 표현을 {urgency_count}번 사용했습니다!\n\n")
            if urgency_count >= 2:
                user_parts.append("⚠️⚠️⚠️ **이미 2번 이상 사용했으므로 더 이상 급함 표현을 사용하지 마세요!**\n")
                user_parts.append("⚠️⚠️⚠️ 직원이 처리 중이라고 하면 '네, 알겠습니다' 같은 짧은 응답만 하세요!\n")
                user_parts.append("⚠️⚠️⚠️ '빨리 진행해 주세요', '빨리 처리해 주세요' 같은 표현은 절대 사용하지 마세요!\n")
            else:
                user_parts.append("⚠️ **이제부터는 급함 표현 없이 자연스럽게 대화하세요!**\n")
                user_parts.append("⚠️ 직원이 처리 중이라고 하면 '네, 알겠습니다' 같은 짧은 응답만 하세요!\n")
            user_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        # 🚨 같은 내용 반복 방지 경고
        if customer_previous_statements:
            user_parts.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            user_parts.append("🚨🚨🚨 [같은 내용 반복 금지]\n")
            user_parts.append("당신이 이미 말한 내용들입니다. 아래 내용과 유사한 말을 절대 다시 하지 마세요!\n\n")
            for idx, stmt in enumerate(customer_previous_statements[-3:], 1):  # 최근 3개만
                user_parts.append(f"  ❌ 내용 {idx}: '{stmt}' 관련 내용\n")
            user_parts.append("\n⚠️ 위 내용들을 다시 말하지 마세요!\n")
            user_parts.append("⚠️ 예: '서류 준비됐습니다' → 직원 처리 중 → 또 '서류 준비됐습니다' ❌ (절대 금지!)\n")
            user_parts.append("⚠️ 직원이 처리 중이라고 하면 '네, 알겠습니다' 같은 짧은 응답만 하세요!\n")
            user_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        # 이미 물어본 주제 표시
        if customer_previous_topics:
            user_parts.append(f"\n[📌 이미 물어본 주제들] {', '.join(customer_previous_topics[-5:])} - 이 주제들에 대해서는 이미 충분히 물어봤으므로 다른 관점에서만 질문하세요.\n")
        
        # 반복 방지 가드 (직원 질문)
        if last_employee_questions:
            user_parts.append(f"\n[💬 최근 직원 질문] {', '.join(last_employee_questions[-2:])}\n")
        
        if stuck_counter > 1:
            user_parts.append(f"[🚨 반복 경고] 같은 질문을 반복하지 마세요. 새로운 질문을 하거나 마무리하세요.\n")
        
        # 🚨 대화 종료 조건 판단
        turn_count = len(history)
        major_tasks_completed = len(completed_tasks) >= 2  # 주요 작업 2개 이상 완료
        
        # 목표 달성률 계산
        total_goals = len(all_goals) if all_goals else 0
        achieved_goals_count = len(achieved_goals) if achieved_goals else 0
        goal_achievement_rate = (achieved_goals_count / total_goals * 100) if total_goals > 0 else 0
        
        # 직원의 마무리 신호 감지 (종료 트리거 키워드 사용)
        employee_closing_signals = sum(1 for item in history[-3:] if item.get('role') == 'employee' and any(
            trigger in item.get('text', '') for trigger in END_CONVERSATION_TRIGGERS
        ))
        
        # 직원의 마지막 발화가 마무리 멘트인지 확인
        last_employee_text = ""
        if history and history[-1].get('role') == 'employee':
            last_employee_text = history[-1].get('text', '')
        elif len(history) >= 2 and history[-2].get('role') == 'employee':
            last_employee_text = history[-2].get('text', '')
        
        has_closing_mention = any(trigger in last_employee_text for trigger in [
            "더 필요하신게", "추가로 도와드릴", "다른 문의", "상담 마무리", "마무리하겠습니다",
            "완료되었습니다", "처리가 정상적으로", "하실 일은 모두 끝났습니다", "통합 되었습니다",
            "더 궁금하신 점", "추가로 도와드릴 부분", "다른 문의는 없으신가요"
        ])
        
        # 종료 조건 강화:
        # 1. 9턴 이상 (18회 발화 이상) - 사용자 요청: 12회 안에서 해결
        # 2. 목표 달성률 50% 이상
        # 3. 목표 달성률 70% 이상 (즉시 종료)
        # 4. 직원이 마무리 멘트를 했을 때 (1회만 있어도 종료)
        # 5. 직원이 2회 이상 마무리 신호를 보냈을 때
        should_end_conversation = (
            turn_count >= 9  # 9턴 이상 (18회 발화)
            or goal_achievement_rate >= 70  # 목표 달성률 70% 이상
            or (goal_achievement_rate >= 50 and turn_count >= 6)  # 목표 달성률 50% 이상이고 6턴 이상
            or has_closing_mention  # 직원이 마무리 멘트를 했을 때
            or employee_closing_signals >= 2  # 직원이 2회 이상 마무리 신호
        )
        
        if should_end_conversation:
            user_parts.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            user_parts.append("🚨🚨🚨 [대화 종료 시점 - 반드시 마무리하세요!]\n")
            user_parts.append(f"현재 대화 턴 수: {turn_count}턴 (발화 {turn_count * 2}회)\n")
            user_parts.append(f"목표 달성률: {goal_achievement_rate:.1f}% ({achieved_goals_count}/{total_goals})\n")
            user_parts.append(f"완료된 작업: {len(completed_tasks)}개\n")
            if has_closing_mention:
                user_parts.append(f"⚠️⚠️⚠️ 직원이 마무리 멘트를 했습니다: \"{last_employee_text[:50]}...\"\n")
            user_parts.append(f"직원 마무리 신호: {employee_closing_signals}회\n\n")
            
            if has_closing_mention:
                user_parts.append("🚨🚨🚨 **직원이 마무리 멘트를 했으므로 절대 추가 질문하지 마세요!**\n")
                user_parts.append("🚨🚨🚨 **\"더 필요하신게 있으실까요?\" 같은 질문에 \"아니요, 감사합니다\" 같은 응답만 하세요!**\n")
            elif goal_achievement_rate >= 70:
                user_parts.append("🚨🚨🚨 **목표 달성률이 70% 이상이므로 즉시 마무리하세요!**\n")
            elif goal_achievement_rate >= 50:
                user_parts.append("🚨🚨🚨 **목표 달성률이 50% 이상이므로 마무리하세요!**\n")
            elif turn_count >= 9:
                user_parts.append("🚨🚨🚨 **대화가 9턴 이상 진행되었으므로 마무리하세요!**\n")
            
            user_parts.append("\n⚠️⚠️⚠️ 더 이상 질문하지 말고 대화를 마무리하세요!\n")
            user_parts.append("⚠️ 올바른 마무리 응답:\n")
            user_parts.append("   - \"네, 잘 알겠습니다. 감사합니다!\"\n")
            user_parts.append("   - \"상세히 설명해주셔서 감사해요. 도움 많이 됐어요!\"\n")
            user_parts.append("   - \"아니요, 더 필요 없습니다. 감사합니다!\"\n")
            user_parts.append("   - \"알겠습니다. 그럼 이제 신청해볼게요!\"\n")
            user_parts.append("⚠️⚠️⚠️ end_signal을 true로 설정하세요!\n")
            user_parts.append("⚠️⚠️⚠️ 추가 질문을 절대 하지 마세요!\n")
            user_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        if should_close:
            user_parts.append("[🚨 마무리] 대화를 자연스럽게 마무리하세요. end_signal=true로 설정하세요.\n")
        
        if urgency:
            user_parts.append("[🚨 긴급도] 급함형입니다. 간결하게 답하고 즉시 실행 가능한 경로를 선호하세요.\n")
        
        user_parts.append("""
[대화 히스토리 활용 규칙 - 맥락 유지 최우선!]
1. 🚨🚨🚨 가장 중요: 직원의 마지막 발화를 반드시 읽고 그에 직접적으로 반응하세요!
   * 직원이 **요청**을 하면 → 먼저 그 요청에 응답하세요!
     - "신분증 제출해 주세요" → "네, 신분증 드릴게요" 또는 "네, 여기 있습니다" ✅
     - "계좌번호 알려주세요" → "네, 123-456-789입니다" ✅
     - 요청에 대한 응답 없이 다른 질문으로 넘어가지 마세요! ❌
   * 직원이 **질문**을 하면 → 먼저 그 질문에 **자연스럽게** 답하세요
     - 정보를 물어보면 → 정보를 제공 ("네, 정기예금이요", "정기예금에 대해 물어보려고 했어요")
     - 불만형이라고 해서 무조건 불만을 섞지 마세요! 직원의 정당한 질문에는 정상적으로 답하세요!
   * 직원이 **설명**하면 그 설명에 대한 자연스러운 반응을 하세요
   * 직원이 언급한 주제를 계속 이어가세요
   
2. 🚨 단답형 응답도 충분히 좋습니다!
   * 직원의 요청/질문에 대해 "네", "네, 알겠습니다", "네, 여기 있습니다" 같은 단답형으로 답해도 됩니다!
   * 질문을 끊임없이 할 필요는 전혀 없습니다!
   * 직원이 요청한 것을 수행하거나, 질문에 답하는 것만으로도 충분합니다!

3. 대화 주제 추적:
   * 현재 대화 주제가 무엇인지 파악하세요 (예: "카드 분실", "예금 상품", "대출 상담" 등)
   * 그 주제를 벗어나는 질문은 절대 하지 마세요!
   * 목표가 다른 주제를 요구하더라도, 현재 대화 주제를 먼저 마무리하세요!

4. 질문 생성 원칙 (질문이 필요한 경우에만):
   * 직원의 마지막 발화 → 현재 대화 주제 → 자연스러운 다음 질문
   * 이 순서로만 질문을 생성하세요!
   * 목표를 강제로 넣으려고 대화 주제를 바꾸지 마세요!

5. 반복 방지:
   - 이미 나온 질문은 반복하지 마세요.
   - 직원이 이미 설명한 내용은 확인만 하고, 새로운 주제로 넘어가지 마세요.
   - 🚨🚨🚨 **직원이 처리 중이라고 하면** (매우 중요!):
     - "잠시만", "기다려주세요", "처리하겠습니다", "접수 진행하겠습니다", "바로 처리하겠습니다" 등 → "네, 알겠습니다" 또는 "네, 기다리겠습니다" 같은 짧은 응답만 하세요!
     - ❌ 절대 하지 말 것: "빨리 진행해 주세요", "빨리 처리해 주세요" (이미 처리 중인데 또 요청)
     - ❌ 절대 하지 말 것: 같은 정보 반복 ("서류 준비됐습니다", "신분증 드릴게요" 등 이미 말한 내용)
     - 추가 질문도 하지 마세요! 직원이 처리 중이면 그냥 기다리세요!
   - 🚨 **같은 내용/정보 반복 금지**:
     - 이미 말한 정보는 다시 말하지 마세요!
     - ❌ 나쁜 예: "서류 준비됐습니다" → 직원 처리 중 → 또 "서류 준비됐습니다"
     - ✅ 좋은 예: "서류 준비됐습니다" → 직원 "처리하겠습니다" → "네, 알겠습니다"
   - 직원이 "네 맞습니다" 등으로 확인했다면 더 이상 질문하지 말고 마무리하세요.

6. 🚨 마무리 신호 인식 및 응답 (매우 중요!):
   - 직원 발화에 다음 종료 트리거 패턴이 포함되면 → 즉시 마무리하세요!
     * 상담 내용 정리: "정리해서 말씀드리면", "오늘 안내드린 내용은", "지금까지 안내드린 내용은"
     * 추가 문의 여부 확인: "더 궁금하신 점 있으실까요?", "추가로 도와드릴 부분 있을까요?", "다른 문의는 없으신가요?"
     * 상담 종료 선언: "없으시면 상담 마무리하겠습니다", "상담은 여기까지 진행하겠습니다", "이제 마무리 도와드릴게요"
     * 업무 완료 안내: "모든 절차가 완료되었습니다", "처리가 정상적으로 마무리되었습니다", "고객님이 하실 일은 모두 끝났습니다"
     * 마무리 인사: "감사합니다. 좋은 하루 보내세요", "이용해주셔서 감사합니다", "언제든 문의 주세요"
   - 직원이 위 패턴 중 하나를 사용하면:
     * 고객은 자연스럽게 "네, 알겠습니다. 감사합니다!" 같은 종료 응답을 하세요
     * end_signal을 true로 설정하세요
     * 추가 질문을 하지 마세요!
   - 🚨🚨🚨 **절대 금지: 이미 완료된 작업을 다시 요청하지 마세요!**
     * 직원: "카드 발급 완료했습니다. 더 궁금하신 점?" 
       → ❌❌❌ "카드 발급해주세요" (절대 금지!)
       → ✅✅✅ "아니요, 감사합니다!" 또는 새로운 질문 1개만

7. 예시:
   * 직원: "카드 재발급은 3일 정도 걸립니다"
   * 좋은 응답: "그럼 그동안은 어떻게 해야 하나요?", "3일 후에 어떻게 받나요?" ✅
   * 나쁜 응답: "카드 한도는 어떻게 되나요?" (완전히 다른 주제) ❌
   
   * 직원: "예금 상품은 이자율이 3%입니다"
   * 좋은 응답: "최소 입금 금액이 있나요?", "언제부터 이자가 들어가나요?" ✅
   * 나쁜 응답: "대출은 어떻게 하나요?" (완전히 다른 주제) ❌
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

