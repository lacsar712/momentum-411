import pandas as pd
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
from sqlmodel import select, func
from app.models import IndexProduct, IndexDailyPrice, Stock, DailyPrice
from app.services.index_sync import sync_index_constituents

def get_index_list(
    session,
    keyword: str = "",
    index_type: str | None = None,
    sort_by: str = "name",
    sort_order: str = "asc",
):
    """获取指数/ETF列表，附带当日表现"""
    query = select(IndexProduct)
    if keyword:
        query = query.where(
            IndexProduct.code.contains(keyword) | IndexProduct.name.contains(keyword)
        )
    if index_type:
        query = query.where(IndexProduct.index_type == index_type)
    
    products = session.exec(query).all()
    
    results = []
    for product in products:
        daily_change, five_day_change, latest_data = _calculate_index_returns(session, product.id)
        
        results.append({
            "id": product.id,
            "code": product.code,
            "name": product.name,
            "index_type": product.index_type,
            "tracking_target": product.tracking_target,
            "list_date": product.list_date.isoformat() if product.list_date else None,
            "daily_change": daily_change,
            "five_day_change": five_day_change,
            "latest_close": latest_data["close"] if latest_data else None,
            "latest_volume": latest_data["volume"] if latest_data else None,
            "latest_amount": latest_data["amount"] if latest_data else None,
        })
    
    reverse = sort_order == "desc"
    if sort_by == "name":
        results.sort(key=lambda x: x["name"], reverse=reverse)
    elif sort_by == "code":
        results.sort(key=lambda x: x["code"], reverse=reverse)
    elif sort_by == "daily_change":
        results.sort(key=lambda x: x["daily_change"] if x["daily_change"] is not None else float("-inf"), reverse=reverse)
    elif sort_by == "five_day_change":
        results.sort(key=lambda x: x["five_day_change"] if x["five_day_change"] is not None else float("-inf"), reverse=reverse)
    elif sort_by == "latest_amount":
        results.sort(key=lambda x: x["latest_amount"] if x["latest_amount"] is not None else 0, reverse=reverse)
    
    return results

def get_index_history(
    session,
    code: str,
    start: date | None = None,
    end: date | None = None,
    limit: int | None = None,
):
    """获取指数/ETF历史K线数据"""
    product = session.exec(
        select(IndexProduct).where(IndexProduct.code == code)
    ).first()
    if not product:
        return None
    
    query = select(IndexDailyPrice).where(IndexDailyPrice.index_id == product.id)
    if start:
        query = query.where(IndexDailyPrice.trade_date >= start)
    if end:
        query = query.where(IndexDailyPrice.trade_date <= end)
    query = query.order_by(IndexDailyPrice.trade_date)
    if limit:
        query = query.limit(limit)
    
    prices = session.exec(query).all()
    
    df = pd.DataFrame([p.dict() for p in prices]) if prices else pd.DataFrame()
    
    results = []
    if not df.empty:
        df = df.sort_values("trade_date")
        close = df["close"]
        df["ma5"] = close.rolling(5).mean()
        df["ma10"] = close.rolling(10).mean()
        df["ma20"] = close.rolling(20).mean()
        df["ma60"] = close.rolling(60).mean()
        
        for _, row in df.iterrows():
            td = row["trade_date"]
            if hasattr(td, "isoformat"):
                td_str = td.isoformat()
            else:
                td_str = str(td)
            results.append({
                "trade_date": td_str,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "amount": float(row["amount"]) if pd.notna(row.get("amount")) else None,
                "ma5": float(row["ma5"]) if pd.notna(row["ma5"]) else None,
                "ma10": float(row["ma10"]) if pd.notna(row["ma10"]) else None,
                "ma20": float(row["ma20"]) if pd.notna(row["ma20"]) else None,
                "ma60": float(row["ma60"]) if pd.notna(row["ma60"]) else None,
            })
    
    return {
        "code": product.code,
        "name": product.name,
        "index_type": product.index_type,
        "tracking_target": product.tracking_target,
        "list_date": product.list_date.isoformat() if product.list_date else None,
        "total": len(results),
        "items": results,
    }

def get_index_compare(
    session,
    codes: List[str],
    start_date: date | None = None,
    base_method: str = "first",
):
    """
    多指数归一化对比序列
    
    Args:
        base_method: first(首日基准=100) / ytd(年初) / y-1(一年前) / custom(指定start_date)
    """
    from datetime import datetime as dt
    
    products = session.exec(
        select(IndexProduct).where(IndexProduct.code.in_(codes))
    ).all()
    if not products:
        return {"items": [], "stats": []}
    
    product_map = {p.code: p for p in products}
    
    all_data = {}
    date_set = set()
    latest_date_overall = None
    
    for code in codes:
        product = product_map.get(code)
        if not product:
            continue
        
        query = select(IndexDailyPrice).where(IndexDailyPrice.index_id == product.id)
        query = query.order_by(IndexDailyPrice.trade_date)
        prices = session.exec(query).all()
        if not prices:
            continue
        
        df = pd.DataFrame([{
            "trade_date": p.trade_date,
            "close": float(p.close),
        } for p in prices])
        df = df.sort_values("trade_date")
        
        all_data[code] = df
        date_set.update(df["trade_date"].tolist())
        if latest_date_overall is None or df["trade_date"].max() > latest_date_overall:
            latest_date_overall = df["trade_date"].max()
    
    if not all_data or latest_date_overall is None:
        return {"items": [], "stats": []}
    
    if base_method == "ytd":
        start_date = date(latest_date_overall.year, 1, 1)
    elif base_method == "y-1":
        start_date = latest_date_overall - timedelta(days=365)
    elif base_method == "first" or start_date is None:
        start_date = min(df["trade_date"].min() for df in all_data.values())
    
    normalized = {}
    common_dates = sorted([d for d in date_set if d >= start_date])
    
    for code, df in all_data.items():
        df_filtered = df[df["trade_date"] >= start_date].copy()
        if df_filtered.empty:
            continue
        
        base_value = df_filtered.iloc[0]["close"]
        if base_value == 0:
            continue
        
        df_filtered["norm"] = df_filtered["close"] / base_value * 100
        price_dict = dict(zip(df_filtered["trade_date"], df_filtered["norm"]))
        series = []
        for d in common_dates:
            if d in price_dict:
                series.append({"trade_date": d.isoformat(), "value": round(price_dict[d], 4)})
            else:
                series.append({"trade_date": d.isoformat(), "value": None})
        
        normalized[code] = {
            "name": product_map[code].name,
            "index_type": product_map[code].index_type,
            "series": series,
        }
    
    stats = []
    for code, data in normalized.items():
        series_values = [s["value"] for s in data["series"] if s["value"] is not None]
        if not series_values:
            continue
        
        total_return = series_values[-1] - 100
        peak = max(series_values)
        trough = min(series_values)
        max_drawdown = 0
        peak_so_far = series_values[0]
        for v in series_values:
            if v > peak_so_far:
                peak_so_far = v
            dd = (v - peak_so_far) / peak_so_far * 100
            if dd < max_drawdown:
                max_drawdown = dd
        
        daily_returns = []
        for i in range(1, len(series_values)):
            if series_values[i-1] and series_values[i]:
                daily_returns.append((series_values[i] - series_values[i-1]) / series_values[i-1])
        
        volatility = (pd.Series(daily_returns).std() * (252 ** 0.5) * 100) if daily_returns else 0
        sharpe = (total_return / volatility) if volatility > 0 else 0
        
        stats.append({
            "code": code,
            "name": data["name"],
            "index_type": data["index_type"],
            "start_date": common_dates[0].isoformat() if common_dates else None,
            "end_date": common_dates[-1].isoformat() if common_dates else None,
            "total_return": round(total_return, 2),
            "max_drawdown": round(max_drawdown, 2),
            "volatility": round(volatility, 2),
            "sharpe": round(sharpe, 2),
            "peak": round(peak - 100, 2),
            "trough": round(trough - 100, 2),
        })
    
    return {
        "items": [{"code": code, **data} for code, data in normalized.items()],
        "stats": stats,
        "dates": [d.isoformat() for d in common_dates],
    }

def get_index_constituents(session, code: str):
    """获取指数成分股"""
    product = session.exec(
        select(IndexProduct).where(IndexProduct.code == code)
    ).first()
    if not product:
        return None
    
    constituents = sync_index_constituents(session, code)
    if constituents is None:
        return None
    
    all_stocks = session.exec(select(Stock)).all()
    stock_map = {s.symbol: s for s in all_stocks}
    
    latest_date = session.exec(
        select(func.max(DailyPrice.trade_date))
    ).one()
    
    results = []
    for c in constituents:
        symbol = c["symbol"]
        stock = stock_map.get(symbol)
        
        daily_change = None
        latest_price = None
        
        if stock and latest_date:
            prev_date = _get_previous_trade_date(session, stock.id, latest_date)
            if prev_date:
                prev_price = session.exec(
                    select(DailyPrice).where(
                        DailyPrice.stock_id == stock.id,
                        DailyPrice.trade_date == prev_date,
                    )
                ).first()
                curr_price = session.exec(
                    select(DailyPrice).where(
                        DailyPrice.stock_id == stock.id,
                        DailyPrice.trade_date == latest_date,
                    )
                ).first()
                if prev_price and curr_price and prev_price.close != 0:
                    daily_change = round((curr_price.close - prev_price.close) / prev_price.close * 100, 2)
                    latest_price = round(curr_price.close, 2)
        
        results.append({
            "symbol": symbol,
            "name": c["name"],
            "weight": c["weight"],
            "market": stock.market if stock else None,
            "industry": stock.industry if stock else None,
            "latest_price": latest_price,
            "daily_change": daily_change,
        })
    
    results.sort(key=lambda x: x["weight"] if x["weight"] is not None else 0, reverse=True)
    
    return {
        "code": product.code,
        "name": product.name,
        "index_type": product.index_type,
        "total": len(results),
        "items": results,
    }

def get_index_detail(session, code: str):
    """获取指数详情（含关键指标）"""
    product = session.exec(
        select(IndexProduct).where(IndexProduct.code == code)
    ).first()
    if not product:
        return None
    
    daily_change, five_day_change, latest_data = _calculate_index_returns(session, product.id)
    
    query = select(IndexDailyPrice).where(IndexDailyPrice.index_id == product.id)
    query = query.order_by(IndexDailyPrice.trade_date.desc()).limit(252)
    prices = session.exec(query).all()
    
    metrics = {}
    if prices and len(prices) >= 2:
        closes = [float(p.close) for p in reversed(prices)]
        s = pd.Series(closes)
        
        current = s.iloc[-1]
        ytd_start = date(prices[-1].trade_date.year, 1, 1) if hasattr(prices[-1].trade_date, "year") else None
        
        metrics = {
            "ytd_return": None,
            "year_return": None,
            "month_return": None,
            "week_return": None,
            "volatility_20d": None,
            "volatility_60d": None,
            "high_52w": None,
            "low_52w": None,
            "avg_volume_20d": None,
        }
        
        if len(s) >= 2:
            daily_ret = s.pct_change().dropna()
            if len(daily_ret) >= 20:
                metrics["volatility_20d"] = round(daily_ret.tail(20).std() * (252 ** 0.5) * 100, 2)
            if len(daily_ret) >= 60:
                metrics["volatility_60d"] = round(daily_ret.tail(60).std() * (252 ** 0.5) * 100, 2)
        
        if len(s) >= 5:
            metrics["week_return"] = round((s.iloc[-1] / s.iloc[-5] - 1) * 100, 2) if len(s) >= 5 else None
        if len(s) >= 22:
            metrics["month_return"] = round((s.iloc[-1] / s.iloc[-22] - 1) * 100, 2) if len(s) >= 22 else None
        if len(s) >= 252:
            metrics["year_return"] = round((s.iloc[-1] / s.iloc[0] - 1) * 100, 2)
            metrics["high_52w"] = round(s.max(), 2)
            metrics["low_52w"] = round(s.min(), 2)
        
        volumes = [float(p.volume) for p in reversed(prices)]
        if len(volumes) >= 20:
            metrics["avg_volume_20d"] = round(sum(volumes[-20:]) / 20, 0)
    
    return {
        "id": product.id,
        "code": product.code,
        "name": product.name,
        "index_type": product.index_type,
        "tracking_target": product.tracking_target,
        "list_date": product.list_date.isoformat() if product.list_date else None,
        "daily_change": daily_change,
        "five_day_change": five_day_change,
        "latest_close": latest_data["close"] if latest_data else None,
        "latest_high": latest_data["high"] if latest_data else None,
        "latest_low": latest_data["low"] if latest_data else None,
        "latest_open": latest_data["open"] if latest_data else None,
        "latest_volume": latest_data["volume"] if latest_data else None,
        "latest_amount": latest_data["amount"] if latest_data else None,
        "metrics": metrics,
    }

def _calculate_index_returns(session, index_id: int) -> Tuple[Optional[float], Optional[float], Optional[Dict]]:
    """计算指数的当日涨跌幅和5日累计涨跌幅"""
    latest_prices = session.exec(
        select(IndexDailyPrice)
        .where(IndexDailyPrice.index_id == index_id)
        .order_by(IndexDailyPrice.trade_date.desc())
        .limit(6)
    ).all()
    
    if not latest_prices or len(latest_prices) < 2:
        return None, None, None
    
    latest_prices = list(reversed(latest_prices))
    
    latest = latest_prices[-1]
    prev = latest_prices[-2]
    
    daily_change = None
    five_day_change = None
    
    if prev.close != 0:
        daily_change = round((latest.close - prev.close) / prev.close * 100, 2)
    
    if len(latest_prices) >= 6 and latest_prices[0].close != 0:
        five_day_change = round((latest.close - latest_prices[0].close) / latest_prices[0].close * 100, 2)
    
    latest_data = {
        "open": float(latest.open),
        "high": float(latest.high),
        "low": float(latest.low),
        "close": float(latest.close),
        "volume": float(latest.volume),
        "amount": float(latest.amount) if latest.amount is not None else None,
        "trade_date": latest.trade_date.isoformat(),
    }
    
    return daily_change, five_day_change, latest_data

def _get_previous_trade_date(session, stock_id: int, current_date: date) -> Optional[date]:
    result = session.exec(
        select(DailyPrice.trade_date)
        .where(DailyPrice.stock_id == stock_id, DailyPrice.trade_date < current_date)
        .order_by(DailyPrice.trade_date.desc())
        .limit(1)
    ).first()
    return result
