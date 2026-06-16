from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlmodel import select

from app.routers.deps import session_dep, require_permission, auth_dep
from app.services.task_manager import task_manager
from app.models import Stock, IndexProduct
from app.schemas import DateRangeRequest
from app.services.auth import log_user_action

router = APIRouter(prefix="/api/v1")


@router.get("/data/sync/progress")
def get_sync_progress():
    return task_manager.get_state()


@router.post("/data/sync/stocks")
def sync_stocks(background_tasks: BackgroundTasks, session=Depends(session_dep), user=Depends(require_permission("data.sync"))):
    if task_manager.is_running():
        raise HTTPException(status_code=400, detail="Task already running")
    background_tasks.add_task(task_manager.run_sync_stock_list_task, user.id)
    log_user_action(session, user_id=user.id, action_type="run_sync", action_detail="启动股票清单同步")
    return {"status": "started", "message": "Stock sync started in background"}


@router.post("/data/sync/daily")
def sync_daily_data(payload: DateRangeRequest, background_tasks: BackgroundTasks, session=Depends(session_dep), user=Depends(require_permission("data.sync"))):
    if task_manager.is_running():
        raise HTTPException(status_code=400, detail="Task already running")

    symbols = payload.symbols or [s.symbol for s in session.exec(select(Stock)).all()]
    if not symbols:
        raise HTTPException(status_code=400, detail="无可同步股票")

    background_tasks.add_task(task_manager.run_sync_daily_task, symbols, payload.start_date, payload.end_date, payload.sync_type, user.id)
    log_user_action(
        session,
        user_id=user.id,
        action_type="run_sync",
        action_detail=f"启动日线数据同步: {len(symbols)}只股票, {payload.start_date}~{payload.end_date}"
    )
    return {"status": "started", "count": len(symbols)}


@router.post("/data/snapshot/update")
def update_snapshots(background_tasks: BackgroundTasks, session=Depends(session_dep), user=Depends(require_permission("data.sync"))):
    if task_manager.is_running():
        raise HTTPException(status_code=400, detail="Task already running")
    background_tasks.add_task(task_manager.run_snapshot_update_task, user.id)
    log_user_action(session, user_id=user.id, action_type="run_sync", action_detail="启动快照更新")
    return {"status": "started", "message": "Snapshot update started"}


@router.post("/data/sync/index/products")
def sync_index_products(background_tasks: BackgroundTasks, session=Depends(session_dep), user=Depends(require_permission("data.sync"))):
    if task_manager.is_running():
        raise HTTPException(status_code=400, detail="Task already running")
    background_tasks.add_task(task_manager.run_sync_index_list_task, user.id)
    log_user_action(session, user_id=user.id, action_type="run_sync", action_detail="启动指数/ETF产品同步")
    return {"status": "started", "message": "Index products sync started"}


@router.post("/data/sync/index/daily")
def sync_index_daily_data(
    background_tasks: BackgroundTasks,
    payload: DateRangeRequest,
    session=Depends(session_dep),
    user=Depends(require_permission("data.sync")),
):
    if task_manager.is_running():
        raise HTTPException(status_code=400, detail="Task already running")

    codes = payload.symbols or [p.code for p in session.exec(select(IndexProduct)).all()]
    if not codes:
        raise HTTPException(status_code=400, detail="无可同步指数/ETF")

    background_tasks.add_task(task_manager.run_sync_index_daily_task, codes, payload.start_date, payload.end_date, payload.sync_type, user.id)
    log_user_action(
        session,
        user_id=user.id,
        action_type="run_sync",
        action_detail=f"启动指数/ETF日线同步: {len(codes)}个产品, {payload.start_date}~{payload.end_date}"
    )
    return {"status": "started", "count": len(codes), "codes": codes}
