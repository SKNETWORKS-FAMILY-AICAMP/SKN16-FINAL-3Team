from app.services.langgraph_agents.workflow import (
    create_simulation_workflow,
    create_rag_workflow,
    create_exam_workflow,
    compile_workflow
)

# LangGraph Studio용 그래프 (checkpointer 없이 컴파일)
# Studio는 자동으로 persistence를 처리하므로 checkpointer가 필요 없습니다
simulation_graph = compile_workflow(create_simulation_workflow(), checkpointer=None)
rag_graph = compile_workflow(create_rag_workflow(), checkpointer=None)
exam_graph = compile_workflow(create_exam_workflow(), checkpointer=None)

