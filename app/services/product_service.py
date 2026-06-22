import re
from typing import Any

from app.schemas.agent_schema import AgentAnalyzeRequest, ChatMessage


PROFILE_ALIAS_FIELDS = {
    "province",
    "city",
    "exam_type",
    "education",
    "identity",
    "accept_relocation",
    "preferences",
    "filled_fields",
}
SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "password",
    "secret",
    "access_token",
    "refresh_token",
    "source_file",
    "file_path",
    "filepath",
    "raw_private",
    "traceback",
    "debug_",
    "model_name",
    "job_analysis_model",
)


def model_dump(value: Any, *, exclude_unset: bool = False) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_unset=exclude_unset)
    if hasattr(value, "dict"):
        return value.dict(exclude_unset=exclude_unset)
    return dict(value) if isinstance(value, dict) else {}


def model_fields_set(value: Any) -> set[str]:
    fields = getattr(value, "model_fields_set", None)
    if fields is None:
        fields = getattr(value, "__fields_set__", set())
    return set(fields or set())


def profile_payload_updates(payload: Any) -> dict[str, Any]:
    data = model_dump(payload, exclude_unset=True)
    raw_profile = dict(data.pop("raw_profile_json", {}) or {})
    aliases = {}
    for field in list(data):
        if field in PROFILE_ALIAS_FIELDS:
            aliases[field] = data.pop(field)
    raw_profile.update(aliases)

    if "education" in aliases and "education_level" not in data:
        data["education_level"] = aliases["education"]
    if "exam_type" in aliases and "target_exam_type" not in data:
        data["target_exam_type"] = aliases["exam_type"]
    if (
        ("province" in aliases or "city" in aliases)
        and "target_region" not in data
    ):
        data["target_region"] = "".join(
            str(aliases.get(field) or "").strip()
            for field in ("province", "city")
        )
    if "identity" in aliases and "is_fresh_graduate" not in data:
        identity = str(aliases["identity"] or "")
        data["is_fresh_graduate"] = True if "应届" in identity else None
    if "accept_relocation" in aliases and "work_preference" not in data:
        data["work_preference"] = f"异地意愿：{aliases['accept_relocation']}"
    data["raw_profile_json"] = sanitize_for_storage(raw_profile)
    return data


def serialize_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    if not profile:
        return {}
    result = dict(profile)
    raw = dict(result.get("raw_profile_json") or {})
    result.update({key: raw.get(key) for key in PROFILE_ALIAS_FIELDS if key in raw})
    result["education"] = result.get("education") or result.get("education_level") or ""
    result["exam_type"] = result.get("exam_type") or result.get("target_exam_type") or ""
    if not result.get("identity") and result.get("is_fresh_graduate") is True:
        result["identity"] = "应届生"
    if not result.get("province"):
        region = str(result.get("target_region") or "")
        result["province"] = _extract_province(region)
        result["city"] = result.get("city") or _extract_city(region)
    return sanitize_for_storage(result)


def apply_profile_defaults(
    payload: AgentAnalyzeRequest,
    stored_profile: dict[str, Any] | None,
) -> AgentAnalyzeRequest:
    stored = serialize_profile(stored_profile)
    request_profile = dict(payload.profile or {})
    combined = {**stored, **request_profile}
    if not combined:
        return payload

    explicit = model_fields_set(payload)
    updates: dict[str, Any] = {}
    candidates = {
        "region": combined.get("province") or combined.get("target_region"),
        "city": combined.get("city"),
        "education": combined.get("education") or combined.get("education_level"),
        "major": combined.get("major"),
        "identity": combined.get("identity"),
    }
    exam_type = str(
        combined.get("exam_type") or combined.get("target_exam_type") or ""
    ).strip()
    if exam_type:
        candidates["exam_type"] = (
            "" if "事业" in exam_type else ("国考" if "国考" in exam_type else "省考")
        )
        candidates["target"] = "事业编" if "事业" in exam_type else "公务员"

    for field, value in candidates.items():
        if field in explicit or not _is_meaningful(value):
            continue
        current = getattr(payload, field, None)
        if _is_unset_filter(current):
            updates[field] = value
    if not updates:
        return payload
    if hasattr(payload, "model_copy"):
        return payload.model_copy(update=updates)
    return payload.copy(update=updates)


def add_session_messages_to_payload(
    payload: AgentAnalyzeRequest,
    messages: list[dict[str, Any]],
) -> AgentAnalyzeRequest:
    if payload.messages or not messages:
        return payload
    recent = [
        ChatMessage(role=item["role"], content=item["content"])
        for item in messages[-12:]
        if item.get("role") in {"user", "assistant"} and item.get("content")
    ]
    if not recent:
        return payload
    if hasattr(payload, "model_copy"):
        return payload.model_copy(update={"messages": recent})
    return payload.copy(update={"messages": recent})


def build_assistant_metadata(response: Any) -> dict[str, Any]:
    data = model_dump(response)
    jobs = data.get("recommendations") or data.get("matched_jobs") or []
    return sanitize_for_storage(
        {
            "recommendation_count": data.get("recommendation_count") or len(jobs),
            "recommended_jobs": [
                {
                    "job_id": job.get("job_id"),
                    "position_code": job.get("display_position_code")
                    or job.get("position_code"),
                    "department": job.get("department"),
                    "position_name": job.get("position_name") or job.get("position"),
                    "province": job.get("province"),
                    "year": job.get("year"),
                }
                for job in jobs[:5]
                if isinstance(job, dict)
            ],
            "citations": data.get("citations") or [],
            "sources": data.get("sources") or [],
        }
    )


def sanitize_for_storage(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if any(part in normalized_key for part in SENSITIVE_KEY_PARTS):
                continue
            result[key] = sanitize_for_storage(item)
        return result
    if isinstance(value, list):
        return [sanitize_for_storage(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_storage(item) for item in value]
    if isinstance(value, str):
        return _redact_secret_text(value)
    return value


def sanitize_for_api(value: Any, text_limit: int = 2000) -> Any:
    cleaned = sanitize_for_storage(value)
    return _truncate_value(cleaned, max(100, text_limit))


def _truncate_value(value: Any, text_limit: int) -> Any:
    if isinstance(value, dict):
        return {key: _truncate_value(item, text_limit) for key, item in value.items()}
    if isinstance(value, list):
        return [_truncate_value(item, text_limit) for item in value]
    if isinstance(value, str) and len(value) > text_limit:
        return f"{value[:text_limit]}…（已截断）"
    return value


def _redact_secret_text(value: str) -> str:
    text = str(value)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{10,}\b", "[已隐藏密钥]", text)
    text = re.sub(
        r"((?:api[_-]?key|authorization|bearer)\s*[:=]?\s*)[A-Za-z0-9._-]{10,}",
        r"\1[已隐藏]",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:jobs|job_scores)_[A-Za-z0-9_-]+_\d{4}\.csv\b",
        "已导入招考数据",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"[A-Za-z]:\\[^\s，。；;]+", "[内部路径已隐藏]", text)
    text = re.sub(r"/(?:app/)?data/[^\s，。；;]+", "[内部路径已隐藏]", text)
    text = re.sub(r"\braw_private\b", "[内部目录已隐藏]", text, flags=re.IGNORECASE)
    return text


def _is_meaningful(value: Any) -> bool:
    return str(value or "").strip() not in {"", "不限", "未填写", "未设置", "请选择"}


def _is_unset_filter(value: Any) -> bool:
    return str(value or "").strip() in {"", "不限", "未填写", "未设置", "请选择"}


def _extract_province(region: str) -> str:
    provinces = (
        "北京 天津 上海 重庆 河北 山西 辽宁 吉林 黑龙江 江苏 浙江 安徽 福建 江西 "
        "山东 河南 湖北 湖南 广东 广西 海南 四川 贵州 云南 陕西 甘肃 青海 宁夏 "
        "新疆 西藏 内蒙古"
    ).split()
    return next((province for province in provinces if province in region), "")


def _extract_city(region: str) -> str:
    province = _extract_province(region)
    remainder = region.replace(province, "", 1).strip()
    return remainder.removesuffix("市") if remainder else ""
