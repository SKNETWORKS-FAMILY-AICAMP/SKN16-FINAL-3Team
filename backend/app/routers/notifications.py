"""
알림 API 라우터
사용자 알림 관리
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime

from app.database import get_session
from app.models.user import User
from app.models.notification import Notification, NotificationRead
from app.utils.auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=List[NotificationRead])
async def get_notifications(
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """사용자의 알림 목록 조회"""
    try:
        print(f"📬 알림 조회 요청: user_id={current_user.id}, email={current_user.email}, unread_only={unread_only}")
        query = select(Notification).where(Notification.user_id == current_user.id)
        
        if unread_only:
            query = query.where(Notification.is_read == False)
        
        query = query.order_by(Notification.created_at.desc())
        
        notifications = session.exec(query).all()
        print(f"📬 알림 조회 결과: {len(notifications)}개 알림 발견")
        for n in notifications:
            print(f"   - id={n.id}, title={n.title}, is_read={n.is_read}, user_id={n.user_id}")
        
        return [
            NotificationRead(
                id=n.id,
                user_id=n.user_id,
                title=n.title,
                message=n.message,
                type=n.type,
                related_type=n.related_type,
                related_id=n.related_id,
                is_read=n.is_read,
                read_at=n.read_at,
                created_at=n.created_at
            )
            for n in notifications
        ]
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"알림 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """알림을 읽음으로 표시"""
    try:
        notification = session.get(Notification, notification_id)
        if not notification:
            raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
        
        if notification.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="권한이 없습니다.")
        
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        
        session.add(notification)
        session.commit()
        session.refresh(notification)
        
        return NotificationRead(
            id=notification.id,
            user_id=notification.user_id,
            title=notification.title,
            message=notification.message,
            type=notification.type,
            related_type=notification.related_type,
            related_id=notification.related_id,
            is_read=notification.is_read,
            read_at=notification.read_at,
            created_at=notification.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"알림 읽음 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.patch("/read-all", response_model=dict)
async def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """모든 알림을 읽음으로 표시"""
    try:
        query = select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        )
        notifications = session.exec(query).all()
        
        now = datetime.utcnow()
        for notification in notifications:
            notification.is_read = True
            notification.read_at = now
            session.add(notification)
        
        session.commit()
        
        return {
            "success": True,
            "count": len(notifications),
            "message": f"{len(notifications)}개의 알림을 읽음으로 표시했습니다."
        }
    except Exception as e:
        session.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"알림 일괄 읽음 처리 중 오류가 발생했습니다: {str(e)}"
        )

