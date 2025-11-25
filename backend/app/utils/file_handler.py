"""
파일 처리 유틸리티
업로드/다운로드 및 삭제 헬퍼
"""
from fastapi import UploadFile, HTTPException
from pathlib import Path
import shutil
import re

# 허용 확장자 (jsonl 포함)
ALLOWED_EXTENSIONS = {
    '.pdf', '.txt', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.jsonl'
}

# 파일 카테고리별 디렉터리
CATEGORY_DIRS = {
    '금융영업': '금융영업',
    '상품개발 및 운용': '상품개발 및 운용',
    '신용분석 및 리스크관리': '신용분석 및 리스크관리',
    '외환': '외환',
    '은행지식 및 관련법률': '은행지식 및 관련법률',
    '하경은행': '하경은행',
    # 'RAG': 'RAG'
}

def get_file_extension(filename: str) -> str:
    """확장자 추출"""
    return Path(filename).suffix.lower()


def is_allowed_file(filename: str) -> bool:
    """확장자 허용 여부 검사"""
    return get_file_extension(filename) in ALLOWED_EXTENSIONS


def _safe_filename(original_name: str, save_dir: Path) -> str:
    """
    원본 이름을 최대한 유지하되, 안전한 문자만 남기고,
    중복 시 숫자 suffix를 붙여 고유한 파일명을 생성합니다.
    허용: 영문/숫자/한글/._-
    """
    stem = Path(original_name).stem
    ext = get_file_extension(original_name)
    safe_stem = re.sub(r"[^A-Za-z0-9._\-가-힣]+", "_", stem).strip("_") or "file"
    candidate = f"{safe_stem}{ext}"
    counter = 1
    while (save_dir / candidate).exists():
        candidate = f"{safe_stem}_{counter}{ext}"
        counter += 1
    return candidate


async def save_upload_file(
    upload_file: UploadFile,
    category: str,
    upload_dir: str = "./uploads",
) -> tuple[str, int]:
    """
    업로드된 파일 저장
    Args:
        upload_file: 업로드 파일
        category: 파일 카테고리
        upload_dir: 업로드 루트 디렉터리
    Returns:
        (저장 경로, 파일 크기 바이트)
    """
    if not is_allowed_file(upload_file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    category_dir = CATEGORY_DIRS.get(category, 'others')
    save_dir = Path(upload_dir) / category_dir
    save_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_filename(upload_file.filename, save_dir)
    file_path = save_dir / safe_name

    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        file_size = file_path.stat().st_size
        return str(file_path), file_size
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


def delete_file(file_path: str) -> bool:
    """파일 삭제"""
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
    파일 크기를 사람이 읽기 쉬운 문자열로 변환 (예: 1.5 MB)
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
