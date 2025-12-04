"""
학습 이력 API 응답 데이터 분석 스크립트
"""
import json
import requests
from datetime import datetime

# API 엔드포인트
BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/admin/learning-history"

# 테스트할 사용자 ID (4기 멘티 중 하나)
TEST_USER_ID = 7310  # 김영민

def analyze_learning_history():
    print("=" * 80)
    print("학습 이력 API 응답 데이터 분석")
    print("=" * 80)
    
    # 헤더 (관리자 토큰 필요 - 실제로는 로그인해서 가져와야 함)
    headers = {
        "Content-Type": "application/json",
        # "Authorization": "Bearer YOUR_TOKEN_HERE"  # 실제로는 토큰 필요
    }
    
    params = {
        "user_id": TEST_USER_ID,
        "limit": 50
    }
    
    print(f"\n요청 URL: {API_URL}")
    print(f"파라미터: {params}")
    print("\n⚠️ 실제 API 호출을 위해서는 인증 토큰이 필요합니다.")
    print("   대신 데이터베이스를 직접 확인합니다...\n")
    
    # 데이터베이스 직접 조회로 대체
    from sqlmodel import Session, select, create_engine
    from app.models.quiz import QuizGenerationLog
    from app.models.mentor import ExamScore
    from app.models.user import User
    
    # 데이터베이스 연결
    DATABASE_URL = "postgresql://mentoruser:mentorpass@localhost:5432/mentordb"
    engine = create_engine(DATABASE_URL)
    
    with Session(engine) as session:
        # 1. 퀴즈 데이터 확인
        print("\n" + "=" * 80)
        print("1. 퀴즈 데이터 분석")
        print("=" * 80)
        
        quiz_logs = session.exec(
            select(QuizGenerationLog).where(QuizGenerationLog.user_id == TEST_USER_ID)
            .order_by(QuizGenerationLog.created_at.desc())
            .limit(5)
        ).all()
        
        print(f"\n퀴즈 로그 수: {len(quiz_logs)}")
        
        for log in quiz_logs:
            print(f"\n퀴즈 ID: {log.id}")
            print(f"  모드: {log.mode}")
            print(f"  점수: {log.score}")
            print(f"  문항수: {log.total_questions}")
            print(f"  질문 수: {len(log.questions) if log.questions else 0}")
            print(f"  답변 수: {len(log.answers) if log.answers else 0}")
            
            if log.questions:
                print(f"\n  질문 카테고리 분포:")
                categories = {}
                for q in log.questions[:5]:  # 처음 5개만
                    cat = q.get("category_name") or q.get("category") or "기타"
                    categories[cat] = categories.get(cat, 0) + 1
                for cat, count in categories.items():
                    print(f"    - {cat}: {count}개")
            
            if log.answers:
                print(f"\n  답변 예시 (처음 3개):")
                for i, (qid, answer) in enumerate(list(log.answers.items())[:3]):
                    print(f"    - {qid}: {answer}")
        
        # 2. 시험 데이터 확인
        print("\n" + "=" * 80)
        print("2. 시험 데이터 분석")
        print("=" * 80)
        
        exam_scores = session.exec(
            select(ExamScore).where(ExamScore.mentee_id == TEST_USER_ID)
            .order_by(ExamScore.exam_date.desc())
        ).all()
        
        print(f"\n시험 점수 수: {len(exam_scores)}")
        
        for exam in exam_scores:
            print(f"\n시험 ID: {exam.id}")
            print(f"  시험 타입: {exam.exam_type}")
            print(f"  총점: {exam.total_score}")
            print(f"  시험명: {exam.exam_name}")
            
            # score_data 파싱
            if exam.score_data:
                try:
                    score_data = json.loads(exam.score_data) if isinstance(exam.score_data, str) else exam.score_data
                    print(f"  영역별 점수:")
                    for key, value in score_data.items():
                        print(f"    - {key}: {value}")
                except Exception as e:
                    print(f"  score_data 파싱 실패: {e}")
                    print(f"  score_data 원본: {exam.score_data[:100] if len(str(exam.score_data)) > 100 else exam.score_data}")
            else:
                print(f"  score_data 없음")

if __name__ == "__main__":
    try:
        analyze_learning_history()
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

