"""
챗봇 일정 관리 서비스
자연어 요청에서 일정 정보를 추출하고 일정을 생성/조회
"""
import re
from datetime import datetime, timedelta
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
        
        # 삭제 패턴
        delete_patterns = [
            r'일정\s*을?\s*(삭제|지워|취소|삭제해|지워줘|취소해)',
            r'일정\s*을?\s*(삭제|지워|취소)\s*해\s*줘',
            r'일정\s*을?\s*(삭제|지워|취소)\s*해',
        ]
        for pattern in delete_patterns:
            if re.search(pattern, message_lower):
                return 'delete'
        
        # 수정 패턴
        update_patterns = [
            r'일정\s*을?\s*(수정|변경|고쳐|바꿔)',
            r'일정\s*을?\s*(수정|변경|고쳐|바꿔)\s*해\s*줘',
            r'일정\s*을?\s*(수정|변경|고쳐|바꿔)\s*해',
        ]
        for pattern in update_patterns:
            if re.search(pattern, message_lower):
                return 'update'
        
        # 조회 패턴 (전체 목록)
        list_patterns = [
            r'일정\s*(보여|보여줘|목록|리스트|조회|확인)',
            r'일정\s*(보여|보여줘|목록|리스트|조회|확인)\s*해\s*줘',
            r'전체\s*일정',
            r'모든\s*일정',
        ]
        for pattern in list_patterns:
            if re.search(pattern, message_lower):
                return 'list'
        
        # 특정 일정 질문 패턴 (새로 추가!)
        query_patterns = [
            r'(첫째|둘째|셋째|넷째|다섯째)\s*주.+(일정|회의|미팅|약속)',
            r'(1|2|3|4|5)주차.+(일정|회의|미팅|약속)',
            r'(\d{1,2})\s*일(날)?\s*.+(일정|회의|미팅|약속|알려|뭐|있어)',  # "5일날 일정 알려줘" 패턴
            r'(오늘|내일|모레).+(몇\s*시|언제|시간)',
            r'(회의|미팅|약속|점심|저녁|수업|강의|휴가|출장|여행).+(몇\s*시|언제|시간)',
            r'(휴가|출장|여행).+(언제|기간|몇\s*일)',
            r'언제부터\s*언제까지',
            r'몇\s*시.+(일정|회의|미팅|약속)',
            r'언제.+(일정|회의|미팅|약속|휴가|출장)',
            r'.*일정\s*(언제|몇\s*시)',
            r'.+(일정|스케줄)\s*(뭐|뭐야|있어|있나)',
            r'.+(일|날).+(없는데|없어|없지|없나)',  # 부정 질문 패턴 추가
        ]
        for pattern in query_patterns:
            if re.search(pattern, message_lower):
                return 'query'
        
        # 추가 패턴
        create_patterns = [
            r'일정\s*을?\s*(추가|만들어|등록|생성|잡아)',
            r'스케줄\s*을?\s*(추가|만들어)',
            r'일정\s*을?\s*(추가|만들어|등록|생성|잡아)\s*해\s*줘',
            r'일정\s*을?\s*(추가|만들어|등록|생성|잡아)\s*해',
        ]
        for pattern in create_patterns:
            if re.search(pattern, message_lower):
                return 'create'
        
        # 기존 키워드도 확인 (하위 호환성)
        if any(kw in message_lower for kw in ["일정 추가", "일정 만들어", "일정 등록", "일정 생성", "일정 잡아"]):
            return 'create'
        
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
    
    def _extract_with_gpt(self, message: str) -> Optional[Dict[str, Any]]:
        """GPT를 사용하여 일정 정보 추출"""
        try:
            prompt = f"""다음 사용자 메시지에서 일정 정보를 추출해주세요. JSON 형식으로 반환해주세요.

사용자 메시지: {message}

다음 형식으로 JSON을 반환해주세요:
{{
    "title": "일정 제목",
    "date": "YYYY-MM-DD 형식의 날짜 (없으면 null)",
    "time": "HH:MM 형식의 시간 (없으면 null)",
    "end_time": "HH:MM 형식의 종료 시간 (없으면 null)",
    "location": "장소 (없으면 null)",
    "description": "설명 (없으면 null)"
}}

현재 날짜: {datetime.now().strftime('%Y-%m-%d')}
현재 시간: {datetime.now().strftime('%H:%M')}

예시:
- "내일 오후 2시에 회의 일정 추가해줘" 
  -> {{"title": "회의", "date": "내일 날짜", "time": "14:00", "end_time": null, "location": null, "description": null}}
  
- "12월 25일 크리스마스 파티 일정 만들어줘"
  -> {{"title": "크리스마스 파티", "date": "2024-12-25", "time": null, "end_time": null, "location": null, "description": null}}

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
            "time": None,
            "end_time": None,
            "location": None,
            "description": None
        }
        
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
        
        # 날짜 패턴
        date_patterns = [
            (r'(\d{1,2})월\s*(\d{1,2})일', self._parse_month_day),
            (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', self._parse_iso_date),
            (r'내일', lambda m: (datetime.now() + timedelta(days=1)).date()),
            (r'모레', lambda m: (datetime.now() + timedelta(days=2)).date()),
            (r'오늘', lambda m: datetime.now().date()),
        ]
        
        for pattern, parser in date_patterns:
            match = re.search(pattern, cleaned_message)
            if match:
                schedule_info["date"] = parser(match)
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
        
        # 제목 추출 (나머지 텍스트)
        title = cleaned_message.strip()
        # 시간, 날짜 관련 키워드 제거
        title = re.sub(r'\d{1,2}시\s*(?:\d{1,2}분)?\s*(?:에)?', '', title)
        title = re.sub(r'\d{1,2}월\s*\d{1,2}일\s*(?:에)?', '', title)
        title = re.sub(r'내일|모레|오늘', '', title)
        title = re.sub(r'에\s*$', '', title)  # 끝에 "에" 제거
        title = title.strip()
        
        if title:
            schedule_info["title"] = title
        else:
            schedule_info["title"] = "새 일정"
        
        return self._parse_datetime(schedule_info)
    
    def _parse_datetime(self, schedule_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """추출된 정보를 datetime으로 변환"""
        try:
            now = datetime.now()
            
            # 날짜 처리
            if schedule_info.get("date"):
                date_value = schedule_info["date"]
                if isinstance(date_value, str):
                    # 문자열 날짜 파싱
                    try:
                        # ISO 형식 시도
                        date_obj = datetime.strptime(date_value, "%Y-%m-%d").date()
                    except:
                        try:
                            # 상대적 날짜 처리
                            if "내일" in date_value or "tomorrow" in date_value.lower():
                                date_obj = (now + timedelta(days=1)).date()
                            elif "모레" in date_value or "day after tomorrow" in date_value.lower():
                                date_obj = (now + timedelta(days=2)).date()
                            elif "오늘" in date_value or "today" in date_value.lower():
                                date_obj = now.date()
                            else:
                                # 다른 형식 시도
                                date_obj = now.date()
                        except:
                            date_obj = now.date()
                elif isinstance(date_value, datetime):
                    date_obj = date_value.date()
                elif hasattr(date_value, 'date'):
                    date_obj = date_value.date()
                else:
                    date_obj = now.date()
            else:
                date_obj = now.date()
            
            # 시간 처리
            if schedule_info.get("time"):
                time_str = schedule_info["time"]
                if ":" in time_str:
                    hour, minute = map(int, time_str.split(":"))
                else:
                    hour = int(time_str)
                    minute = 0
                
                start_time = datetime.combine(date_obj, datetime.min.time().replace(hour=hour, minute=minute))
            else:
                # 시간이 없으면 오늘 오후 2시로 기본 설정
                start_time = datetime.combine(date_obj, datetime.min.time().replace(hour=14, minute=0))
            
            # 종료 시간 처리
            if schedule_info.get("end_time"):
                end_time_str = schedule_info["end_time"]
                if ":" in end_time_str:
                    hour, minute = map(int, end_time_str.split(":"))
                else:
                    hour = int(end_time_str)
                    minute = 0
                end_time = datetime.combine(date_obj, datetime.min.time().replace(hour=hour, minute=minute))
            else:
                # 종료 시간이 없으면 시작 시간 + 1시간
                end_time = start_time + timedelta(hours=1)
            
            return {
                "title": schedule_info.get("title") or "새 일정",
                "start_time": start_time,
                "end_time": end_time,
                "location": schedule_info.get("location"),
                "description": schedule_info.get("description")
            }
        except Exception as e:
            print(f"날짜/시간 파싱 오류: {e}")
            return None
    
    def _parse_month_day(self, match) -> datetime.date:
        """월/일 형식 파싱 (예: 12월 25일)"""
        month = int(match.group(1))
        day = int(match.group(2))
        year = datetime.now().year
        return datetime(year, month, day).date()
    
    def _parse_iso_date(self, match) -> datetime.date:
        """ISO 형식 날짜 파싱 (예: 2024-12-25)"""
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        return datetime(year, month, day).date()
    
    def _parse_day_only(self, match) -> datetime.date:
        """일(day)만 있는 경우 파싱 (예: "5일", "10일날")"""
        day = int(match.group(1))
        today = datetime.now()
        year = today.year
        month = today.month
        
        try:
            # 이번 달의 해당 날짜
            target_date = datetime(year, month, day).date()
            
            # 이미 지난 날짜면 다음 달로
            if target_date < today.date():
                if month == 12:
                    month = 1
                    year += 1
                else:
                    month += 1
                target_date = datetime(year, month, day).date()
            
            return target_date
        except ValueError:
            # 유효하지 않은 날짜 (예: 2월 30일)
            # 다음 달의 해당 날짜로 시도
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1
            try:
                return datetime(year, month, day).date()
            except ValueError:
                # 그래도 안 되면 오늘 날짜 반환
                return today.date()
    
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
        # 세션 갱신 (최신 데이터 보장)
        self.session.expire_all()
        
        # 날짜/기간 추출
        date_obj = None
        date_range = None  # (start_date, end_date) 튜플
        
        # 기간 패턴 (우선 순위 높음)
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
        
        # 특정 월 패턴 체크 (예: "11월", "12월")
        month_match = re.search(r'(\d{1,2})\s*월', message)
        if month_match and not date_range:
            month = int(month_match.group(1))
            date_range = self._get_specific_month_range(month)
        
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
                (r'(\d{1,2})\s*일(날)?', self._parse_day_only),  # "5일", "10일날" 패턴
            ]
            
            for pattern, parser in date_patterns:
                match = re.search(pattern, message)
                if match:
                    date_obj = parser(match)
                    break
        
        # 제목 키워드 추출 (중복 제거)
        title_keywords = []
        keyword_patterns = [
            r'(회의|미팅)',
            r'(약속)',
            r'(점심|저녁|식사)',
            r'(수업|강의)',
            r'(면접|인터뷰)',
            r'(발표|프레젠테이션)',
            r'(휴가|연차|반차)',
            r'(출장|외근)',
            r'(여행|휴양)',
        ]
        
        for pattern in keyword_patterns:
            match = re.search(pattern, message)
            if match:
                keyword = match.group(1)
                if keyword not in title_keywords:  # 중복 방지
                    title_keywords.append(keyword)
        
        # 디버깅: 추출된 키워드 로그
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
            statement = statement.where(
                Schedule.start_time >= start_of_period,
                Schedule.start_time <= end_of_period
            )
        elif date_obj:
            # 특정 날짜로 필터링
            start_of_day = datetime.combine(date_obj, datetime.min.time())
            end_of_day = datetime.combine(date_obj, datetime.max.time())
            statement = statement.where(
                Schedule.start_time >= start_of_day,
                Schedule.start_time <= end_of_day
            )
        else:
            # 날짜가 없으면 오늘 이후의 일정만
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
        
        # 삭제된 일정 제외 (이중 확인)
        schedules = [s for s in schedules if not s.is_deleted]
        
        # 디버깅: 검색 결과 로그
        print(f"📊 일정 검색 결과: {len(schedules)}개")
        for schedule in schedules:
            print(f"  - {schedule.title} ({schedule.start_time.strftime('%Y-%m-%d %H:%M')}) [deleted: {schedule.is_deleted}]")
        
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
    
    def _get_specific_month_range(self, month: int):
        """특정 월의 범위 (예: 11월 → 11월 1일 ~ 11월 30일)"""
        today = datetime.now().date()
        year = today.year
        
        # 지정된 월이 현재 월보다 작으면 내년으로 간주 (예: 현재 12월인데 1월 일정 조회하면 내년 1월)
        if month < today.month and today.month >= 10:  # 10월 이후에만 적용
            year += 1
        
        try:
            start_of_month = datetime(year, month, 1).date()
            
            # 해당 월의 마지막 날 계산
            if month == 12:
                end_of_month = datetime(year, 12, 31).date()
            else:
                end_of_month = datetime(year, month + 1, 1).date() - timedelta(days=1)
            
            return (start_of_month, end_of_month)
        except ValueError:
            # 유효하지 않은 월인 경우 이번 달 반환
            return self._get_this_month_range()
    
    def format_schedule_response(self, schedule: Schedule, action: str = "create") -> str:
        """일정 응답 메시지 생성"""
        start_time_str = schedule.start_time.strftime("%Y년 %m월 %d일 %H:%M")
        end_time_str = schedule.end_time.strftime("%H:%M") if schedule.end_time else "미정"
        
        if action == "create":
            response = f"✅ 일정이 추가되었습니다!\n\n"
        elif action == "delete":
            response = f"🗑️ 일정이 삭제되었습니다!\n\n"
        elif action == "update":
            response = f"✏️ 일정이 수정되었습니다!\n\n"
        else:
            response = f"📅 일정 정보\n\n"
        
        response += f"📅 **{schedule.title}**\n"
        response += f"🕐 {start_time_str}"
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
            # 부정 질문인 경우 (예: "~일은 없는데?")
            if re.search(r'없는데|없어|없지|없나', message):
                return f"✅ 맞아요! {period_str} 일정이 없습니다.\n\n일정을 추가하시려면 \"일정 추가\"라고 말씀해주세요!"
            else:
                return f"🔍 {period_str} 일정을 찾을 수 없습니다.\n\n다른 날짜나 키워드로 다시 검색해보세요!"
        
        # 일정이 1개인 경우 - 상세 정보 표시
        if len(schedules) == 1:
            schedule = schedules[0]
            response = f"📅 {period_str} 일정을 찾았어요!\n\n"
            response += f"**{schedule.title}**\n"
            
            # 시작일과 종료일 표시
            start_date = schedule.start_time.strftime('%Y년 %m월 %d일')
            start_time = schedule.start_time.strftime('%H:%M')
            
            if schedule.end_time:
                end_date = schedule.end_time.strftime('%Y년 %m월 %d일')
                end_time = schedule.end_time.strftime('%H:%M')
                
                # 같은 날이면 시간만, 다른 날이면 날짜까지 표시
                if schedule.start_time.date() == schedule.end_time.date():
                    response += f"🕐 {start_date} {start_time} ~ {end_time}\n"
                else:
                    response += f"🕐 **시작**: {start_date} {start_time}\n"
                    response += f"🕐 **종료**: {end_date} {end_time}\n"
                    
                    # 기간 계산
                    duration = (schedule.end_time.date() - schedule.start_time.date()).days + 1
                    response += f"📆 **기간**: {duration}일\n"
            else:
                response += f"🕐 {start_date} {start_time}\n"
            
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
            response += f"\n... 외 {len(schedules) - 5}개의 일정이 더 있어요"
        
        return response

