"""应用配置：从 .env 读取，AI 服务（OCR/LLM）provider 的切换总开关。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 数据库
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "invoice_system"

    # JWT
    JWT_SECRET: str = "dev-insecure-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AI 服务切换：OCR_PROVIDER=mock|paddle  LLM_PROVIDER=mock|qwen|glm
    OCR_PROVIDER: str = "mock"
    LLM_PROVIDER: str = "mock"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    # 抬头核验：公司主体（需求 4.4）
    COMPANY_NAME: str = "示例科技有限公司"
    COMPANY_TAX_NO: str = "91330100MA2XXXXXXX"

    # 预审规则参数
    OCR_CONFIDENCE_THRESHOLD: float = 0.85
    AMOUNT_TOLERANCE: float = 0.01
    BUDGET_WARN_RATIO: float = 0.8

    # 上传
    MAX_UPLOAD_MB: int = 10
    UPLOAD_DIR: str = "storage/uploads"

    # 登录安全：连续 5 次错误锁定 15 分钟
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 15

    # Cookie 名
    ACCESS_COOKIE: str = "access_token"
    REFRESH_COOKIE: str = "refresh_token"
    CSRF_COOKIE: str = "csrf_token"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
