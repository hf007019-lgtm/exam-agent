import json

from app.core.config import settings


def generate_llm_json(prompt: str, fallback_data: dict) -> dict:
    """Ask the configured chat model for one JSON object."""
    fallback = dict(fallback_data or {})
    if not settings.LLM_API_KEY or not settings.LLM_MODEL_NAME:
        fallback["llm_used"] = False
        fallback["model"] = settings.LLM_MODEL_NAME or ""
        fallback["error"] = "LLM is not configured."
        return fallback

    try:
        from openai import OpenAI
    except ImportError:
        fallback["llm_used"] = False
        fallback["model"] = settings.LLM_MODEL_NAME or ""
        fallback["error"] = "OpenAI SDK is not installed."
        return fallback

    try:
        client = _build_client(OpenAI)
        response = client.chat.completions.create(
            model=settings.LLM_MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the planning brain for a Chinese civil-service exam advisor. "
                        "Return exactly one valid JSON object. Do not use markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        data = _parse_json_object(response.choices[0].message.content or "")
    except Exception:
        fallback["llm_used"] = False
        fallback["model"] = settings.LLM_MODEL_NAME or ""
        fallback["error"] = "LLM JSON planning failed."
        return fallback

    if not data:
        fallback["llm_used"] = False
        fallback["model"] = settings.LLM_MODEL_NAME or ""
        fallback["error"] = "LLM JSON planning returned invalid content."
        return fallback

    data["llm_used"] = True
    data["model"] = settings.LLM_MODEL_NAME or ""
    data.setdefault("error", "")
    return data


def generate_llm_chat(
    system_prompt: str,
    messages: list[dict],
    fallback_report: str,
    temperature: float = 0.45,
) -> dict:
    """Generate a natural answer with recent conversation context."""
    if not settings.LLM_API_KEY:
        return _fallback_result(
            fallback_report=fallback_report,
            error="LLM_API_KEY is not configured; returned fallback answer.",
        )

    if not settings.LLM_MODEL_NAME:
        return _fallback_result(
            fallback_report=fallback_report,
            error="LLM_MODEL_NAME is not configured; returned fallback answer.",
        )

    try:
        from openai import OpenAI
    except ImportError:
        return _fallback_result(
            fallback_report=fallback_report,
            error="OpenAI Python SDK is not installed; returned fallback answer.",
        )

    try:
        client = _build_client(OpenAI)
        response = client.chat.completions.create(
            model=settings.LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                *_normalize_chat_messages(messages),
            ],
            temperature=temperature,
        )
        content = (response.choices[0].message.content or "").strip()
    except Exception:
        return _fallback_result(
            fallback_report=fallback_report,
            error="LLM chat call failed; returned fallback answer.",
        )

    if not content:
        return _fallback_result(
            fallback_report=fallback_report,
            error="LLM chat returned empty content; returned fallback answer.",
        )

    return {
        "summary": content,
        "analysis_report": content,
        "llm_used": True,
        "model": settings.LLM_MODEL_NAME or "",
        "error": "",
    }


def generate_llm_summary(prompt: str, fallback_report: str) -> dict:
    """Generate the tool-grounded recommendation report used by existing flows."""
    return generate_llm_chat(
        system_prompt=(
            "You are a careful Chinese exam-position advisor. Only use the provided "
            "tool results to discuss job recommendations, risk, scores, and checks. "
            "Do not invent jobs, score lines, competition data, notices, or policy sources."
        ),
        messages=[{"role": "user", "content": prompt}],
        fallback_report=fallback_report,
        temperature=0.2,
    )


def _build_client(openai_class):
    """Create an OpenAI-compatible SDK client."""
    client_kwargs = {"api_key": settings.LLM_API_KEY}
    if settings.LLM_BASE_URL:
        client_kwargs["base_url"] = settings.LLM_BASE_URL
    return openai_class(**client_kwargs)


def _parse_json_object(content: str) -> dict:
    text = (content or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def _normalize_chat_messages(messages: list[dict]) -> list[dict]:
    normalized = []
    for message in messages[-12:]:
        role = str(message.get("role") or "").strip()
        content = str(message.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def _fallback_result(fallback_report: str, error: str) -> dict:
    safe_report = (fallback_report or "").strip()
    if not safe_report:
        safe_report = "暂时无法生成有效回答，请稍后再试。"

    return {
        "summary": safe_report,
        "analysis_report": safe_report,
        "llm_used": False,
        "model": settings.LLM_MODEL_NAME or "",
        "error": error,
    }
