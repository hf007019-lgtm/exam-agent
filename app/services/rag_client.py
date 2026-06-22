import logging
from typing import Any, TypedDict

import requests

from app.core.config import settings


logger = logging.getLogger(__name__)


class RagAnswer(TypedDict, total=False):
    status: str
    message: str
    answer: str
    policy_answer: str
    citations: list[dict]
    sources: list[dict]
    used_retrieval: bool
    answer_type: str
    error: str
    raw: dict[str, Any]


def ask_rag(query: str, top_k: int | None = None) -> RagAnswer:
    """调用外部政策知识库，并把响应整理为稳定的 Agent 契约。"""
    question = str(query or "").strip()
    if not settings.RAG_ENABLED:
        return _failure_result(
            answer_type="rag_disabled",
            error="RAG 知识库未启用",
            message="政策知识库当前未启用，已继续使用无来源模式。",
        )
    if not question:
        return _failure_result(
            answer_type="unanswerable",
            error="",
            message="政策知识库查询内容为空。",
            status="empty",
        )

    citation_limit = _normalize_top_k(top_k)
    url = _build_ask_url()
    try:
        response = requests.post(
            url,
            json={"question": question},
            timeout=settings.RAG_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.warning("政策知识库请求失败，已自动降级：%s", exc)
        return _failure_result(
            answer_type="rag_unavailable",
            error="RAG 知识库服务暂时不可用",
            message="政策知识库暂时不可用，已继续使用无来源模式。",
        )
    except ValueError as exc:
        logger.warning("政策知识库响应不是合法 JSON，已自动降级：%s", exc)
        return _failure_result(
            answer_type="rag_unavailable",
            error="RAG 知识库服务暂时不可用",
            message="政策知识库返回内容异常，已继续使用无来源模式。",
        )

    if not isinstance(data, dict):
        logger.warning("政策知识库响应结构异常，顶层类型为 %s", type(data).__name__)
        return _failure_result(
            answer_type="rag_unavailable",
            error="RAG 知识库服务暂时不可用",
            message="政策知识库返回内容异常，已继续使用无来源模式。",
        )

    answer = str(data.get("answer", "") or "")
    upstream_answer_type = str(data.get("answer_type", "") or "").strip().lower()
    answer_type = _normalize_answer_type(upstream_answer_type, answer)
    used_retrieval = bool(data.get("used_retrieval", answer_type == "knowledge_answer"))
    raw_sources = _select_raw_sources(data)
    citations = _normalize_sources(raw_sources)[:citation_limit]
    has_grounded_answer = (
        answer_type == "knowledge_answer"
        and used_retrieval
        and bool(answer)
        and bool(citations)
    )

    if has_grounded_answer:
        return RagAnswer(
            status="success",
            message=f"检索到 {len(citations)} 条政策来源",
            answer=answer,
            policy_answer=answer,
            citations=citations,
            sources=citations,
            used_retrieval=True,
            answer_type=answer_type,
            error="",
            raw=data,
        )

    return RagAnswer(
        status="empty",
        message="政策知识库已响应，但没有检索到足够的可核验依据。",
        answer="",
        policy_answer="",
        citations=[],
        sources=[],
        used_retrieval=used_retrieval,
        answer_type=answer_type,
        error="",
        raw=data,
    )


def ask_rag_builder(question: str) -> RagAnswer:
    """兼容旧调用入口；新代码统一使用 ask_rag。"""
    return ask_rag(question)


def _build_ask_url() -> str:
    base_url = str(settings.RAG_BASE_URL or "").strip().rstrip("/")
    ask_path = str(settings.RAG_ASK_PATH or "/api/v1/search/ask").strip()
    return f"{base_url}/{ask_path.lstrip('/')}"


def _normalize_top_k(top_k: int | None) -> int:
    try:
        value = int(top_k if top_k is not None else settings.RAG_TOP_K)
    except (TypeError, ValueError):
        value = settings.RAG_TOP_K
    return max(1, min(value, 20))


def _normalize_answer_type(answer_type: str, answer: str) -> str:
    aliases = {
        "grounded": "knowledge_answer",
        "knowledge_answer": "knowledge_answer",
        "unanswerable": "unanswerable",
        "chitchat": "chitchat",
    }
    normalized = aliases.get(answer_type, "")
    if normalized:
        return normalized
    return "knowledge_answer" if answer else "unanswerable"


def _failure_result(
    answer_type: str,
    error: str,
    message: str,
    status: str = "error",
) -> RagAnswer:
    return RagAnswer(
        status=status,
        message=message,
        answer="",
        policy_answer="",
        citations=[],
        sources=[],
        used_retrieval=False,
        answer_type=answer_type,
        error=error,
        raw={},
    )


def _normalize_sources(raw_sources: Any) -> list[dict]:
    """把服务返回的引用整理为前端和 Agent 共用字段。"""
    if not isinstance(raw_sources, list):
        return []

    normalized = []
    seen = set()
    for item in raw_sources:
        source = _normalize_source(item)
        identity = (
            str(source.get("doc_id") or ""),
            str(source.get("chunk_id") or ""),
            str(source.get("title") or ""),
            str(source.get("snippet") or ""),
        )
        if identity in seen or not (source.get("title") or source.get("snippet")):
            continue
        seen.add(identity)
        normalized.append(source)
    return normalized


def _select_raw_sources(data: dict) -> list:
    """优先读取标准 citations，避免与兼容 sources 重复计数。"""
    for key in ("citations", "sources", "chunks", "documents"):
        value = data.get(key)
        if isinstance(value, list) and value:
            return value
    return []


def _normalize_source(item: Any) -> dict:
    """把单条来源整理成稳定、可展示的引用字段。"""
    if isinstance(item, str):
        return {
            "doc_id": None,
            "chunk_id": "",
            "document_name": "政策来源",
            "score": None,
            "text_preview": item,
            "source_type": "政策文件",
            "title": "政策来源",
            "url": "",
            "page": "",
            "snippet": item,
            "confidence": None,
        }

    if isinstance(item, dict):
        title = str(
            item.get("document_name")
            or item.get("title")
            or item.get("name")
            or item.get("filename")
            or item.get("file_name")
            or item.get("document_title")
            or item.get("document")
            or "政策来源"
        )
        snippet = str(
            item.get("text_preview")
            or item.get("chunk_text")
            or item.get("snippet")
            or item.get("content")
            or item.get("text")
            or item.get("preview")
            or ""
        )
        score = item.get("score")
        if score is None:
            score = item.get("confidence")
        return {
            "doc_id": item.get("doc_id"),
            "chunk_id": str(item.get("chunk_id") or ""),
            "document_name": title,
            "score": score,
            "text_preview": snippet,
            "source_type": "政策文件",
            "title": title,
            "url": str(item.get("url") or item.get("source_url") or ""),
            "page": str(item.get("page") or item.get("page_number") or ""),
            "snippet": snippet,
            "confidence": score,
        }

    text = str(item or "")
    return {
        "doc_id": None,
        "chunk_id": "",
        "document_name": "政策来源",
        "score": None,
        "text_preview": text,
        "source_type": "政策文件",
        "title": "政策来源",
        "url": "",
        "page": "",
        "snippet": text,
        "confidence": None,
    }
