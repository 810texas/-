"""安全工具：BCrypt 密码散列、JWT 双令牌、CSRF 双提交 Token。"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()


# ---------- 密码 ----------
def hash_password(raw: str) -> str:
    """BCrypt 散列（需求 4.2：加密密码 BCrypt 存储）。"""
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------- JWT ----------
def _encode(payload: dict[str, Any], expires: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    body = {**payload, "type": token_type, "iat": now, "exp": now + expires}
    return jwt.encode(body, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int, role_code: str, token_version: int) -> str:
    # jti 随机因子：避免同一秒内重复签发产生完全相同的令牌
    return _encode(
        {
            "sub": str(user_id),
            "role": role_code,
            "ver": token_version,
            "jti": secrets.token_urlsafe(12),
        },
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "access",
    )


def create_refresh_token(user_id: int, token_version: int) -> str:
    return _encode(
        {
            "sub": str(user_id),
            "ver": token_version,
            "jti": secrets.token_urlsafe(16),
        },
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "refresh",
    )


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """解码并校验令牌类型；失败抛 jwt 异常由调用方转 401。"""
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("令牌类型不匹配")
    return payload


def token_fingerprint(token: str) -> str:
    """Refresh Token 只存哈希入库（需求 5.2：入库可撤销）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------- CSRF ----------
def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
