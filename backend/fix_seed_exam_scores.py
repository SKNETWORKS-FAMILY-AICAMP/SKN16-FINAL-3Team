"""
Seed 데이터의 시험 점수 수정 스크립트
- 하경은행 점수 다양화 (5~10점 범위)
- 각 영역 골고루 분포
- 초기/중간/최종 점진적 성장 (초기 30~40%, 중간 50~70%, 최종 80~90%)
- 일부(15%)는 공부를 안 해서 성적이 거의 오르지 않음
"""
import json
import random
from pathlib import Path
from typing import Dict, List, Optional

# 시험 영역 키
EXAM_SECTION_KEYS = [
    "은행업무",
    "상품개발 및 운용",
    "신용분석 및 리스크관리",
    "외환",
    "은행지식 및 관련법률",
    "하경은행",
]

def generate_balanced_section_scores(total: int) -> Dict[str, int]:
    """
    총점을 6개 섹션으로 균등 분배하면서 약간의 변동을 준다.
    - 하경은행을 포함한 모든 영역을 동일하게 처리
    - 각 영역이 골고루 분포되도록 보장
    """
    total = max(0, min(60, total))
    base = total // len(EXAM_SECTION_KEYS)
    remainder = total % len(EXAM_SECTION_KEYS)
    scores: Dict[str, int] = {}
    
    # 초기 분배: 균등 분배 + 나머지 처리
    for idx, key in enumerate(EXAM_SECTION_KEYS):
        scores[key] = min(10, base + (1 if idx < remainder else 0))
    
    # 더 다양한 편차 부여 (각 영역이 골고루 분포되도록)
    for _ in range(10):
        donor, receiver = random.sample(EXAM_SECTION_KEYS, 2)
        # 하경은행도 다른 영역과 동일하게 처리
        if scores[donor] > 2 and scores[receiver] < 10:
            transfer = min(2, scores[donor] - 2, 10 - scores[receiver])
            if transfer > 0:
                scores[donor] -= transfer
                scores[receiver] += transfer
    
    # 최종 검증: 각 영역이 0~10 범위 내에 있는지 확인
    for key in EXAM_SECTION_KEYS:
        scores[key] = max(0, min(10, scores[key]))
    
    # 총점 조정
    current_total = sum(scores.values())
    if current_total != total:
        diff = total - current_total
        if diff > 0:
            min_key = min(EXAM_SECTION_KEYS, key=lambda k: scores[k])
            scores[min_key] = min(10, scores[min_key] + diff)
        elif diff < 0:
            max_key = max(EXAM_SECTION_KEYS, key=lambda k: scores[k])
            scores[max_key] = max(0, scores[max_key] + diff)
    
    return scores


def generate_progressive_total_scores(user_index: int, exam_type: str, previous_total: Optional[int] = None) -> int:
    """
    사용자별, 시험 타입별 점진적 성장 점수 생성
    - 초기: 30~40점 / 100점 → 18~24점 (60점 만점)
    - 중간: 50~70점 / 100점 → 30~42점 (60점 만점)
    - 최종: 80~90점 / 100점 → 48~54점 (60점 만점)
    - 일부(15%)는 공부를 안 해서 성적이 거의 오르지 않음
    """
    # 사용자별 시드 생성 (일관된 점수 분포)
    user_seed = user_index % 10000
    random.seed(user_seed)
    
    # 성적이 오르지 않는 사람인지 결정 (15% 확률, 사용자별로 일관성 있게)
    is_low_performer = (user_seed % 100) < 15  # 0~99 중 0~14는 저성과자
    
    if exam_type == "beginning":
        # 초기: 30~40점 / 100점 → 18~24점
        if is_low_performer:
            base_score = random.randint(15, 20)  # 더 낮은 점수
        else:
            base_score = random.randint(18, 24)
    elif exam_type == "midterm":
        # 중간: 50~70점 / 100점 → 30~42점
        if previous_total is not None:
            if is_low_performer:
                # 성적이 안 오르는 경우: 최대 +3점
                base_score = random.randint(int(previous_total), int(previous_total) + 3)
                base_score = min(42, base_score)  # 최대 42점
            else:
                # 정상 상승: 초기보다 최소 +6점 이상
                min_score = max(30, int(previous_total) + 6)
                base_score = random.randint(min_score, 42)
        else:
            if is_low_performer:
                base_score = random.randint(20, 28)
            else:
                base_score = random.randint(30, 42)
    elif exam_type == "final":
        # 최종: 80~90점 / 100점 → 48~54점
        if previous_total is not None:
            if is_low_performer:
                # 성적이 안 오르는 경우: 최대 +3점
                base_score = random.randint(int(previous_total), int(previous_total) + 3)
                base_score = min(54, base_score)  # 최대 54점
            else:
                # 정상 상승: 중간보다 최소 +6점 이상
                min_score = max(48, int(previous_total) + 6)
                base_score = random.randint(min_score, 54)
        else:
            if is_low_performer:
                base_score = random.randint(25, 35)
            else:
                base_score = random.randint(48, 54)
    else:
        base_score = random.randint(18, 54)
    
    return base_score


def fix_exam_scores_in_seed_file(file_path: Path) -> None:
    """Seed 파일의 시험 점수 수정"""
    print(f"\n📝 {file_path.name} 수정 중...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    exam_scores = data.get('exam_scores', [])
    if not exam_scores:
        print(f"  ⚠️ 시험 점수 데이터가 없습니다.")
        return
    
    print(f"  총 {len(exam_scores)}개의 시험 점수 발견")
    
    # 사용자별 시험 타입별 추적 (점진적 성장 보장)
    user_exam_map: Dict[int, Dict[str, Dict]] = {}  # {mentee_id: {exam_type: {previous_score, ...}}}
    
    fixed_count = 0
    for exam in exam_scores:
        mentee_id = exam.get('mentee_id')
        exam_type = exam.get('exam_type', 'beginning')
        score_data_str = exam.get('score_data', '{}')
        
        if not score_data_str:
            continue
        
        # JSON 파싱
        try:
            score_data = json.loads(score_data_str) if isinstance(score_data_str, str) else score_data_str
        except:
            continue
        
        # 점진적 성장 점수 생성
        if mentee_id not in user_exam_map:
            user_exam_map[mentee_id] = {}
        
        # 이전 시험 타입 확인하여 점진적 성장 보장
        previous_score = None
        if exam_type == "midterm" and "beginning" in user_exam_map[mentee_id]:
            previous_score = user_exam_map[mentee_id]["beginning"].get("total")
        elif exam_type == "final":
            if "midterm" in user_exam_map[mentee_id]:
                previous_score = user_exam_map[mentee_id]["midterm"].get("total")
            elif "beginning" in user_exam_map[mentee_id]:
                previous_score = user_exam_map[mentee_id]["beginning"].get("total")
        
        # 총점 생성 (점진적 상승 패턴 적용)
        total_score = generate_progressive_total_scores(mentee_id, exam_type, previous_score)
        
        # 균등 분포 섹션 점수 생성
        new_section_scores = generate_balanced_section_scores(total_score)
        
        # 기존 키 매핑 유지 (은행업무 -> 은행업무 등)
        # 새로운 점수 데이터 생성
        new_score_data = {}
        for key in EXAM_SECTION_KEYS:
            new_score_data[key] = new_section_scores[key]
        
        # score_data 업데이트
        exam['score_data'] = json.dumps(new_score_data, ensure_ascii=False)
        
        # total_score 업데이트
        exam['total_score'] = float(total_score)
        
        # 사용자별 시험 타입 저장
        user_exam_map[mentee_id][exam_type] = {
            "total": total_score,
            "section_scores": new_section_scores
        }
        
        fixed_count += 1
    
    # 수정된 데이터 저장
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ {fixed_count}개의 시험 점수 수정 완료")


def main():
    """메인 함수"""
    print("=" * 80)
    print("Seed 데이터 시험 점수 수정")
    print("=" * 80)
    
    seed_dir = Path(__file__).parent / 'data' / 'seed'
    
    seed_files = [
        'cohort_1_2025.json',
        'cohort_2_2025.json',
        'cohort_3_2025.json',
    ]
    
    for seed_file in seed_files:
        file_path = seed_dir / seed_file
        if file_path.exists():
            try:
                fix_exam_scores_in_seed_file(file_path)
            except Exception as e:
                print(f"  ❌ 오류 발생: {e}")
        else:
            print(f"  ⚠️ {seed_file} 파일을 찾을 수 없습니다.")
    
    print("\n" + "=" * 80)
    print("✅ Seed 데이터 수정 완료")
    print("=" * 80)


if __name__ == "__main__":
    main()
