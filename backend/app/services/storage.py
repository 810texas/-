"""上传落盘：扩展名 + magic bytes 双重校验、UUID 重命名（需求 5.2）。"""
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import get_settings

settings = get_settings()

# 本期仅支持 JPG/PNG（需求 1.3）
MAGIC_SIGNATURES = {
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
}
ALLOWED_EXT = set(MAGIC_SIGNATURES)


def upload_root() -> Path:
    root = Path(settings.UPLOAD_DIR)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_and_read(file: UploadFile, data: bytes) -> str:
    """返回规范化扩展名；不合法直接 400 并给出明确原因（验收标准：上传校验）。"""
    name = file.filename or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400, detail=f"仅支持 JPG/PNG 格式，当前文件扩展名为 .{ext or '未知'}"
        )

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小 {len(data) / 1024 / 1024:.1f}MB 超过 {settings.MAX_UPLOAD_MB}MB 限制",
        )
    if not data:
        raise HTTPException(status_code=400, detail="文件内容为空")

    # 扩展名与真实内容双重校验，拦截伪装扩展名
    if not any(data.startswith(sig) for sig in MAGIC_SIGNATURES[ext]):
        raise HTTPException(
            status_code=400, detail="文件真实内容与扩展名不符（magic bytes 校验失败）"
        )
    return "jpg" if ext == "jpeg" else ext


def save_bytes(data: bytes, ext: str) -> str:
    """UUID 重命名后落盘，返回存储文件名。"""
    stored = f"{uuid.uuid4().hex}.{ext}"
    (upload_root() / stored).write_bytes(data)
    return stored


def path_of(stored_name: str) -> Path:
    return upload_root() / stored_name
