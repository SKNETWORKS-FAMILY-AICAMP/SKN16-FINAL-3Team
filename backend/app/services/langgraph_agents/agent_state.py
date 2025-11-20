"""
LangGraph Agent State 정의
모든 에이전트가 공유하는 상태 구조
"""
from typing import TypedDict, List, Dict, Optional, Any, Annotated
from typing_extensions import TypedDict as ExtTypedDict
from langgraph.graph import add_messages
from datetime import datetime


class AgentState(TypedDict):
    """
    멀티 에이전트 시스템의 공유 상태
    LangGraph가 에이전트 간 데이터를 전달하는 데 사용
    """
    # 메시지 히스토리 (LangGraph 표준)
    messages: Annotated[List[Dict], add_messages]
    
    # 사용자 입력
    user_input: Optional[str]
    user_input_raw: Optional[str]
    audio_data: Optional[bytes]
    
    # 페르소나 & 시츄에이션
    persona: Optional[Dict]
    situation: Optional[Dict]
    
    # 정규화된 텍스트
    normalized_text: Optional[str]
    corrections: Optional[List[tuple]]
    
    # 주제 적합성
    is_ontopic: Optional[bool]
    offtopic_category: Optional[str]
    pivot_response: Optional[str]
    
    # RAG 검색 결과
    rag_results: Optional[List[Dict]]
    rag_answer: Optional[str]
    rag_sources: Optional[List[str]]
    
    # 상품 지식
    product_matches: Optional[List[Dict]]
    product_details: Optional[Dict]
    
    # LLM 응답
    llm_messages: Optional[List[Dict]]
    customer_response: Optional[str]
    customer_emotion: Optional[str]
    
    # 음성 생성
    voice_params: Optional[Dict]
    ssml: Optional[str]
    audio_output: Optional[bytes]
    
    # 평가 & 피드백
    evaluation: Optional[Dict]
    feedback: Optional[str]
    scores: Optional[Dict]
    improvement_tips: Optional[List[str]]
    
    # 시뮬레이션 메타데이터
    session_id: Optional[str]
    session_type: Optional[str]
    turn_count: Optional[int]
    current_turn_index: Optional[int]
    
    # 워크플로우 제어
    next_step: Optional[str]
    should_end: bool
    error: Optional[str]
    
    # 실행 추적 (LangSmith)
    trace_id: Optional[str]
    agent_calls: Optional[List[Dict]]
    
    # 기타
    metadata: Optional[Dict]


class SimulationState(AgentState):
    """시뮬레이션 전용 상태 (AgentState 확장)"""
    # 시뮬레이션 특화 필드
    transcript: Optional[str]
    turns: Optional[List[Dict]]
    rag_evaluations: Optional[List[Dict]]
    
    # 고객 응답 생성 관련
    achieved_goals: Optional[List[int]]
    stuck_counter: Optional[int]
    last_employee_questions: Optional[List[str]]


class RAGState(AgentState):
    """RAG 쿼리 전용 상태"""
    # RAG 특화
    query: str
    chat_history: Optional[List[Dict]]
    user_id: Optional[int]
    doc_type: Optional[str]
    confidence: Optional[float]


class ExamState(AgentState):
    """시험 평가 전용 상태"""
    # 시험 특화
    exam_data: Optional[Dict]
    answers: Optional[Dict]
    question_scores: Optional[List[Dict]]
    analysis: Optional[str]
    recommendations: Optional[List[str]]


def create_initial_state(**kwargs) -> AgentState:
    """
    초기 상태 생성 헬퍼 함수
    
    Usage:
        state = create_initial_state(
            user_input="안녕하세요",
            persona={...},
            situation={...}
        )
    """
    return AgentState(
        messages=[],
        user_input=kwargs.get('user_input'),
        user_input_raw=kwargs.get('user_input_raw'),
        audio_data=kwargs.get('audio_data'),
        persona=kwargs.get('persona'),
        situation=kwargs.get('situation'),
        normalized_text=None,
        corrections=None,
        is_ontopic=None,
        offtopic_category=None,
        pivot_response=None,
        rag_results=None,
        rag_answer=None,
        rag_sources=None,
        product_matches=None,
        product_details=None,
        llm_messages=None,
        customer_response=None,
        customer_emotion=None,
        voice_params=None,
        ssml=None,
        audio_output=None,
        evaluation=None,
        feedback=None,
        scores=None,
        improvement_tips=None,
        session_id=kwargs.get('session_id'),
        session_type=kwargs.get('session_type', 'simulation'),
        turn_count=0,
        current_turn_index=0,
        next_step=None,
        should_end=False,
        error=None,
        trace_id=None,
        agent_calls=[],
        metadata=kwargs.get('metadata', {})
    )

