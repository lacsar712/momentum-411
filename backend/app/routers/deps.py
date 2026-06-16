from fastapi import Depends, Header, HTTPException
from sqlmodel import select

from app.db import get_session
from app.models import User, Role, Permission, RolePermission, UserRole


def session_dep():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def auth_dep(authorization: str | None = Header(default=None), session=Depends(session_dep)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.replace("Bearer ", "")
    from app.services.auth import get_token_payload
    payload = get_token_payload(token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期")
    user = session.exec(select(User).where(User.username == payload["username"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def admin_dep(user=Depends(auth_dep)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限")
    return user


def _get_user_permissions(session, user: User) -> set:
    role_ids = [ur.role_id for ur in session.exec(select(UserRole).where(UserRole.user_id == user.id)).all()]
    if not role_ids:
        return set()
    perm_ids = [rp.permission_id for rp in session.exec(select(RolePermission).where(RolePermission.role_id.in_(role_ids))).all()]
    if not perm_ids:
        return set()
    perms = session.exec(select(Permission.code).where(Permission.id.in_(perm_ids))).all()
    return set(perms)


def require_permission(permission_code: str):
    def _dep(user=Depends(auth_dep), session=Depends(session_dep)):
        if user.role == "admin":
            return user
        perms = _get_user_permissions(session, user)
        if permission_code not in perms:
            raise HTTPException(status_code=403, detail=f"需要权限: {permission_code}")
        return user
    return _dep
