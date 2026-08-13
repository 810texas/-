"""汇总 /api/v1 各子路由。"""
from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
