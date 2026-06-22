from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.dependencies import get_current_user
from app.db import repositories
from app.schemas.product_schema import ReportCreateRequest
from app.services.product_service import model_dump, sanitize_for_storage


router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("")
def create_analysis_report(
    payload: ReportCreateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    data = model_dump(payload)
    run_id = data.pop("agent_run_id", None)
    if data.get("session_id") and not repositories.get_session(
        user["id"],
        data["session_id"],
    ):
        raise HTTPException(status_code=404, detail="会话不存在")
    if run_id:
        run = repositories.get_agent_run(user["id"], run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Agent 运行记录不存在")
        message = (
            repositories.get_message_by_id(run["message_id"])
            if run.get("message_id")
            else None
        )
        data["session_id"] = data.get("session_id") or run.get("session_id")
        data["title"] = data.get("title") or _report_title(run.get("question"))
        data["content"] = data.get("content") or (message or {}).get("content") or run.get("rag_answer") or ""
        data["summary"] = data.get("summary") or data["content"][:500]
        data["citations_json"] = data.get("citations_json") or run.get("citations_json") or []
    data["title"] = data.get("title") or "分析报告"
    data["related_jobs_json"] = sanitize_for_storage(data.get("related_jobs_json") or [])
    data["citations_json"] = sanitize_for_storage(data.get("citations_json") or [])
    return repositories.create_report(user["id"], data)


@router.get("")
def get_analysis_reports(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    items = repositories.list_reports(user["id"], limit, offset)
    return {"items": items, "count": len(items)}


@router.get("/{report_id}")
def get_analysis_report(
    report_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    report = repositories.get_report(user["id"], report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return report


@router.delete("/{report_id}")
def delete_analysis_report(
    report_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    if not repositories.delete_report(user["id"], report_id):
        raise HTTPException(status_code=404, detail="报告不存在")
    return {"deleted": True, "report_id": report_id}


def _report_title(question: str | None) -> str:
    text = " ".join(str(question or "").split())
    return text[:60] or "Agent 分析报告"
