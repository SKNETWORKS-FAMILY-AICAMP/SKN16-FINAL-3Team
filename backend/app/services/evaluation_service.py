"""
시뮬레이션 평가 서비스
RAG 시뮬레이션 결과를 GPT-4로 평가하고 DB에 저장
"""
import json
import re
from typing import Dict, List, Tuple, Optional
from sqlmodel import Session, select
import openai
import os

from app.models.rag_simulation import (
    RAGSimulationSession, 
    RAGSimulationTurn, 
    RAGSimulationEvaluation
)

# 시스템 프롬프트
EVAL_SYSTEM_PROMPT = """당신은 "신입 은행원 고객 응대 시뮬레이션 평가 모델"입니다.
NCS 국가직무능력기준을 기반으로 지식(40) / 기술(30) / 태도(30)로 평가합니다.
대화 속 teller 발화만 평가하고, 반드시 JSON 스키마를 준수하며 출력합니다.
근거는 반드시 발화 문장을 직접 인용합니다.
개선안은 행동 기반 문장으로 제시합니다.
불필요한 설명 없이 JSON ONLY 출력."""


class EvaluationService:
    """시뮬레이션 평가 서비스"""
    
    def __init__(self, session: Session):
        self.session = session
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.client = openai.OpenAI(api_key=api_key)
        else:
            print("⚠️ OpenAI API 키가 없습니다. 평가 기능을 사용할 수 없습니다.")
            self.client = None
    
    def evaluate_session(self, session_key: str) -> Dict:
        """세션 평가 실행"""
        # 세션 조회
        sim_session = self.session.exec(
            select(RAGSimulationSession)
            .where(RAGSimulationSession.session_key == session_key)
        ).first()
        
        if not sim_session:
            raise ValueError(f"세션을 찾을 수 없습니다: {session_key}")
        
        # 대화 기록 조회
        turns = self.session.exec(
            select(RAGSimulationTurn)
            .where(RAGSimulationTurn.session_id == sim_session.id)
            .order_by(RAGSimulationTurn.turn_index.asc())
        ).all()
        
        if not turns:
            raise ValueError("평가할 대화 기록이 없습니다.")
        
        # 평가용 데이터 준비
        dialogue_payload, voice_payload = self._build_payload(turns)
        
        # GPT-4로 평가 실행
        model_output = self._call_eval_model(dialogue_payload, voice_payload)
        
        # JSON 파싱 및 검증
        parsed = self._parse_eval_json(model_output)
        
        # DB에 평가 결과 저장
        eval_record = self._save_evaluation(sim_session, parsed, model_output)
        
        # 세션 완료 처리
        self._mark_session_completed(sim_session)
        
        # 응답 형식으로 변환
        return {
            "session_id": session_key,
            "score": {
                "knowledge": {"point": eval_record.knowledge_point, "reason": ""},
                "skill": {"point": eval_record.skill_point, "reason": ""},
                "attitude": {"point": eval_record.attitude_point, "reason": ""},
                "total": eval_record.total_point
            },
            "detail_feedback": {
                "strengths": json.loads(eval_record.strengths) if eval_record.strengths else [],
                "improvements": json.loads(eval_record.improvements) if eval_record.improvements else [],
                "recommended_training": json.loads(eval_record.recommended_training) if eval_record.recommended_training else []
            }
        }
    
    def _build_payload(self, turns: List[RAGSimulationTurn]) -> Tuple[Dict, Dict]:
        """평가용 데이터 구조 생성"""
        dialogue = []
        for turn in turns:
            dialogue.append({
                "role": turn.role,
                "text": turn.text
            })
        
        # 음성 특성 집계 (teller 발화만)
        teller_speeds = [
            t.voice_speed for t in turns 
            if t.role == "teller" and t.voice_speed is not None
        ]
        teller_tones = [
            t.tone_score for t in turns 
            if t.role == "teller" and t.tone_score is not None
        ]
        
        voice_payload = {
            "speed": round(sum(teller_speeds) / len(teller_speeds), 3) if teller_speeds else None,
            "tone_score": round(sum(teller_tones) / len(teller_tones), 3) if teller_tones else None
        }
        
        dialogue_payload = {"dialogue": dialogue}
        
        return dialogue_payload, voice_payload
    
    def _call_eval_model(self, dialogue_payload: Dict, voice_payload: Dict) -> str:
        """GPT-4 평가 모델 호출"""
        if not self.client:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다.")
        
        # 사용자 프롬프트 생성
        user_prompt = json.dumps({
            **dialogue_payload,
            **voice_payload
        }, ensure_ascii=False)
        
        print(f"📊 평가 요청 전송... (대화 {len(dialogue_payload['dialogue'])}턴)")
        
        # GPT-4 호출 (temperature=0.0으로 일관성 확보)
        response = self.client.chat.completions.create(
            model="gpt-4o",
            temperature=0.0,  # 일관된 평가를 위해
            response_format={"type": "json_object"},  # JSON 강제
            messages=[
                {"role": "system", "content": EVAL_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1500
        )
        
        content = response.choices[0].message.content
        print(f"✅ 평가 완료: {len(content)} bytes")
        
        return content
    
    def _parse_eval_json(self, content: str) -> Dict:
        """평가 JSON 파싱 및 검증"""
        try:
            # 정상적인 JSON 파싱 시도
            obj = json.loads(content)
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 정규식으로 추출
            print("⚠️ JSON 파싱 실패, 정규식으로 재시도...")
            match = re.search(r'\{[\s\S]*\}', content)
            if not match:
                raise ValueError("평가 결과 JSON 파싱 실패")
            obj = json.loads(match.group(0))
        
        # 필수 필드 검증
        required_score_keys = {"knowledge", "skill", "attitude", "total"}
        if "score" not in obj or not all(key in obj["score"] for key in required_score_keys):
            raise ValueError("평가 JSON 스키마 검증 실패: score 필드가 올바르지 않습니다")
        
        # 점수 범위 검증
        score = obj["score"]
        if not (0 <= score.get("knowledge", {}).get("point", 0) <= 40):
            raise ValueError("지식 점수는 0~40 사이여야 합니다")
        if not (0 <= score.get("skill", {}).get("point", 0) <= 30):
            raise ValueError("기술 점수는 0~30 사이여야 합니다")
        if not (0 <= score.get("attitude", {}).get("point", 0) <= 30):
            raise ValueError("태도 점수는 0~30 사이여야 합니다")
        
        print("✅ JSON 파싱 및 검증 완료")
        return obj
    
    def _save_evaluation(self, session: RAGSimulationSession, parsed: Dict, raw_json: str) -> RAGSimulationEvaluation:
        """평가 결과 DB 저장"""
        score = parsed.get("score", {})
        detail = parsed.get("detail_feedback", {})
        
        eval_record = RAGSimulationEvaluation(
            session_id=session.id,
            user_id=session.user_id,
            knowledge_point=int(score["knowledge"].get("point", 0)),
            skill_point=int(score["skill"].get("point", 0)),
            attitude_point=int(score["attitude"].get("point", 0)),
            total_point=int(score.get("total", 0)),
            strengths=json.dumps(detail.get("strengths", []), ensure_ascii=False),
            improvements=json.dumps(detail.get("improvements", []), ensure_ascii=False),
            recommended_training=json.dumps(detail.get("recommended_training", []), ensure_ascii=False),
            raw_json=raw_json
        )
        
        self.session.add(eval_record)
        self.session.commit()
        self.session.refresh(eval_record)
        
        print(f"✅ 평가 결과 저장 완료 (ID: {eval_record.id})")
        return eval_record
    
    def _mark_session_completed(self, session: RAGSimulationSession):
        """세션 완료 처리"""
        from datetime import datetime
        
        session.is_completed = True
        session.ended_at = datetime.utcnow()
        
        if session.started_at and session.ended_at:
            duration = (session.ended_at - session.started_at).total_seconds()
            session.duration_seconds = int(duration)
        
        self.session.add(session)
        self.session.commit()
        
        print("✅ 세션 완료 처리 완료")

