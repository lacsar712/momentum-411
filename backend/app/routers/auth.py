import json
import os
import uuid
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile
from sqlmodel import select

from app.routers.deps import session_dep, auth_dep, _get_user_permissions
from app.core.config import settings
from app.models import User, UserActionLog, Role, UserRole, RolePermission, Permission
from app.schemas import (
    LoginRequest, AuthResponse, UserInfoResponse, ChangePasswordRequest,
    ActivityLogResponse, PreferencesUpdateRequest, PreferencesResponse,
    MyPermissionsResponse,
)
from app.services.auth import (
    verify_password, issue_token, get_token_payload, hash_password,
    check_password_strength, invalidate_user_tokens, log_user_action,
)

router = APIRouter(prefix="/api/v1")


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, session=Depends(session_dep)):
    user = session.exec(select(User).where(User.username == payload.username)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = issue_token(user.username, user.role)
    user.last_login = datetime.utcnow()
    session.add(user)
    session.commit()
    log_user_action(
        session,
        user_id=user.id,
        action_type="login",
        action_detail="用户登录",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    return {"token": token, "role": user.role}


@router.get("/auth/me", response_model=UserInfoResponse)
def get_me(user=Depends(auth_dep)):
    return user


@router.post("/auth/change_password")
def change_password(payload: ChangePasswordRequest, user=Depends(auth_dep), session=Depends(session_dep)):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="旧密码错误")
    strength = check_password_strength(payload.new_password)
    if not strength["passed"]:
        raise HTTPException(status_code=400, detail={"message": "密码强度不足", "details": strength["feedback"]})
    user.password_hash = hash_password(payload.new_password)
    session.add(user)
    session.commit()
    invalidate_user_tokens(user.username)
    log_user_action(session, user_id=user.id, action_type="change_password", action_detail="修改密码")
    return {"status": "ok", "message": "密码修改成功"}


@router.get("/auth/password_strength")
def get_password_strength(password: str):
    return check_password_strength(password)


@router.get("/auth/activity_log", response_model=ActivityLogResponse)
def get_activity_log(
    user=Depends(auth_dep),
    session=Depends(session_dep),
    action_type: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    query = select(UserActionLog).where(UserActionLog.user_id == user.id)
    if action_type:
        query = query.where(UserActionLog.action_type == action_type)
    if start_date:
        query = query.where(UserActionLog.created_at >= start_date)
    if end_date:
        query = query.where(UserActionLog.created_at <= end_date + timedelta(days=1))
    query = query.order_by(UserActionLog.created_at.desc())
    total = len(session.exec(query).all())
    logs = session.exec(query.offset(offset).limit(limit)).all()
    return {"total": total, "items": logs}


@router.get("/auth/preferences", response_model=PreferencesResponse)
def get_preferences(user=Depends(auth_dep)):
    if user.preferences_json:
        import json
        return json.loads(user.preferences_json)
    return {}


@router.put("/auth/preferences", response_model=PreferencesResponse)
def update_preferences(payload: PreferencesUpdateRequest, user=Depends(auth_dep), session=Depends(session_dep)):
    import json
    prefs = {}
    if user.preferences_json:
        prefs = json.loads(user.preferences_json)
    if payload.theme is not None:
        prefs["theme"] = payload.theme
    if payload.language is not None:
        prefs["language"] = payload.language
    if payload.default_page is not None:
        prefs["default_page"] = payload.default_page
    user.preferences_json = json.dumps(prefs, ensure_ascii=False)
    session.add(user)
    session.commit()
    log_user_action(session, user_id=user.id, action_type="update_preferences", action_detail="更新用户偏好")
    return prefs


@router.get("/auth/avatar")
def get_avatar(user=Depends(auth_dep)):
    return {"avatar_url": user.avatar_url}


@router.post("/auth/avatar")
def upload_avatar(file: UploadFile = File(...), user=Depends(auth_dep), session=Depends(session_dep)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件")

    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "avatars")
    os.makedirs(upload_dir, exist_ok=True)

    file_ext = os.path.splitext(file.filename)[1] if file.filename else ".png"
    new_filename = f"{user.id}_{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(upload_dir, new_filename)

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    avatar_url = f"/uploads/avatars/{new_filename}"
    user.avatar_url = avatar_url
    session.add(user)
    session.commit()

    log_user_action(session, user_id=user.id, action_type="upload_avatar", action_detail="上传头像")
    return {"avatar_url": avatar_url}


@router.get("/auth/my_permissions", response_model=MyPermissionsResponse)
def get_my_permissions(user=Depends(auth_dep), session=Depends(session_dep)):
    perms = _get_user_permissions(session, user)
    user_roles = session.exec(select(UserRole).where(UserRole.user_id == user.id)).all()
    role_ids = [ur.role_id for ur in user_roles]
    role_names = []
    if role_ids:
        roles = session.exec(select(Role).where(Role.id.in_(role_ids))).all()
        role_names = [r.name for r in roles]
    return {"permissions": sorted(perms), "roles": role_names}


from datetime import datetime
