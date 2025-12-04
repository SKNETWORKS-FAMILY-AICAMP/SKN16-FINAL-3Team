"""
데모용 시드 데이터 생성 스크립트

2025년 1~3기 멘티/멘토 데이터를 생성하여 JSON 파일로 저장합니다.
- 멘티 30명 / 멘토 15명 per 기수
- 시뮬레이션 점수: 초반 30점 → 중간 55점 → 최종 75점 (발전 곡선)
- 사람마다 편차 존재, 극소수는 우상향 못함
"""

import json
import random
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path


# ============================================================================
# 설정 상수
# ============================================================================

SEED_OUTPUT_DIR = Path(__file__).parent.parent / "backend" / "data" / "seed"
MENTEES_PER_COHORT = 30
MENTORS_PER_COHORT = 15

# 기수별 날짜 (2025년 1~3기: 완수, 4기: 진행 중)
COHORT_DATES = {
    1: date(2025, 3, 1),   # 1기: 3월 입사
    2: date(2025, 6, 1),   # 2기: 6월 입사
    3: date(2025, 9, 1),   # 3기: 9월 입사
    4: date(2025, 12, 1),  # 4기: 12월 입사 (진행 중)
}

# 시뮬레이션 점수 발전 곡선 (100점 만점)
# - 대다수 (80%): 정상 우상향
# - 일부 (13%): 느린 성장
# - 극소수 (7%): 정체/하락
GROWTH_TYPES = {
    "normal": 0.80,    # 정상 우상향
    "slow": 0.13,      # 느린 성장
    "stagnant": 0.07,  # 정체/하락
}

# 성장 타입별 점수 범위
SCORE_RANGES = {
    "normal": {
        "initial": (25, 35),
        "mid": (50, 60),
        "final": (70, 82),
    },
    "slow": {
        "initial": (20, 30),
        "mid": (40, 50),
        "final": (55, 65),
    },
    "stagnant": {
        "initial": (25, 35),
        "mid": (30, 40),
        "final": (35, 45),
    },
}

# 6대 역량 카테고리
EXAM_CATEGORIES = [
    "은행업무",
    "상품개발 및 운용",
    "신용분석 및 리스크관리",
    "외환",
    "은행지식 및 관련법률",
    "하경은행",
]

# 시뮬레이션 6가지 평가 지표
SIMULATION_METRICS = [
    "knowledge_point",    # 지식
    "skill_point",        # 기술
    "empathy_point",      # 공감도
    "clarity_point",      # 명확성
    "kindness_point",     # 친절도
    "confidence_point",   # 자신감
]

# 퀴즈 모드
QUIZ_MODES = ["random", "custom", "midterm", "final"]

# 이름 생성용 데이터
LAST_NAMES = ["김", "이", "박", "정", "최", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송", "유", "홍", "양"]
MALE_FIRST_LEADING = ["민", "서", "도", "하", "지", "유", "준", "시", "태", "수", "건", "현", "연", "재", "가", "동", "성", "영", "호", "우"]
MALE_FIRST_TRAILING = ["현", "우", "윤", "진", "환", "혁", "훈", "열", "형", "람", "석", "준", "호", "성", "민", "재", "영", "수", "태", "원"]
FEMALE_FIRST_LEADING = ["민", "서", "하", "지", "아", "유", "예", "다", "채", "주", "현", "연", "수", "가", "은", "혜", "지", "서", "예", "나"]
FEMALE_FIRST_TRAILING = ["림", "은", "율", "빈", "영", "정", "미", "솔", "나", "람", "아", "연", "희", "진", "수", "영", "미", "은", "혜", "지"]

# 기타 속성 옵션
MBTI_OPTIONS = ["INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP", "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP"]
MBTI_WEIGHTS = [0.04, 0.04, 0.05, 0.04, 0.05, 0.05, 0.06, 0.06, 0.09, 0.13, 0.08, 0.10, 0.04, 0.05, 0.05, 0.05]

CITY_OPTIONS = ["서울특별시", "부산광역시", "인천광역시", "대구광역시", "대전광역시", "광주광역시", "울산광역시", "세종특별자치시", "고양시", "성남시", "용인시", "수원시", "청주시", "전주시", "창원시", "천안시"]
CITY_WEIGHTS = [0.25, 0.10, 0.08, 0.05, 0.05, 0.05, 0.05, 0.03, 0.06, 0.06, 0.06, 0.05, 0.04, 0.03, 0.03, 0.03]

HOBBY_OPTIONS = ["스포츠", "영화감상", "독서", "요리", "러닝", "사진", "게임", "음악", "여행", "원예"]

MAJOR_OPTIONS = ["경제학", "경영학", "회계학", "금융학", "통계학", "수학", "컴퓨터공학", "산업공학", "법학", "행정학", "국제통상", "영어영문학", "중어중문학", "심리학", "사회학"]
MAJOR_WEIGHTS = [0.18, 0.20, 0.12, 0.10, 0.05, 0.04, 0.08, 0.04, 0.05, 0.04, 0.03, 0.03, 0.02, 0.02, 0.02]

CAREER_GOALS = ["VIP자산관리전문가", "기업금융전문가", "여신심사전문가", "디지털금융전문가", "외환딜러", "PB(프라이빗뱅커)", "지점장", "본부전문직", "리스크관리전문가", "금융상품개발자"]

BRANCH_TEAMS = ["창구영업1팀", "창구영업2팀", "VIP창구팀", "외환창구팀", "디지털창구팀", "기업창구팀"]
TEAM_WEIGHTS = [0.3, 0.3, 0.1, 0.1, 0.1, 0.1]

# 페르소나/시나리오 ID (실제 시스템의 값 참조)
PERSONA_IDS = ["persona_001", "persona_002", "persona_003", "persona_004", "persona_005"]
SCENARIO_IDS = ["scenario_001", "scenario_002", "scenario_003", "scenario_004", "scenario_005"]

# 페르소나 정보 옵션 (시뮬레이션 분석용)
PERSONA_AGE_GROUPS = ["20대", "30대", "40대", "50대", "60대 이상"]
PERSONA_GENDERS = ["남성", "여성"]
PERSONA_OCCUPATIONS = ["학생", "직장인", "자영업자", "은퇴자", "무직"]
PERSONA_CUSTOMER_STYLES = ["실용형", "보수형", "불만형", "긍정형", "급함형"]
SITUATION_CATEGORIES = ["수신", "여신", "카드", "외환", "인터넷뱅킹", "민원처리"]


# ============================================================================
# 유틸리티 함수
# ============================================================================

def generate_name(gender: str) -> str:
    """성별에 맞는 이름 생성"""
    last = random.choice(LAST_NAMES)
    if gender == "남성":
        first = random.choice(MALE_FIRST_LEADING) + random.choice(MALE_FIRST_TRAILING)
    else:
        first = random.choice(FEMALE_FIRST_LEADING) + random.choice(FEMALE_FIRST_TRAILING)
    return f"{last}{first}"


def generate_birth(join_year: int, gender: str) -> date:
    """입사년도와 성별에 맞는 생년월일 생성"""
    if gender == "남성":
        birth_year = random.randint(join_year - 27, join_year - 25)
    else:
        birth_year = random.randint(join_year - 25, join_year - 23)
    return date(birth_year, random.randint(1, 12), random.randint(1, 28))


def generate_phone() -> str:
    """전화번호 생성"""
    mid = random.randint(2000, 9999)
    last = random.randint(1000, 9999)
    return f"010-{mid:04d}-{last:04d}"


def weighted_choice(options: List[str], weights: List[float]) -> str:
    """가중치 기반 랜덤 선택"""
    return random.choices(options, weights=weights, k=1)[0]


def get_growth_type() -> str:
    """성장 타입 결정"""
    rand = random.random()
    cumulative = 0.0
    for growth_type, weight in GROWTH_TYPES.items():
        cumulative += weight
        if rand < cumulative:
            return growth_type
    return "normal"


def generate_score_progression(growth_type: str) -> Tuple[int, int, int]:
    """성장 타입에 따른 점수 진행 생성 (초기, 중간, 최종)"""
    ranges = SCORE_RANGES[growth_type]
    initial = random.randint(*ranges["initial"])
    mid = random.randint(*ranges["mid"])
    final = random.randint(*ranges["final"])
    
    # 중간/최종은 이전보다 낮으면 안됨 (stagnant 제외)
    if growth_type != "stagnant":
        mid = max(mid, initial + random.randint(5, 15))
        final = max(final, mid + random.randint(5, 15))
    
    return min(initial, 100), min(mid, 100), min(final, 100)


def distribute_score_to_categories(total_score: int, num_categories: int = 6) -> Dict[str, int]:
    """총점을 카테고리별로 분배"""
    max_per_category = 10  # 각 카테고리당 최대 10점 (총 60점 만점)
    target_per_category = total_score * max_per_category // 100  # 100점 만점 → 60점 만점으로 변환
    
    scores = {}
    remaining = (total_score * 60) // 100  # 60점 만점으로 변환
    
    for i, category in enumerate(EXAM_CATEGORIES):
        if i == len(EXAM_CATEGORIES) - 1:
            scores[category] = min(max_per_category, remaining)
        else:
            variation = random.randint(-2, 2)
            score = max(0, min(max_per_category, target_per_category // num_categories + variation))
            scores[category] = score
            remaining -= score
    
    # 총점 보정
    current_total = sum(scores.values())
    target_total = (total_score * 60) // 100
    
    if current_total != target_total:
        diff = target_total - current_total
        adjustable = [c for c in EXAM_CATEGORIES if 0 < scores[c] < max_per_category]
        if adjustable:
            category = random.choice(adjustable)
            scores[category] = max(0, min(max_per_category, scores[category] + diff))
    
    return scores


def generate_simulation_metrics(total_score: int) -> Dict[str, int]:
    """시뮬레이션 6가지 지표 점수 생성"""
    metrics = {}
    base_score = total_score
    
    for metric in SIMULATION_METRICS:
        variation = random.randint(-10, 10)
        score = max(0, min(100, base_score + variation))
        metrics[metric] = score
    
    return metrics


def generate_datetime_in_range(start_date: date, end_date: date) -> datetime:
    """주어진 범위 내에서 랜덤 datetime 생성"""
    delta = (end_date - start_date).days
    random_days = random.randint(0, max(0, delta))
    random_date = start_date + timedelta(days=random_days)
    random_time = timedelta(hours=random.randint(9, 18), minutes=random.randint(0, 59))
    return datetime.combine(random_date, datetime.min.time()) + random_time


# ============================================================================
# 데이터 생성 함수
# ============================================================================

def generate_user(
    user_id: int,
    employee_number: str,
    name: str,
    role: str,
    gender: str,
    birth: date,
    join_year: int,
    team: str,
    mbti: str,
    hobbies: List[str],
) -> Dict[str, Any]:
    """User 데이터 생성"""
    return {
        "id": user_id,
        "email": f"{employee_number}@bank.com",
        "hashed_password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VttYyOd4JxIxE2",  # birth date hash placeholder
        "name": name,
        "role": role,  # "mentee" or "mentor"
        "employee_number": employee_number,
        "join_year": join_year,
        "position": "사원" if role == "mentee" else random.choice(["선임", "사원", "책임"]),
        "team": team,
        "phone": generate_phone(),
        "mbti": mbti,
        "hobbies": hobbies[0] if hobbies else "",
        "interests": json.dumps(hobbies, ensure_ascii=False) if hobbies else None,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    }


def generate_training_record(
    record_id: int,
    cohort_id: int,
    cohort_date: date,
    cohort_label: str,
    employee_type: str,
    name: str,
    employee_number: str,
    gender: str,
    join_year: int,
    team: str,
    mbti: str,
    city: str,
    hobby1: str,
    hobby2: str,
    major: str,
    career_goal: str,
    birth: date,
) -> Dict[str, Any]:
    """TrainingCenterRecord 데이터 생성"""
    return {
        "id": record_id,
        "cohort_id": cohort_id,
        "cohort_slot": record_id % 100,
        "cohort_date": cohort_date.isoformat(),
        "cohort_label": cohort_label,
        "employee_type": employee_type,
        "name": name,
        "employee_number": employee_number,
        "gender": gender,
        "join_year": join_year,
        "mbti": mbti,
        "position": "사원" if employee_type == "mentee" else random.choice(["선임", "사원", "책임"]),
        "department": "영업지원본부",
        "team": team,
        "city": city,
        "hobby1": hobby1,
        "hobby2": hobby2,
        "major": major,
        "career_goal": career_goal,
        "birth": birth.isoformat(),
        "phone": generate_phone(),
        "address": f"{city} 중앙로 {random.randint(1, 100)}",
        "email": f"{employee_number}@bank.com",
        "section_scores": {},
        "question_scores": {},
        "total_score": 0.0,
        "created_at": datetime.now().isoformat(),
    }


def generate_exam_score(
    exam_id: int,
    mentee_id: int,
    exam_type: str,
    exam_date: datetime,
    score_data: Dict[str, int],
) -> Dict[str, Any]:
    """ExamScore 데이터 생성"""
    total = sum(score_data.values())
    
    # 등급 계산 (60점 만점)
    if total >= 54:
        grade = "A"
    elif total >= 48:
        grade = "B"
    elif total >= 42:
        grade = "C"
    elif total >= 36:
        grade = "D"
    else:
        grade = "F"
    
    exam_names = {
        "beginning": "초기 평가",
        "midterm": "중간 평가",
        "final": "최종 평가",
    }
    
    return {
        "id": exam_id,
        "mentee_id": mentee_id,
        "exam_name": exam_names.get(exam_type, "연수원 평가"),
        "exam_type": exam_type,
        "exam_date": exam_date.isoformat(),
        "score_data": json.dumps(score_data, ensure_ascii=False),
        "total_score": float(total),
        "grade": grade,
        "feedback": f"{exam_names.get(exam_type, '평가')} 결과가 기록되었습니다.",
        "created_at": exam_date.isoformat(),
    }


def generate_quiz_log(
    log_id: int,
    user_id: int,
    mode: str,
    created_at: datetime,
    score: float,
) -> Dict[str, Any]:
    """QuizGenerationLog 데이터 생성"""
    total_questions = 10 if mode in ["random", "custom"] else 20
    
    return {
        "id": log_id,
        "user_id": user_id,
        "mode": mode,
        "total_questions": total_questions,
        "questions": [],  # 실제 문제는 생략
        "extra": {"category": random.choice(EXAM_CATEGORIES)},
        "answers": {},
        "score": score,
        "submitted_at": created_at.isoformat(),
        "created_at": created_at.isoformat(),
    }


def generate_simulation_session(
    session_id: int,
    user_id: int,
    started_at: datetime,
    is_completed: bool = True,
    total_turns: int = 10,
) -> Dict[str, Any]:
    """RAGSimulationSession 데이터 생성"""
    duration = random.randint(180, 600) if is_completed else None
    
    return {
        "id": session_id,
        "session_key": f"session_{user_id}_{int(started_at.timestamp())}",
        "user_id": user_id,
        "persona_id": random.choice(PERSONA_IDS),
        "scenario_id": random.choice(SCENARIO_IDS),
        "persona_name": f"고객_{random.randint(1, 100)}",
        "scenario_title": f"시나리오_{random.randint(1, 50)}",
        "persona_info": None,
        "situation_info": None,
        "goal_achievement_data": None,
        "achieved_goals": None,
        "started_at": started_at.isoformat(),
        "ended_at": (started_at + timedelta(seconds=duration)).isoformat() if is_completed else None,
        "is_completed": is_completed,
        "total_turns": total_turns,
        "duration_seconds": duration,
    }


def generate_simulation_evaluation(
    eval_id: int,
    session_id: int,
    user_id: int,
    metrics: Dict[str, int],
    created_at: datetime,
) -> Dict[str, Any]:
    """RAGSimulationEvaluation 데이터 생성"""
    # 가중 평균 총점 계산
    weights = {
        "knowledge_point": 0.20,
        "skill_point": 0.20,
        "empathy_point": 0.15,
        "clarity_point": 0.15,
        "kindness_point": 0.15,
        "confidence_point": 0.15,
    }
    
    total = sum(metrics[k] * weights[k] for k in weights)
    total = int(round(total))
    
    # 등급 계산
    if total >= 90:
        grade = "A+"
    elif total >= 85:
        grade = "A"
    elif total >= 80:
        grade = "B+"
    elif total >= 75:
        grade = "B"
    elif total >= 70:
        grade = "C+"
    elif total >= 65:
        grade = "C"
    else:
        grade = "D"
    
    return {
        "id": eval_id,
        "session_id": session_id,
        "user_id": user_id,
        **metrics,
        "total_point": total,
        "grade": grade,
        "knowledge_reason": "상품 정보를 정확하게 설명했습니다.",
        "skill_reason": "업무 절차를 잘 따랐습니다.",
        "empathy_reason": "고객의 입장을 잘 이해했습니다.",
        "clarity_reason": "명확하게 설명했습니다.",
        "kindness_reason": "친절하게 응대했습니다.",
        "confidence_reason": "자신감 있게 대응했습니다.",
        "feedback_summary": f"전반적으로 {'우수한' if total >= 75 else '양호한' if total >= 55 else '개선이 필요한'} 응대였습니다.",
        "detail_json": None,
        "created_at": created_at.isoformat(),
    }


def generate_simulation_feedback(
    feedback_id: int,
    user_id: int,
    session_key: str,
    total_score: int,
    created_at: datetime,
) -> Dict[str, Any]:
    """SimulationFeedback 데이터 생성 (시뮬레이션 분석용)"""
    # 점수 생성
    knowledge = max(0, min(100, total_score + random.randint(-10, 10)))
    skill = max(0, min(100, total_score + random.randint(-10, 10)))
    kindness = max(0, min(100, total_score + random.randint(-10, 10)))
    clarity = max(0, min(100, total_score + random.randint(-10, 10)))
    confidence = max(0, min(100, total_score + random.randint(-10, 10)))
    persona_fit = max(0, min(100, total_score + random.randint(-10, 10)))
    
    # 종합 점수 (가중 평균)
    overall = (knowledge * 0.2 + skill * 0.2 + kindness * 0.15 + 
               ((clarity + confidence) / 2) * 0.15 + persona_fit * 0.3)
    overall = round(overall, 1)
    
    # 등급 계산
    if overall >= 90:
        grade = "A+"
    elif overall >= 85:
        grade = "A"
    elif overall >= 80:
        grade = "B+"
    elif overall >= 75:
        grade = "B"
    elif overall >= 70:
        grade = "C+"
    elif overall >= 65:
        grade = "C"
    else:
        grade = "D"
    
    # 성과 수준
    if overall >= 80:
        performance_level = "우수한 성과"
    elif overall >= 60:
        performance_level = "양호한 성과"
    else:
        performance_level = "개선 필요"
    
    # 페르소나 정보
    age_group = random.choice(PERSONA_AGE_GROUPS)
    gender = random.choice(PERSONA_GENDERS)
    occupation = random.choice(PERSONA_OCCUPATIONS)
    customer_style = random.choice(PERSONA_CUSTOMER_STYLES)
    situation = random.choice(SITUATION_CATEGORIES)
    
    return {
        "id": feedback_id,
        "user_id": user_id,
        "session_key": session_key,
        "persona_id": random.choice(PERSONA_IDS),
        "situation_id": random.choice(SCENARIO_IDS),
        "persona_info": f"{age_group} {gender} {occupation}",
        "persona_age_group": age_group,
        "persona_gender": gender,
        "persona_occupation": occupation,
        "persona_customer_style": customer_style,
        "situation_info": situation,
        "overall_score": overall,
        "grade": grade,
        "performance_level": performance_level,
        "knowledge_score": knowledge,
        "skill_score": skill,
        "empathy_score": 0,  # 레거시 호환
        "clarity_score": clarity,
        "kindness_score": kindness,
        "confidence_score": confidence,
        "persona_fit_score": persona_fit,
        "knowledge_feedback": "상품 지식이 전반적으로 양호합니다.",
        "skill_feedback": "업무 처리 스킬이 적절합니다.",
        "empathy_feedback": None,
        "clarity_feedback": "설명이 명확합니다.",
        "kindness_feedback": "친절한 응대가 좋습니다.",
        "confidence_feedback": "자신감 있게 응대했습니다.",
        "persona_fit_feedback": "페르소나에 맞는 응대를 했습니다.",
        "summary": f"전반적으로 {performance_level}를 보였습니다.",
        "improvements": "꾸준한 연습을 통해 더 발전할 수 있습니다.",
        "total_turns": random.randint(6, 15),
        "duration_seconds": random.randint(180, 600),
        "conversation_log": None,
        "goal_achievement_data": None,
        "is_test_mode": False,
        "rag_evaluations": None,
        "rag_summary": None,
        "created_at": created_at.isoformat(),
    }


def generate_matching_result(
    result_id: int,
    mentee_id: int,
    mentor_id: int,
    matched_at: datetime,
) -> Dict[str, Any]:
    """MatchingResult 데이터 생성"""
    team_score = random.uniform(0.7, 1.0)
    city_score = random.uniform(0.5, 1.0)
    hobby_score = random.uniform(0.3, 1.0)
    weakness_strength_score = random.uniform(0.5, 1.0)
    career_score = random.uniform(0.4, 1.0)
    major_score = random.uniform(0.3, 1.0)
    
    total_score = (
        team_score * 2.5 +
        weakness_strength_score * 2.0 +
        career_score * 1.2 +
        city_score * 1.0 +
        hobby_score * 0.8 +
        major_score * 0.5
    ) / 8.0
    
    return {
        "id": result_id,
        "mentee_id": mentee_id,
        "mentor_id": mentor_id,
        "total_score": round(total_score, 4),
        "team_score": round(team_score, 4),
        "city_score": round(city_score, 4),
        "hobby_score": round(hobby_score, 4),
        "weakness_strength_score": round(weakness_strength_score, 4),
        "career_score": round(career_score, 4),
        "major_score": round(major_score, 4),
        "matching_details": {},
        "is_active": True,
        "matched_at": matched_at.isoformat(),
    }


def generate_mentor_mentee_relation(
    relation_id: int,
    mentor_user_id: int,
    mentee_user_id: int,
    matched_at: datetime,
) -> Dict[str, Any]:
    """MentorMenteeRelation 데이터 생성"""
    return {
        "id": relation_id,
        "mentor_id": mentor_user_id,
        "mentee_id": mentee_user_id,
        "matched_at": matched_at.isoformat(),
        "is_active": True,
        "notes": "매칭 시스템 자동 생성",
    }


def generate_feedback(
    feedback_id: int,
    mentor_id: int,
    mentee_id: int,
    created_at: datetime,
) -> Dict[str, Any]:
    """Feedback 데이터 생성"""
    feedback_texts = [
        "이번 주 시뮬레이션에서 많이 발전했습니다. 특히 고객 응대 스킬이 좋아졌어요.",
        "상품 지식이 부족한 부분이 있으니 추가 학습이 필요합니다.",
        "전반적으로 잘하고 있습니다. 자신감을 가지세요!",
        "고객의 질문에 더 명확하게 답변할 수 있도록 연습해보세요.",
        "친절한 태도가 인상적입니다. 계속 유지해주세요.",
    ]
    
    return {
        "id": feedback_id,
        "mentor_id": mentor_id,
        "mentee_id": mentee_id,
        "feedback_text": random.choice(feedback_texts),
        "feedback_type": random.choice(["general", "performance", "improvement"]),
        "color_section": random.choice(["red", "orange", "yellow", "gray"]),
        "is_read": random.choice([True, False]),
        "created_at": created_at.isoformat(),
        "read_at": created_at.isoformat() if random.choice([True, False]) else None,
    }


# ============================================================================
# 기수별 데이터 생성
# ============================================================================

def generate_cohort_data(cohort_num: int, id_offset: int = 0) -> Dict[str, Any]:
    """
    한 기수의 전체 데이터 생성
    
    Args:
        cohort_num: 기수 번호 (1, 2, 3)
        id_offset: ID 시작 오프셋
    """
    cohort_date = COHORT_DATES[cohort_num]
    cohort_label = f"2025년 {cohort_num}기"
    
    # 기수별 기간 설정 (3개월)
    cohort_start = cohort_date
    cohort_end = cohort_date + timedelta(days=90)
    
    # ID 카운터
    user_id_counter = id_offset * 1000 + 1
    record_id_counter = id_offset * 1000 + 1
    exam_id_counter = id_offset * 10000 + 1
    quiz_id_counter = id_offset * 10000 + 1
    session_id_counter = id_offset * 10000 + 1
    eval_id_counter = id_offset * 10000 + 1
    matching_id_counter = id_offset * 1000 + 1
    relation_id_counter = id_offset * 1000 + 1
    feedback_id_counter = id_offset * 1000 + 1
    
    # 데이터 컨테이너
    data = {
        "cohort_info": {
            "cohort_num": cohort_num,
            "cohort_date": cohort_date.isoformat(),
            "cohort_label": cohort_label,
        },
        "training_cohorts": [],
        "users": [],
        "training_records": [],
        "exam_scores": [],
        "quiz_logs": [],
        "simulation_sessions": [],
        "simulation_evaluations": [],
        "simulation_feedbacks": [],  # 시뮬레이션 분석용
        "matching_results": [],
        "mentor_mentee_relations": [],
        "feedbacks": [],
    }
    
    # SimulationFeedback ID 카운터
    sim_feedback_id_counter = id_offset * 10000 + 1
    
    # 기수 정보
    data["training_cohorts"].append({
        "id": cohort_num,
        "cohort_date": cohort_date.isoformat(),
        "cohort_index": cohort_num,
        "label": cohort_label,
    })
    
    # 멘토 풀 생성
    mentors = []
    for i in range(MENTORS_PER_COHORT):
        gender = random.choice(["남성", "여성"])
        name = generate_name(gender)
        current_year = 2025
        join_year = random.randint(current_year - 10, current_year - 4)
        birth = generate_birth(join_year, gender)
        employee_number = f"{join_year}01{(i+1):03d}"
        team = weighted_choice(BRANCH_TEAMS, TEAM_WEIGHTS)
        mbti = weighted_choice(MBTI_OPTIONS, MBTI_WEIGHTS)
        city = weighted_choice(CITY_OPTIONS, CITY_WEIGHTS)
        hobbies = random.sample(HOBBY_OPTIONS, 2)
        major = weighted_choice(MAJOR_OPTIONS, MAJOR_WEIGHTS)
        career_goal = random.choice(CAREER_GOALS)
        
        user_id = user_id_counter
        user_id_counter += 1
        
        # User 생성
        user = generate_user(
            user_id=user_id,
            employee_number=employee_number,
            name=name,
            role="mentor",
            gender=gender,
            birth=birth,
            join_year=join_year,
            team=team,
            mbti=mbti,
            hobbies=hobbies,
        )
        data["users"].append(user)
        
        # TrainingCenterRecord 생성
        record = generate_training_record(
            record_id=record_id_counter,
            cohort_id=cohort_num,
            cohort_date=date(join_year, 1, 1),
            cohort_label=f"{join_year}년 입사",
            employee_type="mentor",
            name=name,
            employee_number=employee_number,
            gender=gender,
            join_year=join_year,
            team=team,
            mbti=mbti,
            city=city,
            hobby1=hobbies[0],
            hobby2=hobbies[1],
            major=major,
            career_goal=career_goal,
            birth=birth,
        )
        record_id_counter += 1
        data["training_records"].append(record)
        
        mentors.append({
            "user_id": user_id,
            "record_id": record["id"],
            "name": name,
            "team": team,
        })
    
    # 멘티 데이터 먼저 생성 (사번 없이)
    mentee_data_list = []
    for i in range(MENTEES_PER_COHORT):
        gender = random.choice(["남성", "여성"])
        name = generate_name(gender)
        join_year = cohort_date.year
        birth = generate_birth(join_year, gender)
        team = weighted_choice(BRANCH_TEAMS, TEAM_WEIGHTS)
        mbti = weighted_choice(MBTI_OPTIONS, MBTI_WEIGHTS)
        city = weighted_choice(CITY_OPTIONS, CITY_WEIGHTS)
        hobbies = random.sample(HOBBY_OPTIONS, 2)
        major = weighted_choice(MAJOR_OPTIONS, MAJOR_WEIGHTS)
        career_goal = random.choice(CAREER_GOALS)
        
        # 성장 타입 결정
        growth_type = get_growth_type()
        initial_score, mid_score, final_score = generate_score_progression(growth_type)
        
        mentee_data_list.append({
            "name": name,
            "gender": gender,
            "join_year": join_year,
            "birth": birth,
            "team": team,
            "mbti": mbti,
            "city": city,
            "hobbies": hobbies,
            "major": major,
            "career_goal": career_goal,
            "growth_type": growth_type,
            "scores": (initial_score, mid_score, final_score),
        })
    
    # 멘티를 이름 가나다 순으로 정렬
    mentee_data_list.sort(key=lambda x: x["name"])
    
    # 멘티 생성 및 사번 부여 (가나다 순으로 001부터)
    mentees = []
    for i, mentee_data in enumerate(mentee_data_list):
        # 사번: 20250{기수번호}{순번}
        employee_number = f"20250{cohort_num}{(i+1):03d}"
        
        user_id = user_id_counter
        user_id_counter += 1
        
        # User 생성
        user = generate_user(
            user_id=user_id,
            employee_number=employee_number,
            name=mentee_data["name"],
            role="mentee",
            gender=mentee_data["gender"],
            birth=mentee_data["birth"],
            join_year=mentee_data["join_year"],
            team=mentee_data["team"],
            mbti=mentee_data["mbti"],
            hobbies=mentee_data["hobbies"],
        )
        data["users"].append(user)
        
        # TrainingCenterRecord 생성
        record = generate_training_record(
            record_id=record_id_counter,
            cohort_id=cohort_num,
            cohort_date=cohort_date,
            cohort_label=cohort_label,
            employee_type="mentee",
            name=mentee_data["name"],
            employee_number=employee_number,
            gender=mentee_data["gender"],
            join_year=mentee_data["join_year"],
            team=mentee_data["team"],
            mbti=mentee_data["mbti"],
            city=mentee_data["city"],
            hobby1=mentee_data["hobbies"][0],
            hobby2=mentee_data["hobbies"][1],
            major=mentee_data["major"],
            career_goal=mentee_data["career_goal"],
            birth=mentee_data["birth"],
        )
        record_id_counter += 1
        data["training_records"].append(record)
        
        mentees.append({
            "user_id": user_id,
            "record_id": record["id"],
            "name": mentee_data["name"],
            "team": mentee_data["team"],
            "growth_type": mentee_data["growth_type"],
            "scores": mentee_data["scores"],
        })
        
        # ================================================================
        # 멘티별 학습 이력 생성
        # ================================================================
        
        # 1. ExamScore (초기/중간/최종)
        exam_types = ["beginning", "midterm", "final"]
        exam_scores_list = [initial_score, mid_score, final_score]
        exam_dates = [
            cohort_start + timedelta(days=7),
            cohort_start + timedelta(days=45),
            cohort_start + timedelta(days=85),
        ]
        
        for exam_type, score_100, exam_date in zip(exam_types, exam_scores_list, exam_dates):
            score_data = distribute_score_to_categories(score_100)
            exam = generate_exam_score(
                exam_id=exam_id_counter,
                mentee_id=user_id,
                exam_type=exam_type,
                exam_date=datetime.combine(exam_date, datetime.min.time()) + timedelta(hours=10),
                score_data=score_data,
            )
            exam_id_counter += 1
            data["exam_scores"].append(exam)
        
        # 2. QuizGenerationLog (여러 번의 퀴즈)
        # 기수 완료까지 평균 15~25회 퀴즈 진행
        num_quizzes = random.randint(15, 25)
        for q in range(num_quizzes):
            quiz_date = generate_datetime_in_range(cohort_start, cohort_end)
            mode = random.choice(QUIZ_MODES)
            
            # 점수는 시간에 따라 상승 (성장 타입 반영)
            progress = (quiz_date - datetime.combine(cohort_start, datetime.min.time())).days / 90
            if growth_type == "normal":
                base_score = 50 + progress * 40
            elif growth_type == "slow":
                base_score = 40 + progress * 30
            else:
                base_score = 45 + progress * 10
            
            score = max(0, min(100, base_score + random.randint(-15, 15)))
            
            quiz = generate_quiz_log(
                log_id=quiz_id_counter,
                user_id=user_id,
                mode=mode,
                created_at=quiz_date,
                score=score,
            )
            quiz_id_counter += 1
            data["quiz_logs"].append(quiz)
        
        # 3. RAGSimulationSession & Evaluation
        # 기수 완료까지 평균 8~15회 시뮬레이션 진행
        num_simulations = random.randint(8, 15)
        for s in range(num_simulations):
            sim_date = generate_datetime_in_range(cohort_start, cohort_end)
            
            # 점수는 시간에 따라 상승
            progress = (sim_date - datetime.combine(cohort_start, datetime.min.time())).days / 90
            if growth_type == "normal":
                base_score = 30 + progress * 50
            elif growth_type == "slow":
                base_score = 25 + progress * 35
            else:
                base_score = 30 + progress * 15
            
            total_score = int(max(0, min(100, base_score + random.randint(-10, 10))))
            metrics = generate_simulation_metrics(total_score)
            
            session = generate_simulation_session(
                session_id=session_id_counter,
                user_id=user_id,
                started_at=sim_date,
                is_completed=True,
                total_turns=random.randint(6, 15),
            )
            data["simulation_sessions"].append(session)
            
            evaluation = generate_simulation_evaluation(
                eval_id=eval_id_counter,
                session_id=session_id_counter,
                user_id=user_id,
                metrics=metrics,
                created_at=sim_date + timedelta(minutes=random.randint(3, 10)),
            )
            data["simulation_evaluations"].append(evaluation)
            
            # SimulationFeedback 생성 (시뮬레이션 분석용)
            sim_feedback = generate_simulation_feedback(
                feedback_id=sim_feedback_id_counter,
                user_id=user_id,
                session_key=session["session_key"],
                total_score=total_score,
                created_at=sim_date + timedelta(minutes=random.randint(3, 10)),
            )
            data["simulation_feedbacks"].append(sim_feedback)
            sim_feedback_id_counter += 1
            
            session_id_counter += 1
            eval_id_counter += 1
    
    # ================================================================
    # 매칭 및 관계 생성
    # ================================================================
    
    # 멘토당 2명의 멘티 매칭 (15명 멘토 × 2 = 30명 멘티)
    matched_at = datetime.combine(cohort_start + timedelta(days=3), datetime.min.time()) + timedelta(hours=14)
    
    for i, mentee in enumerate(mentees):
        mentor_idx = i // 2  # 2명당 1명의 멘토
        if mentor_idx >= len(mentors):
            mentor_idx = len(mentors) - 1
        mentor = mentors[mentor_idx]
        
        # MatchingResult
        matching = generate_matching_result(
            result_id=matching_id_counter,
            mentee_id=mentee["record_id"],
            mentor_id=mentor["record_id"],
            matched_at=matched_at,
        )
        matching_id_counter += 1
        data["matching_results"].append(matching)
        
        # MentorMenteeRelation
        relation = generate_mentor_mentee_relation(
            relation_id=relation_id_counter,
            mentor_user_id=mentor["user_id"],
            mentee_user_id=mentee["user_id"],
            matched_at=matched_at,
        )
        relation_id_counter += 1
        data["mentor_mentee_relations"].append(relation)
        
        # Feedback (멘토가 멘티에게 2~5개)
        num_feedbacks = random.randint(2, 5)
        for f in range(num_feedbacks):
            feedback_date = generate_datetime_in_range(cohort_start + timedelta(days=14), cohort_end)
            feedback = generate_feedback(
                feedback_id=feedback_id_counter,
                mentor_id=mentor["user_id"],
                mentee_id=mentee["user_id"],
                created_at=feedback_date,
            )
            feedback_id_counter += 1
            data["feedbacks"].append(feedback)
    
    return data


# ============================================================================
# 메인 실행
# ============================================================================

def main():
    """메인 함수: 1~3기 시드 데이터 생성"""
    print("=" * 60)
    print("데모용 시드 데이터 생성 시작")
    print("=" * 60)
    
    # 출력 디렉토리 생성
    SEED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1~3기 데이터 생성
    for cohort_num in range(1, 4):
        print(f"\n[{cohort_num}기] 데이터 생성 중...")
        
        data = generate_cohort_data(cohort_num, id_offset=cohort_num)
        
        # JSON 파일로 저장
        output_file = SEED_OUTPUT_DIR / f"cohort_{cohort_num}_2025.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 통계 출력
        print(f"  - 멘토: {len([u for u in data['users'] if u['role'] == 'mentor'])}명")
        print(f"  - 멘티: {len([u for u in data['users'] if u['role'] == 'mentee'])}명")
        print(f"  - ExamScore: {len(data['exam_scores'])}개")
        print(f"  - QuizLog: {len(data['quiz_logs'])}개")
        print(f"  - Simulation: {len(data['simulation_sessions'])}개")
        print(f"  - SimulationFeedback: {len(data['simulation_feedbacks'])}개")
        print(f"  - Matching: {len(data['matching_results'])}개")
        print(f"  - Feedback: {len(data['feedbacks'])}개")
        print(f"  → 저장: {output_file}")
    
    print("\n" + "=" * 60)
    print("시드 데이터 생성 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()

