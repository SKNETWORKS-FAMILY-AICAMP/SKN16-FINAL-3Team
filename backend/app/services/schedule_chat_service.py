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
        
        # 특정 일정 질문 패턴
        query_patterns = [
            # 지나간 일정 제외 패턴 (최우선)
            r'(지나간|지난|과거)\s*일정\s*(빼고|제외하고|빼면)\s*(남은|앞으로|다가오는)?\s*일정?',  # "지나간 일정 빼고 남은 일정"
            r'일정\s*(빼고|제외하고|빼면)\s*(남은|앞으로|다가오는)\s*일정',  # "일정 빼고 남은 일정"
            r'(지나간|지난|과거)\s*일정\s*(빼고|제외하고|빼면)',  # "지나간 일정 빼고"
            r'(남은|앞으로|다가오는|향후|앞으로의)\s*일정',  # "남은 일정", "앞으로 일정"
            r'남은\s*일정\s*(뭐|뭐야|있어|있나|알려|보여)',  # "남은 일정 뭐야"
            r'앞으로\s*일정\s*(뭐|뭐야|있어|있나|알려|보여)',  # "앞으로 일정 뭐야"
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
        
        # 추가 패턴
        create_patterns = [
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

예시 (현재 날짜: {datetime.now().strftime('%Y-%m-%d')}):
- "내일 오후 2시에 회의 일정 추가해줘" 
  -> {{"title": "회의", "date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}", "time": "14:00", "end_time": null, "location": null, "description": null}}
  
- "12월 25일 크리스마스 파티 일정 만들어줘"
  -> {{"title": "크리스마스 파티", "date": "2024-12-25", "time": null, "end_time": null, "location": null, "description": null}}
  
- "11월 27일 오후 9시 성수동 이라고 일정 추가해줘"
  -> {{"title": "성수동", "date": "2024-11-27", "time": "21:00", "end_time": null, "location": null, "description": null}}
  **주의**: "11월 27일"은 현재 연도를 기준으로 YYYY-MM-DD 형식으로 변환합니다. 현재가 2024년 11월이면 2024-11-27입니다.
  
- "내일 휴가 잡아줘"
  -> {{"title": "휴가", "date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}", "time": null, "end_time": null, "location": null, "description": null}}
  
- "오늘 오후 1시 점심식사"
  -> {{"title": "점심식사", "date": "{datetime.now().strftime('%Y-%m-%d')}", "time": "13:00", "end_date": null, "end_time": null, "location": null, "description": null}}
  
- "12월 8일부터 10일까지 휴가"
  -> {{"title": "휴가", "date": "2024-12-08", "end_date": "2024-12-10", "time": null, "end_time": null, "location": null, "description": null}}

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
        
        # 1순위: 메시지에서 회사 일정 키워드 찾기
        for keyword in schedule_type_keywords:
            if keyword in cleaned_message:
                extracted_title = keyword
                break
        
        # 2순위: 패턴에서 제목 추출
        if not extracted_title:
            title = cleaned_message.strip()
            # 시간, 날짜 관련 키워드 제거
            title = re.sub(r'\d{1,2}시\s*(?:\d{1,2}분)?\s*(?:에)?', '', title)
            title = re.sub(r'(오전|오후|AM|PM)', '', title)
            title = re.sub(r'\d{1,2}월\s*\d{1,2}일\s*(?:에)?', '', title)
            title = re.sub(r'\d{1,2}일\s*(?:에)?', '', title)  # "2일" 형식도 제거
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
        
        return self._parse_datetime(schedule_info)
    
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
                print(f"⚠️ [날짜 파싱] 날짜 정보가 없습니다. 현재 날짜로 설정합니다.")
                date_obj = now.date()
            
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
            
            # 시간 처리
            has_explicit_time = schedule_info.get("has_explicit_time", False)  # 기본값 False (안전)
            
            # 기간 일정인 경우 시간을 종일로 설정 (시작일 00:00 ~ 종료일 23:59)
            if is_period and end_date_obj:
                start_time = datetime.combine(date_obj, datetime.min.time())
                end_time = datetime.combine(end_date_obj, datetime.max.time())
                has_explicit_time = True  # 기간 일정은 시간을 묻지 않음
                print(f"📅 [기간 일정] {start_time} ~ {end_time}")
            elif schedule_info.get("time"):
                time_str = schedule_info["time"]
                if ":" in time_str:
                    hour, minute = map(int, time_str.split(":"))
                else:
                    hour = int(time_str)
                    minute = 0
                
                start_time = datetime.combine(date_obj, datetime.min.time().replace(hour=hour, minute=minute))
                end_time = None  # 끝 시간은 자동 생성하지 않음
            elif has_explicit_time:
                # 시간이 있다고 했지만 파싱 실패 (GPT 방식 등)
                start_time = datetime.combine(date_obj, datetime.min.time().replace(hour=14, minute=0))
                end_time = None  # 끝 시간은 자동 생성하지 않음
            else:
                # 시간이 명시되지 않음 - None으로 설정
                start_time = datetime.combine(date_obj, datetime.min.time().replace(hour=0, minute=0))
                end_time = None
            
            # end_time이 명시된 경우 처리
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
                "has_explicit_time": has_explicit_time
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
        
        # 현재 월보다 이전 달이면 내년으로 간주
        # 예: 현재가 12월인데 11월을 입력하면 내년 11월
        if month < now.month:
            year += 1
        elif month == now.month and day < now.day:
            # 같은 월이지만 날짜가 지났으면 내년으로 간주 (안전장치)
            # 하지만 보통은 올해로 간주하는 것이 맞으므로 주석 처리
            # year += 1
            pass
        
        print(f"📅 [월일 파싱] {month}월 {day}일 → {year}년 {month}월 {day}일")
        return datetime(year, month, day).date()
    
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
    
    def create_schedule(self, schedule_info: Dict[str, Any], user: User) -> Schedule:
        """일정 생성"""
        schedule = Schedule(
            title=schedule_info["title"],
            description=schedule_info.get("description"),
            start_time=schedule_info["start_time"],
            end_time=schedule_info.get("end_time"),
            location=schedule_info.get("location"),
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

