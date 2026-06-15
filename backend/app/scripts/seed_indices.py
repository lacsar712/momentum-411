"""
指数与ETF产品初始化脚本
运行: python -m app.scripts.seed_indices
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import date, timedelta
from app.db import get_session
from app.services.index_sync import seed_index_products, sync_index_daily
from app.models import IndexProduct
from sqlmodel import select

def main():
    session = get_session()
    try:
        print("=" * 60)
        print("指数与ETF数据初始化")
        print("=" * 60)
        
        print("\n[1/3] 初始化指数/ETF产品列表...")
        seed_index_products(session)
        products = session.exec(select(IndexProduct)).all()
        print(f"    已加载 {len(products)} 个指数/ETF产品:")
        for p in products:
            type_label = "指数" if p.index_type == "index" else "ETF"
            print(f"      - {p.code} {p.name} [{type_label}]")
        
        print(f"\n[2/3] 开始同步日线数据 (近5年历史)...")
        end_date = date.today()
        start_date = end_date - timedelta(days=365 * 5)
        
        def progress_cb(current, total, msg=""):
            print(f"    进度: {current}/{total} - {msg}")
        
        count = sync_index_daily(
            session,
            start=start_date,
            end=end_date,
            sync_type="full",
            progress_callback=progress_cb,
        )
        print(f"    共同步 {count} 条日线数据记录")
        
        print("\n[3/3] 验证数据完整性...")
        for p in products:
            from sqlmodel import func
            from app.models import IndexDailyPrice
            price_count = session.exec(
                select(func.count(IndexDailyPrice.id)).where(IndexDailyPrice.index_id == p.id)
            ).one()
            latest = session.exec(
                select(IndexDailyPrice)
                .where(IndexDailyPrice.index_id == p.id)
                .order_by(IndexDailyPrice.trade_date.desc())
                .limit(1)
            ).first()
            latest_date = latest.trade_date.isoformat() if latest else "无数据"
            print(f"    - {p.code} {p.name}: {price_count} 条, 最新 {latest_date}")
        
        print("\n" + "=" * 60)
        print("初始化完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    main()
