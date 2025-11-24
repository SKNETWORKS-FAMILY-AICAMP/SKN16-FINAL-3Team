"""
?몄쬆 API ?쇱슦???뚯썝媛?? 濡쒓렇?? ?좏겙 愿由?"""
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
    """?쒕뜡 ?깃낵 吏???앹꽦"""
    return {
        "??됱뾽臾?: random.randint(60, 95),
        "?곹뭹吏??: random.randint(60, 95),
        "怨좉컼?묐?": random.randint(60, 95),
        "踰뺢퇋以??: random.randint(60, 95),
        "IT?쒖슜": random.randint(60, 95),
        "?곸뾽?ㅼ쟻": random.randint(60, 95)
    }


def create_initial_exam_score(user_id: int, session: Session):
    """??硫섑떚?먭쾶 珥덇린 ?쒗뿕 ?먯닔 ?앹꽦"""
    try:
        performance_scores = generate_random_performance_scores()
        total_score = sum(performance_scores.values()) / len(performance_scores)
        
        # ?깃툒 怨꾩궛
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
            exam_name="?좎엯?ъ썝 ?됯?",
            exam_date=datetime.utcnow(),
            score_data=json.dumps(performance_scores, ensure_ascii=False),
            total_score=round(total_score, 1),
            grade=grade,
            feedback="?좎엯?ъ썝 ?됯?瑜??꾨즺?섏뀲?듬땲?? ?욎쑝濡쒕룄 袁몄???諛쒖쟾???섍??몄슂!"
        )
        
        session.add(exam_score)
        session.commit()
        print(f"????硫섑떚 ({user_id})?먭쾶 珥덇린 ?쒗뿕 ?먯닔 ?앹꽦 ?꾨즺")
        
    except Exception as e:
        print(f"?좑툘 珥덇린 ?쒗뿕 ?먯닔 ?앹꽦 ?ㅽ뙣: {e}")


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    session: Session = Depends(get_session)
):
    """
    ?뚯썝媛??    - ?대찓??以묐났 ?뺤씤
    - 鍮꾨?踰덊샇 ?댁떛
    - ?ъ슜???뺣낫 ???    """
    # ?대찓??以묐났 ?뺤씤
    statement = select(User).where(User.email == user_data.email)
    existing_user = session.exec(statement).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # 鍮꾨?踰덊샇 ?댁떛
    hashed_password = get_password_hash(user_data.password)
    
    # ?ъ슜???앹꽦
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
    
    # 硫섑떚??寃쎌슦 ?먮룞?쇰줈 珥덇린 ?쒗뿕 ?먯닔 ?앹꽦
    if user.role == UserRole.MENTEE:
        create_initial_exam_score(user.id, session)
    
    return user


@router.post("/generate-scores-for-existing-mentees")
async def generate_scores_for_existing_mentees(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_admin)
):
    """湲곗〈 硫섑떚?ㅼ뿉寃??쒕뜡 ?깃낵 吏???앹꽦 (愿由ъ옄 ?꾩슜)"""
    try:
        # 紐⑤뱺 硫섑떚 議고쉶
        mentees = session.exec(select(User).where(User.role == UserRole.MENTEE)).all()
        
        generated_count = 0
        for mentee in mentees:
            # ?대? ?쒗뿕 ?먯닔媛 ?덈뒗吏 ?뺤씤
            existing_exam = session.exec(
                select(ExamScore).where(ExamScore.mentee_id == mentee.id)
            ).first()
            
            if not existing_exam:
                create_initial_exam_score(mentee.id, session)
                generated_count += 1
        
        return {
            "message": f"??{generated_count}紐낆쓽 硫섑떚?먭쾶 ?깃낵 吏?쒕? ?앹꽦?덉뒿?덈떎.",
            "total_mentees": len(mentees),
            "generated_count": generated_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"?깃낵 吏???앹꽦 ?ㅽ뙣: {str(e)}"
        )


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
):
    """
    濡쒓렇??    - ?대찓??鍮꾨?踰덊샇 寃利?    - JWT ?좏겙 諛쒓툒 (?≪꽭???좏겙 + 由ы봽?덉떆 ?좏겙)
    """
    # ?ъ슜??議고쉶: ?대찓???먮뒗 ?щ쾲(?レ옄/?섏씠???놁쓬) 紐⑤몢 ?덉슜
    username = form_data.username.strip()
    user = None
    if "@" in username:
        user = session.exec(select(User).where(User.email == username)).first()
    else:
        # ?щ쾲?쇰줈 議고쉶 (?먮뒗 怨쇨굅 ?곗씠???명솚???꾪빐 email==?щ쾲???덉슜)
        user = session.exec(
            select(User).where((User.employee_number == username) | (User.email == username))
        ).first()
    
    # ?ъ슜??議댁옱 ?щ? 諛?鍮꾨?踰덊샇 ?뺤씤
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 鍮꾪솢???ъ슜???뺤씤
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    # ?좏겙 ?앹꽦
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


@router.get("/me", response_model=UserRead)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """?꾩옱 濡쒓렇?명븳 ?ъ슜???뺣낫 議고쉶"""
    return current_user


@router.put("/me", response_model=UserRead)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    ?꾩옱 ?ъ슜???뺣낫 ?섏젙
    """
    # ?섏젙???꾨뱶留??낅뜲?댄듃
    update_data = user_update.dict(exclude_unset=True)
    
    # 鍮꾨?踰덊샇 蹂寃????댁떛
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
    ?꾩껜 ?ъ슜??紐⑸줉 議고쉶 (愿由ъ옄留?媛??
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
    ?ъ슜????젣 (愿由ъ옄留?媛??
    ?ㅼ젣濡쒕뒗 is_active瑜?False濡??ㅼ젙 (?뚰봽????젣)
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
    ?꾩씠???대찓?? 李얘린
    - ?대쫫怨??ъ썝踰덊샇濡??대찓??李얘린
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
    鍮꾨?踰덊샇 ?ъ꽕??    - ?대찓?쇨낵 ?ъ썝踰덊샇濡?蹂몄씤 ?뺤씤
    - ??鍮꾨?踰덊샇濡?蹂寃?    """
    statement = select(User).where(User.email == email, User.employee_number == employee_number)
    user = session.exec(statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found with provided information"
        )
    
    # ??鍮꾨?踰덊샇 ?댁떛 諛????    user.hashed_password = get_password_hash(new_password)
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
    ?꾨줈???ъ쭊 ?낅줈??諛??ъ슜???꾨줈???낅뜲?댄듃
    - ?낅줈?쒕맂 ?뚯씪??uploads/profiles ?대뜑?????    - ???寃쎈줈瑜?User.photo_url??諛섏쁺
    - 諛섑솚: { photo_url: "/uploads/profiles/<filename>" }
    """
    # ????붾젆?좊━ 以鍮?    profiles_dir = Path(settings.UPLOAD_DIR) / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    # ?뚯씪 ?뺤옣???쒗븳(媛꾨떒???대?吏 ?뺤옣???덉슜)
    allowed_ext = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="Only image files are allowed (png, jpg, jpeg, gif, webp)")

    # ?뚯씪 ???    unique_name = f"{uuid.uuid4()}{ext}"
    save_path = profiles_dir / unique_name
    try:
        with save_path.open("wb") as buffer:
            buffer.write(await file.read())
    except Exception as e:
        if save_path.exists():
            save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to save image: {e}")

    # ?뺤쟻 寃쎈줈(?대씪?댁뼵?몄뿉???묎렐??URL)
    public_url = f"/uploads/profiles/{unique_name}"

    # ?ъ슜???낅뜲?댄듃
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
    ?꾨줈???ъ쭊 珥덇린??(湲곕낯 ?곹깭濡?蹂듦뎄)
    - 湲곗〈 ?뚯씪???쒕쾭???덉쑝硫???젣 ?쒕룄
    - DB??photo_url ??None ?쇰줈 ?ㅼ젙
    """
    # 湲곗〈 ?뚯씪 ??젣 ?쒕룄
    try:
        if current_user.photo_url and current_user.photo_url.startswith("/uploads/"):
            path = Path(settings.UPLOAD_DIR) / Path(current_user.photo_url).relative_to("/uploads")
            if path.exists():
                path.unlink(missing_ok=True)
    except Exception:
        # ?뚯씪 ??젣 ?ㅽ뙣?대룄 ?댁뼱??吏꾪뻾 (臾댄빐???ㅽ뙣)
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
    QR 濡쒓렇??(鍮꾨?踰덊샇 遺덊븘??
    - QR 肄붾뱶?먯꽌 ?대찓??異붿텧
    - JWT ?좏겙 諛쒓툒
    """
    try:
        # QR ?곗씠???뚯떛: "qr-login:email"
        parts = qr_data.split(":", 1)  # 理쒕? 2媛쒕줈 遺꾪븷 (?대찓?쇱뿉 :媛 ?녿떎怨?媛??
        
        if len(parts) < 2 or parts[0] != "qr-login":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid QR code format"
            )
        
        email = parts[1]
        
        # ?ъ슜??議고쉶
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 鍮꾪솢???ъ슜???뺤씤
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )
        
        # ?좏겙 ?앹꽦
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
