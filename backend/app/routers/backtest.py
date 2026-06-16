import inspect
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.routers.deps import session_dep, require_permission, auth_dep
from app.models import Stock, DailyPrice, BacktestResult, StrategyDefinition
from app.schemas import BacktestRequest
from app.services.strategies import get_strategy_map
from app.services.backtest import run_backtest
from app.services.notification import create_notification
from app.services.auth import log_user_action

router = APIRouter(prefix="/api/v1")


@router.get("/strategies")
def list_strategies(session=Depends(session_dep)):
    strategies = session.exec(select(StrategyDefinition)).all()
    if not strategies:
        return [{"name": name, "description": f"{name}策略"} for name in get_strategy_map().keys()]
    return [s.dict() for s in strategies]


@router.post("/backtest/run")
def run_strategy_backtest(payload: BacktestRequest, session=Depends(session_dep), user=Depends(require_permission("backtest.run"))):
    strategy_map = get_strategy_map()
    if payload.strategy_name not in strategy_map:
        raise HTTPException(status_code=400, detail="策略不存在")
    results = []
    task_name = "策略回测"
    try:
        for symbol in payload.symbols:
            stock = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
            if not stock:
                continue
            prices = session.exec(select(DailyPrice).where(DailyPrice.stock_id == stock.id, DailyPrice.trade_date >= payload.start_date, DailyPrice.trade_date <= payload.end_date)).all()
            if not prices:
                continue
            df = pd.DataFrame([p.dict() for p in prices])
            if df.empty:
                continue
            df = df.sort_values("trade_date")
            strategy_func = strategy_map[payload.strategy_name]
            allowed_params = {k: v for k, v in payload.parameters.items() if k in inspect.signature(strategy_func).parameters}
            signal = strategy_func(df, **allowed_params)
            result = run_backtest(df, signal)
            metrics = result["metrics"]
            session.add(BacktestResult(
                strategy_name=payload.strategy_name,
                symbol=symbol,
                start_date=payload.start_date,
                end_date=payload.end_date,
                annual_return=metrics["annual_return"],
                max_drawdown=metrics["max_drawdown"],
                sharpe=metrics["sharpe"],
                win_rate=metrics["win_rate"],
                profit_factor=metrics["profit_factor"],
            ))
            results.append({"symbol": symbol, **metrics, "equity_curve": result["equity_curve"], "dates": result["dates"]})
        session.commit()
        avg_return = sum(r["annual_return"] for r in results) / len(results) if results else 0
        message = f"回测完成，{payload.strategy_name} 策略共回测 {len(results)} 只股票，平均年化收益: {avg_return:.2%}"
        create_notification(
            session,
            user_id=user.id,
            notification_type="backtest",
            title=f"{task_name}成功",
            content=message,
            link_url="/backtest",
            severity="success",
        )
        log_user_action(
            session,
            user_id=user.id,
            action_type="run_backtest",
            action_detail=f"运行回测: {payload.strategy_name}, {len(payload.symbols)}只股票, {payload.start_date}~{payload.end_date}"
        )
        return results
    except Exception as e:
        session.rollback()
        error_msg = f"{task_name}失败: {str(e)}"
        create_notification(
            session,
            user_id=user.id,
            notification_type="backtest",
            title=f"{task_name}失败",
            content=error_msg,
            link_url="/backtest",
            severity="error",
        )
        raise HTTPException(status_code=500, detail=error_msg)
