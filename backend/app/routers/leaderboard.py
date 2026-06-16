from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.deps import session_dep, auth_dep
from app.schemas import LeaderboardResponse, LeaderboardDimensionListResponse, CustomLeaderboardRequest
from app.services.leaderboard import (
    get_leaderboard,
    get_custom_leaderboard,
    LEADERBOARD_DIMENSIONS,
)
from app.services.auth import log_user_action

router = APIRouter(prefix="/api/v1")


@router.get("/leaderboard/dimensions", response_model=LeaderboardDimensionListResponse)
def list_leaderboard_dimensions():
    return {"dimensions": LEADERBOARD_DIMENSIONS}


@router.get("/leaderboard/{dimension}", response_model=LeaderboardResponse)
def get_leaderboard_data(
    dimension: str,
    period: int = Query(1, ge=1, le=60),
    market: str = Query("all", pattern="^(all|sh|sz|cyb)$"),
    limit: int = Query(50, ge=1, le=200),
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    valid_dimensions = [d["key"] for d in LEADERBOARD_DIMENSIONS]
    if dimension not in valid_dimensions:
        raise HTTPException(status_code=400, detail=f"无效的排行榜维度: {dimension}")

    result = get_leaderboard(
        session,
        dimension=dimension,
        period=period,
        market=market,
        limit=limit,
    )

    log_user_action(
        session,
        user_id=user.id,
        action_type="leaderboard_view",
        action_detail=f"查看排行榜: {dimension}, 周期:{period}日, 市场:{market}"
    )

    return result


@router.post("/leaderboard/custom", response_model=LeaderboardResponse)
def get_custom_leaderboard_data(
    payload: CustomLeaderboardRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    result = get_custom_leaderboard(
        session,
        sort_field=payload.sort_field,
        sort_order=payload.sort_order,
        market=payload.market,
        limit=payload.limit,
    )

    log_user_action(
        session,
        user_id=user.id,
        action_type="leaderboard_custom",
        action_detail=f"自定义排行榜: {payload.sort_field} {payload.sort_order}, 市场:{payload.market}"
    )

    return result
