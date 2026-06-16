import io
import json
import inspect
from datetime import date, datetime, timedelta
from typing import List, Optional
from sqlalchemy import func, distinct
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, File, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse
import pandas as pd
from sqlmodel import select
from app.db import get_session
from app.models import Stock, DailyPrice, ScreeningPreset, PatternResult, BacktestResult, StrategyDefinition, User, DataSyncLog, UserActionLog, Role, Permission, RolePermission, UserRole, Notification, NotificationPreference, UserWatchlist, StockSnapshot, ScoringCardPreset
from app.schemas import DateRangeRequest, DailyDataRequest, PriceRangeRequest, ScreeningRequest, ScreeningExportRequest, ScreeningResponse, PatternScanRequest, BacktestRequest, ExportRequest, PresetRequest, LoginRequest, AuthResponse, LogDeleteRequest, UserInfoResponse, ChangePasswordRequest, ActivityLogResponse, PreferencesUpdateRequest, PreferencesResponse, RoleCreateRequest, RoleUpdateRequest, UserRoleRequest, RolePermissionRequest, PermissionGroupResponse, UserDetailResponse, RoleDetailResponse, MyPermissionsResponse, NotificationItem, NotificationListResponse, NotificationUnreadResponse, NotificationMarkReadRequest, NotificationDeleteRequest, NotificationPreferenceUpdateRequest, NotificationPreferenceResponse, WatchlistItem, WatchlistAddRequest, WatchlistRemoveRequest, WatchlistResponse, NotificationPreferenceItem, RecommendationRequest, CustomScoreRequest, ScoringCardSaveRequest, ScoringCardInfo, RecommendationResponse, ScoringRuleListResponse, ScoringCardListResponse, StockScoreItem
from app.services.notification import create_notification, get_all_preferences, NOTIFICATION_TYPES, check_price_alerts
from app.services.data_sync import sync_stock_list, sync_daily, validate_integrity
from app.services.screening import screen_stocks
from app.services.patterns import detect_patterns, PATTERN_NAMES
from app.services.strategies import get_strategy_map
from app.services.backtest import run_backtest
from app.services.cache import cache_get, cache_set
from app.services.recommend import (
    get_default_rules,
    get_top_n_recommendations,
    get_stock_score_detail,
    score_stock,
)
from app.services.auth import verify_password, issue_token, get_token_payload, hash_password, check_password_strength, invalidate_user_tokens, log_user_action
from app.services.concept import (
    get_concept_list,
    get_concept_detail,
    get_concept_constituents,
    get_concept_leaderboard,
    get_stock_concepts,
    get_related_concepts,
)

router = APIRouter(prefix="/api/v1")

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
    import os
    import uuid
    from app.core.config import settings

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

@router.get("/stocks")
def list_stocks(keyword: str = "", limit: int = 20, offset: int = 0, session=Depends(session_dep)):
    query = select(Stock)
    if keyword:
        # Simple case-insensitive search
        query = query.where(Stock.symbol.contains(keyword) | Stock.name.contains(keyword))
    
    # Get total count efficiently
    # Note: For strict performance on large datasets, use select(func.count()).select_from(...)
    # But here fetching all id is fine for < 5000 stocks
    all_results = session.exec(query).all()
    total = len(all_results)
    
    # Pagination
    stocks = session.exec(query.offset(offset).limit(limit)).all()
    return {"total": total, "items": [s.dict() for s in stocks]}

@router.get("/stocks/query")
def search_stocks(keyword: str = "", limit: int = 20, offset: int = 0, session=Depends(session_dep)):
    query = select(Stock)
    if keyword:
        # Simple case-insensitive search
        query = query.where(Stock.symbol.contains(keyword) | Stock.name.contains(keyword))
    
    total = len(session.exec(query).all())
    stocks = session.exec(query.offset(offset).limit(limit)).all()
    return {"total": total, "items": [s.dict() for s in stocks]}

from fastapi import BackgroundTasks

# Simple in-memory progress tracking
SYNC_STATE = {
    "status": "idle", # idle, running, finished, error
    "type": None, # stock_list, daily
    "current": 0,
    "total": 0,
    "message": "",
    "user_id": None,
}

def update_progress(current, total, message=""):
    SYNC_STATE["current"] = current
    SYNC_STATE["total"] = total
    SYNC_STATE["message"] = message

def _send_task_notification(user_id: int, task_type: str, task_name: str, success: bool, message: str = ""):
    if not user_id:
        return
    try:
        with get_session() as session:
            severity = "success" if success else "error"
            link_url = {
                "stock_list": "/data",
                "daily": "/data",
                "snapshot": "/data",
                "backtest": "/backtest",
                "pattern_scan": "/patterns",
                "index_list": "/index",
                "index_daily": "/index",
            }.get(task_type, "/notifications")
            create_notification(
                session,
                user_id=user_id,
                notification_type={
                    "stock_list": "data_sync",
                    "daily": "data_sync",
                    "snapshot": "data_sync",
                    "backtest": "backtest",
                    "pattern_scan": "pattern_scan",
                    "index_list": "data_sync",
                    "index_daily": "data_sync",
                }.get(task_type, "system"),
                title=f"{task_name}{'成功' if success else '失败'}",
                content=message or f"{task_name}已{'成功完成' if success else '执行失败'}",
                link_url=link_url,
                severity=severity,
            )
    except Exception as e:
        print(f"[通知] 发送任务通知失败: {e}")

@router.get("/data/sync/progress")
def get_sync_progress():
    return SYNC_STATE



def run_sync_stock_list_task(user_id: int = None):
    global SYNC_STATE
    SYNC_STATE.update({"status": "running", "type": "stock_list", "current": 0, "total": 0, "message": "正在启动...", "user_id": user_id})
    task_name = "股票清单同步"
    try:
        # Create a new session for the background task
        with get_session() as session:
            count = sync_stock_list(session, progress_callback=update_progress)
            SYNC_STATE.update({"status": "running", "current": count, "total": count, "message": f"股票清单同步完成，正在更新快照..."})
            
            # 自动更新快照
            from app.services.snapshot_updater import update_stock_snapshots
            snapshot_count = update_stock_snapshots(session, progress_callback=update_progress)
            
            message = f"任务全部完成。已同步 {count} 只股票，更新 {snapshot_count} 个快照。"
            SYNC_STATE.update({"status": "finished", "current": count, "total": count, "message": message})
            _send_task_notification(user_id, "stock_list", task_name, True, message)
    except Exception as e:
        print(f"Background task failed: {e}")
        error_msg = f"任务执行失败: {str(e)}"
        SYNC_STATE.update({"status": "error", "message": error_msg})
        _send_task_notification(user_id, "stock_list", task_name, False, error_msg)

def run_sync_daily_task(symbols, start_date, end_date, sync_type, user_id: int = None):
    global SYNC_STATE
    SYNC_STATE.update({"status": "running", "type": "daily", "current": 0, "total": len(symbols), "message": "正在启动...", "user_id": user_id})
    task_name = "日线数据同步"
    try:
        # Create a new session for the background task
        with get_session() as session:
            count = sync_daily(session, symbols, start_date, end_date, sync_type, progress_callback=update_progress)
            SYNC_STATE.update({"status": "running", "current": len(symbols), "total": len(symbols), "message": f"日线数据同步完成，正在更新快照..."})
            
            # 自动更新快照
            from app.services.snapshot_updater import update_stock_snapshots
            snapshot_count = update_stock_snapshots(session, progress_callback=update_progress)
            
            message = f"任务全部完成。已同步 {count} 条记录，更新 {snapshot_count} 个快照。"
            SYNC_STATE.update({"status": "finished", "current": len(symbols), "total": len(symbols), "message": message})
            _send_task_notification(user_id, "daily", task_name, True, message)
    except Exception as e:
        print(f"Background task failed: {e}")
        error_msg = f"任务执行失败: {str(e)}"
        SYNC_STATE.update({"status": "error", "message": error_msg})
        _send_task_notification(user_id, "daily", task_name, False, error_msg)


@router.post("/data/sync/stocks")
def sync_stocks(background_tasks: BackgroundTasks, session=Depends(session_dep), user=Depends(require_permission("data.sync")):
    if SYNC_STATE["status"] == "running":
        raise HTTPException(status_code=400, detail="Task already running")
    background_tasks.add_task(run_sync_stock_list_task, user.id)
    log_user_action(session, user_id=user.id, action_type="run_sync", action_detail="启动股票清单同步")
    return {"status": "started", "message": "Stock sync started in background"}

@router.post("/data/sync/daily")
def sync_daily_data(payload: DateRangeRequest, background_tasks: BackgroundTasks, session=Depends(session_dep), user=Depends(require_permission("data.sync")):
    if SYNC_STATE["status"] == "running":
        raise HTTPException(status_code=400, detail="Task already running")
    
    symbols = payload.symbols or [s.symbol for s in session.exec(select(Stock)).all()
    if not symbols:
        raise HTTPException(status_code=400, detail="无可同步股票")
    
    background_tasks.add_task(run_sync_daily_task, symbols, payload.start_date, payload.end_date, payload.sync_type, user.id)
    log_user_action(
        session,
        user_id=user.id,
        action_type="run_sync",
        action_detail=f"启动日线数据同步: {len(symbols)}只股票, {payload.start_date}~{payload.end_date}"
    )
    return {"status": "started", "count": len(symbols)}

# 导入快照更新服务
from app.services.snapshot_updater import update_stock_snapshots

def run_snapshot_update_task(user_id: int = None):
    global SYNC_STATE
    SYNC_STATE.update({"status": "running", "type": "snapshot", "current": 0, "total": 0, "message": "更新快照中...", "user_id": user_id})
    task_name = "快照更新"
    try:
        with get_session() as session:
            count = update_stock_snapshots(session, progress_callback=update_progress)
            message = f"快照更新完成，共更新 {count} 只股票"
            SYNC_STATE.update({"status": "finished", "current": count, "total": count, "message": message})
            _send_task_notification(user_id, "snapshot", task_name, True, message)
    except Exception as e:
        print(f"Background task failed: {e}")
        error_msg = f"任务执行失败: {str(e)}"
        SYNC_STATE.update({"status": "error", "message": error_msg})
        _send_task_notification(user_id, "snapshot", task_name, False, error_msg)

@router.post("/data/snapshot/update")
def update_snapshots(background_tasks: BackgroundTasks, session=Depends(session_dep), user=Depends(require_permission("data.sync")):
    """手动触发快照更新"""
    if SYNC_STATE["status"] == "running":
        raise HTTPException(status_code=400, detail="Task already running")
    background_tasks.add_task(run_snapshot_update_task, user.id)
    log_user_action(session, user_id=user.id, action_type="run_sync", action_detail="启动快照更新")
    return {"status": "started", "message": "Snapshot update started"}

@router.post("/data/daily")
def get_daily_data(payload: DailyDataRequest, session=Depends(session_dep)):
    symbols = payload.symbols or [s.symbol for s in session.exec(select(Stock)).all()]
    if not symbols:
        return []
    stocks = session.exec(select(Stock).where(Stock.symbol.in_(symbols))).all()
    ids = [s.id for s in stocks]
    prices = session.exec(select(DailyPrice).where(DailyPrice.stock_id.in_(ids), DailyPrice.trade_date == payload.trade_date)).all()
    return [p.dict() for p in prices]

@router.post("/data/price_range")
def get_price_range(payload: PriceRangeRequest, session=Depends(session_dep)):
    stock = session.exec(select(Stock).where(Stock.symbol == payload.symbol)).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")
    prices = session.exec(select(DailyPrice).where(DailyPrice.stock_id == stock.id, DailyPrice.trade_date >= payload.start_date, DailyPrice.trade_date <= payload.end_date).order_by(DailyPrice.trade_date)).all()
    
    
    if not prices:
        return []

    if payload.frequency == "D":
        return [p.dict() for p in prices]

    # Resampling for Weekly/Monthly
    df = pd.DataFrame([p.dict() for p in prices])
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df.set_index('trade_date', inplace=True)
    
    rule = 'W' if payload.frequency == 'W' else 'M'
    resampled = df.resample(rule).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    # Format back to list of dicts with date string
    results = []
    for date, row in resampled.iterrows():
        results.append({
            "trade_date": date.strftime('%Y-%m-%d'),
            "open": row['open'],
            "high": row['high'],
            "low": row['low'],
            "close": row['close'],
            "volume": row['volume']
        })
    return results

@router.post("/data/integrity")
def check_integrity(payload: DateRangeRequest, session=Depends(session_dep)):
    symbols = payload.symbols or [s.symbol for s in session.exec(select(Stock)).all()]
    return [validate_integrity(session, symbol, payload.start_date, payload.end_date) for symbol in symbols]

@router.post("/screening/run", response_model=ScreeningResponse)
def run_screening(payload: ScreeningRequest, session=Depends(session_dep), user=Depends(auth_dep)):
    cache_key = f"screen:{json.dumps(payload.dict(), ensure_ascii=False)}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    items = screen_stocks(session, payload.dict())
    response = {"total": len(items), "items": items}
    cache_set(cache_key, response, ttl=300)
    log_user_action(
        session,
        user_id=user.id,
        action_type="run_screening",
        action_detail=f"运行选股, 命中{len(items)}只股票"
    )
    return response

@router.post("/screening/export")
def export_screening(payload: ScreeningExportRequest, session=Depends(session_dep), user=Depends(require_permission("screening.export"))):
    items = screen_stocks(session, payload.dict())
    df = pd.DataFrame(items)
    if payload.file_type == "xlsx":
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=screening.xlsx"})
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=screening.csv"})

@router.post("/screening/preset")
def save_preset(payload: PresetRequest, session=Depends(session_dep), user=Depends(auth_dep)):
    preset = session.exec(select(ScreeningPreset).where(ScreeningPreset.name == payload.name)).first()
    action = "更新" if preset else "新建"
    if preset:
        preset.payload_json = json.dumps(payload.payload, ensure_ascii=False)
    else:
        preset = ScreeningPreset(name=payload.name, payload_json=json.dumps(payload.payload, ensure_ascii=False))
        session.add(preset)
    session.commit()
    log_user_action(session, user_id=user.id, action_type="save_preset", action_detail=f"{action}选股方案: {payload.name}")
    return {"status": "ok"}

@router.get("/screening/preset")
def list_presets(session=Depends(session_dep)):
    presets = session.exec(select(ScreeningPreset)).all()
    return [{"name": p.name, "payload": json.loads(p.payload_json)} for p in presets]

@router.delete("/screening/preset")
def delete_preset(name: str, session=Depends(session_dep), user=Depends(auth_dep)):
    preset = session.exec(select(ScreeningPreset).where(ScreeningPreset.name == name)).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    session.delete(preset)
    session.commit()
    return {"status": "ok"}

@router.post("/patterns/scan")
def scan_patterns(payload: PatternScanRequest, session=Depends(session_dep), user=Depends(auth_dep)):
    symbols = payload.symbols or [s.symbol for s in session.exec(select(Stock)).all()]
    results = []
    task_name = "形态扫描"
    try:
        for symbol in symbols:
            stock = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
            if not stock:
                continue
            prices = session.exec(select(DailyPrice).where(DailyPrice.stock_id == stock.id, DailyPrice.trade_date >= payload.start_date, DailyPrice.trade_date <= payload.end_date)).all()
            if not prices:
                continue
            df = pd.DataFrame([p.dict() for p in prices])
            if df.empty:
                continue
            patterns = detect_patterns(df.sort_values("trade_date"), payload.patterns, payload.params)
            if not patterns:
                continue
            for item in patterns:
                session.add(PatternResult(symbol=symbol, pattern_name=item["pattern_name"], detected_date=item["detected_date"], success_rate=item["success_rate"], score=item["score"]))
            results.append({"symbol": symbol, "name": stock.name, "patterns": patterns})
        session.commit()
        pattern_count = sum(len(r["patterns"]) for r in results)
        message = f"扫描完成，共扫描 {len(symbols)} 只股票，发现 {len(results)} 只股票匹配 {pattern_count} 个形态"
        create_notification(
            session,
            user_id=user.id,
            notification_type="pattern_scan",
            title=f"{task_name}成功",
            content=message,
            link_url="/patterns",
            severity="success",
        )
        log_user_action(
            session,
            user_id=user.id,
            action_type="pattern_scan",
            action_detail=f"形态扫描: {','.join(payload.patterns)}, {len(symbols)}只股票"
        )
        return results
    except Exception as e:
        session.rollback()
        error_msg = f"{task_name}失败: {str(e)}"
        create_notification(
            session,
            user_id=user.id,
            notification_type="pattern_scan",
            title=f"{task_name}失败",
            content=error_msg,
            link_url="/patterns",
            severity="error",
        )
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/patterns/library")
def list_patterns():
    return PATTERN_NAMES

@router.get("/dashboard/stats")
def get_dashboard_stats(session=Depends(session_dep)):
    stock_count = len(session.exec(select(Stock)).all())
    daily_coverage = session.exec(select(func.count(distinct(DailyPrice.stock_id)))).one()
    
    return {
        "stock_count": stock_count,
        "daily_coverage": daily_coverage,
        "backtest_count": len(session.exec(select(BacktestResult)).all()),
        "screening_count": len(session.exec(select(ScreeningPreset)).all()),
        "data_status": "稳定"
    }

@router.get("/dashboard/tasks")
def get_dashboard_tasks(session=Depends(session_dep)):
    today = date.today()
    
    # Check if sync happened today
    sync_log = session.exec(select(DataSyncLog).where(DataSyncLog.created_at >= today, DataSyncLog.data_source == "akshare").limit(1)).first()
    sync_done = sync_log is not None
    
    # Check if any backtest ran today
    backtest_log = session.exec(select(BacktestResult).where(BacktestResult.created_at >= today).limit(1)).first()
    backtest_done = backtest_log is not None
    
    tasks = [
        {"id": 1, "text": "完成全市场增量数据同步", "completed": sync_done},
        {"id": 2, "text": "执行每日策略回测验证", "completed": backtest_done},
        {"id": 3, "text": "导出最新选股结果清单", "completed": False} # Logic for export check is harder, keep as manual reminder or check logs
    ]
    return tasks

@router.get("/dashboard/market_cap")
def get_market_cap_distribution(session=Depends(session_dep)):
    # Only include stocks with valid market_cap data
    stocks = session.exec(
        select(Stock)
        .where(Stock.market_cap != None)
        .where(Stock.market_cap > 0)
        .order_by(Stock.market_cap.desc())
        .limit(6)
    ).all()
    data = []
    for s in stocks:
        data.append({"name": s.name, "value": s.market_cap, "symbol": s.symbol})
    return data

@router.get("/strategies")
def list_strategies(session=Depends(session_dep)):
    strategies = session.exec(select(StrategyDefinition)).all()
    if not strategies:
        return [{"name": name, "description": f"{name}策略"} for name in get_strategy_map().keys()]
    return [s.dict() for s in strategies]

@router.post("/backtest/run")
def run_strategy_backtest(payload: BacktestRequest, session=Depends(session_dep), user=Depends(require_permission("backtest.run"))):
    strategy_map = get_strategy_map()
    if payload.strategy_name not in strategy_map:
        raise HTTPException(status_code=400, detail="策略不存在")
    results = []
    task_name = "策略回测"
    try:
        for symbol in payload.symbols:
            stock = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
            if not stock:
                continue
            prices = session.exec(select(DailyPrice).where(DailyPrice.stock_id == stock.id, DailyPrice.trade_date >= payload.start_date, DailyPrice.trade_date <= payload.end_date)).all()
            if not prices:
                continue
            df = pd.DataFrame([p.dict() for p in prices])
            if df.empty:
                continue
            df = df.sort_values("trade_date")
            strategy_func = strategy_map[payload.strategy_name]
            allowed_params = {k: v for k, v in payload.parameters.items() if k in inspect.signature(strategy_func).parameters}
            signal = strategy_func(df, **allowed_params)
            result = run_backtest(df, signal)
            metrics = result["metrics"]
            session.add(BacktestResult(
                strategy_name=payload.strategy_name,
                symbol=symbol,
                start_date=payload.start_date,
                end_date=payload.end_date,
                annual_return=metrics["annual_return"],
                max_drawdown=metrics["max_drawdown"],
                sharpe=metrics["sharpe"],
                win_rate=metrics["win_rate"],
                profit_factor=metrics["profit_factor"],
            ))
            results.append({"symbol": symbol, **metrics, "equity_curve": result["equity_curve"], "dates": result["dates"]})
        session.commit()
        avg_return = sum(r["annual_return"] for r in results) / len(results) if results else 0
        message = f"回测完成，{payload.strategy_name} 策略共回测 {len(results)} 只股票，平均年化收益: {avg_return:.2%}"
        create_notification(
            session,
            user_id=user.id,
            notification_type="backtest",
            title=f"{task_name}成功",
            content=message,
            link_url="/backtest",
            severity="success",
        )
        log_user_action(
            session,
            user_id=user.id,
            action_type="run_backtest",
            action_detail=f"运行回测: {payload.strategy_name}, {len(payload.symbols)}只股票, {payload.start_date}~{payload.end_date}"
        )
        return results
    except Exception as e:
        session.rollback()
        error_msg = f"{task_name}失败: {str(e)}"
        create_notification(
            session,
            user_id=user.id,
            notification_type="backtest",
            title=f"{task_name}失败",
            content=error_msg,
            link_url="/backtest",
            severity="error",
        )
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/export")
def export_data(payload: ExportRequest, session=Depends(session_dep), user=Depends(auth_dep)):
    symbols = payload.symbols or [s.symbol for s in session.exec(select(Stock)).all()]
    stocks = session.exec(select(Stock).where(Stock.symbol.in_(symbols))).all()
    # Optimization: If no date range provided, default to last 30 days to avoid full DB dump
    if not payload.start_date and not payload.end_date:
        payload.start_date = date.today() - timedelta(days=30)
    
    ids = [s.id for s in stocks]
    query = select(DailyPrice).where(DailyPrice.stock_id.in_(ids))
    if payload.start_date:
        query = query.where(DailyPrice.trade_date >= payload.start_date)
    if payload.end_date:
        query = query.where(DailyPrice.trade_date <= payload.end_date)
    prices = session.exec(query).all()
    df = pd.DataFrame([p.dict() for p in prices]) if prices else pd.DataFrame()
    if payload.file_type == "xlsx":
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=export.xlsx"})
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=export.csv"})

@router.get("/system/logs")
def get_system_logs(session=Depends(session_dep), limit: int = 100, offset: int = 0):
    query = select(DataSyncLog).order_by(DataSyncLog.created_at.desc())
    total = len(session.exec(query).all())
    logs = session.exec(query.offset(offset).limit(limit)).all()
    return {"total": total, "items": logs}

@router.delete("/system/logs")
def delete_system_logs(payload: LogDeleteRequest, session=Depends(session_dep), user=Depends(require_permission("logs.delete"))):
    query = select(DataSyncLog)
    if not payload.delete_all:
        if payload.start_date:
            query = query.where(DataSyncLog.created_at >= payload.start_date)
        if payload.end_date:
            # Add one day to include the end date
            query = query.where(DataSyncLog.created_at < payload.end_date + pd.Timedelta(days=1))
    
    logs = session.exec(query).all()
    count = len(logs)
    for log in logs:
        session.delete(log)
    session.commit()
    return {"status": "ok", "deleted": count}

@router.get("/concept/list")
def list_concepts(
    keyword: str = "",
    sort_by: str = Query("name", pattern="^(name|daily_change|five_day_change|constituent_count)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    session=Depends(session_dep)
):
    results = get_concept_list(session, keyword=keyword, sort_by=sort_by, sort_order=sort_order)
    return {"total": len(results), "items": results}

@router.get("/concept/{code}/detail")
def concept_detail(code: str, session=Depends(session_dep)):
    detail = get_concept_detail(session, code)
    if not detail:
        raise HTTPException(status_code=404, detail="概念板块不存在")
    return detail

@router.get("/concept/{code}/constituents")
def concept_constituents(code: str, session=Depends(session_dep)):
    constituents = get_concept_constituents(session, code)
    return {"total": len(constituents), "items": constituents}

@router.get("/concept/leaderboard")
def concept_leaderboard(
    days: int = Query(5, ge=1, le=250),
    limit: int = Query(20, ge=1, le=100),
    session=Depends(session_dep)
):
    results = get_concept_leaderboard(session, days=days, limit=limit)
    return {"days": days, "items": results}

@router.get("/concept/stock/{symbol}")
def stock_concepts(symbol: str, session=Depends(session_dep)):
    concepts = get_stock_concepts(session, symbol)
    return {"symbol": symbol, "total": len(concepts), "items": concepts}

@router.get("/concept/{code}/related")
def related_concepts(
    code: str,
    limit: int = Query(10, ge=1, le=50),
    session=Depends(session_dep)
):
    related = get_related_concepts(session, code, limit=limit)
    return {"items": related}

# ==================== 指数与ETF接口 ====================
from datetime import date as date_type
from app.services.index_service import (
    get_index_list,
    get_index_history,
    get_index_compare,
    get_index_constituents,
    get_index_detail,
)
from app.services.index_sync import sync_index_list, sync_index_daily
from app.models import IndexProduct

def run_sync_index_list_task(user_id: int = None):
    global SYNC_STATE
    SYNC_STATE.update({"status": "running", "type": "index_list", "current": 0, "total": 0, "message": "正在初始化指数/ETF产品...", "user_id": user_id})
    task_name = "指数/ETF产品同步"
    try:
        with get_session() as session:
            count = sync_index_list(session, progress_callback=update_progress)
            message = f"指数/ETF产品初始化完成，共 {count} 个"
            SYNC_STATE.update({"status": "finished", "current": count, "total": count, "message": message})
            _send_task_notification(user_id, "index_list", task_name, True, message)
    except Exception as e:
        print(f"Background task failed: {e}")
        error_msg = f"任务执行失败: {str(e)}"
        SYNC_STATE.update({"status": "error", "message": error_msg})
        _send_task_notification(user_id, "index_list", task_name, False, error_msg)

def run_sync_index_daily_task(codes, start_date, end_date, sync_type, user_id: int = None):
    global SYNC_STATE
    SYNC_STATE.update({"status": "running", "type": "index_daily", "current": 0, "total": 0, "message": "正在启动...", "user_id": user_id})
    task_name = "指数/ETF日线同步"
    try:
        with get_session() as session:
            count = sync_index_daily(session, codes, start_date, end_date, sync_type, progress_callback=update_progress)
            message = f"指数/ETF日线同步完成，共 {count} 条记录"
            SYNC_STATE.update({"status": "finished", "current": count, "total": max(count, 1), "message": message})
            _send_task_notification(user_id, "index_daily", task_name, True, message)
    except Exception as e:
        print(f"Background task failed: {e}")
        error_msg = f"任务执行失败: {str(e)}"
        SYNC_STATE.update({"status": "error", "message": error_msg})
        _send_task_notification(user_id, "index_daily", task_name, False, error_msg)

@router.get("/index/list")
def list_indices(
    keyword: str = "",
    index_type: str | None = Query(None, pattern="^(index|etf)$"),
    sort_by: str = Query("name", pattern="^(name|code|daily_change|five_day_change|latest_amount)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    session=Depends(session_dep),
):
    """指数/ETF列表 + 当日表现"""
    results = get_index_list(
        session,
        keyword=keyword,
        index_type=index_type,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return {"total": len(results), "items": results}

@router.get("/index/{code}/detail")
def index_detail(code: str, session=Depends(session_dep)):
    """指数/ETF详情（关键指标）"""
    detail = get_index_detail(session, code)
    if not detail:
        raise HTTPException(status_code=404, detail="指数/ETF不存在")
    return detail

@router.get("/index/{code}/history")
def index_history(
    code: str,
    start_date: date_type | None = None,
    end_date: date_type | None = None,
    limit: int | None = Query(None, ge=1, le=10000),
    session=Depends(session_dep),
):
    """指数/ETF K线历史数据（含MA均线）"""
    history = get_index_history(session, code, start=start_date, end=end_date, limit=limit)
    if history is None:
        raise HTTPException(status_code=404, detail="指数/ETF不存在")
    return history

@router.get("/index/compare")
def index_compare(
    codes: str = Query(..., description="指数/ETF代码，逗号分隔，2~4个"),
    start_date: date_type | None = None,
    base_method: str = Query("first", pattern="^(first|ytd|y-1|custom)$"),
    session=Depends(session_dep),
):
    """多指数归一化对比序列"""
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if len(code_list) < 2:
        raise HTTPException(status_code=400, detail="至少选择2个指数/ETF进行对比")
    if len(code_list) > 4:
        raise HTTPException(status_code=400, detail="最多支持4个指数/ETF同时对比")
    return get_index_compare(session, code_list, start_date=start_date, base_method=base_method)

@router.get("/index/constituents/{code}")
def index_constituents(code: str, session=Depends(session_dep)):
    """指数成分股"""
    result = get_index_constituents(session, code)
    if result is None:
        raise HTTPException(status_code=404, detail="指数/ETF不存在")
    return result

@router.post("/data/sync/index/products")
def sync_index_products(background_tasks: BackgroundTasks, session=Depends(session_dep), user=Depends(require_permission("data.sync")):
    """初始化指数/ETF产品列表"""
    if SYNC_STATE["status"] == "running":
        raise HTTPException(status_code=400, detail="Task already running")
    background_tasks.add_task(run_sync_index_list_task, user.id)
    log_user_action(session, user_id=user.id, action_type="run_sync", action_detail="启动指数/ETF产品同步")
    return {"status": "started", "message": "Index products sync started"}

@router.post("/data/sync/index/daily")
def sync_index_daily_data(
    background_tasks: BackgroundTasks,
    payload: DateRangeRequest,
    session=Depends(session_dep),
    user=Depends(require_permission("data.sync")),
):
    """同步指数/ETF日线数据"""
    if SYNC_STATE["status"] == "running":
        raise HTTPException(status_code=400, detail="Task already running")
    
    codes = payload.symbols or [p.code for p in session.exec(select(IndexProduct)).all()]
    if not codes:
        raise HTTPException(status_code=400, detail="无可同步指数/ETF")
    
    background_tasks.add_task(run_sync_index_daily_task, codes, payload.start_date, payload.end_date, payload.sync_type, user.id)
    log_user_action(
        session,
        user_id=user.id,
        action_type="run_sync",
        action_detail=f"启动指数/ETF日线同步: {len(codes)}个产品, {payload.start_date}~{payload.end_date}"
    )
    return {"status": "started", "count": len(codes), "codes": codes}

# ==================== 权限管理接口 ====================

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

# ==================== 通知中心接口 ====================

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

# ==================== 自选股接口 ====================

@router.get("/watchlist", response_model=WatchlistResponse)
def get_watchlist(user=Depends(auth_dep), session=Depends(session_dep)):
    watchlist = session.exec(
        select(UserWatchlist).where(UserWatchlist.user_id == user.id).order_by(UserWatchlist.created_at.desc())
    ).all()
    today = datetime.utcnow().date()
    items = []
    for w in watchlist:
        stock = session.exec(select(Stock).where(Stock.symbol == w.symbol)).first()
        if not stock:
            continue
        latest_price = None
        daily_change = None
        prices = session.exec(
            select(DailyPrice).where(
                DailyPrice.stock_id == stock.id,
                DailyPrice.trade_date <= today
            ).order_by(DailyPrice.trade_date.desc()).limit(2)
        ).all()
        if len(prices) >= 1:
            latest_price = prices[0].close
        if len(prices) >= 2:
            daily_change = ((prices[0].close - prices[1].close) / prices[1].close) * 100
        items.append({
            "id": w.id,
            "symbol": w.symbol,
            "name": stock.name,
            "notes": w.notes,
            "created_at": w.created_at,
            "latest_price": latest_price,
            "daily_change": daily_change,
        })
    return {"total": len(items), "items": items}

@router.post("/watchlist")
def add_to_watchlist(
    payload: WatchlistAddRequest,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    existing = session.exec(
        select(UserWatchlist).where(
            UserWatchlist.user_id == user.id,
            UserWatchlist.symbol == payload.symbol,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该股票已在自选股中")
    stock = session.exec(select(Stock).where(Stock.symbol == payload.symbol)).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")
    watchlist_item = UserWatchlist(
        user_id=user.id,
        symbol=payload.symbol,
        notes=payload.notes,
        created_at=datetime.utcnow(),
    )
    session.add(watchlist_item)
    session.commit()
    session.refresh(watchlist_item)
    log_user_action(session, user_id=user.id, action_type="add_watchlist", action_detail=f"添加自选股: {payload.symbol}")
    return {"status": "ok", "id": watchlist_item.id}

@router.delete("/watchlist")
def remove_from_watchlist(
    payload: WatchlistRemoveRequest,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    item = session.exec(
        select(UserWatchlist).where(
            UserWatchlist.user_id == user.id,
            UserWatchlist.symbol == payload.symbol,
        )
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="该股票不在自选股中")
    session.delete(item)
    session.commit()
    log_user_action(session, user_id=user.id, action_type="remove_watchlist", action_detail=f"移除自选股: {payload.symbol}")
    return {"status": "ok"}

# ==================== 内部：价格检查接口 ====================

@router.post("/notifications/check_price_alerts")
def trigger_price_alerts(session=Depends(session_dep), user=Depends(admin_dep)):
    notifications = check_price_alerts(session)
    return {"status": "ok", "generated_count": len(notifications)}

# ==================== 投资组合管理接口 ====================

from app.services.portfolio import (
    get_portfolio_list,
    get_portfolio_detail,
    create_portfolio,
    update_portfolio,
    copy_portfolio,
    delete_portfolio,
    batch_save_holdings,
    add_holding,
    update_holding,
    delete_holding,
    calculate_portfolio_nav,
    calculate_portfolio_metrics,
    get_rebalance_suggestions,
)
from app.models import Portfolio, PortfolioHolding
from app.schemas import (
    PortfolioCreateRequest,
    PortfolioUpdateRequest,
    PortfolioCopyRequest,
    PortfolioResponse,
    PortfolioListResponse,
    PortfolioHoldingCreateRequest,
    PortfolioHoldingUpdateRequest,
    PortfolioHoldingsBatchSaveRequest,
    PortfolioHoldingsResponse,
    PortfolioNavResponse,
    PortfolioMetricsResponse,
    RebalanceResponse,
)

@router.get("/portfolio", response_model=PortfolioListResponse)
def list_portfolios(user=Depends(auth_dep), session=Depends(session_dep)):
    """获取用户投资组合列表"""
    items = get_portfolio_list(session, user.id)
    return {"total": len(items), "items": items}

@router.get("/portfolio/{portfolio_id}", response_model=PortfolioResponse)
def get_portfolio(portfolio_id: int, user=Depends(auth_dep), session=Depends(session_dep)):
    """获取组合详情"""
    detail = get_portfolio_detail(session, portfolio_id, user.id)
    if not detail:
        raise HTTPException(status_code=404, detail="组合不存在")
    return detail

@router.post("/portfolio", response_model=PortfolioResponse)
def create_new_portfolio(
    payload: PortfolioCreateRequest,
    user=Depends(auth_dep), session=Depends(session_dep)):
    """创建新组合"""
    holdings_data = [h.dict(exclude_none=True) for h in payload.holdings]
    result, err = create_portfolio(
        session,
        user.id,
        payload.name,
        payload.description,
        payload.benchmark_code or "000300",
        payload.rebalance_frequency or "monthly",
        holdings_data,
    )
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="create_portfolio", action_detail=f"创建组合: {payload.name}")
    return result

@router.put("/portfolio/{portfolio_id}", response_model=PortfolioResponse)
def update_existing_portfolio(
    portfolio_id: int,
    payload: PortfolioUpdateRequest,
    user=Depends(auth_dep), session=Depends(session_dep)):
    """更新组合信息"""
    update_data = payload.dict(exclude_unset=True)
    result, err = update_portfolio(session, portfolio_id, user.id, update_data)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="update_portfolio", action_detail=f"更新组合: id={portfolio_id}")
    return result

@router.post("/portfolio/{portfolio_id}/copy", response_model=PortfolioResponse)
def copy_existing_portfolio(
    portfolio_id: int,
    payload: PortfolioCopyRequest,
    user=Depends(auth_dep), session=Depends(session_dep)):
    """复制组合"""
    result, err = copy_portfolio(session, portfolio_id, user.id, payload.new_name)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="copy_portfolio", action_detail=f"复制组合: id={portfolio_id} -> {payload.new_name}")
    return result

@router.delete("/portfolio/{portfolio_id}")
def delete_existing_portfolio(
    portfolio_id: int,
    user=Depends(auth_dep), session=Depends(session_dep)):
    """删除组合"""
    ok, err = delete_portfolio(session, portfolio_id, user.id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="delete_portfolio", action_detail=f"删除组合: id={portfolio_id}")
    return {"status": "ok"}

# ---------- 组合持仓接口 ----------

@router.get("/portfolio/{portfolio_id}/holdings", response_model=PortfolioHoldingsResponse)
def list_holdings(portfolio_id: int, user=Depends(auth_dep), session=Depends(session_dep)):
    """获取组合持仓列表"""
    detail = get_portfolio_detail(session, portfolio_id, user.id)
    if not detail:
        raise HTTPException(status_code=404, detail="组合不存在")
    return {"total": len(detail["holdings"]), "items": detail["holdings"]}

@router.put("/portfolio/{portfolio_id}/holdings/batch", response_model=PortfolioHoldingsResponse)
def batch_update_holdings(
    portfolio_id: int,
    payload: PortfolioHoldingsBatchSaveRequest,
    user=Depends(auth_dep), session=Depends(session_dep)):
    """批量保存持仓（整体替换，校验权重总和）"""
    holdings_data = [h.dict(exclude_none=True) for h in payload.holdings]
    result, err = batch_save_holdings(session, portfolio_id, user.id, holdings_data)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="update_holdings", action_detail=f"批量保存持仓: portfolio_id={portfolio_id}, {len(payload.holdings)}只")
    return {"total": len(result) if result else 0, "items": result or []}

@router.post("/portfolio/{portfolio_id}/holdings")
def add_single_holding(
    portfolio_id: int,
    payload: PortfolioHoldingCreateRequest,
    user=Depends(auth_dep), session=Depends(session_dep)):
    """添加单个持仓"""
    result, err = add_holding(session, portfolio_id, user.id, payload.symbol, payload.target_weight)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="add_holding", action_detail=f"添加持仓: {payload.symbol}={payload.target_weight}%")
    return result

@router.patch("/portfolio/{portfolio_id}/holdings/{holding_id}")
def update_single_holding(
    portfolio_id: int,
    holding_id: int,
    payload: PortfolioHoldingUpdateRequest,
    user=Depends(auth_dep), session=Depends(session_dep)):
    """更新单个持仓权重"""
    result, err = update_holding(session, portfolio_id, user.id, holding_id, payload.target_weight)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="update_holding", action_detail=f"更新持仓: holding_id={holding_id}")
    return result

@router.delete("/portfolio/{portfolio_id}/holdings/{holding_id}")
def delete_single_holding(
    portfolio_id: int,
    holding_id: int,
    user=Depends(auth_dep), session=Depends(session_dep)):
    """删除单个持仓"""
    ok, err = delete_holding(session, portfolio_id, user.id, holding_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="delete_holding", action_detail=f"删除持仓: holding_id={holding_id}")
    return {"status": "ok"}

# ---------- 组合分析接口 ----------

@router.get("/portfolio/{portfolio_id}/nav", response_model=PortfolioNavResponse)
def get_portfolio_nav_history(
    portfolio_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user=Depends(auth_dep), session=Depends(session_dep)):
    """组合历史净值回算（含基准对比）"""
    result, err = calculate_portfolio_nav(session, portfolio_id, user.id, start_date, end_date)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {
        "start_date": result["start_date"],
        "end_date": result["end_date"],
        "rebalance_frequency": result["rebalance_frequency"],
        "rebalance_count": result["rebalance_count"],
        "data": result["data"],
    }

@router.get("/portfolio/{portfolio_id}/metrics", response_model=PortfolioMetricsResponse)
def get_portfolio_analysis_metrics(
    portfolio_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user=Depends(auth_dep), session=Depends(session_dep)):
    """组合关键指标（年化、最大回撤、夏普、信息比率、相关性）"""
    result, err = calculate_portfolio_metrics(session, portfolio_id, user.id, start_date, end_date)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return result

@router.get("/portfolio/{portfolio_id}/rebalance", response_model=RebalanceResponse)
def get_suggested_rebalance(
    portfolio_id: int,
    threshold: float = Query(5.0, ge=0.1, le=50.0, description="偏离阈值（百分比）"),
    portfolio_value: float = Query(1000000.0, ge=0, description="组合总市值（用于计算建议金额）"),
    user=Depends(auth_dep), session=Depends(session_dep)):
    """再平衡建议（偏离超过阈值给出买卖建议）"""
    result, err = get_rebalance_suggestions(session, portfolio_id, user.id, threshold, portfolio_value)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return result

# ==================== 风险指标接口 ====================

from app.services.risk import (
    compute_var,
    compute_beta_alpha,
    compute_correlation_matrix,
    compute_risk_metrics,
    compute_rolling_beta,
    compute_all_risk_metrics,
)
from app.schemas import (
    RiskVarRequest,
    RiskBetaRequest,
    RiskCorrelationRequest,
    RiskMetricsRequest,
    RiskRollingBetaRequest,
    RiskAllRequest,
)

@router.post("/risk/var")
def get_var(
    payload: RiskVarRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """VaR（在险价值）计算：历史模拟法 + 参数法，支持多置信度与持有期"""
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="请至少选择一只股票")
    result = compute_var(
        session,
        symbols=payload.symbols,
        start_date=payload.start_date,
        end_date=payload.end_date,
        confidence_levels=payload.confidence_levels,
        holding_period=payload.holding_period,
    )
    log_user_action(
        session,
        user_id=user.id,
        action_type="risk_var",
        action_detail=f"VaR计算: {len(payload.symbols)}只股票, 置信度{payload.confidence_levels}, 持有期{payload.holding_period}天"
    )
    return result

@router.post("/risk/beta_alpha")
def get_beta_alpha(
    payload: RiskBetaRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """Beta/Alpha计算：对指定基准线性回归，返回Beta、年化Alpha、R²、p-value"""
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="请至少选择一只股票")
    result = compute_beta_alpha(
        session,
        symbols=payload.symbols,
        benchmark_code=payload.benchmark_code,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    log_user_action(
        session,
        user_id=user.id,
        action_type="risk_beta",
        action_detail=f"Beta/Alpha计算: {len(payload.symbols)}只股票, 基准{payload.benchmark_code}"
    )
    return result

@router.post("/risk/correlation")
def get_correlation(
    payload: RiskCorrelationRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """相关性矩阵：多只股票/指数两两皮尔逊相关系数"""
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="请至少选择一只股票")
    result = compute_correlation_matrix(
        session,
        symbols=payload.symbols,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    log_user_action(
        session,
        user_id=user.id,
        action_type="risk_correlation",
        action_detail=f"相关性矩阵: {len(payload.symbols)}只股票"
    )
    return result

@router.post("/risk/metrics")
def get_metrics(
    payload: RiskMetricsRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """综合风险指标：年化波动率、最大回撤、累计收益、夏普/索提诺/卡玛比率"""
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="请至少选择一只股票")
    result = compute_risk_metrics(
        session,
        symbols=payload.symbols,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    log_user_action(
        session,
        user_id=user.id,
        action_type="risk_metrics",
        action_detail=f"风险指标计算: {len(payload.symbols)}只股票"
    )
    return result

@router.post("/risk/rolling_beta")
def get_rolling_beta(
    payload: RiskRollingBetaRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """滚动Beta时间序列"""
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="请至少选择一只股票")
    result = compute_rolling_beta(
        session,
        symbols=payload.symbols,
        benchmark_code=payload.benchmark_code,
        start_date=payload.start_date,
        end_date=payload.end_date,
        window=payload.window,
    )
    log_user_action(
        session,
        user_id=user.id,
        action_type="risk_rolling_beta",
        action_detail=f"滚动Beta: {len(payload.symbols)}只股票, 窗口{payload.window}天"
    )
    return result

@router.post("/risk/all")
def get_all_risk(
    payload: RiskAllRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """一键获取所有风险指标（VaR + Beta/Alpha + 相关性 + 综合指标 + 滚动Beta）"""
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="请至少选择一只股票")
    result = compute_all_risk_metrics(
        session,
        symbols=payload.symbols,
        benchmark_code=payload.benchmark_code,
        start_date=payload.start_date,
        end_date=payload.end_date,
        confidence_levels=payload.confidence_levels,
        holding_period=payload.holding_period,
        rolling_window=payload.rolling_window,
    )
    log_user_action(
        session,
        user_id=user.id,
        action_type="risk_all",
        action_detail=f"综合风险分析: {len(payload.symbols)}只股票, 基准{payload.benchmark_code}"
    )
    return result


# ==================== 智能选股推荐接口 ====================

def _convert_score_result_to_item(result) -> StockScoreItem:
    """将评分结果转换为API响应格式"""
    return StockScoreItem(
        symbol=result.symbol,
        name=result.name,
        industry=result.industry,
        total_score=round(result.total_score, 4),
        max_possible_score=round(result.max_possible_score, 4),
        normalized_score=round(result.normalized_score, 4),
        rule_details=[
            {
                "rule_id": rd.rule_id,
                "name": rd.name,
                "raw_value": round(rd.raw_value, 4),
                "score": round(rd.score, 4),
                "weight": round(rd.weight, 4),
                "weighted_score": round(rd.weighted_score, 4),
                "enabled": rd.enabled,
            }
            for rd in result.rule_details
        ],
    )


@router.get("/recommend/rules", response_model=ScoringRuleListResponse)
def get_scoring_rules():
    """获取所有评分规则信息"""
    rules = get_default_rules()
    return {
        "rules": [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "description": r.description,
                "default_weight": r.default_weight,
                "min_value": r.min_value,
                "max_value": r.max_value,
                "optimal_min": r.optimal_min,
                "optimal_max": r.optimal_max,
                "unit": r.unit,
            }
            for r in rules
        ]
    }


@router.post("/recommend/top", response_model=RecommendationResponse)
def get_top_recommendations(
    payload: RecommendationRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """获取默认评分卡的 Top-N 推荐"""
    cache_key = f"recommend:top:{json.dumps(payload.dict(), ensure_ascii=False)}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    results = get_top_n_recommendations(
        session,
        n=payload.n,
        weights=payload.weights,
        enabled_rules=payload.enabled_rules,
        industry_filter=payload.industry_filter,
    )

    items = [_convert_score_result_to_item(r) for r in results]
    response = {"total": len(items), "items": items}
    cache_set(cache_key, response, ttl=120)

    log_user_action(
        session,
        user_id=user.id,
        action_type="recommend_top",
        action_detail=f"获取Top-{payload.n}推荐, 命中{len(items)}只股票"
    )
    return response


@router.post("/recommend/custom", response_model=RecommendationResponse)
def get_custom_score_recommendations(
    payload: CustomScoreRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """自定义权重实时评分"""
    weights = payload.weights
    enabled_rules = payload.enabled_rules

    if payload.rule_configs:
        weights = {rc.rule_id: rc.weight for rc in payload.rule_configs}
        enabled_rules = {rc.rule_id: rc.enabled for rc in payload.rule_configs}

    results = get_top_n_recommendations(
        session,
        n=payload.n,
        weights=weights,
        enabled_rules=enabled_rules,
    )

    items = [_convert_score_result_to_item(r) for r in results]
    response = {"total": len(items), "items": items}

    log_user_action(
        session,
        user_id=user.id,
        action_type="recommend_custom",
        action_detail=f"自定义权重评分, 返回{len(items)}只股票"
    )
    return response


@router.get("/recommend/stock/{symbol}", response_model=StockScoreItem)
def get_stock_detail_score(
    symbol: str,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """获取指定股票的评分明细"""
    weights_param = None
    enabled_param = None

    result = get_stock_score_detail(session, symbol, weights_param, enabled_param)
    if not result:
        raise HTTPException(status_code=404, detail="股票不存在或无评分数据")

    log_user_action(
        session,
        user_id=user.id,
        action_type="recommend_stock_detail",
        action_detail=f"查看股票{symbol}评分明细"
    )
    return _convert_score_result_to_item(result)


@router.post("/recommend/stock/{symbol}", response_model=StockScoreItem)
def get_stock_detail_score_custom(
    symbol: str,
    payload: CustomScoreRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """使用自定义权重获取指定股票的评分明细"""
    weights = payload.weights
    enabled_rules = payload.enabled_rules

    if payload.rule_configs:
        weights = {rc.rule_id: rc.weight for rc in payload.rule_configs}
        enabled_rules = {rc.rule_id: rc.enabled for rc in payload.rule_configs}

    result = get_stock_score_detail(session, symbol, weights, enabled_rules)
    if not result:
        raise HTTPException(status_code=404, detail="股票不存在或无评分数据")

    return _convert_score_result_to_item(result)


@router.get("/recommend/cards", response_model=ScoringCardListResponse)
def list_scoring_cards(
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """获取用户的评分卡方案列表"""
    query = select(ScoringCardPreset).where(ScoringCardPreset.user_id == user.id).order_by(
        ScoringCardPreset.is_default.desc(), ScoringCardPreset.updated_at.desc()
    )
    presets = session.exec(query).all()

    items = []
    for p in presets:
        items.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "weights": json.loads(p.weights_json),
            "enabled_rules": json.loads(p.enabled_rules_json) if p.enabled_rules_json else {},
            "is_default": p.is_default,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        })

    return {"total": len(items), "items": items}


@router.post("/recommend/cards", response_model=ScoringCardInfo)
def save_scoring_card(
    payload: ScoringCardSaveRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """保存评分卡方案"""
    existing = session.exec(
        select(ScoringCardPreset).where(
            ScoringCardPreset.user_id == user.id,
            ScoringCardPreset.name == payload.name,
        )
    ).first()

    if existing:
        existing.description = payload.description
        existing.weights_json = json.dumps(payload.weights, ensure_ascii=False)
        existing.enabled_rules_json = json.dumps(payload.enabled_rules, ensure_ascii=False)
        existing.updated_at = datetime.utcnow()
        preset = existing
        action = "更新"
    else:
        preset = ScoringCardPreset(
            user_id=user.id,
            name=payload.name,
            description=payload.description,
            weights_json=json.dumps(payload.weights, ensure_ascii=False),
            enabled_rules_json=json.dumps(payload.enabled_rules, ensure_ascii=False),
            is_default=payload.is_default,
        )
        session.add(preset)
        action = "创建"

    if payload.is_default:
        other_defaults = session.exec(
            select(ScoringCardPreset).where(
                ScoringCardPreset.user_id == user.id,
                ScoringCardPreset.id != preset.id,
                ScoringCardPreset.is_default == True,
            )
        ).all()
        for d in other_defaults:
            d.is_default = False

    session.commit()
    session.refresh(preset)

    log_user_action(
        session,
        user_id=user.id,
        action_type="recommend_save_card",
        action_detail=f"{action}评分卡方案: {payload.name}"
    )

    return {
        "id": preset.id,
        "name": preset.name,
        "description": preset.description,
        "weights": json.loads(preset.weights_json),
        "enabled_rules": json.loads(preset.enabled_rules_json) if preset.enabled_rules_json else {},
        "is_default": preset.is_default,
        "created_at": preset.created_at,
        "updated_at": preset.updated_at,
    }


@router.get("/recommend/cards/{card_id}", response_model=ScoringCardInfo)
def load_scoring_card(
    card_id: int,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """加载评分卡方案"""
    preset = session.exec(
        select(ScoringCardPreset).where(
            ScoringCardPreset.id == card_id,
            ScoringCardPreset.user_id == user.id,
        )
    ).first()

    if not preset:
        raise HTTPException(status_code=404, detail="评分卡方案不存在")

    log_user_action(
        session,
        user_id=user.id,
        action_type="recommend_load_card",
        action_detail=f"加载评分卡方案: {preset.name}"
    )

    return {
        "id": preset.id,
        "name": preset.name,
        "description": preset.description,
        "weights": json.loads(preset.weights_json),
        "enabled_rules": json.loads(preset.enabled_rules_json) if preset.enabled_rules_json else {},
        "is_default": preset.is_default,
        "created_at": preset.created_at,
        "updated_at": preset.updated_at,
    }


@router.delete("/recommend/cards/{card_id}")
def delete_scoring_card(
    card_id: int,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    """删除评分卡方案"""
    preset = session.exec(
        select(ScoringCardPreset).where(
            ScoringCardPreset.id == card_id,
            ScoringCardPreset.user_id == user.id,
        )
    ).first()

    if not preset:
        raise HTTPException(status_code=404, detail="评分卡方案不存在")

    session.delete(preset)
    session.commit()

    log_user_action(
        session,
        user_id=user.id,
        action_type="recommend_delete_card",
        action_detail=f"删除评分卡方案: {preset.name}"
    )

    return {"status": "ok"}
