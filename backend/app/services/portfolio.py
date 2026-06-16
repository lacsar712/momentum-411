import math
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Tuple
import pandas as pd
import numpy as np
from sqlmodel import Session, select
from app.models import (
    Portfolio, PortfolioHolding, Stock, DailyPrice,
    IndexProduct, IndexDailyPrice
)
from app.services.backtest import compute_metrics

REBALANCE_FREQUENCY_MAP = {
    "daily": "D",
    "weekly": "W",
    "monthly": "M",
    "quarterly": "Q",
    "yearly": "Y",
}

def _enrich_holdings_with_market_data(
    session: Session, holdings: List[PortfolioHolding]
) -> List[Dict]:
    """为持仓列表补充名称、最新价、涨跌幅、当前权重"""
    symbols = [h.symbol for h in holdings]
    if not symbols:
        return []
    
    stocks = session.exec(
        select(Stock).where(Stock.symbol.in_(symbols))
    ).all()
    stock_map = {s.symbol: s for s in stocks}
    
    stock_ids = [s.id for s in stocks]
    latest_prices = {}
    if stock_ids:
        from app.services.snapshot_updater import StockSnapshot
        snapshots = session.exec(
            select(StockSnapshot).where(StockSnapshot.stock_id.in_(stock_ids))
        ).all()
        for snap in snapshots:
            stock_obj = session.get(Stock, snap.stock_id)
            if stock_obj:
                latest_prices[stock_obj.symbol] = {
                    "price": snap.close,
                    "date": snap.latest_date,
                }
        if not snapshots:
            for stock in stocks:
                price_row = session.exec(
                    select(DailyPrice)
                    .where(DailyPrice.stock_id == stock.id)
                    .order_by(DailyPrice.trade_date.desc())
                    .limit(2)
                ).all()
                if price_row:
                    latest = price_row[0]
                    prev = price_row[1] if len(price_row) > 1 else None
                    change = None
                    if prev and prev.close:
                        change = (latest.close - prev.close) / prev.close
                    latest_prices[stock.symbol] = {
                        "price": latest.close,
                        "date": latest.trade_date,
                        "daily_change": change,
                    }
    
    total_target = sum(h.target_weight for h in holdings)
    
    result = []
    total_current_value = 0.0
    value_map = {}
    
    for h in holdings:
        s = stock_map.get(h.symbol)
        price_info = latest_prices.get(h.symbol, {})
        current_value = (price_info.get("price") or 0) * (h.target_weight)
        value_map[h.symbol] = current_value
        total_current_value += current_value
        
        result.append({
            "id": h.id,
            "symbol": h.symbol,
            "name": s.name if s else h.symbol,
            "target_weight": h.target_weight,
            "latest_price": price_info.get("price"),
            "daily_change": price_info.get("daily_change"),
            "_value": current_value,
        })
    
    if total_current_value > 0:
        for item in result:
            current_w = (item["_value"] / total_current_value) * 100 if total_current_value > 0 else 0
            target = item["target_weight"]
            if total_target > 0 and abs(total_target - 100) > 0.01:
                target = (item["target_weight"] / total_target) * 100
            item["current_weight"] = round(current_w, 2)
            item["weight_deviation"] = round(current_w - target, 2)
            item.pop("_value", None)
    else:
        for item in result:
            item["current_weight"] = item["target_weight"]
            item["weight_deviation"] = 0.0
            item.pop("_value", None)
    
    return result


def validate_weights_sum(holdings_data: List[Dict]) -> Tuple[bool, float]:
    """校验权重总和是否为100%（允许±0.5%的误差）"""
    total = sum(h.get("target_weight", 0) for h in holdings_data)
    return abs(total - 100.0) <= 0.5, total


def get_portfolio_list(session: Session, user_id: int) -> List[Dict]:
    """获取用户组合列表"""
    portfolios = session.exec(
        select(Portfolio)
        .where(Portfolio.user_id == user_id)
        .order_by(Portfolio.updated_at.desc())
    ).all()
    
    result = []
    for p in portfolios:
        enriched_holdings = _enrich_holdings_with_market_data(session, p.holdings)
        result.append({
            "id": p.id,
            "user_id": p.user_id,
            "name": p.name,
            "description": p.description,
            "benchmark_code": p.benchmark_code or "000300",
            "rebalance_frequency": p.rebalance_frequency or "monthly",
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "holdings": enriched_holdings,
        })
    return result


def get_portfolio_detail(session: Session, portfolio_id: int, user_id: int) -> Optional[Dict]:
    """获取组合详情"""
    portfolio = session.exec(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    ).first()
    if not portfolio:
        return None
    
    enriched_holdings = _enrich_holdings_with_market_data(session, portfolio.holdings)
    return {
        "id": portfolio.id,
        "user_id": portfolio.user_id,
        "name": portfolio.name,
        "description": portfolio.description,
        "benchmark_code": portfolio.benchmark_code or "000300",
        "rebalance_frequency": portfolio.rebalance_frequency or "monthly",
        "created_at": portfolio.created_at,
        "updated_at": portfolio.updated_at,
        "holdings": enriched_holdings,
    }


def create_portfolio(
    session: Session,
    user_id: int,
    name: str,
    description: Optional[str],
    benchmark_code: str,
    rebalance_frequency: str,
    holdings_data: List[Dict],
) -> Tuple[Optional[Dict], Optional[str]]:
    """创建新组合"""
    existing = session.exec(
        select(Portfolio).where(Portfolio.name == name, Portfolio.user_id == user_id)
    ).first()
    if existing:
        return None, f"组合名称 '{name}' 已存在"
    
    if holdings_data:
        valid, total = validate_weights_sum(holdings_data)
        if not valid:
            return None, f"持仓权重总和应为100%，当前为 {total:.2f}%"
    
    now = datetime.utcnow()
    portfolio = Portfolio(
        user_id=user_id,
        name=name,
        description=description,
        benchmark_code=benchmark_code,
        rebalance_frequency=rebalance_frequency,
        created_at=now,
        updated_at=now,
    )
    session.add(portfolio)
    session.flush()
    
    for h_data in holdings_data:
        holding = PortfolioHolding(
            portfolio_id=portfolio.id,
            symbol=h_data["symbol"],
            target_weight=h_data["target_weight"],
            created_at=now,
            updated_at=now,
        )
        session.add(holding)
    
    session.commit()
    session.refresh(portfolio)
    
    return get_portfolio_detail(session, portfolio.id, user_id), None


def update_portfolio(
    session: Session,
    portfolio_id: int,
    user_id: int,
    update_data: Dict,
) -> Tuple[Optional[Dict], Optional[str]]:
    """更新组合基本信息"""
    portfolio = session.exec(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    ).first()
    if not portfolio:
        return None, "组合不存在"
    
    if "name" in update_data and update_data["name"] != portfolio.name:
        existing = session.exec(
            select(Portfolio).where(
                Portfolio.name == update_data["name"],
                Portfolio.user_id == user_id,
                Portfolio.id != portfolio_id,
            )
        ).first()
        if existing:
            return None, f"组合名称 '{update_data['name']}' 已存在"
        portfolio.name = update_data["name"]
    
    if "description" in update_data:
        portfolio.description = update_data["description"]
    if "benchmark_code" in update_data:
        portfolio.benchmark_code = update_data["benchmark_code"]
    if "rebalance_frequency" in update_data:
        portfolio.rebalance_frequency = update_data["rebalance_frequency"]
    
    portfolio.updated_at = datetime.utcnow()
    session.add(portfolio)
    session.commit()
    
    return get_portfolio_detail(session, portfolio.id, user_id), None


def copy_portfolio(
    session: Session,
    portfolio_id: int,
    user_id: int,
    new_name: str,
) -> Tuple[Optional[Dict], Optional[str]]:
    """复制组合"""
    source = session.exec(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    ).first()
    if not source:
        return None, "源组合不存在"
    
    existing = session.exec(
        select(Portfolio).where(Portfolio.name == new_name, Portfolio.user_id == user_id)
    ).first()
    if existing:
        return None, f"组合名称 '{new_name}' 已存在"
    
    now = datetime.utcnow()
    new_portfolio = Portfolio(
        user_id=user_id,
        name=new_name,
        description=f"{source.description or ''}（复制自 {source.name}）",
        benchmark_code=source.benchmark_code,
        rebalance_frequency=source.rebalance_frequency,
        created_at=now,
        updated_at=now,
    )
    session.add(new_portfolio)
    session.flush()
    
    for h in source.holdings:
        new_holding = PortfolioHolding(
            portfolio_id=new_portfolio.id,
            symbol=h.symbol,
            target_weight=h.target_weight,
            created_at=now,
            updated_at=now,
        )
        session.add(new_holding)
    
    session.commit()
    return get_portfolio_detail(session, new_portfolio.id, user_id), None


def delete_portfolio(
    session: Session, portfolio_id: int, user_id: int
) -> Tuple[bool, Optional[str]]:
    """删除组合"""
    portfolio = session.exec(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    ).first()
    if not portfolio:
        return False, "组合不存在"
    session.delete(portfolio)
    session.commit()
    return True, None


def batch_save_holdings(
    session: Session,
    portfolio_id: int,
    user_id: int,
    holdings_data: List[Dict],
) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """批量保存持仓（整体替换，校验权重总和）"""
    portfolio = session.exec(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    ).first()
    if not portfolio:
        return None, "组合不存在"
    
    if holdings_data:
        valid, total = validate_weights_sum(holdings_data)
        if not valid:
            return None, f"持仓权重总和应为100%，当前为 {total:.2f}%"
    
    for h in portfolio.holdings:
        session.delete(h)
    session.flush()
    
    now = datetime.utcnow()
    portfolio.updated_at = now
    session.add(portfolio)
    
    for h_data in holdings_data:
        holding = PortfolioHolding(
            portfolio_id=portfolio.id,
            symbol=h_data["symbol"],
            target_weight=h_data["target_weight"],
            created_at=now,
            updated_at=now,
        )
        session.add(holding)
    
    session.commit()
    session.refresh(portfolio)
    
    enriched = _enrich_holdings_with_market_data(session, portfolio.holdings)
    return enriched, None


def add_holding(
    session: Session,
    portfolio_id: int,
    user_id: int,
    symbol: str,
    target_weight: float,
) -> Tuple[Optional[Dict], Optional[str]]:
    """添加单个持仓"""
    portfolio = session.exec(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    ).first()
    if not portfolio:
        return None, "组合不存在"
    
    existing = session.exec(
        select(PortfolioHolding).where(
            PortfolioHolding.portfolio_id == portfolio_id,
            PortfolioHolding.symbol == symbol,
        )
    ).first()
    if existing:
        return None, f"股票 {symbol} 已在组合中"
    
    total_existing = sum(h.target_weight for h in portfolio.holdings)
    if total_existing + target_weight > 100.5:
        return None, f"权重总和将超过100%（当前 {total_existing:.2f}% + 新增 {target_weight:.2f}%）"
    
    stock = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
    if not stock:
        return None, f"股票 {symbol} 不存在"
    
    now = datetime.utcnow()
    holding = PortfolioHolding(
        portfolio_id=portfolio_id,
        symbol=symbol,
        target_weight=target_weight,
        created_at=now,
        updated_at=now,
    )
    session.add(holding)
    portfolio.updated_at = now
    session.add(portfolio)
    session.commit()
    
    enriched = _enrich_holdings_with_market_data(session, [holding])
    return enriched[0] if enriched else None, None


def update_holding(
    session: Session,
    portfolio_id: int,
    user_id: int,
    holding_id: int,
    target_weight: Optional[float],
) -> Tuple[Optional[Dict], Optional[str]]:
    """更新单个持仓权重"""
    portfolio = session.exec(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    ).first()
    if not portfolio:
        return None, "组合不存在"
    
    holding = session.get(PortfolioHolding, holding_id)
    if not holding or holding.portfolio_id != portfolio_id:
        return None, "持仓不存在"
    
    if target_weight is not None:
        others_total = sum(
            h.target_weight for h in portfolio.holdings if h.id != holding_id
        )
        if others_total + target_weight > 100.5:
            return None, f"权重总和将超过100%（其他 {others_total:.2f}% + 本仓 {target_weight:.2f}%）"
        holding.target_weight = target_weight
    
    holding.updated_at = datetime.utcnow()
    portfolio.updated_at = holding.updated_at
    session.add(holding)
    session.add(portfolio)
    session.commit()
    
    enriched = _enrich_holdings_with_market_data(session, [holding])
    return enriched[0] if enriched else None, None


def delete_holding(
    session: Session,
    portfolio_id: int,
    user_id: int,
    holding_id: int,
) -> Tuple[bool, Optional[str]]:
    """删除单个持仓"""
    portfolio = session.exec(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    ).first()
    if not portfolio:
        return False, "组合不存在"
    
    holding = session.get(PortfolioHolding, holding_id)
    if not holding or holding.portfolio_id != portfolio_id:
        return False, "持仓不存在"
    
    session.delete(holding)
    portfolio.updated_at = datetime.utcnow()
    session.add(portfolio)
    session.commit()
    return True, None


def _get_stock_price_series(
    session: Session, symbol: str, start: date, end: date
) -> Optional[pd.Series]:
    """获取单只股票的日收盘价格序列"""
    stock = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
    if not stock:
        return None
    rows = session.exec(
        select(DailyPrice)
        .where(
            DailyPrice.stock_id == stock.id,
            DailyPrice.trade_date >= start,
            DailyPrice.trade_date <= end,
        )
        .order_by(DailyPrice.trade_date)
    ).all()
    if not rows:
        return None
    df = pd.DataFrame([{"trade_date": r.trade_date, "close": r.close} for r in rows])
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.set_index("trade_date").sort_index()
    return df["close"]


def _get_index_price_series(
    session: Session, code: str, start: date, end: date
) -> Optional[pd.Series]:
    """获取指数的日收盘价格序列"""
    idx = session.exec(select(IndexProduct).where(IndexProduct.code == code)).first()
    if not idx:
        return None
    rows = session.exec(
        select(IndexDailyPrice)
        .where(
            IndexDailyPrice.index_id == idx.id,
            IndexDailyPrice.trade_date >= start,
            IndexDailyPrice.trade_date <= end,
        )
        .order_by(IndexDailyPrice.trade_date)
    ).all()
    if not rows:
        return None
    df = pd.DataFrame([{"trade_date": r.trade_date, "close": r.close} for r in rows])
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.set_index("trade_date").sort_index()
    return df["close"]


def _should_rebalance(current_date: pd.Timestamp, last_rebalance: Optional[pd.Timestamp], freq: str) -> bool:
    """判断当前日期是否需要再平衡"""
    if last_rebalance is None:
        return True
    delta = current_date - last_rebalance
    days = delta.days
    if freq == "daily":
        return days >= 1
    elif freq == "weekly":
        return days >= 5
    elif freq == "monthly":
        return (
            current_date.month != last_rebalance.month
            or current_date.year != last_rebalance.year
        )
    elif freq == "quarterly":
        curr_q = (current_date.month - 1) // 3
        last_q = (last_rebalance.month - 1) // 3
        return curr_q != last_q or current_date.year != last_rebalance.year
    elif freq == "yearly":
        return current_date.year != last_rebalance.year
    return False


def calculate_portfolio_nav(
    session: Session,
    portfolio_id: int,
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Tuple[Optional[Dict], Optional[str]]:
    """回算组合历史净值（按目标权重定期再平衡）"""
    portfolio = session.exec(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    ).first()
    if not portfolio:
        return None, "组合不存在"
    if not portfolio.holdings:
        return None, "组合暂无持仓"
    
    freq = portfolio.rebalance_frequency or "monthly"
    benchmark_code = portfolio.benchmark_code or "000300"
    
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=365)
    
    price_dict = {}
    symbols = []
    weights = []
    for h in portfolio.holdings:
        series = _get_stock_price_series(session, h.symbol, start_date, end_date)
        if series is None or series.empty:
            continue
        price_dict[h.symbol] = series
        symbols.append(h.symbol)
        weights.append(h.target_weight)
    
    if not symbols:
        return None, "持仓股票均无历史数据"
    
    weight_sum = sum(weights)
    weights = [w / weight_sum for w in weights]
    
    prices_df = pd.DataFrame(price_dict)
    prices_df = prices_df.dropna(how="all").fillna(method="ffill").fillna(method="bfill")
    prices_df = prices_df.sort_index()
    
    returns_df = prices_df.pct_change().fillna(0)
    
    benchmark_series = _get_index_price_series(session, benchmark_code, start_date, end_date)
    if benchmark_series is None or benchmark_series.empty:
        benchmark_series = pd.Series(1.0, index=prices_df.index)
    else:
        benchmark_series = benchmark_series.reindex(prices_df.index).fillna(method="ffill").fillna(method="bfill")
    benchmark_returns = benchmark_series.pct_change().fillna(0)
    
    nav = 1.0
    benchmark_nav = 1.0
    current_weights = np.array(weights)
    last_rebalance: Optional[pd.Timestamp] = None
    rebalance_count = 0
    
    nav_series = []
    bm_series = []
    dates = []
    
    for dt in prices_df.index:
        if _should_rebalance(dt, last_rebalance, freq):
            current_weights = np.array(weights)
            last_rebalance = dt
            rebalance_count += 1
        
        day_returns = returns_df.loc[dt, symbols].values if len(symbols) > 1 else returns_df.loc[dt, symbols]
        weighted_ret = float(np.dot(current_weights, day_returns))
        
        current_weights = current_weights * (1 + day_returns)
        weight_sum_today = current_weights.sum()
        if weight_sum_today > 0:
            current_weights = current_weights / weight_sum_today
        
        nav = nav * (1 + weighted_ret)
        benchmark_nav = benchmark_nav * (1 + benchmark_returns.loc[dt])
        
        nav_series.append(round(nav, 6))
        bm_series.append(round(benchmark_nav, 6))
        dates.append(dt.date())
    
    result_data = [
        {"trade_date": d, "portfolio_nav": n, "benchmark_nav": b}
        for d, n, b in zip(dates, nav_series, bm_series)
    ]
    
    return {
        "start_date": dates[0] if dates else start_date,
        "end_date": dates[-1] if dates else end_date,
        "rebalance_frequency": freq,
        "rebalance_count": rebalance_count,
        "data": result_data,
        "_nav_series": nav_series,
        "_bm_series": bm_series,
        "_dates": dates,
    }, None


def calculate_portfolio_metrics(
    session: Session,
    portfolio_id: int,
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Tuple[Optional[Dict], Optional[str]]:
    """计算组合关键指标"""
    nav_result, err = calculate_portfolio_nav(session, portfolio_id, user_id, start_date, end_date)
    if err:
        return None, err
    
    nav_series = pd.Series(nav_result["_nav_series"])
    bm_series = pd.Series(nav_result["_bm_series"])
    dates = nav_result["_dates"]
    
    portfolio_returns = nav_series.pct_change().fillna(0)
    benchmark_returns = bm_series.pct_change().fillna(0)
    
    pf_metrics = compute_metrics(portfolio_returns)
    bm_metrics = compute_metrics(benchmark_returns)
    
    n_days = len(dates)
    if n_days > 1:
        total_return = nav_series.iloc[-1] - 1
        bm_total_return = bm_series.iloc[-1] - 1
    else:
        total_return = 0.0
        bm_total_return = 0.0
    
    excess_returns = portfolio_returns - benchmark_returns
    tracking_error = excess_returns.std() * math.sqrt(252) if len(excess_returns) > 1 else 0.0
    information_ratio = (
        (pf_metrics["annual_return"] - bm_metrics["annual_return"]) / tracking_error
        if tracking_error > 1e-9
        else 0.0
    )
    
    if len(portfolio_returns) > 1 and len(benchmark_returns) > 1:
        correlation = portfolio_returns.corr(benchmark_returns)
        if pd.isna(correlation):
            correlation = 0.0
    else:
        correlation = 0.0
    
    volatility = portfolio_returns.std() * math.sqrt(252) if len(portfolio_returns) > 1 else 0.0
    bm_volatility = benchmark_returns.std() * math.sqrt(252) if len(benchmark_returns) > 1 else 0.0
    
    return {
        "annual_return": round(pf_metrics["annual_return"], 6),
        "benchmark_annual_return": round(bm_metrics["annual_return"], 6),
        "excess_return": round(pf_metrics["annual_return"] - bm_metrics["annual_return"], 6),
        "max_drawdown": round(pf_metrics["max_drawdown"], 6),
        "benchmark_max_drawdown": round(bm_metrics["max_drawdown"], 6),
        "sharpe_ratio": round(pf_metrics["sharpe"], 6),
        "information_ratio": round(information_ratio, 6),
        "correlation": round(correlation, 6),
        "total_return": round(total_return, 6),
        "benchmark_total_return": round(bm_total_return, 6),
        "volatility": round(volatility, 6),
        "benchmark_volatility": round(bm_volatility, 6),
    }, None


def get_rebalance_suggestions(
    session: Session,
    portfolio_id: int,
    user_id: int,
    threshold: float = 5.0,
    portfolio_value: float = 1000000.0,
) -> Tuple[Optional[Dict], Optional[str]]:
    """获取再平衡建议"""
    detail = get_portfolio_detail(session, portfolio_id, user_id)
    if not detail:
        return None, "组合不存在"
    
    holdings = detail["holdings"]
    if not holdings:
        return None, "组合暂无持仓"
    
    suggestions = []
    total_deviation = 0.0
    needs_rebalance = False
    
    for h in holdings:
        target = h["target_weight"]
        current = h.get("current_weight", target)
        deviation = current - target
        abs_dev = abs(deviation)
        total_deviation += abs_dev
        
        if abs_dev > threshold:
            needs_rebalance = True
            action = "买入" if deviation < 0 else "卖出"
            weight_diff = abs(deviation)
            suggested_amount = round(portfolio_value * weight_diff / 100, 2)
            suggestions.append({
                "symbol": h["symbol"],
                "name": h.get("name"),
                "target_weight": round(target, 2),
                "current_weight": round(current, 2),
                "deviation": round(deviation, 2),
                "action": action,
                "suggested_amount": suggested_amount,
                "latest_price": h.get("latest_price"),
            })
    
    suggestions.sort(key=lambda x: abs(x["deviation"]), reverse=True)
    
    return {
        "threshold": threshold,
        "total_deviation": round(total_deviation, 2),
        "needs_rebalance": needs_rebalance,
        "suggestions": suggestions,
        "portfolio_value": portfolio_value,
    }, None
