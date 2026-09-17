"""鉴权业务：登录、锁定策略、Refresh Token 轮换与撤销。"""
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    token_fingerprint,
    verify_password,
)
from app.models.rbac import RefreshToken
from app.models.user import User

settings = get_settings()


def authenticate(db: Session, username: str, password: str) -> User:
    """密码校验 + 连续错误 5 次锁定 15 分钟（需求 3.1）。"""
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    now = datetime.now()
    if user.locked_until and user.locked_until > now:
        minutes = int((user.locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(status_code=423, detail=f"账号已锁定，请 {minutes} 分钟后重试")
    if user.status != "NORMAL":
        raise HTTPException(status_code=403, detail="账号已停用，请联系管理员")

    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= settings.LOGIN_MAX_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
            user.failed_attempts = 0
            db.commit()
            raise HTTPException(
                status_code=423,
                detail=f"密码连续错误 {settings.LOGIN_MAX_ATTEMPTS} 次，账号锁定 "
                f"{settings.LOGIN_LOCK_MINUTES} 分钟",
            )
        db.commit()
        left = settings.LOGIN_MAX_ATTEMPTS - user.failed_attempts
        raise HTTPException(status_code=401, detail=f"用户名或密码错误，剩余 {left} 次尝试机会")

    # 登录成功清零计数与锁定
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()
    db.refresh(user)
    return user


def issue_tokens(db: Session, user: User) -> tuple[str, str, str]:
    """返回 (access, refresh, csrf)。Refresh Token 哈希入库以便撤销。"""
    access = create_access_token(user.id, user.role.code, user.token_version)
    refresh = create_refresh_token(user.id, user.token_version)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_fingerprint(refresh),
            expires_at=datetime.now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()
    from app.core.security import new_csrf_token

    return access, refresh, new_csrf_token()


def rotate(db: Session, raw_refresh: str) -> tuple[str, str, User]:
    """Refresh 轮换：旧令牌撤销，换发新 access/refresh。"""
    from app.core.security import decode_token

    try:
        payload = decode_token(raw_refresh, "refresh")
    except Exception:
        raise HTTPException(status_code=401, detail="Refresh Token 无效或已过期")

    fp = token_fingerprint(raw_refresh)
    record = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == fp)
    ).scalar_one_or_none()
    if record is None or record.revoked:
        raise HTTPException(status_code=401, detail="Refresh Token 已撤销")

    user = db.get(User, int(payload["sub"]))
    if user is None or payload.get("ver") != user.token_version:
        raise HTTPException(status_code=401, detail="凭证已撤销，请重新登录")

    record.revoked = 1
    db.commit()
    access = create_access_token(user.id, user.role.code, user.token_version)
    refresh = create_refresh_token(user.id, user.token_version)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_fingerprint(refresh),
            expires_at=datetime.now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()
    return access, refresh, user


def revoke(db: Session, raw_refresh: str | None, user: User | None) -> None:
    """登出：撤销该 Refresh Token；解析失败时按用户全量撤销。"""
    if raw_refresh:
        record = db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_fingerprint(raw_refresh))
        ).scalar_one_or_none()
        if record:
            record.revoked = 1
            db.commit()
            return
    if user:
        for record in db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id, RefreshToken.revoked == 0
            )
        ).scalars().all():
            record.revoked = 1
        db.commit()


def set_password(db: Session, user: User, new_password: str) -> None:
    """管理员重置密码：密码版本 +1，旧令牌全部失效（需求 3.3）。"""
    user.password_hash = hash_password(new_password)
    user.token_version += 1
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()
