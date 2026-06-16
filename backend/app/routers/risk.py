from fastapi import APIRouter, Depends, HTTPException

from app.routers.deps import session_dep, auth_dep
from app.schemas import (
    RiskVarRequest,
    RiskBetaRequest,
    RiskCorrelationRequest,
    RiskMetricsRequest,
    RiskRollingBetaRequest,
    RiskAllRequest,
)
from app.services.risk import (
    compute_var,
    compute_beta_alpha,
    compute_correlation_matrix,
    compute_risk_metrics,
    compute_rolling_beta,
    compute_all_risk_metrics,
)
from app.services.auth import log_user_action

router = APIRouter(prefix="/api/v1")


@router.post("/risk/var")
def get_var(
    payload: RiskVarRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="请至少选择一只股票")
    result = compute_var(
        session,
        symbols=payload.symbols,
        start_date=payload.start_date,
        end_date=payload.end_date,
        confidence_levels=payload.confidence_levels,
        holding_period=payload.holding_period,
    )
    log_user_action(
        session,
        user_id=user.id,
        action_type="risk_var",
        action_detail=f"VaR计算: {len(payload.symbols)}只股票, 置信度{payload.confidence_levels}, 持有期{payload.holding_period}天"
    )
    return result


@router.post("/risk/beta_alpha")
def get_beta_alpha(
    payload: RiskBetaRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="请至少选择一只股票")
    result = compute_beta_alpha(
        session,
        symbols=payload.symbols,
        benchmark_code=payload.benchmark_code,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    log_user_action(
        session,
        user_id=user.id,
        action_type="risk_beta",
        action_detail=f"Beta/Alpha计算: {len(payload.symbols)}只股票, 基准{payload.benchmark_code}"
    )
    return result


@router.post("/risk/correlation")
def get_correlation(
    payload: RiskCorrelationRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="请至少选择一只股票")
    result = compute_correlation_matrix(
        session,
        symbols=payload.symbols,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    log_user_action(
        session,
        user_id=user.id,
        action_type="risk_correlation",
        action_detail=f"相关性矩阵: {len(payload.symbols)}只股票"
    )
    return result


@router.post("/risk/metrics")
def get_metrics(
    payload: RiskMetricsRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="请至少选择一只股票")
    result = compute_risk_metrics(
        session,
        symbols=payload.symbols,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    log_user_action(
        session,
        user_id=user.id,
        action_type="risk_metrics",
        action_detail=f"风险指标计算: {len(payload.symbols)}只股票"
    )
    return result


@router.post("/risk/rolling_beta")
def get_rolling_beta(
    payload: RiskRollingBetaRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="请至少选择一只股票")
    result = compute_rolling_beta(
        session,
        symbols=payload.symbols,
        benchmark_code=payload.benchmark_code,
        start_date=payload.start_date,
        end_date=payload.end_date,
        window=payload.window,
    )
    log_user_action(
        session,
        user_id=user.id,
        action_type="risk_rolling_beta",
        action_detail=f"滚动Beta: {len(payload.symbols)}只股票, 窗口{payload.window}天"
    )
    return result


@router.post("/risk/all")
def get_all_risk(
    payload: RiskAllRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="请至少选择一只股票")
    result = compute_all_risk_metrics(
        session,
        symbols=payload.symbols,
        benchmark_code=payload.benchmark_code,
        start_date=payload.start_date,
        end_date=payload.end_date,
        confidence_levels=payload.confidence_levels,
        holding_period=payload.holding_period,
        rolling_window=payload.rolling_window,
    )
    log_user_action(
        session,
        user_id=user.id,
        action_type="risk_all",
        action_detail=f"综合风险分析: {len(payload.symbols)}只股票, 基准{payload.benchmark_code}"
    )
    return result
