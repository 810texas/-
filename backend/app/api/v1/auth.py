"""登录 / 登出 / 当前用户 / 刷新令牌。"""
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import current_user_with_csrf, get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.services import auth as auth_service

router = APIRouter()
settings = get_settings()

COOKIE_COMMON = {"httponly": True, "samesite": "lax", "path": "/"}


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


def _set_auth_cookies(response: Response, access: str, refresh: str, csrf: str) -> None:
    """Access/Refresh 存 HttpOnly Cookie，CSRF Token 需前端可读（非 HttpOnly）。"""
    response.set_cookie(
        settings.ACCESS_COOKIE,
        access,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **COOKIE_COMMON,
    )
    response.set_cookie(
        settings.REFRESH_COOKIE,
        refresh,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        **COOKIE_COMMON,
    )
    response.set_cookie(settings.CSRF_COOKIE, csrf, samesite="lax", path="/")


def user_profile(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "role": user.role.code,
        "role_name": user.role.name,
        "dept": user.dept.name if user.dept else "",
        "dept_id": user.dept_id,
        "menus": [
            {"title": m.title, "path": m.path, "icon": m.icon, "sort": m.sort}
            for m in sorted(user.role.menus, key=lambda m: m.sort)
        ],
    }


@router.post("/auth/login")
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    try:
        user = auth_service.authenticate(db, payload.username, payload.password)
    except HTTPException as exc:
        raise exc
    access, refresh, csrf = auth_service.issue_tokens(db, user)
    _set_auth_cookies(response, access, refresh, csrf)
    return {"user": user_profile(user), "csrf_token": csrf}


@router.post("/auth/refresh")
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=settings.REFRESH_COOKIE),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="缺少 Refresh Token")
    access, new_refresh, user = auth_service.rotate(db, refresh_token)
    from app.core.security import new_csrf_token

    csrf = new_csrf_token()
    _set_auth_cookies(response, access, new_refresh, csrf)
    return {"user": user_profile(user), "csrf_token": csrf}


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return user_profile(user)


@router.post("/auth/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=settings.REFRESH_COOKIE),
):
    auth_service.revoke(db, refresh_token, None)
    for name in (settings.ACCESS_COOKIE, settings.REFRESH_COOKIE, settings.CSRF_COOKIE):
        response.delete_cookie(name, path="/")
    return {"ok": True}
