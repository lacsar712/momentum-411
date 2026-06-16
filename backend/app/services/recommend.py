"""
智能选股推荐服务 - 可插拔的综合打分排序引擎
提供多维度评分规则，支持自定义权重和评分卡方案管理
"""
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple
from sqlmodel import Session, select

from app.models import Stock, StockSnapshot, FactorValue


@dataclass
class ScoringRule:
    """评分规则定义"""
    rule_id: str
    name: str
    description: str
    default_weight: float
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    optimal_min: Optional[float] = None
    optimal_max: Optional[float] = None
    unit: str = ""
    score_func: Optional[Callable[[Dict], Tuple[float, float]]] = None  # (raw_value, score_0_1)
    enabled: bool = True


def _decay_score(value: float, opt_min: float, opt_max: float,
                 hard_min: Optional[float] = None, hard_max: Optional[float] = None) -> float:
    """
    距离衰减评分函数：
    - 在最优区间内给满分 1.0
    - 超出最优区间后按距离线性衰减到 0
    - 超出硬边界直接给 0
    """
    if hard_min is not None and value < hard_min:
        return 0.0
    if hard_max is not None and value > hard_max:
        return 0.0

    if opt_min <= value <= opt_max:
        return 1.0

    if value < opt_min:
        if hard_min is not None:
            return max(0.0, 1.0 - (opt_min - value) / (opt_min - hard_min))
        return max(0.0, 1.0 - (opt_min - value) / opt_min)
    else:
        if hard_max is not None:
            return max(0.0, 1.0 - (value - opt_max) / (hard_max - opt_max))
        return max(0.0, 1.0 - (value - opt_max) / opt_max)


def _score_pe(stock_data: Dict) -> Tuple[float, float]:
    """PE 评分：10~20 给满分，超出按距离衰减，硬边界 0~50"""
    pe = stock_data.get("pe_ratio")
    if pe is None or pe <= 0:
        return 0.0, 0.0
    raw_value = pe
    score = _decay_score(pe, opt_min=10, opt_max=20, hard_min=0, hard_max=50)
    return raw_value, score


def _score_pb(stock_data: Dict) -> Tuple[float, float]:
    """PB 评分：1~3 给满分，超出按距离衰减，硬边界 0~10"""
    pb = stock_data.get("pb_ratio")
    if pb is None or pb <= 0:
        return 0.0, 0.0
    raw_value = pb
    score = _decay_score(pb, opt_min=1, opt_max=3, hard_min=0, hard_max=10)
    return raw_value, score


def _score_rsi(stock_data: Dict) -> Tuple[float, float]:
    """RSI 评分：30~50 给满分，超出按距离衰减"""
    rsi_val = stock_data.get("rsi")
    if rsi_val is None:
        return 0.0, 0.0
    raw_value = rsi_val
    score = _decay_score(rsi_val, opt_min=30, opt_max=50, hard_min=0, hard_max=100)
    return raw_value, score


def _score_momentum_20d(stock_data: Dict) -> Tuple[float, float]:
    """20日动量评分：大于 0 给满分，否则按衰减"""
    momentum = stock_data.get("momentum")
    if momentum is None:
        return 0.0, 0.0
    raw_value = momentum
    if momentum > 0:
        score = 1.0
    else:
        score = max(0.0, 1.0 + momentum / 0.3)
    return raw_value, score


def _score_macd_golden_cross(stock_data: Dict) -> Tuple[float, float]:
    """MACD 金叉评分：金叉（MACD线上穿信号线）给满分"""
    macd_hist = stock_data.get("macd_hist")
    macd_line = stock_data.get("macd_line")
    macd_signal = stock_data.get("macd_signal")

    if macd_hist is None or macd_line is None or macd_signal is None:
        return 0.0, 0.0

    raw_value = macd_hist
    if macd_hist > 0 and macd_line > macd_signal:
        score = 1.0
    elif macd_hist > 0:
        score = 0.7
    elif macd_line > macd_signal:
        score = 0.5
    else:
        score = max(0.0, 0.5 + macd_hist / 0.1)
    return raw_value, score


def _score_market_cap(stock_data: Dict) -> Tuple[float, float]:
    """市值评分：100~1000 亿给满分，超出按距离衰减"""
    market_cap = stock_data.get("market_cap")
    if market_cap is None or market_cap <= 0:
        return 0.0, 0.0
    market_cap_yi = market_cap / 1e8
    raw_value = market_cap_yi
    score = _decay_score(market_cap_yi, opt_min=100, opt_max=1000, hard_min=10, hard_max=5000)
    return raw_value, score


def _get_industry_rank(session: Session, stock: Stock, all_stocks: List[Stock]) -> Tuple[float, float]:
    """
    计算行业排名百分位（0~1，越小越好）
    返回：(percentile, score)  - score 是转换为越高越好
    """
    if not stock.industry:
        return 0.0, 0.0

    industry_stocks = [s for s in all_stocks if s.industry == stock.industry]
    if len(industry_stocks) < 2:
        return 0.5, 0.5

    sorted_stocks = sorted(industry_stocks, key=lambda s: (s.market_cap or 0) * (s.pe_ratio or 1), reverse=True)
    rank = next((i for i, s in enumerate(sorted_stocks) if s.id == stock.id), len(sorted_stocks))
    percentile = rank / len(sorted_stocks)

    score = 1.0 if percentile <= 0.3 else max(0.0, 1.0 - (percentile - 0.3) / 0.7)
    return percentile, score


def get_default_rules() -> List[ScoringRule]:
    """获取默认评分规则集合"""
    return [
        ScoringRule(
            rule_id="pe",
            name="市盈率 (PE)",
            description="市盈率在 10-20 倍区间为最优，估值合理",
            default_weight=1.0,
            optimal_min=10,
            optimal_max=20,
            min_value=0,
            max_value=50,
            unit="倍",
            score_func=_score_pe,
        ),
        ScoringRule(
            rule_id="pb",
            name="市净率 (PB)",
            description="市净率在 1-3 倍区间为最优，资产质量好",
            default_weight=1.0,
            optimal_min=1,
            optimal_max=3,
            min_value=0,
            max_value=10,
            unit="倍",
            score_func=_score_pb,
        ),
        ScoringRule(
            rule_id="rsi",
            name="相对强弱 (RSI)",
            description="RSI 在 30-50 区间为最优，趋势健康",
            default_weight=1.0,
            optimal_min=30,
            optimal_max=50,
            min_value=0,
            max_value=100,
            unit="",
            score_func=_score_rsi,
        ),
        ScoringRule(
            rule_id="momentum_20d",
            name="20日动量",
            description="近20日涨幅大于 0 为最优，上涨趋势",
            default_weight=1.5,
            optimal_min=0,
            optimal_max=0.3,
            min_value=-0.3,
            max_value=0.3,
            unit="%",
            score_func=_score_momentum_20d,
        ),
        ScoringRule(
            rule_id="macd_golden_cross",
            name="MACD 金叉",
            description="MACD 线上穿信号线为金叉，买入信号",
            default_weight=1.5,
            optimal_min=0,
            optimal_max=0.1,
            min_value=-0.1,
            max_value=0.1,
            unit="",
            score_func=_score_macd_golden_cross,
        ),
        ScoringRule(
            rule_id="industry_rank",
            name="行业排名",
            description="行业综合排名前 30% 为最优",
            default_weight=1.0,
            optimal_min=0,
            optimal_max=0.3,
            min_value=0,
            max_value=1,
            unit="%",
            score_func=None,
        ),
        ScoringRule(
            rule_id="market_cap",
            name="市值规模",
            description="市值在 100-1000 亿区间为最优，流动性适中",
            default_weight=0.8,
            optimal_min=100,
            optimal_max=1000,
            min_value=10,
            max_value=5000,
            unit="亿",
            score_func=_score_market_cap,
        ),
    ]


@dataclass
class RuleScoreDetail:
    """单条规则的评分详情"""
    rule_id: str
    name: str
    raw_value: float
    score: float
    weight: float
    weighted_score: float
    enabled: bool


@dataclass
class StockScoreResult:
    """单只股票的综合评分结果"""
    symbol: str
    name: str
    industry: Optional[str]
    total_score: float
    max_possible_score: float
    normalized_score: float
    rule_details: List[RuleScoreDetail]


def _get_stock_data(session: Session, stock: Stock) -> Dict:
    """获取股票的所有相关数据用于评分"""
    snapshot = session.exec(
        select(StockSnapshot).where(StockSnapshot.stock_id == stock.id)
    ).first()

    factor = session.exec(
        select(FactorValue)
        .where(FactorValue.stock_id == stock.id)
        .order_by(FactorValue.factor_date.desc())
        .limit(1)
    ).first()

    data = {
        "pe_ratio": stock.pe_ratio,
        "pb_ratio": stock.pb_ratio,
        "market_cap": stock.market_cap,
        "industry": stock.industry,
        "rsi": snapshot.rsi if snapshot else None,
        "macd_line": snapshot.macd_line if snapshot else None,
        "macd_signal": snapshot.macd_signal if snapshot else None,
        "macd_hist": snapshot.macd_hist if snapshot else None,
        "kdj_k": snapshot.kdj_k if snapshot else None,
        "kdj_d": snapshot.kdj_d if snapshot else None,
        "kdj_j": snapshot.kdj_j if snapshot else None,
        "momentum": factor.momentum if factor else None,
        "volatility": factor.volatility if factor else None,
        "liquidity": factor.liquidity if factor else None,
        "close": snapshot.close if snapshot else None,
    }
    return data


def score_stock(
    session: Session,
    stock: Stock,
    rules: List[ScoringRule],
    weights: Optional[Dict[str, float]] = None,
    enabled_rules: Optional[Dict[str, bool]] = None,
    all_stocks: Optional[List[Stock]] = None,
) -> StockScoreResult:
    """
    对单只股票进行综合评分

    Args:
        session: 数据库会话
        stock: 股票对象
        rules: 评分规则列表
        weights: 自定义权重字典 {rule_id: weight}
        enabled_rules: 规则启停用字典 {rule_id: enabled}
        all_stocks: 所有股票列表（用于计算行业排名）

    Returns:
        StockScoreResult 评分结果
    """
    stock_data = _get_stock_data(session, stock)

    if all_stocks is None:
        all_stocks = session.exec(select(Stock)).all()

    rule_details: List[RuleScoreDetail] = []
    total_score = 0.0
    max_possible_score = 0.0

    for rule in rules:
        weight = weights.get(rule.rule_id, rule.default_weight) if weights else rule.default_weight
        enabled = enabled_rules.get(rule.rule_id, rule.enabled) if enabled_rules else rule.enabled

        if not enabled or weight <= 0:
            rule_details.append(RuleScoreDetail(
                rule_id=rule.rule_id,
                name=rule.name,
                raw_value=0.0,
                score=0.0,
                weight=weight,
                weighted_score=0.0,
                enabled=False,
            ))
            continue

        if rule.rule_id == "industry_rank":
            raw_value, score = _get_industry_rank(session, stock, all_stocks)
        elif rule.score_func:
            raw_value, score = rule.score_func(stock_data)
        else:
            raw_value, score = 0.0, 0.0

        weighted_score = score * weight
        total_score += weighted_score
        max_possible_score += weight

        rule_details.append(RuleScoreDetail(
            rule_id=rule.rule_id,
            name=rule.name,
            raw_value=raw_value,
            score=score,
            weight=weight,
            weighted_score=weighted_score,
            enabled=True,
        ))

    normalized_score = total_score / max_possible_score if max_possible_score > 0 else 0.0

    return StockScoreResult(
        symbol=stock.symbol,
        name=stock.name,
        industry=stock.industry,
        total_score=total_score,
        max_possible_score=max_possible_score,
        normalized_score=normalized_score,
        rule_details=rule_details,
    )


def get_top_n_recommendations(
    session: Session,
    n: int = 20,
    weights: Optional[Dict[str, float]] = None,
    enabled_rules: Optional[Dict[str, bool]] = None,
    industry_filter: Optional[str] = None,
) -> List[StockScoreResult]:
    """
    获取 Top-N 推荐股票

    Args:
        session: 数据库会话
        n: 返回股票数量
        weights: 自定义权重
        enabled_rules: 规则启用状态
        industry_filter: 行业筛选

    Returns:
        按综合评分排序的股票列表
    """
    rules = get_default_rules()

    query = select(Stock)
    if industry_filter:
        query = query.where(Stock.industry == industry_filter)

    stocks = session.exec(query).all()
    all_stocks = session.exec(select(Stock)).all()

    results = []
    for stock in stocks:
        result = score_stock(session, stock, rules, weights, enabled_rules, all_stocks)
        results.append(result)

    results.sort(key=lambda x: x.normalized_score, reverse=True)
    return results[:n]


def get_stock_score_detail(
    session: Session,
    symbol: str,
    weights: Optional[Dict[str, float]] = None,
    enabled_rules: Optional[Dict[str, bool]] = None,
) -> Optional[StockScoreResult]:
    """
    获取指定股票的评分明细

    Args:
        session: 数据库会话
        symbol: 股票代码
        weights: 自定义权重
        enabled_rules: 规则启用状态

    Returns:
        StockScoreResult 或 None
    """
    stock = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
    if not stock:
        return None

    rules = get_default_rules()
    all_stocks = session.exec(select(Stock)).all()
    return score_stock(session, stock, rules, weights, enabled_rules, all_stocks)
