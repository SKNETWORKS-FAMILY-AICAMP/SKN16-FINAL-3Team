"""
파일 처리 유틸리티
파일 업로드, 저장, 삭제 등
"""
import os
import shutil
from typing import Optional
from fastapi import UploadFile, HTTPException
from pathlib import Path
import uuid

# 허용된 파일 확장자
ALLOWED_EXTENSIONS = {
    '.pdf', '.txt', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt'
}

# 파일 카테고리별 디렉토리
CATEGORY_DIRS = {
    "일반": "1_general",
    "법규": "2_law",
    "상품설명서": "3_pd",
    "서식": "4_forms",
    "약관": "5_tc",
    "FAQ": "6_faq",
    "RAG": "RAG"  # 기존 RAG 카테고리 유지
}


def get_file_extension(filename: str) -> str:
    """파일 확장자 추출"""
    return Path(filename).suffix.lower()


def is_allowed_file(filename: str) -> bool:
    """파일 확장자 검증"""
    return get_file_extension(filename) in ALLOWED_EXTENSIONS


async def save_upload_file(
    upload_file: UploadFile,
    category: str,
    upload_dir: str = "./uploads"
) -> tuple[str, int]:
    """
    업로드된 파일 저장
    Args:
        upload_file: 업로드된 파일
        category: 파일 카테고리
        upload_dir: 업로드 디렉토리
    Returns:
        tuple: (저장된 파일 경로, 파일 크기)
    """
    # 파일 확장자 검증
    if not is_allowed_file(upload_file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # 카테고리 디렉토리 생성
    category_dir = CATEGORY_DIRS.get(category, "others")
    save_dir = Path(upload_dir) / category_dir
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # 고유한 파일명 생성 (UUID 사용)
    file_extension = get_file_extension(upload_file.filename)
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = save_dir / unique_filename
    
    # 파일 저장
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        
        # 파일 크기 확인
        file_size = file_path.stat().st_size
        
        return str(file_path), file_size
    
    except Exception as e:
        # 오류 발생 시 파일 삭제
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


def delete_file(file_path: str) -> bool:
    """
    파일 삭제
    Args:
        file_path: 삭제할 파일 경로
    Returns:
        bool: 삭제 성공 여부
    """
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            return True
        return False
    except Exception as e:
        print(f"Error deleting file: {e}")
        return False


def get_file_size_str(size_bytes: int) -> str:
    """
    파일 크기를 읽기 쉬운 문자열로 변환
    Args:
        size_bytes: 바이트 단위 크기
    Returns:
        str: 변환된 문자열 (예: "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"





