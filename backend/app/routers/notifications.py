from datetime import date, timedelta, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.routers.deps import session_dep, auth_dep, admin_dep
from app.models import Notification, NotificationPreference
from app.schemas import (
    NotificationListResponse, NotificationUnreadResponse,
    NotificationMarkReadRequest, NotificationDeleteRequest,
    NotificationPreferenceResponse, NotificationPreferenceUpdateRequest,
)
from app.services.notification import create_notification, get_all_preferences, NOTIFICATION_TYPES, check_price_alerts
from app.services.auth import log_user_action

router = APIRouter(prefix="/api/v1")


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    user=Depends(auth_dep),
    session=Depends(session_dep),
    notification_type: Optional[str] = None,
    is_read: Optional[bool] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = select(Notification).where(Notification.user_id == user.id)
    if notification_type:
        query = query.where(Notification.type == notification_type)
    if is_read is not None:
        query = query.where(Notification.is_read == is_read)
    if start_date:
        query = query.where(Notification.created_at >= start_date)
    if end_date:
        query = query.where(Notification.created_at <= end_date + timedelta(days=1))
    query = query.order_by(Notification.created_at.desc())
    total = len(session.exec(query).all())
    notifications = session.exec(query.offset(offset).limit(limit)).all()
    return {"total": total, "items": notifications}


@router.get("/notifications/unread", response_model=NotificationUnreadResponse)
def get_unread_count(user=Depends(auth_dep), session=Depends(session_dep)):
    count = len(session.exec(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.is_read == False,
        )
    ).all())
    return {"unread_count": count}


@router.post("/notifications/mark_read")
def mark_notifications_read(
    payload: NotificationMarkReadRequest,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    if payload.mark_all:
        notifications = session.exec(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.is_read == False,
            )
        ).all()
    elif payload.ids:
        notifications = session.exec(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.id.in_(payload.ids),
            )
        ).all()
    else:
        raise HTTPException(status_code=400, detail="请指定要标记的通知ID或标记全部")
    for n in notifications:
        n.is_read = True
    session.commit()
    log_user_action(session, user_id=user.id, action_type="mark_read", action_detail=f"标记 {len(notifications)} 条通知为已读")
    return {"status": "ok", "marked_count": len(notifications)}


@router.delete("/notifications")
def delete_notifications(
    payload: NotificationDeleteRequest,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    notifications = session.exec(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.id.in_(payload.ids),
        )
    ).all()
    count = len(notifications)
    for n in notifications:
        session.delete(n)
    session.commit()
    log_user_action(session, user_id=user.id, action_type="delete_notification", action_detail=f"删除 {count} 条通知")
    return {"status": "ok", "deleted_count": count}


@router.get("/notifications/preferences", response_model=NotificationPreferenceResponse)
def get_notification_preferences(user=Depends(auth_dep), session=Depends(session_dep)):
    prefs = get_all_preferences(session, user.id)
    return {
        "preferences": [
            {
                "id": p.id,
                "notification_type": p.notification_type,
                "enabled": p.enabled,
                "threshold_up": p.threshold_up,
                "threshold_down": p.threshold_down,
            }
            for p in prefs
        ],
        "available_types": NOTIFICATION_TYPES,
    }


@router.put("/notifications/preferences", response_model=NotificationPreferenceResponse)
def update_notification_preferences(
    payload: NotificationPreferenceUpdateRequest,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    for item in payload.preferences:
        pref = session.exec(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user.id,
                NotificationPreference.notification_type == item.notification_type,
            )
        ).first()
        if not pref:
            pref = NotificationPreference(
                user_id=user.id,
                notification_type=item.notification_type,
                enabled=item.enabled,
                threshold_up=item.threshold_up,
                threshold_down=item.threshold_down,
            )
        else:
            pref.enabled = item.enabled
            pref.threshold_up = item.threshold_up
            pref.threshold_down = item.threshold_down
            pref.updated_at = datetime.utcnow()
        session.add(pref)
    session.commit()
    log_user_action(session, user_id=user.id, action_type="update_notification_prefs", action_detail="更新通知偏好设置")
    prefs = get_all_preferences(session, user.id)
    return {
        "preferences": [
            {
                "id": p.id,
                "notification_type": p.notification_type,
                "enabled": p.enabled,
                "threshold_up": p.threshold_up,
                "threshold_down": p.threshold_down,
            }
            for p in prefs
        ],
        "available_types": NOTIFICATION_TYPES,
    }


@router.post("/notifications/check_price_alerts")
def trigger_price_alerts(session=Depends(session_dep), user=Depends(admin_dep)):
    notifications = check_price_alerts(session)
    return {"status": "ok", "generated_count": len(notifications)}
