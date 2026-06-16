import io
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import select
import pandas as pd

from app.routers.deps import session_dep, auth_dep, require_permission
from app.models import ScreeningPreset
from app.schemas import ScreeningRequest, ScreeningExportRequest, ScreeningResponse, PresetRequest
from app.services.screening import screen_stocks
from app.services.cache import cache_get, cache_set
from app.services.auth import log_user_action

router = APIRouter(prefix="/api/v1")


@router.post("/screening/run", response_model=ScreeningResponse)
def run_screening(payload: ScreeningRequest, session=Depends(session_dep), user=Depends(auth_dep)):
    cache_key = f"screen:{json.dumps(payload.dict(), ensure_ascii=False)}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    items = screen_stocks(session, payload.dict())
    response = {"total": len(items), "items": items}
    cache_set(cache_key, response, ttl=300)
    log_user_action(
        session,
        user_id=user.id,
        action_type="run_screening",
        action_detail=f"运行选股, 命中{len(items)}只股票"
    )
    return response


@router.post("/screening/export")
def export_screening(payload: ScreeningExportRequest, session=Depends(session_dep), user=Depends(require_permission("screening.export"))):
    items = screen_stocks(session, payload.dict())
    df = pd.DataFrame(items)
    if payload.file_type == "xlsx":
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=screening.xlsx"})
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=screening.csv"})


@router.post("/screening/preset")
def save_preset(payload: PresetRequest, session=Depends(session_dep), user=Depends(auth_dep)):
    preset = session.exec(select(ScreeningPreset).where(ScreeningPreset.name == payload.name)).first()
    action = "更新" if preset else "新建"
    if preset:
        preset.payload_json = json.dumps(payload.payload, ensure_ascii=False)
    else:
        preset = ScreeningPreset(name=payload.name, payload_json=json.dumps(payload.payload, ensure_ascii=False))
        session.add(preset)
    session.commit()
    log_user_action(session, user_id=user.id, action_type="save_preset", action_detail=f"{action}选股方案: {payload.name}")
    return {"status": "ok"}


@router.get("/screening/preset")
def list_presets(session=Depends(session_dep)):
    presets = session.exec(select(ScreeningPreset)).all()
    return [{"name": p.name, "payload": json.loads(p.payload_json)} for p in presets]


@router.delete("/screening/preset")
def delete_preset(name: str, session=Depends(session_dep), user=Depends(auth_dep)):
    preset = session.exec(select(ScreeningPreset).where(ScreeningPreset.name == name)).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    session.delete(preset)
    session.commit()
    return {"status": "ok"}


from fastapi import HTTPException
