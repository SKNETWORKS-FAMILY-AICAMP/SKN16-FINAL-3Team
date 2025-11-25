"""
테스트 계정 생성 스크립트
AWS/로컬 테스트용 계정 생성
"""
from sqlmodel import Session, select
from app.database import engine
from app.models.user import User, UserRole
from app.models.mentor import ExamScore
from app.models.training_center import TrainingCenterRecord, TrainingCohort
from app.utils.auth import get_password_hash
import json
from datetime import date, datetime
from typing import Optional


def create_test_accounts(session: Session):
    """테스트 계정 생성"""
    print("🧪 테스트 계정 생성 중...")
    
    # 멘토 계정 (1번 사진 기준)
    mentors_data = [
        {
            "name": "강동기",
            "join_year": 2018,
            "employee_number": "201812001",
            "position": "선임",
            "team": "창구영업1팀",
            "birth": date(1992, 11, 11),
            "city": "서울특별시",
            "email": "201812001@bank.com",
            "phone": "010-2222-2222",
        },
        {
            "name": "안주영",
            "join_year": 2023,
            "employee_number": "202312001",
            "position": "사원",
            "team": "창구영업2팀",
            "birth": date(1997, 1, 27),
            "city": "고양시",
            "email": "202312001@bank.com",
            "phone": "010-3333-3333",
        },
        {
            "name": "양승호",
            "join_year": 2016,
            "employee_number": "201612001",
            "position": "책임",
            "team": "외환창구팀",
            "birth": date(1990, 2, 18),
            "city": "서울특별시",
            "email": "201612001@bank.com",
            "phone": "010-4444-4444",
        },
        {
            "name": "이현민",
            "join_year": 2018,
            "employee_number": "201812002",
            "position": "선임",
            "team": "디지털창구팀",
            "birth": date(1992, 3, 28),
            "city": "서울특별시",
            "email": "201812002@bank.com",
            "phone": "010-5555-5555",
        },
    ]
    
    # 멘티 계정 (2번 사진 기준, 2025년 12월 특채)
    mentees_data = [
        {
            "employee_number": "202512001",
            "team": "창구영업1팀",
            "birth": date(2003, 5, 23),
            "city": "서울특별시",
            "email": "202512001@bank.com",
            "phone": "010-2000-2000",
        },
        {
            "employee_number": "202512002",
            "team": "창구영업1팀",
            "birth": date(2001, 1, 7),
            "city": "부천시",
            "email": "202512002@bank.com",
            "phone": "010-3000-3000",
        },
        {
            "employee_number": "202512003",
            "team": "창구영업2팀",
            "birth": date(2001, 5, 12),
            "city": "서울특별시",
            "email": "202512003@bank.com",
            "phone": "010-4000-4000",
        },
        {
            "employee_number": "202512004",
            "team": "창구영업2팀",
            "birth": date(2001, 4, 23),
            "city": "서울특별시",
            "email": "202512004@bank.com",
            "phone": "010-5000-5000",
        },
        {
            "employee_number": "202512005",
            "team": "외환창구팀",
            "birth": date(1998, 6, 23),
            "city": "서울특별시",
            "email": "202512005@bank.com",
            "phone": "010-6000-6000",
        },
        {
            "employee_number": "202512006",
            "team": "외환창구팀",
            "birth": date(2004, 7, 11),
            "city": "서울특별시",
            "email": "202512006@bank.com",
            "phone": "010-7000-7000",
        },
        {
            "employee_number": "202512007",
            "team": "디지털창구팀",
            "birth": date(1999, 2, 18),
            "city": "성남시",
            "email": "202512007@bank.com",
            "phone": "010-8000-8000",
        },
        {
            "employee_number": "202512008",
            "team": "디지털창구팀",
            "birth": date(1998, 5, 25),
            "city": "성남시",
            "email": "202512008@bank.com",
            "phone": "010-9000-9000",
        },
    ]
    
    import random
    random_gen = random.Random(42)  # 시드 고정으로 일관성 유지
    
    # 랜덤 생성할 필드들
    MBTI_OPTIONS = ["INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP", 
                    "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP"]
    MAJOR_OPTIONS = ["경제학", "경영학", "회계학", "금융학", "통계학", "수학", "컴퓨터공학"]
    HOBBY_OPTIONS = ["스포츠", "영화감상", "독서", "요리", "러닝", "사진", "게임", "음악", "여행", "원예"]
    CAREER_GOAL_OPTIONS = ["VIP자산관리전문가", "기업금융전문가", "여신심사전문가", "디지털금융전문가"]
    
    created_users = []
    
    # 멘토 계정 생성
    for mentor_data in mentors_data:
        birth_str = mentor_data["birth"].strftime("%Y%m%d")
        password = get_password_hash(birth_str)
        
        # 기존 계정 확인
        existing = session.exec(
            select(User).where(User.email == mentor_data["email"])
        ).first()
        
        if existing:
            print(f"  ⚠️ 멘토 계정 이미 존재: {mentor_data['name']} ({mentor_data['email']})")
            continue
        
        user = User(
            email=mentor_data["email"],
            hashed_password=password,
            name=mentor_data["name"],
            role=UserRole.MENTOR,
            employee_number=mentor_data["employee_number"],
            join_year=mentor_data["join_year"],
            position=mentor_data["position"],
            team=mentor_data["team"],
            phone=mentor_data["phone"],
            mbti=random_gen.choice(MBTI_OPTIONS),
            hobbies=random_gen.choice(HOBBY_OPTIONS),
        )
        session.add(user)
        created_users.append({
            "role": "멘토",
            "name": mentor_data["name"],
            "email": mentor_data["email"],
            "password": birth_str,
        })
        print(f"  ✅ 멘토 계정 생성: {mentor_data['name']} ({mentor_data['email']})")
    
    # 멘티 계정 생성 (12월 특채 기수)
    cohort_date = date(2025, 12, 1)
    cohort = session.exec(
        select(TrainingCohort).where(TrainingCohort.cohort_date == cohort_date)
    ).first()
    
    if not cohort:
        cohort = TrainingCohort(
            label="2025년 12월 특채 기수",
            cohort_date=cohort_date,
            cohort_index=12,
        )
        session.add(cohort)
        session.flush()
    
    for idx, mentee_data in enumerate(mentees_data):
        birth_str = mentee_data["birth"].strftime("%Y%m%d")
        password = get_password_hash(birth_str)
        
        # 기존 계정 확인
        existing = session.exec(
            select(User).where(User.email == mentee_data["email"])
        ).first()
        
        if existing:
            print(f"  ⚠️ 멘티 계정 이미 존재: {mentee_data['email']}")
            continue
        
        # 이름 생성 (랜덤)
        last_names = ["김", "이", "박", "정", "최", "조", "윤", "장"]
        first_names = ["민준", "서준", "도윤", "하준", "지호", "유준", "준서", "건우"]
        name = random_gen.choice(last_names) + random_gen.choice(first_names)
        
        user = User(
            email=mentee_data["email"],
            hashed_password=password,
            name=name,
            role=UserRole.MENTEE,
            employee_number=mentee_data["employee_number"],
            join_year=2025,
            position="사원",
            team=mentee_data["team"],
            phone=mentee_data["phone"],
            mbti=random_gen.choice(MBTI_OPTIONS),
            hobbies=random_gen.choice(HOBBY_OPTIONS),
        )
        session.add(user)
        session.flush()
        
        # 연수원 시험 점수 생성
        section_scores = {
            "금융영업": random_gen.randint(7, 10),
            "금융상품개발": random_gen.randint(6, 10),
            "신용분석": random_gen.randint(6, 10),
            "자산운용": random_gen.randint(6, 10),
            "금융영업지원": random_gen.randint(7, 10),
            "증권외환": random_gen.randint(6, 10),
        }
        total_score = sum(section_scores.values())
        
        exam_score = ExamScore(
            mentee_id=user.id,
            exam_name="연수원 시험",
            exam_date=datetime.utcnow(),
            score_data=json.dumps(section_scores, ensure_ascii=False),
            total_score=float(total_score),
            grade="A" if total_score >= 50 else "B" if total_score >= 40 else "C",
        )
        session.add(exam_score)
        
        # TrainingCenterRecord도 생성
        training_record = TrainingCenterRecord(
            cohort_id=cohort.id,
            cohort_slot=idx + 1,
            cohort_date=cohort_date,
            cohort_label=cohort.label,
            employee_type="mentee",
            name=name,
            employee_number=mentee_data["employee_number"],
            gender=random_gen.choice(["남성", "여성"]),
            join_year=2025,
            mbti=user.mbti,
            position="사원",
            department="영업지원본부",
            team=mentee_data["team"],
            city=mentee_data["city"],
            hobby1=user.hobbies,
            hobby2=random_gen.choice(HOBBY_OPTIONS),
            major=random_gen.choice(MAJOR_OPTIONS),
            career_goal=random_gen.choice(CAREER_GOAL_OPTIONS),
            birth=mentee_data["birth"],
            email=mentee_data["email"],
            phone=mentee_data["phone"],
            address=f"{mentee_data['city']} 중앙로",
            section_scores=section_scores,
            question_scores={k: [1] * v for k, v in section_scores.items()},
            total_score=total_score,
        )
        session.add(training_record)
        
        created_users.append({
            "role": "멘티",
            "name": name,
            "email": mentee_data["email"],
            "password": birth_str,
        })
        print(f"  ✅ 멘티 계정 생성: {name} ({mentee_data['email']})")
    
    session.commit()
    
    # 계정 정보 출력
    print("\n📋 생성된 테스트 계정 목록:")
    print("=" * 80)
    for acc in created_users:
        print(f"  {acc['role']:4s} | {acc['name']:10s} | {acc['email']:25s} | PW: {acc['password']}")
    print("=" * 80)
    
    return created_users


if __name__ == "__main__":
    with Session(engine) as session:
        create_test_accounts(session)

