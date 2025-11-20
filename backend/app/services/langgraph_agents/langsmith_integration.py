"""
LangSmith 연동 서비스
에이전트 실행 추적 및 모니터링
"""
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import json


class LangSmithTracer:
    """LangSmith 추적 서비스"""
    
    def __init__(self):
        self.api_key = os.getenv("LANGSMITH_API_KEY")
        self.project_name = os.getenv("LANGSMITH_PROJECT", "bank-mentor-system")
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            print(f"✅ LangSmith 추적 활성화 - 프로젝트: {self.project_name}")
        else:
            print("⚠️ LangSmith API 키가 설정되지 않았습니다")
    
    def trace_agent_execution(
        self,
        agent_id: str,
        agent_name: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        execution_time: float,
        status: str = "success",
        error: Optional[str] = None
    ) -> Dict:
        """
        에이전트 실행 추적
        
        Args:
            agent_id: 에이전트 ID
            agent_name: 에이전트 이름
            inputs: 입력 데이터
            outputs: 출력 데이터
            execution_time: 실행 시간 (초)
            status: 실행 상태 (success/error)
            error: 에러 메시지 (있는 경우)
        
        Returns:
            추적 레코드
        """
        trace_record = {
            "trace_id": f"{agent_id}_{datetime.now().timestamp()}",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "timestamp": datetime.now().isoformat(),
            "inputs": inputs,
            "outputs": outputs,
            "execution_time": execution_time,
            "status": status,
            "error": error,
            "project": self.project_name
        }
        
        if self.enabled:
            # TODO: 실제 LangSmith API 호출
            # 현재는 로컬 로깅만 수행
            print(f"📊 [LangSmith] {agent_name} 실행 추적: {status} ({execution_time:.2f}s)")
        
        return trace_record
    
    def trace_session(
        self,
        session_id: str,
        session_type: str,
        agents_used: List[str],
        total_time: float,
        status: str = "completed"
    ) -> Dict:
        """
        세션 전체 추적
        
        Args:
            session_id: 세션 ID
            session_type: 세션 타입 (simulation/rag/exam 등)
            agents_used: 사용된 에이전트 목록
            total_time: 총 실행 시간
            status: 세션 상태
        
        Returns:
            세션 추적 레코드
        """
        session_record = {
            "session_id": session_id,
            "session_type": session_type,
            "timestamp": datetime.now().isoformat(),
            "agents_used": agents_used,
            "total_agents": len(agents_used),
            "total_time": total_time,
            "status": status,
            "project": self.project_name
        }
        
        if self.enabled:
            print(f"📊 [LangSmith] 세션 추적: {session_id} ({len(agents_used)} agents, {total_time:.2f}s)")
        
        return session_record
    
    def get_agent_statistics(self, agent_id: str, days: int = 7) -> Dict:
        """
        에이전트 통계 조회
        
        Args:
            agent_id: 에이전트 ID
            days: 조회 기간 (일)
        
        Returns:
            통계 데이터
        """
        # TODO: 실제 LangSmith에서 데이터 조회
        # 현재는 더미 데이터 반환
        return {
            "agent_id": agent_id,
            "period_days": days,
            "total_executions": 0,
            "success_rate": 0.0,
            "avg_execution_time": 0.0,
            "error_count": 0,
            "message": "LangSmith 실제 연동 예정"
        }
    
    def get_session_trace(self, session_id: str) -> Dict:
        """
        특정 세션의 추적 정보 조회
        
        Args:
            session_id: 세션 ID
        
        Returns:
            세션 추적 데이터
        """
        # TODO: 실제 LangSmith에서 데이터 조회
        return {
            "session_id": session_id,
            "traces": [],
            "message": "LangSmith 실제 연동 예정"
        }


# 싱글톤 인스턴스
_tracer_instance = None

def get_langsmith_tracer() -> LangSmithTracer:
    """LangSmith 추적기 싱글톤 인스턴스 반환"""
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = LangSmithTracer()
    return _tracer_instance


# 데코레이터: 에이전트 함수 실행 자동 추적
def trace_agent(agent_id: str, agent_name: str):
    """
    에이전트 함수 실행을 자동으로 추적하는 데코레이터
    
    Usage:
        @trace_agent("rag_service", "RAG Service")
        def process_query(query: str):
            # ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            tracer = get_langsmith_tracer()
            start_time = datetime.now()
            
            try:
                result = func(*args, **kwargs)
                execution_time = (datetime.now() - start_time).total_seconds()
                
                tracer.trace_agent_execution(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    inputs={"args": str(args)[:200], "kwargs": str(kwargs)[:200]},
                    outputs={"result": str(result)[:200]},
                    execution_time=execution_time,
                    status="success"
                )
                
                return result
            
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                
                tracer.trace_agent_execution(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    inputs={"args": str(args)[:200], "kwargs": str(kwargs)[:200]},
                    outputs={},
                    execution_time=execution_time,
                    status="error",
                    error=str(e)
                )
                
                raise
        
        return wrapper
    return decorator

