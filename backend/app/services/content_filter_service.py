"""
부적절한 내용 필터링 서비스
기업 내부 챗봇용 컨텐츠 모더레이션
"""
import re
from typing import Dict, Optional, Tuple
from enum import Enum


class FilterResult(Enum):
    """필터링 결과"""
    ALLOWED = "allowed"  # 허용
    PROFANITY = "profanity"  # 욕설
    OFF_TOPIC = "off_topic"  # 업무 범위 밖
    INAPPROPRIATE = "inappropriate"  # 부적절한 내용
    PRIVACY_VIOLATION = "privacy_violation"  # 개인정보 침해


class ContentFilterService:
    """부적절한 내용 필터링 서비스"""
    
    def __init__(self):
        # 욕설 키워드 리스트 (한국어)
        self.profanity_keywords = [
            # 직접적인 욕설
            "시발", "씨발", "좆", "개새끼", "병신", "미친", "미친놈", "미친년",
            "지랄", "좆같", "좆되", "좆망", "좆됐", "좆나", "좆만", "좆도",
            "개같", "개되", "개망", "개새", "개소리", "개수작", "개지랄",
            "병신", "병맛", "병크", "병신같", "병신놈", "병신년",
            "미친", "미친놈", "미친년", "미친새끼", "미친것",
            "지랄", "지랄하", "지랄떨", "지랄맞",
            "또라이", "돌아이", "돌대가리", "멍청이", "바보",
            "쓰레기", "찌질이", "한심", "한심하",
            # 은어/비속어
            "존나", "존맛", "존좋", "존싫", "존나게",
            "개빡", "개빡치", "빡치", "빡쳐",
            "허접", "허접하", "허접맞",
            # 영어 욕설
            "fuck", "shit", "damn", "bitch", "asshole", "bastard",
            "stupid", "idiot", "moron", "retard",
        ]
        
        # 업무 관련 키워드 (하경은행 신입 행원 지원 챗봇)
        self.work_keywords = [
            # 은행 업무
            "은행", "대출", "예금", "적금", "계좌", "송금", "이체",
            "카드", "신용카드", "체크카드", "할부", "리볼빙",
            "금리", "이자", "수수료", "연체", "상환",
            "고객", "상담", "문의", "신청", "승인", "거절",
            "서류", "신분증", "통장", "인감", "위임장",
            "상품", "정기예금", "자유적금", "주택담보대출", "신용대출",
            # 외환/해외 업무
            "외환", "환전", "해외", "해외송금", "외화", "재외", "교포",
            "재산", "반출", "국외", "수취", "환율", "거주자", "비거주자",
            # 일정 관리
            "일정", "스케줄", "회의", "약속", "미팅", "이벤트",
            "추가", "삭제", "수정", "조회", "확인",
            # 문서/자료
            "문서", "자료", "검색", "조회", "다운로드", "업로드",
            "규정", "정책", "절차", "가이드", "매뉴얼",
            # 동아리 라운지
            "게시판", "게시물", "게시글", "댓글", "동아리", "라운지",
            "취미", "카테고리",
            # 일반 업무
            "업무", "업무지원", "도움", "안내", "문의", "질문",
            "신입", "행원", "직원", "사원",
        ]
        
        # 부적절한 질문 패턴
        self.inappropriate_patterns = [
            r"너\s*누구야",
            r"너\s*뭐야",
            r"너\s*어디서\s*왔어",
            r"너\s*몇\s*살이야",
            r"너\s*결혼\s*했어",
            r"너\s*남자야\s*여자야",
            r"너\s*좋아하는\s*것",
            r"너\s*싫어하는\s*것",
            r"날씨",
            r"오늘\s*날씨",
            r"내일\s*날씨",
            r"주식",
            r"비트코인",
            r"암호화폐",
            r"로또",
            r"복권",
            r"운세",
            r"점술",
            r"사주",
        ]
        
        # 개인정보 관련 질문 패턴 (민감한 개인정보 요청 차단)
        self.privacy_patterns = [
            r"주민\s*등록\s*번호",
            r"주민번호",
            r"주민\s*번호",
            r"고객\s*주민번호",
            r"고객\s*주민\s*번호",
            r"개인\s*정보\s*조회",
            r"계좌\s*번호\s*(알려|조회|확인)",
            r"비밀번호\s*(알려|조회|확인)",
            r"패스워드\s*(알려|조회|확인)",
            r"카드\s*번호\s*(알려|조회|확인)",
            r"신용카드\s*번호",
            r"체크카드\s*번호",
            r"cvv",
            r"cvc",
            r"유효\s*기간\s*(알려|조회)",
            r"생년월일\s*(알려|조회|확인)",
            r"전화번호\s*(알려|조회|확인)",
            r"휴대폰\s*번호\s*(알려|조회)",
            r"핸드폰\s*번호\s*(알려|조회)",
            r"주소\s*(알려|조회|확인)",
            r"이메일\s*(알려|조회|확인)",
            r"보안\s*카드\s*번호",
            r"otp\s*번호",
            r"인증\s*번호\s*(알려|조회)",
            r"비밀\s*번호\s*(알려|조회)",
            r"암호\s*(알려|조회)",
            r"고객\s*정보\s*(유출|공유|제공)",
            r"잔액\s*(알려|조회|확인).*고객",
            r"거래\s*내역\s*(알려|조회|확인).*고객",
        ]
    
    def contains_profanity(self, text: str) -> bool:
        """욕설 포함 여부 확인"""
        text_lower = text.lower()
        for keyword in self.profanity_keywords:
            if keyword in text_lower:
                return True
        return False
    
    def contains_privacy_violation(self, text: str) -> bool:
        """개인정보 침해 시도 확인"""
        text_lower = text.lower()
        for pattern in self.privacy_patterns:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def is_work_related(self, text: str) -> bool:
        """업무 관련 질문인지 확인"""
        text_lower = text.lower()
        
        # 업무 키워드가 하나라도 포함되면 업무 관련으로 판단
        for keyword in self.work_keywords:
            if keyword in text_lower:
                return True
        
        # 부적절한 패턴이 매칭되면 업무 범위 밖
        for pattern in self.inappropriate_patterns:
            if re.search(pattern, text_lower):
                return False
        
        # 키워드가 없고 패턴도 없으면 애매한 경우
        # 짧은 인사말은 허용
        greeting_keywords = ["안녕", "하이", "hello", "hi", "감사", "고마", "수고"]
        if any(kw in text_lower for kw in greeting_keywords) and len(text) < 20:
            return True
        
        # 기본적으로 업무 관련이 아니면 False
        return False
    
    def filter_content(self, message: str) -> Tuple[FilterResult, Optional[str]]:
        """
        내용 필터링
        
        Returns:
            (FilterResult, Optional[str]): (필터링 결과, 거절 메시지)
        """
        # 1. 개인정보 침해 시도 검사 (최우선)
        if self.contains_privacy_violation(message):
            return (
                FilterResult.PRIVACY_VIOLATION,
                "🔒 개인정보 보호 안내\n\n"
                "죄송합니다. 보안상의 이유로 다음과 같은 개인정보는 제공하거나 조회할 수 없습니다:\n\n"
                "• 주민등록번호, 계좌번호, 카드번호\n"
                "• 비밀번호, 보안카드 번호, OTP\n"
                "• 개인 연락처, 주소, 이메일\n"
                "• 고객의 거래내역 및 잔액 정보\n\n"
                "**고객 정보는 본인 확인 후 정식 시스템을 통해서만 조회 가능합니다.**\n\n"
                "은행 업무 절차나 상품에 대해서는 도와드릴 수 있습니다. 다른 질문이 있으신가요?"
            )
        
        # 2. 욕설 검사
        if self.contains_profanity(message):
            return (
                FilterResult.PROFANITY,
                "부적절한 표현이 포함되어 있습니다. 업무 관련 질문만 답변 가능합니다."
            )
        
        # 3. 업무 범위 검증
        if not self.is_work_related(message):
            return (
                FilterResult.OFF_TOPIC,
                "업무 관련 질문만 답변 가능합니다.\n\n"
                "다음과 같은 업무를 도와드릴 수 있습니다:\n"
                "• 은행 업무 (대출, 예금, 계좌, 카드 등)\n"
                "• 일정 관리 (일정 추가, 수정, 삭제, 조회)\n"
                "• 문서 검색 (규정, 정책, 매뉴얼 등)\n"
                "• 동아리 라운지 게시물 검색\n\n"
                "업무 관련 질문을 해주시면 도와드리겠습니다."
            )
        
        # 4. 허용
        return (FilterResult.ALLOWED, None)
    
    def get_filter_stats(self) -> Dict[str, int]:
        """필터링 통계 (향후 로깅용)"""
        return {
            "profanity_keywords_count": len(self.profanity_keywords),
            "work_keywords_count": len(self.work_keywords),
            "inappropriate_patterns_count": len(self.inappropriate_patterns),
            "privacy_patterns_count": len(self.privacy_patterns),
        }

