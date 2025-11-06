"""
고도화된 시뮬레이션 서비스
STT/LLM/TTS 기반 음성 시뮬레이션 및 AI 기반 고객 페르소나 시스템
"""
import json
import os
import tempfile
import base64
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from sqlmodel import Session, select
import openai
import requests
from io import BytesIO

from app.models.advanced_simulation import (
    CustomerPersona, SimulationSituation, VoiceSimulationSession, 
    VoiceInteraction, SimulationAnalytics
)
from app.models.user import User


class AdvancedSimulationService:
    """고도화된 시뮬레이션 서비스"""
    
    def __init__(self, session: Session):
        self.session = session
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def get_customer_personas(self, filters: Optional[Dict] = None) -> List[Dict]:
        """고객 페르소나 목록 조회"""
        query = select(CustomerPersona).where(CustomerPersona.is_active == True)
        
        if filters:
            if filters.get("age_group"):
                query = query.where(CustomerPersona.age_group == filters["age_group"])
            if filters.get("occupation"):
                query = query.where(CustomerPersona.occupation == filters["occupation"])
            if filters.get("customer_type"):
                query = query.where(CustomerPersona.customer_type == filters["customer_type"])
        
        personas = self.session.exec(query.order_by(CustomerPersona.created_at.desc())).all()
        
        result = []
        for persona in personas:
            result.append({
                "id": persona.id,
                "name": persona.name,
                "age_group": persona.age_group,
                "occupation": persona.occupation,
                "financial_literacy": persona.financial_literacy,
                "customer_type": persona.customer_type,
                "personality_traits": json.loads(persona.personality_traits),
                "communication_style": json.loads(persona.communication_style),
                "voice_characteristics": json.loads(persona.voice_characteristics)
            })
        
        return result
    
    def get_simulation_situations(self, filters: Optional[Dict] = None) -> List[Dict]:
        """시뮬레이션 상황 목록 조회"""
        query = select(SimulationSituation).where(SimulationSituation.is_active == True)
        
        if filters:
            if filters.get("business_category"):
                query = query.where(SimulationSituation.business_category == filters["business_category"])
            if filters.get("difficulty_level"):
                query = query.where(SimulationSituation.difficulty_level == filters["difficulty_level"])
        
        situations = self.session.exec(query.order_by(SimulationSituation.created_at.desc())).all()
        
        result = []
        for situation in situations:
            result.append({
                "id": situation.id,
                "title": situation.title,
                "business_category": situation.business_category,
                "situation_type": situation.situation_type,
                "difficulty_level": situation.difficulty_level,
                "situation_context": json.loads(situation.situation_context),
                "expected_outcomes": json.loads(situation.expected_outcomes)
            })
        
        return result
    
    def start_voice_simulation(self, user_id: int, persona_id: int, situation_id: int, 
                             session_name: str) -> Dict:
        """음성 시뮬레이션 시작"""
        # 페르소나와 상황 조회
        persona = self.session.get(CustomerPersona, persona_id)
        situation = self.session.get(SimulationSituation, situation_id)
        
        if not persona or not situation:
            raise ValueError("페르소나 또는 상황을 찾을 수 없습니다.")
        
        # 새로운 세션 생성
        session = VoiceSimulationSession(
            user_id=user_id,
            persona_id=persona_id,
            situation_id=situation_id,
            session_name=session_name,
            status="in_progress"
        )
        
        self.session.add(session)
        self.session.commit()
        self.session.refresh(session)
        
        # 초기 고객 메시지 생성
        initial_message = self._generate_initial_customer_message(persona, situation)
        
        return {
            "session_id": session.id,
            "persona": {
                "id": persona.id,
                "name": persona.name,
                "age_group": persona.age_group,
                "customer_type": persona.customer_type,
                "voice_characteristics": json.loads(persona.voice_characteristics)
            },
            "situation": {
                "id": situation.id,
                "title": situation.title,
                "business_category": situation.business_category,
                "difficulty_level": situation.difficulty_level
            },
            "initial_message": initial_message,
            "session_name": session_name
        }
    
    def process_voice_interaction(self, session_id: int, audio_data: bytes, 
                                interaction_type: str = "user_speech") -> Dict:
        """음성 상호작용 처리"""
        session = self.session.get(VoiceSimulationSession, session_id)
        if not session or session.status != "in_progress":
            raise ValueError("진행 중인 세션을 찾을 수 없습니다.")
        
        # STT: 음성을 텍스트로 변환
        transcribed_text = self._speech_to_text(audio_data)
        
        # 대화 플로우 처리
        if interaction_type == "user_speech":
            # 사용자 음성을 고객 페르소나가 이해하고 응답 생성
            customer_response = self._generate_customer_response(
                session, transcribed_text
            )
            
            # TTS: 고객 응답을 음성으로 변환
            customer_audio = self._text_to_speech(customer_response["text"], session.persona)
            
            # 상호작용 기록 저장
            interaction = VoiceInteraction(
                session_id=session_id,
                interaction_type="user_speech",
                sequence_number=self._get_next_sequence_number(session_id),
                transcribed_text=transcribed_text,
                ai_response_text=customer_response["text"],
                ai_response_audio=customer_audio,
                feedback=customer_response.get("feedback")
            )
            
            self.session.add(interaction)
            self.session.commit()
            
            return {
                "transcribed_text": transcribed_text,
                "customer_response": customer_response["text"],
                "customer_audio": customer_audio,
                "feedback": customer_response.get("feedback"),
                "conversation_phase": customer_response.get("phase"),
                "session_score": self._calculate_session_score(session_id)
            }
        
        return {"error": "지원하지 않는 상호작용 타입입니다."}
    
    def _speech_to_text(self, audio_data: bytes) -> str:
        """음성을 텍스트로 변환 (STT)"""
        try:
            # OpenAI Whisper API 사용
            audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            audio_file.write(audio_data)
            audio_file.close()
            
            with open(audio_file.name, "rb") as f:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="ko"  # 한국어 설정
                )
            
            os.unlink(audio_file.name)
            return transcript.text
            
        except Exception as e:
            print(f"STT 오류: {e}")
            return "음성 인식에 실패했습니다."
    
    def _text_to_speech(self, text: str, persona: CustomerPersona) -> str:
        """텍스트를 음성으로 변환 (TTS)"""
        try:
            voice_characteristics = json.loads(persona.voice_characteristics)
            
            # OpenAI TTS API 사용
            response = self.openai_client.audio.speech.create(
                model="tts-1",
                voice=voice_characteristics.get("voice", "alloy"),
                speed=voice_characteristics.get("speed", 1.0),
                input=text
            )
            
            # 음성 파일을 base64로 인코딩하여 반환
            audio_data = response.content
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            return f"data:audio/mpeg;base64,{audio_base64}"
            
        except Exception as e:
            print(f"TTS 오류: {e}")
            return ""
    
    def _generate_initial_customer_message(self, persona: CustomerPersona, 
                                         situation: SimulationSituation) -> Dict:
        """초기 고객 메시지 생성"""
        situation_context = json.loads(situation.situation_context)
        personality_traits = json.loads(persona.personality_traits)
        
        prompt = f"""
        당신은 {persona.name}이라는 고객입니다.
        
        고객 정보:
        - 연령대: {persona.age_group}
        - 직업: {persona.occupation}
        - 금융 이해도: {persona.financial_literacy}
        - 고객 타입: {persona.customer_type}
        - 성격 특성: {personality_traits}
        
        상황:
        {situation_context.get('description', '')}
        
        이 상황에서 고객이 은행 직원에게 처음으로 말할 내용을 생성해주세요.
        고객의 성격과 상황에 맞는 자연스러운 대화를 만들어주세요.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200
            )
            
            return {
                "text": response.choices[0].message.content,
                "phase": "initial"
            }
            
        except Exception as e:
            print(f"초기 메시지 생성 오류: {e}")
            return {
                "text": "안녕하세요, 은행 업무에 대해 문의드리고 싶습니다.",
                "phase": "initial"
            }
    
    def _generate_customer_response(self, session: VoiceSimulationSession, 
                                  user_message: str) -> Dict:
        """고객 응답 생성"""
        persona = session.persona
        situation = session.situation
        
        personality_traits = json.loads(persona.personality_traits)
        communication_style = json.loads(persona.communication_style)
        conversation_flow = json.loads(situation.conversation_flow)
        
        prompt = f"""
        당신은 {persona.name}이라는 고객입니다.
        
        고객 정보:
        - 연령대: {persona.age_group}
        - 직업: {persona.occupation}
        - 금융 이해도: {persona.financial_literacy}
        - 고객 타입: {persona.customer_type}
        - 성격 특성: {personality_traits}
        - 소통 스타일: {communication_style}
        
        상황: {situation.title}
        업무 카테고리: {situation.business_category}
        
        은행 직원이 "{user_message}"라고 말했습니다.
        
        이 상황에서 고객이 자연스럽게 응답할 내용을 생성해주세요.
        고객의 성격과 상황에 맞는 반응을 보여주세요.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300
            )
            
            # 응답 평가
            feedback = self._evaluate_user_response(user_message, persona, situation)
            
            return {
                "text": response.choices[0].message.content,
                "feedback": feedback,
                "phase": self._determine_conversation_phase(session)
            }
            
        except Exception as e:
            print(f"고객 응답 생성 오류: {e}")
            return {
                "text": "네, 이해했습니다.",
                "feedback": "응답 생성에 실패했습니다.",
                "phase": "ongoing"
            }
    
    def _evaluate_user_response(self, user_message: str, persona: CustomerPersona, 
                              situation: SimulationSituation) -> str:
        """사용자 응답 평가"""
        evaluation_criteria = json.loads(situation.evaluation_criteria)
        
        prompt = f"""
        은행 직원의 응답: "{user_message}"
        
        고객 정보:
        - 고객 타입: {persona.customer_type}
        - 금융 이해도: {persona.financial_literacy}
        
        평가 기준:
        {evaluation_criteria}
        
        이 응답이 고객에게 적절했는지 평가하고, 개선점이 있다면 피드백을 제공해주세요.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"응답 평가 오류: {e}")
            return "응답 평가를 완료할 수 없습니다."
    
    def _get_next_sequence_number(self, session_id: int) -> int:
        """다음 시퀀스 번호 조회"""
        last_interaction = self.session.exec(
            select(VoiceInteraction)
            .where(VoiceInteraction.session_id == session_id)
            .order_by(VoiceInteraction.sequence_number.desc())
        ).first()
        
        return (last_interaction.sequence_number + 1) if last_interaction else 1
    
    def _calculate_session_score(self, session_id: int) -> float:
        """세션 점수 계산"""
        interactions = self.session.exec(
            select(VoiceInteraction)
            .where(VoiceInteraction.session_id == session_id)
        ).all()
        
        if not interactions:
            return 0.0
        
        total_score = sum(interaction.score for interaction in interactions)
        max_score = sum(interaction.max_score for interaction in interactions)
        
        return (total_score / max_score * 100) if max_score > 0 else 0.0
    
    def _determine_conversation_phase(self, session: VoiceSimulationSession) -> str:
        """대화 단계 결정"""
        interactions = self.session.exec(
            select(VoiceInteraction)
            .where(VoiceInteraction.session_id == session.id)
            .order_by(VoiceInteraction.sequence_number)
        ).all()
        
        interaction_count = len(interactions)
        
        if interaction_count == 0:
            return "initial"
        elif interaction_count < 5:
            return "ongoing"
        elif interaction_count < 10:
            return "developing"
        else:
            return "concluding"
    
    def complete_simulation(self, session_id: int) -> Dict:
        """시뮬레이션 완료 처리"""
        session = self.session.get(VoiceSimulationSession, session_id)
        if not session:
            raise ValueError("세션을 찾을 수 없습니다.")
        
        # 최종 점수 계산
        final_score = self._calculate_session_score(session_id)
        grade = self._calculate_grade(final_score)
        
        # 세션 완료 처리
        session.completed_at = datetime.utcnow()
        session.duration_seconds = int((session.completed_at - session.started_at).total_seconds())
        session.total_score = final_score
        session.grade = grade
        session.status = "completed"
        
        # 최종 피드백 생성
        final_feedback = self._generate_final_feedback(session)
        session.feedback = final_feedback
        
        # 대화 기록 저장
        conversation_log = self._generate_conversation_log(session_id)
        session.conversation_log = conversation_log
        
        self.session.add(session)
        self.session.commit()
        
        return {
            "session_id": session_id,
            "total_score": final_score,
            "grade": grade,
            "duration_seconds": session.duration_seconds,
            "feedback": final_feedback,
            "conversation_log": conversation_log
        }
    
    def _calculate_grade(self, score: float) -> str:
        """등급 계산"""
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "B+"
        elif score >= 75:
            return "B"
        elif score >= 70:
            return "C+"
        elif score >= 65:
            return "C"
        else:
            return "D"
    
    def _generate_final_feedback(self, session: VoiceSimulationSession) -> str:
        """최종 피드백 생성"""
        interactions = self.session.exec(
            select(VoiceInteraction)
            .where(VoiceInteraction.session_id == session.id)
        ).all()
        
        if not interactions:
            return "시뮬레이션이 완료되지 않았습니다."
        
        # 피드백 요약 생성
        feedbacks = [interaction.feedback for interaction in interactions if interaction.feedback]
        
        if not feedbacks:
            return "피드백을 생성할 수 없습니다."
        
        return " ".join(feedbacks[:3])  # 처음 3개 피드백만 사용
    
    def _generate_conversation_log(self, session_id: int) -> str:
        """대화 기록 생성"""
        interactions = self.session.exec(
            select(VoiceInteraction)
            .where(VoiceInteraction.session_id == session_id)
            .order_by(VoiceInteraction.sequence_number)
        ).all()
        
        log_entries = []
        for interaction in interactions:
            log_entry = {
                "sequence": interaction.sequence_number,
                "type": interaction.interaction_type,
                "transcribed_text": interaction.transcribed_text,
                "ai_response": interaction.ai_response_text,
                "score": interaction.score,
                "feedback": interaction.feedback
            }
            log_entries.append(log_entry)
        
        return json.dumps(log_entries, ensure_ascii=False)
    
    def get_simulation_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """시뮬레이션 기록 조회"""
        sessions = self.session.exec(
            select(VoiceSimulationSession)
            .where(VoiceSimulationSession.user_id == user_id)
            .order_by(VoiceSimulationSession.created_at.desc())
            .limit(limit)
        ).all()
        
        result = []
        for session in sessions:
            result.append({
                "id": session.id,
                "session_name": session.session_name,
                "persona_name": session.persona.name,
                "situation_title": session.situation.title,
                "total_score": session.total_score,
                "grade": session.grade,
                "duration_seconds": session.duration_seconds,
                "status": session.status,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None
            })
        
        return result
