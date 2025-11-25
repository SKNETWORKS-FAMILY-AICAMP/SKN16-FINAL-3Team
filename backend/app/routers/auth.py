"""
인증 API 라우터
회원가입, 로그인, 토큰 관리
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from typing import List
import os
import uuid
from pathlib import Path

from app.database import get_session
from app.models.user import User, UserCreate, UserRead, UserUpdate, Token, UserRole
from app.models.mentor import ExamScore
from app.models.training_center import TrainingCenterRecord
from app.utils.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_current_active_admin
)
from app.config import settings
import json
import random
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])


def generate_random_performance_scores():
    """랜덤 성과 지표 생성"""
    return {
        "은행업무": random.randint(60, 95),
        "상품지식": random.randint(60, 95),
        "고객응대": random.randint(60, 95),
        "법규준수": random.randint(60, 95),
        "IT활용": random.randint(60, 95),
        "영업실적": random.randint(60, 95)
    }


def create_initial_exam_score(user_id: int, session: Session):
    """새 멘티에게 초기 시험 점수 생성 (연수원 시험 점수 우선)"""
    try:
        from app.models.training_center import TrainingCenterRecord
        
        # 사용자 정보 조회
        user = session.get(User, user_id)
        if not user:
            return
        
        # 연수원 레코드에서 점수 가져오기 (employee_number로 매칭)
        training_record = None
        if user.employee_number:
            training_record = session.exec(
                select(TrainingCenterRecord).where(
                    TrainingCenterRecord.employee_number == user.employee_number,
                    TrainingCenterRecord.employee_type == "mentee"
                )
            ).first()
        
        if training_record and training_record.section_scores:
            # 연수원 시험 점수 생성
            section_scores = training_record.section_scores
            total_score = float(training_record.total_score)
            
            # 등급 계산
            if total_score >= 50:
                grade = "A"
            elif total_score >= 40:
                grade = "B"
            elif total_score >= 30:
                grade = "C"
            else:
                grade = "D"
            
            exam_score = ExamScore(
                mentee_id=user_id,
                exam_name="연수원 시험",
                exam_date=datetime.utcnow(),
                score_data=json.dumps(section_scores, ensure_ascii=False),
                total_score=total_score,
                grade=grade,
                feedback="연수원 시험 점수가 반영되었습니다."
            )
        else:
            # 일반 초기 시험 점수 생성
            performance_scores = generate_random_performance_scores()
            total_score = sum(performance_scores.values()) / len(performance_scores)
            
            # 등급 계산
            if total_score >= 90:
                grade = "A+"
            elif total_score >= 85:
                grade = "A"
            elif total_score >= 80:
                grade = "B+"
            elif total_score >= 75:
                grade = "B"
            elif total_score >= 70:
                grade = "C+"
            else:
                grade = "C"
            
            exam_score = ExamScore(
                mentee_id=user_id,
                exam_name="신입사원 평가",
                exam_date=datetime.utcnow(),
                score_data=json.dumps(performance_scores, ensure_ascii=False),
                total_score=round(total_score, 1),
                grade=grade,
                feedback="신입사원 평가를 완료하셨습니다. 앞으로도 꾸준히 발전해 나가세요!"
            )
        
        session.add(exam_score)
        session.commit()
        print(f"✅ 새 멘티 ({user_id})에게 초기 시험 점수 생성 완료")
        
    except Exception as e:
        print(f"⚠️ 초기 시험 점수 생성 실패: {e}")


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    session: Session = Depends(get_session)
):
    """
    회원가입
    - 이메일 중복 확인
    - 비밀번호 해싱
    - 사용자 정보 저장
    """
    # 이메일 중복 확인
    statement = select(User).where(User.email == user_data.email)
    existing_user = session.exec(statement).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # 비밀번호 해싱
    hashed_password = get_password_hash(user_data.password)
    
    # 사용자 생성
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        name=user_data.name,
        role=user_data.role,
        photo_url=user_data.photo_url,
        phone=user_data.phone,
        interests=user_data.interests,
        hobbies=user_data.hobbies,
        specialties=user_data.specialties,
        team=user_data.team,
        team_number=user_data.team_number,
        employee_number=user_data.employee_number,
        join_year=user_data.join_year,
        position=user_data.position,
        extension=user_data.extension,
        emergency_contact=user_data.emergency_contact,
        encouragement_message=user_data.encouragement_message
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # 멘티인 경우 자동으로 초기 시험 점수 생성
    if user.role == UserRole.MENTEE:
        create_initial_exam_score(user.id, session)
    
    return user


@router.post("/generate-scores-for-existing-mentees")
async def generate_scores_for_existing_mentees(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_admin)
):
    """기존 멘티들에게 랜덤 성과 지표 생성 (관리자 전용)"""
    try:
        # 모든 멘티 조회
        mentees = session.exec(select(User).where(User.role == UserRole.MENTEE)).all()
        
        generated_count = 0
        for mentee in mentees:
            # 이미 시험 점수가 있는지 확인
            existing_exam = session.exec(
                select(ExamScore).where(ExamScore.mentee_id == mentee.id)
            ).first()
            
            if not existing_exam:
                create_initial_exam_score(mentee.id, session)
                generated_count += 1
        
        return {
            "message": f"✅ {generated_count}명의 멘티에게 성과 지표를 생성했습니다.",
            "total_mentees": len(mentees),
            "generated_count": generated_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"성과 지표 생성 실패: {str(e)}"
        )


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
):
    """
    로그인
    - 이메일/비밀번호 검증
    - JWT 토큰 발급 (액세스 토큰 + 리프레시 토큰)
    """
    try:
        print(f"🔵 [LOGIN] 로그인 요청 시작: username={form_data.username[:10]}...")
        
        # 사용자 조회: 이메일 또는 사번(숫자/하이픈 없음) 모두 허용
        username = form_data.username.strip()
        print(f"🔵 [LOGIN] 사용자 조회 시작: {username}")
        
        user = None
        try:
            if "@" in username:
                print(f"🔵 [LOGIN] 이메일로 조회 시도")
                user = session.exec(select(User).where(User.email == username)).first()
            else:
                print(f"🔵 [LOGIN] 사번으로 조회 시도")
                # 사번으로 조회 (또는 과거 데이터 호환을 위해 email==사번도 허용)
                user = session.exec(
                    select(User).where((User.employee_number == username) | (User.email == username))
                ).first()
            print(f"🔵 [LOGIN] 사용자 조회 완료: user={'found' if user else 'not found'}")
        except Exception as db_error:
            import traceback
            print(f"❌ [LOGIN] 데이터베이스 조회 오류: {str(db_error)}\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(db_error)}"
            )
        
        # 사용자 존재 여부 및 비밀번호 확인
        print(f"🔵 [LOGIN] 비밀번호 검증 시작")
        if not user or not verify_password(form_data.password, user.hashed_password):
            print(f"❌ [LOGIN] 사용자 없음 또는 비밀번호 불일치")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        print(f"🔵 [LOGIN] 비밀번호 검증 완료")
        
        # 비활성 사용자 확인
        print(f"🔵 [LOGIN] 사용자 활성 상태 확인: is_active={user.is_active}")
        if not user.is_active:
            print(f"❌ [LOGIN] 비활성 사용자")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )
        
        # 토큰 생성
        print(f"🔵 [LOGIN] 토큰 생성 시작: email={user.email}, role={user.role}")
        try:
            # role을 문자열로 변환 (Enum 직렬화 문제 방지)
            role_value = user.role.value if hasattr(user.role, 'value') else str(user.role)
            print(f"🔵 [LOGIN] role 변환 완료: {role_value}")
            
            print(f"🔵 [LOGIN] access_token 생성 시작")
            access_token = create_access_token(
                data={"sub": user.email, "role": role_value}
            )
            print(f"🔵 [LOGIN] access_token 생성 완료")
            
            print(f"🔵 [LOGIN] refresh_token 생성 시작")
            refresh_token = create_refresh_token(
                data={"sub": user.email, "role": role_value}
            )
            print(f"🔵 [LOGIN] refresh_token 생성 완료")
            
            print(f"✅ [LOGIN] 로그인 성공: {user.email}")
        except Exception as token_error:
            import traceback
            error_detail = f"Token creation error: {str(token_error)}\n{traceback.format_exc()}"
            print(f"❌ [LOGIN] 토큰 생성 오류: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Token creation failed: {str(token_error)}"
            )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Login error: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ [LOGIN] 예상치 못한 오류: {error_detail}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/me", response_model=UserRead)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """현재 로그인한 사용자 정보 조회"""
    return current_user


@router.put("/me", response_model=UserRead)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    현재 사용자 정보 수정
    """
    # 수정할 필드만 업데이트
    update_data = user_update.dict(exclude_unset=True)
    
    # 비밀번호 변경 시 해싱
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data["password"])
        del update_data["password"]
    
    for key, value in update_data.items():
        setattr(current_user, key, value)
    
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    
    return current_user


@router.get("/users", response_model=List[UserRead])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """
    전체 사용자 목록 조회 (관리자만 가능)
    """
    statement = select(User).offset(skip).limit(limit)
    users = session.exec(statement).all()
    return users


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """
    사용자 삭제 (관리자만 가능)
    실제로는 is_active를 False로 설정 (소프트 삭제)
    """
    statement = select(User).where(User.id == user_id)
    user = session.exec(statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = False
    session.add(user)
    session.commit()
    
    return {"message": "User deactivated successfully"}


@router.post("/find-id")
async def find_id(
    name: str,
    employee_number: str,
    session: Session = Depends(get_session)
):
    """
    아이디(이메일) 찾기
    - 이름과 사원번호로 이메일 찾기
    """
    statement = select(User).where(User.name == name, User.employee_number == employee_number)
    user = session.exec(statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found with provided information"
        )
    
    return {
        "email": user.email
    }


@router.post("/reset-password")
async def reset_password(
    email: str,
    employee_number: str,
    new_password: str,
    session: Session = Depends(get_session)
):
    """
    비밀번호 재설정
    - 이메일과 사원번호로 본인 확인
    - 새 비밀번호로 변경
    """
    statement = select(User).where(User.email == email, User.employee_number == employee_number)
    user = session.exec(statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found with provided information"
        )
    
    # 새 비밀번호 해싱 및 저장
    user.hashed_password = get_password_hash(new_password)
    session.add(user)
    session.commit()
    
    return {
        "message": "Password has been reset successfully",
        "email": email
    }


@router.post("/me/photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    프로필 사진 업로드 및 사용자 프로필 업데이트
    - 업로드된 파일을 uploads/profiles 폴더에 저장
    - 저장 경로를 User.photo_url에 반영
    - 반환: { photo_url: "/uploads/profiles/<filename>" }
    """
    # 저장 디렉토리 준비
    profiles_dir = Path(settings.UPLOAD_DIR) / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    # 파일 확장자 제한(간단한 이미지 확장자 허용)
    allowed_ext = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="Only image files are allowed (png, jpg, jpeg, gif, webp)")

    # 파일 저장
    unique_name = f"{uuid.uuid4()}{ext}"
    save_path = profiles_dir / unique_name
    try:
        with save_path.open("wb") as buffer:
            buffer.write(await file.read())
    except Exception as e:
        if save_path.exists():
            save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to save image: {e}")

    # 정적 경로(클라이언트에서 접근할 URL)
    public_url = f"/uploads/profiles/{unique_name}"

    # 사용자 업데이트
    current_user.photo_url = public_url
    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    return {"photo_url": public_url}


@router.delete("/me/photo")
async def delete_profile_photo(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    프로필 사진 초기화 (기본 상태로 복구)
    - 기존 파일이 서버에 있으면 삭제 시도
    - DB의 photo_url 을 None 으로 설정
    """
    # 기존 파일 삭제 시도
    try:
        if current_user.photo_url and current_user.photo_url.startswith("/uploads/"):
            path = Path(settings.UPLOAD_DIR) / Path(current_user.photo_url).relative_to("/uploads")
            if path.exists():
                path.unlink(missing_ok=True)
    except Exception:
        # 파일 삭제 실패해도 이어서 진행 (무해한 실패)
        pass

    current_user.photo_url = None
    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    return {"message": "profile photo reset", "photo_url": None}


@router.post("/qr-login", response_model=Token)
async def qr_login(
    qr_data: str,
    session: Session = Depends(get_session)
):
    """
    QR 로그인 (비밀번호 불필요)
    - QR 코드에서 이메일 추출
    - JWT 토큰 발급
    """
    try:
        # QR 데이터 파싱: "qr-login:email"
        parts = qr_data.split(":", 1)  # 최대 2개로 분할 (이메일에 :가 없다고 가정)
        
        if len(parts) < 2 or parts[0] != "qr-login":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid QR code format"
            )
        
        email = parts[1]
        
        # 사용자 조회
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 비활성 사용자 확인
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )
        
        # 토큰 생성
        access_token = create_access_token(
            data={"sub": user.email, "role": user.role}
        )
        refresh_token = create_refresh_token(
            data={"sub": user.email, "role": user.role}
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid QR code: {str(e)}"
        )