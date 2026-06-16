import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.routers.deps import session_dep, require_permission, _get_user_permissions
from app.models import User, Role, Permission, RolePermission, UserRole
from app.schemas import (
    UserDetailResponse, RoleDetailResponse, PermissionGroupResponse,
    UserRoleRequest, RoleCreateRequest, RoleUpdateRequest, RolePermissionRequest,
)
from app.services.auth import log_user_action

router = APIRouter(prefix="/api/v1")


@router.get("/admin/users", response_model=List[UserDetailResponse])
def list_users(session=Depends(session_dep), user=Depends(require_permission("user.manage"))):
    users = session.exec(select(User)).all()
    result = []
    for u in users:
        user_roles = session.exec(select(UserRole).where(UserRole.user_id == u.id)).all()
        role_ids = [ur.role_id for ur in user_roles]
        roles = session.exec(select(Role).where(Role.id.in_(role_ids))).all() if role_ids else []
        perms = _get_user_permissions(session, u)
        result.append({
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "avatar_url": u.avatar_url,
            "created_at": u.created_at,
            "last_login": u.last_login,
            "roles": [{"id": r.id, "name": r.name, "description": r.description} for r in roles],
            "permissions": sorted(perms),
        })
    return result


@router.get("/admin/users/{user_id}", response_model=UserDetailResponse)
def get_user_detail(user_id: int, session=Depends(session_dep), user=Depends(require_permission("user.manage"))):
    target = session.exec(select(User).where(User.id == user_id)).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    user_roles = session.exec(select(UserRole).where(UserRole.user_id == target.id)).all()
    role_ids = [ur.role_id for ur in user_roles]
    roles = session.exec(select(Role).where(Role.id.in_(role_ids))).all() if role_ids else []
    perms = _get_user_permissions(session, target)
    return {
        "id": target.id,
        "username": target.username,
        "role": target.role,
        "avatar_url": target.avatar_url,
        "created_at": target.created_at,
        "last_login": target.last_login,
        "roles": [{"id": r.id, "name": r.name, "description": r.description} for r in roles],
        "permissions": sorted(perms),
    }


@router.post("/admin/users/{user_id}/roles")
def assign_role_to_user(user_id: int, payload: UserRoleRequest, session=Depends(session_dep), user=Depends(require_permission("user.manage"))):
    target = session.exec(select(User).where(User.id == user_id)).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    role = session.exec(select(Role).where(Role.id == payload.role_id)).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    existing = session.exec(select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == payload.role_id)).first()
    if existing:
        return {"status": "ok", "message": "角色已分配"}
    session.add(UserRole(user_id=user_id, role_id=payload.role_id))
    session.commit()
    log_user_action(session, user_id=user.id, action_type="assign_role", action_detail=f"为用户 {target.username} 分配角色 {role.name}")
    return {"status": "ok"}


@router.delete("/admin/users/{user_id}/roles/{role_id}")
def remove_role_from_user(user_id: int, role_id: int, session=Depends(session_dep), user=Depends(require_permission("user.manage"))):
    existing = session.exec(select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)).first()
    if not existing:
        raise HTTPException(status_code=404, detail="该用户未分配此角色")
    session.delete(existing)
    session.commit()
    log_user_action(session, user_id=user.id, action_type="remove_role", action_detail=f"移除用户角色, user_id={user_id}, role_id={role_id}")
    return {"status": "ok"}


@router.get("/admin/roles", response_model=List[RoleDetailResponse])
def list_roles(session=Depends(session_dep), user=Depends(require_permission("user.manage"))):
    roles = session.exec(select(Role)).all()
    result = []
    for r in roles:
        rp_list = session.exec(select(RolePermission).where(RolePermission.role_id == r.id)).all()
        perm_ids = [rp.permission_id for rp in rp_list]
        perms = session.exec(select(Permission).where(Permission.id.in_(perm_ids))).all() if perm_ids else []
        result.append({
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "is_builtin": r.is_builtin,
            "created_at": r.created_at,
            "permissions": [{"id": p.id, "code": p.code, "name": p.name, "module": p.module} for p in perms],
        })
    return result


@router.post("/admin/roles", response_model=RoleDetailResponse)
def create_role(payload: RoleCreateRequest, session=Depends(session_dep), user=Depends(require_permission("user.manage"))):
    existing = session.exec(select(Role).where(Role.name == payload.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="角色名已存在")
    role = Role(name=payload.name, description=payload.description)
    session.add(role)
    session.commit()
    session.refresh(role)
    log_user_action(session, user_id=user.id, action_type="create_role", action_detail=f"创建角色 {role.name}")
    return {"id": role.id, "name": role.name, "description": role.description, "is_builtin": role.is_builtin, "created_at": role.created_at, "permissions": []}


@router.put("/admin/roles/{role_id}", response_model=RoleDetailResponse)
def update_role(role_id: int, payload: RoleUpdateRequest, session=Depends(session_dep), user=Depends(require_permission("user.manage"))):
    role = session.exec(select(Role).where(Role.id == role_id)).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_builtin:
        raise HTTPException(status_code=400, detail="内置角色不可修改")
    if payload.name is not None:
        existing = session.exec(select(Role).where(Role.name == payload.name, Role.id != role_id)).first()
        if existing:
            raise HTTPException(status_code=400, detail="角色名已存在")
        role.name = payload.name
    if payload.description is not None:
        role.description = payload.description
    session.add(role)
    session.commit()
    session.refresh(role)
    rp_list = session.exec(select(RolePermission).where(RolePermission.role_id == role.id)).all()
    perm_ids = [rp.permission_id for rp in rp_list]
    perms = session.exec(select(Permission).where(Permission.id.in_(perm_ids))).all() if perm_ids else []
    log_user_action(session, user_id=user.id, action_type="update_role", action_detail=f"更新角色 {role.name}")
    return {"id": role.id, "name": role.name, "description": role.description, "is_builtin": role.is_builtin, "created_at": role.created_at, "permissions": [{"id": p.id, "code": p.code, "name": p.name, "module": p.module} for p in perms]}


@router.delete("/admin/roles/{role_id}")
def delete_role(role_id: int, session=Depends(session_dep), user=Depends(require_permission("user.manage"))):
    role = session.exec(select(Role).where(Role.id == role_id)).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_builtin:
        raise HTTPException(status_code=400, detail="内置角色不可删除")
    rp_list = session.exec(select(RolePermission).where(RolePermission.role_id == role_id)).all()
    for rp in rp_list:
        session.delete(rp)
    ur_list = session.exec(select(UserRole).where(UserRole.role_id == role_id)).all()
    for ur in ur_list:
        session.delete(ur)
    session.delete(role)
    session.commit()
    log_user_action(session, user_id=user.id, action_type="delete_role", action_detail=f"删除角色 {role.name}")
    return {"status": "ok"}


@router.post("/admin/roles/{role_id}/permissions")
def assign_permission_to_role(role_id: int, payload: RolePermissionRequest, session=Depends(session_dep), user=Depends(require_permission("user.manage"))):
    role = session.exec(select(Role).where(Role.id == role_id)).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    perm = session.exec(select(Permission).where(Permission.id == payload.permission_id)).first()
    if not perm:
        raise HTTPException(status_code=404, detail="权限点不存在")
    existing = session.exec(select(RolePermission).where(RolePermission.role_id == role_id, RolePermission.permission_id == payload.permission_id)).first()
    if existing:
        return {"status": "ok", "message": "权限已分配"}
    session.add(RolePermission(role_id=role_id, permission_id=payload.permission_id))
    session.commit()
    log_user_action(session, user_id=user.id, action_type="assign_permission", action_detail=f"为角色 {role.name} 分配权限 {perm.code}")
    return {"status": "ok"}


@router.delete("/admin/roles/{role_id}/permissions/{permission_id}")
def remove_permission_from_role(role_id: int, permission_id: int, session=Depends(session_dep), user=Depends(require_permission("user.manage"))):
    existing = session.exec(select(RolePermission).where(RolePermission.role_id == role_id, RolePermission.permission_id == permission_id)).first()
    if not existing:
        raise HTTPException(status_code=404, detail="该角色未分配此权限")
    session.delete(existing)
    session.commit()
    log_user_action(session, user_id=user.id, action_type="remove_permission", action_detail=f"移除角色权限, role_id={role_id}, permission_id={permission_id}")
    return {"status": "ok"}


@router.get("/admin/permissions", response_model=List[PermissionGroupResponse])
def list_permissions(session=Depends(session_dep), user=Depends(require_permission("user.manage"))):
    perms = session.exec(select(Permission).order_by(Permission.module, Permission.code)).all()
    groups: dict = {}
    for p in perms:
        if p.module not in groups:
            groups[p.module] = []
        protected = json.loads(p.protected_apis) if p.protected_apis else []
        groups[p.module].append({"id": p.id, "code": p.code, "name": p.name, "description": p.description, "protected_apis": protected})
    return [{"module": m, "permissions": items} for m, items in groups.items()]
