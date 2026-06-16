import numpy as np
import pandas as pd
from datetime import date
from typing import List, Dict, Optional, Tuple
from sqlmodel import select
from app.models import Stock, DailyPrice, IndexProduct, IndexDailyPrice


TRADING_DAYS = 252
CONFIDENCE_Z = {0.95: 1.645, 0.99: 2.326}


def _get_stock_prices(session, symbol: str, start_date: date, end_date: date) -> Optional[pd.DataFrame]:
    stock = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
    if not stock:
        return None
    prices = session.exec(
        select(DailyPrice)
        .where(DailyPrice.stock_id == stock.id)
        .where(DailyPrice.trade_date >= start_date)
        .where(DailyPrice.trade_date <= end_date)
        .order_by(DailyPrice.trade_date)
    ).all()
    if not prices:
        return None
    return pd.DataFrame([{
        "trade_date": p.trade_date,
        "close": float(p.close),
    } for p in prices])


def _get_index_prices(session, code: str, start_date: date, end_date: date) -> Optional[pd.DataFrame]:
    product = session.exec(select(IndexProduct).where(IndexProduct.code == code)).first()
    if not product:
        return None
    prices = session.exec(
        select(IndexDailyPrice)
        .where(IndexDailyPrice.index_id == product.id)
        .where(IndexDailyPrice.trade_date >= start_date)
        .where(IndexDailyPrice.trade_date <= end_date)
        .order_by(IndexDailyPrice.trade_date)
    ).all()
    if not prices:
        return None
    return pd.DataFrame([{
        "trade_date": p.trade_date,
        "close": float(p.close),
    } for p in prices])


def _compute_returns(prices_df: pd.DataFrame) -> pd.Series:
    if prices_df is None or prices_df.empty or len(prices_df) < 2:
        return pd.Series(dtype=float)
    df = prices_df.sort_values("trade_date").copy()
    returns = df["close"].pct_change().dropna()
    return returns


def var_historical(returns: pd.Series, confidence: float = 0.95, holding_period: int = 1) -> Optional[float]:
    if returns.empty:
        return None
    hp_factor = np.sqrt(holding_period)
    percentile = (1 - confidence) * 100
    return float(np.percentile(returns, percentile) * hp_factor)


def var_parametric(returns: pd.Series, confidence: float = 0.95, holding_period: int = 1) -> Optional[float]:
    if returns.empty or returns.std() == 0:
        return None
    mu = returns.mean()
    sigma = returns.std()
    z = CONFIDENCE_Z.get(confidence, 1.645)
    hp_factor = np.sqrt(holding_period)
    return float((mu - z * sigma) * hp_factor)


def compute_var(
    session,
    symbols: List[str],
    start_date: date,
    end_date: date,
    confidence_levels: List[float] | None = None,
    holding_period: int = 1,
) -> Dict:
    confidence_levels = confidence_levels or [0.95, 0.99]
    results = {}

    for symbol in symbols:
        prices = _get_stock_prices(session, symbol, start_date, end_date)
        returns = _compute_returns(prices)
        stock_info = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
        name = stock_info.name if stock_info else symbol
        data_points = len(returns)

        entry: Dict = {
            "symbol": symbol,
            "name": name,
            "data_points": data_points,
            "sufficient_data": data_points >= 30,
        }

        for cl in confidence_levels:
            vh = var_historical(returns, cl, holding_period)
            vp = var_parametric(returns, cl, holding_period)
            entry[f"var_historical_{int(cl * 100)}"] = round(vh * 100, 4) if vh is not None else None
            entry[f"var_parametric_{int(cl * 100)}"] = round(vp * 100, 4) if vp is not None else None

        results[symbol] = entry

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "holding_period": holding_period,
        "confidence_levels": confidence_levels,
        "items": list(results.values()),
    }


def linear_regression(x: np.ndarray, y: np.ndarray) -> Dict:
    n = len(x)
    if n < 3:
        return {
            "beta": None, "alpha": None, "r_squared": None, "p_value": None,
            "data_points": n, "sufficient_data": False,
        }
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    ss_xx = np.sum((x - x_mean) ** 2)
    ss_xy = np.sum((x - x_mean) * (y - y_mean))

    if ss_xx == 0:
        return {
            "beta": None, "alpha": None, "r_squared": None, "p_value": None,
            "data_points": n, "sufficient_data": False,
        }

    beta = ss_xy / ss_xx
    alpha = y_mean - beta * x_mean
    y_pred = alpha + beta * x
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    se_beta = np.sqrt(ss_res / (n - 2) / ss_xx) if n > 2 and ss_xx > 0 else None
    t_stat = beta / se_beta if se_beta and se_beta > 0 else None

    p_value = None
    if t_stat is not None:
        from math import gamma, sqrt, pi
        t = abs(t_stat)
        df = n - 2
        if df > 0:
            x_val = df / (df + t * t)
            try:
                from math import lgamma
                a = df / 2.0
                b = 0.5
                beta_ab = np.exp(lgamma(a) + lgamma(b) - lgamma(a + b))
                I = _regularized_incomplete_beta(x_val, a, b)
                p_value = float(I)
            except Exception:
                p_value = None

    return {
        "beta": round(float(beta), 4),
        "alpha": round(float(alpha * TRADING_DAYS), 4),
        "r_squared": round(float(r_squared), 4),
        "p_value": round(float(p_value), 4) if p_value is not None else None,
        "data_points": n,
        "sufficient_data": n >= 30,
    }


def _regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    if x == 0:
        return 0.0
    if x == 1:
        return 1.0
    from math import lgamma
    lbeta_ab = lgamma(a) + lgamma(b) - lgamma(a + b)
    front = np.exp(np.log(x) * a + np.log(1 - x) * b - lbeta_ab)

    if x < (a + 1) / (a + b + 2):
        return front * _betacf(x, a, b) / a
    else:
        return 1 - front * _betacf(1 - x, b, a) / b


def _betacf(x: float, a: float, b: float, max_iter: int = 200) -> float:
    fpmin = 1e-30
    qab = a + b
    qap = a + 1
    qam = a - 1
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h = h * d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h = h * delta
        if abs(delta - 1.0) < 3e-7:
            break
    return h


def compute_beta_alpha(
    session,
    symbols: List[str],
    benchmark_code: str,
    start_date: date,
    end_date: date,
) -> Dict:
    bench_prices = _get_index_prices(session, benchmark_code, start_date, end_date)
    if bench_prices is None:
        bench_prices = _get_stock_prices(session, benchmark_code, start_date, end_date)

    bench_info = session.exec(select(IndexProduct).where(IndexProduct.code == benchmark_code)).first()
    bench_name = bench_info.name if bench_info else benchmark_code
    if not bench_info:
        bench_stock = session.exec(select(Stock).where(Stock.symbol == benchmark_code)).first()
        if bench_stock:
            bench_name = bench_stock.name

    bench_returns = _compute_returns(bench_prices)

    items = []
    for symbol in symbols:
        stock_prices = _get_stock_prices(session, symbol, start_date, end_date)
        stock_returns = _compute_returns(stock_prices)
        stock_info = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
        name = stock_info.name if stock_info else symbol

        if stock_returns.empty or bench_returns.empty:
            items.append({
                "symbol": symbol,
                "name": name,
                "beta": None,
                "alpha": None,
                "r_squared": None,
                "p_value": None,
                "data_points": 0,
                "sufficient_data": False,
            })
            continue

        merged = pd.concat([stock_returns, bench_returns], axis=1, join="inner", keys=["stock", "bench"]).dropna()
        if merged.empty:
            items.append({
                "symbol": symbol,
                "name": name,
                "beta": None,
                "alpha": None,
                "r_squared": None,
                "p_value": None,
                "data_points": 0,
                "sufficient_data": False,
            })
            continue

        reg = linear_regression(merged["bench"].values, merged["stock"].values)
        items.append({
            "symbol": symbol,
            "name": name,
            **reg,
        })

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "benchmark_code": benchmark_code,
        "benchmark_name": bench_name,
        "items": items,
    }


def compute_correlation_matrix(
    session,
    symbols: List[str],
    start_date: date,
    end_date: date,
) -> Dict:
    all_returns = {}
    symbol_names = {}

    for symbol in symbols:
        prices = _get_stock_prices(session, symbol, start_date, end_date)
        returns = _compute_returns(prices)
        stock_info = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
        symbol_names[symbol] = stock_info.name if stock_info else symbol
        if not returns.empty:
            all_returns[symbol] = returns

    valid_symbols = list(all_returns.keys())
    if not valid_symbols:
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols": symbols,
            "symbol_names": symbol_names,
            "matrix": [],
            "data_points": {},
            "sufficient_data": {s: False for s in symbols},
        }

    df = pd.DataFrame(all_returns)
    df = df.dropna()

    corr = df.corr(method="pearson")

    data_points = {}
    sufficient_data = {}
    for s in symbols:
        if s in all_returns:
            count = len(all_returns[s].dropna())
            data_points[s] = count
            sufficient_data[s] = count >= 30
        else:
            data_points[s] = 0
            sufficient_data[s] = False

    matrix = []
    for i, s1 in enumerate(valid_symbols):
        row = []
        for j, s2 in enumerate(valid_symbols):
            val = corr.loc[s1, s2] if s1 in corr.index and s2 in corr.columns else None
            row.append(round(float(val), 4) if val is not None and pd.notna(val) else None)
        matrix.append(row)

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "symbols": valid_symbols,
        "symbol_names": symbol_names,
        "matrix": matrix,
        "data_points": data_points,
        "sufficient_data": sufficient_data,
    }


def compute_annual_volatility(returns: pd.Series) -> Optional[float]:
    if returns.empty or returns.std() == 0:
        return None
    return float(returns.std() * np.sqrt(TRADING_DAYS))


def compute_max_drawdown(prices_df: pd.DataFrame) -> Optional[float]:
    if prices_df is None or prices_df.empty:
        return None
    df = prices_df.sort_values("trade_date").copy()
    cumulative = df["close"]
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    return float(drawdown.min())


def compute_risk_metrics(
    session,
    symbols: List[str],
    start_date: date,
    end_date: date,
) -> Dict:
    items = []

    for symbol in symbols:
        prices = _get_stock_prices(session, symbol, start_date, end_date)
        returns = _compute_returns(prices)
        stock_info = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
        name = stock_info.name if stock_info else symbol
        data_points = len(returns)
        sufficient = data_points >= 30

        vol = compute_annual_volatility(returns)
        mdd = compute_max_drawdown(prices)

        total_return = None
        sharpe = None
        sortino = None
        calmar = None

        if prices is not None and not prices.empty:
            df_sorted = prices.sort_values("trade_date")
            if len(df_sorted) >= 2 and df_sorted.iloc[0]["close"] != 0:
                total_return = float((df_sorted.iloc[-1]["close"] / df_sorted.iloc[0]["close"]) - 1)

        if vol is not None and vol > 0 and returns.mean() is not None:
            sharpe = float((returns.mean() * TRADING_DAYS) / vol)

        if not returns.empty:
            downside = returns[returns < 0]
            if len(downside) > 0 and downside.std() > 0:
                downside_vol = float(downside.std() * np.sqrt(TRADING_DAYS))
                if downside_vol > 0:
                    sortino = float((returns.mean() * TRADING_DAYS) / downside_vol)

        if mdd is not None and mdd != 0 and total_return is not None:
            calmar = float(total_return / abs(mdd)) if abs(mdd) > 0 else None

        items.append({
            "symbol": symbol,
            "name": name,
            "data_points": data_points,
            "sufficient_data": sufficient,
            "annual_volatility": round(vol * 100, 2) if vol is not None else None,
            "max_drawdown": round(mdd * 100, 2) if mdd is not None else None,
            "total_return": round(total_return * 100, 2) if total_return is not None else None,
            "sharpe_ratio": round(sharpe, 2) if sharpe is not None else None,
            "sortino_ratio": round(sortino, 2) if sortino is not None else None,
            "calmar_ratio": round(calmar, 2) if calmar is not None else None,
        })

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "items": items,
    }


def compute_rolling_beta(
    session,
    symbols: List[str],
    benchmark_code: str,
    start_date: date,
    end_date: date,
    window: int = 60,
) -> Dict:
    bench_prices = _get_index_prices(session, benchmark_code, start_date, end_date)
    if bench_prices is None:
        bench_prices = _get_stock_prices(session, benchmark_code, start_date, end_date)
    bench_returns = _compute_returns(bench_prices)

    bench_info = session.exec(select(IndexProduct).where(IndexProduct.code == benchmark_code)).first()
    bench_name = bench_info.name if bench_info else benchmark_code
    if not bench_info:
        bench_stock = session.exec(select(Stock).where(Stock.symbol == benchmark_code)).first()
        if bench_stock:
            bench_name = bench_stock.name

    results = {}
    dates_series = []

    for symbol in symbols:
        prices = _get_stock_prices(session, symbol, start_date, end_date)
        returns = _compute_returns(prices)
        stock_info = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
        name = stock_info.name if stock_info else symbol

        if returns.empty or bench_returns.empty:
            results[symbol] = {"name": name, "series": [], "sufficient_data": False}
            continue

        merged = pd.concat([returns, bench_returns], axis=1, join="inner", keys=["stock", "bench"]).dropna()
        if len(merged) < window:
            results[symbol] = {
                "name": name,
                "series": [],
                "sufficient_data": False,
                "message": f"有效数据点 {len(merged)} 少于滚动窗口 {window}",
            }
            continue

        rolling_betas = []
        rolling_dates = []

        for i in range(window - 1, len(merged)):
            window_data = merged.iloc[i - window + 1 : i + 1]
            x = window_data["bench"].values
            y = window_data["stock"].values

            x_mean = np.mean(x)
            y_mean = np.mean(y)
            ss_xx = np.sum((x - x_mean) ** 2)
            ss_xy = np.sum((x - x_mean) * (y - y_mean))
            beta = ss_xy / ss_xx if ss_xx != 0 else np.nan

            td = window_data.index[-1]
            if hasattr(td, "isoformat"):
                date_str = td.isoformat()
            else:
                date_str = str(td)
            rolling_betas.append(round(float(beta), 4) if not np.isnan(beta) else None)
            rolling_dates.append(date_str)

        if not dates_series:
            dates_series = rolling_dates

        results[symbol] = {
            "name": name,
            "series": rolling_betas,
            "sufficient_data": True,
        }

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "benchmark_code": benchmark_code,
        "benchmark_name": bench_name,
        "window": window,
        "dates": dates_series,
        "items": results,
    }


def compute_all_risk_metrics(
    session,
    symbols: List[str],
    benchmark_code: str,
    start_date: date,
    end_date: date,
    confidence_levels: List[float] | None = None,
    holding_period: int = 1,
    rolling_window: int = 60,
) -> Dict:
    confidence_levels = confidence_levels or [0.95, 0.99]
    var_data = compute_var(session, symbols, start_date, end_date, confidence_levels, holding_period)
    beta_data = compute_beta_alpha(session, symbols, benchmark_code, start_date, end_date)
    corr_data = compute_correlation_matrix(session, symbols, start_date, end_date)
    metrics_data = compute_risk_metrics(session, symbols, start_date, end_date)
    rolling_beta_data = compute_rolling_beta(session, symbols, benchmark_code, start_date, end_date, rolling_window)

    return {
        "var": var_data,
        "beta_alpha": beta_data,
        "correlation": corr_data,
        "metrics": metrics_data,
        "rolling_beta": rolling_beta_data,
    }
