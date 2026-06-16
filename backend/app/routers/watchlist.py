from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.routers.deps import session_dep, auth_dep
from app.models import Stock, UserWatchlist, DailyPrice
from app.schemas import WatchlistAddRequest, WatchlistRemoveRequest, WatchlistResponse
from app.services.auth import log_user_action

router = APIRouter(prefix="/api/v1")


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
