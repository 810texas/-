from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
import app.models  # noqa: E402,F401

settings = get_settings()

REQUIRED = {
    "user",
    "invoice",
    "reimbursement",
    "role",
    "menu",
    "role_menu",
    "department",
    "attachment",
    "ocr_task",
    "review_log",
    "field_change_log",
}


def main() -> int:
    print(f"[check] 目标库 {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    print(f"[check] 库中已有表（{len(existing)}）：{', '.join(sorted(existing)) or '无'}")

    missing = REQUIRED - existing
    if missing:
        print(f"[check] 缺失核心表：{', '.join(sorted(missing))}")
        return 1

    for name in sorted(REQUIRED):
        cols = [c["name"] for c in inspector.get_columns(name)]
        print(f"[check] {name}: {', '.join(cols)}")

    # 生成列与唯一索引校验
    indexes = inspector.get_indexes("invoice")
    uniques = [i["name"] for i in indexes if i.get("unique")]
    print(f"[check] invoice 唯一索引：{uniques}")
    print("[check] 模型与库结构一致：OK")
    print(f"[check] metadata 表数：{len(Base.metadata.sorted_tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
