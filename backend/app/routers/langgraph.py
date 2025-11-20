"""
LangGraph 관련 API 엔드포인트
실제 LangGraph 워크플로우 실행 및 관리
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import Session
from typing import Dict, List, Optional
import os

from app.database import get_session
from app.utils.auth import get_current_user
from app.models.user import User
from app.services.langgraph_agents.graph_definition import (
    get_agent_graph,
    MultiAgentGraph,
    NodeStatus
)
from app.services.langgraph_agents.langsmith_integration import get_langsmith_tracer
# LangGraph 워크플로우는 선택적 import (패키지가 없어도 기존 API는 작동)
try:
    from app.services.langgraph_agents.workflow import (
        get_simulation_app,
        get_rag_app,
        get_exam_app,
        execute_simulation,
        execute_rag_query,
        execute_exam_grading,
        get_workflow_graph
    )
    from app.services.langgraph_agents.agent_state import create_initial_state
    LANGGRAPH_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ LangGraph 워크플로우를 사용할 수 없습니다: {e}")
    LANGGRAPH_AVAILABLE = False

router = APIRouter(prefix="/langgraph", tags=["langgraph"])


@router.get("/graph")
async def get_graph_structure(
    current_user: User = Depends(get_current_user)
):
    """
    LangGraph 전체 구조 조회
    관리자 대시보드에서 사용
    """
    # 관리자 권한 체크
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    graph = get_agent_graph()
    return {
        "success": True,
        "data": graph.to_dict()
    }


@router.get("/nodes")
async def get_all_nodes(
    current_user: User = Depends(get_current_user)
):
    """
    모든 에이전트 노드 조회
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    graph = get_agent_graph()
    nodes = [node.to_dict() for node in graph.nodes.values()]
    
    return {
        "success": True,
        "data": nodes
    }


@router.get("/nodes/{node_id}")
async def get_node_detail(
    node_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    특정 노드의 상세 정보 조회
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    graph = get_agent_graph()
    node = graph.get_node(node_id)
    
    if not node:
        raise HTTPException(status_code=404, detail="노드를 찾을 수 없습니다")
    
    # 입력/출력 엣지 정보 추가
    incoming_edges = graph.get_edges_by_target(node_id)
    outgoing_edges = graph.get_edges_by_source(node_id)
    
    return {
        "success": True,
        "data": {
            "node": node.to_dict(),
            "incoming_edges": [edge.to_dict() for edge in incoming_edges],
            "outgoing_edges": [edge.to_dict() for edge in outgoing_edges],
            "dependencies": node.dependencies
        }
    }


@router.get("/edges")
async def get_all_edges(
    current_user: User = Depends(get_current_user)
):
    """
    모든 엣지 조회
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    graph = get_agent_graph()
    
    return {
        "success": True,
        "data": [edge.to_dict() for edge in graph.edges]
    }


@router.get("/execution-order")
async def get_execution_order(
    current_user: User = Depends(get_current_user)
):
    """
    에이전트 실행 순서 조회 (토폴로지 정렬)
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    graph = get_agent_graph()
    order = graph.get_execution_order()
    
    return {
        "success": True,
        "data": {
            "execution_order": order,
            "total_nodes": len(order)
        }
    }


@router.get("/trace/{session_id}")
async def trace_execution(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    특정 세션의 에이전트 실행 추적
    LangSmith 연동
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    tracer = get_langsmith_tracer()
    trace_data = tracer.get_session_trace(session_id)
    
    return {
        "success": True,
        "data": trace_data
    }


@router.get("/statistics")
async def get_statistics(
    current_user: User = Depends(get_current_user)
):
    """
    에이전트 통계 정보
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    graph = get_agent_graph()
    tracer = get_langsmith_tracer()
    
    # 노드 타입별 통계
    type_stats = {}
    total_modules = 0
    for node in graph.nodes.values():
        type_name = node.type.value
        if type_name not in type_stats:
            type_stats[type_name] = 0
        type_stats[type_name] += 1
        
        if type_name == 'module':
            total_modules += 1
    
    return {
        "success": True,
        "data": {
            "total_nodes": len(graph.nodes),
            "total_edges": len(graph.edges),
            "total_modules": total_modules,
            "node_types": type_stats,
            "architecture": "Hierarchical + Network",
            "langsmith_enabled": tracer.enabled,
            "langsmith_project": tracer.project_name
        }
    }


@router.post("/nodes/{node_id}/status")
async def update_node_status(
    node_id: str,
    status: NodeStatus,
    current_user: User = Depends(get_current_user)
):
    """
    노드 상태 업데이트 (테스트/디버깅용)
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    graph = get_agent_graph()
    node = graph.get_node(node_id)
    
    if not node:
        raise HTTPException(status_code=404, detail="노드를 찾을 수 없습니다")
    
    node.status = status
    
    return {
        "success": True,
        "data": {
            "node_id": node_id,
            "status": status.value
        }
    }


@router.get("/agent/{agent_id}/statistics")
async def get_agent_statistics(
    agent_id: str,
    days: int = Query(default=7, ge=1, le=30),
    current_user: User = Depends(get_current_user)
):
    """
    특정 에이전트의 통계 정보
    LangSmith 데이터 기반
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    tracer = get_langsmith_tracer()
    stats = tracer.get_agent_statistics(agent_id, days)
    
    return {
        "success": True,
        "data": stats
    }


@router.post("/execute/simulation")
async def execute_simulation_workflow(
    data: Dict = Body(...),
    current_user: User = Depends(get_current_user)
):
    """
    시뮬레이션 워크플로우 실행
    
    Request Body:
    {
        "user_input": "안녕하세요",
        "persona": {...},
        "situation": {...},
        "session_id": "session_123"
    }
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    if not LANGGRAPH_AVAILABLE:
        raise HTTPException(status_code=503, detail="LangGraph 패키지가 설치되지 않았습니다. requirements.txt를 확인하세요.")
    
    try:
        # 초기 상태 생성
        initial_state = create_initial_state(
            user_input=data.get("user_input"),
            persona=data.get("persona", {}),
            situation=data.get("situation", {}),
            session_id=data.get("session_id", "default")
        )
        
        # 워크플로우 실행
        final_state = execute_simulation(initial_state)
        
        return {
            "success": True,
            "data": {
                "customer_response": final_state.get("customer_response"),
                "turn_count": final_state.get("turn_count"),
                "evaluation": final_state.get("evaluation"),
                "agent_calls": final_state.get("agent_calls", []),
                "error": final_state.get("error")
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/rag")
async def execute_rag_workflow(
    data: Dict = Body(...),
    current_user: User = Depends(get_current_user)
):
    """
    RAG 쿼리 워크플로우 실행
    
    Request Body:
    {
        "query": "정기예금이란?",
        "user_id": 1
    }
    """
    if not LANGGRAPH_AVAILABLE:
        raise HTTPException(status_code=503, detail="LangGraph 패키지가 설치되지 않았습니다.")
    
    try:
        query = data.get("query")
        if not query:
            raise HTTPException(status_code=400, detail="query is required")
        
        user_id = data.get("user_id", current_user.id)
        
        # 워크플로우 실행
        final_state = execute_rag_query(query, user_id)
        
        return {
            "success": True,
            "data": {
                "answer": final_state.get("rag_answer"),
                "sources": final_state.get("rag_sources", []),
                "results": final_state.get("rag_results", []),
                "agent_calls": final_state.get("agent_calls", [])
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/exam")
async def execute_exam_workflow(
    data: Dict = Body(...),
    current_user: User = Depends(get_current_user)
):
    """
    시험 채점 워크플로우 실행
    
    Request Body:
    {
        "exam_data": {...},
        "answers": {...}
    }
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    if not LANGGRAPH_AVAILABLE:
        raise HTTPException(status_code=503, detail="LangGraph 패키지가 설치되지 않았습니다.")
    
    try:
        exam_data = data.get("exam_data")
        answers = data.get("answers")
        
        if not exam_data or not answers:
            raise HTTPException(status_code=400, detail="exam_data and answers are required")
        
        # 워크플로우 실행
        final_state = execute_exam_grading(exam_data, answers)
        
        return {
            "success": True,
            "data": {
                "scores": final_state.get("scores"),
                "analysis": final_state.get("analysis"),
                "recommendations": final_state.get("recommendations", []),
                "agent_calls": final_state.get("agent_calls", [])
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow/graph")
async def get_workflow_graph_structure(
    workflow_type: str = Query(default="simulation", regex="^(simulation|rag|exam)$"),
    current_user: User = Depends(get_current_user)
):
    """
    워크플로우 그래프 구조 조회 (Mermaid 다이어그램)
    
    Query Parameters:
    - workflow_type: simulation, rag, exam
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    if not LANGGRAPH_AVAILABLE:
        raise HTTPException(status_code=503, detail="LangGraph 패키지가 설치되지 않았습니다.")
    
    try:
        mermaid = get_workflow_graph(workflow_type)
        
        return {
            "success": True,
            "data": {
                "workflow_type": workflow_type,
                "mermaid": mermaid
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

