from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db import repositories
from app.schemas.product_schema import AuthLoginRequest, AuthRegisterRequest, DevLoginRequest
from app.services.auth_service import create_access_token, dev_login, login_user, register_user
from app.services.product_service import serialize_profile


router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: dict) -> dict:
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "expires_in": settings.JWT_EXPIRE_MINUTES * 60,
        "user": user,
    }


@router.post("/register")
def register_account(payload: AuthRegisterRequest) -> dict:
    try:
        user = register_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _token_response(user)


@router.post("/login")
def login_account(payload: AuthLoginRequest) -> dict:
    try:
        user = login_user(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return _token_response(user)


@router.post("/logout")
def logout_account(user: dict = Depends(get_current_user)) -> dict:
    del user
    return {
        "status": "LOGGED_OUT",
        "message": "已退出登录",
    }


@router.post("/dev-login")
def login_with_dev_account(payload: DevLoginRequest) -> dict:
    if not settings.DEV_LOGIN_ENABLED:
        raise HTTPException(status_code=403, detail="开发登录未启用")
    try:
        user = dev_login(payload.username, payload.nickname)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _token_response(user)


@router.get("/me")
def get_me(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    profile = repositories.get_user_profile(user["id"])
    return {
        "user": user,
        "profile": serialize_profile(profile),
        "auth_enabled": settings.AUTH_ENABLED,
    }
