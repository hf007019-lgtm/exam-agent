from typing import Any

from fastapi import HTTPException, Request

from app.core.config import settings
from app.services.auth_service import authenticate_token, ensure_default_user


def get_current_user(request: Request) -> dict[str, Any]:
    user = resolve_request_user(request, required=settings.AUTH_ENABLED)
    if user:
        return user
    return ensure_default_user()


def get_optional_agent_user(request: Request) -> dict[str, Any] | None:
    return resolve_request_user(request, required=False)


def resolve_request_user(
    request: Request,
    *,
    required: bool,
) -> dict[str, Any] | None:
    authorization = str(request.headers.get("Authorization") or "").strip()
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(status_code=401, detail="Authorization Header 格式无效")
        try:
            return authenticate_token(token.strip())
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    if required:
        raise HTTPException(status_code=401, detail="请先登录")
    if not settings.AUTH_ENABLED:
        return ensure_default_user()
    return None
