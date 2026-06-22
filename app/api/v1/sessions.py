from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.dependencies import get_current_user
from app.db import repositories
from app.schemas.product_schema import SessionCreateRequest, SessionMessageCreateRequest


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("")
def create_chat_session(
    payload: SessionCreateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    return repositories.create_session(
        user["id"],
        payload.title,
        payload.scene,
    )


@router.get("")
def get_chat_sessions(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    items = repositories.list_sessions(user["id"], limit, offset)
    return {"items": items, "count": len(items)}


@router.get("/{session_id}")
def get_chat_session(
    session_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    session = repositories.get_session(user["id"], session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.delete("/{session_id}")
def delete_chat_session(
    session_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    if not repositories.delete_session(user["id"], session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"deleted": True, "session_id": session_id}


@router.get("/{session_id}/messages")
def get_chat_messages(
    session_id: int,
    request: Request,
    limit: int = Query(200, ge=1, le=500),
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    items = repositories.list_messages(user["id"], session_id, limit)
    if items is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"items": items, "count": len(items), "session_id": session_id}


@router.post("/{session_id}/messages")
def create_chat_message(
    session_id: int,
    payload: SessionMessageCreateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    if not repositories.get_session(user["id"], session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    try:
        return repositories.add_message(
            session_id,
            user["id"],
            payload.role,
            payload.content,
            metadata=payload.metadata_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
