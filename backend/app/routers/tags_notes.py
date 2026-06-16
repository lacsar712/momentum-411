from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.routers.deps import session_dep, auth_dep
from app.models import Stock, StockTag, StockTagMap, StockNote
from app.schemas import (
    StockTagCreateRequest, StockTagUpdateRequest, StockTagResponse,
    StockTagListResponse, StockTagAssignRequest, StockTagBatchAssignRequest,
    StockNoteCreateRequest, StockNoteUpdateRequest, StockNoteResponse,
    StockNoteListResponse, StockTagNoteAggregateResponse,
)
from app.services.auth import log_user_action

router = APIRouter(prefix="/api/v1")


@router.get("/tags", response_model=StockTagListResponse)
def list_stock_tags(
    user=Depends(auth_dep),
    session=Depends(session_dep),
    keyword: str = "",
):
    query = select(StockTag).where(StockTag.user_id == user.id)
    if keyword:
        query = query.where(StockTag.name.contains(keyword))
    query = query.order_by(StockTag.updated_at.desc())

    tags = session.exec(query).all()

    items = []
    for tag in tags:
        count = len(session.exec(
            select(StockTagMap).where(
                StockTagMap.user_id == user.id,
                StockTagMap.tag_id == tag.id,
            )
        ).all())
        items.append({
            "id": tag.id,
            "name": tag.name,
            "color": tag.color,
            "description": tag.description,
            "stock_count": count,
            "created_at": tag.created_at,
            "updated_at": tag.updated_at,
        })

    return {"total": len(items), "items": items}


@router.post("/tags", response_model=StockTagResponse)
def create_stock_tag(
    payload: StockTagCreateRequest,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    existing = session.exec(
        select(StockTag).where(
            StockTag.user_id == user.id,
            StockTag.name == payload.name,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="标签名称已存在")

    tag = StockTag(
        user_id=user.id,
        name=payload.name,
        color=payload.color or "#3b82f6",
        description=payload.description,
    )
    session.add(tag)
    session.commit()
    session.refresh(tag)

    log_user_action(session, user_id=user.id, action_type="create_tag", action_detail=f"创建标签: {payload.name}")

    return {
        "id": tag.id,
        "name": tag.name,
        "color": tag.color,
        "description": tag.description,
        "stock_count": 0,
        "created_at": tag.created_at,
        "updated_at": tag.updated_at,
    }


@router.put("/tags/{tag_id}", response_model=StockTagResponse)
def update_stock_tag(
    tag_id: int,
    payload: StockTagUpdateRequest,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    tag = session.exec(
        select(StockTag).where(
            StockTag.id == tag_id,
            StockTag.user_id == user.id,
        )
    ).first()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")

    if payload.name is not None and payload.name != tag.name:
        existing = session.exec(
            select(StockTag).where(
                StockTag.user_id == user.id,
                StockTag.name == payload.name,
                StockTag.id != tag_id,
            )
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="标签名称已存在")
        tag.name = payload.name

    if payload.color is not None:
        tag.color = payload.color
    if payload.description is not None:
        tag.description = payload.description

    tag.updated_at = datetime.utcnow()
    session.add(tag)
    session.commit()
    session.refresh(tag)

    count = len(session.exec(
        select(StockTagMap).where(
            StockTagMap.user_id == user.id,
            StockTagMap.tag_id == tag.id,
        )
    ).all())

    log_user_action(session, user_id=user.id, action_type="update_tag", action_detail=f"更新标签: {tag.name}")

    return {
        "id": tag.id,
        "name": tag.name,
        "color": tag.color,
        "description": tag.description,
        "stock_count": count,
        "created_at": tag.created_at,
        "updated_at": tag.updated_at,
    }


@router.delete("/tags/{tag_id}")
def delete_stock_tag(
    tag_id: int,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    tag = session.exec(
        select(StockTag).where(
            StockTag.id == tag_id,
            StockTag.user_id == user.id,
        )
    ).first()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")

    tag_name = tag.name

    maps = session.exec(
        select(StockTagMap).where(
            StockTagMap.user_id == user.id,
            StockTagMap.tag_id == tag_id,
        )
    ).all()
    for m in maps:
        session.delete(m)

    session.delete(tag)
    session.commit()

    log_user_action(session, user_id=user.id, action_type="delete_tag", action_detail=f"删除标签: {tag_name}")

    return {"status": "ok"}


@router.post("/tags/assign")
def assign_tags_to_stock(
    payload: StockTagAssignRequest,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    stock = session.exec(select(Stock).where(Stock.symbol == payload.symbol)).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")

    existing_maps = session.exec(
        select(StockTagMap).where(
            StockTagMap.user_id == user.id,
            StockTagMap.symbol == payload.symbol,
        )
    ).all()
    for m in existing_maps:
        session.delete(m)

    for tag_id in payload.tag_ids:
        tag = session.exec(
            select(StockTag).where(
                StockTag.id == tag_id,
                StockTag.user_id == user.id,
            )
        ).first()
        if tag:
            session.add(StockTagMap(
                user_id=user.id,
                symbol=payload.symbol,
                tag_id=tag_id,
            ))

    session.commit()

    log_user_action(session, user_id=user.id, action_type="assign_tags", action_detail=f"给股票 {payload.symbol} 打标签: {len(payload.tag_ids)}个")

    return {"status": "ok"}


@router.post("/tags/batch_assign")
def batch_assign_tags(
    payload: StockTagBatchAssignRequest,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    added_count = 0
    for symbol in payload.symbols:
        stock = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
        if not stock:
            continue
        for tag_id in payload.tag_ids:
            existing = session.exec(
                select(StockTagMap).where(
                    StockTagMap.user_id == user.id,
                    StockTagMap.symbol == symbol,
                    StockTagMap.tag_id == tag_id,
                )
            ).first()
            if not existing:
                session.add(StockTagMap(
                    user_id=user.id,
                    symbol=symbol,
                    tag_id=tag_id,
                ))
                added_count += 1

    session.commit()

    log_user_action(session, user_id=user.id, action_type="batch_assign_tags", action_detail=f"批量打标签: {len(payload.symbols)}只股票, {len(payload.tag_ids)}个标签, 新增{added_count}个映射")

    return {"status": "ok", "added_count": added_count}


@router.get("/tags/stock/{symbol}")
def get_stock_tags(
    symbol: str,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    maps = session.exec(
        select(StockTagMap).where(
            StockTagMap.user_id == user.id,
            StockTagMap.symbol == symbol,
        )
    ).all()

    tag_ids = [m.tag_id for m in maps]
    if not tag_ids:
        return {"symbol": symbol, "total": 0, "items": []}

    tags = session.exec(
        select(StockTag).where(StockTag.id.in_(tag_ids))
    ).all()

    items = []
    for tag in tags:
        count = len(session.exec(
            select(StockTagMap).where(
                StockTagMap.user_id == user.id,
                StockTagMap.tag_id == tag.id,
            )
        ).all())
        items.append({
            "id": tag.id,
            "name": tag.name,
            "color": tag.color,
            "description": tag.description,
            "stock_count": count,
            "created_at": tag.created_at,
            "updated_at": tag.updated_at,
        })

    return {"symbol": symbol, "total": len(items), "items": items}


@router.get("/tags/{tag_id}/stocks")
def get_stocks_by_tag(
    tag_id: int,
    user=Depends(auth_dep),
    session=Depends(session_dep),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    tag = session.exec(
        select(StockTag).where(
            StockTag.id == tag_id,
            StockTag.user_id == user.id,
        )
    ).first()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")

    maps_query = select(StockTagMap).where(
        StockTagMap.user_id == user.id,
        StockTagMap.tag_id == tag_id,
    ).order_by(StockTagMap.created_at.desc())

    all_maps = session.exec(maps_query).all()
    total = len(all_maps)

    maps = session.exec(maps_query.offset(offset).limit(limit)).all()

    symbols = [m.symbol for m in maps]
    if not symbols:
        return {"tag_id": tag_id, "tag_name": tag.name, "total": 0, "items": []}

    stocks = session.exec(select(Stock).where(Stock.symbol.in_(symbols))).all()
    stock_map = {s.symbol: s for s in stocks}

    items = []
    for symbol in symbols:
        stock = stock_map.get(symbol)
        if stock:
            items.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "market": stock.market,
                "industry": stock.industry,
            })

    return {"tag_id": tag_id, "tag_name": tag.name, "total": total, "items": items}


@router.get("/notes", response_model=StockNoteListResponse)
def list_stock_notes(
    user=Depends(auth_dep),
    session=Depends(session_dep),
    keyword: str = "",
    tag_id: Optional[int] = None,
    symbol: Optional[str] = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = select(StockNote).where(StockNote.user_id == user.id)

    if symbol:
        query = query.where(StockNote.symbol == symbol)

    if keyword:
        query = query.where(
            StockNote.content.contains(keyword) | (StockNote.title.contains(keyword) if StockNote.title else False)
        )

    if tag_id:
        tag_maps = session.exec(
            select(StockTagMap).where(
                StockTagMap.user_id == user.id,
                StockTagMap.tag_id == tag_id,
            )
        ).all()
        tag_symbols = [m.symbol for m in tag_maps]
        if tag_symbols:
            query = query.where(StockNote.symbol.in_(tag_symbols))
        else:
            return {"total": 0, "items": []}

    query = query.order_by(StockNote.updated_at.desc())

    all_notes = session.exec(query).all()
    total = len(all_notes)

    notes = session.exec(query.offset(offset).limit(limit)).all()

    symbols = list(set([n.symbol for n in notes]))
    stocks = session.exec(select(Stock).where(Stock.symbol.in_(symbols))).all() if symbols else []
    stock_map = {s.symbol: s for s in stocks}

    items = []
    for note in notes:
        stock = stock_map.get(note.symbol)
        items.append({
            "id": note.id,
            "symbol": note.symbol,
            "stock_name": stock.name if stock else None,
            "title": note.title,
            "content": note.content,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        })

    return {"total": total, "items": items}


@router.post("/notes", response_model=StockNoteResponse)
def create_stock_note(
    payload: StockNoteCreateRequest,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    stock = session.exec(select(Stock).where(Stock.symbol == payload.symbol)).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")

    note = StockNote(
        user_id=user.id,
        symbol=payload.symbol,
        title=payload.title,
        content=payload.content,
    )
    session.add(note)
    session.commit()
    session.refresh(note)

    log_user_action(session, user_id=user.id, action_type="create_note", action_detail=f"创建笔记: {payload.symbol}")

    return {
        "id": note.id,
        "symbol": note.symbol,
        "stock_name": stock.name,
        "title": note.title,
        "content": note.content,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


@router.get("/notes/{note_id}", response_model=StockNoteResponse)
def get_stock_note(
    note_id: int,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    note = session.exec(
        select(StockNote).where(
            StockNote.id == note_id,
            StockNote.user_id == user.id,
        )
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")

    stock = session.exec(select(Stock).where(Stock.symbol == note.symbol)).first()

    return {
        "id": note.id,
        "symbol": note.symbol,
        "stock_name": stock.name if stock else None,
        "title": note.title,
        "content": note.content,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


@router.put("/notes/{note_id}", response_model=StockNoteResponse)
def update_stock_note(
    note_id: int,
    payload: StockNoteUpdateRequest,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    note = session.exec(
        select(StockNote).where(
            StockNote.id == note_id,
            StockNote.user_id == user.id,
        )
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")

    if payload.title is not None:
        note.title = payload.title
    if payload.content is not None:
        note.content = payload.content

    note.updated_at = datetime.utcnow()
    session.add(note)
    session.commit()
    session.refresh(note)

    stock = session.exec(select(Stock).where(Stock.symbol == note.symbol)).first()

    log_user_action(session, user_id=user.id, action_type="update_note", action_detail=f"更新笔记: id={note_id}")

    return {
        "id": note.id,
        "symbol": note.symbol,
        "stock_name": stock.name if stock else None,
        "title": note.title,
        "content": note.content,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


@router.delete("/notes/{note_id}")
def delete_stock_note(
    note_id: int,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    note = session.exec(
        select(StockNote).where(
            StockNote.id == note_id,
            StockNote.user_id == user.id,
        )
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")

    session.delete(note)
    session.commit()

    log_user_action(session, user_id=user.id, action_type="delete_note", action_detail=f"删除笔记: id={note_id}")

    return {"status": "ok"}


@router.get("/stock/{symbol}/tags_notes", response_model=StockTagNoteAggregateResponse)
def get_stock_tags_and_notes(
    symbol: str,
    user=Depends(auth_dep),
    session=Depends(session_dep),
):
    stock = session.exec(select(Stock).where(Stock.symbol == symbol)).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")

    tag_maps = session.exec(
        select(StockTagMap).where(
            StockTagMap.user_id == user.id,
            StockTagMap.symbol == symbol,
        )
    ).all()

    tag_ids = [m.tag_id for m in tag_maps]
    tags = []
    if tag_ids:
        tag_list = session.exec(select(StockTag).where(StockTag.id.in_(tag_ids))).all()
        for tag in tag_list:
            count = len(session.exec(
                select(StockTagMap).where(
                    StockTagMap.user_id == user.id,
                    StockTagMap.tag_id == tag.id,
                )
            ).all())
            tags.append({
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
                "description": tag.description,
                "stock_count": count,
                "created_at": tag.created_at,
                "updated_at": tag.updated_at,
            })

    notes_query = select(StockNote).where(
        StockNote.user_id == user.id,
        StockNote.symbol == symbol,
    ).order_by(StockNote.updated_at.desc())

    notes = session.exec(notes_query).all()
    note_items = []
    for note in notes:
        note_items.append({
            "id": note.id,
            "symbol": note.symbol,
            "stock_name": stock.name,
            "title": note.title,
            "content": note.content,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        })

    return {
        "symbol": symbol,
        "stock_name": stock.name,
        "tags": tags,
        "notes": note_items,
    }
