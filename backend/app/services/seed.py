import json
from datetime import date
from sqlmodel import select
from app.models import Stock, StrategyDefinition, DailyPrice, FactorValue, User, ConceptBoard, StockConceptMap
from app.services.auth import hash_password
from app.services.strategies import get_strategy_map
from app.services.index_sync import seed_index_products

CONCEPT_DATA = [
    {"code": "AI", "name": "人工智能", "category": "科技", "description": "人工智能产业链，包括算法、算力、应用等领域"},
    {"code": "NEW_ENERGY", "name": "新能源", "category": "能源", "description": "新能源产业链，包括光伏、风电、储能等"},
    {"code": "NEV", "name": "新能源车", "category": "汽车", "description": "新能源汽车产业链，包括整车、电池、电机等"},
    {"code": "SEMICONDUCTOR", "name": "半导体", "category": "科技", "description": "半导体芯片产业链，设计、制造、封测等"},
    {"code": "5G", "name": "5G通信", "category": "科技", "description": "5G通信技术及应用相关上市公司"},
    {"code": "CLOUD_COMPUTING", "name": "云计算", "category": "科技", "description": "云计算服务及基础设施提供商"},
    {"code": "BIG_DATA", "name": "大数据", "category": "科技", "description": "大数据采集、存储、分析及应用"},
    {"code": "INTERNET", "name": "互联网", "category": "科技", "description": "互联网平台及服务提供商"},
    {"code": "MEDICAL", "name": "医药生物", "category": "医药", "description": "医药研发、生产及流通企业"},
    {"code": "MEDICAL_DEVICE", "name": "医疗器械", "category": "医药", "description": "医疗器械研发与生产企业"},
    {"code": "CONSUMPTION", "name": "大消费", "category": "消费", "description": "食品饮料、家电等消费板块"},
    {"code": "LIQUOR", "name": "白酒", "category": "消费", "description": "白酒生产企业"},
    {"code": "REAL_ESTATE", "name": "房地产", "category": "地产", "description": "房地产开发及相关企业"},
    {"code": "FINANCE", "name": "大金融", "category": "金融", "description": "银行、证券、保险等金融板块"},
    {"code": "BANK", "name": "银行", "category": "金融", "description": "商业银行及政策性银行"},
    {"code": "SECURITIES", "name": "证券", "category": "金融", "description": "证券公司及相关金融服务"},
    {"code": "INSURANCE", "name": "保险", "category": "金融", "description": "保险公司及保险服务"},
    {"code": "MILITARY", "name": "军工", "category": "国防", "description": "军工航天及国防科技企业"},
    {"code": "AEROSPACE", "name": "航空航天", "category": "国防", "description": "航空航天制造及相关产业"},
    {"code": "NEW_MATERIAL", "name": "新材料", "category": "材料", "description": "新型材料研发与生产企业"},
    {"code": "RARE_EARTH", "name": "稀土永磁", "category": "材料", "description": "稀土开采及永磁材料企业"},
    {"code": "LITHIUM", "name": "锂电池", "category": "能源", "description": "锂电池及上游材料企业"},
    {"code": "SOLAR", "name": "光伏", "category": "能源", "description": "太阳能光伏产业链"},
    {"code": "WIND_POWER", "name": "风电", "category": "能源", "description": "风力发电设备及运营企业"},
    {"code": "HYDROGEN", "name": "氢能源", "category": "能源", "description": "氢能产业链相关企业"},
    {"code": "STORAGE", "name": "储能", "category": "能源", "description": "储能技术及设备提供商"},
    {"code": "ROBOTICS", "name": "机器人", "category": "制造", "description": "工业机器人及自动化设备"},
    {"code": "HIGH_END_EQUIPMENT", "name": "高端装备", "category": "制造", "description": "高端装备制造企业"},
    {"code": "CHIP_DESIGN", "name": "芯片设计", "category": "科技", "description": "集成电路设计企业"},
    {"code": "CHIP_MANUFACTURING", "name": "芯片制造", "category": "科技", "description": "芯片晶圆制造企业"},
    {"code": "SOFTWARE", "name": "国产软件", "category": "科技", "description": "国产软件及信创产业"},
    {"code": "CYBER_SECURITY", "name": "网络安全", "category": "科技", "description": "网络安全及信息安全企业"},
    {"code": "METAVERSE", "name": "元宇宙", "category": "科技", "description": "元宇宙概念相关上市公司"},
    {"code": "VR_AR", "name": "VR/AR", "category": "科技", "description": "虚拟现实/增强现实技术企业"},
    {"code": "BLOCKCHAIN", "name": "区块链", "category": "科技", "description": "区块链技术及应用企业"},
    {"code": "AGRICULTURE", "name": "乡村振兴", "category": "农业", "description": "农业现代化及乡村振兴相关"},
    {"code": "ENVIRONMENT", "name": "环保", "category": "公用", "description": "环境保护及治理企业"},
    {"code": "CARBON_NEUTRAL", "name": "碳中和", "category": "环保", "description": "碳中和及碳交易相关企业"},
    {"code": "SOE_REFORM", "name": "国企改革", "category": "政策", "description": "国有企业改革相关上市公司"},
    {"code": "CENTRAL_SOE", "name": "央国企", "category": "政策", "description": "中央国有企业及地方国企"},
    {"code": "BELT_AND_ROAD", "name": "一带一路", "category": "政策", "description": "一带一路倡议相关企业"},
    {"code": "GREAT_BAY_AREA", "name": "粤港澳大湾区", "category": "区域", "description": "粤港澳大湾区相关上市公司"},
    {"code": "YANGTZE_RIVER", "name": "长江经济带", "category": "区域", "description": "长江经济带相关上市公司"},
    {"code": "BEIJING_TIANJIN", "name": "京津冀", "category": "区域", "description": "京津冀协同发展相关企业"},
    {"code": "FREE_TRADE", "name": "自贸区", "category": "区域", "description": "自由贸易试验区相关企业"},
]

CONCEPT_STOCK_MAP = {
    "AI": ["600519", "000858", "601318", "000333", "600036", "000001", "600276", "002415", "601899", "002594"],
    "NEW_ENERGY": ["002594", "300750", "002475", "600030", "601899", "002460", "002466", "300274", "601012", "002129"],
    "NEV": ["002594", "600104", "000625", "601633", "000550", "002202", "300750", "002460", "002466", "603799"],
    "SEMICONDUCTOR": ["600584", "002371", "600703", "300661", "002049", "688981", "688396", "688012", "300782", "300059"],
    "5G": ["600050", "600198", "000063", "600745", "002281", "300628", "300502", "002916", "600522", "600487"],
    "CLOUD_COMPUTING": ["600588", "002410", "300017", "300059", "600845", "002230", "600410", "300454", "688111", "688083"],
    "BIG_DATA": ["600588", "002230", "300059", "300229", "002439", "300383", "002335", "600718", "000977", "300166"],
    "INTERNET": ["300059", "002415", "002230", "300017", "002024", "002315", "300413", "600986", "002602", "002555"],
    "MEDICAL": ["600276", "000538", "000661", "600196", "300760", "600587", "002422", "002007", "300015", "600436"],
    "MEDICAL_DEVICE": ["300760", "600587", "002223", "600055", "300326", "002901", "300171", "002551", "688588", "300206"],
    "CONSUMPTION": ["600519", "000858", "600887", "000333", "000651", "600690", "002415", "600309", "002714", "600809"],
    "LIQUOR": ["600519", "000858", "600809", "002304", "600779", "000568", "600559", "600197", "000799", "000596"],
    "REAL_ESTATE": ["000002", "600048", "601155", "001979", "600383", "000671", "002146", "600208", "000069", "600376"],
    "FINANCE": ["601318", "600036", "000001", "600030", "600837", "601628", "601318", "600000", "601166", "601328"],
    "BANK": ["600036", "000001", "600000", "601166", "601328", "600016", "601939", "601398", "601288", "601988"],
    "SECURITIES": ["600030", "600837", "601688", "000776", "600109", "601211", "600369", "000166", "601377", "002797"],
    "INSURANCE": ["601318", "601628", "601601", "601336", "601319", "601601", "000627", "600291", "601099", "000062"],
    "MILITARY": ["600893", "000768", "600760", "600038", "600150", "002025", "000547", "600685", "300034", "600990"],
    "AEROSPACE": ["600893", "000768", "600760", "600038", "600151", "002025", "000547", "600677", "002013", "600316"],
    "NEW_MATERIAL": ["600309", "600516", "300390", "002709", "300433", "002456", "600206", "300285", "600558", "002297"],
    "RARE_EARTH": ["600111", "600259", "000831", "600392", "000970", "600366", "002056", "300224", "600980", "000795"],
    "LITHIUM": ["002460", "002466", "300750", "002594", "603799", "002709", "300014", "002460", "002074", "002192"],
    "SOLAR": ["601012", "002129", "300274", "002459", "600438", "002006", "002218", "300111", "600537", "002610"],
    "WIND_POWER": ["002202", "601615", "300772", "600089", "600416", "002531", "002080", "300129", "600290", "600483"],
    "HYDROGEN": ["600273", "000723", "600875", "601222", "300325", "002274", "600378", "603906", "002639", "300471"],
    "STORAGE": ["300750", "002460", "002466", "600522", "300274", "600884", "002812", "002334", "300014", "300037"],
    "ROBOTICS": ["002747", "300024", "603486", "600855", "002698", "300124", "002527", "600560", "300450", "002756"],
    "HIGH_END_EQUIPMENT": ["600031", "000425", "600320", "601100", "002353", "600761", "002595", "002204", "600582", "300094"],
    "CHIP_DESIGN": ["300782", "603501", "603893", "600584", "300661", "300458", "688099", "688008", "300327", "002156"],
    "CHIP_MANUFACTURING": ["688981", "600703", "600584", "688012", "002371", "300236", "603690", "688082", "300316", "300604"],
    "SOFTWARE": ["600588", "002410", "300033", "002230", "600845", "300379", "002368", "688111", "600718", "300454"],
    "CYBER_SECURITY": ["002439", "300369", "601360", "002268", "300454", "688023", "300352", "300188", "002649", "600734"],
    "METAVERSE": ["002230", "300059", "002555", "300413", "600986", "002602", "002416", "300251", "603598", "600198"],
    "VR_AR": ["002241", "300433", "002681", "300031", "002273", "603005", "688036", "002416", "300473", "300691"],
    "BLOCKCHAIN": ["300059", "002230", "600099", "300386", "002657", "300468", "600208", "002268", "300202", "600797"],
    "AGRICULTURE": ["000876", "600438", "002714", "000998", "600371", "002385", "300498", "000713", "600598", "002041"],
    "ENVIRONMENT": ["600008", "600292", "000826", "600874", "300070", "002499", "300190", "600323", "603686", "002573"],
    "CARBON_NEUTRAL": ["601012", "002129", "300274", "600522", "002594", "300750", "600900", "600011", "600027", "000027"],
    "SOE_REFORM": ["600028", "601857", "601398", "600036", "600050", "600519", "601318", "600030", "000063", "601111"],
    "CENTRAL_SOE": ["600028", "601857", "601398", "601288", "600036", "601318", "601628", "600050", "600519", "600028"],
    "BELT_AND_ROAD": ["601390", "601186", "601800", "000063", "600030", "600436", "601866", "601919", "000039", "600031"],
    "GREAT_BAY_AREA": ["000001", "000002", "000333", "002594", "300750", "002415", "000858", "000651", "002475", "002304"],
    "YANGTZE_RIVER": ["600519", "600036", "600887", "600309", "600019", "000895", "601012", "002415", "000651", "600406"],
    "BEIJING_TIANJIN": ["601398", "600036", "600030", "601318", "601628", "600050", "600588", "002410", "601888", "600276"],
    "FREE_TRADE": ["600018", "600317", "000088", "002202", "600717", "601866", "601919", "600708", "002095", "300059"],
}

def seed_basic_data(session):
    if not session.exec(select(User)).first():
        session.add(User(username="admin", password_hash=hash_password("123456"), role="admin"))
        session.add(User(username="analyst", password_hash=hash_password("123456"), role="analyst"))
        session.commit()
    
    if not session.exec(select(StrategyDefinition)).first():
        for name, func in get_strategy_map().items():
            session.add(StrategyDefinition(name=name, description=f"{name}策略", parameters_json=json.dumps({}, ensure_ascii=False)))
        session.commit()
    
    seed_index_products(session)

def seed_concept_data(session):
    if session.exec(select(ConceptBoard)).first():
        return
    
    for concept_info in CONCEPT_DATA:
        concept = ConceptBoard(
            code=concept_info["code"],
            name=concept_info["name"],
            description=concept_info.get("description"),
            category=concept_info.get("category"),
        )
        session.add(concept)
    session.commit()
    
    all_stocks = session.exec(select(Stock)).all()
    stock_symbol_map = {s.symbol: s.id for s in all_stocks}
    
    for concept_code, symbols in CONCEPT_STOCK_MAP.items():
        concept = session.exec(
            select(ConceptBoard).where(ConceptBoard.code == concept_code)
        ).first()
        if not concept:
            continue
        
        for symbol in symbols:
            stock_id = stock_symbol_map.get(symbol)
            if stock_id:
                existing = session.exec(
                    select(StockConceptMap).where(
                        StockConceptMap.concept_id == concept.id,
                        StockConceptMap.stock_id == stock_id,
                    )
                ).first()
                if not existing:
                    session.add(StockConceptMap(
                        stock_id=stock_id,
                        concept_id=concept.id,
                    ))
    
    session.commit()
