"""
연수원(Training Center) 데이터 시뮬레이션 & API 서비스
"""
from __future__ import annotations

import random
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, func, or_
from sqlmodel import Session, select

from app.models.matching import MatchingReport, MatchingResult
from app.models.training_center import TrainingCohort, TrainingCenterRecord
from app.models.user import User, UserRole
from app.utils.auth import get_password_hash


class TrainingCenterService:
    """연수원 데이터 생성 및 조회 로직"""

    MONTH_HISTORY = 1  # 현재 달(11월)만 생성
    MONTHLY_NEWCOMERS = 120  # 한 기수당 120명
    MENTOR_POOL_SIZE = 60  # 멘티:멘토 = 2:1 비율 (120명 멘티 -> 60명 멘토)

    CATEGORY_KEYS = [
        "금융영업",
        "상품개발 및 운용",
        "신용분석 및 리스크관리",
        "외환",
        "은행지식 및 관련법률",
        "하경은행",
    ]

    # MBTI 옵션 및 가중치 (한국 실제 분포 기반)
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
    # 한국 MBTI 분포 가중치 (ISFJ 13%, ESFJ 10%, ISTJ 9%, ESTJ 8%, 나머지 균등 분배)
    MBTI_WEIGHTS = [0.04, 0.04, 0.05, 0.04, 0.05, 0.05, 0.06, 0.06, 0.09, 0.13, 0.08, 0.10, 0.04, 0.05, 0.05, 0.05]

    POSITIONS = ["사원"]  # 신입은 모두 사원

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

    # 남자 이름
    MALE_FIRST_NAME_LEADING = [
        "민", "서", "도", "하", "지", "유", "준", "시", "태", "수",
        "건", "현", "연", "재", "가", "동", "성", "영", "호", "우",
    ]
    MALE_FIRST_NAME_TRAILING = [
        "현", "우", "윤", "진", "환", "혁", "훈", "열", "형", "람",
        "석", "준", "호", "성", "민", "재", "영", "수", "태", "원",
    ]

    # 여자 이름
    FEMALE_FIRST_NAME_LEADING = [
        "민", "서", "하", "지", "아", "유", "예", "다", "채", "주",
        "현", "연", "수", "가", "은", "혜", "지", "서", "예", "나",
    ]
    FEMALE_FIRST_NAME_TRAILING = [
        "림", "은", "율", "빈", "영", "정", "미", "솔", "나", "람",
        "아", "연", "희", "진", "수", "영", "미", "은", "혜", "지",
    ]

    EMAIL_DOMAINS = [
        "training.bank.local",
        "academy.bank.co",
        "kfinance.academy",
    ]

    PHONE_PREFIXES = ["010"]

    # 거주지 옵션 및 가중치 (인구 분포 기반)
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
    # 인구 분포 기반 가중치 (서울 25%, 부산 10%, 인천 8%, 대구 5%, 나머지 균등 분배)
    CITY_WEIGHTS = [0.25, 0.10, 0.08, 0.05, 0.05, 0.05, 0.05, 0.03, 0.06, 0.06, 0.06, 0.05, 0.04, 0.03, 0.03, 0.03]

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

    # 전공 옵션 및 가중치 (실제 대학생 전공 분포 기반)
    MAJOR_OPTIONS = [
        "경제학",
        "경영학",
        "회계학",
        "금융학",
        "통계학",
        "수학",
        "컴퓨터공학",
        "산업공학",
        "법학",
        "행정학",
        "국제통상",
        "영어영문학",
        "중어중문학",
        "심리학",
        "사회학",
    ]
    # 전공 분포 가중치 (경영학 20%, 경제학 18%, 회계학 12%, 금융학 10%, 나머지 균등)
    MAJOR_WEIGHTS = [0.18, 0.20, 0.12, 0.10, 0.05, 0.04, 0.08, 0.04, 0.05, 0.04, 0.03, 0.03, 0.02, 0.02, 0.02]

    CAREER_GOAL_OPTIONS = [
        "VIP자산관리전문가",
        "기업금융전문가",
        "여신심사전문가",
        "디지털금융전문가",
        "외환딜러",
        "PB(프라이빗뱅커)",
        "지점장",
        "본부전문직",
        "리스크관리전문가",
        "금융상품개발자",
    ]

    # 팀 비율: 창구영업 60%, VIP/외환/디지털/기업 각 10%
    BRANCH_TEAMS = [
        "창구영업1팀",
        "창구영업2팀",
        "VIP창구팀",
        "외환창구팀",
        "디지털창구팀",
        "기업창구팀",
    ]
    
    # 팀 비율 가중치 (창구영업 60%, 나머지 각 10%)
    TEAM_WEIGHTS = [0.3, 0.3, 0.1, 0.1, 0.1, 0.1]  # 창구영업1팀, 창구영업2팀, VIP, 외환, 디지털, 기업

    def __init__(self, session: Session):
        self.session = session
        self.random = random.Random()

    # ------------------------------------------------------------------ #
    # Public APIs
    # ------------------------------------------------------------------ #
    def rebuild_dataset(
        self,
        selected_cohort_dates: Optional[List[date]] = None,
        create_accounts: bool = False,
        create_mentees: bool = True,
        create_mentors: bool = True,
    ) -> Dict[str, Any]:
        """신입(멘티)·기존 사원(멘토) 데이터를 초기화 후 재생성
        
        Args:
            selected_cohort_dates: 생성할 기수 날짜 리스트 (None이면 모든 기수 생성)
            create_accounts: User 계정도 함께 생성할지 여부
            create_mentees: 멘티 생성 여부
            create_mentors: 멘토 생성 여부
        """
        # 매칭 결과/리포트 → 연수원 레코드 순으로 삭제 (FK 보호)
        self.session.exec(delete(MatchingResult))
        self.session.exec(delete(MatchingReport))
        self.session.exec(delete(TrainingCenterRecord))
        self.session.exec(delete(TrainingCohort))
        self.session.commit()

        today = date.today().replace(day=1)
        start_month = self._add_months(today, -(self.MONTH_HISTORY - 1))

        mentee_total = 0
        mentor_total = 0
        created_accounts = 0
        all_created_records: List[TrainingCenterRecord] = []

        # 신입 기수 생성
        if selected_cohort_dates:
            # 선택된 기수만 생성 (각 기수마다 멘티 120명)
            for cohort_date in selected_cohort_dates:
                # 기수 라벨 생성 (2025년 1기, 2기, 3기, 4기 형식)
                quarter = (cohort_date.month - 1) // 3 + 1
                cohort = self._create_cohort(
                    label=f"{cohort_date.year}년 {quarter}기",
                    cohort_date=cohort_date,
                    cohort_index=quarter,
                )
                
                # 멘티 생성
                if create_mentees:
                    mentee_records = self._generate_records_for_cohort(
                        cohort=cohort,
                        slots=self.MONTHLY_NEWCOMERS,
                        employee_type="mentee",
                    )
                    # 한 기수 내에서 이름 순서로 사번 부여
                    self._assign_employee_numbers_by_name(mentee_records, cohort_date)
                    mentee_total += len(mentee_records)
                    all_created_records.extend(mentee_records)
            
            # 멘토 풀 생성 (기수와 무관하게 한 번만 생성)
            if create_mentors:
                today = date.today()
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
                # 멘토는 입사년도별로 그룹화하여 사번 부여
                self._assign_employee_numbers_by_join_year(mentor_records)
                mentor_total += len(mentor_records)
                all_created_records.extend(mentor_records)
        else:
            # 모든 기수 생성 (기존 로직) - 옵션 무시하고 모두 생성
            for idx in range(self.MONTH_HISTORY):
                cohort_date = self._add_months(start_month, idx)
                cohort = self._create_cohort(
                    label=f"{cohort_date.year}년 {cohort_date.month}월 신입 기수",
                    cohort_date=cohort_date,
                    cohort_index=idx + 1,
                )
                if create_mentees:
                    new_records = self._generate_records_for_cohort(
                        cohort=cohort,
                        slots=self.MONTHLY_NEWCOMERS,
                        employee_type="mentee",
                    )
                    # 한 기수 내에서 이름 순서로 사번 부여
                    self._assign_employee_numbers_by_name(new_records, cohort_date)
                    mentee_total += len(new_records)
                    all_created_records.extend(new_records)

            # 멘토 풀 생성 (기존 사원) - selected_cohort_dates가 없을 때만
            if create_mentors:
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
                # 멘토는 입사년도별로 그룹화하여 사번 부여 (기수 불필요)
                self._assign_employee_numbers_by_join_year(mentor_records)
                mentor_total += len(mentor_records)
                all_created_records.extend(mentor_records)

        self.session.commit()

        # User 계정 생성 (옵션이 활성화된 경우)
        if create_accounts and all_created_records:
            created_accounts = self._create_user_accounts(all_created_records)
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
            "created_accounts": created_accounts,
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
        page_size = min(max(page_size, 1), 10000)

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
        slot_start: int = 0,
    ) -> List[TrainingCenterRecord]:
        created_records: List[TrainingCenterRecord] = []
        for slot in range(slot_start, slot_start + slots):
            record_payload = self._build_record_payload(
                cohort=cohort,
                slot=slot,
                employee_type=employee_type,
            )
            record = TrainingCenterRecord(**record_payload)
            self.session.add(record)
            created_records.append(record)
        # flush 없이 이름으로 정렬만 수행 (사번은 나중에 부여)
        return created_records

    def _build_record_payload(
        self,
        cohort: TrainingCohort,
        slot: int,
        employee_type: str,
    ) -> Dict[str, Any]:
        # 성별 생성 (50:50)
        gender = self.random.choice(["남성", "여성"])
        
        # 직급 및 연차 설정 (생년월일 생성 전에 입사년도 결정 필요)
        if employee_type == "mentee":
            position = "사원"
            join_year = cohort.cohort_date.year
        else:
            # 멘토 자격 기준:
            # - 일반 멘토: 입사 후 5년 이상 근무
            # - 선임급: 4년 이상 근무
            # - 책임급: 10년 이상 근무
            # 멘토: 선임 80%, 일반 멘토(5년 이상) 15%, 책임 5%
            position_choice = self.random.choices(
                ["선임", "사원", "책임"],
                weights=[0.80, 0.15, 0.05],
                k=1
            )[0]
            position = position_choice
            
            current_year = date.today().year
            # 연차를 직급과 멘토 자격 기준에 맞게 설정
            if position == "사원":
                # 일반 멘토: 5년 이상 근무 (5-15년차)
                join_year = self.random.randint(current_year - 15, current_year - 5)
            elif position == "선임":
                # 선임급: 4년 이상 근무 (4-10년차)
                join_year = self.random.randint(current_year - 10, current_year - 4)
            else:  # 책임
                # 책임급: 10년 이상 근무 (10-20년차)
                join_year = self.random.randint(current_year - 20, current_year - 10)
        
        # 성별에 맞는 이름 생성
        name = self._generate_name(gender)
        
        # 입사년도와 성별에 맞는 생년월일 생성
        birth = self._random_birth(join_year, gender)
        
        # 사번은 나중에 이름 순서로 부여 (임시로 unique한 값 사용)
        employee_number = f"TEMP_{cohort.id}_{slot}"
        department = "영업지원본부"
        # 팀 비율에 따라 선택
        team = self.random.choices(self.BRANCH_TEAMS, weights=self.TEAM_WEIGHTS, k=1)[0]
        # MBTI는 실제 분포를 고려하여 가중치 기반 선택
        mbti = self.random.choices(self.MBTI_OPTIONS, weights=self.MBTI_WEIGHTS, k=1)[0]
        phone = self._random_phone()
        # 거주지는 인구 분포를 고려하여 가중치 기반 선택
        city = self.random.choices(self.CITY_OPTIONS, weights=self.CITY_WEIGHTS, k=1)[0]
        hobby1, hobby2 = self._random_hobbies_pair()
        # 전공은 실제 분포를 고려하여 가중치 기반 선택
        major = self.random.choices(self.MAJOR_OPTIONS, weights=self.MAJOR_WEIGHTS, k=1)[0]
        career_goal = self.random.choice(self.CAREER_GOAL_OPTIONS)
        address = f"{city} {self.random.choice(['중앙로', '역전로', '시청로', '문화로'])}"
        question_scores, section_scores, total_score = self._generate_scores(employee_type)

        # 멘토의 경우 cohort_date를 입사년도 기반으로 설정 (기수 불필요)
        if employee_type == "mentor":
            mentor_cohort_date = date(join_year, 1, 1)  # 입사년도 1월 1일
            mentor_cohort_label = f"{join_year}년 입사"
        else:
            mentor_cohort_date = cohort.cohort_date
            mentor_cohort_label = cohort.label
        
        return {
            "cohort_id": cohort.id,
            "cohort_slot": slot,
            "cohort_date": mentor_cohort_date,
            "cohort_label": mentor_cohort_label,
            "employee_type": employee_type,
            "name": name,
            "employee_number": employee_number,
            "gender": gender,
            "join_year": join_year,
            "mbti": mbti,
            "position": position,
            "department": department,
            "team": team,
            "city": city,
            "hobby1": hobby1,
            "hobby2": hobby2,
            "major": major,
            "career_goal": career_goal,
            "birth": birth,
            "phone": phone,
            "address": address,
            "section_scores": section_scores,
            "question_scores": question_scores,
            "total_score": total_score,
        }

    def _generate_scores(
        self, employee_type: str
    ) -> Tuple[Dict[str, List[int]], Dict[str, int], float]:
        """6대 역량 지표 점수 생성 (각 카테고리당 10점 만점, 총점 60점 만점)"""
        question_scores: Dict[str, List[int]] = {}
        section_totals: Dict[str, int] = {}

        # 먼저 각 카테고리별로 문제별 정답 여부 생성 (0 또는 1)
        for category in self.CATEGORY_KEYS:
            # 멘토는 높은 점수, 멘티는 낮은 점수
            if employee_type == "mentor":
                # 멘토: 7-10점 범위 (70-100% 정답률)
                correct_count = self.random.randint(7, 10)
            else:
                # 멘티: 6-9점 범위 (60-90% 정답률)
                correct_count = self.random.randint(6, 9)
            
            # 10문제 중 correct_count개를 정답(1)으로 설정
            questions = [0] * 10
            correct_indices = self.random.sample(range(10), correct_count)
            for idx in correct_indices:
                questions[idx] = 1
            
            # 섞기
            self.random.shuffle(questions)
            
            question_scores[category] = questions
            # 섹션 점수는 정답 개수 (0-10점)
            section_totals[category] = correct_count

        # 총점은 모든 섹션 점수의 합 (최대 60점)
        total_score = sum(section_totals.values())
        return question_scores, section_totals, float(total_score)

    def _generate_name(self, gender: str) -> str:
        """성별에 맞는 이름 생성"""
        last = self.random.choice(self.LAST_NAMES)
        if gender == "남성":
            first = self.random.choice(self.MALE_FIRST_NAME_LEADING) + self.random.choice(
                self.MALE_FIRST_NAME_TRAILING
            )
        else:  # 여성
            first = self.random.choice(self.FEMALE_FIRST_NAME_LEADING) + self.random.choice(
                self.FEMALE_FIRST_NAME_TRAILING
            )
        return f"{last}{first}"

    def _assign_employee_numbers_by_name(
        self, records: List[TrainingCenterRecord], cohort_date: date
    ) -> None:
        """한 기수 내에서 이름 순서로 사번 부여 (202507001 형식)"""
        # 이름으로 정렬
        sorted_records = sorted(records, key=lambda r: r.name)
        
        year_month = f"{cohort_date.year}{cohort_date.month:02d}"
        for idx, record in enumerate(sorted_records, start=1):
            employee_number = f"{year_month}{idx:03d}"
            record.employee_number = employee_number
            # 이메일도 사번 기반으로 업데이트 (사번@bank.com 형식)
            record.email = f"{employee_number}@bank.com"

    def _assign_employee_numbers_by_join_year(
        self, records: List[TrainingCenterRecord]
    ) -> None:
        """멘토의 경우 입사년도별로 그룹화하여 이름 순서로 사번 부여"""
        # 입사년도별로 그룹화
        by_year: Dict[int, List[TrainingCenterRecord]] = {}
        for record in records:
            if record.join_year not in by_year:
                by_year[record.join_year] = []
            by_year[record.join_year].append(record)
        
        # 각 입사년도별로 이름 순서로 정렬하여 사번 부여
        for join_year, year_records in sorted(by_year.items()):
            sorted_records = sorted(year_records, key=lambda r: r.name)
            year_str = f"{join_year}"
            
            for idx, record in enumerate(sorted_records, start=1):
                # 입사년도 + 01월 + 순번 (예: 202001001)
                employee_number = f"{year_str}01{idx:03d}"
                record.employee_number = employee_number
                # 이메일도 사번 기반으로 업데이트
                record.email = f"{employee_number}@bank.com"

    def _random_birth(self, join_year: int, gender: str) -> date:
        """입사년도와 성별에 맞는 생년월일 생성
        - 남성: 25-27세 입사 (군대 고려)
        - 여성: 23-25세 입사
        """
        if gender == "남성":
            # 남성: 입사년도 기준 25-27세
            birth_year_min = join_year - 27
            birth_year_max = join_year - 25
        else:  # 여성
            # 여성: 입사년도 기준 23-25세
            birth_year_min = join_year - 25
            birth_year_max = join_year - 23
        
        # 생년월일 랜덤 생성 (1월 1일 ~ 12월 31일)
        birth_year = self.random.randint(birth_year_min, birth_year_max)
        birth_month = self.random.randint(1, 12)
        # 월별 최대 일수 계산
        if birth_month in [1, 3, 5, 7, 8, 10, 12]:
            max_day = 31
        elif birth_month in [4, 6, 9, 11]:
            max_day = 30
        else:  # 2월
            # 윤년 체크 (간단히 4로 나누어떨어지면 윤년)
            max_day = 29 if birth_year % 4 == 0 else 28
        birth_day = self.random.randint(1, max_day)
        return date(birth_year, birth_month, birth_day)

    def _random_phone(self) -> str:
        prefix = self.random.choice(self.PHONE_PREFIXES)
        # 중간 4자리의 첫 번째 자리는 0이나 1이 오면 안 됨 (2~9만 가능)
        mid_first = self.random.randint(2, 9)
        mid_rest = self.random.randint(0, 999)
        mid = mid_first * 1000 + mid_rest
        last = self.random.randint(1000, 9999)
        return f"{prefix}-{mid:04d}-{last:04d}"

    def _add_months(self, input_date: date, months: int) -> date:
        year = input_date.year + (input_date.month - 1 + months) // 12
        month = (input_date.month - 1 + months) % 12 + 1
        return date(year, month, 1)

    def _random_hobbies_pair(self) -> Tuple[Optional[str], Optional[str]]:
        """취미 2개를 선택 (취미1, 취미2)"""
        selected = self.random.sample(self.HOBBY_OPTIONS, min(2, len(self.HOBBY_OPTIONS)))
        hobby1 = selected[0] if len(selected) > 0 else None
        hobby2 = selected[1] if len(selected) > 1 else None
        return hobby1, hobby2

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
            "gender": record.gender,
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
            "hobby1": record.hobby1,
            "hobby2": record.hobby2,
            "major": record.major,
            "career_goal": record.career_goal,
            "section_scores": record.section_scores,
            "question_scores": record.question_scores,
            "total_score": record.total_score,
            "created_at": record.created_at.isoformat(),
        }

    def _create_user_accounts(self, records: List[TrainingCenterRecord]) -> int:
        """TrainingCenterRecord를 기반으로 User 계정 생성
        
        Args:
            records: 생성할 TrainingCenterRecord 리스트
            
        Returns:
            생성된 계정 수
        """
        created_count = 0
        
        for record in records:
            # 이미 존재하는 계정인지 확인
            existing_user = self.session.exec(
                select(User).where(User.email == record.email)
            ).first()
            
            if existing_user:
                continue  # 이미 존재하면 스킵
            
            # 생년월일을 비밀번호로 사용 (YYYYMMDD 형식)
            birth_str = record.birth.strftime("%Y%m%d")
            password_hash = get_password_hash(birth_str)
            
            # 역할 결정
            role = UserRole.MENTEE if record.employee_type == "mentee" else UserRole.MENTOR
            
            # User 계정 생성
            user = User(
                email=record.email,
                hashed_password=password_hash,
                name=record.name,
                role=role,
                employee_number=record.employee_number,
                join_year=record.join_year,
                position=record.position,
                team=record.team,
                phone=record.phone,
                mbti=record.mbti,
                hobbies=record.hobby1 or "",
            )
            self.session.add(user)
            created_count += 1
        
        return created_count

    def delete_records(self, record_ids: List[int]) -> int:
        """선택된 레코드 삭제"""
        # 매칭 결과에서 해당 레코드 참조 삭제
        self.session.exec(
            delete(MatchingResult).where(
                or_(
                    MatchingResult.mentee_id.in_(record_ids),
                    MatchingResult.mentor_id.in_(record_ids),
                )
            )
        )
        
        # 레코드 삭제
        result = self.session.exec(
            delete(TrainingCenterRecord).where(TrainingCenterRecord.id.in_(record_ids))
        )
        self.session.commit()
        return result.rowcount

    def delete_all_records(self) -> int:
        """전체 연수원 데이터 삭제 (매칭 결과 포함)"""
        # 매칭 결과 및 리포트 삭제
        self.session.exec(delete(MatchingResult))
        self.session.exec(delete(MatchingReport))
        
        # 연수원 레코드 삭제
        record_count = self.session.exec(
            select(func.count()).select_from(TrainingCenterRecord)
        ).one()
        
        self.session.exec(delete(TrainingCenterRecord))
        self.session.exec(delete(TrainingCohort))
        self.session.commit()
        
        return record_count


