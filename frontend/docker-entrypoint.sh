#!/bin/sh
set -e

echo "🔍 node_modules 상태 확인 중..."

# node_modules 디렉토리 확인
if [ ! -d "node_modules" ]; then
  echo "⚠️  node_modules 디렉토리가 없습니다. 의존성을 설치합니다..."
  npm install --legacy-peer-deps
  echo "✅ 의존성 설치 완료"
else
  # react-markdown 패키지 확인
  if [ ! -d "node_modules/react-markdown" ]; then
    echo "⚠️  react-markdown이 없습니다. 의존성을 재설치합니다..."
    npm install --legacy-peer-deps
    echo "✅ 의존성 재설치 완료"
  else
    echo "✅ node_modules 확인 완료 (react-markdown 존재)"
  fi
fi

# 개발 서버 시작
echo "🚀 개발 서버 시작..."
exec npm run dev

