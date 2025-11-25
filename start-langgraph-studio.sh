#!/bin/bash
# LangGraph Studio Quickstart 스크립트 (Linux/Mac)

echo "========================================"
echo "LangGraph Studio Quickstart"
echo "========================================"
echo ""

# 프로젝트 루트로 이동
cd "$(dirname "$0")"

# 가상환경 활성화 (있는 경우)
if [ -f "backend/venv/bin/activate" ]; then
    echo "가상환경 활성화 중..."
    source backend/venv/bin/activate
fi

# LangGraph CLI 설치 확인
python -c "import langgraph_cli" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "LangGraph CLI가 설치되지 않았습니다. 설치 중..."
    pip install -U "langgraph-cli[inmem]"
fi

# LangGraph dev 서버 시작
echo ""
echo "LangGraph dev 서버를 시작합니다..."
echo "포트: 2024"
echo ""
echo "브라우저에서 다음 URL로 접속하세요:"
echo "https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024"
echo ""
echo "종료하려면 Ctrl+C를 누르세요."
echo ""

# Change to backend directory and start LangGraph dev server
cd backend
langgraph dev --host 127.0.0.1 --port 2024 --config ../langgraph.json

