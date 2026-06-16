import io
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import select
import pandas as pd

from app.routers.deps import session_dep, auth_dep
from app.models import Stock, DailyPrice
from app.schemas import ExportRequest

router = APIRouter(prefix="/api/v1")


@router.post("/export")
def export_data(payload: ExportRequest, session=Depends(session_dep), user=Depends(auth_dep)):
    symbols = payload.symbols or [s.symbol for s in session.exec(select(Stock)).all()]
    stocks = session.exec(select(Stock).where(Stock.symbol.in_(symbols))).all()
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
