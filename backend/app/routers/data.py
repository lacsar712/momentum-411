from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import select, func, distinct
import pandas as pd

from app.routers.deps import session_dep
from app.models import Stock, DailyPrice, DataSyncLog, BacktestResult, ScreeningPreset
from app.schemas import DailyDataRequest, PriceRangeRequest, DateRangeRequest
from app.services.data_sync import validate_integrity
from app.services.concept import (
    get_concept_list,
    get_concept_detail,
    get_concept_constituents,
    get_concept_leaderboard,
    get_stock_concepts,
    get_related_concepts,
)
from datetime import date as date_type
from app.services.index_service import (
    get_index_list,
    get_index_history,
    get_index_compare,
    get_index_constituents,
    get_index_detail,
)

router = APIRouter(prefix="/api/v1")


@router.get("/stocks")
def list_stocks(keyword: str = "", limit: int = 20, offset: int = 0, session=Depends(session_dep)):
    query = select(Stock)
    if keyword:
        query = query.where(Stock.symbol.contains(keyword) | Stock.name.contains(keyword))

    all_results = session.exec(query).all()
    total = len(all_results)

    stocks = session.exec(query.offset(offset).limit(limit)).all()
    return {"total": total, "items": [s.dict() for s in stocks]}


@router.get("/stocks/query")
def search_stocks(keyword: str = "", limit: int = 20, offset: int = 0, session=Depends(session_dep)):
    query = select(Stock)
    if keyword:
        query = query.where(Stock.symbol.contains(keyword) | Stock.name.contains(keyword))

    total = len(session.exec(query).all())
    stocks = session.exec(query.offset(offset).limit(limit)).all()
    return {"total": total, "items": [s.dict() for s in stocks]}


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

    sync_log = session.exec(select(DataSyncLog).where(DataSyncLog.created_at >= today, DataSyncLog.data_source == "akshare").limit(1)).first()
    sync_done = sync_log is not None

    backtest_log = session.exec(select(BacktestResult).where(BacktestResult.created_at >= today).limit(1)).first()
    backtest_done = backtest_log is not None

    tasks = [
        {"id": 1, "text": "完成全市场增量数据同步", "completed": sync_done},
        {"id": 2, "text": "执行每日策略回测验证", "completed": backtest_done},
        {"id": 3, "text": "导出最新选股结果清单", "completed": False}
    ]
    return tasks


@router.get("/dashboard/market_cap")
def get_market_cap_distribution(session=Depends(session_dep)):
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


@router.get("/index/list")
def list_indices(
    keyword: str = "",
    index_type: str | None = Query(None, pattern="^(index|etf)$"),
    sort_by: str = Query("name", pattern="^(name|code|daily_change|five_day_change|latest_amount)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    session=Depends(session_dep),
):
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
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if len(code_list) < 2:
        raise HTTPException(status_code=400, detail="至少选择2个指数/ETF进行对比")
    if len(code_list) > 4:
        raise HTTPException(status_code=400, detail="最多支持4个指数/ETF同时对比")
    return get_index_compare(session, code_list, start_date=start_date, base_method=base_method)


@router.get("/index/constituents/{code}")
def index_constituents(code: str, session=Depends(session_dep)):
    result = get_index_constituents(session, code)
    if result is None:
        raise HTTPException(status_code=404, detail="指数/ETF不存在")
    return result


from fastapi import HTTPException
