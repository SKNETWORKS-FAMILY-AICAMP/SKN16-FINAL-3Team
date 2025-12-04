"""
상세 시험 점수 분석 - 문제점 확인
"""
import json
from pathlib import Path

def detailed_check():
    seed_file = Path(__file__).parent / 'data' / 'seed' / 'cohort_2_2025.json'
    
    with open(seed_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    exam_scores = data.get('exam_scores', [])
    
    # 멘티별로 그룹화
    mentee_scores = {}
    for exam in exam_scores:
        mentee_id = exam.get('mentee_id')
        exam_type = exam.get('exam_type')
        total_score = exam.get('total_score', 0)
        
        if mentee_id not in mentee_scores:
            mentee_scores[mentee_id] = {}
        
        mentee_scores[mentee_id][exam_type] = total_score
    
    print("=" * 80)
    print("상세 점수 분석 - cohort_2_2025.json")
    print("=" * 80)
    
    # 범위별 분류
    beginning_low = []  # 18점 미만
    beginning_good = []  # 18~24점
    beginning_high = []  # 24점 초과
    
    midterm_low = []  # 30점 미만
    midterm_good = []  # 30~42점
    midterm_high = []  # 42점 초과
    
    final_low = []  # 48점 미만
    final_good = []  # 48~54점
    final_high = []  # 54점 초과
    
    for mentee_id, scores in mentee_scores.items():
        beginning = scores.get('beginning')
        midterm = scores.get('midterm')
        final = scores.get('final')
        
        if beginning:
            if beginning < 18:
                beginning_low.append((mentee_id, beginning))
            elif beginning <= 24:
                beginning_good.append((mentee_id, beginning))
            else:
                beginning_high.append((mentee_id, beginning))
        
        if midterm:
            if midterm < 30:
                midterm_low.append((mentee_id, midterm))
            elif midterm <= 42:
                midterm_good.append((mentee_id, midterm))
            else:
                midterm_high.append((mentee_id, midterm))
        
        if final:
            if final < 48:
                final_low.append((mentee_id, final))
            elif final <= 54:
                final_good.append((mentee_id, final))
            else:
                final_high.append((mentee_id, final))
    
    print(f"\n초기 평가 (목표: 18~24점, 30~40%):")
    print(f"  ✅ 적절한 범위 (18~24점): {len(beginning_good)}명")
    print(f"  ❌ 범위 밖 낮음 (<18점): {len(beginning_low)}명")
    if beginning_low:
        print(f"     예시: {beginning_low[:5]}")
    print(f"  ❌ 범위 밖 높음 (>24점): {len(beginning_high)}명")
    if beginning_high:
        print(f"     예시: {beginning_high[:5]}")
    
    print(f"\n중간 평가 (목표: 30~42점, 50~70%):")
    print(f"  ✅ 적절한 범위 (30~42점): {len(midterm_good)}명")
    print(f"  ❌ 범위 밖 낮음 (<30점): {len(midterm_low)}명")
    if midterm_low:
        print(f"     예시: {midterm_low[:5]}")
    print(f"  ❌ 범위 밖 높음 (>42점): {len(midterm_high)}명")
    if midterm_high:
        print(f"     예시: {midterm_high[:5]}")
    
    print(f"\n최종 평가 (목표: 48~54점, 80~90%):")
    print(f"  ✅ 적절한 범위 (48~54점): {len(final_good)}명")
    print(f"  ❌ 범위 밖 낮음 (<48점): {len(final_low)}명")
    if final_low:
        print(f"     예시: {final_low[:5]}")
    print(f"  ❌ 범위 밖 높음 (>54점): {len(final_high)}명")
    if final_high:
        print(f"     예시: {final_high[:5]}")
    
    # 점진적 상승 위반 사례
    print(f"\n점진적 상승 위반 사례:")
    violations = []
    for mentee_id, scores in mentee_scores.items():
        beginning = scores.get('beginning')
        midterm = scores.get('midterm')
        final = scores.get('final')
        
        issue = []
        if beginning and midterm:
            if midterm < beginning:
                issue.append(f"중간({midterm}점) < 초기({beginning}점)")
        
        if midterm and final:
            if final < midterm:
                issue.append(f"최종({final}점) < 중간({midterm}점)")
        
        if issue:
            violations.append((mentee_id, issue))
    
    if violations:
        print(f"  총 {len(violations)}명의 멘티에서 위반 발견:")
        for mentee_id, issues in violations[:10]:
            print(f"    멘티 {mentee_id}: {', '.join(issues)}")
    else:
        print(f"  ✅ 점진적 상승 패턴 위반 없음")
    
    # 요청한 범위 확인 (30~40%, 50~70%, 80~90%)
    print(f"\n요청하신 범위 대비 확인:")
    print(f"  초기: 30~40% = 18~24점/60점 ✅")
    print(f"  중간: 50~70% = 30~42점/60점 ✅")
    print(f"  최종: 80~90% = 48~54점/60점 ✅")

if __name__ == "__main__":
    detailed_check()

