"""FastAPI 应用入口。"""
import hashlib

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core import ratelimit
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="智能发票报销审核系统",
    description="OCR + 大模型语义理解的智能报销审核系统 API",
    version="0.1.0",
)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
LOGIN_PATH = "/api/v1/auth/login"


# 注意：本中间件必须在 add_middleware(CORSMiddleware) 之前注册，
# 这样 CORS 位于最外层，429 响应同样带上 CORS 头，浏览器才能读到原因。
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """写接口限流（需求 5.2）：登录按 IP，其余按登录态，超限 429。"""
    if not settings.RATE_LIMIT_ENABLED:
        return await call_next(request)
    if request.method not in WRITE_METHODS or not request.url.path.startswith("/api/v1"):
        return await call_next(request)

    is_login = request.url.path == LOGIN_PATH
    limit = (
        settings.RATE_LIMIT_LOGIN_PER_MINUTE
        if is_login
        else settings.RATE_LIMIT_WRITE_PER_MINUTE
    )
    token = request.cookies.get(settings.ACCESS_COOKIE)
    identity = token or f"anon:{request.client.host if request.client else 'unknown'}"
    key = hashlib.sha256(identity.encode()).hexdigest()[:16]

    allowed, retry_after = ratelimit.allow(key, limit)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"操作过于频繁，请 {retry_after} 秒后重试（每分钟最多 {limit} 次）"
            },
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root():
    return {"name": "智能发票报销审核系统", "docs": "/docs"}
