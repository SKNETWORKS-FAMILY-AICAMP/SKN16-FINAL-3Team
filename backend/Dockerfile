FROM python:3.11-slim

# 비대화형 설치 설정 (debconf 에러 방지)
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies (불필요 패키지 제외)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install LangGraph CLI
RUN pip install -U "langgraph-cli[inmem]"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
