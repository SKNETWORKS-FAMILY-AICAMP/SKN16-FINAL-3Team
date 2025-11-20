"""
LangGraph 워크플로우 정의
실제 실행 가능한 멀티 에이전트 그래프
"""
import os
from typing import Dict, List, Literal
try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    # LangGraph가 설치되지 않은 경우 fallback
    StateGraph = None
    END = None
    MemorySaver = None

try:
    from langsmith import traceable
except ImportError:
    # LangSmith가 설치되지 않은 경우 fallback
    def traceable(name=None):
        def decorator(func):
            return func
        return decorator

from app.services.langgraph_agents.agent_state import AgentState, SimulationState
from app.services.langgraph_agents.nodes import (
    banking_normalizer_node,
    offtopic_detector_node,
    rag_service_node,
    product_knowledge_node,
    prompt_orchestrator_node,
    rag_simulation_node,
    persona_voice_node,
    feedback_service_node,
    error_handler_node
)


def should_continue_simulation(state: AgentState) -> Literal["continue", "end"]:
    """
    시뮬레이션 계속 진행 여부 결정 (조건부 라우팅)
    """
    if state.get("should_end"):
        return "end"
    
    if state.get("error"):
        return "end"
    
    # 10턴 이상이면 종료
    if state.get("turn_count", 0) >= 10:
        return "end"
    
    return "continue"


def route_by_topic(state: AgentState) -> Literal["rag", "offtopic", "continue"]:
    """
    주제 적합성에 따른 라우팅
    """
    if not state.get("is_ontopic"):
        return "offtopic"
    
    # RAG가 필요한 경우
    if state.get("user_input"):
        return "rag"
    
    return "continue"


def create_simulation_workflow() -> StateGraph:
    """
    시뮬레이션 워크플로우 생성
    
    워크플로우 구조:
    START → Normalizer → Offtopic Detector → [조건부]
                                           ↓
                        RAG Service ← Product Knowledge
                                           ↓
                        Prompt Orchestrator
                                           ↓
                        RAG Simulation → Persona Voice
                                           ↓
                        Feedback Service → END
    """
    # StateGraph 생성
    workflow = StateGraph(AgentState)
    
    # 노드 추가 (실제 함수 연결)
    workflow.add_node("normalizer", banking_normalizer_node)
    workflow.add_node("offtopic_detector", offtopic_detector_node)
    workflow.add_node("rag_service", rag_service_node)
    workflow.add_node("product_knowledge", product_knowledge_node)
    workflow.add_node("orchestrator", prompt_orchestrator_node)
    workflow.add_node("simulation", rag_simulation_node)
    workflow.add_node("voice", persona_voice_node)
    workflow.add_node("feedback", feedback_service_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # 엣지 추가 (데이터 흐름)
    workflow.set_entry_point("normalizer")
    
    # Normalizer → Offtopic Detector
    workflow.add_edge("normalizer", "offtopic_detector")
    
    # Offtopic Detector → [조건부 라우팅]
    workflow.add_conditional_edges(
        "offtopic_detector",
        route_by_topic,
        {
            "rag": "rag_service",
            "offtopic": "error_handler",
            "continue": "orchestrator"
        }
    )
    
    # RAG Service → Product Knowledge → Orchestrator
    workflow.add_edge("rag_service", "product_knowledge")
    workflow.add_edge("product_knowledge", "orchestrator")
    
    # Orchestrator → Simulation
    workflow.add_edge("orchestrator", "simulation")
    
    # Simulation → [조건부 계속/종료]
    workflow.add_conditional_edges(
        "simulation",
        should_continue_simulation,
        {
            "continue": "voice",
            "end": "feedback"
        }
    )
    
    # Voice → Feedback
    workflow.add_edge("voice", "feedback")
    
    # Feedback → END
    workflow.add_edge("feedback", END)
    
    # Error Handler → END
    workflow.add_edge("error_handler", END)
    
    return workflow


def create_rag_workflow() -> StateGraph:
    """
    RAG 쿼리 워크플로우 생성
    
    더 간단한 워크플로우:
    START → Normalizer → RAG Service → END
    """
    workflow = StateGraph(AgentState)
    
    workflow.add_node("normalizer", banking_normalizer_node)
    workflow.add_node("rag_service", rag_service_node)
    
    workflow.set_entry_point("normalizer")
    workflow.add_edge("normalizer", "rag_service")
    workflow.add_edge("rag_service", END)
    
    return workflow


def create_exam_workflow() -> StateGraph:
    """
    시험 평가 워크플로우
    
    START → Product Knowledge → Exam Service → Feedback → END
    """
    from app.services.langgraph_agents.nodes import exam_service_node
    
    workflow = StateGraph(AgentState)
    
    workflow.add_node("product_knowledge", product_knowledge_node)
    workflow.add_node("exam", exam_service_node)
    workflow.add_node("feedback", feedback_service_node)
    
    workflow.set_entry_point("product_knowledge")
    workflow.add_edge("product_knowledge", "exam")
    workflow.add_edge("exam", "feedback")
    workflow.add_edge("feedback", END)
    
    return workflow


# 체크포인트 메모리 (상태 저장)
memory = MemorySaver()


def compile_workflow(workflow: StateGraph, checkpointer=None):
    """
    워크플로우 컴파일
    
    Args:
        workflow: StateGraph 인스턴스
        checkpointer: 체크포인트 저장소 (선택)
    
    Returns:
        컴파일된 실행 가능한 앱
    """
    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)
    return workflow.compile()


# 전역 워크플로우 인스턴스
_simulation_app = None
_rag_app = None
_exam_app = None


def get_simulation_app():
    """시뮬레이션 워크플로우 앱 가져오기 (싱글톤)"""
    global _simulation_app
    if _simulation_app is None:
        workflow = create_simulation_workflow()
        _simulation_app = compile_workflow(workflow, checkpointer=memory)
    return _simulation_app


def get_rag_app():
    """RAG 워크플로우 앱 가져오기"""
    global _rag_app
    if _rag_app is None:
        workflow = create_rag_workflow()
        _rag_app = compile_workflow(workflow)
    return _rag_app


def get_exam_app():
    """시험 워크플로우 앱 가져오기"""
    global _exam_app
    if _exam_app is None:
        workflow = create_exam_workflow()
        _exam_app = compile_workflow(workflow)
    return _exam_app


@traceable(name="execute_simulation")
def execute_simulation(initial_state: Dict) -> Dict:
    """
    시뮬레이션 워크플로우 실행
    
    Args:
        initial_state: 초기 상태 딕셔너리
    
    Returns:
        최종 상태
    """
    app = get_simulation_app()
    
    # LangSmith 추적을 위한 config
    config = {
        "configurable": {
            "thread_id": initial_state.get("session_id", "default")
        }
    }
    
    # 실행
    final_state = app.invoke(initial_state, config=config)
    return final_state


@traceable(name="execute_rag_query")
def execute_rag_query(query: str, user_id: int = None) -> Dict:
    """
    RAG 쿼리 실행
    
    Args:
        query: 사용자 질문
        user_id: 사용자 ID (선택)
    
    Returns:
        답변 결과
    """
    app = get_rag_app()
    
    initial_state = {
        "messages": [],
        "user_input": query,
        "user_id": user_id,
        "should_end": False
    }
    
    final_state = app.invoke(initial_state)
    return final_state


@traceable(name="execute_exam_grading")
def execute_exam_grading(exam_data: Dict, answers: Dict) -> Dict:
    """
    시험 채점 실행
    
    Args:
        exam_data: 시험 데이터
        answers: 학생 답안
    
    Returns:
        채점 결과
    """
    app = get_exam_app()
    
    initial_state = {
        "messages": [],
        "exam_data": exam_data,
        "answers": answers,
        "should_end": False
    }
    
    final_state = app.invoke(initial_state)
    return final_state


def get_workflow_graph(workflow_type: str = "simulation"):
    """
    워크플로우 그래프 구조 반환 (시각화용)
    
    Args:
        workflow_type: "simulation", "rag", "exam"
    
    Returns:
        그래프 구조 (Mermaid 다이어그램)
    """
    if workflow_type == "simulation":
        app = get_simulation_app()
    elif workflow_type == "rag":
        app = get_rag_app()
    elif workflow_type == "exam":
        app = get_exam_app()
    else:
        raise ValueError(f"Unknown workflow type: {workflow_type}")
    
    # Mermaid 다이어그램 생성
    try:
        from langgraph.graph import START
        graph = app.get_graph()
        mermaid = graph.draw_mermaid()
        return mermaid
    except Exception as e:
        return f"Error generating graph: {str(e)}"

