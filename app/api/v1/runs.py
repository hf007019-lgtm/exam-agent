from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db import repositories
from app.services.product_service import sanitize_for_api


router = APIRouter(prefix="/agent/runs", tags=["agent-runs"])


@router.get("")
def get_agent_runs(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    items = repositories.list_agent_runs(user["id"], limit, offset)
    summaries = [_present_run(item, detail=False) for item in items]
    return {"items": summaries, "count": len(summaries)}


@router.get("/{run_id}")
def get_agent_run(
    run_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    run = repositories.get_agent_run(user["id"], run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent 运行记录不存在")
    return _present_run(run, detail=True)


@router.get("/{run_id}/tool-calls")
def get_agent_run_tool_calls(
    run_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    items = repositories.list_tool_calls(user["id"], run_id)
    if items is None:
        raise HTTPException(status_code=404, detail="Agent 运行记录不存在")
    safe_items = [
        sanitize_for_api(item, settings.OBSERVABILITY_TEXT_LIMIT)
        for item in items
    ]
    return {"items": safe_items, "count": len(safe_items), "agent_run_id": run_id}


def _present_run(run: dict, *, detail: bool) -> dict:
    data = dict(run)
    if not detail:
        data.pop("trace_json", None)
        data.pop("sources_json", None)
        data.pop("citations_json", None)
        data.pop("rag_answer", None)
    return sanitize_for_api(data, settings.OBSERVABILITY_TEXT_LIMIT)
