from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.db import get_session
from app.services.data_sync import sync_daily, sync_stock_list
from app.services.snapshot_updater import update_stock_snapshots
from app.services.notification import check_price_alerts, create_notification
from app.models import Stock, User
from sqlmodel import select
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

def daily_sync_job():
    logger.info("Starting scheduled daily sync...")
    admin_user_id = None
    try:
        with get_session() as session:
            admin = session.exec(select(User).where(User.role == "admin")).first()
            if admin:
                admin_user_id = admin.id
            
            # 1. Sync stock list first
            sync_stock_list(session)
            
            # 2. Sync daily data for all stocks
            stocks = session.exec(select(Stock)).all()
            symbols = [s.symbol for s in stocks]
            
            today = date.today()
            start_date = today - timedelta(days=3)
            
            logger.info(f"Syncing {len(symbols)} stocks from {start_date} to {today}")
            sync_daily(session, symbols, start_date, today, sync_type="scheduled")
            
            # 3. 更新股票快照表 (预计算技术指标)
            logger.info("Updating stock snapshots for fast screening...")
            updated_count = update_stock_snapshots(session)
            logger.info(f"Stock snapshots updated: {updated_count} stocks")
            
            # 4. 检查自选股涨跌幅阈值并发送通知
            logger.info("Checking watchlist price alerts...")
            alerts = check_price_alerts(session)
            logger.info(f"Generated {len(alerts)} price alert notifications")
            
            # 5. 发送定时任务完成通知
            if admin_user_id:
                create_notification(
                    session,
                    user_id=admin_user_id,
                    notification_type="scheduled_task",
                    title="每日同步任务完成",
                    content=f"每日数据同步任务已完成，同步 {len(symbols)} 只股票，更新 {updated_count} 个快照，生成 {len(alerts)} 条价格提醒",
                    link_url="/data",
                    severity="success",
                    check_preference=False,
                )
    except Exception as e:
        logger.error(f"Scheduled daily sync failed: {e}")
        if admin_user_id:
            with get_session() as session:
                create_notification(
                    session,
                    user_id=admin_user_id,
                    notification_type="scheduled_task",
                    title="每日同步任务失败",
                    content=f"每日数据同步任务执行失败: {str(e)}",
                    link_url="/logs",
                    severity="error",
                    check_preference=False,
                )
        
    logger.info("Scheduled daily sync completed.")

def init_scheduler():
    # Run at 15:35 every weekday
    trigger = CronTrigger(day_of_week='mon-fri', hour=15, minute=35)
    scheduler.add_job(daily_sync_job, trigger, id='daily_sync', replace_existing=True)
    
    # 价格检查：交易日 10:00, 11:30, 14:00, 15:00 各执行一次
    price_trigger = CronTrigger(day_of_week='mon-fri', hour='10,11,14,15', minute='0,30')
    def price_alert_job():
        with get_session() as session:
            check_price_alerts(session)
    scheduler.add_job(
        price_alert_job,
        price_trigger,
        id='price_alert_check',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("APScheduler started. Daily sync scheduled for 15:35 Mon-Fri. Price alert check scheduled for 10:00, 11:30, 14:00, 15:00 Mon-Fri.")

