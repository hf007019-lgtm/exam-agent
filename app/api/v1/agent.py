import json
import logging
import re
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError

from app.agents.exam_agent import analyze_exam_request
from app.api.dependencies import get_optional_agent_user
from app.db import repositories
from app.schemas.agent_schema import AgentAnalyzeRequest, AgentAnalyzeResponse
from app.services.product_service import (
    add_session_messages_to_payload,
    apply_profile_defaults,
    build_assistant_metadata,
    model_dump,
)
from app.tools.data_catalog import get_data_catalog, search_score_catalog
from app.tools.region_resolver import get_region_options


router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=AgentAnalyzeResponse)
async def analyze_agent(request: Request) -> AgentAnalyzeResponse:
    """分析用户报考条件并返回 Agent 结果。"""
    request_id = uuid.uuid4().hex
    started_at = time.perf_counter()
    payload, debug_info, debug_enabled = _parse_analyze_payload(await request.body())
    warnings: list[str] = []
    try:
        user = get_optional_agent_user(request)
    except HTTPException:
        raise
    except Exception:
        logger.exception("[%s] 用户识别失败，继续以无登录模式分析", request_id)
        user = None
        warnings.append("用户识别暂时不可用，本次已按无登录模式继续分析。")
    session_id: int | None = None
    assistant_message_id: int | None = None
    user_id = user["id"] if user else None

    if user_id:
        try:
            stored_profile = repositories.get_user_profile(user_id)
            payload = apply_profile_defaults(payload, stored_profile)
        except Exception:
            logger.exception("[%s] 读取用户画像失败，继续使用本次请求条件", request_id)
            warnings.append("用户画像读取失败，本次已按请求中的条件继续分析。")

    should_save_messages = bool(payload.session_id or payload.save_history)
    if payload.session_id:
        if not user_id:
            raise HTTPException(status_code=401, detail="保存到指定会话前请先登录")
        try:
            session = repositories.get_session(user_id, payload.session_id)
        except Exception:
            logger.exception("[%s] 校验会话失败，继续执行但不保存消息", request_id)
            session = None
            warnings.append("会话服务暂时不可用，本次回答未保存到历史会话。")
            should_save_messages = False
        if not session and not should_save_messages:
            session_id = None
        elif not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        else:
            session_id = session["id"]
        if session_id:
            try:
                previous_messages = repositories.list_messages(user_id, session_id, 12) or []
                payload = add_session_messages_to_payload(payload, previous_messages)
            except Exception:
                logger.exception("[%s] 读取会话上下文失败", request_id)
                warnings.append("历史会话读取失败，本次仍可继续分析。")
    elif payload.save_history and user_id:
        try:
            session = repositories.create_session(
                user_id,
                _session_title(payload.question),
                _session_scene(payload),
            )
            session_id = session["id"]
        except Exception:
            logger.exception("[%s] 自动创建会话失败", request_id)
            warnings.append("会话创建失败，本次回答未保存到历史会话。")
            should_save_messages = False
    elif payload.save_history and not user_id:
        warnings.append("当前未登录，本次回答未保存到历史会话。")
        should_save_messages = False

    if should_save_messages and session_id:
        try:
            repositories.add_message(
                session_id=session_id,
                user_id=user_id,
                role="user",
                content=payload.question,
                metadata={"request_id": request_id},
            )
        except Exception:
            logger.exception("[%s] 保存用户消息失败", request_id)
            warnings.append("用户消息保存失败，但不影响本次分析结果。")

    logger.info(
        "[%s] Agent analyze started user_id=%s session_id=%s",
        request_id,
        user_id,
        session_id,
    )
    response = analyze_exam_request(payload)
    latency_ms = int((time.perf_counter() - started_at) * 1000)

    if should_save_messages and session_id:
        try:
            assistant_message = repositories.add_message(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=response.analysis_report or response.summary,
                intent=response.intent,
                rag_used=response.rag_used,
                metadata=build_assistant_metadata(response),
            )
            assistant_message_id = assistant_message["id"]
        except Exception:
            logger.exception("[%s] 保存助手消息失败", request_id)
            warnings.append("助手消息保存失败，但本次回答仍已正常返回。")

    agent_run_id = None
    try:
        run = repositories.create_agent_run(
            {
                "user_id": user_id,
                "session_id": session_id,
                "message_id": assistant_message_id,
                "request_id": request_id,
                "question": payload.question,
                "intent": response.intent,
                "status": _run_status(response),
                "rag_used": response.rag_used,
                "rag_answer": response.rag_answer,
                "llm_used": response.llm_used,
                "tool_used": response.tool_used,
                "used_tools": response.used_tools,
                "trace": [model_dump(step) for step in response.trace],
                "citations": [model_dump(item) for item in response.citations],
                "sources": [model_dump(item) for item in response.sources],
                "latency_ms": latency_ms,
                "error_message": "",
            }
        )
        agent_run_id = run["id"]
    except Exception:
        logger.exception("[%s] 保存 Agent 运行记录失败", request_id)
        warnings.append("Agent 运行记录保存失败，但不影响本次回答。")
    if agent_run_id:
        try:
            _save_trace_tool_calls(agent_run_id, response)
        except Exception:
            logger.exception("[%s] 保存工具调用记录失败", request_id)
            warnings.append("部分工具调用记录保存失败，但不影响本次回答。")

    response.request_id = request_id
    response.session_id = session_id
    response.message_id = assistant_message_id
    response.agent_run_id = agent_run_id
    response.persistence_warnings = warnings
    if debug_enabled:
        response.debug_request_raw_text = debug_info["debug_request_raw_text"]
        response.debug_request_payload = debug_info["debug_request_payload"]
        response.debug_agent_input = debug_info["debug_agent_input"]
    logger.info(
        "[%s] Agent analyze finished intent=%s latency_ms=%s run_id=%s warnings=%s",
        request_id,
        response.intent,
        latency_ms,
        agent_run_id,
        len(warnings),
    )
    return response


@router.get("/options")
def get_agent_options(province: str = Query("不限")) -> dict:
    """Return filter options, with cities scoped to the selected province."""
    return get_region_options(province)


@router.get("/data-catalog")
def get_agent_data_catalog() -> dict:
    """Return user-facing coverage details for imported datasets."""
    return get_data_catalog()


@router.get("/score-references")
def get_score_references(
    province: str = Query(""),
    keyword: str = Query(""),
    position_code: str = Query(""),
    min_score: float | None = Query(None),
    max_score: float | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
) -> dict:
    """Search historical score references without exposing internal files."""
    return search_score_catalog(
        province=province,
        keyword=keyword,
        position_code=position_code,
        min_score=min_score,
        max_score=max_score,
        limit=limit,
    )


def _parse_analyze_payload(body: bytes) -> tuple[AgentAnalyzeRequest, dict[str, Any], bool]:
    """Parse request JSON without lossy ASCII replacement."""
    if not body:
        raise HTTPException(status_code=400, detail="请求体不能为空")

    data = None
    raw_text = ""
    last_decode_error: UnicodeDecodeError | None = None
    last_json_error: json.JSONDecodeError | None = None
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            raw_text = body.decode(encoding)
            data = json.loads(raw_text)
            break
        except UnicodeDecodeError as exc:
            last_decode_error = exc
            continue
        except json.JSONDecodeError as exc:
            last_json_error = exc
            continue

    if data is None:
        if last_json_error:
            raise HTTPException(status_code=400, detail=f"请求体不是合法 JSON：{last_json_error.msg}") from last_json_error
        raise HTTPException(
            status_code=400,
            detail=f"请求体编码不是 UTF-8/GB18030：{last_decode_error}",
        )

    data = _repair_payload_text(data)
    debug_enabled = _truthy_debug_flag(data)
    _reject_question_mark_payload(data)

    try:
        if hasattr(AgentAnalyzeRequest, "model_validate"):
            payload = AgentAnalyzeRequest.model_validate(data)
        else:
            payload = AgentAnalyzeRequest.parse_obj(data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    debug_info = {
        "debug_request_raw_text": _readable_raw_text(raw_text, data),
        "debug_request_payload": data,
        "debug_agent_input": _payload_to_dict(payload),
    }
    return payload, debug_info, debug_enabled


def _repair_payload_text(value):
    if isinstance(value, dict):
        return {key: _repair_payload_text(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_repair_payload_text(item) for item in value]
    if isinstance(value, str):
        return _repair_mojibake_text(value)
    return value


def _truthy_debug_flag(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    value = data.get("debug", False)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _reject_question_mark_payload(data: Any) -> None:
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="请求体 JSON 必须是对象")

    corrupted_fields = [
        field
        for field in [
            "target",
            "exam_type",
            "region",
            "city",
            "education",
            "major",
            "identity",
            "question",
        ]
        if _is_question_mark_placeholder(data.get(field))
    ]
    if corrupted_fields:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "请求字段疑似已在进入后端前被替换成问号，已拒绝继续分析。",
                "fields": corrupted_fields,
            },
        )


def _is_question_mark_placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return bool(re.fullmatch(r"\?{2,}", text))


def _payload_to_dict(payload: AgentAnalyzeRequest) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return payload.dict()


def _readable_raw_text(raw_text: str, data: Any) -> str:
    if "\\u" not in raw_text:
        return raw_text
    try:
        return json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        return raw_text


def _repair_mojibake_text(text: str) -> str:
    """Recover UTF-8 text that was accidentally decoded as GBK."""
    if not _looks_like_utf8_as_gbk_mojibake(text):
        return text
    try:
        repaired = text.encode("gb18030").decode("utf-8")
    except UnicodeError:
        return text
    return repaired if repaired else text


def _looks_like_utf8_as_gbk_mojibake(text: str) -> bool:
    markers = ("骞", "涓", "鐪", "宀", "鍏", "绋", "鎺", "杞", "搴", "浣")
    return any(marker in text for marker in markers)


def _session_title(question: str) -> str:
    title = " ".join(str(question or "").split())
    return title[:60] or "新会话"


def _session_scene(payload: AgentAnalyzeRequest) -> str:
    mode = str(payload.mode or "").strip()
    question = str(payload.question or "")
    if mode == "job_recommendation" or re.search(r"(推荐|筛岗位|可报岗位)", question):
        return "job_recommendation"
    if mode in {"policy_qa", "help_qa"}:
        return "policy_qa"
    if re.search(r"(分数|进面分|竞争比|报名人数)", question):
        return "score_analysis"
    return "general_chat"


def _run_status(response: AgentAnalyzeResponse) -> str:
    statuses = {str(step.status or "").lower() for step in response.trace}
    if "error" in statuses or "failed" in statuses:
        return "failed"
    if "warning" in statuses:
        return "completed_with_warnings"
    return "completed"


def _save_trace_tool_calls(
    agent_run_id: int,
    response: AgentAnalyzeResponse,
) -> None:
    for step in response.trace:
        data = model_dump(step)
        tool_name = str(data.get("tool") or "").strip()
        if not tool_name:
            continue
        status = str(data.get("status") or "success")
        repositories.add_tool_call(
            agent_run_id=agent_run_id,
            tool_name=tool_name,
            tool_input=data.get("input") or {},
            output_summary=str(data.get("output_summary") or ""),
            status=status,
            error_message=(
                str(data.get("output_summary") or "")
                if status.lower() in {"error", "failed"}
                else ""
            ),
        )
