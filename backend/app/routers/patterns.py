import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.routers.deps import session_dep, auth_dep
from app.models import Stock, DailyPrice, PatternResult
from app.schemas import PatternScanRequest
from app.services.patterns import detect_patterns, PATTERN_NAMES
from app.services.notification import create_notification
from app.services.auth import log_user_action

router = APIRouter(prefix="/api/v1")


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
