from sqlmodel import Session, select, col
from app.database import engine
from app.models.simulation_feedback import SimulationFeedback
import json
from datetime import datetime

def check_past_rag_methods():
    with Session(engine) as session:
        # 12월 1일 ~ 12월 3일 기록 조회
        start_date = datetime(2025, 12, 1)
        end_date = datetime(2025, 12, 4)
        
        statement = select(SimulationFeedback).where(
            SimulationFeedback.created_at >= start_date,
            SimulationFeedback.created_at < end_date
        ).order_by(SimulationFeedback.created_at.desc()).limit(10)
        
        feedbacks = session.exec(statement).all()
        
        print(f"🔍 2025-12-01 ~ 12-03 시뮬레이션 기록 분석\n" + "="*60)
        
        for fb in feedbacks:
            if not fb.rag_evaluations:
                continue
                
            evals = fb.rag_evaluations
            if isinstance(evals, str):
                try:
                    evals = json.loads(evals)
                except:
                    continue
            
            # 날짜 포맷
            date_str = fb.created_at.strftime("%Y-%m-%d %H:%M")
            print(f"\n📅 날짜: {date_str} (ID: {fb.id})")
            
            has_vector = False
            has_keyword = False
            similarities = []
            
            for item in evals:
                if not isinstance(item, dict):
                    continue
                    
                # claim 검증 결과 확인
                claim_verifications = item.get('evaluation', {}).get('claim_verifications', [])
                for cv in claim_verifications:
                    method = cv.get('verification_method', 'unknown')
                    sim = cv.get('similarity') or 0.0
                    
                    if 'vector' in method:
                        has_vector = True
                    if 'keyword' in method or 'llm' in method: # llm 메서드일 때도 similarity가 높으면 키워드일 수 있음
                        # verification_method가 'llm'으로 덮어씌워진 경우, similarity 점수로 추정
                        # (벡터 검색은 보통 정밀한 float값, 키워드 재계산도 float이지만...)
                        # 사실상 method 이름으로 구분해야 함.
                        pass
                        
                    similarities.append(f"{method}({sim:.1%}%)")
                
                # 근거 청크 확인 (product_evidence)
                evidence = item.get('evaluation', {}).get('product_evidence', {})
                if evidence and evidence.get('matched_chunks'):
                    # 여기에 벡터 검색 결과가 있는지 확인
                    pass

            print(f"   👉 검증 방식 분포: {', '.join(similarities[:3])}...")
            
            # 벡터 검색 성공 여부 판단
            if any("vector" in s for s in similarities):
                print(f"   ✅ [벡터 검색 성공] 이 기록은 벡터 검색을 사용했습니다.")
            else:
                print(f"   ⚠️ [키워드/LLM 사용] 이 기록은 벡터 검색 결과가 없거나 키워드 검색을 사용했습니다.")

if __name__ == "__main__":
    check_past_rag_methods()

