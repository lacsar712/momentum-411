from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.routers.deps import session_dep, auth_dep
from app.schemas import (
    PortfolioCreateRequest,
    PortfolioUpdateRequest,
    PortfolioCopyRequest,
    PortfolioResponse,
    PortfolioListResponse,
    PortfolioHoldingCreateRequest,
    PortfolioHoldingUpdateRequest,
    PortfolioHoldingsBatchSaveRequest,
    PortfolioHoldingsResponse,
    PortfolioNavResponse,
    PortfolioMetricsResponse,
    RebalanceResponse,
)
from app.services.portfolio import (
    get_portfolio_list,
    get_portfolio_detail,
    create_portfolio,
    update_portfolio,
    copy_portfolio,
    delete_portfolio,
    batch_save_holdings,
    add_holding,
    update_holding,
    delete_holding,
    calculate_portfolio_nav,
    calculate_portfolio_metrics,
    get_rebalance_suggestions,
)
from app.services.auth import log_user_action

router = APIRouter(prefix="/api/v1")


@router.get("/portfolio", response_model=PortfolioListResponse)
def list_portfolios(user=Depends(auth_dep), session=Depends(session_dep)):
    items = get_portfolio_list(session, user.id)
    return {"total": len(items), "items": items}


@router.get("/portfolio/{portfolio_id}", response_model=PortfolioResponse)
def get_portfolio(portfolio_id: int, user=Depends(auth_dep), session=Depends(session_dep)):
    detail = get_portfolio_detail(session, portfolio_id, user.id)
    if not detail:
        raise HTTPException(status_code=404, detail="组合不存在")
    return detail


@router.post("/portfolio", response_model=PortfolioResponse)
def create_new_portfolio(
    payload: PortfolioCreateRequest,
    user=Depends(auth_dep), session=Depends(session_dep)):
    holdings_data = [h.dict(exclude_none=True) for h in payload.holdings]
    result, err = create_portfolio(
        session,
        user.id,
        payload.name,
        payload.description,
        payload.benchmark_code or "000300",
        payload.rebalance_frequency or "monthly",
        holdings_data,
    )
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="create_portfolio", action_detail=f"创建组合: {payload.name}")
    return result


@router.put("/portfolio/{portfolio_id}", response_model=PortfolioResponse)
def update_existing_portfolio(
    portfolio_id: int,
    payload: PortfolioUpdateRequest,
    user=Depends(auth_dep), session=Depends(session_dep)):
    update_data = payload.dict(exclude_unset=True)
    result, err = update_portfolio(session, portfolio_id, user.id, update_data)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="update_portfolio", action_detail=f"更新组合: id={portfolio_id}")
    return result


@router.post("/portfolio/{portfolio_id}/copy", response_model=PortfolioResponse)
def copy_existing_portfolio(
    portfolio_id: int,
    payload: PortfolioCopyRequest,
    user=Depends(auth_dep), session=Depends(session_dep)):
    result, err = copy_portfolio(session, portfolio_id, user.id, payload.new_name)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="copy_portfolio", action_detail=f"复制组合: id={portfolio_id} -> {payload.new_name}")
    return result


@router.delete("/portfolio/{portfolio_id}")
def delete_existing_portfolio(
    portfolio_id: int,
    user=Depends(auth_dep), session=Depends(session_dep)):
    ok, err = delete_portfolio(session, portfolio_id, user.id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="delete_portfolio", action_detail=f"删除组合: id={portfolio_id}")
    return {"status": "ok"}


@router.get("/portfolio/{portfolio_id}/holdings", response_model=PortfolioHoldingsResponse)
def list_holdings(portfolio_id: int, user=Depends(auth_dep), session=Depends(session_dep)):
    detail = get_portfolio_detail(session, portfolio_id, user.id)
    if not detail:
        raise HTTPException(status_code=404, detail="组合不存在")
    return {"total": len(detail["holdings"]), "items": detail["holdings"]}


@router.put("/portfolio/{portfolio_id}/holdings/batch", response_model=PortfolioHoldingsResponse)
def batch_update_holdings(
    portfolio_id: int,
    payload: PortfolioHoldingsBatchSaveRequest,
    user=Depends(auth_dep), session=Depends(session_dep)):
    holdings_data = [h.dict(exclude_none=True) for h in payload.holdings]
    result, err = batch_save_holdings(session, portfolio_id, user.id, holdings_data)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="update_holdings", action_detail=f"批量保存持仓: portfolio_id={portfolio_id}, {len(payload.holdings)}只")
    return {"total": len(result) if result else 0, "items": result or []}


@router.post("/portfolio/{portfolio_id}/holdings")
def add_single_holding(
    portfolio_id: int,
    payload: PortfolioHoldingCreateRequest,
    user=Depends(auth_dep), session=Depends(session_dep)):
    result, err = add_holding(session, portfolio_id, user.id, payload.symbol, payload.target_weight)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="add_holding", action_detail=f"添加持仓: {payload.symbol}={payload.target_weight}%")
    return result


@router.patch("/portfolio/{portfolio_id}/holdings/{holding_id}")
def update_single_holding(
    portfolio_id: int,
    holding_id: int,
    payload: PortfolioHoldingUpdateRequest,
    user=Depends(auth_dep), session=Depends(session_dep)):
    result, err = update_holding(session, portfolio_id, user.id, holding_id, payload.target_weight)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="update_holding", action_detail=f"更新持仓: holding_id={holding_id}")
    return result


@router.delete("/portfolio/{portfolio_id}/holdings/{holding_id}")
def delete_single_holding(
    portfolio_id: int,
    holding_id: int,
    user=Depends(auth_dep), session=Depends(session_dep)):
    ok, err = delete_holding(session, portfolio_id, user.id, holding_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    log_user_action(session, user_id=user.id, action_type="delete_holding", action_detail=f"删除持仓: holding_id={holding_id}")
    return {"status": "ok"}


@router.get("/portfolio/{portfolio_id}/nav", response_model=PortfolioNavResponse)
def get_portfolio_nav_history(
    portfolio_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user=Depends(auth_dep), session=Depends(session_dep)):
    result, err = calculate_portfolio_nav(session, portfolio_id, user.id, start_date, end_date)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {
        "start_date": result["start_date"],
        "end_date": result["end_date"],
        "rebalance_frequency": result["rebalance_frequency"],
        "rebalance_count": result["rebalance_count"],
        "data": result["data"],
    }


@router.get("/portfolio/{portfolio_id}/metrics", response_model=PortfolioMetricsResponse)
def get_portfolio_analysis_metrics(
    portfolio_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user=Depends(auth_dep), session=Depends(session_dep)):
    result, err = calculate_portfolio_metrics(session, portfolio_id, user.id, start_date, end_date)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return result


@router.get("/portfolio/{portfolio_id}/rebalance", response_model=RebalanceResponse)
def get_suggested_rebalance(
    portfolio_id: int,
    threshold: float = Query(5.0, ge=0.1, le=50.0, description="偏离阈值（百分比）"),
    portfolio_value: float = Query(1000000.0, ge=0, description="组合总市值（用于计算建议金额）"),
    user=Depends(auth_dep), session=Depends(session_dep)):
    result, err = get_rebalance_suggestions(session, portfolio_id, user.id, threshold, portfolio_value)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return result
