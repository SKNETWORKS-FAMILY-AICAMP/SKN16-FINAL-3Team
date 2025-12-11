"""
퀴즈 데이터 개선 스크립트
- 맞춤/랜덤 퀴즈: 다양한 영역과 다양한 문제 수로 개선
- 초기/중간/최종 평가: 1회만 유지
"""
import json
import random
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict

# 영역 목록
TRAINING_SECTION_KEYS = [
    "금융영업",
    "상품개발 및 운용",
    "신용분석 및 리스크관리",
    "외환",
    "은행지식 및 관련법률",
    "하경은행",
]

# 평가 모드 (1회만 유지)
EXAM_MODES = ["pre", "midterm", "final"]


def generate_custom_quiz_extra() -> Dict[str, Any]:
    """맞춤 퀴즈 extra 생성: 단일 또는 2개 영역, 5~30개 문제"""
    num_categories = random.choice([1, 2])  # 1개 또는 2개 영역
    categories = random.sample(TRAINING_SECTION_KEYS, num_categories)
    total_questions = random.choice([5, 8, 10, 12, 15, 18, 20, 25, 30])
    
    if num_categories == 1:
        return {
            "category": categories[0],
            "categories": categories,
            "category_distribution": {categories[0]: total_questions}
        }
    else:
        # 2개 영역으로 분배
        q1 = total_questions // 2
        q2 = total_questions - q1
        return {
            "category": categories[0],  # 호환성을 위해 첫 번째 카테고리 유지
            "categories": categories,
            "category_distribution": {
                categories[0]: q1,
                categories[1]: q2
            }
        }


def generate_random_quiz_extra() -> Dict[str, Any]:
    """랜덤 퀴즈 extra 생성: 2~6개 영역, 10~40개 문제"""
    num_categories = random.randint(2, 6)
    categories = random.sample(TRAINING_SECTION_KEYS, num_categories)
    total_questions = random.choice([10, 12, 15, 18, 20, 25, 30, 35, 40])
    
    # 문제 수를 영역별로 분배
    base_per_category = total_questions // num_categories
    remainder = total_questions % num_categories
    
    category_distribution = {}
    for i, cat in enumerate(categories):
        category_distribution[cat] = base_per_category + (1 if i < remainder else 0)
    
    return {
        "category": categories[0],  # 호환성을 위해 첫 번째 카테고리 유지
        "categories": categories,
        "category_distribution": category_distribution
    }


def update_quiz_logs(quiz_logs: List[Dict[str, Any]], user_exam_modes: Dict[int, set]) -> List[Dict[str, Any]]:
    """퀴즈 로그 업데이트"""
    updated_logs = []
    
    for quiz in quiz_logs:
        mode = quiz.get("mode")
        user_id = quiz.get("user_id")
        
        # 평가 모드 (pre/midterm/final)는 1회만 유지
        if mode in EXAM_MODES:
            if user_id not in user_exam_modes:
                user_exam_modes[user_id] = set()
            
            if mode in user_exam_modes[user_id]:
                # 이미 해당 평가가 있으면 스킵
                continue
            
            user_exam_modes[user_id].add(mode)
            # 평가는 60문제 고정 (6개 영역 * 10문제)
            quiz["total_questions"] = 60
            quiz["extra"] = {
                "category": "전체",
                "categories": TRAINING_SECTION_KEYS,
                "category_distribution": {cat: 10 for cat in TRAINING_SECTION_KEYS}
            }
        
        # 맞춤 퀴즈
        elif mode == "custom":
            quiz["total_questions"] = random.choice([5, 8, 10, 12, 15, 18, 20, 25, 30])
            quiz["extra"] = generate_custom_quiz_extra()
        
        # 랜덤 퀴즈
        elif mode == "random":
            quiz["total_questions"] = random.choice([10, 12, 15, 18, 20, 25, 30, 35, 40])
            quiz["extra"] = generate_random_quiz_extra()
        
        updated_logs.append(quiz)
    
    return updated_logs


def ensure_single_exam_per_type(exam_scores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """각 사용자별로 초기/중간/최종 평가가 1회만 있도록 보장"""
    user_exams = defaultdict(dict)  # {user_id: {exam_type: exam_data}}
    
    for exam in exam_scores:
        user_id = exam.get("mentee_id")
        exam_type = exam.get("exam_type")
        
        if user_id and exam_type:
            # 이미 해당 타입의 평가가 없으면 추가
            if exam_type not in user_exams[user_id]:
                user_exams[user_id][exam_type] = exam
    
    # 중복 제거된 평가 목록 생성
    unique_exams = []
    for user_id, exams in user_exams.items():
        for exam_type, exam in exams.items():
            unique_exams.append(exam)
    
    return unique_exams


def process_cohort_file(file_path: Path):
    """cohort JSON 파일 처리"""
    print(f"\n📝 처리 중: {file_path.name}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 1. exam_scores 정리 (1회만 유지)
    if "exam_scores" in data:
        original_count = len(data["exam_scores"])
        data["exam_scores"] = ensure_single_exam_per_type(data["exam_scores"])
        updated_count = len(data["exam_scores"])
        print(f"  ✅ exam_scores: {original_count} → {updated_count} (중복 제거)")
    
    # 2. quiz_logs 업데이트
    if "quiz_logs" in data:
        user_exam_modes = defaultdict(set)  # 각 사용자별 평가 모드 추적
        
        original_count = len(data["quiz_logs"])
        data["quiz_logs"] = update_quiz_logs(data["quiz_logs"], user_exam_modes)
        updated_count = len(data["quiz_logs"])
        
        # 통계
        custom_count = sum(1 for q in data["quiz_logs"] if q.get("mode") == "custom")
        random_count = sum(1 for q in data["quiz_logs"] if q.get("mode") == "random")
        exam_count = sum(1 for q in data["quiz_logs"] if q.get("mode") in EXAM_MODES)
        
        print(f"  ✅ quiz_logs: {original_count} → {updated_count}")
        print(f"     - 맞춤: {custom_count}개, 랜덤: {random_count}개, 평가: {exam_count}개")
        
        # 문제 수 분포 확인
        question_counts = defaultdict(int)
        for quiz in data["quiz_logs"]:
            count = quiz.get("total_questions", 0)
            question_counts[count] += 1
        
        print(f"     - 문제 수 분포: {dict(sorted(question_counts.items()))}")
    
    # 백업 파일 생성
    backup_path = file_path.with_suffix(".json.backup")
    if not backup_path.exists():
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  💾 백업 생성: {backup_path.name}")
    
    # 업데이트된 파일 저장
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ 완료: {file_path.name}")


def main():
    """메인 함수"""
    seed_dir = Path(__file__).parent.parent / "data" / "seed"
    
    cohort_files = [
        seed_dir / "cohort_1_2025.json",
        seed_dir / "cohort_2_2025.json",
        seed_dir / "cohort_3_2025.json",
    ]
    
    print("🚀 퀴즈 데이터 개선 시작...")
    print("=" * 60)
    
    for file_path in cohort_files:
        if file_path.exists():
            try:
                process_cohort_file(file_path)
            except Exception as e:
                print(f"  ❌ 오류 발생: {e}")
        else:
            print(f"  ⚠️  파일 없음: {file_path.name}")
    
    print("=" * 60)
    print("✅ 모든 파일 처리 완료!")


if __name__ == "__main__":
    main()



