import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import time
from typing import Any

from app.core.config import settings
from app.db import repositories


PASSWORD_HASH_ITERATIONS = 210_000


def create_access_token(user: dict[str, Any]) -> str:
    if settings.JWT_ALGORITHM.upper() != "HS256":
        raise ValueError("当前仅支持 HS256 JWT")
    now = int(time.time())
    payload = {
        "sub": str(user["id"]),
        "username": user.get("username") or "",
        "iat": now,
        "exp": now + settings.JWT_EXPIRE_MINUTES * 60,
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64_json(header),
            _b64_json(payload),
        ]
    )
    signature = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    parts = str(token or "").split(".")
    if len(parts) != 3:
        raise ValueError("Token 格式无效")
    signing_input = f"{parts[0]}.{parts[1]}"
    expected = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    supplied = _b64_decode(parts[2])
    if not hmac.compare_digest(expected, supplied):
        raise ValueError("Token 签名无效")
    try:
        payload = json.loads(_b64_decode(parts[1]).decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Token 内容无效") from exc
    if not isinstance(payload, dict):
        raise ValueError("Token 内容无效")
    if int(payload.get("exp") or 0) <= int(time.time()):
        raise ValueError("Token 已过期")
    if not str(payload.get("sub") or "").isdigit():
        raise ValueError("Token 用户无效")
    return payload


def authenticate_token(token: str) -> dict[str, Any]:
    payload = decode_access_token(token)
    user = repositories.get_user_by_id(int(payload["sub"]))
    if not user or user.get("status") != "active" or user.get("is_active") is False:
        raise ValueError("用户不存在或已停用")
    return user


def register_user(
    *,
    username: str,
    email: str,
    password: str,
    display_name: str = "",
) -> dict[str, Any]:
    clean_username = _validate_username(username)
    clean_password = str(password or "")
    if len(clean_password) < 6:
        raise ValueError("密码至少需要 6 位")
    clean_email = str(email or "").strip()
    if clean_email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", clean_email):
        raise ValueError("邮箱格式无效")
    return repositories.create_password_user(
        username=clean_username,
        email=clean_email,
        password_hash=hash_password(clean_password),
        display_name=str(display_name or "").strip(),
    )


def login_user(username: str, password: str) -> dict[str, Any]:
    clean_username = _validate_username(username)
    auth_user = repositories.get_auth_user_by_username(clean_username)
    if not auth_user or not verify_password(password, auth_user.get("password_hash")):
        raise ValueError("用户名或密码错误")
    if auth_user.get("status") != "active" or auth_user.get("is_active") is False:
        raise ValueError("用户已停用")
    return repositories.mark_user_login(int(auth_user["id"]))


def dev_login(username: str, nickname: str = "") -> dict[str, Any]:
    clean_username = _validate_username(username)
    return repositories.upsert_dev_user(clean_username, nickname)


def ensure_default_user() -> dict[str, Any]:
    username = str(settings.DEFAULT_DEV_USERNAME or "anonymous_dev").strip()
    return repositories.upsert_dev_user(username, "本地开发用户")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}$"
        f"{salt.hex()}${digest.hex()}"
    )


def verify_password(password: Any, password_hash: Any) -> bool:
    parts = str(password_hash or "").split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected = bytes.fromhex(parts[3])
    except (TypeError, ValueError):
        return False
    supplied = hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(supplied, expected)


def _validate_username(username: str) -> str:
    clean_username = str(username or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{2,64}", clean_username):
        raise ValueError("用户名仅支持 2-64 位字母、数字、点、下划线或短横线")
    return clean_username


def _b64_json(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _b64_encode(raw)


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64_decode(value: str) -> bytes:
    encoded = value.encode("ascii")
    encoded += b"=" * (-len(encoded) % 4)
    try:
        return base64.urlsafe_b64decode(encoded)
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise ValueError("Token 编码无效") from exc
