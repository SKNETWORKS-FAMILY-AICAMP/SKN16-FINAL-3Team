"""
연수원(Training Center) 데이터 시뮬레이션 & API 서비스
"""
from __future__ import annotations

import random
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, func, or_
from sqlmodel import Session, select

from app.models.training_center import TrainingCohort, TrainingCenterRecord


class TrainingCenterService:
    """연수원 데이터 생성 및 조회 로직"""

    MONTH_HISTORY = 12
    MONTHLY_NEWCOMERS = 30
    MENTOR_POOL_SIZE = 60
    EMPLOYEE_START = 2_025_000

    CATEGORY_KEYS = [
        "금융영업",
        "금융상품개발",
        "신용분석",
        "자산운용",
        "금융영업지원",
        "증권외환",
    ]

    MBTI_OPTIONS = [
        "INTJ",
        "INTP",
        "ENTJ",
        "ENTP",
        "INFJ",
        "INFP",
        "ENFJ",
        "ENFP",
        "ISTJ",
        "ISFJ",
        "ESTJ",
        "ESFJ",
        "ISTP",
        "ISFP",
        "ESTP",
        "ESFP",
    ]

    POSITIONS = ["사원", "주임", "대리"]

    DEPARTMENTS = ["외환", "수신", "여신", "디지털", "자산관리", "기업금융"]

    TEAM_BY_DEPT = {
        "외환": ["글로벌결제팀", "환리스크팀", "무역금융팀"],
        "수신": ["리테일전략팀", "상품혁신팀", "채널운영팀"],
        "여신": ["여신심사팀", "기업여신팀", "가계여신팀"],
        "디지털": ["디지털전략팀", "모바일뱅킹팀", "AI혁신팀"],
        "자산관리": ["WM전략팀", "VIP컨설팅팀", "연금솔루션팀"],
        "기업금융": ["투자금융팀", "IB전략팀", "글로벌IB팀"],
    }

    LAST_NAMES = [
        "김",
        "이",
        "박",
        "정",
        "최",
        "조",
        "윤",
        "장",
        "임",
        "한",
        "오",
        "서",
        "신",
        "권",
        "황",
        "안",
        "송",
        "유",
        "홍",
        "양",
    ]

    FIRST_NAME_LEADING = [
        "민",
        "서",
        "도",
        "하",
        "지",
        "아",
        "유",
        "준",
        "시",
        "태",
        "수",
        "예",
        "다",
        "채",
        "주",
        "건",
        "현",
        "연",
        "재",
        "가",
    ]

    FIRST_NAME_TRAILING = [
        "현",
        "우",
        "윤",
        "림",
        "진",
        "은",
        "율",
        "빈",
        "수",
        "영",
        "정",
        "미",
        "환",
        "혁",
        "훈",
        "열",
        "솔",
        "나",
        "형",
        "람",
    ]

    EMAIL_DOMAINS = [
        "training.bank.local",
        "academy.bank.co",
        "kfinance.academy",
    ]

    PHONE_PREFIXES = ["010"]

    CITY_OPTIONS = [
        "서울특별시",
        "부산광역시",
        "인천광역시",
        "대구광역시",
        "대전광역시",
        "광주광역시",
        "울산광역시",
        "세종특별자치시",
        "고양시",
        "성남시",
        "용인시",
        "수원시",
        "청주시",
        "전주시",
        "창원시",
        "천안시",
    ]

    HOBBY_OPTIONS = [
        "스포츠",
        "영화감상",
        "독서",
        "요리",
        "러닝",
        "사진",
        "게임",
        "음악",
        "여행",
        "원예",
    ]

    BRANCH_TEAMS = [
        "창구영업1팀",
        "창구영업2팀",
        "VIP창구팀",
        "기업창구팀",
        "외환창구팀",
        "디지털창구팀",
    ]

    def __init__(self, session: Session):
        self.session = session
        self.random = random.Random()
        self._employee_sequence: Optional[int] = None

    # ------------------------------------------------------------------ #
    # Public APIs
    # ------------------------------------------------------------------ #
    def rebuild_dataset(self) -> Dict[str, Any]:
        """신입(멘티)·기존 사원(멘토) 데이터를 초기화 후 재생성"""
        self.session.exec(delete(TrainingCenterRecord))
        self.session.exec(delete(TrainingCohort))
        self.session.commit()
        self._employee_sequence = self.EMPLOYEE_START

        today = date.today().replace(day=1)
        start_month = self._add_months(today, -(self.MONTH_HISTORY - 1))

        mentee_total = 0
        mentor_total = 0

        # 신입 기수 생성
        for idx in range(self.MONTH_HISTORY):
            cohort_date = self._add_months(start_month, idx)
            cohort = self._create_cohort(
                label=f"{cohort_date.year}년 {cohort_date.month}월 신입 기수",
                cohort_date=cohort_date,
                cohort_index=idx + 1,
            )
            new_records = self._generate_records_for_cohort(
                cohort=cohort,
                slots=self.MONTHLY_NEWCOMERS,
                employee_type="mentee",
            )
            mentee_total += len(new_records)

        # 멘토 풀 생성 (기존 사원)
        mentor_cohort = self._create_cohort(
            label=f"{today.year}년 멘토 풀",
            cohort_date=date(today.year, 12, 31),
            cohort_index=0,
        )
        mentor_records = self._generate_records_for_cohort(
            cohort=mentor_cohort,
            slots=self.MENTOR_POOL_SIZE,
            employee_type="mentor",
        )
        mentor_total += len(mentor_records)

        self.session.commit()

        last_synced_at = self.session.exec(
            select(func.max(TrainingCenterRecord.created_at))
        ).one()

        return {
            "message": "연수원 DB 재생성 완료",
            "generated_months": self.MONTH_HISTORY,
            "generated_mentees": mentee_total,
            "generated_mentors": mentor_total,
            "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
            "total_mentees": self._count_records("mentee"),
            "total_mentors": self._count_records("mentor"),
        }

    def list_records(
        self,
        page: int,
        page_size: int,
        cohort_date: Optional[date] = None,
        search: Optional[str] = None,
        employee_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """연수원 데이터 조회 (페이징)"""
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)

        filters = []
        if cohort_date:
            filters.append(TrainingCenterRecord.cohort_date == cohort_date)
        if search:
            like_term = f"%{search}%"
            filters.append(
                or_(
                    TrainingCenterRecord.name.ilike(like_term),
                    TrainingCenterRecord.employee_number.ilike(like_term),
                )
            )
        if employee_type:
            filters.append(TrainingCenterRecord.employee_type == employee_type)

        count_query = select(func.count()).select_from(TrainingCenterRecord)
        if filters:
            count_query = count_query.where(*filters)
        total = self.session.exec(count_query).one()

        query = (
            select(TrainingCenterRecord)
            .where(*filters)
            .order_by(
                TrainingCenterRecord.cohort_date.desc(),
                TrainingCenterRecord.cohort_slot.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        records = self.session.exec(query).all()

        cohort_query = (
            select(
                TrainingCohort.cohort_date,
                TrainingCohort.label,
                func.count(TrainingCenterRecord.id).label("count"),
            )
            .join(
                TrainingCenterRecord,
                TrainingCenterRecord.cohort_id == TrainingCohort.id,
                isouter=True,
            )
            .group_by(TrainingCohort.id, TrainingCohort.cohort_date, TrainingCohort.label)
            .order_by(TrainingCohort.cohort_date.desc())
        )
        if employee_type:
            cohort_query = cohort_query.where(
                TrainingCenterRecord.employee_type == employee_type
            )
        cohort_stats = self.session.exec(cohort_query).all()

        last_synced_at = self.session.exec(
            select(func.max(TrainingCenterRecord.created_at))
        ).one()

        return {
            "records": [self._serialize_record(r) for r in records],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_cohorts": len(cohort_stats),
            "cohorts": [
                {
                    "date": row.cohort_date.isoformat(),
                    "label": row.label,
                    "count": int(row.count or 0),
                }
                for row in cohort_stats
            ],
            "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
            "employee_type": employee_type,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _get_or_create_cohort(
        self, index: int, cohort_date: date
    ) -> Tuple[TrainingCohort, bool]:
        cohort = self.session.exec(
            select(TrainingCohort).where(TrainingCohort.cohort_date == cohort_date)
        ).first()
        if cohort:
            return cohort, False

        label = f"{cohort_date.year}년 {cohort_date.month}월 {cohort_date.day}일 {index}기"
        cohort = TrainingCohort(cohort_date=cohort_date, cohort_index=index, label=label)
        self.session.add(cohort)
        self.session.flush()
        return cohort, True

    def _create_cohort(self, label: str, cohort_date: date, cohort_index: int) -> TrainingCohort:
        cohort = TrainingCohort(
            cohort_date=cohort_date,
            cohort_index=cohort_index,
            label=label,
        )
        self.session.add(cohort)
        self.session.flush()
        return cohort

    def _generate_records_for_cohort(
        self,
        cohort: TrainingCohort,
        slots: int,
        employee_type: str,
    ) -> List[TrainingCenterRecord]:
        created_records: List[TrainingCenterRecord] = []
        for slot in range(slots):
            record_payload = self._build_record_payload(
                cohort=cohort,
                slot=slot,
                employee_type=employee_type,
            )
            record = TrainingCenterRecord(**record_payload)
            self.session.add(record)
            created_records.append(record)
        return created_records

    def _build_record_payload(
        self,
        cohort: TrainingCohort,
        slot: int,
        employee_type: str,
    ) -> Dict[str, Any]:
        name = self._generate_name()
        employee_number = self._next_employee_number()
        department = "영업지원본부"
        team = self.random.choice(self.BRANCH_TEAMS)
        mbti = self.random.choice(self.MBTI_OPTIONS)
        position = self.random.choice(self.POSITIONS)
        birth = self._random_birth()
        email = f"{employee_number}@{self.random.choice(self.EMAIL_DOMAINS)}"
        phone = self._random_phone()
        city = self.random.choice(self.CITY_OPTIONS)
        hobbies = self._random_hobbies()
        address = f"{city} {self.random.choice(['중앙로', '역전로', '시청로', '문화로'])}"
        question_scores, section_scores, total_score = self._generate_scores(employee_type)

        if employee_type == "mentee":
            join_year = cohort.cohort_date.year
        else:
            current_year = date.today().year
            join_year = self.random.randint(current_year - 8, current_year - 2)

        return {
            "cohort_id": cohort.id,
            "cohort_slot": slot,
            "cohort_date": cohort.cohort_date,
            "cohort_label": cohort.label,
            "employee_type": employee_type,
            "name": name,
            "employee_number": employee_number,
            "join_year": join_year,
            "mbti": mbti,
            "position": position,
            "department": department,
            "team": team,
            "city": city,
            "hobbies": hobbies,
            "birth": birth,
            "email": email,
            "phone": phone,
            "address": address,
            "section_scores": section_scores,
            "question_scores": question_scores,
            "total_score": total_score,
        }

    def _generate_scores(
        self, employee_type: str
    ) -> Tuple[Dict[str, List[int]], Dict[str, int], int]:
        question_scores: Dict[str, List[int]] = {}
        section_totals: Dict[str, int] = {}
        base_prob = 0.85 if employee_type == "mentor" else 0.6
        for category in self.CATEGORY_KEYS:
            questions = [
                1 if self.random.random() < base_prob else 0 for _ in range(10)
            ]
            question_scores[category] = questions
            section_totals[category] = sum(questions)

        total_score = sum(section_totals.values())
        return question_scores, section_totals, total_score

    def _generate_name(self) -> str:
        last = self.random.choice(self.LAST_NAMES)
        first = self.random.choice(self.FIRST_NAME_LEADING) + self.random.choice(
            self.FIRST_NAME_TRAILING
        )
        return f"{last}{first}"

    def _next_employee_number(self) -> str:
        if self._employee_sequence is None:
            last_record = self.session.exec(
                select(TrainingCenterRecord)
                .order_by(TrainingCenterRecord.employee_number.desc())
                .limit(1)
            ).first()
            if last_record:
                self._employee_sequence = int(last_record.employee_number)
            else:
                self._employee_sequence = self.EMPLOYEE_START
        self._employee_sequence += 1
        return f"{self._employee_sequence:07d}"

    def _random_birth(self) -> date:
        start = date(1998, 1, 1).toordinal()
        end = date(2005, 12, 31).toordinal()
        ordinal = self.random.randint(start, end)
        return date.fromordinal(ordinal)

    def _random_phone(self) -> str:
        prefix = self.random.choice(self.PHONE_PREFIXES)
        mid = self.random.randint(1000, 9999)
        last = self.random.randint(1000, 9999)
        return f"{prefix}-{mid:04d}-{last:04d}"

    def _add_months(self, input_date: date, months: int) -> date:
        year = input_date.year + (input_date.month - 1 + months) // 12
        month = (input_date.month - 1 + months) % 12 + 1
        return date(year, month, 1)

    def _random_hobbies(self) -> List[str]:
        count = self.random.randint(1, 2)
        return self.random.sample(self.HOBBY_OPTIONS, count)

    def _count_records(self, employee_type: str) -> int:
        return self.session.exec(
            select(func.count())
            .select_from(TrainingCenterRecord)
            .where(TrainingCenterRecord.employee_type == employee_type)
        ).one()

    def _serialize_record(self, record: TrainingCenterRecord) -> Dict[str, Any]:
        return {
            "id": record.id,
            "name": record.name,
            "employee_number": record.employee_number,
            "cohort_date": record.cohort_date.isoformat(),
            "cohort_label": record.cohort_label,
            "cohort_slot": record.cohort_slot,
            "employee_type": record.employee_type,
            "mbti": record.mbti,
            "position": record.position,
            "department": record.department,
            "team": record.team,
            "join_year": record.join_year,
            "birth": record.birth.isoformat(),
            "email": record.email,
            "phone": record.phone,
            "address": record.address,
            "city": record.city,
            "hobbies": record.hobbies,
            "section_scores": record.section_scores,
            "question_scores": record.question_scores,
            "total_score": record.total_score,
            "created_at": record.created_at.isoformat(),
        }


