"""
이탈 감지 모듈
신입사원(직원)의 발화가 은행 업무 맥락을 벗어났는지 감지
"""
from typing import Dict, Tuple


# 은행 업무 관련 키워드
BANK_KEYWORDS = [
    "예금", "적금", "대출", "신용", "금리", "이자", "카드", "계좌",
    "이체", "송금", "인증서", "민원", "해지", "만기", "한도", "상환",
    "정기예금", "자유적금", "보통예금", "정기적금", "대출금", "신용카드",
    "체크카드", "인출", "입금", "출금", "통장", "비밀번호", "OTP",
    "인증", "발급", "재발급", "분실", "정지", "해제", "연체", "이자율",
    "가입", "상담", "안내", "문의", "확인", "조회", "변경", "수정",
    "은행", "금융", "상품", "상환일", "결제일", "명세서", "잔액", "잔고",
    "수수료", "혜택", "할인", "마일리지", "포인트", "페이백", "적립",
    "해외", "수수료", "차지백", "환율", "외화", "송금", "해외송금",
    "보험", "펀드", "투자", "적립식", "자동이체", "자동납입"
]


def is_on_topic(utterance: str) -> bool:
    """
    발화가 은행 업무 맥락에 있는지 확인
    
    Args:
        utterance: 사용자 발화 텍스트
        
    Returns:
        True: 은행 업무 관련, False: 이탈
    """
    if not utterance or len(utterance.strip()) < 2:
        return True  # 너무 짧은 발화는 통과
    
    utterance_lower = utterance.lower()
    
    # 은행 키워드가 하나라도 포함되어 있으면 온토픽
    for keyword in BANK_KEYWORDS:
        if keyword in utterance_lower:
            return True
    
    # 인사말/예의 표현은 항상 허용 (단, 매우 짧은 경우만)
    greetings = ["안녕", "안녕하세요", "감사", "감사합니다", "수고", "죄송", "죄송합니다"]
    is_greeting = any(greeting in utterance_lower for greeting in greetings)
    
    # 인사말이면서 매우 짧은 경우(5자 이하)만 허용
    if is_greeting and len(utterance.strip()) <= 5:
        return True
    
    # 명백한 잡담/이탈 키워드가 있는 경우 이탈로 판단
    offtopic_keywords = [
        "맛있", "먹", "음식", "밥", "배고", "배고파", "배고픔", "맛", "식당", "식사",
        "영화", "드라마", "여행", "주말", "휴가", "운동", "게임", "노래", "책", "공부", 
        "취미", "날씨", "비", "눈", "더워", "추워", "따뜻", "시원",
        "뭐드실", "뭐먹", "뭐마실", "뭐할", "뭐하", "뭐해", "뭐하세요",
        "어디가", "어디서", "어디에", "어디로",
        "누구", "누가", "누구랑", "누구와",
        "재밌", "재미", "즐거", "즐겁", "즐거워",
        "피곤", "졸려", "잠", "자고", "잠자",
        "힘들", "어려워", "어렵", "쉬워", "쉬운"
    ]
    
    # 잡담 키워드가 있으면 이탈로 판단
    has_offtopic = any(kw in utterance_lower for kw in offtopic_keywords)
    if has_offtopic:
        return False
    
    # 기본적으로는 통과 (은행 키워드가 없고 잡담 키워드도 없으면 통과)
    return True


def detect_offtopic_category(utterance: str) -> str:
    """
    이탈 카테고리를 분류 (LLM 기반 감지 시 사용)
    
    Returns:
        'BANK_TASK': 은행 업무 관련
        'SMALL_TALK': 잡담 (음식, 날씨, 취미 등)
        'PERSONAL': 개인사 공유
        'POLICY_RISK': 보안/규정 위반 소지
    """
    if is_on_topic(utterance):
        return 'BANK_TASK'
    
    utterance_lower = utterance.lower()
    
    # 잡담 키워드
    small_talk_keywords = ["맛", "먹", "음식", "날씨", "비", "날씨", "취미", 
                          "영화", "드라마", "여행", "주말", "휴가", "운동",
                          "스포츠", "게임", "노래", "책", "공부"]
    
    # 개인사 키워드
    personal_keywords = ["가족", "친구", "연인", "결혼", "출산", "이사", 
                        "직장", "회사", "학교", "학원", "병원"]
    
    # 보안/규정 위반 키워드
    policy_risk_keywords = ["비밀번호", "계좌번호", "주민번호", "카드번호", 
                           "비밀번호 알려줘", "계좌번호 알려줘", "돈 보내줘",
                           "이체해줘", "출금해줘", "대출해줘"]
    
    if any(kw in utterance_lower for kw in small_talk_keywords):
        return 'SMALL_TALK'
    elif any(kw in utterance_lower for kw in personal_keywords):
        return 'PERSONAL'
    elif any(kw in utterance_lower for kw in policy_risk_keywords):
        return 'POLICY_RISK'
    
    return 'SMALL_TALK'  # 기본값


def generate_pivot_response(offtopic_count: int, situation_title: str, 
                           current_context: str = "") -> str:
    """
    이탈 시 피벗 응답 생성
    
    Args:
        offtopic_count: 이탈 횟수 (1, 2, 3+)
        situation_title: 현재 상황 제목
        current_context: 현재 대화 맥락
        
    Returns:
        피벗 응답 텍스트
    """
    if offtopic_count == 1:
        # 1단계: 부드러운 피벗
        templates = [
            f"네, 이해했습니다. 지금 진행 중인 {situation_title} 관련해서 몇 가지 확인만 도와드리겠습니다. 어떤 부분부터 확인해드릴까요?",
            f"좋습니다. 방문 목적이 {situation_title}이 맞으실까요? 확인을 위해 몇 가지 정보를 알려주시면 도와드리겠습니다.",
            f"네, 알겠습니다. {situation_title} 관련해서 어떤 도움이 필요하신지 알려주세요.",
        ]
        return templates[0] if not templates else templates[0]
    
    elif offtopic_count == 2:
        # 2단계: 경계 안내
        templates = [
            f"죄송하지만, 본 상담은 은행 업무 안내에 초점이 맞춰져 있습니다. 고객님의 {situation_title} 관련 업무부터 도와드리겠습니다. 어떤 부분부터 확인해드릴까요?",
            f"해당 주제는 본 상담 범위를 벗어나므로, {situation_title} 관련 업무 진행에 필요한 질문부터 드리겠습니다. 어떤 도움이 필요하신가요?",
        ]
        return templates[0] if not templates else templates[0]
    
    else:
        # 3단계 이상: 종료 안내
        return "안내드린 대로, 본 과정은 은행 상담 훈련 목적입니다. 계속 진행이 어려울 경우, 이번 시뮬레이션을 중단하고 피드백을 제공드리겠습니다. 계속 진행하시겠습니까?"

