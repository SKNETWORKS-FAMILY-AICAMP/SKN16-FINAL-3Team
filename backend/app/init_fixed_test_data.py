"""
테스트 기수(2025년 5기) 고정 데이터 생성 스크립트
- 멘토 4명, 멘티 8명
- 연수원 시험 점수 및 TrainingCenterRecord 동기화
"""
from __future__ import annotations

from datetime import date, datetime
import json
from typing import Dict, List

from sqlmodel import Session, select

from app.database import engine
from app.models.mentor import ExamScore
from app.models.training_center import TrainingCenterRecord, TrainingCohort
from app.models.user import User, UserRole
from app.utils.auth import get_password_hash

SCORE_KEYS = ["은행업무", "상품지식", "고객응대", "법규준수", "IT활용", "영업실적"]
COHORT_INFO = {
    "label": "2025년 5기 (테스트 기수)",
    "cohort_date": date(2025, 12, 1),
    "cohort_index": 5,
}

FIXED_MENTORS: List[Dict] = [
    {
        "name": "강동기",
        "employee_number": "201812001",
        "team": "창구영업1팀",
        "position": "선임",
        "join_year": 2018,
        "birth": date(1992, 11, 11),
        "city": "서울특별시",
        "email": "201812001@bank.com",
        "phone": "010-2222-2222",
        "mbti": "ESTJ",
        "hobbies": "독서",
        "section_scores": {
            "은행업무": 92,
            "상품지식": 88,
            "고객응대": 90,
            "법규준수": 94,
            "IT활용": 86,
            "영업실적": 91,
        },
    },
    {
        "name": "안주영",
        "employee_number": "201903014",
        "team": "디지털창구팀",
        "position": "선임",
        "join_year": 2019,
        "birth": date(1993, 3, 9),
        "city": "부산광역시",
        "email": "201903014@bank.com",
        "phone": "010-3333-2222",
        "mbti": "INFJ",
        "hobbies": "요리",
        "section_scores": {
            "은행업무": 88,
            "상품지식": 90,
            "고객응대": 94,
            "법규준수": 92,
            "IT활용": 95,
            "영업실적": 89,
        },
    },
    {
        "name": "양도경",
        "employee_number": "202001007",
        "team": "외환창구팀",
        "position": "사원",
        "join_year": 2020,
        "birth": date(1994, 7, 4),
        "city": "대구광역시",
        "email": "202001007@bank.com",
        "phone": "010-4444-3333",
        "mbti": "ENTP",
        "hobbies": "러닝",
        "section_scores": {
            "은행업무": 86,
            "상품지식": 84,
            "고객응대": 87,
            "법규준수": 89,
            "IT활용": 90,
            "영업실적": 88,
        },
    },
    {
        "name": "김서연",
        "employee_number": "202101022",
        "team": "자산관리팀",
        "position": "사원",
        "join_year": 2021,
        "birth": date(1995, 2, 14),
        "city": "인천광역시",
        "email": "202101022@bank.com",
        "phone": "010-5555-5555",
        "mbti": "ISFJ",
        "hobbies": "원예",
        "section_scores": {
            "은행업무": 85,
            "상품지식": 87,
            "고객응대": 93,
            "법규준수": 90,
            "IT활용": 82,
            "영업실적": 88,
        },
    },
]

FIXED_MENTEES: List[Dict] = [
    {
        "name": "김민정",
        "employee_number": "202512001",
        "team": "창구영업1팀",
        "birth": date(2001, 5, 17),
        "city": "서울특별시",
        "email": "202512001@bank.com",
        "phone": "010-1000-1000",
        "mbti": "ENFP",
        "hobbies": "사진",
        "major": "경영학",
        "career_goal": "VIP자산관리전문가",
        "section_scores": {
            "은행업무": 78,
            "상품지식": 74,
            "고객응대": 85,
            "법규준수": 81,
            "IT활용": 76,
            "영업실적": 80,
        },
    },
    {
        "name": "문승현",
        "employee_number": "202512002",
        "team": "창구영업1팀",
        "birth": date(2001, 1, 7),
        "city": "부천시",
        "email": "202512002@bank.com",
        "phone": "010-3000-3000",
        "mbti": "ESTP",
        "hobbies": "스포츠",
        "major": "경제학",
        "career_goal": "기업금융전문가",
        "section_scores": {
            "은행업무": 75,
            "상품지식": 72,
            "고객응대": 78,
            "법규준수": 80,
            "IT활용": 70,
            "영업실적": 79,
        },
    },
    {
        "name": "박지호",
        "employee_number": "202512003",
        "team": "디지털창구팀",
        "birth": date(2000, 3, 21),
        "city": "대구광역시",
        "email": "202512003@bank.com",
        "phone": "010-1200-4500",
        "mbti": "ISTJ",
        "hobbies": "게임",
        "major": "컴퓨터공학",
        "career_goal": "디지털금융전문가",
        "section_scores": {
            "은행업무": 72,
            "상품지식": 75,
            "고객응대": 70,
            "법규준수": 76,
            "IT활용": 88,
            "영업실적": 74,
        },
    },
    {
        "name": "신희정",
        "employee_number": "202512004",
        "team": "디지털창구팀",
        "birth": date(2000, 8, 13),
        "city": "세종특별자치시",
        "email": "202512004@bank.com",
        "phone": "010-1400-5500",
        "mbti": "ENFJ",
        "hobbies": "음악",
        "major": "산업공학",
        "career_goal": "디지털금융전문가",
        "section_scores": {
            "은행업무": 76,
            "상품지식": 80,
            "고객응대": 82,
            "법규준수": 78,
            "IT활용": 84,
            "영업실적": 77,
        },
    },
    {
        "name": "허원준",
        "employee_number": "202512005",
        "team": "외환창구팀",
        "birth": date(2001, 9, 12),
        "city": "부산광역시",
        "email": "202512005@bank.com",
        "phone": "010-1500-6600",
        "mbti": "INTP",
        "hobbies": "독서",
        "major": "국제통상",
        "career_goal": "외환딜러",
        "section_scores": {
            "은행업무": 70,
            "상품지식": 73,
            "고객응대": 69,
            "법규준수": 75,
            "IT활용": 71,
            "영업실적": 72,
        },
    },
    {
        "name": "이준서",
        "employee_number": "202512006",
        "team": "외환창구팀",
        "birth": date(1999, 12, 28),
        "city": "울산광역시",
        "email": "202512006@bank.com",
        "phone": "010-1600-7700",
        "mbti": "ISFP",
        "hobbies": "여행",
        "major": "경영학",
        "career_goal": "외환딜러",
        "section_scores": {
            "은행업무": 74,
            "상품지식": 76,
            "고객응대": 80,
            "법규준수": 77,
            "IT활용": 73,
            "영업실적": 75,
        },
    },
    {
        "name": "최신입",
        "employee_number": "202512007",
        "team": "기업금융팀",
        "birth": date(2001, 6, 2),
        "city": "대전광역시",
        "email": "202512007@bank.com",
        "phone": "010-1700-8800",
        "mbti": "INTJ",
        "hobbies": "러닝",
        "major": "경제학",
        "career_goal": "기업금융전문가",
        "section_scores": {
            "은행업무": 79,
            "상품지식": 77,
            "고객응대": 73,
            "법규준수": 82,
            "IT활용": 75,
            "영업실적": 78,
        },
    },
    {
        "name": "박신입",
        "employee_number": "202512008",
        "team": "기업금융팀",
        "birth": date(2001, 10, 18),
        "city": "광주광역시",
        "email": "202512008@bank.com",
        "phone": "010-1800-9900",
        "mbti": "ESFP",
        "hobbies": "영화감상",
        "major": "회계학",
        "career_goal": "기업금융전문가",
        "section_scores": {
            "은행업무": 81,
            "상품지식": 79,
            "고객응대": 84,
            "법규준수": 80,
            "IT활용": 77,
            "영업실적": 83,
        },
    },
]


def create_fixed_test_data(session: Session):
    """12월 테스트 기수 고정 데이터 생성"""
    print("🔧 2025년 5기(테스트) 데이터 생성 중...")

    cohort = _ensure_test_cohort(session)
    _reset_test_cohort(session, cohort)

    mentor_users = [
        _create_or_update_user(session, mentor, UserRole.MENTOR)
        for mentor in FIXED_MENTORS
    ]
    for idx, mentor in enumerate(mentor_users, start=1):
        _create_training_record(
            session,
            cohort,
            idx,
            mentor,
            FIXED_MENTORS[idx - 1],
            employee_type="mentor",
        )

    mentee_users = [
        _create_or_update_user(session, mentee, UserRole.MENTEE)
        for mentee in FIXED_MENTEES
    ]
    for idx, mentee in enumerate(mentee_users, start=1):
        record = _create_training_record(
            session,
            cohort,
            idx,
            mentee,
            FIXED_MENTEES[idx - 1],
            employee_type="mentee",
        )
        _create_initial_exam_score(
            session, mentee.id, record.section_scores, cohort.cohort_date
        )

    session.commit()
    print("✅ 테스트 기수 계정 생성 및 연수원 데이터 동기화 완료")


def _ensure_test_cohort(session: Session) -> TrainingCohort:
    cohort = session.exec(
        select(TrainingCohort).where(
            TrainingCohort.cohort_date == COHORT_INFO["cohort_date"]
        )
    ).first()

    if cohort:
        return cohort

    cohort = TrainingCohort(
        label=COHORT_INFO["label"],
        cohort_date=COHORT_INFO["cohort_date"],
        cohort_index=COHORT_INFO["cohort_index"],
    )
    session.add(cohort)
    session.flush()
    return cohort


def _reset_test_cohort(session: Session, cohort: TrainingCohort):
    session.exec(
        delete(TrainingCenterRecord).where(
            TrainingCenterRecord.cohort_id == cohort.id
        )
    )
    session.commit()


def _create_or_update_user(session: Session, data: Dict, role: UserRole) -> User:
    existing = session.exec(
        select(User).where(User.email == data["email"])
    ).first()

    if existing:
        for key, value in data.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        return existing

    password = get_password_hash(data["birth"].strftime("%Y%m%d"))
    user = User(
        email=data["email"],
        hashed_password=password,
        name=data["name"],
        role=role,
        employee_number=data["employee_number"],
        join_year=data.get("join_year", 2025),
        position=data.get("position", "사원"),
        team=data["team"],
        phone=data["phone"],
        hobbies=data.get("hobbies"),
        mbti=data.get("mbti"),
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def _create_training_record(
    session: Session,
    cohort: TrainingCohort,
    slot: int,
    user: User,
    profile: Dict,
    employee_type: str,
) -> TrainingCenterRecord:
    section_scores = profile.get("section_scores") or {
        key: 0 for key in SCORE_KEYS
    }
    record = TrainingCenterRecord(
        cohort_id=cohort.id,
        cohort_slot=slot,
        cohort_date=cohort.cohort_date,
        cohort_label=cohort.label,
        employee_type=employee_type,
        name=user.name,
        employee_number=user.employee_number,
        gender=profile.get("gender"),
        join_year=user.join_year,
        mbti=user.mbti,
        position=user.position,
        department="영업지원본부",
        team=user.team,
        city=profile.get("city", "서울특별시"),
        hobby1=user.hobbies,
        hobby2=None,
        major=profile.get("major"),
        career_goal=profile.get("career_goal"),
        birth=profile.get("birth"),
        email=user.email,
        phone=user.phone,
        address=f"{profile.get('city', '서울특별시')} 중앙로",
        section_scores=section_scores,
        question_scores={
            key: [1 if score >= 80 else 0 for _ in range(10)]
            for key, score in section_scores.items()
        },
        total_score=round(
            sum(section_scores.values()) / len(section_scores), 1
        ),
    )
    session.add(record)
    return record


def _create_initial_exam_score(
    session: Session, mentee_id: int, section_scores: Dict[str, int], exam_date: date
):
    existing = session.exec(
        select(ExamScore).where(
            ExamScore.mentee_id == mentee_id,
            ExamScore.exam_name == "연수원 시험",
        )
    ).first()
    if existing:
        return

    total = round(sum(section_scores.values()) / len(section_scores), 1)
    grade = "A" if total >= 85 else "B" if total >= 75 else "C"

    exam = ExamScore(
        mentee_id=mentee_id,
        exam_name="연수원 시험",
        exam_date=datetime.combine(exam_date, datetime.min.time()),
        score_data=json.dumps(section_scores, ensure_ascii=False),
        total_score=total,
        grade=grade,
        feedback="초기 연수원 시험 결과입니다.",
    )
    session.add(exam)


if __name__ == "__main__":
    with Session(engine) as session:
        create_fixed_test_data(session)

