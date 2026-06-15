from datetime import date, datetime
import pandas as pd
from sqlmodel import select, func
from app.models import IndexProduct, IndexDailyPrice, DataSyncLog, Stock
from app.services.data_sources import (
    fetch_index_daily_akshare,
    fetch_etf_daily_akshare,
    fetch_index_constituents_akshare,
)

INDEX_PRESET = [
    {"code": "000300", "name": "沪深300", "index_type": "index", "tracking_target": None, "list_date": "2005-04-08"},
    {"code": "000016", "name": "上证50", "index_type": "index", "tracking_target": None, "list_date": "2004-01-02"},
    {"code": "399006", "name": "创业板指", "index_type": "index", "tracking_target": None, "list_date": "2010-06-01"},
    {"code": "000688", "name": "科创50", "index_type": "index", "tracking_target": None, "list_date": "2020-07-23"},
    {"code": "000905", "name": "中证500", "index_type": "index", "tracking_target": None, "list_date": "2007-01-15"},
    {"code": "000852", "name": "中证1000", "index_type": "index", "tracking_target": None, "list_date": "2014-10-17"},
    {"code": "000001", "name": "上证指数", "index_type": "index", "tracking_target": None, "list_date": "1991-07-15"},
    {"code": "399001", "name": "深证成指", "index_type": "index", "tracking_target": None, "list_date": "1995-01-23"},
    {"code": "510300", "name": "沪深300ETF", "index_type": "etf", "tracking_target": "000300", "list_date": "2012-05-28"},
    {"code": "510500", "name": "中证500ETF", "index_type": "etf", "tracking_target": "000905", "list_date": "2015-04-22"},
    {"code": "512000", "name": "券商ETF", "index_type": "etf", "tracking_target": "399975", "list_date": "2016-08-08"},
    {"code": "510050", "name": "上证50ETF", "index_type": "etf", "tracking_target": "000016", "list_date": "2005-02-23"},
    {"code": "159915", "name": "创业板ETF", "index_type": "etf", "tracking_target": "399006", "list_date": "2011-12-09"},
    {"code": "588000", "name": "科创50ETF", "index_type": "etf", "tracking_target": "000688", "list_date": "2020-09-28"},
    {"code": "512100", "name": "中证1000ETF", "index_type": "etf", "tracking_target": "000852", "list_date": "2022-07-22"},
]

def seed_index_products(session):
    """初始化指数与ETF产品数据"""
    if session.exec(select(IndexProduct)).first():
        return
    
    for item in INDEX_PRESET:
        list_date = None
        if item["list_date"]:
            try:
                list_date = datetime.strptime(item["list_date"], "%Y-%m-%d").date()
            except Exception:
                pass
        product = IndexProduct(
            code=item["code"],
            name=item["name"],
            index_type=item["index_type"],
            tracking_target=item["tracking_target"],
            list_date=list_date,
        )
        session.add(product)
    session.commit()
    print(f"[种子] 已初始化 {len(INDEX_PRESET)} 个指数/ETF产品")

def _log_sync(session, source: str, sync_type: str, start: date | None, end: date | None, status: str, message: str | None):
    session.add(DataSyncLog(
        data_source=source,
        sync_type=sync_type,
        start_date=start,
        end_date=end,
        status=status,
        message=message,
    ))
    session.commit()

def _delete_existing_index_prices(session, index_id: int, start: date, end: date):
    prices = session.exec(
        select(IndexDailyPrice).where(
            IndexDailyPrice.index_id == index_id,
            IndexDailyPrice.trade_date >= start,
            IndexDailyPrice.trade_date <= end,
        )
    ).all()
    for price in prices:
        session.delete(price)
    session.commit()

def sync_index_list(session, progress_callback=None):
    """同步指数与ETF产品列表（初始化）"""
    seed_index_products(session)
    count = len(session.exec(select(IndexProduct)).all())
    if progress_callback:
        progress_callback(count, count, f"已初始化 {count} 个指数/ETF产品")
    return count

def sync_index_daily(
    session,
    codes: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    sync_type: str = "incremental",
    progress_callback=None,
):
    """
    同步指数与ETF日线数据
    
    Args:
        session: 数据库会话
        codes: 指定代码列表，None表示所有
        start: 开始日期
        end: 结束日期
        sync_type: incremental(增量) / full(全量)
        progress_callback: 进度回调
    """
    from datetime import timedelta
    
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=365 * 5)
    
    query = select(IndexProduct)
    if codes:
        query = query.where(IndexProduct.code.in_(codes))
    products = session.exec(query).all()
    
    if not products:
        print("[同步] 无可用的指数/ETF产品")
        return 0
    
    total = len(products)
    count = 0
    
    for i, product in enumerate(products):
        if progress_callback:
            progress_callback(i, total, f"正在同步 {product.code} {product.name} ({i+1}/{total})")
        
        actual_start = start
        if sync_type == "incremental":
            last_date = session.exec(
                select(func.max(IndexDailyPrice.trade_date))
                .where(IndexDailyPrice.index_id == product.id)
            ).one()
            if last_date:
                actual_start = last_date + timedelta(days=1)
                if actual_start > end:
                    print(f"[同步] {product.code} 已是最新数据 (截至 {last_date})")
                    continue
        
        data = None
        try:
            if product.index_type == "index":
                data = fetch_index_daily_akshare(product.code, actual_start, end)
            elif product.index_type == "etf":
                data = fetch_etf_daily_akshare(product.code, actual_start, end)
            else:
                continue
            
            if data is None or data.empty:
                _log_sync(session, "akshare", sync_type, actual_start, end, "empty", f"{product.code}: 无数据")
                print(f"[同步] {product.code}: 无数据")
                continue
            
            _log_sync(session, "akshare", sync_type, actual_start, end, "success", f"{product.code}: {len(data)} 条")
            print(f"[同步] {product.code}: 获取 {len(data)} 条记录")
            
        except Exception as exc:
            _log_sync(session, "akshare", sync_type, actual_start, end, "failed", f"{product.code}: {str(exc)}")
            print(f"[同步] {product.code} 获取失败: {exc}")
            continue
        
        if sync_type == "full":
            _delete_existing_index_prices(session, product.id, actual_start, end)
        
        for _, row in data.iterrows():
            amount_val = row.get("amount", 0)
            session.add(IndexDailyPrice(
                index_id=product.id,
                trade_date=row["trade_date"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                amount=float(amount_val) if pd.notna(amount_val) else None,
            ))
        session.commit()
        count += len(data)
    
    if progress_callback:
        progress_callback(total, total, f"同步完成，共 {count} 条记录")
    
    return count

def sync_index_constituents(session, code: str):
    """同步指数成分股"""
    product = session.exec(
        select(IndexProduct).where(IndexProduct.code == code)
    ).first()
    if not product:
        return None
    
    df = fetch_index_constituents_akshare(code)
    if df.empty:
        return []
    
    results = []
    all_stocks = session.exec(select(Stock)).all() if not df.empty else []
    stock_map = {s.symbol: s for s in all_stocks}
    
    for _, row in df.iterrows():
        symbol = row["symbol"]
        stock = stock_map.get(symbol)
        results.append({
            "symbol": symbol,
            "name": row["name"],
            "weight": float(row["weight"]) if pd.notna(row.get("weight")) else None,
            "market": stock.market if stock else None,
            "industry": stock.industry if stock else None,
        })
    
    return results
