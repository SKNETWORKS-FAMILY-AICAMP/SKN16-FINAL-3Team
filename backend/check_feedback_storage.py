#!/usr/bin/env python3
"""
시뮬레이션 피드백 저장 확인 스크립트
"""
from sqlmodel import Session, select
from app.database import engine
from app.models.simulation_feedback import SimulationFeedback
from datetime import datetime, timedelta

def check_feedback_storage():
    """시뮬레이션 피드백 저장 확인"""
    with Session(engine) as session:
        # 전체 평가서 수 확인
        all_feedbacks = session.exec(select(SimulationFeedback)).all()
        print(f"\n{'='*60}")
        print(f"📊 시뮬레이션 피드백 저장 현황")
        print(f"{'='*60}")
        print(f"총 평가서 수: {len(all_feedbacks)}개\n")
        
        if len(all_feedbacks) == 0:
            print("⚠️ 저장된 평가서가 없습니다.")
            return
        
        # 최근 10개 평가서 상세 정보
        recent_feedbacks = session.exec(
            select(SimulationFeedback)
            .order_by(SimulationFeedback.created_at.desc())
            .limit(10)
        ).all()
        
        print("최근 평가서 목록:")
        print("-" * 60)
        for idx, fb in enumerate(recent_feedbacks, 1):
            print(f"\n{idx}. Feedback ID: {fb.id}")
            print(f"   User ID: {fb.user_id}")
            print(f"   Session Key: {fb.session_key}")
            print(f"   Persona ID: {fb.persona_id}")
            print(f"   Situation ID: {fb.situation_id}")
            print(f"   Overall Score: {fb.overall_score}")
            print(f"   Grade: {fb.grade}")
            print(f"   Test Mode: {fb.is_test_mode}")
            print(f"   Total Turns: {fb.total_turns}")
            print(f"   Duration: {fb.duration_seconds}초" if fb.duration_seconds else "   Duration: N/A")
            print(f"   Created At: {fb.created_at}")
            print(f"   Has Conversation Log: {bool(fb.conversation_log)}")
            print(f"   Has Goal Achievement: {bool(fb.goal_achievement_data)}")
            print(f"   Has RAG Evaluations: {bool(fb.rag_evaluations)}")
        
        # 오늘 생성된 평가서 수
        today = datetime.now().date()
        today_feedbacks = [
            fb for fb in all_feedbacks 
            if fb.created_at.date() == today
        ]
        print(f"\n{'='*60}")
        print(f"📅 오늘 생성된 평가서: {len(today_feedbacks)}개")
        print(f"{'='*60}\n")
        
        # 사용자별 평가서 수
        from collections import defaultdict
        user_counts = defaultdict(int)
        for fb in all_feedbacks:
            user_counts[fb.user_id] += 1
        
        print("사용자별 평가서 수:")
        for user_id, count in sorted(user_counts.items()):
            print(f"  User {user_id}: {count}개")
        
        print(f"\n{'='*60}\n")

if __name__ == "__main__":
    check_feedback_storage()

