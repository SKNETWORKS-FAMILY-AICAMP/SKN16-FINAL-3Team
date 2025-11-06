"""
Rhubarb LipSync API 라우터
오디오 파일을 받아 viseme 타임라인(JSON) 생성
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import tempfile
import json
import os
import asyncio

router = APIRouter(prefix="/lipsync", tags=["lipsync"])

# CORS 설정 (프론트엔드 접근 허용)
from fastapi.middleware.cors import CORSMiddleware

async def create_viseme_timeline(audio_file_path: str) -> dict:
    """
    Rhubarb CLI를 사용하여 viseme 타임라인 생성
    """
    output_path = audio_file_path.replace(".wav", ".json")
    
    # Rhubarb CLI 실행
    # 참고: Docker 컨테이너에 rhubarb가 설치되어 있어야 함
    try:
        cmd = ["rhubarb", "-f", "json", "-o", output_path, audio_file_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # JSON 파일 읽기
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 임시 파일 삭제
        os.remove(output_path)
        
        return data
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Rhubarb 실행 실패: {e.stderr}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Viseme 생성 실패: {str(e)}"
        )


@router.post("/generate")
async def generate_lipsync(file: UploadFile = File(...)):
    """
    오디오 파일을 받아 viseme 타임라인 생성
    - 입력: WAV 파일
    - 출력: { "mouthCues": [{ "start": 0.12, "end": 0.20, "value": "A" }, ...] }
    """
    # 임시 파일에 오디오 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
        # 파일 내용 저장
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        # viseme 타임라인 생성
        timeline = await create_viseme_timeline(tmp_file_path)
        
        return {
            "success": True,
            "mouthCues": timeline.get("mouthCues", []),
            "audioFile": file.filename
        }
        
    finally:
        # 임시 파일 삭제
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)


@router.get("/health")
async def health_check():
    """
    Rhubarb 설치 여부 확인
    """
    try:
        result = subprocess.run(
            ["rhubarb", "--version"],
            capture_output=True,
            text=True
        )
        return {
            "status": "ok",
            "rhubarb_version": result.stdout.strip() if result.returncode == 0 else "unknown"
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "message": "Rhubarb가 설치되지 않았습니다."
        }

