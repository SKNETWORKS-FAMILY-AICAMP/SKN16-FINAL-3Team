"""
시험 점수 점진적 상승 패턴 확인 스크립트
"""
import json
from pathlib import Path
from collections import defaultdict

def check_exam_scores():
    seed_dir = Path(__file__).parent / 'data' / 'seed'
    
    seed_files = [
        'cohort_1_2025.json',
        'cohort_2_2025.json',
        'cohort_3_2025.json',
    ]
    
    for seed_file in seed_files:
        file_path = seed_dir / seed_file
        if not file_path.exists():
            print(f"⚠️ {seed_file} 파일을 찾을 수 없습니다.")
            continue
        
        print(f"\n{'=' * 80}")
        print(f"📊 {seed_file} 분석")
        print(f"{'=' * 80}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        exam_scores = data.get('exam_scores', [])
        
        # 멘티별로 시험 점수 그룹화
        mentee_exams = defaultdict(dict)
        for exam in exam_scores:
            mentee_id = exam.get('mentee_id')
            exam_type = exam.get('exam_type')
            total_score = exam.get('total_score', 0)
            
            if mentee_id and exam_type:
                mentee_exams[mentee_id][exam_type] = total_score
        
        # 초기/중간/최종 점수 분포 확인
        beginning_scores = []
        midterm_scores = []
        final_scores = []
        
        for mentee_id, exams in mentee_exams.items():
            if 'beginning' in exams:
                beginning_scores.append(exams['beginning'])
            if 'midterm' in exams:
                midterm_scores.append(exams['midterm'])
            if 'final' in exams:
                final_scores.append(exams['final'])
        
        print(f"\n📈 점수 분포 분석:")
        if beginning_scores:
            avg_b = sum(beginning_scores) / len(beginning_scores)
            min_b = min(beginning_scores)
            max_b = max(beginning_scores)
            print(f"  초기 평가: 평균 {avg_b:.1f}점 ({avg_b/60*100:.1f}%), 범위 {min_b:.0f}~{max_b:.0f}점 (목표: 18~24점, 30~40%)")
        if midterm_scores:
            avg_m = sum(midterm_scores) / len(midterm_scores)
            min_m = min(midterm_scores)
            max_m = max(midterm_scores)
            print(f"  중간 평가: 평균 {avg_m:.1f}점 ({avg_m/60*100:.1f}%), 범위 {min_m:.0f}~{max_m:.0f}점 (목표: 30~42점, 50~70%)")
        if final_scores:
            avg_f = sum(final_scores) / len(final_scores)
            min_f = min(final_scores)
            max_f = max(final_scores)
            print(f"  최종 평가: 평균 {avg_f:.1f}점 ({avg_f/60*100:.1f}%), 범위 {min_f:.0f}~{max_f:.0f}점 (목표: 48~54점, 80~90%)")
        
        # 멘티별 점진적 상승 패턴 확인 (처음 10명)
        print(f"\n📋 멘티별 점진적 상승 패턴 (처음 10명):")
        count = 0
        for mentee_id in sorted(mentee_exams.keys())[:10]:
            exams = mentee_exams[mentee_id]
            beginning = exams.get('beginning', 'N/A')
            midterm = exams.get('midterm', 'N/A')
            final = exams.get('final', 'N/A')
            
            beginning_pct = f"({beginning/60*100:.1f}%)" if isinstance(beginning, (int, float)) else ""
            midterm_pct = f"({midterm/60*100:.1f}%)" if isinstance(midterm, (int, float)) else ""
            final_pct = f"({final/60*100:.1f}%)" if isinstance(final, (int, float)) else ""
            
            print(f"  멘티 {mentee_id}: 초기={beginning}점 {beginning_pct}, 중간={midterm}점 {midterm_pct}, 최종={final}점 {final_pct}")
            count += 1
            if count >= 10:
                break
        
        # 점진적 상승 패턴 위반 확인
        print(f"\n⚠️ 점진적 상승 패턴 위반 확인:")
        violations = []
        for mentee_id, exams in mentee_exams.items():
            beginning = exams.get('beginning')
            midterm = exams.get('midterm')
            final = exams.get('final')
            
            issues = []
            if beginning and isinstance(beginning, (int, float)):
                if beginning < 18 or beginning > 24:
                    issues.append(f"초기({beginning}점)가 18~24점 범위를 벗어남")
            
            if midterm and isinstance(midterm, (int, float)):
                if midterm < 30 or midterm > 42:
                    issues.append(f"중간({midterm}점)이 30~42점 범위를 벗어남")
                if beginning and isinstance(beginning, (int, float)):
                    if midterm < beginning:
                        issues.append(f"중간({midterm}점)이 초기({beginning}점)보다 낮음")
            
            if final and isinstance(final, (int, float)):
                if final < 48 or final > 54:
                    issues.append(f"최종({final}점)이 48~54점 범위를 벗어남")
                if midterm and isinstance(midterm, (int, float)):
                    if final < midterm:
                        issues.append(f"최종({final}점)이 중간({midterm}점)보다 낮음")
            
            if issues:
                violations.append((mentee_id, issues))
        
        if violations:
            print(f"  총 {len(violations)}명의 멘티에서 패턴 위반 발견:")
            for mentee_id, issues in violations[:5]:  # 처음 5명만 표시
                print(f"    멘티 {mentee_id}: {', '.join(issues)}")
            if len(violations) > 5:
                print(f"    ... 외 {len(violations) - 5}명")
        else:
            print(f"  ✅ 모든 멘티가 점진적 상승 패턴을 따릅니다!")

if __name__ == "__main__":
    check_exam_scores()

