"""
多维排行榜服务 - 跨多个市场维度的统一榜单
提供六类全市场排行接口 + 自定义维度接口
"""
from datetime import date, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from sqlmodel import Session, select, func
from sqlalchemy import text

from app.models import Stock, DailyPrice, StockSnapshot
from app.services.indicators import moving_average, rsi


MARKET_MAP = {
    "all": "全部",
    "sh": "沪市",
    "sz": "深市",
    "cyb": "创业板",
}

VALID_MARKETS = list(MARKET_MAP.keys())
VALID_PERIODS = [1, 5, 20]


def _filter_market_condition(market: str) -> Tuple[str, Dict[str, Any]]:
    """根据市场类型生成SQL过滤条件"""
    if market == "all":
        return "", {}
    elif market == "sh":
        return " AND s.market = :market", {"market": "SH"}
    elif market == "sz":
        return " AND s.market = :market AND s.symbol NOT LIKE '300%'", {"market": "SZ"}
    elif market == "cyb":
        return " AND s.symbol LIKE '300%'", {}
    return "", {}


def _get_latest_trade_date(session: Session) -> Optional[date]:
    """获取最新交易日"""
    latest = session.exec(
        select(DailyPrice.trade_date)
        .order_by(DailyPrice.trade_date.desc())
        .limit(1)
    ).first()
    return latest


def _get_price_data_for_period(
    session: Session,
    stock_id: int,
    end_date: date,
    days: int
) -> Optional[pd.DataFrame]:
    """获取指定股票在时间窗口内的价格数据"""
    start_date = end_date - timedelta(days=days * 2)
    prices = session.exec(
        select(DailyPrice)
        .where(DailyPrice.stock_id == stock_id)
        .where(DailyPrice.trade_date >= start_date)
        .where(DailyPrice.trade_date <= end_date)
        .order_by(DailyPrice.trade_date.desc())
        .limit(days + 5)
    ).all()
    
    if not prices or len(prices) < max(days, 2):
        return None
    
    prices_list = list(reversed(prices))
    df = pd.DataFrame([{
        "trade_date": p.trade_date,
        "open": p.open,
        "high": p.high,
        "low": p.low,
        "close": p.close,
        "volume": p.volume,
        "amount": p.amount if p.amount else 0,
    } for p in prices_list])
    
    return df.tail(days + 1) if len(df) > days else df


def _calculate_change_pct(df: pd.DataFrame, period: int) -> Optional[float]:
    """计算涨跌幅"""
    if len(df) < period + 1:
        return None
    start_close = df.iloc[-(period + 1)]["close"]
    end_close = df.iloc[-1]["close"]
    if start_close == 0:
        return None
    return (end_close - start_close) / start_close * 100


def _calculate_turnover_rate(df: pd.DataFrame, period: int, market_cap: Optional[float]) -> Optional[float]:
    """计算换手率（成交量 / 流通市值代理）"""
    if market_cap is None or market_cap == 0:
        return None
    if len(df) < period:
        return None
    recent = df.tail(period)
    avg_volume = recent["volume"].mean()
    price = recent.iloc[-1]["close"]
    if price == 0:
        return None
    turnover = (avg_volume * price) / market_cap * 100
    return turnover


def _calculate_amplitude(df: pd.DataFrame, period: int) -> Optional[float]:
    """计算振幅（高低差 / 前收盘）"""
    if len(df) < period + 1:
        return None
    recent = df.tail(period + 1)
    prev_close = recent.iloc[0]["close"]
    if prev_close == 0:
        return None
    high = recent.iloc[1:]["high"].max()
    low = recent.iloc[1:]["low"].min()
    return (high - low) / prev_close * 100


def _calculate_net_inflow(df: pd.DataFrame, period: int) -> Optional[float]:
    """计算资金净流入（基于成交额差分代理）"""
    if len(df) < period + 1:
        return None
    recent = df.tail(period + 1)
    amounts = recent["amount"].values
    changes = []
    for i in range(1, len(amounts)):
        price_change = (recent.iloc[i]["close"] - recent.iloc[i - 1]["close"]) / recent.iloc[i - 1]["close"]
        if price_change > 0:
            changes.append(amounts[i])
        else:
            changes.append(-amounts[i])
    return sum(changes[-period:]) / 100000000


def _check_strong_stock(df: pd.DataFrame) -> Tuple[bool, Optional[float], Optional[Dict[str, float]]]:
    """判断是否为强势股（RSI高 + 均线多头排列）"""
    if len(df) < 25:
        return False, None, None
    
    close_series = df["close"]
    rsi_val = float(rsi(close_series, window=14).iloc[-1]) if len(df) >= 14 else None
    
    ma5 = float(moving_average(close_series, 5).iloc[-1])
    ma10 = float(moving_average(close_series, 10).iloc[-1])
    ma20 = float(moving_average(close_series, 20).iloc[-1])
    
    ma_bullish = ma5 > ma10 > ma20
    rsi_strong = rsi_val is not None and rsi_val > 55
    
    is_strong = ma_bullish and rsi_strong
    
    ma_values = {"ma5": ma5, "ma10": ma10, "ma20": ma20}
    
    return is_strong, rsi_val, ma_values


def _calculate_strong_score(df: pd.DataFrame) -> float:
    """计算强势股综合得分"""
    is_strong, rsi_val, ma_values = _check_strong_stock(df)
    if not is_strong or rsi_val is None or ma_values is None:
        return 0.0
    
    rsi_score = min((rsi_val - 50) / 30, 1.0) * 50
    
    ma5, ma10, ma20 = ma_values["ma5"], ma_values["ma10"], ma_values["ma20"]
    if ma20 == 0:
        ma_score = 0
    else:
        ma_diff = ((ma5 - ma10) / ma20 + (ma10 - ma20) / ma20) * 100
        ma_score = min(ma_diff * 10, 50)
    
    return rsi_score + max(ma_score, 0)


def _get_market_distribution(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """计算市场分布饼图数据"""
    count_map: Dict[str, int] = {"SH": 0, "SZ": 0, "CYB": 0}
    for item in items:
        symbol = item.get("symbol", "")
        market = item.get("market", "")
        if symbol.startswith("300"):
            count_map["CYB"] += 1
        elif market == "SH":
            count_map["SH"] += 1
        else:
            count_map["SZ"] += 1
    
    return [
        {"name": "沪市", "value": count_map["SH"]},
        {"name": "深市", "value": count_map["SZ"]},
        {"name": "创业板", "value": count_map["CYB"]},
    ]


def get_leaderboard(
    session: Session,
    dimension: str,
    period: int = 1,
    market: str = "all",
    limit: int = 50,
) -> Dict[str, Any]:
    """
    获取指定维度的排行榜
    
    Args:
        session: 数据库会话
        dimension: 排行维度 (gain, loss, turnover, amplitude, inflow, strong)
        period: 时间窗口 (1, 5, 20)
        market: 市场 (all, sh, sz, cyb)
        limit: 返回数量上限
    
    Returns:
        排行榜数据，包含股票列表和市场分布
    """
    if period not in VALID_PERIODS:
        period = 1
    if market not in VALID_MARKETS:
        market = "all"
    
    latest_date = _get_latest_trade_date(session)
    if not latest_date:
        return {"items": [], "market_distribution": [], "total": 0, "latest_date": None}
    
    market_cond, market_params = _filter_market_condition(market)
    
    sql = f"""
        SELECT 
            s.id,
            s.symbol,
            s.name,
            s.market,
            s.industry,
            s.market_cap,
            snap.close as latest_close,
            snap.rsi,
            snap.latest_date
        FROM stock s
        LEFT JOIN stocksnapshot snap ON s.id = snap.stock_id
        WHERE 1=1 {market_cond}
        ORDER BY s.id
    """
    
    stocks = session.execute(text(sql), market_params).mappings().all()
    
    results = []
    for stock in stocks:
        try:
            df = _get_price_data_for_period(session, stock["id"], latest_date, max(period + 1, 25))
            if df is None or len(df) < period + 1:
                continue
            
            item = {
                "symbol": stock["symbol"],
                "name": stock["name"],
                "market": stock["market"],
                "industry": stock["industry"],
                "latest_price": float(df.iloc[-1]["close"]),
                "period": period,
            }
            
            if dimension == "gain":
                change_pct = _calculate_change_pct(df, period)
                if change_pct is None:
                    continue
                item["change_pct"] = round(change_pct, 2)
                item["sort_value"] = change_pct
            
            elif dimension == "loss":
                change_pct = _calculate_change_pct(df, period)
                if change_pct is None:
                    continue
                item["change_pct"] = round(change_pct, 2)
                item["sort_value"] = -change_pct
            
            elif dimension == "turnover":
                turnover = _calculate_turnover_rate(df, period, stock["market_cap"])
                if turnover is None:
                    continue
                item["turnover_rate"] = round(turnover, 2)
                item["change_pct"] = round(_calculate_change_pct(df, period) or 0, 2)
                item["sort_value"] = turnover
            
            elif dimension == "amplitude":
                amp = _calculate_amplitude(df, period)
                if amp is None:
                    continue
                item["amplitude"] = round(amp, 2)
                item["change_pct"] = round(_calculate_change_pct(df, period) or 0, 2)
                item["sort_value"] = amp
            
            elif dimension == "inflow":
                inflow = _calculate_net_inflow(df, period)
                if inflow is None:
                    continue
                item["net_inflow"] = round(inflow, 2)
                item["change_pct"] = round(_calculate_change_pct(df, period) or 0, 2)
                item["sort_value"] = inflow
            
            elif dimension == "strong":
                score = _calculate_strong_score(df)
                if score <= 0:
                    continue
                _, rsi_val, ma_values = _check_strong_stock(df)
                item["strong_score"] = round(score, 2)
                item["rsi"] = round(rsi_val, 2) if rsi_val else None
                item["ma5"] = round(ma_values["ma5"], 2) if ma_values else None
                item["ma10"] = round(ma_values["ma10"], 2) if ma_values else None
                item["ma20"] = round(ma_values["ma20"], 2) if ma_values else None
                item["change_pct"] = round(_calculate_change_pct(df, period) or 0, 2)
                item["sort_value"] = score
            
            sparkline_data = df.tail(min(period + 10, 20))[["trade_date", "close"]].to_dict("records")
            item["sparkline"] = [{"date": str(d["trade_date"]), "value": float(d["close"])} for d in sparkline_data]
            
            results.append(item)
            
        except Exception:
            continue
    
    results.sort(key=lambda x: x["sort_value"], reverse=True)
    results = results[:limit]
    
    for item in results:
        item.pop("sort_value", None)
    
    return {
        "items": results,
        "market_distribution": _get_market_distribution(results),
        "total": len(results),
        "latest_date": str(latest_date),
        "dimension": dimension,
        "period": period,
        "market": market,
    }


def get_custom_leaderboard(
    session: Session,
    sort_field: str,
    sort_order: str = "desc",
    market: str = "all",
    limit: int = 50,
) -> Dict[str, Any]:
    """
    自定义维度排行榜
    
    Args:
        session: 数据库会话
        sort_field: 排序字段 (close, volume, market_cap, pe_ratio, pb_ratio, rsi, momentum, volatility, liquidity)
        sort_order: 排序方向 (asc, desc)
        market: 市场过滤
        limit: 返回数量
    """
    valid_fields = [
        "close", "volume", "market_cap", "pe_ratio", "pb_ratio",
        "rsi", "macd_hist", "kdj_k", "kdj_j", "momentum", "volatility", "liquidity"
    ]
    
    if sort_field not in valid_fields:
        sort_field = "close"
    if sort_order not in ["asc", "desc"]:
        sort_order = "desc"
    if market not in VALID_MARKETS:
        market = "all"
    
    market_cond, market_params = _filter_market_condition(market)
    
    field_map = {
        "close": "snap.close",
        "volume": "snap.volume",
        "market_cap": "s.market_cap",
        "pe_ratio": "s.pe_ratio",
        "pb_ratio": "s.pb_ratio",
        "rsi": "snap.rsi",
        "macd_hist": "snap.macd_hist",
        "kdj_k": "snap.kdj_k",
        "kdj_j": "snap.kdj_j",
        "momentum": "snap.momentum",
        "volatility": "snap.volatility",
        "liquidity": "snap.liquidity",
    }
    
    order_direction = "DESC" if sort_order == "desc" else "ASC"
    sort_sql = field_map[sort_field]
    
    sql = f"""
        SELECT 
            s.symbol,
            s.name,
            s.market,
            s.industry,
            s.market_cap,
            s.pe_ratio,
            s.pb_ratio,
            snap.close as latest_price,
            snap.volume,
            snap.rsi,
            snap.momentum,
            snap.volatility,
            snap.liquidity,
            snap.latest_date
        FROM stock s
        LEFT JOIN stocksnapshot snap ON s.id = snap.stock_id
        WHERE {sort_sql} IS NOT NULL {market_cond}
        ORDER BY {sort_sql} {order_direction}
        LIMIT :limit
    """
    
    params = {"limit": limit, **market_params}
    rows = session.execute(text(sql), params).mappings().all()
    
    items = []
    for row in rows:
        item = {
            "symbol": row["symbol"],
            "name": row["name"],
            "market": row["market"],
            "industry": row["industry"],
            "latest_price": float(row["latest_price"]) if row["latest_price"] else None,
            "market_cap": row["market_cap"],
            "pe_ratio": row["pe_ratio"],
            "pb_ratio": row["pb_ratio"],
            "rsi": row["rsi"],
            "momentum": row["momentum"],
            "volatility": row["volatility"],
            "liquidity": row["liquidity"],
            "sort_value": row[sort_field] if sort_field in row else None,
        }
        items.append(item)
    
    return {
        "items": items,
        "market_distribution": _get_market_distribution(items),
        "total": len(items),
        "sort_field": sort_field,
        "sort_order": sort_order,
        "market": market,
    }


LEADERBOARD_DIMENSIONS = [
    {"key": "gain", "name": "涨幅榜", "description": "当日/周期涨幅最大的股票"},
    {"key": "loss", "name": "跌幅榜", "description": "当日/周期跌幅最大的股票"},
    {"key": "turnover", "name": "换手率榜", "description": "成交量/流通市值，衡量交易活跃度"},
    {"key": "amplitude", "name": "振幅榜", "description": "高低差/前收盘，衡量价格波动"},
    {"key": "inflow", "name": "资金净流入榜", "description": "基于成交额差分代理的资金流向"},
    {"key": "strong", "name": "强势股榜", "description": "综合RSI高且均线多头排列"},
]
