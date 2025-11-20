"""
LangGraph 노드 함수들
각 노드는 AgentState를 받아 수정된 state를 반환
"""
from typing import Dict, Any
from datetime import datetime
import traceback

from app.services.langgraph_agents.agent_state import AgentState
from langsmith import traceable


@traceable(name="banking_normalizer")
def banking_normalizer_node(state: AgentState) -> AgentState:
    """
    은행 용어 정규화 노드
    """
    try:
        from app.services.banking_normalizer import normalize_text
        
        user_input = state.get("user_input") or state.get("user_input_raw", "")
        
        if not user_input:
            return state
        
        # 정규화 실행
        normalized, corrections = normalize_text(user_input)
        
        # 상태 업데이트
        state["normalized_text"] = normalized
        state["corrections"] = corrections
        
        # 메시지 추가
        state["messages"].append({
            "role": "system",
            "content": f"[Normalizer] 입력 정규화 완료: {len(corrections)}개 수정",
            "timestamp": datetime.now().isoformat()
        })
        
        # agent_calls 추적
        if "agent_calls" not in state:
            state["agent_calls"] = []
        state["agent_calls"].append({
            "agent": "banking_normalizer",
            "timestamp": datetime.now().isoformat(),
            "input": user_input[:100],
            "output": normalized[:100]
        })
        
        return state
    
    except Exception as e:
        state["error"] = f"Normalizer error: {str(e)}"
        state["should_end"] = True
        return state


@traceable(name="offtopic_detector")
def offtopic_detector_node(state: AgentState) -> AgentState:
    """
    주제 이탈 감지 노드
    """
    try:
        from app.services.offtopic_detector import is_on_topic, generate_pivot_response
        
        text = state.get("normalized_text") or state.get("user_input", "")
        
        if not text:
            state["is_ontopic"] = True
            return state
        
        # 주제 적합성 체크
        is_ontopic = is_on_topic(text)
        
        state["is_ontopic"] = is_ontopic
        
        if not is_ontopic:
            # 피벗 응답 생성
            pivot = generate_pivot_response(text)
            state["pivot_response"] = pivot
            state["offtopic_category"] = "offtopic"
            
            state["messages"].append({
                "role": "assistant",
                "content": pivot,
                "timestamp": datetime.now().isoformat()
            })
        
        state["agent_calls"].append({
            "agent": "offtopic_detector",
            "timestamp": datetime.now().isoformat(),
            "is_ontopic": is_ontopic
        })
        
        return state
    
    except Exception as e:
        state["error"] = f"Offtopic detector error: {str(e)}"
        state["is_ontopic"] = True  # 에러 시 계속 진행
        return state


@traceable(name="rag_service")
def rag_service_node(state: AgentState) -> AgentState:
    """
    RAG 검색 노드
    """
    try:
        # TODO: 실제 RAG 서비스 연동
        # 현재는 더미 데이터
        query = state.get("normalized_text") or state.get("user_input", "")
        
        # 더미 RAG 결과
        state["rag_results"] = [
            {
                "doc_id": "doc_001",
                "title": "예금 상품 안내",
                "snippet": "정기예금은 일정 기간 동안 자금을 예치하는 상품입니다.",
                "score": 0.85
            }
        ]
        state["rag_answer"] = "정기예금은 일정 기간 동안 자금을 예치하여 이자를 받는 상품입니다."
        state["rag_sources"] = ["doc_001"]
        
        state["messages"].append({
            "role": "system",
            "content": f"[RAG] 검색 완료: {len(state['rag_results'])}개 문서",
            "timestamp": datetime.now().isoformat()
        })
        
        state["agent_calls"].append({
            "agent": "rag_service",
            "timestamp": datetime.now().isoformat(),
            "query": query[:100],
            "results_count": len(state["rag_results"])
        })
        
        return state
    
    except Exception as e:
        state["error"] = f"RAG service error: {str(e)}"
        state["rag_results"] = []
        return state


@traceable(name="product_knowledge")
def product_knowledge_node(state: AgentState) -> AgentState:
    """
    상품 지식 검색 노드
    """
    try:
        # TODO: 실제 상품 검색 연동
        query = state.get("normalized_text") or state.get("user_input", "")
        
        # 더미 상품 데이터
        state["product_matches"] = [
            {
                "product_id": "P001",
                "product_name": "KB 정기예금",
                "category": "예금",
                "interest_rate": 3.5
            }
        ]
        state["product_details"] = state["product_matches"][0] if state["product_matches"] else None
        
        state["agent_calls"].append({
            "agent": "product_knowledge",
            "timestamp": datetime.now().isoformat(),
            "products_found": len(state["product_matches"])
        })
        
        return state
    
    except Exception as e:
        state["error"] = f"Product knowledge error: {str(e)}"
        state["product_matches"] = []
        return state


@traceable(name="prompt_orchestrator")
def prompt_orchestrator_node(state: AgentState) -> AgentState:
    """
    프롬프트 오케스트레이터 노드
    """
    try:
        from app.services.promptOrchestrator import compose_llm_messages
        
        persona = state.get("persona", {})
        situation = state.get("situation", {})
        user_text = state.get("normalized_text") or state.get("user_input", "")
        rag_hits = state.get("rag_results", [])
        
        # 히스토리 변환
        history = []
        for msg in state.get("messages", []):
            if msg.get("role") in ["user", "assistant"]:
                history.append({
                    "role": msg["role"],
                    "text": msg.get("content", "")
                })
        
        # LLM 메시지 구성
        llm_messages = compose_llm_messages(
            persona=persona,
            situation=situation,
            user_text=user_text,
            rag_hits=rag_hits,
            history=history[-10:]  # 최근 10턴
        )
        
        state["llm_messages"] = llm_messages
        
        state["messages"].append({
            "role": "system",
            "content": f"[Orchestrator] LLM 메시지 구성 완료",
            "timestamp": datetime.now().isoformat()
        })
        
        state["agent_calls"].append({
            "agent": "prompt_orchestrator",
            "timestamp": datetime.now().isoformat(),
            "message_count": len(llm_messages)
        })
        
        return state
    
    except Exception as e:
        state["error"] = f"Orchestrator error: {str(e)}"
        traceback.print_exc()
        return state


@traceable(name="rag_simulation")
def rag_simulation_node(state: AgentState) -> AgentState:
    """
    RAG 시뮬레이션 노드 (고객 응답 생성)
    """
    try:
        import openai
        import os
        
        llm_messages = state.get("llm_messages")
        
        if not llm_messages:
            state["customer_response"] = "죄송합니다. 응답을 생성할 수 없습니다."
            return state
        
        # OpenAI API 호출
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            state["customer_response"] = "[데모] 고객 응답입니다."
            return state
        
        client = openai.OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=llm_messages,
            temperature=0.8,
            max_tokens=300
        )
        
        customer_response = response.choices[0].message.content
        
        # JSON 파싱 시도
        try:
            import json
            from app.services.promptOrchestrator import parse_llm_response
            parsed = parse_llm_response(customer_response)
            state["customer_response"] = parsed.get("script", customer_response)
            state["customer_emotion"] = parsed.get("customer_emotion", "긍정형")
        except:
            state["customer_response"] = customer_response
        
        # 메시지 추가
        state["messages"].append({
            "role": "assistant",
            "content": state["customer_response"],
            "timestamp": datetime.now().isoformat()
        })
        
        # 턴 카운트 증가
        state["turn_count"] = state.get("turn_count", 0) + 1
        
        state["agent_calls"].append({
            "agent": "rag_simulation",
            "timestamp": datetime.now().isoformat(),
            "turn": state["turn_count"],
            "response_length": len(state["customer_response"])
        })
        
        return state
    
    except Exception as e:
        state["error"] = f"Simulation error: {str(e)}"
        traceback.print_exc()
        state["customer_response"] = "죄송합니다. 응답 생성 중 오류가 발생했습니다."
        return state


@traceable(name="persona_voice")
def persona_voice_node(state: AgentState) -> AgentState:
    """
    페르소나 음성 생성 노드
    """
    try:
        from app.services.persona_voice import get_voice_params, build_ssml
        
        persona = state.get("persona", {})
        script = state.get("customer_response", "")
        age_group = persona.get("age_group", "30s")
        
        # 음성 파라미터 생성
        voice_params = get_voice_params(persona)
        ssml = build_ssml(script, age_group)
        
        state["voice_params"] = voice_params
        state["ssml"] = ssml
        
        # TODO: 실제 TTS 연동
        state["audio_output"] = None
        
        state["agent_calls"].append({
            "agent": "persona_voice",
            "timestamp": datetime.now().isoformat(),
            "voice_model": voice_params.get("voice_id")
        })
        
        return state
    
    except Exception as e:
        state["error"] = f"Voice generation error: {str(e)}"
        return state


@traceable(name="feedback_service")
def feedback_service_node(state: AgentState) -> AgentState:
    """
    피드백 생성 노드
    """
    try:
        # 간단한 평가 생성
        turn_count = state.get("turn_count", 0)
        messages = state.get("messages", [])
        
        evaluation = {
            "total_turns": turn_count,
            "message_count": len(messages),
            "completed": not state.get("error")
        }
        
        feedback = f"총 {turn_count}턴의 대화를 진행했습니다."
        
        scores = {
            "knowledge": 85,
            "skill": 80,
            "attitude": 90
        }
        
        state["evaluation"] = evaluation
        state["feedback"] = feedback
        state["scores"] = scores
        state["improvement_tips"] = ["더 구체적인 질문을 해보세요."]
        
        state["agent_calls"].append({
            "agent": "feedback_service",
            "timestamp": datetime.now().isoformat(),
            "overall_score": sum(scores.values()) / len(scores)
        })
        
        state["should_end"] = True
        
        return state
    
    except Exception as e:
        state["error"] = f"Feedback error: {str(e)}"
        state["should_end"] = True
        return state


@traceable(name="exam_service")
def exam_service_node(state: AgentState) -> AgentState:
    """
    시험 채점 노드
    """
    try:
        # TODO: 실제 시험 채점 로직
        exam_data = state.get("exam_data", {})
        answers = state.get("answers", {})
        
        # 더미 채점
        state["question_scores"] = []
        state["scores"] = {"overall": 85}
        state["analysis"] = "전반적으로 양호한 성적입니다."
        state["recommendations"] = ["상품 지식을 더 강화하세요."]
        
        state["agent_calls"].append({
            "agent": "exam_service",
            "timestamp": datetime.now().isoformat(),
            "score": 85
        })
        
        return state
    
    except Exception as e:
        state["error"] = f"Exam service error: {str(e)}"
        return state


@traceable(name="error_handler")
def error_handler_node(state: AgentState) -> AgentState:
    """
    에러 처리 노드
    """
    error = state.get("error", "Unknown error")
    
    state["messages"].append({
        "role": "system",
        "content": f"[Error] {error}",
        "timestamp": datetime.now().isoformat()
    })
    
    state["should_end"] = True
    
    # 피벗 응답이 있으면 사용
    if state.get("pivot_response"):
        state["customer_response"] = state["pivot_response"]
    
    return state

