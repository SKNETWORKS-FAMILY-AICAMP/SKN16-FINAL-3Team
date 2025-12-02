"""
챗봇 일정 관리 서비스
자연어 요청에서 일정 정보를 추출하고 일정을 생성/조회
"""
import re
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, List
from sqlmodel import Session
from openai import OpenAI
import os

from app.models.schedule import Schedule, ScheduleCreate, ScheduleUpdate
from app.models.user import User
from app.services.holiday_service import HolidayService
from sqlmodel import select


class ScheduleChatService:
    """챗봇 일정 관리 서비스"""
    
    def __init__(self, session: Session):
        self.session = session
        self.openai_client = None
        if os.getenv("OPENAI_API_KEY"):
            self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def get_schedule_action_type(self, message: str) -> str:
        """일정 관련 요청 타입 반환: 'create', 'delete', 'update', 'list', 'query', None"""
        message_lower = message.lower()
        print(f"🔍 [일정 감지] 메시지: '{message}'")
        
        # 삭제 패턴
        delete_patterns = [
            r'일정\s*을?\s*(삭제|지워|취소|삭제해|지워줘|취소해)',
            r'일정\s*을?\s*(삭제|지워|취소)\s*해\s*줘',
            r'일정\s*을?\s*(삭제|지워|취소)\s*해',
        ]
        for pattern in delete_patterns:
            if re.search(pattern, message_lower):
                action_type = 'delete'
                print(f"✅ [일정 감지] 타입: {action_type}")
                return action_type
        
        # 수정 패턴
        update_patterns = [
            r'일정\s*을?\s*(수정|변경|고쳐|바꿔)',
            r'일정\s*을?\s*(수정|변경|고쳐|바꿔)\s*해\s*줘',
            r'일정\s*을?\s*(수정|변경|고쳐|바꿔)\s*해',
        ]
        for pattern in update_patterns:
            if re.search(pattern, message_lower):
                action_type = 'update'
                print(f"✅ [일정 감지] 타입: {action_type}")
                return action_type
        
        # 조회 패턴 (전체 목록)
        list_patterns = [
            r'일정\s*(보여|보여줘|목록|리스트|조회|확인)',
            r'일정\s*(보여|보여줘|목록|리스트|조회|확인)\s*해\s*줘',
            r'전체\s*일정',
            r'모든\s*일정',
        ]
        for pattern in list_patterns:
            if re.search(pattern, message_lower):
                action_type = 'list'
                print(f"✅ [일정 감지] 타입: {action_type}")
                return action_type
        
        # 생성 키워드가 있으면 먼저 create로 인식 (query보다 우선)
        create_keywords = ['잡아', '잡아줘', '추가', '만들어', '등록', '생성']
        if any(kw in message_lower for kw in create_keywords):
            action_type = 'create'
            print(f"✅ [일정 감지] 타입: {action_type} (생성 키워드 감지)")
            return action_type
        
        # 특정 일정 질문 패턴
        query_patterns = [
            # 지나간 일정 제외 패턴 (최우선)
            r'(지나간|지난|과거)\s*일정\s*(빼고|제외하고|빼면)\s*(남은|앞으로|다가오는)?\s*일정?',  # "지나간 일정 빼고 남은 일정"
            r'일정\s*(빼고|제외하고|빼면)\s*(남은|앞으로|다가오는)\s*일정',  # "일정 빼고 남은 일정"
            r'(지나간|지난|과거)\s*일정\s*(빼고|제외하고|빼면)',  # "지나간 일정 빼고"
            r'(남은|앞으로|다가오는|향후|앞으로의)\s*일정',  # "남은 일정", "앞으로 일정"
            r'남은\s*일정\s*(뭐|뭐야|있어|있나|알려|보여)',  # "남은 일정 뭐야"
            r'앞으로\s*일정\s*(뭐|뭐야|있어|있나|알려|보여)',  # "앞으로 일정 뭐야"
            # 구체적인 날짜 + 일정 패턴 (우선순위 높음)
            r'\d{1,2}\s*월\s*\d{1,2}\s*일\s*(일정|스케줄)\s*(뭐|뭐야|있어|있나|알려|보여|어떤|어떤게)?',  # "12월 2일 일정 뭐야", "12월 2일 일정"
            r'\d{1,2}\s*월\s*\d{1,2}\s*일.*(일정|스케줄)',  # "12월 2일 일정이 뭐야" (일정 앞에 다른 단어 가능)
            r'(일정|스케줄).*\d{1,2}\s*월\s*\d{1,2}\s*일',  # "일정 12월 2일" (순서 반대)
            # 월/날짜 + 일정 패턴
            r'\d{1,2}\s*월\s*(일정|스케줄)',  # "11월 일정", "12월 일정"
            r'(오늘|내일|모레)\s*(일정|스케줄)',  # "오늘 일정", "내일 일정"
            r'(이번|다음|지난)\s*(주|달|월|년)\s*(일정|스케줄)',  # "이번 주 일정", "다음 달 일정"
            r'(이번|다음|지난)\s*(주|달|월|년)\s*(지나간|지난|과거)\s*일정\s*(빼고|제외하고)',  # "이번 달 지나간 일정 빼고"
            r'(첫째|둘째|셋째|넷째|다섯째)\s*주\s*(일정|스케줄)',  # "첫째 주 일정"
            r'(1|2|3|4|5)주차\s*(일정|스케줄)',  # "1주차 일정"
            # 일정 질문 패턴 (일정/스케줄 단어가 명확히 있는 경우만)
            r'^(나의|내)\s*(일정|스케줄)\s*(뭐|뭐야|있어|있나)',  # "내 일정 뭐야", "나의 스케줄 있어"
            r'(일정|스케줄)\s+(뭐|뭐야|있어|있나|어떤|어떤게)',  # "일정 뭐야", "스케줄 있어" (공백 필수)
            # 시간/날짜 질문 패턴
            r'(첫째|둘째|셋째|넷째|다섯째)\s*주.+(회의|미팅|약속)',
            r'(1|2|3|4|5)주차.+(회의|미팅|약속)',
            r'(오늘|내일|모레).+(몇\s*시|언제|시간)',
            r'(회의|미팅|약속|점심|저녁|수업|강의).+(몇\s*시|언제|시간)',
            r'몇\s*시.+(일정|회의|미팅|약속)',
            r'언제.+(일정|회의|미팅|약속)',
            r'.*일정\s*(언제|몇\s*시)',
        ]
        for pattern in query_patterns:
            if re.search(pattern, message_lower):
                action_type = 'query'
                print(f"✅ [일정 감지] 타입: {action_type}")
                return action_type
        
        # 추가 패턴 (생성 키워드 우선 확인)
        create_patterns = [
            r'.*(잡아|잡아줘|추가|만들어|등록|생성).*',  # "잡아줘" 같은 생성 키워드가 있으면 우선 create
            r'일정\s*을?\s*(추가|만들어|등록|생성|잡아)',
            r'스케줄\s*을?\s*(추가|만들어)',
            r'일정\s*을?\s*(추가|만들어|등록|생성|잡아)\s*해\s*줘',
            r'일정\s*을?\s*(추가|만들어|등록|생성|잡아)\s*해',
        ]
        for pattern in create_patterns:
            if re.search(pattern, message_lower):
                action_type = 'create'
                print(f"✅ [일정 감지] 타입: {action_type}")
                return action_type
        
        # 회사 일정 키워드 직접 사용 패턴 ("회의 잡아줘", "휴가 신청해줘" 등)
        schedule_keywords = [
            '회의', '미팅', '회의실', '휴가', '연차', '반차', '조퇴', '지각', '병결',
            '출장', '외근', '방문', '점심', '저녁', '아침', '식사', '회식',
            '교육', '연수', '세미나', '면접', '인터뷰', '발표', '보고', '평가', '약속', '예약'
        ]
        
        for keyword in schedule_keywords:
            # "회의 잡아줘", "휴가 신청해줘", "점심 예약해줘" 등
            keyword_patterns = [
                rf'{keyword}\s*(잡아|신청|등록|추가|만들어|예약)',
                rf'{keyword}\s*(잡아|신청|등록|추가|만들어|예약)\s*해\s*줘',
            ]
            for pattern in keyword_patterns:
                if re.search(pattern, message_lower):
                    action_type = 'create'
                    print(f"✅ [일정 감지] 타입: {action_type} (키워드: {keyword})")
                    return action_type
        
        # 기존 키워드도 확인 (하위 호환성)
        if any(kw in message_lower for kw in ["일정 추가", "일정 만들어", "일정 등록", "일정 생성", "일정 잡아"]):
            action_type = 'create'
            print(f"✅ [일정 감지] 타입: {action_type} (키워드 매칭)")
            return action_type
        
        print(f"❌ [일정 감지] 일정 관련 요청 아님 → RAG로 처리")
        return None
    
    def is_schedule_request(self, message: str) -> bool:
        """일정 관련 요청인지 확인"""
        return self.get_schedule_action_type(message) is not None
    
    def extract_schedule_info(self, message: str) -> Optional[Dict[str, Any]]:
        """자연어 메시지에서 일정 정보 추출"""
        try:
            # 주차 패턴은 패턴 매칭으로 먼저 처리 (GPT보다 우선)
            week_pattern = re.search(r'(\d{1,2})월\s*(첫째|둘째|셋째|넷째|다섯째)\s*주', message)
            print(f"🔍 [주차 패턴 검사] 메시지: '{message}', 패턴 매칭: {week_pattern is not None}")
            if week_pattern:
                # 주차 패턴이 있으면 패턴 매칭으로 처리 (요일이 없으면 물어봐야 함)
                result = self._extract_with_pattern(message)
                print(f"🔍 [주차 패턴 처리 결과] result: {result}")
                return result
            
            # GPT를 사용하여 구조화된 정보 추출
            if self.openai_client:
                return self._extract_with_gpt(message)
            else:
                # GPT가 없으면 패턴 매칭으로 추출
                return self._extract_with_pattern(message)
        except Exception as e:
            print(f"일정 정보 추출 오류: {e}")
            return None
    
    def extract_time_from_message(self, message: str) -> Optional[Dict[str, Any]]:
        """메시지에서 시간 정보만 추출 (pending action 완성용)"""
        try:
            # 시간 패턴 매칭
            time_patterns = [
                r'(\d{1,2})시\s*(?:(\d{1,2})분)?\s*(?:에)?\s*(오전|오후|AM|PM|am|pm)?',
                r'(오전|오후|AM|PM|am|pm)\s*(\d{1,2})시\s*(?:(\d{1,2})분)?\s*(?:에)?',
            ]
            
            hour = None
            minute = 0
            am_pm = None
            
            for pattern in time_patterns:
                time_match = re.search(pattern, message)
                if time_match:
                    # 첫 번째 패턴: "14시" 또는 "14시에"
                    if len(time_match.groups()) >= 2 and time_match.group(1).isdigit():
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2)) if time_match.group(2) and time_match.group(2).isdigit() else 0
                        am_pm = time_match.group(3) if len(time_match.groups()) >= 3 else None
                    else:
                        # 두 번째 패턴: "오후 2시"
                        am_pm = time_match.group(1)
                        hour = int(time_match.group(2))
                        minute = int(time_match.group(3)) if len(time_match.groups()) >= 3 and time_match.group(3) and time_match.group(3).isdigit() else 0
                    break
            
            if hour is None:
                return None
            
            # 오전/오후 처리
            if am_pm:
                if '오후' in am_pm or 'PM' in am_pm.upper():
                    if hour != 12:
                        hour += 12
                elif '오전' in am_pm or 'AM' in am_pm.upper():
                    if hour == 12:
                        hour = 0
            else:
                # am_pm이 없고 12시간 형식인 경우 (1-11시) 오후로 추정
                if 1 <= hour < 12:
                    hour += 12
            
            # datetime 객체 생성 (오늘 날짜 기준)
            from datetime import datetime
            now = datetime.now()
            start_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            # 끝 시간은 자동 생성하지 않음 (시작 시간만 입력)
            end_time = None
            
            return {
                "start_time": start_time,
                "end_time": end_time
            }
        except Exception as e:
            print(f"시간 추출 오류: {e}")
            return None
    
    def _extract_with_gpt(self, message: str) -> Optional[Dict[str, Any]]:
        """GPT를 사용하여 일정 정보 추출"""
        try:
            prompt = f"""다음 사용자 메시지에서 일정 정보를 추출해주세요. JSON 형식으로 반환해주세요.

사용자 메시지: {message}

다음 형식으로 JSON을 반환해주세요:
{{
    "title": "일정 제목",
    "date": "YYYY-MM-DD 형식의 시작 날짜 (반드시 YYYY-MM-DD 형식으로, 예: 2024-11-27)",
    "end_date": "YYYY-MM-DD 형식의 종료 날짜 (기간이 있으면 종료일, 없으면 null)",
    "time": "HH:MM 형식의 시간 (없으면 null)",
    "end_time": "HH:MM 형식의 종료 시간 (없으면 null)",
    "location": "장소 (없으면 null)",
    "description": "설명 (없으면 null)"
}}

**중요**: date 필드는 반드시 YYYY-MM-DD 형식(예: 2024-11-27)으로 반환해야 합니다. "11월 27일" 같은 형식은 사용하지 마세요.

**중요**: "N일부터 M일까지" 형식은 기간 일정입니다:
- date: 시작일
- end_date: 종료일

**중요**: "1월 둘째주", "12월 셋째주" 같은 주차 표현은:
- 요일이 명시되지 않으면 기간 일정이 아닙니다
- 단일 날짜로 해석하지 마세요 (요일이 필요함)
- 예: "1월 둘째주 회의" → 요일이 없으므로 date와 end_date를 모두 null로 설정

현재 날짜: {datetime.now().strftime('%Y-%m-%d')}
현재 시간: {datetime.now().strftime('%H:%M')}

**회사 일정 타입 키워드:**
- 회의, 미팅, 회의실 예약
- 휴가, 연차, 반차, 반반차
- 출장, 외근, 방문
- 점심, 저녁, 식사, 회식
- 조퇴, 지각, 병결, 결근
- 교육, 연수, 세미나, 강의
- 면접, 인터뷰
- 발표, 프레젠테이션
- 보고, 보고서 제출
- 평가, 면담

**중요**: 날짜 추출 시 반드시 현재 날짜({datetime.now().strftime('%Y-%m-%d')})를 기준으로 올바른 연도를 사용하세요:
- 현재가 11월 27일이고 "12월 1일"을 요청하면 → {datetime.now().year}-12-01 (올해 12월)
- 현재가 12월 1일이고 "11월 30일"을 요청하면 → {datetime.now().year + 1}-11-30 (내년 11월)
- 현재가 11월 27일이고 "1일"만 요청하면 → {datetime.now().year}-12-01 (다음 달인 12월 1일)
- 절대로 하드코딩된 연도(2024, 2026 등)를 사용하지 마세요!

예시 (현재 날짜: {datetime.now().strftime('%Y-%m-%d')}):
- "내일 오후 2시에 회의 일정 추가해줘" 
  -> {{"title": "회의", "date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}", "time": "14:00", "end_time": null, "location": null, "description": null}}
  
- "12월 25일 크리스마스 파티 일정 만들어줘"
  -> 현재가 11월이면 {{"title": "크리스마스 파티", "date": "{datetime.now().year}-12-25", "time": null, "end_time": null, "location": null, "description": null}}
  -> 현재가 12월 26일이면 {{"title": "크리스마스 파티", "date": "{datetime.now().year + 1}-12-25", "time": null, "end_time": null, "location": null, "description": null}}
  
- "12월 3일 휴가 잡아줘"
  -> 현재가 11월 27일이면 {{"title": "휴가", "date": "{datetime.now().year}-12-03", "time": null, "end_time": null, "location": null, "description": null}}
  -> 현재가 12월 4일이면 {{"title": "휴가", "date": "{datetime.now().year + 1}-12-03", "time": null, "end_time": null, "location": null, "description": null}}
  
- "내일 휴가 잡아줘"
  -> {{"title": "휴가", "date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}", "time": null, "end_time": null, "location": null, "description": null}}
  
- "오늘 오후 1시 점심식사"
  -> {{"title": "점심식사", "date": "{datetime.now().strftime('%Y-%m-%d')}", "time": "13:00", "end_date": null, "end_time": null, "location": null, "description": null}}
  
- "12월 8일부터 10일까지 휴가"
  -> 현재가 11월이면 {{"title": "휴가", "date": "{datetime.now().year}-12-08", "end_date": "{datetime.now().year}-12-10", "time": null, "end_time": null, "location": null, "description": null}}

JSON만 반환하고 다른 설명은 하지 마세요."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts schedule information from user messages. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            # JSON 추출 (코드 블록 제거)
            if content.startswith("```"):
                content = re.sub(r'^```json\s*', '', content)
                content = re.sub(r'^```\s*', '', content)
                content = re.sub(r'```\s*$', '', content)
            
            import json
            schedule_info = json.loads(content)
            
            # 시간 정보가 있는지 확인
            has_time = schedule_info.get("time") is not None and schedule_info.get("time") != "null"
            schedule_info["has_explicit_time"] = has_time
            
            # 기간 정보 확인
            has_end_date = schedule_info.get("end_date") is not None and schedule_info.get("end_date") != "null"
            schedule_info["is_period"] = has_end_date
            
            print(f"📋 [GPT 추출] time={schedule_info.get('time')}, end_date={schedule_info.get('end_date')}, is_period={has_end_date}, has_explicit_time={has_time}")
            
            # 날짜와 시간을 datetime으로 변환
            parsed_info = self._parse_datetime(schedule_info)
            if parsed_info:
                return parsed_info
            # 파싱 실패 시 패턴 매칭으로 폴백
            return self._extract_with_pattern(message)
            
        except Exception as e:
            print(f"GPT 추출 오류: {e}")
            return self._extract_with_pattern(message)
    
    def _extract_with_pattern(self, message: str) -> Optional[Dict[str, Any]]:
        """패턴 매칭으로 일정 정보 추출"""
        try:
            schedule_info = {
                "title": None,
                "date": None,
                "end_date": None,
                "time": None,
                "end_time": None,
                "location": None,
                "description": None,
                "is_period": False
            }
            
            # 제목 추출 전에 회사 일정 키워드 확인
            schedule_type_keywords = [
            '회의', '미팅', '회의실',
            '휴가', '연차', '반차', '반반차', '휴무',
            '조퇴', '지각', '병결', '결근',
            '출장', '외근', '방문', '출근',
            '점심', '저녁', '아침', '식사', '회식', '중식', '석식',
            '수업', '강의', '교육', '연수', '세미나', '워크샵',
            '면접', '인터뷰', '면담', '상담',
            '발표', '프레젠테이션', '보고', '제출',
            '평가', '검토', '점검',
            '약속', '예약',
            ]
            
            # 제목 추출 (간단한 패턴)
            # "일정 추가", "일정 만들어" 등의 키워드 제거 (조사 포함)
            title_patterns = [
            r'일정\s*을?\s*(추가|만들어|등록|생성|잡아)',
            r'스케줄\s*을?\s*(추가|만들어)',
            r'일정\s*을?\s*(추가|만들어|등록|생성|잡아)\s*해\s*줘',
            r'일정\s*을?\s*(추가|만들어|등록|생성|잡아)\s*해',
            ]
            
            cleaned_message = message
            for pattern in title_patterns:
                cleaned_message = re.sub(pattern, '', cleaned_message, flags=re.IGNORECASE)
            
            print(f"🔍 [메시지 정리] 원본: '{message}' → 정리 후: '{cleaned_message}'")
            
            # 기간 패턴 (우선 처리): "12월 8일부터 10일까지", "8일부터 10일까지"
            period_patterns = [
            # "12월 8일부터 10일까지", "12월 8일 ~ 10일"
            (r'(\d{1,2})월\s*(\d{1,2})일\s*(?:부터|~|-)?\s*(\d{1,2})일\s*(?:까지)?', 
             lambda m: self._parse_period_same_month(m)),
            # "12월 8일부터 1월 10일까지"
            (r'(\d{1,2})월\s*(\d{1,2})일\s*(?:부터|~|-)?\s*(\d{1,2})월\s*(\d{1,2})일\s*(?:까지)?',
             lambda m: self._parse_period_different_months(m)),
            ]
            
            period_found = False
            for pattern, parser in period_patterns:
                match = re.search(pattern, cleaned_message)
                if match:
                    start_date, end_date = parser(match)
                    schedule_info["date"] = start_date
                    schedule_info["end_date"] = end_date
                    schedule_info["is_period"] = True
                    period_found = True
                    print(f"📅 [기간 인식] {start_date} ~ {end_date}")
                    break
            
            # 기간이 아닌 경우 단일 날짜 패턴
            if not period_found:
                # 특정 월의 주차 + 요일 패턴 (예: "1월 둘째주 월요일" 또는 "1월 둘째주")
                week_weekday_pattern = re.search(r'(\d{1,2})월\s*(첫째|둘째|셋째|넷째|다섯째)\s*주\s*(?:(\d{1,2})일)?\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)?', message)
            if week_weekday_pattern:
                month = int(week_weekday_pattern.group(1))
                week_names = {'첫째': 1, '둘째': 2, '셋째': 3, '넷째': 4, '다섯째': 5}
                week_number = week_names[week_weekday_pattern.group(2)]
                # 요일이 있으면 사용, 없으면 needs_weekday 플래그 설정
                weekday_str = week_weekday_pattern.group(4)
                if weekday_str:
                    weekday_names = {'월요일': 0, '화요일': 1, '수요일': 2, '목요일': 3, '금요일': 4, '토요일': 5, '일요일': 6}
                    weekday = weekday_names[weekday_str]
                    parsed_date = self._get_weekday_of_month(month, week_number, weekday)
                    schedule_info["date"] = parsed_date
                    schedule_info["is_period"] = False
                    print(f"📅 [주차+요일 파싱] {month}월 {week_number}째주 {weekday_str} → {parsed_date}")
                else:
                    # 요일이 없으면 month와 week_number만 저장하고 needs_weekday 플래그 설정
                    schedule_info["month"] = month
                    schedule_info["week_number"] = week_number
                    schedule_info["needs_weekday"] = True
                    schedule_info["is_period"] = False
                    print(f"📅 [주차 파싱] {month}월 {week_number}째주 - 요일 필요")
            else:
                date_patterns = [
                    (r'(\d{1,2})월\s*(\d{1,2})일', self._parse_month_day),
                    (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', self._parse_iso_date),
                    (r'(\d{1,2})일', self._parse_day_only),  # "2일" 형식 (월 없이 일만)
                    (r'내일', lambda m: (datetime.now() + timedelta(days=1)).date()),
                    (r'모레', lambda m: (datetime.now() + timedelta(days=2)).date()),
                    (r'오늘', lambda m: datetime.now().date()),
                ]
            
            for pattern, parser in date_patterns:
                match = re.search(pattern, cleaned_message)
                if match:
                    matched_text = match.group(0)
                    parsed_date = parser(match)
                    schedule_info["date"] = parsed_date
                    schedule_info["is_period"] = False
                    print(f"📅 [날짜 추출] 패턴 '{pattern}' 매칭: '{matched_text}' → {parsed_date}")
                    break
            
            # 시간 패턴 (더 유연하게)
            # "14시", "14시에", "오후 2시", "2시 30분" 등 다양한 형식 지원
            time_patterns = [
            r'(\d{1,2})시\s*(?:(\d{1,2})분)?\s*(?:에)?\s*(오전|오후|AM|PM|am|pm)?',
            r'(오전|오후|AM|PM|am|pm)\s*(\d{1,2})시\s*(?:(\d{1,2})분)?\s*(?:에)?',
            ]
            
            time_match = None
            for pattern in time_patterns:
                time_match = re.search(pattern, cleaned_message)
                if time_match:
                    break
            
            if time_match:
                # 첫 번째 패턴: "14시" 또는 "14시에"
                if len(time_match.groups()) >= 2 and time_match.group(1).isdigit():
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2)) if time_match.group(2) and time_match.group(2).isdigit() else 0
                    am_pm = time_match.group(3) if len(time_match.groups()) >= 3 else None
                else:
                    # 두 번째 패턴: "오후 2시"
                    am_pm = time_match.group(1)
                    hour = int(time_match.group(2))
                    minute = int(time_match.group(3)) if len(time_match.groups()) >= 3 and time_match.group(3) and time_match.group(3).isdigit() else 0
                
                if am_pm:
                    if '오후' in am_pm or 'PM' in am_pm.upper():
                        if hour != 12:
                            hour += 12
                    elif '오전' in am_pm or 'AM' in am_pm.upper():
                        if hour == 12:
                            hour = 0
                else:
                    # am_pm이 없을 때
                    # 13시 이상이면 이미 24시간 형식이므로 그대로 사용
                    # 12시 이하면 오후로 추정 (단, 12시는 정오로 처리)
                    if hour < 12:
                        hour += 12
                    # hour >= 12이면 이미 24시간 형식이므로 그대로 사용
                
                schedule_info["time"] = f"{hour:02d}:{minute:02d}"
                schedule_info["has_explicit_time"] = True  # 시간이 명시되었음
            else:
                schedule_info["has_explicit_time"] = False  # 시간이 없음
            
            # 제목 추출 - 회사 일정 키워드 우선 검색
            extracted_title = None
            
            # 1순위: 메시지에서 회사 일정 키워드 찾기 (원본 메시지에서도 검색)
            for keyword in schedule_type_keywords:
                if keyword in message or keyword in cleaned_message:
                    extracted_title = keyword
                    print(f"📝 [제목 추출] 키워드 매칭: '{keyword}'")
                    break
            
            # 2순위: 패턴에서 제목 추출
            if not extracted_title:
                title = cleaned_message.strip()
                # 시간, 날짜 관련 키워드 제거
                title = re.sub(r'\d{1,2}시\s*(?:\d{1,2}분)?\s*(?:에)?', '', title)
                title = re.sub(r'(오전|오후|AM|PM)', '', title)
                title = re.sub(r'\d{1,2}월\s*\d{1,2}일\s*(?:에)?', '', title)
                title = re.sub(r'\d{1,2}일\s*(?:에)?', '', title)  # "2일" 형식도 제거
                title = re.sub(r'\d{1,2}월\s*(첫째|둘째|셋째|넷째|다섯째)\s*주\s*(?:(\d{1,2})일)?\s*(?:월요일|화요일|수요일|목요일|금요일|토요일|일요일)?', '', title)  # 주차 패턴 제거
                title = re.sub(r'내일|모레|오늘', '', title)
                title = re.sub(r'에\s*$', '', title)  # 끝에 "에" 제거
                title = re.sub(r'잡아|해\s*줘|해줘', '', title)  # 동사 제거
                # 조사 제거 ("이라고", "라고" 등)
                title = re.sub(r'\s*(이라고|라고|을|를|이|가|은|는)\s*', ' ', title)
                title = title.strip()
                
                if title and len(title) > 0:
                    extracted_title = title
            
            # 최종 제목 설정
            if extracted_title and len(extracted_title) > 0:
                schedule_info["title"] = extracted_title
            else:
                schedule_info["title"] = "새 일정"
            
            print(f"📝 [최종 제목] '{schedule_info['title']}'")
            print(f"📝 [schedule_info 상태] needs_weekday={schedule_info.get('needs_weekday', False)}, month={schedule_info.get('month')}, week_number={schedule_info.get('week_number')}")
            
            result = self._parse_datetime(schedule_info)
            if result is None:
                print(f"⚠️ [패턴 추출 실패] _parse_datetime이 None을 반환했습니다. schedule_info: {schedule_info}")
            return result
        except Exception as e:
            print(f"❌ [패턴 추출 오류] _extract_with_pattern에서 예외 발생: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_datetime(self, schedule_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """추출된 정보를 datetime으로 변환"""
        try:
            now = datetime.now()
            is_period = schedule_info.get("is_period", False)
            
            # 날짜 처리
            if schedule_info.get("date"):
                date_value = schedule_info["date"]
                print(f"📅 [날짜 파싱 시작] date_value={date_value}, type={type(date_value).__name__}")
                
                # datetime.date 객체인 경우 바로 사용
                if isinstance(date_value, date):
                    date_obj = date_value
                    print(f"📅 [날짜 파싱] date 객체 직접 사용: {date_obj}")
                elif isinstance(date_value, str):
                    # 문자열 날짜 파싱
                    date_obj = None
                    try:
                        # ISO 형식 시도
                        date_obj = datetime.strptime(date_value, "%Y-%m-%d").date()
                        # GPT가 반환한 날짜가 현재 날짜와 너무 차이나면 보정
                        today = now.date()
                        current_year = now.year
                        
                        # 연도가 현재 연도와 다르면 보정
                        if date_obj.year != current_year:
                            # 같은 월/일을 현재 연도 기준으로 생성
                            same_date_this_year = datetime(current_year, date_obj.month, date_obj.day).date()
                            # 올해 같은 날짜가 이미 지났으면 내년으로
                            if same_date_this_year < today:
                                date_obj = datetime(current_year + 1, date_obj.month, date_obj.day).date()
                                print(f"📅 [날짜 보정] 연도 불일치 및 과거 날짜 → {date_obj}로 보정 (원본: {date_value})")
                            else:
                                date_obj = same_date_this_year
                                print(f"📅 [날짜 보정] 연도 불일치 → {date_obj}로 보정 (원본: {date_value})")
                        elif date_obj < today:
                            # 같은 연도인데 과거 날짜면 내년으로
                            date_obj = datetime(current_year + 1, date_obj.month, date_obj.day).date()
                            print(f"📅 [날짜 보정] 과거 날짜 감지 → {date_obj}로 보정 (원본: {date_value})")
                    except:
                        try:
                            # "11월 27일" 형식 시도
                            month_day_match = re.search(r'(\d{1,2})월\s*(\d{1,2})일', date_value)
                            if month_day_match:
                                month = int(month_day_match.group(1))
                                day = int(month_day_match.group(2))
                                year = now.year
                                # 현재 월보다 이전 달이면 내년으로 간주
                                if month < now.month:
                                    year += 1
                                date_obj = datetime(year, month, day).date()
                        except:
                            pass
                    
                    if date_obj is None:
                        try:
                            # 상대적 날짜 처리
                            if "내일" in date_value or "tomorrow" in date_value.lower():
                                date_obj = (now + timedelta(days=1)).date()
                            elif "모레" in date_value or "day after tomorrow" in date_value.lower():
                                date_obj = (now + timedelta(days=2)).date()
                            elif "오늘" in date_value or "today" in date_value.lower():
                                date_obj = now.date()
                            else:
                                # 파싱 실패 시 현재 날짜로 폴백 (디버깅을 위해 로그 출력)
                                print(f"⚠️ [날짜 파싱 실패] '{date_value}' 형식을 인식하지 못했습니다. 현재 날짜로 설정합니다.")
                                date_obj = now.date()
                        except:
                            print(f"⚠️ [날짜 파싱 오류] '{date_value}' 파싱 중 오류 발생. 현재 날짜로 설정합니다.")
                            date_obj = now.date()
                elif isinstance(date_value, datetime):
                    date_obj = date_value.date()
                    print(f"📅 [날짜 파싱] datetime 객체에서 추출: {date_obj}")
                elif hasattr(date_value, 'date') and callable(getattr(date_value, 'date', None)):
                    # date() 메서드가 있는 경우 (datetime 객체 등)
                    try:
                        date_obj = date_value.date()
                        print(f"📅 [날짜 파싱] date() 메서드로 추출: {date_obj}")
                    except Exception as e:
                        print(f"⚠️ [날짜 파싱 오류] date() 메서드 호출 실패: {e}, 현재 날짜로 설정합니다.")
                        date_obj = now.date()
                else:
                    print(f"⚠️ [날짜 파싱] 알 수 없는 타입: {type(date_value).__name__}, 현재 날짜로 설정합니다.")
                    date_obj = now.date()
            else:
                # needs_weekday가 True이면 날짜를 설정하지 않음 (요일을 물어봐야 함)
                if schedule_info.get("needs_weekday", False):
                    print(f"📅 [날짜 파싱] 요일이 필요하여 날짜 설정을 보류합니다.")
                    date_obj = None  # 날짜를 None으로 설정하여 나중에 요일로 계산
                else:
                    print(f"⚠️ [날짜 파싱] 날짜 정보가 없습니다. 현재 날짜로 설정합니다.")
                    date_obj = now.date()
            
            # needs_weekday True인 경우는 기존 그대로
            if date_obj is None and schedule_info.get("needs_weekday", False):
                print(f"📅 [날짜 파싱] 요일이 필요하여 start_time 설정을 보류합니다.")
                return {
                    "title": schedule_info.get("title") or "새 일정",
                    "start_time": None,
                    "end_time": None,
                    "location": schedule_info.get("location"),
                    "description": schedule_info.get("description"),
                    "has_explicit_time": schedule_info.get("has_explicit_time", False),
                    "needs_weekday": True,
                    "month": schedule_info.get("month"),
                    "week_number": schedule_info.get("week_number"),
                    "needs_time": False,   # 요일이 먼저
                }
            
            print(f"📅 [최종 날짜] {date_obj}")
            
            # 종료 날짜 처리 (기간 일정인 경우)
            end_date_obj = None
            if is_period and schedule_info.get("end_date"):
                end_date_value = schedule_info["end_date"]
                if isinstance(end_date_value, str):
                    try:
                        end_date_obj = datetime.strptime(end_date_value, "%Y-%m-%d").date()
                    except:
                        end_date_obj = date_obj
                elif isinstance(end_date_value, datetime):
                    end_date_obj = end_date_value.date()
                elif hasattr(end_date_value, 'date'):
                    end_date_obj = end_date_value.date()
                else:
                    end_date_obj = date_obj
            
            # -------------------------
            # 🔥 여기부터 시간 처리 정책 개편
            # -------------------------
            has_explicit_time = schedule_info.get("has_explicit_time", False)
            title_lower = (schedule_info.get("title") or "").lower()
            
            # 1) 기간 일정: 종일 처리
            if is_period and end_date_obj:
                start_time = datetime.combine(date_obj, datetime.min.time())
                end_time = datetime.combine(end_date_obj, datetime.max.time())
                has_explicit_time = True  # 기간 일정은 추가 질문 안 함
                print(f"📅 [기간 일정] {start_time} ~ {end_time}")
            
            # 2) 명시된 시간이 있는 경우 → 그대로 사용
            elif schedule_info.get("time"):
                time_str = schedule_info["time"]
                if ":" in time_str:
                    hour, minute = map(int, time_str.split(":"))
                else:
                    hour = int(time_str)
                    minute = 0
                
                start_time = datetime.combine(
                    date_obj,
                    datetime.min.time().replace(hour=hour, minute=minute)
                )
                end_time = None
            
            # 3) 시간이 없는데, '휴가/연차/병결/결근/휴무' → 종일 일정으로 자동 처리
            elif not has_explicit_time and any(
                kw in title_lower for kw in ['휴가', '연차', '반차', '반반차', '병결', '결근', '휴무']
            ):
                start_time = datetime.combine(date_obj, datetime.min.time())
                end_time = datetime.combine(date_obj, datetime.max.time())
                has_explicit_time = False  # 사용자가 시간을 직접 말한 건 아님
                print(f"📅 [종일 일정] '{schedule_info.get('title')}' → {start_time} ~ {end_time}")
            
            # 4) 그 외의 경우: 날짜만 있고 시간 없음 → 시간 재질문용 플래그
            else:
                print(f"⏰ [시간 미지정] '{schedule_info.get('title')}' - 시간 추가 확인 필요")
                return {
                    "title": schedule_info.get("title") or "새 일정",
                    "start_time": None,
                    "end_time": None,
                    "location": schedule_info.get("location"),
                    "description": schedule_info.get("description"),
                    "has_explicit_time": False,
                    "needs_weekday": False,
                    "needs_time": True,
                    "date": date_obj,  # 나중에 시간만 붙이기 쉽도록
                }
            
            # end_time이 명시된 경우 처리 (기존 로직 유지)
            if schedule_info.get("end_time"):
                end_time_str = schedule_info["end_time"]
                if ":" in end_time_str:
                    hour, minute = map(int, end_time_str.split(":"))
                else:
                    hour = int(end_time_str)
                    minute = 0
                end_time = datetime.combine(date_obj, datetime.min.time().replace(hour=hour, minute=minute))
            
            return {
                "title": schedule_info.get("title") or "새 일정",
                "start_time": start_time,
                "end_time": end_time,
                "location": schedule_info.get("location"),
                "description": schedule_info.get("description"),
                "has_explicit_time": has_explicit_time,
                "needs_time": False,   # 여기까지 오면 시간은 확정된 상태
            }
        except Exception as e:
            print(f"날짜/시간 파싱 오류: {e}")
            return None
    
    def _parse_month_day(self, match) -> datetime.date:
        """월/일 형식 파싱 (예: 12월 25일)"""
        month = int(match.group(1))
        day = int(match.group(2))
        now = datetime.now()
        year = now.year
        
        # 날짜 생성 및 과거 여부 확인
        parsed_date = datetime(year, month, day).date()
        today = now.date()
        
        # 현재 월보다 이전 달이면 내년으로 간주
        # 예: 현재가 1월인데 12월을 입력하면 올해 12월 (아직 안 지남)
        # 예: 현재가 12월인데 11월을 입력하면 내년 11월
        if month < now.month:
            year += 1
            parsed_date = datetime(year, month, day).date()
        # 같은 월이거나 이후 월인 경우, 날짜가 이미 지났는지 확인
        elif parsed_date < today:
            # 날짜가 이미 지났으면 내년으로 간주
            year += 1
            parsed_date = datetime(year, month, day).date()
        
        print(f"📅 [월일 파싱] {month}월 {day}일 → {parsed_date} (현재: {today})")
        return parsed_date
    
    def _parse_iso_date(self, match) -> datetime.date:
        """ISO 형식 날짜 파싱 (예: 2024-12-25)"""
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        return datetime(year, month, day).date()
    
    def _parse_day_only(self, match) -> datetime.date:
        """일만 있는 경우 파싱 (예: "2일", "27일") - 현재 날짜와 비교하여 같은 달 또는 다음 달로 해석"""
        day = int(match.group(1))
        now = datetime.now()
        year = now.year
        month = now.month
        
        # 현재 날짜와 비교하여 같은 달 또는 다음 달 결정
        # 규칙:
        # - 입력한 일이 현재 일보다 크거나 같으면 → 같은 달
        # - 입력한 일이 현재 일보다 작으면 → 다음 달
        # 
        # 예시 (오늘이 11월 24일인 경우):
        #   - "27일" 입력 → 11월 27일 (같은 달, 27 >= 24)
        #   - "2일" 입력 → 12월 2일 (다음 달, 2 < 24)
        #   - "24일" 입력 → 11월 24일 (같은 달, 24 >= 24)
        
        if day < now.day:
            # 입력한 일이 현재 일보다 작으면 다음 달로
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1
            print(f"📅 [일만 파싱] {day}일 → {year}년 {month}월 {day}일 (다음 달, 현재: {now.year}년 {now.month}월 {now.day}일)")
        else:
            # 입력한 일이 현재 일보다 크거나 같으면 같은 달로
            print(f"📅 [일만 파싱] {day}일 → {year}년 {month}월 {day}일 (같은 달, 현재: {now.year}년 {now.month}월 {now.day}일)")
        
        return datetime(year, month, day).date()
    
    def _parse_period_same_month(self, match) -> tuple:
        """같은 월의 기간 파싱 (예: 12월 8일부터 10일까지)"""
        month = int(match.group(1))
        start_day = int(match.group(2))
        end_day = int(match.group(3))
        
        now = datetime.now()
        year = now.year
        current_month = now.month
        
        print(f"🗓️ [연도 계산] 현재: {now.year}년 {now.month}월, 입력: {month}월")
        
        # 현재 월보다 이전 달이면 내년으로 간주
        if month < current_month:
            year += 1
            print(f"🗓️ [연도 계산] {month}월 < {current_month}월 → 내년({year}년)으로 설정")
        else:
            print(f"🗓️ [연도 계산] 올해({year}년)으로 설정")
        
        start_date = datetime(year, month, start_day).date()
        end_date = datetime(year, month, end_day).date()
        return (start_date, end_date)
    
    def _parse_period_different_months(self, match) -> tuple:
        """다른 월의 기간 파싱 (예: 12월 25일부터 1월 5일까지)"""
        start_month = int(match.group(1))
        start_day = int(match.group(2))
        end_month = int(match.group(3))
        end_day = int(match.group(4))
        year = datetime.now().year
        
        # 종료월이 시작월보다 작으면 연도 넘김
        if end_month < start_month:
            end_year = year + 1
        else:
            end_year = year
        
        start_date = datetime(year, start_month, start_day).date()
        end_date = datetime(end_year, end_month, end_day).date()
        return (start_date, end_date)
    
    def _get_color_by_keyword(self, title: str) -> str:
        """키워드 기반 색상 자동 할당"""
        title_lower = title.lower()
        
        # 업무 관련 키워드 (파란색 #3B82F6)
        work_keywords = [
            '외근', '출장', '회의', '미팅', '회의실', '보고', '발표', '프레젠테이션',
            '업무', '업무처리', '점검', '평가', '검토', '교육', '연수', '세미나',
            '워크샵', '면접', '인터뷰', '면담', '상담', '출근'
        ]
        
        # 휴가/외출 관련 키워드 (초록색 #10B981)
        leave_keywords = [
            '휴가', '연차', '반차', '반반차', '조퇴', '외출', '병결', '결근', '휴무'
        ]
        
        # 사적 모임 관련 키워드 (주황색 #F97316)
        personal_keywords = [
            '점심', '저녁', '아침', '식사', '회식', '중식', '석식', '동아리',
            '개인', '약속', '예약', '모임', '만남'
        ]
        
        # 우선순위: 휴가/외출 > 사적 모임 > 업무
        for keyword in leave_keywords:
            if keyword in title_lower:
                print(f"🎨 [색상 할당] '{title}' → 초록색 (휴가/외출)")
                return "#10B981"  # 초록색
        
        for keyword in personal_keywords:
            if keyword in title_lower:
                print(f"🎨 [색상 할당] '{title}' → 주황색 (사적 모임)")
                return "#F97316"  # 주황색
        
        for keyword in work_keywords:
            if keyword in title_lower:
                print(f"🎨 [색상 할당] '{title}' → 파란색 (업무)")
                return "#3B82F6"  # 파란색
        
        # 키워드가 없으면 기본 파란색
        print(f"🎨 [색상 할당] '{title}' → 기본 파란색 (키워드 없음)")
        return "#3B82F6"  # 기본 파란색
    
    def create_schedule(self, schedule_info: Dict[str, Any], user: User) -> Schedule:
        """일정 생성"""
        # 🔥 1차 안전장치: 미완성 일정이면 여기서 바로 막기
        # - start_time 이 None 이면 아직 시간/요일이 안 정해진 상태
        # - 이런 상태에서 DB에 넣으면 에러 or 이상한 데이터 저장
        if not schedule_info.get("start_time"):
            # needs_* 플래그를 보고 어떤 종류의 미완성인지 판단
            needs_weekday = schedule_info.get("needs_weekday", False)
            needs_time = schedule_info.get("needs_time", False)
            debug_msg = (
                f"[create_schedule] 미완성 일정 감지: "
                f"title={schedule_info.get('title')}, "
                f"needs_weekday={needs_weekday}, needs_time={needs_time}"
            )
            print(debug_msg)
            # 여기서는 그냥 명시적으로 에러를 터뜨려서 상위 레이어에서 처리하도록 유도
            raise ValueError(
                "start_time 이 없는 미완성 일정입니다. "
                "needs_weekday / needs_time 플로우를 먼저 처리한 후 create_schedule 을 호출해야 합니다."
            )
        
        title = schedule_info["title"]
        
        # 키워드 기반 색상 자동 할당
        color = schedule_info.get("color")
        if not color:
            color = self._get_color_by_keyword(title)
        
        schedule = Schedule(
            title=title,
            description=schedule_info.get("description"),
            start_time=schedule_info["start_time"],
            end_time=schedule_info.get("end_time"),
            location=schedule_info.get("location"),
            color=color,
            author_id=user.id
        )
        
        self.session.add(schedule)
        self.session.commit()
        self.session.refresh(schedule)
        
        return schedule
    
    def find_schedule(self, message: str, user: User) -> Optional[Schedule]:
        """메시지에서 일정을 찾기 (제목 또는 날짜로)"""
        # 제목 추출 시도
        title_patterns = [
            r'["\']([^"\']+)["\']',  # 따옴표로 감싼 제목
            r'일정\s*["\']([^"\']+)["\']',  # "일정 '제목'"
        ]
        
        title = None
        for pattern in title_patterns:
            match = re.search(pattern, message)
            if match:
                title = match.group(1)
                break
        
        # 제목이 없으면 메시지에서 키워드 제거 후 남은 텍스트를 제목으로 사용
        if not title:
            cleaned = message
            # 일정 관련 키워드 제거
            cleaned = re.sub(r'일정\s*을?\s*(추가|만들어|등록|생성|잡아|삭제|지워|취소|수정|변경)', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\d{1,2}월\s*\d{1,2}일', '', cleaned)
            cleaned = re.sub(r'\d{1,2}시', '', cleaned)
            cleaned = re.sub(r'해\s*줘|해', '', cleaned)
            cleaned = cleaned.strip()
            if cleaned and len(cleaned) > 1:
                title = cleaned
        
        # 날짜 추출
        date_obj = None
        date_patterns = [
            (r'(\d{1,2})월\s*(\d{1,2})일', self._parse_month_day),
            (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', self._parse_iso_date),
            (r'내일', lambda m: (datetime.now() + timedelta(days=1)).date()),
            (r'모레', lambda m: (datetime.now() + timedelta(days=2)).date()),
            (r'오늘', lambda m: datetime.now().date()),
        ]
        
        for pattern, parser in date_patterns:
            match = re.search(pattern, message)
            if match:
                date_obj = parser(match)
                break
        
        # 일정 검색
        statement = select(Schedule).where(
            Schedule.author_id == user.id,
            Schedule.is_deleted == False
        )
        
        if title:
            statement = statement.where(Schedule.title.contains(title))
        
        if date_obj:
            start_of_day = datetime.combine(date_obj, datetime.min.time())
            end_of_day = datetime.combine(date_obj, datetime.max.time())
            statement = statement.where(
                Schedule.start_time >= start_of_day,
                Schedule.start_time <= end_of_day
            )
        
        statement = statement.order_by(Schedule.start_time.desc())
        schedules = list(self.session.exec(statement).all())
        
        if schedules:
            # 가장 최근 일정 반환
            return schedules[0]
        
        return None
    
    def delete_schedule(self, message: str, user: User) -> Optional[Schedule]:
        """일정 삭제"""
        schedule = self.find_schedule(message, user)
        
        if not schedule:
            return None
        
        schedule.is_deleted = True
        schedule.updated_at = datetime.utcnow()
        self.session.add(schedule)
        self.session.commit()
        
        return schedule
    
    def update_schedule(self, message: str, user: User) -> Optional[Dict[str, Any]]:
        """일정 수정"""
        # 기존 일정 찾기
        schedule = self.find_schedule(message, user)
        
        if not schedule:
            return None
        
        # 수정할 정보 추출
        update_info = self.extract_schedule_info(message)
        
        if not update_info:
            return None
        
        # 일정 업데이트
        if update_info.get("title"):
            schedule.title = update_info["title"]
        if update_info.get("start_time"):
            schedule.start_time = update_info["start_time"]
        if update_info.get("end_time"):
            schedule.end_time = update_info["end_time"]
        if update_info.get("location") is not None:
            schedule.location = update_info["location"]
        if update_info.get("description") is not None:
            schedule.description = update_info["description"]
        
        schedule.updated_at = datetime.utcnow()
        self.session.add(schedule)
        self.session.commit()
        self.session.refresh(schedule)
        
        return {"schedule": schedule, "updated_fields": update_info}
    
    def list_schedules(self, user: User, limit: int = 10) -> List[Schedule]:
        """일정 목록 조회"""
        statement = select(Schedule).where(
            Schedule.author_id == user.id,
            Schedule.is_deleted == False
        ).order_by(Schedule.start_time.asc()).limit(limit)
        
        return list(self.session.exec(statement).all())
    
    def query_schedules(self, message: str, user: User) -> List[Schedule]:
        """자연어 메시지로 일정 검색"""
        # "지나간 일정 빼고", "남은 일정", "앞으로의 일정" 등 표현 감지
        message_lower = message.lower()
        exclude_past = any(kw in message_lower for kw in [
            "지나간", "지난", "과거", "남은", "앞으로", "다가오는", 
            "향후", "앞으로의", "남은 일정", "앞으로 일정", "다음 일정"
        ])
        
        # 날짜/기간 추출
        date_obj = None
        date_range = None  # (start_date, end_date) 튜플
        
        # 기간 패턴 (우선 순위 높음)
        # 첫 번째 패턴은 match 객체를 필요로 함
        month_pattern = r'(\d{1,2})\s*월(?!\s*\d+\s*일)'
        month_match = re.search(month_pattern, message)
        if month_match:
            date_range = self._get_specific_month_range(month_match)
        else:
            # 나머지 패턴들
            range_patterns = [
                (r'첫째\s*주|첫\s*주|1주차', lambda: self._get_week_of_month(1)),
                (r'둘째\s*주|두\s*번째\s*주|2주차', lambda: self._get_week_of_month(2)),
                (r'셋째\s*주|세\s*번째\s*주|3주차', lambda: self._get_week_of_month(3)),
                (r'넷째\s*주|네\s*번째\s*주|4주차', lambda: self._get_week_of_month(4)),
                (r'다섯째\s*주|다섯\s*번째\s*주|5주차', lambda: self._get_week_of_month(5)),
                (r'이번\s*주', self._get_this_week_range),
                (r'다음\s*주', self._get_next_week_range),
                (r'이번\s*달|이번\s*월', self._get_this_month_range),
                (r'다음\s*달|다음\s*월', self._get_next_month_range),
                (r'이번\s*년|올해', self._get_this_year_range),
            ]
            
            for pattern, range_func in range_patterns:
                if re.search(pattern, message):
                    date_range = range_func()
                    break
        
        # 기간이 없으면 특정 날짜 확인
        if not date_range:
            date_patterns = [
                (r'오늘', lambda m: datetime.now().date()),
                (r'내일', lambda m: (datetime.now() + timedelta(days=1)).date()),
                (r'모레', lambda m: (datetime.now() + timedelta(days=2)).date()),
                (r'(\d{1,2})월\s*(\d{1,2})일', self._parse_month_day),
                (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', self._parse_iso_date),
            ]
            
            for pattern, parser in date_patterns:
                match = re.search(pattern, message)
                if match:
                    date_obj = parser(match)
                    break
        
        # 제목 키워드 추출 (중복 제거) - 회사 일정 키워드 확장
        title_keywords = []
        keyword_patterns = [
            # 회의/미팅
            r'(회의|미팅|회의실)',
            # 휴가/결근
            r'(휴가|연차|반차|반반차|휴무)',
            r'(조퇴|지각|병결|결근)',
            # 출장/외근
            r'(출장|외근|방문|출근)',
            # 식사
            r'(점심|저녁|아침|식사|회식|중식|석식)',
            # 교육/학습
            r'(수업|강의|교육|연수|세미나|워크샵)',
            # 인사/면담
            r'(면접|인터뷰|면담|상담)',
            # 업무
            r'(발표|프레젠테이션|보고|제출)',
            r'(평가|검토|점검)',
            # 기타
            r'(약속|예약)',
        ]
        
        for pattern in keyword_patterns:
            match = re.search(pattern, message)
            if match:
                keyword = match.group(1)
                if keyword not in title_keywords:  # 중복 방지
                    title_keywords.append(keyword)
        
        # 디버깅: 추출된 정보 로그
        if date_range:
            print(f"📅 날짜 범위: {date_range[0]} ~ {date_range[1]}")
            if exclude_past:
                print(f"⏰ 지나간 일정 제외: 오늘 이후만 표시")
        elif date_obj:
            print(f"📅 특정 날짜: {date_obj}")
        else:
            print(f"📅 날짜 필터 없음 (오늘 이후 모든 일정)")
        
        if title_keywords:
            print(f"🔍 일정 검색 키워드: {title_keywords}")
        
        # 일정 검색
        statement = select(Schedule).where(
            Schedule.author_id == user.id,
            Schedule.is_deleted == False
        )
        
        # 날짜 필터링
        if date_range:
            # 기간 범위로 필터링
            start_date, end_date = date_range
            start_of_period = datetime.combine(start_date, datetime.min.time())
            end_of_period = datetime.combine(end_date, datetime.max.time())
            
            # "지나간 일정 빼고" 표현이 있으면 오늘 이후만 필터링
            if exclude_past:
                # 기간 범위 내에서 오늘 이후만
                now = datetime.now()
                if now > start_of_period:
                    start_of_period = now
                statement = statement.where(
                    Schedule.start_time >= start_of_period,
                    Schedule.start_time <= end_of_period
                )
            else:
                # 기간 전체
                statement = statement.where(
                    Schedule.start_time >= start_of_period,
                    Schedule.start_time <= end_of_period
                )
        elif date_obj:
            # 특정 날짜로 필터링
            start_of_day = datetime.combine(date_obj, datetime.min.time())
            end_of_day = datetime.combine(date_obj, datetime.max.time())
            
            # "지나간 일정 빼고" 표현이 있고 오늘이면 오늘 이후만
            if exclude_past and date_obj == datetime.now().date():
                statement = statement.where(
                    Schedule.start_time >= datetime.now(),
                    Schedule.start_time <= end_of_day
                )
            else:
                statement = statement.where(
                    Schedule.start_time >= start_of_day,
                    Schedule.start_time <= end_of_day
                )
        else:
            # 날짜가 없으면 오늘 이후의 일정만 (또는 exclude_past가 True면)
            statement = statement.where(
                Schedule.start_time >= datetime.now()
            )
        
        # 제목 필터링
        if title_keywords:
            # OR 조건으로 여러 키워드 중 하나라도 포함
            from sqlalchemy import or_
            title_filters = [Schedule.title.contains(kw) for kw in title_keywords]
            statement = statement.where(or_(*title_filters))
        
        statement = statement.order_by(Schedule.start_time.asc())
        
        schedules = list(self.session.exec(statement).all())
        
        # 디버깅: 검색 결과 로그
        print(f"📊 일정 검색 결과: {len(schedules)}개")
        for schedule in schedules:
            print(f"  - {schedule.title} ({schedule.start_time.strftime('%Y-%m-%d %H:%M')})")
        
        return schedules
    
    def _get_weekday_of_month(self, month: int, week_number: int, weekday: int) -> date:
        """특정 월의 특정 주차의 특정 요일 계산 (예: 1월 둘째주 월요일)
        
        주차 계산 방식:
        - 첫째주: 1일부터 첫 번째 일요일까지
        - 둘째주: 첫 번째 월요일부터 시작
        """
        now = datetime.now()
        year = now.year
        
        # 입력된 월이 현재 월보다 작으면 내년으로 간주
        if month < now.month:
            year += 1
        
        # 해당 월의 1일
        first_day = datetime(year, month, 1).date()
        first_day_weekday = first_day.weekday()  # 0=월요일, 6=일요일
        
        # 첫 번째 일요일 찾기
        # 1일이 일요일이면 첫 번째 일요일은 1일
        if first_day_weekday == 6:  # 일요일
            first_sunday = first_day
        else:
            # 1일부터 다음 일요일까지의 일수 계산
            days_to_sunday = (6 - first_day_weekday) % 7
            if days_to_sunday == 0:
                days_to_sunday = 7
            first_sunday = first_day + timedelta(days=days_to_sunday)
        
        # 첫 번째 월요일 (둘째주 시작)
        # 첫 번째 일요일 다음 날이 월요일
        first_monday = first_sunday + timedelta(days=1)
        
        # 첫째주에 포함된 특정 요일 찾기
        days_from_first_day = (weekday - first_day_weekday) % 7
        if days_from_first_day == 0 and first_day_weekday != weekday:
            days_from_first_day = 7
        first_week_target = first_day + timedelta(days=days_from_first_day)
        
        if week_number == 1:
            # 첫째주 요청
            if first_week_target <= first_sunday:
                # 첫째주에 포함됨
                target_date = first_week_target
            else:
                # 첫째주에 없으면 첫 월요일부터 시작하는 둘째주로
                target_date = first_monday + timedelta(days=(weekday - 0) % 7)
        else:
            # 둘째주 이상
            # 항상 첫 번째 월요일부터 시작하는 주차 기준으로 계산
            # 첫 번째 월요일부터 N째주까지의 요일 계산
            days_from_monday = (weekday - 0) % 7  # 월요일(0)부터 목표 요일까지의 일수
            target_date = first_monday + timedelta(days=(week_number - 2) * 7 + days_from_monday)
        
        print(f"📅 [주차+요일 계산] {year}년 {month}월 {week_number}째주 {['월', '화', '수', '목', '금', '토', '일'][weekday]}요일 → {target_date}")
        return target_date
    
    def _get_week_of_month(self, week_number: int):
        """이번 달의 특정 주차 범위 계산 (1~5주차)"""
        today = datetime.now().date()
        start_of_month = today.replace(day=1)
        
        # 이번 달 마지막 날 계산
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        
        # 이번 달의 주차별 범위 계산
        # 각 주는 월요일부터 일요일까지
        current_date = start_of_month
        week_count = 0
        week_start = None
        
        while current_date <= end_of_month:
            # 월요일이면 새로운 주 시작
            if current_date.weekday() == 0:  # 0 = 월요일
                week_count += 1
                if week_count == week_number:
                    week_start = current_date
                    week_end = min(current_date + timedelta(days=6), end_of_month)
                    return (week_start, week_end)
            # 1일이 월요일이 아닌 경우, 1일부터 첫 번째 일요일까지가 첫째 주
            elif current_date == start_of_month and week_number == 1:
                week_count = 1
                week_start = start_of_month
                # 첫 번째 일요일 찾기
                days_until_sunday = (6 - start_of_month.weekday()) % 7
                if days_until_sunday == 0 and start_of_month.weekday() != 6:
                    days_until_sunday = 7
                week_end = start_of_month + timedelta(days=days_until_sunday)
                week_end = min(week_end, end_of_month)
                return (week_start, week_end)
            
            current_date += timedelta(days=1)
        
        # 요청한 주차가 없으면 이번 달 전체 반환
        return (start_of_month, end_of_month)
    
    def _get_this_week_range(self):
        """이번 주 범위 (월요일 ~ 일요일)"""
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())  # 이번 주 월요일
        end_of_week = start_of_week + timedelta(days=6)  # 이번 주 일요일
        return (start_of_week, end_of_week)
    
    def _get_next_week_range(self):
        """다음 주 범위"""
        today = datetime.now().date()
        start_of_next_week = today - timedelta(days=today.weekday()) + timedelta(days=7)
        end_of_next_week = start_of_next_week + timedelta(days=6)
        return (start_of_next_week, end_of_next_week)
    
    def _get_this_month_range(self):
        """이번 달 범위"""
        today = datetime.now().date()
        start_of_month = today.replace(day=1)
        # 다음 달 1일에서 하루 빼기
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return (start_of_month, end_of_month)
    
    def _get_next_month_range(self):
        """다음 달 범위"""
        today = datetime.now().date()
        if today.month == 12:
            start_of_next_month = today.replace(year=today.year + 1, month=1, day=1)
            end_of_next_month = start_of_next_month.replace(day=31)
        else:
            start_of_next_month = today.replace(month=today.month + 1, day=1)
            # 다다음 달 1일에서 하루 빼기
            if today.month == 11:
                end_of_next_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_of_next_month = today.replace(month=today.month + 2, day=1) - timedelta(days=1)
        return (start_of_next_month, end_of_next_month)
    
    def _get_this_year_range(self):
        """올해 범위"""
        today = datetime.now().date()
        start_of_year = today.replace(month=1, day=1)
        end_of_year = today.replace(month=12, day=31)
        return (start_of_year, end_of_year)
    
    def _get_specific_month_range(self, match):
        """특정 월의 범위 (예: "11월" → 2024-11-01 ~ 2024-11-30)"""
        if not match:
            # match가 None이면 이번 달 반환
            return self._get_this_month_range()
        
        try:
            month = int(match.group(1))
        except (AttributeError, IndexError, ValueError):
            # 파싱 실패 시 이번 달 반환
            return self._get_this_month_range()
        
        today = datetime.now().date()
        year = today.year
        
        # 입력된 월이 현재 월보다 작으면 내년으로 간주 (예: 현재 12월인데 1월을 물어보면 내년 1월)
        if month < today.month:
            year += 1
        
        # 해당 월의 시작일
        start_of_month = datetime(year, month, 1).date()
        
        # 해당 월의 마지막 날 계산
        if month == 12:
            end_of_month = datetime(year, 12, 31).date()
        else:
            end_of_month = datetime(year, month + 1, 1).date() - timedelta(days=1)
        
        print(f"📅 [월 범위 계산] {month}월 → {start_of_month} ~ {end_of_month}")
        return (start_of_month, end_of_month)
    
    def format_schedule_response(self, schedule: Schedule, action: str = "create") -> str:
        """일정 응답 메시지 생성"""
        from datetime import datetime
        
        # 현재 연도와 같으면 연도 생략
        current_year = datetime.now().year
        if schedule.start_time.year == current_year:
            start_time_str = schedule.start_time.strftime("%m월 %d일 %H:%M")
        else:
            start_time_str = schedule.start_time.strftime("%Y년 %m월 %d일 %H:%M")
        
        # 종료 시간 포맷 (날짜가 다르면 날짜까지 표시)
        if schedule.end_time:
            if schedule.end_time.date() != schedule.start_time.date():
                # 날짜가 다른 경우 (기간 일정)
                if schedule.end_time.year == current_year:
                    end_time_str = schedule.end_time.strftime("%m월 %d일 %H:%M")
                else:
                    end_time_str = schedule.end_time.strftime("%Y년 %m월 %d일 %H:%M")
            else:
                # 같은 날짜인 경우 시간만 표시
                end_time_str = schedule.end_time.strftime("%H:%M")
        else:
            end_time_str = "미정"
        
        if action == "create":
            response = f"✅ 일정이 추가되었습니다!\n\n"
        elif action == "delete":
            response = f"🗑️ 일정이 삭제되었습니다!\n\n"
        elif action == "update":
            response = f"✏️ 일정이 수정되었습니다!\n\n"
        else:
            response = f"📅 일정 정보\n\n"
        
        # 응답 포맷: 📅 {제목} 🕐 {날짜} {시간}
        response += f"📅 {schedule.title} 🕐 {start_time_str}"
        if schedule.end_time:
            response += f" ~ {end_time_str}"
        response += "\n"
        
        if schedule.location:
            response += f"📍 {schedule.location}\n"
        if schedule.description:
            response += f"📝 {schedule.description}\n"
        
        return response
    
    def format_schedule_list_response(self, schedules: List[Schedule]) -> str:
        """일정 목록 응답 메시지 생성"""
        if not schedules:
            return "📅 등록된 일정이 없습니다."
        
        response = f"📅 일정 목록 ({len(schedules)}개)\n\n"
        
        for idx, schedule in enumerate(schedules[:10], 1):  # 최대 10개만 표시
            start_time_str = schedule.start_time.strftime("%m월 %d일 %H:%M")
            response += f"{idx}. **{schedule.title}** - {start_time_str}\n"
        
        if len(schedules) > 10:
            response += f"\n... 외 {len(schedules) - 10}개"
        
        return response
    
    def format_schedule_query_response(self, schedules: List[Schedule], message: str) -> str:
        """일정 검색 결과 응답 메시지 생성"""
        # 검색 기간/날짜 파악
        period_str = "해당"
        if re.search(r'첫째\s*주|첫\s*주|1주차', message):
            period_str = "이번 달 첫째 주"
        elif re.search(r'둘째\s*주|두\s*번째\s*주|2주차', message):
            period_str = "이번 달 둘째 주"
        elif re.search(r'셋째\s*주|세\s*번째\s*주|3주차', message):
            period_str = "이번 달 셋째 주"
        elif re.search(r'넷째\s*주|네\s*번째\s*주|4주차', message):
            period_str = "이번 달 넷째 주"
        elif re.search(r'다섯째\s*주|다섯\s*번째\s*주|5주차', message):
            period_str = "이번 달 다섯째 주"
        elif "오늘" in message:
            period_str = "오늘"
        elif "내일" in message:
            period_str = "내일"
        elif "모레" in message:
            period_str = "모레"
        elif re.search(r'이번\s*주', message):
            period_str = "이번 주"
        elif re.search(r'다음\s*주', message):
            period_str = "다음 주"
        elif re.search(r'이번\s*달|이번\s*월', message):
            period_str = "이번 달"
        elif re.search(r'다음\s*달|다음\s*월', message):
            period_str = "다음 달"
        elif re.search(r'이번\s*년|올해', message):
            period_str = "올해"
        
        if not schedules:
            return f"🔍 {period_str} 일정을 찾을 수 없습니다.\n\n다른 날짜나 키워드로 다시 검색해보세요!"
        
        # 일정이 1개인 경우 - 상세 정보 표시
        if len(schedules) == 1:
            schedule = schedules[0]
            response = f"📅 {period_str} 일정을 찾았어요!\n\n"
            response += f"**{schedule.title}**\n"
            response += f"🕐 {schedule.start_time.strftime('%Y년 %m월 %d일 %H:%M')}"
            
            if schedule.end_time:
                response += f" ~ {schedule.end_time.strftime('%H:%M')}"
            response += "\n"
            
            if schedule.location:
                response += f"📍 {schedule.location}\n"
            if schedule.description:
                response += f"📝 {schedule.description}\n"
            
            return response
        
        # 일정이 여러 개인 경우 - 목록 표시
        response = f"📅 {period_str} {len(schedules)}개의 일정을 찾았어요!\n\n"
        
        for idx, schedule in enumerate(schedules[:5], 1):  # 최대 5개만 표시
            start_time_str = schedule.start_time.strftime("%m월 %d일 %H:%M")
            response += f"{idx}. **{schedule.title}**\n"
            response += f"   🕐 {start_time_str}"
            
            if schedule.location:
                response += f" | 📍 {schedule.location}"
            response += "\n"
        
        if len(schedules) > 5:
            # 나머지 일정 데이터를 JSON으로 인코딩하여 포함
            remaining_schedules = schedules[5:]
            import json
            schedule_data = [
                {
                    "title": s.title,
                    "start_time": s.start_time.isoformat(),
                    "end_time": s.end_time.isoformat() if s.end_time else None,
                    "location": s.location,
                    "description": s.description
                }
                for s in remaining_schedules
            ]
            schedule_json = json.dumps(schedule_data, ensure_ascii=False)
            # 특별한 마커로 감싸기 (마크다운에서 숨김)
            response += f"\n\n<!-- EXPAND_SCHEDULES:{len(schedules) - 5}:{schedule_json} -->"
            response += f"\n... 외 {len(schedules) - 5}개의 일정이 더 있어요"
        
        return response
    
    def is_holiday_query(self, message: str) -> bool:
        """공휴일 관련 질문인지 확인"""
        message_lower = message.lower()
        
        # 공휴일 관련 키워드 패턴
        holiday_patterns = [
            r'공휴일\s*(언제|뭐야|있어|있나|알려|보여|몇\s*일|날짜)',
            r'공휴일\s*(이|가)\s*(언제|뭐야|있어|있나)',
            r'공휴일\s*(은|는)\s*(언제|뭐야|있어|있나)',
            r'공휴일\s*(을|를)\s*(알려|보여|알려줘|보여줘)',
            r'공휴일\s*(목록|리스트|일정)',
            r'공휴일\s*(조회|확인)',
            r'공휴일',
            r'휴일\s*(언제|뭐야|있어|있나|알려|보여)',
            r'휴일\s*(목록|리스트)',
            r'공휴일\s*(\d{1,2})\s*월',
            r'(\d{1,2})\s*월\s*공휴일',
            r'올해\s*공휴일',
            r'이번\s*달\s*공휴일',
            r'다음\s*달\s*공휴일',
            r'설날|추석|어린이날|현충일|광복절|개천절|한글날|성탄절|크리스마스',
        ]
        
        for pattern in holiday_patterns:
            if re.search(pattern, message_lower):
                print(f"✅ [공휴일 감지] 공휴일 관련 질문으로 인식")
                return True
        
        return False
    
    def query_holidays(self, message: str) -> str:
        """공휴일 조회 및 응답 생성"""
        try:
            now = datetime.now()
            current_year = now.year
            current_month = now.month
            
            # 메시지에서 연도/월 추출
            year = current_year
            month = None
            
            message_lower = message.lower()
            
            # 특정 공휴일 이름 추출
            holiday_names = {
                '설날': ['설날', '설', '설 연휴'],
                '추석': ['추석', '추석 연휴'],
                '어린이날': ['어린이날'],
                '현충일': ['현충일'],
                '광복절': ['광복절'],
                '개천절': ['개천절'],
                '한글날': ['한글날'],
                '성탄절': ['성탄절', '크리스마스', 'christmas'],
                '신정': ['신정', '새해'],
                '부처님 오신 날': ['부처님', '부처님 오신 날', '석가탄신일'],
                '3·1절': ['3·1절', '삼일절', '3.1절'],
            }
            
            target_holiday_name = None
            for key, keywords in holiday_names.items():
                for keyword in keywords:
                    if keyword in message_lower:
                        target_holiday_name = key
                        print(f"🔍 [공휴일 필터] 특정 공휴일 감지: {target_holiday_name} (키워드: {keyword})")
                        break
                if target_holiday_name:
                    break
            
            if not target_holiday_name:
                print(f"🔍 [공휴일 필터] 특정 공휴일 없음 - 전체 공휴일 조회")
            
            # 상대적 연도 표현 처리 (우선순위 높음)
            if '내후년' in message_lower or '내후 년' in message_lower:
                year = current_year + 2
            elif '내년' in message_lower or '다음 년' in message_lower or '다음년' in message_lower:
                year = current_year + 1
            elif '작년' in message_lower or '지난 년' in message_lower or '지난년' in message_lower:
                year = current_year - 1
            elif '올해' in message_lower or '금년' in message_lower or '올 년' in message_lower:
                year = current_year
            else:
                # 숫자 연도 추출 (예: "2025년 공휴일", "2026년 공휴일")
                year_match = re.search(r'(\d{4})\s*년', message)
                if year_match:
                    year = int(year_match.group(1))
            
            # 월 추출 (예: "11월 공휴일", "이번 달 공휴일")
            if '이번 달' in message_lower or '이번달' in message_lower or '이번 월' in message_lower:
                month = current_month
            elif '다음 달' in message_lower or '다음달' in message_lower or '다음 월' in message_lower:
                month = current_month + 1
                if month > 12:
                    month = 1
                    year += 1
            else:
                month_match = re.search(r'(\d{1,2})\s*월', message)
                if month_match:
                    month = int(month_match.group(1))
            
            # 공휴일 조회 (특정 공휴일이 아닌 경우 전체 조회를 위해 force_refresh=False)
            print(f"🔍 [공휴일 조회] year={year}, month={month}, target_holiday={target_holiday_name}")
            # 전체 공휴일 조회 시 데이터가 없으면 강제로 새로고침
            holidays = HolidayService.get_holidays(self.session, year, month, force_refresh=False)
            print(f"🔍 [공휴일 조회 결과] {len(holidays)}개 공휴일 발견")
            
            # 전체 공휴일 조회인데 데이터가 적으면 (예: 1-2개만) 강제 새로고침 시도
            if not target_holiday_name and len(holidays) < 5 and month is None:
                print(f"⚠️ [공휴일 조회] 공휴일이 적어서 강제 새로고침 시도")
                holidays = HolidayService.get_holidays(self.session, year, month, force_refresh=True)
                print(f"🔍 [공휴일 조회 결과 (새로고침 후)] {len(holidays)}개 공휴일 발견")
            
            if not holidays:
                if target_holiday_name:
                    return f"📅 {target_holiday_name}에 대한 정보를 찾을 수 없습니다."
                elif month:
                    return f"📅 {year}년 {month}월에는 등록된 공휴일이 없습니다."
                else:
                    return f"📅 {year}년에는 등록된 공휴일이 없습니다."
            
            # 특정 공휴일 이름이 있으면 필터링
            if target_holiday_name:
                # 공휴일 이름에 키워드가 포함된 것만 필터링
                filtered_holidays = []
                for holiday in holidays:
                    # 공휴일 이름에 타겟 키워드가 포함되어 있는지 확인
                    holiday_name_lower = holiday.name.lower()
                    # 예: "추석"이면 "추석", "추석 연휴" 모두 매칭
                    if target_holiday_name in holiday.name or any(
                        keyword in holiday_name_lower 
                        for keyword in holiday_names[target_holiday_name]
                    ):
                        filtered_holidays.append(holiday)
                
                if not filtered_holidays:
                    return f"📅 {target_holiday_name}에 대한 정보를 찾을 수 없습니다."
                
                holidays = filtered_holidays
                
                # 특정 공휴일만 조회한 경우 상세 정보 표시
                if len(holidays) == 1:
                    holiday = holidays[0]
                    holiday_date = holiday.holiday_date
                    date_str = holiday_date.strftime("%Y년 %m월 %d일")
                    weekday_num = holiday_date.weekday()
                    weekday_kr = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일'][weekday_num]
                    
                    response = f"📅 {holiday.name}\n\n"
                    response += f"🗓️ {date_str} ({weekday_kr})\n"
                    return response
                else:
                    # 여러 개인 경우 (예: 추석 연휴가 여러 날)
                    response = f"📅 {target_holiday_name} 관련 공휴일\n\n"
                    holidays_sorted = sorted(holidays, key=lambda h: h.holiday_date)
                    for holiday in holidays_sorted:
                        holiday_date = holiday.holiday_date
                        date_str = holiday_date.strftime("%Y년 %m월 %d일")
                        weekday_num = holiday_date.weekday()
                        weekday_kr = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일'][weekday_num]
                        response += f"🗓️ {date_str} ({weekday_kr}) - {holiday.name}\n"
                    return response
            
            # 전체 공휴일 목록 표시
            if month:
                response = f"📅 {year}년 {month}월 공휴일\n\n"
            else:
                response = f"📅 {year}년 공휴일\n\n"
            
            # 날짜순으로 정렬
            holidays_sorted = sorted(holidays, key=lambda h: h.holiday_date)
            
            for holiday in holidays_sorted:
                holiday_date = holiday.holiday_date
                date_str = holiday_date.strftime("%m월 %d일")
                weekday_num = holiday_date.weekday()  # 0=월요일, 6=일요일
                weekday_kr = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일'][weekday_num]
                
                response += f"🗓️ {date_str} ({weekday_kr}) - {holiday.name}\n"
            
            return response
            
        except Exception as e:
            print(f"공휴일 조회 오류: {e}")
            return f"❌ 공휴일 정보를 가져오는 중 오류가 발생했습니다: {str(e)}"

