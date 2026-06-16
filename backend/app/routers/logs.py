from fastapi import APIRouter, Depends
from sqlmodel import select
import pandas as pd

from app.routers.deps import session_dep, require_permission
from app.models import DataSyncLog
from app.schemas import LogDeleteRequest

router = APIRouter(prefix="/api/v1")


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
            query = query.where(DataSyncLog.created_at < payload.end_date + pd.Timedelta(days=1))

    logs = session.exec(query).all()
    count = len(logs)
    for log in logs:
        session.delete(log)
    session.commit()
    return {"status": "ok", "deleted": count}
