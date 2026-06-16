from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import select
from app.models import Notification, NotificationPreference, UserWatchlist, User, Stock, DailyPrice, StockSnapshot
from app.db import get_session

NOTIFICATION_TYPES = [
    {
        "type": "data_sync",
        "name": "数据同步",
        "description": "数据同步任务完成或失败时通知",
        "has_threshold": False,
        "default_enabled": True,
    },
    {
        "type": "backtest",
        "name": "策略回测",
        "description": "批量回测任务完成或失败时通知",
        "has_threshold": False,
        "default_enabled": True,
    },
    {
        "type": "pattern_scan",
        "name": "形态扫描",
        "description": "形态扫描任务完成或失败时通知",
        "has_threshold": False,
        "default_enabled": True,
    },
    {
        "type": "price_alert",
        "name": "自选股涨跌提醒",
        "description": "自选股涨跌幅触达阈值时通知",
        "has_threshold": True,
        "default_enabled": True,
        "default_threshold_up": 5.0,
        "default_threshold_down": -5.0,
    },
    {
        "type": "scheduled_task",
        "name": "定时任务",
        "description": "定时任务执行结果通知",
        "has_threshold": False,
        "default_enabled": True,
    },
    {
        "type": "system",
        "name": "系统通知",
        "description": "系统级别的重要通知",
        "has_threshold": False,
        "default_enabled": True,
    },
]

NOTIFICATION_TYPE_MAP = {t["type"]: t for t in NOTIFICATION_TYPES}


def create_notification(
    session,
    user_id: int,
    notification_type: str,
    title: str,
    content: Optional[str] = None,
    link_url: Optional[str] = None,
    severity: str = "info",
    check_preference: bool = True,
) -> Optional[Notification]:
    if check_preference:
        pref = session.exec(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == notification_type,
            )
        ).first()
        if pref and not pref.enabled:
            return None
        if not pref and not NOTIFICATION_TYPE_MAP.get(notification_type, {}).get("default_enabled", True):
            return None

    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        content=content,
        link_url=link_url,
        severity=severity,
        is_read=False,
        created_at=datetime.utcnow(),
    )
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


def get_or_create_preference(session, user_id: int, notification_type: str) -> NotificationPreference:
    pref = session.exec(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.notification_type == notification_type,
        )
    ).first()
    if not pref:
        type_config = NOTIFICATION_TYPE_MAP.get(notification_type, {})
        pref = NotificationPreference(
            user_id=user_id,
            notification_type=notification_type,
            enabled=type_config.get("default_enabled", True),
            threshold_up=type_config.get("default_threshold_up"),
            threshold_down=type_config.get("default_threshold_down"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(pref)
        session.commit()
        session.refresh(pref)
    return pref


def get_all_preferences(session, user_id: int) -> List[NotificationPreference]:
    prefs = session.exec(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    ).all()
    pref_map = {p.notification_type: p for p in prefs}
    result = []
    for t in NOTIFICATION_TYPES:
        if t["type"] in pref_map:
            result.append(pref_map[t["type"]])
        else:
            result.append(get_or_create_preference(session, user_id, t["type"]))
    return result


def check_price_alerts(session) -> List[Notification]:
    users = session.exec(select(User)).all()
    notifications = []
    today = datetime.utcnow().date()
    for user in users:
        watchlist = session.exec(
            select(UserWatchlist).where(UserWatchlist.user_id == user.id)
        ).all()
        if not watchlist:
            continue
        pref = session.exec(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user.id,
                NotificationPreference.notification_type == "price_alert",
            )
        ).first()
        if not pref:
            pref = get_or_create_preference(session, user.id, "price_alert")
        if not pref.enabled:
            continue
        threshold_up = pref.threshold_up or 5.0
        threshold_down = pref.threshold_down or -5.0
        symbols = [w.symbol for w in watchlist]
        stocks = session.exec(select(Stock).where(Stock.symbol.in_(symbols))).all()
        stock_map = {s.symbol: s for s in stocks}
        for w in watchlist:
            stock = stock_map.get(w.symbol)
            if not stock:
                continue
            snapshot = session.exec(
                select(StockSnapshot).where(StockSnapshot.stock_id == stock.id)
            ).first()
            if not snapshot:
                continue
            prices = session.exec(
                select(DailyPrice).where(
                    DailyPrice.stock_id == stock.id,
                    DailyPrice.trade_date <= today
                ).order_by(DailyPrice.trade_date.desc()).limit(2)
            ).all()
            if len(prices) < 2:
                continue
            latest_price = prices[0].close
            prev_close = prices[1].close
            change_pct = ((latest_price - prev_close) / prev_close) * 100
            if change_pct >= threshold_up or change_pct <= threshold_down:
                direction = "上涨" if change_pct > 0 else "下跌"
                severity = "warning" if abs(change_pct) >= 10 else "info"
                notification = create_notification(
                    session,
                    user_id=user.id,
                    notification_type="price_alert",
                    title=f"{stock.name}({stock.symbol}){direction}提醒",
                    content=f"{stock.name}({stock.symbol})今日{direction}{change_pct:.2f}%，最新价: {latest_price:.2f}元",
                    link_url=f"/index/{stock.symbol}",
                    severity=severity,
                    check_preference=False,
                )
                if notification:
                    notifications.append(notification)
    return notifications
