"""初始化数据库：建表 + 种子数据 + 生成 DDL。

用法（在 backend 目录下）：
    .venv\\Scripts\\python.exe scripts\\init_db.py            # 建表 + 种子数据
    .venv\\Scripts\\python.exe scripts\\init_db.py --ddl      # 仅打印 DDL，不连库改结构
    .venv\\Scripts\\python.exe scripts\\init_db.py --drop     # 先删表再重建（危险）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.schema import CreateTable  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.permissions import (  # noqa: E402
    ROLE_ADMIN,
    ROLE_EMPLOYEE,
    ROLE_FINANCE,
)
from app.core.security import hash_password  # noqa: E402
import app.models  # noqa: E402,F401  导入即注册全部表
from app.models.rbac import Menu, Role  # noqa: E402
from app.models.user import Department, User  # noqa: E402

settings = get_settings()

# 菜单种子：按角色可见性（需求 3.3 第 3 项）
MENUS = [
    ("我的报销单", "/my-reimbursements", "Document", 10, [ROLE_EMPLOYEE]),
    ("新建报销单", "/new-reimbursement", "Plus", 20, [ROLE_EMPLOYEE]),
    ("待办审核", "/review/todos", "List", 30, [ROLE_FINANCE]),
    ("审核轨迹", "/review/logs", "Clock", 40, [ROLE_FINANCE, ROLE_ADMIN]),
    ("用户管理", "/admin/users", "User", 50, [ROLE_ADMIN]),
    ("部门维护", "/admin/departments", "OfficeBuilding", 60, [ROLE_ADMIN]),
    ("基础数据", "/admin/base", "Setting", 70, [ROLE_ADMIN]),
]

ROLES = [
    (ROLE_EMPLOYEE, "普通员工"),
    (ROLE_FINANCE, "财务人员"),
    (ROLE_ADMIN, "管理员"),
]

DEPARTMENTS = [
    ("研发部", 5000.00, 50000.00),
    ("市场部", 8000.00, 80000.00),
    ("财务部", 3000.00, 30000.00),
]

# 演示账号（密码统一 123456，仅用于本地演示）
DEMO_USERS = [
    ("employee", "张三", ROLE_EMPLOYEE, "研发部"),
    ("employee2", "李四", ROLE_EMPLOYEE, "研发部"),
    ("finance", "王五", ROLE_FINANCE, "财务部"),
    ("admin", "赵六", ROLE_ADMIN, "财务部"),
]
DEMO_PASSWORD = "123456"


def print_ddl() -> None:
    for table in Base.metadata.sorted_tables:
        print(str(CreateTable(table).compile(dialect=engine.dialect)).strip() + ";\n")


def seed() -> None:
    db = SessionLocal()
    try:
        # 角色
        role_map: dict[str, Role] = {}
        for code, name in ROLES:
            role = db.execute(select(Role).where(Role.code == code)).scalar_one_or_none()
            if role is None:
                role = Role(code=code, name=name)
                db.add(role)
                db.flush()
            role_map[code] = role

        # 菜单 + 角色关联
        for title, path, icon, sort, role_codes in MENUS:
            menu = db.execute(select(Menu).where(Menu.path == path)).scalar_one_or_none()
            if menu is None:
                menu = Menu(title=title, path=path, icon=icon, sort=sort)
                db.add(menu)
                db.flush()
            for code in role_codes:
                role = role_map[code]
                if menu not in role.menus:
                    role.menus.append(menu)

        # 部门
        dept_map: dict[str, Department] = {}
        for name, single, monthly in DEPARTMENTS:
            dept = db.execute(
                select(Department).where(Department.name == name)
            ).scalar_one_or_none()
            if dept is None:
                dept = Department(name=name, single_limit=single, monthly_limit=monthly)
                db.add(dept)
                db.flush()
            dept_map[name] = dept

        # 用户
        for username, name, role_code, dept_name in DEMO_USERS:
            exists = db.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()
            if exists:
                continue
            db.add(
                User(
                    username=username,
                    name=name,
                    password_hash=hash_password(DEMO_PASSWORD),
                    role_id=role_map[role_code].id,
                    dept_id=dept_map[dept_name].id,
                    status="NORMAL",
                )
            )
        db.commit()
        print("[seed] 角色 / 菜单 / 部门 / 演示用户 就绪")
        print(f"[seed] 演示密码统一为 {DEMO_PASSWORD}：", ", ".join(u[0] for u in DEMO_USERS))
    finally:
        db.close()


def main() -> None:
    args = set(sys.argv[1:])
    print(f"[db] {settings.DB_USER}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")

    if "--ddl" in args:
        print_ddl()
        return

    if "--drop" in args:
        Base.metadata.drop_all(bind=engine)
        print("[db] 已删除全部表")

    Base.metadata.create_all(bind=engine)
    print(f"[db] 建表完成，共 {len(Base.metadata.sorted_tables)} 张表：")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")
    seed()


if __name__ == "__main__":
    main()
