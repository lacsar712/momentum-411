import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.routers.deps import session_dep, auth_dep
from app.models import ScoringCardPreset
from app.schemas import (
    RecommendationRequest, CustomScoreRequest, ScoringCardSaveRequest,
    ScoringCardInfo, RecommendationResponse, ScoringRuleListResponse,
    ScoringCardListResponse, StockScoreItem,
)
from app.services.recommend import (
    get_default_rules,
    get_top_n_recommendations,
    get_stock_score_detail,
    score_stock,
)
from app.services.cache import cache_get, cache_set
from app.services.auth import log_user_action

router = APIRouter(prefix="/api/v1")


def _convert_score_result_to_item(result) -> StockScoreItem:
    return StockScoreItem(
        symbol=result.symbol,
        name=result.name,
        industry=result.industry,
        total_score=round(result.total_score, 4),
        max_possible_score=round(result.max_possible_score, 4),
        normalized_score=round(result.normalized_score, 4),
        rule_details=[
            {
                "rule_id": rd.rule_id,
                "name": rd.name,
                "raw_value": round(rd.raw_value, 4),
                "score": round(rd.score, 4),
                "weight": round(rd.weight, 4),
                "weighted_score": round(rd.weighted_score, 4),
                "enabled": rd.enabled,
            }
            for rd in result.rule_details
        ],
    )


@router.get("/recommend/rules", response_model=ScoringRuleListResponse)
def get_scoring_rules():
    rules = get_default_rules()
    return {
        "rules": [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "description": r.description,
                "default_weight": r.default_weight,
                "min_value": r.min_value,
                "max_value": r.max_value,
                "optimal_min": r.optimal_min,
                "optimal_max": r.optimal_max,
                "unit": r.unit,
            }
            for r in rules
        ]
    }


@router.post("/recommend/top", response_model=RecommendationResponse)
def get_top_recommendations(
    payload: RecommendationRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    cache_key = f"recommend:top:{json.dumps(payload.dict(), ensure_ascii=False)}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    results = get_top_n_recommendations(
        session,
        n=payload.n,
        weights=payload.weights,
        enabled_rules=payload.enabled_rules,
        industry_filter=payload.industry_filter,
    )

    items = [_convert_score_result_to_item(r) for r in results]
    response = {"total": len(items), "items": items}
    cache_set(cache_key, response, ttl=120)

    log_user_action(
        session,
        user_id=user.id,
        action_type="recommend_top",
        action_detail=f"获取Top-{payload.n}推荐, 命中{len(items)}只股票"
    )
    return response


@router.post("/recommend/custom", response_model=RecommendationResponse)
def get_custom_score_recommendations(
    payload: CustomScoreRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    weights = payload.weights
    enabled_rules = payload.enabled_rules

    if payload.rule_configs:
        weights = {rc.rule_id: rc.weight for rc in payload.rule_configs}
        enabled_rules = {rc.rule_id: rc.enabled for rc in payload.rule_configs}

    results = get_top_n_recommendations(
        session,
        n=payload.n,
        weights=weights,
        enabled_rules=enabled_rules,
    )

    items = [_convert_score_result_to_item(r) for r in results]
    response = {"total": len(items), "items": items}

    log_user_action(
        session,
        user_id=user.id,
        action_type="recommend_custom",
        action_detail=f"自定义权重评分, 返回{len(items)}只股票"
    )
    return response


@router.get("/recommend/stock/{symbol}", response_model=StockScoreItem)
def get_stock_detail_score(
    symbol: str,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    weights_param = None
    enabled_param = None

    result = get_stock_score_detail(session, symbol, weights_param, enabled_param)
    if not result:
        raise HTTPException(status_code=404, detail="股票不存在或无评分数据")

    log_user_action(
        session,
        user_id=user.id,
        action_type="recommend_stock_detail",
        action_detail=f"查看股票{symbol}评分明细"
    )
    return _convert_score_result_to_item(result)


@router.post("/recommend/stock/{symbol}", response_model=StockScoreItem)
def get_stock_detail_score_custom(
    symbol: str,
    payload: CustomScoreRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    weights = payload.weights
    enabled_rules = payload.enabled_rules

    if payload.rule_configs:
        weights = {rc.rule_id: rc.weight for rc in payload.rule_configs}
        enabled_rules = {rc.rule_id: rc.enabled for rc in payload.rule_configs}

    result = get_stock_score_detail(session, symbol, weights, enabled_rules)
    if not result:
        raise HTTPException(status_code=404, detail="股票不存在或无评分数据")

    return _convert_score_result_to_item(result)


@router.get("/recommend/cards", response_model=ScoringCardListResponse)
def list_scoring_cards(
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    query = select(ScoringCardPreset).where(ScoringCardPreset.user_id == user.id).order_by(
        ScoringCardPreset.is_default.desc(), ScoringCardPreset.updated_at.desc()
    )
    presets = session.exec(query).all()

    items = []
    for p in presets:
        items.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "weights": json.loads(p.weights_json),
            "enabled_rules": json.loads(p.enabled_rules_json) if p.enabled_rules_json else {},
            "is_default": p.is_default,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        })

    return {"total": len(items), "items": items}


@router.post("/recommend/cards", response_model=ScoringCardInfo)
def save_scoring_card(
    payload: ScoringCardSaveRequest,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    existing = session.exec(
        select(ScoringCardPreset).where(
            ScoringCardPreset.user_id == user.id,
            ScoringCardPreset.name == payload.name,
        )
    ).first()

    if existing:
        existing.description = payload.description
        existing.weights_json = json.dumps(payload.weights, ensure_ascii=False)
        existing.enabled_rules_json = json.dumps(payload.enabled_rules, ensure_ascii=False)
        existing.updated_at = datetime.utcnow()
        preset = existing
        action = "更新"
    else:
        preset = ScoringCardPreset(
            user_id=user.id,
            name=payload.name,
            description=payload.description,
            weights_json=json.dumps(payload.weights, ensure_ascii=False),
            enabled_rules_json=json.dumps(payload.enabled_rules, ensure_ascii=False),
            is_default=payload.is_default,
        )
        session.add(preset)
        action = "创建"

    if payload.is_default:
        other_defaults = session.exec(
            select(ScoringCardPreset).where(
                ScoringCardPreset.user_id == user.id,
                ScoringCardPreset.id != preset.id,
                ScoringCardPreset.is_default == True,
            )
        ).all()
        for d in other_defaults:
            d.is_default = False

    session.commit()
    session.refresh(preset)

    log_user_action(
        session,
        user_id=user.id,
        action_type="recommend_save_card",
        action_detail=f"{action}评分卡方案: {payload.name}"
    )

    return {
        "id": preset.id,
        "name": preset.name,
        "description": preset.description,
        "weights": json.loads(preset.weights_json),
        "enabled_rules": json.loads(preset.enabled_rules_json) if preset.enabled_rules_json else {},
        "is_default": preset.is_default,
        "created_at": preset.created_at,
        "updated_at": preset.updated_at,
    }


@router.get("/recommend/cards/{card_id}", response_model=ScoringCardInfo)
def load_scoring_card(
    card_id: int,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    preset = session.exec(
        select(ScoringCardPreset).where(
            ScoringCardPreset.id == card_id,
            ScoringCardPreset.user_id == user.id,
        )
    ).first()

    if not preset:
        raise HTTPException(status_code=404, detail="评分卡方案不存在")

    log_user_action(
        session,
        user_id=user.id,
        action_type="recommend_load_card",
        action_detail=f"加载评分卡方案: {preset.name}"
    )

    return {
        "id": preset.id,
        "name": preset.name,
        "description": preset.description,
        "weights": json.loads(preset.weights_json),
        "enabled_rules": json.loads(preset.enabled_rules_json) if preset.enabled_rules_json else {},
        "is_default": preset.is_default,
        "created_at": preset.created_at,
        "updated_at": preset.updated_at,
    }


@router.delete("/recommend/cards/{card_id}")
def delete_scoring_card(
    card_id: int,
    session=Depends(session_dep),
    user=Depends(auth_dep),
):
    preset = session.exec(
        select(ScoringCardPreset).where(
            ScoringCardPreset.id == card_id,
            ScoringCardPreset.user_id == user.id,
        )
    ).first()

    if not preset:
        raise HTTPException(status_code=404, detail="评分卡方案不存在")

    session.delete(preset)
    session.commit()

    log_user_action(
        session,
        user_id=user.id,
        action_type="recommend_delete_card",
        action_detail=f"删除评分卡方案: {preset.name}"
    )

    return {"status": "ok"}
