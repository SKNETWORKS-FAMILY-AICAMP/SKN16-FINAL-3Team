"""
LangGraph 멀티 에이전트 아키텍처 정의
하이라키 + 네트워크 구조의 에이전트 시스템
모듈 기반 하이라키 구조로 재구성
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum


class AgentType(str, Enum):
    """에이전트 타입"""
    MODULE = "module"  # 모듈 (하위 에이전트 그룹)
    ORCHESTRATOR = "orchestrator"  # 오케스트레이터
    PROCESSOR = "processor"  # 프로세서
    EVALUATOR = "evaluator"  # 평가자
    DETECTOR = "detector"  # 감지기
    GENERATOR = "generator"  # 생성기
    RETRIEVER = "retriever"  # 검색기


class NodeStatus(str, Enum):
    """노드 실행 상태"""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


@dataclass
class AgentNode:
    """에이전트 노드 정의"""
    id: str
    name: str
    type: AgentType
    description: str
    inputs: List[str]
    outputs: List[str]
    dependencies: List[str]
    service_file: Optional[str] = None
    function_name: Optional[str] = None
    status: NodeStatus = NodeStatus.IDLE
    module_id: Optional[str] = None  # 모듈에 속한 경우 모듈 ID
    agent_id: Optional[str] = None  # 모듈인 경우 하위 에이전트 ID 목록
    children: List[str] = field(default_factory=list)  # 하위 노드 ID 목록
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        result = asdict(self)
        # Enum을 값으로 변환
        result['type'] = self.type.value
        result['status'] = self.status.value
        return result


@dataclass
class AgentEdge:
    """에이전트 간 연결 정의"""
    id: str
    source: str
    target: str
    label: str
    data_type: str
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return asdict(self)


class MultiAgentGraph:
    """멀티 에이전트 그래프 정의 - 모듈 기반 하이라키 구조"""
    
    def __init__(self):
        self.nodes: Dict[str, AgentNode] = {}
        self.edges: List[AgentEdge] = []
        self.modules: Dict[str, List[str]] = {}  # 모듈 ID -> 에이전트 ID 목록
        self._build_graph()
    
    def _build_graph(self):
        """그래프 구조 빌드 - 모듈 기반"""
        
        # ==================== 모듈 정의 ====================
        
        # 1. 학습관리 모듈
        self._build_learning_management_module()
        
        # 2. 시뮬레이션 모듈 (가장 복잡)
        self._build_simulation_module()
        
        # 3. 일정관리 모듈
        self._build_schedule_management_module()
        
        # 4. 챗봇 모듈
        self._build_chatbot_module()
        
        # 5. 동아리 라운지 모듈
        self._build_community_lounge_module()
        
        # 모듈 간 연결 정의
        self._build_module_edges()
    
    def _build_learning_management_module(self):
        """학습관리 모듈 빌드"""
        module_id = "learning_management_module"
        
        # 모듈 노드
        self.add_node(AgentNode(
            id=module_id,
            name="학습관리 모듈",
            type=AgentType.MODULE,
            description="학습 자료 관리, 시험 시스템, 학습 진도 관리",
            inputs=["user_id", "learning_request"],
            outputs=["learning_content", "progress_data"],
            dependencies=[],
            children=[]
        ))
        
        # 학습관리 모듈 내 에이전트들
        exam_agent = AgentNode(
            id="exam_service",
            name="시험 평가 서비스",
            type=AgentType.EVALUATOR,
            description="은행원 시험 채점 및 평가",
            inputs=["answers", "exam_data"],
            outputs=["scores", "analysis", "recommendations"],
            dependencies=["product_knowledge"],
            service_file="exam_service.py",
            function_name="grade_exam",
            module_id=module_id
        )
        
        self.add_node(exam_agent)
        self.modules[module_id] = ["exam_service"]
        self.nodes[module_id].children = ["exam_service"]
    
    def _build_simulation_module(self):
        """시뮬레이션 모듈 빌드 - 가장 복잡한 구조"""
        module_id = "simulation_module"
        
        # 모듈 노드
        self.add_node(AgentNode(
            id=module_id,
            name="시뮬레이션 모듈",
            type=AgentType.MODULE,
            description="음성 시뮬레이션, 페르소나 기반 고객 응답 생성, 피드백 및 평가",
            inputs=["user_id", "persona_id", "situation_id", "audio_data"],
            outputs=["simulation_result", "feedback", "evaluation"],
            dependencies=["chatbot_module"],
            children=[]
        ))
        
        children_agents = []
        
        # === RAG Simulation Service 관련 에이전트들 ===
        rag_sim_agents = [
            AgentNode(
                id="rag_sim_start",
                name="RAG 시뮬레이션 시작",
                type=AgentType.ORCHESTRATOR,
                description="시뮬레이션 세션 초기화 및 페르소나/상황 설정",
                inputs=["user_id", "persona_id", "situation_id"],
                outputs=["session_data", "initial_message"],
                dependencies=[],
                service_file="rag_simulation_service.py",
                function_name="start_voice_simulation",
                module_id=module_id
            ),
            AgentNode(
                id="rag_sim_stt",
                name="음성 인식 (STT)",
                type=AgentType.PROCESSOR,
                description="음성 데이터를 텍스트로 변환",
                inputs=["audio_data"],
                outputs=["transcribed_text", "confidence"],
                dependencies=[],
                service_file="rag_simulation_service.py",
                function_name="_speech_to_text",
                module_id=module_id
            ),
            AgentNode(
                id="rag_sim_text_normalizer",
                name="텍스트 정규화",
                type=AgentType.PROCESSOR,
                description="은행 용어 정규화 및 음성인식 오류 교정",
                inputs=["raw_text", "confidence"],
                outputs=["normalized_text", "corrections"],
                dependencies=["banking_normalizer"],
                service_file="rag_simulation_service.py",
                function_name="normalize_user_text",
                module_id=module_id
            ),
            AgentNode(
                id="rag_sim_customer_generator",
                name="고객 응답 생성기",
                type=AgentType.GENERATOR,
                description="페르소나 기반 고객 응답 텍스트 생성",
                inputs=["user_message", "persona", "situation", "history"],
                outputs=["customer_response", "response_metadata"],
                dependencies=["natural_customer_simulator", "prompt_orchestrator"],
                service_file="rag_simulation_service.py",
                function_name="process_voice_interaction",
                module_id=module_id
            ),
            AgentNode(
                id="rag_sim_tts",
                name="음성 합성 (TTS)",
                type=AgentType.GENERATOR,
                description="고객 응답 텍스트를 음성으로 변환",
                inputs=["text", "persona"],
                outputs=["audio_output", "ssml"],
                dependencies=["persona_voice"],
                service_file="rag_simulation_service.py",
                function_name="_text_to_speech",
                module_id=module_id
            ),
            AgentNode(
                id="rag_sim_evaluator",
                name="응답 평가기",
                type=AgentType.EVALUATOR,
                description="사용자 응답 평가 및 점수 계산",
                inputs=["user_message", "persona", "situation", "history"],
                outputs=["score", "feedback", "improvement_tips"],
                dependencies=[],
                service_file="rag_simulation_service.py",
                function_name="_evaluate_user_response",
                module_id=module_id
            ),
            AgentNode(
                id="rag_sim_score_calculator",
                name="세션 점수 계산기",
                type=AgentType.EVALUATOR,
                description="전체 세션 점수 계산 및 등급 결정",
                inputs=["session_data", "interaction_scores"],
                outputs=["total_score", "grade", "statistics"],
                dependencies=["rag_sim_evaluator"],
                service_file="rag_simulation_service.py",
                function_name="_calculate_session_score",
                module_id=module_id
            ),
            AgentNode(
                id="rag_sim_goal_analyzer",
                name="목표 달성 분석기",
                type=AgentType.EVALUATOR,
                description="훈련 목표 달성 여부 분석",
                inputs=["conversation_history", "goals"],
                outputs=["goal_achievement", "achieved_goals", "remaining_goals"],
                dependencies=[],
                service_file="rag_simulation_service.py",
                function_name="analyze_goal_achievement",
                module_id=module_id
            ),
            AgentNode(
                id="rag_sim_product_matcher",
                name="상품 매칭기",
                type=AgentType.RETRIEVER,
                description="대화 내용에서 상품 정보 매칭",
                inputs=["normalized_text"],
                outputs=["matched_products", "product_details"],
                dependencies=["product_knowledge"],
                service_file="rag_simulation_service.py",
                function_name="match_product_catalog",
                module_id=module_id
            ),
            AgentNode(
                id="rag_sim_query_expander",
                name="검색 쿼리 확장기",
                type=AgentType.PROCESSOR,
                description="정규화된 텍스트를 검색 쿼리로 확장",
                inputs=["normalized_text", "catalog_hits"],
                outputs=["expanded_queries"],
                dependencies=["rag_sim_product_matcher"],
                service_file="rag_simulation_service.py",
                function_name="expand_search_query",
                module_id=module_id
            ),
        ]
        
        # === Advanced Simulation Service 관련 에이전트들 ===
        advanced_sim_agents = [
            AgentNode(
                id="advanced_sim_start",
                name="고급 시뮬레이션 시작",
                type=AgentType.ORCHESTRATOR,
                description="고도화된 시뮬레이션 세션 초기화",
                inputs=["user_id", "persona_id", "situation_id", "session_name"],
                outputs=["session_id", "persona_info", "situation_info", "initial_message"],
                dependencies=[],
                service_file="advanced_simulation_service.py",
                function_name="start_voice_simulation",
                module_id=module_id
            ),
            AgentNode(
                id="advanced_sim_stt",
                name="고급 STT",
                type=AgentType.PROCESSOR,
                description="Whisper API를 사용한 고품질 음성 인식",
                inputs=["audio_data"],
                outputs=["transcribed_text"],
                dependencies=[],
                service_file="advanced_simulation_service.py",
                function_name="_speech_to_text",
                module_id=module_id
            ),
            AgentNode(
                id="advanced_sim_customer_response",
                name="고급 고객 응답 생성",
                type=AgentType.GENERATOR,
                description="AI 기반 페르소나 고객 응답 생성",
                inputs=["session", "user_message"],
                outputs=["customer_response_text", "feedback", "phase"],
                dependencies=[],
                service_file="advanced_simulation_service.py",
                function_name="_generate_customer_response",
                module_id=module_id
            ),
            AgentNode(
                id="advanced_sim_initial_message",
                name="초기 메시지 생성",
                type=AgentType.GENERATOR,
                description="시뮬레이션 시작 시 초기 고객 메시지 생성",
                inputs=["persona", "situation"],
                outputs=["initial_message"],
                dependencies=[],
                service_file="advanced_simulation_service.py",
                function_name="_generate_initial_customer_message",
                module_id=module_id
            ),
            AgentNode(
                id="advanced_sim_tts",
                name="고급 TTS",
                type=AgentType.GENERATOR,
                description="페르소나 기반 음성 합성",
                inputs=["text", "persona"],
                outputs=["audio_output"],
                dependencies=["persona_voice"],
                service_file="advanced_simulation_service.py",
                function_name="_text_to_speech",
                module_id=module_id
            ),
            AgentNode(
                id="advanced_sim_evaluator",
                name="고급 응답 평가기",
                type=AgentType.EVALUATOR,
                description="사용자 응답 평가 및 피드백 생성",
                inputs=["user_message", "persona", "situation"],
                outputs=["evaluation_feedback"],
                dependencies=[],
                service_file="advanced_simulation_service.py",
                function_name="_evaluate_user_response",
                module_id=module_id
            ),
            AgentNode(
                id="advanced_sim_completer",
                name="시뮬레이션 완료 처리",
                type=AgentType.ORCHESTRATOR,
                description="시뮬레이션 완료 및 최종 점수/피드백 생성",
                inputs=["session_id"],
                outputs=["final_score", "grade", "duration", "feedback", "conversation_log"],
                dependencies=["advanced_sim_score_calculator"],
                service_file="advanced_simulation_service.py",
                function_name="complete_simulation",
                module_id=module_id
            ),
            AgentNode(
                id="advanced_sim_score_calculator",
                name="고급 점수 계산기",
                type=AgentType.EVALUATOR,
                description="세션 점수 계산 및 등급 결정",
                inputs=["session_id"],
                outputs=["total_score", "grade"],
                dependencies=[],
                service_file="advanced_simulation_service.py",
                function_name="_calculate_session_score",
                module_id=module_id
            ),
        ]
        
        # === Simulation Service 관련 에이전트들 ===
        basic_sim_agents = [
            AgentNode(
                id="basic_sim_start",
                name="기본 시뮬레이션 시작",
                type=AgentType.ORCHESTRATOR,
                description="기본 시나리오 기반 시뮬레이션 시작",
                inputs=["user_id", "scenario_id"],
                outputs=["attempt_id", "scenario_info", "current_step"],
                dependencies=[],
                service_file="simulation_service.py",
                function_name="start_simulation",
                module_id=module_id
            ),
            AgentNode(
                id="basic_sim_step_evaluator",
                name="단계 응답 평가기",
                type=AgentType.EVALUATOR,
                description="시뮬레이션 단계별 응답 평가",
                inputs=["step", "user_response", "user_action", "criteria"],
                outputs=["is_correct", "score", "feedback", "tips"],
                dependencies=[],
                service_file="simulation_service.py",
                function_name="_evaluate_step_response",
                module_id=module_id
            ),
            AgentNode(
                id="basic_sim_step_feedback",
                name="단계 피드백 생성",
                type=AgentType.GENERATOR,
                description="단계별 피드백 메시지 생성",
                inputs=["step", "user_response", "score", "max_score"],
                outputs=["feedback_message"],
                dependencies=[],
                service_file="simulation_service.py",
                function_name="_generate_step_feedback",
                module_id=module_id
            ),
            AgentNode(
                id="basic_sim_completer",
                name="기본 시뮬레이션 완료",
                type=AgentType.ORCHESTRATOR,
                description="시뮬레이션 완료 및 최종 결과 생성",
                inputs=["attempt_id"],
                outputs=["total_score", "grade", "duration", "feedback", "detailed_results"],
                dependencies=["basic_sim_step_evaluator"],
                service_file="simulation_service.py",
                function_name="_complete_simulation",
                module_id=module_id
            ),
            AgentNode(
                id="basic_sim_progress_tracker",
                name="진행 상황 추적기",
                type=AgentType.RETRIEVER,
                description="사용자 학습 진행 상황 추적",
                inputs=["user_id"],
                outputs=["progress_data", "completed_scenarios", "statistics"],
                dependencies=[],
                service_file="simulation_service.py",
                function_name="get_user_progress",
                module_id=module_id
            ),
        ]
        
        # === Natural Customer Simulator 관련 에이전트들 ===
        natural_sim_agents = [
            AgentNode(
                id="natural_customer_first_turn",
                name="첫 발화 생성",
                type=AgentType.GENERATOR,
                description="고객의 첫 발화를 자연스럽게 생성",
                inputs=["persona", "situation", "goals", "history"],
                outputs=["customer_first_utterance"],
                dependencies=[],
                service_file="natural_customer_simulator.py",
                function_name="generate_first_turn",
                module_id=module_id
            ),
            AgentNode(
                id="natural_customer_follow_up",
                name="후속 발화 생성",
                type=AgentType.GENERATOR,
                description="대화 맥락에 맞는 후속 고객 발화 생성",
                inputs=["persona", "situation", "trainee_asked", "history", "goals", "achieved_goals"],
                outputs=["customer_follow_up_utterance"],
                dependencies=[],
                service_file="natural_customer_simulator.py",
                function_name="generate_follow_up",
                module_id=module_id
            ),
        ]
        
        # === Persona Voice 관련 에이전트들 ===
        persona_voice_agents = [
            AgentNode(
                id="persona_voice_params",
                name="페르소나 음성 파라미터",
                type=AgentType.GENERATOR,
                description="페르소나 기반 음성 파라미터 계산 (voice/rate/pitch)",
                inputs=["persona"],
                outputs=["voice_params"],
                dependencies=[],
                service_file="persona_voice.py",
                function_name="get_voice_params",
                module_id=module_id
            ),
            AgentNode(
                id="persona_voice_ssml",
                name="SSML 생성기",
                type=AgentType.GENERATOR,
                description="음성 합성을 위한 SSML 생성",
                inputs=["text", "rate", "pitch"],
                outputs=["ssml"],
                dependencies=[],
                service_file="persona_voice.py",
                function_name="build_ssml",
                module_id=module_id
            ),
        ]
        
        # === Feedback Service 관련 에이전트들 ===
        feedback_agents = [
            AgentNode(
                id="feedback_comprehensive",
                name="종합 피드백 생성기",
                type=AgentType.EVALUATOR,
                description="시뮬레이션 종합 피드백 생성",
                inputs=["conversation_history", "persona", "situation", "evaluation_data"],
                outputs=["comprehensive_feedback"],
                dependencies=["rag_sim_evaluator", "rag_sim_goal_analyzer"],
                service_file="rag_simulation_service.py",
                function_name="generate_comprehensive_feedback",
                module_id=module_id
            ),
            AgentNode(
                id="feedback_final",
                name="최종 피드백 생성기",
                type=AgentType.EVALUATOR,
                description="시뮬레이션 종료 시 최종 피드백 생성",
                inputs=["session"],
                outputs=["final_feedback"],
                dependencies=["advanced_sim_score_calculator"],
                service_file="advanced_simulation_service.py",
                function_name="_generate_final_feedback",
                module_id=module_id
            ),
        ]
        
        # 모든 시뮬레이션 모듈 에이전트 추가
        all_sim_agents = (
            rag_sim_agents + 
            advanced_sim_agents + 
            basic_sim_agents + 
            natural_sim_agents + 
            persona_voice_agents + 
            feedback_agents
        )
        
        for agent in all_sim_agents:
            self.add_node(agent)
            children_agents.append(agent.id)
        
        self.modules[module_id] = children_agents
        self.nodes[module_id].children = children_agents
    
    def _build_schedule_management_module(self):
        """일정관리 모듈 빌드"""
        module_id = "schedule_management_module"
        
        # 모듈 노드
        self.add_node(AgentNode(
            id=module_id,
            name="일정관리 모듈",
            type=AgentType.MODULE,
            description="일정 생성, 수정, 삭제, 조회 기능",
            inputs=["user_id", "schedule_data"],
            outputs=["schedule_info"],
            dependencies=["chatbot_module"],
            children=[]
        ))
        
        # 일정관리 모듈 내 에이전트들
        schedule_agents = [
            AgentNode(
                id="schedule_creator",
                name="일정 생성기",
                type=AgentType.PROCESSOR,
                description="사용자 요청에서 일정 정보 추출 및 생성",
                inputs=["user_request", "user_id"],
                outputs=["schedule"],
                dependencies=[],
                service_file="schedule_chat_service.py",
                function_name="create_schedule",
                module_id=module_id
            ),
            AgentNode(
                id="schedule_extractor",
                name="일정 정보 추출기",
                type=AgentType.PROCESSOR,
                description="자연어 요청에서 일정 정보 추출",
                inputs=["user_request"],
                outputs=["extracted_schedule_info"],
                dependencies=[],
                service_file="schedule_chat_service.py",
                function_name="extract_schedule_info",
                module_id=module_id
            ),
        ]
        
        for agent in schedule_agents:
            self.add_node(agent)
        
        children_ids = [a.id for a in schedule_agents]
        self.modules[module_id] = children_ids
        self.nodes[module_id].children = children_ids
    
    def _build_chatbot_module(self):
        """챗봇 모듈 빌드"""
        module_id = "chatbot_module"
        
        # 모듈 노드
        self.add_node(AgentNode(
            id=module_id,
            name="챗봇 모듈",
            type=AgentType.MODULE,
            description="RAG 기반 지능형 챗봇, 문서 검색, 자연어 처리",
            inputs=["query", "user_id", "chat_history"],
            outputs=["answer", "sources"],
            dependencies=[],
            children=[]
        ))
        
        # 챗봇 모듈 내 에이전트들
        chatbot_agents = [
            AgentNode(
                id="rag_service",
                name="RAG 서비스",
                type=AgentType.RETRIEVER,
                description="벡터 검색 기반 문서 검색 및 답변 생성",
                inputs=["query", "chat_history", "user_id"],
                outputs=["search_results", "answer", "sources"],
                dependencies=[],
                service_file="rag_service.py",
                function_name="process_chat",
                module_id=module_id
            ),
            AgentNode(
                id="prompt_orchestrator",
                name="프롬프트 오케스트레이터",
                type=AgentType.ORCHESTRATOR,
                description="페르소나/시츄에이션 기반 프롬프트 구성 및 대화 흐름 관리",
                inputs=["persona", "situation", "user_text", "rag_hits", "history"],
                outputs=["llm_messages", "conversation_state"],
                dependencies=["banking_normalizer", "offtopic_detector"],
                service_file="promptOrchestrator.py",
                function_name="compose_llm_messages",
                module_id=module_id
            ),
            AgentNode(
                id="banking_normalizer",
                name="은행 용어 정규화기",
                type=AgentType.PROCESSOR,
                description="은행 용어 및 음성인식 텍스트 정규화",
                inputs=["raw_text"],
                outputs=["normalized_text", "corrections"],
                dependencies=[],
                service_file="banking_normalizer.py",
                function_name="normalize_text",
                module_id=module_id
            ),
            AgentNode(
                id="offtopic_detector",
                name="주제 이탈 감지기",
                type=AgentType.DETECTOR,
                description="은행 업무 범위 이탈 감지 및 피벗 응답 생성",
                inputs=["user_message", "context"],
                outputs=["is_ontopic", "category", "pivot_response"],
                dependencies=[],
                service_file="offtopic_detector.py",
                function_name="is_on_topic",
                module_id=module_id
            ),
            AgentNode(
                id="product_knowledge",
                name="상품 지식 서비스",
                type=AgentType.RETRIEVER,
                description="은행 상품 정보 검색 및 매칭",
                inputs=["query", "product_type"],
                outputs=["product_matches", "product_details"],
                dependencies=[],
                service_file="product_knowledge_service.py",
                function_name="search_products",
                module_id=module_id
            ),
        ]
        
        for agent in chatbot_agents:
            self.add_node(agent)
        
        children_ids = [a.id for a in chatbot_agents]
        self.modules[module_id] = children_ids
        self.nodes[module_id].children = children_ids
    
    def _build_community_lounge_module(self):
        """동아리 라운지 모듈 빌드"""
        module_id = "community_lounge_module"
        
        # 모듈 노드
        self.add_node(AgentNode(
            id=module_id,
            name="동아리 라운지 모듈",
            type=AgentType.MODULE,
            description="익명 게시판, 댓글, 커뮤니티 기능",
            inputs=["user_id", "post_data"],
            outputs=["post_info"],
            dependencies=["chatbot_module"],
            children=[]
        ))
        
        # 동아리 라운지 모듈 내 에이전트들 (기본 구조만)
        community_agents = [
            AgentNode(
                id="post_manager",
                name="게시글 관리자",
                type=AgentType.PROCESSOR,
                description="게시글 생성, 수정, 삭제 관리",
                inputs=["post_data", "user_id"],
                outputs=["post_info"],
                dependencies=[],
                module_id=module_id
            ),
            AgentNode(
                id="comment_manager",
                name="댓글 관리자",
                type=AgentType.PROCESSOR,
                description="댓글 생성, 수정, 삭제 관리",
                inputs=["comment_data", "post_id", "user_id"],
                outputs=["comment_info"],
                dependencies=[],
                module_id=module_id
            ),
        ]
        
        for agent in community_agents:
            self.add_node(agent)
        
        children_ids = [a.id for a in community_agents]
        self.modules[module_id] = children_ids
        self.nodes[module_id].children = children_ids
    
    def _build_module_edges(self):
        """모듈 간 연결 정의"""
        
        # 챗봇 모듈 → 시뮬레이션 모듈
        self.add_edge(AgentEdge(
            id="module_edge_1",
            source="chatbot_module",
            target="simulation_module",
            label="대화 맥락 공유",
            data_type="conversation_context"
        ))
        
        # 챗봇 모듈 → 일정관리 모듈
        self.add_edge(AgentEdge(
            id="module_edge_2",
            source="chatbot_module",
            target="schedule_management_module",
            label="일정 생성 요청",
            data_type="schedule_request"
        ))
        
        # 챗봇 모듈 → 동아리 라운지 모듈
        self.add_edge(AgentEdge(
            id="module_edge_3",
            source="chatbot_module",
            target="community_lounge_module",
            label="게시글/댓글 요청",
            data_type="community_request"
        ))
        
        # 학습관리 모듈 → 일정관리 모듈
        self.add_edge(AgentEdge(
            id="module_edge_4",
            source="learning_management_module",
            target="schedule_management_module",
            label="학습 일정 조회",
            data_type="learning_schedule_request"
        ))
        
        # 시뮬레이션 모듈 내부 연결들
        self._build_simulation_module_internal_edges()
        
        # 챗봇 모듈 내부 연결들
        self._build_chatbot_module_internal_edges()
    
    def _build_simulation_module_internal_edges(self):
        """시뮬레이션 모듈 내부 에이전트 간 연결"""
        
        # RAG Simulation 플로우
        self.add_edge(AgentEdge(
            id="sim_edge_1",
            source="rag_sim_start",
            target="rag_sim_stt",
            label="세션 데이터",
            data_type="session_data"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_2",
            source="rag_sim_stt",
            target="rag_sim_text_normalizer",
            label="음성 인식 텍스트",
            data_type="transcribed_text"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_3",
            source="rag_sim_text_normalizer",
            target="rag_sim_product_matcher",
            label="정규화된 텍스트",
            data_type="normalized_text"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_4",
            source="rag_sim_product_matcher",
            target="rag_sim_query_expander",
            label="매칭된 상품",
            data_type="matched_products"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_5",
            source="rag_sim_query_expander",
            target="rag_sim_customer_generator",
            label="확장된 쿼리",
            data_type="expanded_queries"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_6",
            source="rag_sim_customer_generator",
            target="rag_sim_tts",
            label="고객 응답 텍스트",
            data_type="customer_response_text"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_7",
            source="rag_sim_customer_generator",
            target="rag_sim_evaluator",
            label="응답 메타데이터",
            data_type="response_metadata"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_8",
            source="rag_sim_evaluator",
            target="rag_sim_score_calculator",
            label="평가 점수",
            data_type="evaluation_score"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_9",
            source="rag_sim_score_calculator",
            target="rag_sim_goal_analyzer",
            label="세션 점수",
            data_type="session_score"
        ))
        
        # Advanced Simulation 플로우
        self.add_edge(AgentEdge(
            id="sim_edge_10",
            source="advanced_sim_start",
            target="advanced_sim_stt",
            label="세션 데이터",
            data_type="session_data"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_10b",
            source="advanced_sim_start",
            target="advanced_sim_initial_message",
            label="페르소나/상황 정보",
            data_type="persona_situation_info"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_11",
            source="advanced_sim_stt",
            target="advanced_sim_customer_response",
            label="인식된 텍스트",
            data_type="transcribed_text"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_12",
            source="advanced_sim_customer_response",
            target="advanced_sim_tts",
            label="고객 응답",
            data_type="customer_response_text"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_13",
            source="advanced_sim_customer_response",
            target="advanced_sim_evaluator",
            label="응답 데이터",
            data_type="response_data"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_14",
            source="advanced_sim_evaluator",
            target="advanced_sim_score_calculator",
            label="평가 결과",
            data_type="evaluation_result"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_15",
            source="advanced_sim_score_calculator",
            target="advanced_sim_completer",
            label="점수 데이터",
            data_type="score_data"
        ))
        
        # Natural Customer Simulator 연결
        self.add_edge(AgentEdge(
            id="sim_edge_16",
            source="natural_customer_first_turn",
            target="rag_sim_customer_generator",
            label="첫 발화",
            data_type="first_utterance"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_17",
            source="natural_customer_follow_up",
            target="rag_sim_customer_generator",
            label="후속 발화",
            data_type="follow_up_utterance"
        ))
        
        # Persona Voice 연결
        self.add_edge(AgentEdge(
            id="sim_edge_18",
            source="persona_voice_params",
            target="persona_voice_ssml",
            label="음성 파라미터",
            data_type="voice_params"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_19",
            source="persona_voice_ssml",
            target="rag_sim_tts",
            label="SSML",
            data_type="ssml"
        ))
        
        # Feedback 연결
        self.add_edge(AgentEdge(
            id="sim_edge_20",
            source="rag_sim_goal_analyzer",
            target="feedback_comprehensive",
            label="목표 달성 데이터",
            data_type="goal_achievement_data"
        ))
        
        self.add_edge(AgentEdge(
            id="sim_edge_21",
            source="advanced_sim_completer",
            target="feedback_final",
            label="완료 세션 데이터",
            data_type="completed_session_data"
        ))
    
    def _build_chatbot_module_internal_edges(self):
        """챗봇 모듈 내부 에이전트 간 연결"""
        
        self.add_edge(AgentEdge(
            id="chatbot_edge_1",
            source="banking_normalizer",
            target="prompt_orchestrator",
            label="정규화된 텍스트",
            data_type="normalized_text"
        ))
        
        self.add_edge(AgentEdge(
            id="chatbot_edge_2",
            source="offtopic_detector",
            target="prompt_orchestrator",
            label="주제 적합성",
            data_type="ontopic_check"
        ))
        
        self.add_edge(AgentEdge(
            id="chatbot_edge_3",
            source="rag_service",
            target="prompt_orchestrator",
            label="RAG 검색 결과",
            data_type="rag_hits"
        ))
        
        self.add_edge(AgentEdge(
            id="chatbot_edge_4",
            source="product_knowledge",
            target="rag_service",
            label="상품 정보",
            data_type="product_info"
        ))
    
    def add_node(self, node: AgentNode):
        """노드 추가"""
        self.nodes[node.id] = node
    
    def add_edge(self, edge: AgentEdge):
        """엣지 추가"""
        self.edges.append(edge)
    
    def get_node(self, node_id: str) -> Optional[AgentNode]:
        """노드 조회"""
        return self.nodes.get(node_id)
    
    def get_module_agents(self, module_id: str) -> List[AgentNode]:
        """모듈 내 에이전트 목록 조회"""
        agent_ids = self.modules.get(module_id, [])
        return [self.nodes[aid] for aid in agent_ids if aid in self.nodes]
    
    def get_edges_by_source(self, source_id: str) -> List[AgentEdge]:
        """특정 소스에서 나가는 엣지 조회"""
        return [edge for edge in self.edges if edge.source == source_id]
    
    def get_edges_by_target(self, target_id: str) -> List[AgentEdge]:
        """특정 타겟으로 들어오는 엣지 조회"""
        return [edge for edge in self.edges if edge.target == target_id]
    
    def to_dict(self) -> Dict:
        """전체 그래프를 딕셔너리로 변환"""
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
            "modules": {
                module_id: {
                    "agents": agent_ids,
                    "agent_count": len(agent_ids)
                }
                for module_id, agent_ids in self.modules.items()
            },
            "metadata": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "total_modules": len(self.modules),
                "architecture_type": "Hierarchical + Network"
            }
        }
    
    def get_execution_order(self) -> List[str]:
        """실행 순서 계산 (토폴로지 정렬)"""
        # 간단한 위상 정렬 구현
        visited = set()
        order = []
        
        def dfs(node_id: str):
            if node_id in visited:
                return
            visited.add(node_id)
            
            node = self.get_node(node_id)
            if node:
                for dep in node.dependencies:
                    dfs(dep)
            
            order.append(node_id)
        
        for node_id in self.nodes:
            dfs(node_id)
        
        return order


# 싱글톤 인스턴스
_graph_instance = None

def get_agent_graph() -> MultiAgentGraph:
    """에이전트 그래프 싱글톤 인스턴스 반환"""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = MultiAgentGraph()
    return _graph_instance