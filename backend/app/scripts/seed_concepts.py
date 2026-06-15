"""
概念板块数据初始化脚本
运行方式: python -m app.scripts.seed_concepts
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.db import init_db, get_session
from app.services.seed import seed_concept_data, CONCEPT_DATA, CONCEPT_STOCK_MAP
from app.models import ConceptBoard, StockConceptMap, Stock
from sqlmodel import select

def main():
    print("=" * 60)
    print("概念板块数据初始化")
    print("=" * 60)
    
    init_db()
    
    with get_session() as session:
        existing_count = len(session.exec(select(ConceptBoard)).all())
        
        if existing_count > 0:
            print(f"\n检测到已存在 {existing_count} 个概念板块")
            print("是否要重新初始化？(y/N): ", end="")
            answer = input().strip().lower()
            if answer != 'y':
                print("已取消。")
                return
            
            session.exec(StockConceptMap.__table__.delete())
            session.exec(ConceptBoard.__table__.delete())
            session.commit()
            print("已清除现有概念板块数据。")
        
        seed_concept_data(session)
        
        concept_count = len(session.exec(select(ConceptBoard)).all())
        mapping_count = len(session.exec(select(StockConceptMap)).all())
        stock_count = len(session.exec(select(Stock)).all())
        
        print(f"\n✅ 初始化完成")
        print(f"   - 概念板块: {concept_count} 个")
        print(f"   - 股票-概念映射: {mapping_count} 条")
        print(f"   - 系统中已有股票: {stock_count} 只")
        
        print(f"\n📋 概念分类统计:")
        categories = {}
        for concept in session.exec(select(ConceptBoard)).all():
            cat = concept.category or '未分类'
            categories[cat] = categories.get(cat, 0) + 1
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"   - {cat}: {count} 个")

if __name__ == "__main__":
    main()
