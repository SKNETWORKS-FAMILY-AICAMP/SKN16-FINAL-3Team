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
        """일정 관련 요청 타입 반환: 'create', 'delete', 'update', 'list', None"""
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
        
        # 조회 패턴
        list_patterns = [
            r'일정\s*(보여|보여줘|목록|리스트|조회|확인)',
            r'일정\s*(보여|보여줘|목록|리스트|조회|확인)\s*해\s*줘',
        ]
        for pattern in list_patterns:
            if re.search(pattern, message_lower):
                return 'list'
        
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

