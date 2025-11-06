// 프론트엔드 이탈 감지 유틸리티

const BANK_KEYWORDS = [
  "예금", "적금", "대출", "신용", "금리", "이자", "카드", "계좌",
  "이체", "송금", "인증서", "민원", "해지", "만기", "한도", "상환",
  "정기예금", "자유적금", "보통예금", "정기적금", "대출금", "신용카드",
  "체크카드", "인출", "입금", "출금", "통장", "비밀번호", "OTP",
  "인증", "발급", "재발급", "분실", "정지", "해제", "연체", "이자율",
  "가입", "상담", "안내", "문의", "확인", "조회", "변경", "수정",
  "은행", "금융", "상품", "상환일", "결제일", "명세서", "잔액", "잔고",
  "수수료", "혜택", "할인", "마일리지", "포인트", "페이백", "적립"
]

const OFFTOPIC_KEYWORDS = [
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

export const isOnTopic = (utterance: string): boolean => {
  if (!utterance || utterance.trim().length < 2) {
    return true
  }
  
  const utteranceLower = utterance.toLowerCase()
  
  // 은행 키워드가 하나라도 포함되어 있으면 온토픽
  for (const keyword of BANK_KEYWORDS) {
    if (utteranceLower.includes(keyword)) {
      return true
    }
  }
  
  // 인사말/예의 표현은 항상 허용 (단, 매우 짧은 경우만)
  const greetings = ["안녕", "안녕하세요", "감사", "감사합니다", "수고", "죄송", "죄송합니다"]
  const isGreeting = greetings.some(greeting => utteranceLower.includes(greeting))
  
  // 인사말이면서 매우 짧은 경우(5자 이하)만 허용
  if (isGreeting && utterance.trim().length <= 5) {
    return true
  }
  
  // 명백한 잡담/이탈 키워드가 있는 경우 이탈로 판단
  const hasOfftopic = OFFTOPIC_KEYWORDS.some(kw => utteranceLower.includes(kw))
  if (hasOfftopic) {
    return false
  }
  
  // 기본적으로는 통과
  return true
}

