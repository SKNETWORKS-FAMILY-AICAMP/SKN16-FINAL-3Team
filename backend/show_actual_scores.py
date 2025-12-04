"""
실제 점수 표시 - 초기/중간/최종 점수를 명확하게 보여주기
"""
import json
from pathlib import Path

def show_scores():
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
    print("초기 / 중간 / 최종 평가 점수 상세")
    print("=" * 80)
    print(f"\n{'멘티ID':<10} {'초기 (30~40%)':<20} {'중간 (50~70%)':<20} {'최종 (80~90%)':<20}")
    print("-" * 80)
    
    # 처음 15명만 표시
    for mentee_id in sorted(mentee_scores.keys())[:15]:
        beginning = mentee_scores[mentee_id].get('beginning', 'N/A')
        midterm = mentee_scores[mentee_id].get('midterm', 'N/A')
        final = mentee_scores[mentee_id].get('final', 'N/A')
        
        # 초기
        if isinstance(beginning, (int, float)):
            beginning_str = f"{beginning:.0f}점 ({beginning/60*100:.1f}%)"
        else:
            beginning_str = "N/A"
        
        # 중간
        if isinstance(midterm, (int, float)):
            midterm_str = f"{midterm:.0f}점 ({midterm/60*100:.1f}%)"
        else:
            midterm_str = "N/A"
        
        # 최종
        if isinstance(final, (int, float)):
            final_str = f"{final:.0f}점 ({final/60*100:.1f}%)"
        else:
            final_str = "N/A"
        
        print(f"{mentee_id:<10} {beginning_str:<20} {midterm_str:<20} {final_str:<20}")
    
    print("\n" + "=" * 80)
    print("요청하신 범위:")
    print("  초기: 30~40점/100점 → 18~24점/60점 (30~40%)")
    print("  중간: 50~70점/100점 → 30~42점/60점 (50~70%)")
    print("  최종: 80~90점/100점 → 48~54점/60점 (80~90%)")
    print("=" * 80)

if __name__ == "__main__":
    show_scores()

