import pandas as pd
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
from sqlmodel import select, func
from app.models import Stock, ConceptBoard, StockConceptMap, DailyPrice


def get_concept_list(session, keyword: str = "", sort_by: str = "name", sort_order: str = "asc"):
    query = select(ConceptBoard)
    if keyword:
        query = query.where(
            ConceptBoard.code.contains(keyword) | ConceptBoard.name.contains(keyword)
        )
    
    concepts = session.exec(query).all()
    
    results = []
    for concept in concepts:
        constituent_count = session.exec(
            select(func.count(StockConceptMap.id)).where(StockConceptMap.concept_id == concept.id)
        ).one()
        
        daily_change, five_day_change = _calculate_concept_returns(session, concept.id)
        
        results.append({
            "id": concept.id,
            "code": concept.code,
            "name": concept.name,
            "description": concept.description,
            "category": concept.category,
            "constituent_count": constituent_count,
            "daily_change": daily_change,
            "five_day_change": five_day_change,
        })
    
    reverse = sort_order == "desc"
    if sort_by == "name":
        results.sort(key=lambda x: x["name"], reverse=reverse)
    elif sort_by == "daily_change":
        results.sort(key=lambda x: x["daily_change"] if x["daily_change"] is not None else float('-inf'), reverse=reverse)
    elif sort_by == "five_day_change":
        results.sort(key=lambda x: x["five_day_change"] if x["five_day_change"] is not None else float('-inf'), reverse=reverse)
    elif sort_by == "constituent_count":
        results.sort(key=lambda x: x["constituent_count"], reverse=reverse)
    
    return results


def get_concept_detail(session, concept_code: str):
    concept = session.exec(
        select(ConceptBoard).where(ConceptBoard.code == concept_code)
    ).first()
    
    if not concept:
        return None
    
    constituent_count = session.exec(
        select(func.count(StockConceptMap.id)).where(StockConceptMap.concept_id == concept.id)
    ).one()
    
    daily_change, five_day_change = _calculate_concept_returns(session, concept.id)
    
    index_series = _calculate_concept_index_series(session, concept.id)
    
    constituents = get_concept_constituents(session, concept_code)
    
    return {
        "id": concept.id,
        "code": concept.code,
        "name": concept.name,
        "description": concept.description,
        "category": concept.category,
        "constituent_count": constituent_count,
        "daily_change": daily_change,
        "five_day_change": five_day_change,
        "index_series": index_series,
        "constituents": constituents,
    }


def get_concept_constituents(session, concept_code: str):
    concept = session.exec(
        select(ConceptBoard).where(ConceptBoard.code == concept_code)
    ).first()
    
    if not concept:
        return []
    
    mappings = session.exec(
        select(StockConceptMap).where(StockConceptMap.concept_id == concept.id)
    ).all()
    
    stock_ids = [m.stock_id for m in mappings]
    
    if not stock_ids:
        return []
    
    stocks = session.exec(
        select(Stock).where(Stock.id.in_(stock_ids))
    ).all()
    
    stock_map = {s.id: s for s in stocks}
    
    latest_date = session.exec(
        select(func.max(DailyPrice.trade_date))
    ).one()
    
    results = []
    for mapping in mappings:
        stock = stock_map.get(mapping.stock_id)
        if not stock:
            continue
        
        daily_change = None
        latest_price = None
        if latest_date:
            prev_date = _get_previous_trade_date(session, stock.id, latest_date)
            if prev_date:
                prev_price = session.exec(
                    select(DailyPrice).where(
                        DailyPrice.stock_id == stock.id,
                        DailyPrice.trade_date == prev_date
                    )
                ).first()
                curr_price = session.exec(
                    select(DailyPrice).where(
                        DailyPrice.stock_id == stock.id,
                        DailyPrice.trade_date == latest_date
                    )
                ).first()
                if prev_price and curr_price and prev_price.close != 0:
                    daily_change = (curr_price.close - prev_price.close) / prev_price.close * 100
                    latest_price = curr_price.close
        
        results.append({
            "symbol": stock.symbol,
            "name": stock.name,
            "market": stock.market,
            "industry": stock.industry,
            "weight": mapping.weight,
            "latest_price": latest_price,
            "daily_change": daily_change,
        })
    
    results.sort(key=lambda x: x["daily_change"] if x["daily_change"] is not None else float('-inf'), reverse=True)
    
    return results


def get_concept_leaderboard(session, days: int = 5, limit: int = 20):
    concepts = session.exec(select(ConceptBoard)).all()
    
    results = []
    for concept in concepts:
        returns = _calculate_concept_returns_for_period(session, concept.id, days)
        if returns is None:
            continue
        
        constituent_count = session.exec(
            select(func.count(StockConceptMap.id)).where(StockConceptMap.concept_id == concept.id)
        ).one()
        
        results.append({
            "code": concept.code,
            "name": concept.name,
            "category": concept.category,
            "constituent_count": constituent_count,
            "change_pct": returns,
        })
    
    results.sort(key=lambda x: x["change_pct"], reverse=True)
    
    return results[:limit]


def get_stock_concepts(session, symbol: str):
    stock = session.exec(
        select(Stock).where(Stock.symbol == symbol)
    ).first()
    
    if not stock:
        return []
    
    mappings = session.exec(
        select(StockConceptMap).where(StockConceptMap.stock_id == stock.id)
    ).all()
    
    concept_ids = [m.concept_id for m in mappings]
    
    if not concept_ids:
        return []
    
    concepts = session.exec(
        select(ConceptBoard).where(ConceptBoard.id.in_(concept_ids))
    ).all()
    
    results = []
    for concept in concepts:
        daily_change, five_day_change = _calculate_concept_returns(session, concept.id)
        results.append({
            "code": concept.code,
            "name": concept.name,
            "category": concept.category,
            "daily_change": daily_change,
            "five_day_change": five_day_change,
        })
    
    return results


def _get_previous_trade_date(session, stock_id: int, current_date: date) -> Optional[date]:
    result = session.exec(
        select(DailyPrice.trade_date)
        .where(DailyPrice.stock_id == stock_id, DailyPrice.trade_date < current_date)
        .order_by(DailyPrice.trade_date.desc())
        .limit(1)
    ).first()
    return result


def _calculate_concept_returns(session, concept_id: int) -> Tuple[Optional[float], Optional[float]]:
    """计算概念板块的当日涨跌幅和5日累计涨跌幅"""
    mappings = session.exec(
        select(StockConceptMap).where(StockConceptMap.concept_id == concept_id)
    ).all()
    
    if not mappings:
        return None, None
    
    stock_ids = [m.stock_id for m in mappings]
    
    latest_date = session.exec(
        select(func.max(DailyPrice.trade_date))
    ).one()
    
    if not latest_date:
        return None, None
    
    daily_returns = []
    five_day_returns = []
    
    for stock_id in stock_ids:
        prev_date = _get_previous_trade_date(session, stock_id, latest_date)
        if not prev_date:
            continue
        
        prev_price = session.exec(
            select(DailyPrice).where(
                DailyPrice.stock_id == stock_id,
                DailyPrice.trade_date == prev_date
            )
        ).first()
        curr_price = session.exec(
            select(DailyPrice).where(
                DailyPrice.stock_id == stock_id,
                DailyPrice.trade_date == latest_date
            )
        ).first()
        
        if prev_price and curr_price and prev_price.close != 0:
            daily_returns.append((curr_price.close - prev_price.close) / prev_price.close)
        
        five_days_ago_date = _get_nth_previous_trade_date(session, stock_id, latest_date, 5)
        if five_days_ago_date:
            five_day_price = session.exec(
                select(DailyPrice).where(
                    DailyPrice.stock_id == stock_id,
                    DailyPrice.trade_date == five_days_ago_date
                )
            ).first()
            if five_day_price and curr_price and five_day_price.close != 0:
                five_day_returns.append((curr_price.close - five_day_price.close) / five_day_price.close)
    
    daily_change = sum(daily_returns) / len(daily_returns) * 100 if daily_returns else None
    five_day_change = sum(five_day_returns) / len(five_day_returns) * 100 if five_day_returns else None
    
    return daily_change, five_day_change


def _calculate_concept_returns_for_period(session, concept_id: int, days: int) -> Optional[float]:
    """计算概念板块指定周期的累计涨跌幅（等权）"""
    mappings = session.exec(
        select(StockConceptMap).where(StockConceptMap.concept_id == concept_id)
    ).all()
    
    if not mappings:
        return None
    
    stock_ids = [m.stock_id for m in mappings]
    
    latest_date = session.exec(
        select(func.max(DailyPrice.trade_date))
    ).one()
    
    if not latest_date:
        return None
    
    period_returns = []
    
    for stock_id in stock_ids:
        n_days_ago_date = _get_nth_previous_trade_date(session, stock_id, latest_date, days)
        if not n_days_ago_date:
            continue
        
        start_price = session.exec(
            select(DailyPrice).where(
                DailyPrice.stock_id == stock_id,
                DailyPrice.trade_date == n_days_ago_date
            )
        ).first()
        end_price = session.exec(
            select(DailyPrice).where(
                DailyPrice.stock_id == stock_id,
                DailyPrice.trade_date == latest_date
            )
        ).first()
        
        if start_price and end_price and start_price.close != 0:
            period_returns.append((end_price.close - start_price.close) / start_price.close)
    
    if not period_returns:
        return None
    
    return sum(period_returns) / len(period_returns) * 100


def _get_nth_previous_trade_date(session, stock_id: int, current_date: date, n: int) -> Optional[date]:
    """获取第N个交易日之前的日期"""
    results = session.exec(
        select(DailyPrice.trade_date)
        .where(DailyPrice.stock_id == stock_id, DailyPrice.trade_date <= current_date)
        .order_by(DailyPrice.trade_date.desc())
        .limit(n + 1)
    ).all()
    
    if len(results) > n:
        return results[n]
    return None


def _calculate_concept_index_series(session, concept_id: int, days: int = 60) -> List[Dict]:
    """计算概念板块指数时间序列（等权收益率合成）"""
    mappings = session.exec(
        select(StockConceptMap).where(StockConceptMap.concept_id == concept_id)
    ).all()
    
    if not mappings:
        return []
    
    stock_ids = [m.stock_id for m in mappings]
    
    latest_date = session.exec(
        select(func.max(DailyPrice.trade_date))
    ).one()
    
    if not latest_date:
        return []
    
    all_dates = set()
    stock_prices = {}
    
    for stock_id in stock_ids:
        prices = session.exec(
            select(DailyPrice)
            .where(DailyPrice.stock_id == stock_id)
            .order_by(DailyPrice.trade_date.desc())
            .limit(days + 1)
        ).all()
        
        if prices:
            stock_prices[stock_id] = {p.trade_date: p for p in prices}
            for p in prices:
                all_dates.add(p.trade_date)
    
    if not all_dates:
        return []
    
    sorted_dates = sorted(all_dates)
    
    index_series = []
    base_value = 1000.0
    
    if len(sorted_dates) < 2:
        return []
    
    for i, d in enumerate(sorted_dates):
        if i == 0:
            index_series.append({
                "trade_date": d.isoformat(),
                "open": base_value,
                "high": base_value,
                "low": base_value,
                "close": base_value,
                "volume": 0,
            })
            continue
        
        daily_returns = []
        prev_date = sorted_dates[i - 1]
        
        for stock_id in stock_ids:
            if stock_id not in stock_prices:
                continue
            prev_price = stock_prices[stock_id].get(prev_date)
            curr_price = stock_prices[stock_id].get(d)
            if prev_price and curr_price and prev_price.close != 0:
                daily_returns.append((curr_price.close - prev_price.close) / prev_price.close)
        
        if daily_returns:
            avg_return = sum(daily_returns) / len(daily_returns)
            prev_close = index_series[-1]["close"]
            curr_close = prev_close * (1 + avg_return)
            
            index_series.append({
                "trade_date": d.isoformat(),
                "open": prev_close,
                "high": curr_close * 1.005,
                "low": curr_close * 0.995,
                "close": curr_close,
                "volume": 0,
            })
    
    return index_series


def get_related_concepts(session, concept_code: str, limit: int = 10) -> List[Dict]:
    """获取关联概念（基于共同成分股数量）"""
    concept = session.exec(
        select(ConceptBoard).where(ConceptBoard.code == concept_code)
    ).first()
    
    if not concept:
        return []
    
    current_stock_ids = session.exec(
        select(StockConceptMap.stock_id).where(StockConceptMap.concept_id == concept.id)
    ).all()
    
    if not current_stock_ids:
        return []
    
    other_concepts = session.exec(
        select(ConceptBoard).where(ConceptBoard.id != concept.id)
    ).all()
    
    related = []
    for other in other_concepts:
        other_stock_ids = session.exec(
            select(StockConceptMap.stock_id).where(StockConceptMap.concept_id == other.id)
        ).all()
        
        if not other_stock_ids:
            continue
        
        overlap = len(set(current_stock_ids) & set(other_stock_ids))
        if overlap > 0:
            daily_change, _ = _calculate_concept_returns(session, other.id)
            related.append({
                "code": other.code,
                "name": other.name,
                "category": other.category,
                "overlap_count": overlap,
                "daily_change": daily_change,
                "constituent_count": len(other_stock_ids),
            })
    
    related.sort(key=lambda x: x["overlap_count"], reverse=True)
    
    return related[:limit]
