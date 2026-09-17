"""管理员：用户管理、部门维护、基础数据（需求 3.3）。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import guard
from app.core.database import get_db
from app.core.permissions import (
    ADMIN_BASE_DATA,
    ADMIN_DEPT_MANAGE,
    ADMIN_USER_MANAGE,
    ROLE_PERMISSIONS,
)
from app.core.security import hash_password
from app.models.rbac import Menu, Role
from app.models.user import Department, User
from app.services import auth as auth_service

router = APIRouter()


class UserIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=50)
    password: str | None = Field(default=None, max_length=128)
    role_id: int
    dept_id: int | None = None
    status: str = "NORMAL"


class DeptIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    single_limit: float = 0
    monthly_limit: float = 0


def user_row(db: Session, u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "name": u.name,
        "role_id": u.role_id,
        "role": u.role.code,
        "dept_id": u.dept_id,
        "dept": u.dept.name if u.dept else "",
        "status": u.status,
        "locked_until": u.locked_until,
        "failed_attempts": u.failed_attempts,
    }


@router.get("/admin/users")
def list_users(
    db: Session = Depends(get_db), user: User = Depends(guard(ADMIN_USER_MANAGE))
):
    rows = db.execute(select(User).order_by(User.id)).scalars().all()
    return [user_row(db, u) for u in rows]


@router.post("/admin/users")
def create_user(
    payload: UserIn,
    db: Session = Depends(get_db),
    user: User = Depends(guard(ADMIN_USER_MANAGE)),
):
    if db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if not payload.password:
        raise HTTPException(status_code=400, detail="新建用户必须设置初始密码")
    new_user = User(
        username=payload.username,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role_id=payload.role_id,
        dept_id=payload.dept_id,
        status=payload.status,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return user_row(db, new_user)


@router.put("/admin/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserIn,
    db: Session = Depends(get_db),
    user: User = Depends(guard(ADMIN_USER_MANAGE)),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == user.id and payload.status != "NORMAL":
        raise HTTPException(status_code=400, detail="不能停用当前登录账号")
    target.name = payload.name
    target.role_id = payload.role_id
    target.dept_id = payload.dept_id
    target.status = payload.status
    if target.status == "NORMAL":
        # 停用解除时清空锁定
        target.failed_attempts = 0
        target.locked_until = None
    db.commit()
    db.refresh(target)
    return user_row(db, target)


@router.post("/admin/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(guard(ADMIN_USER_MANAGE)),
):
    """重置密码：密码版本 +1，旧令牌全部失效。"""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    new_password = (payload or {}).get("new_password") or ""
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    auth_service.set_password(db, target, new_password)
    return {"ok": True}


@router.post("/admin/users/{user_id}/unlock")
def unlock(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(guard(ADMIN_USER_MANAGE)),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    target.status = "NORMAL"
    target.failed_attempts = 0
    target.locked_until = None
    db.commit()
    return {"ok": True}


@router.get("/admin/departments")
def list_depts(
    db: Session = Depends(get_db), user: User = Depends(guard(ADMIN_DEPT_MANAGE))
):
    rows = db.execute(select(Department).order_by(Department.id)).scalars().all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "single_limit": float(d.single_limit or 0),
            "monthly_limit": float(d.monthly_limit or 0),
        }
        for d in rows
    ]


@router.post("/admin/departments")
def create_dept(
    payload: DeptIn,
    db: Session = Depends(get_db),
    user: User = Depends(guard(ADMIN_DEPT_MANAGE)),
):
    if db.execute(select(Department).where(Department.name == payload.name)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="部门已存在")
    dept = Department(
        name=payload.name,
        single_limit=payload.single_limit,
        monthly_limit=payload.monthly_limit,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return {"id": dept.id, "name": dept.name}


@router.put("/admin/departments/{dept_id}")
def update_dept(
    dept_id: int,
    payload: DeptIn,
    db: Session = Depends(get_db),
    user: User = Depends(guard(ADMIN_DEPT_MANAGE)),
):
    dept = db.get(Department, dept_id)
    if dept is None:
        raise HTTPException(status_code=404, detail="部门不存在")
    dept.name = payload.name
    dept.single_limit = payload.single_limit
    dept.monthly_limit = payload.monthly_limit
    db.commit()
    db.refresh(dept)
    return {
        "id": dept.id,
        "name": dept.name,
        "single_limit": float(dept.single_limit or 0),
        "monthly_limit": float(dept.monthly_limit or 0),
    }


@router.get("/admin/roles")
def list_roles(
    db: Session = Depends(get_db), user: User = Depends(guard(ADMIN_BASE_DATA))
):
    rows = db.execute(select(Role).order_by(Role.id)).scalars().all()
    return [
        {
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "permissions": sorted(ROLE_PERMISSIONS.get(r.code, [])),
            "menus": [
                {"title": m.title, "path": m.path, "sort": m.sort}
                for m in sorted(r.menus, key=lambda m: m.sort)
            ],
        }
        for r in rows
    ]


@router.get("/admin/menus")
def list_menus(
    db: Session = Depends(get_db), user: User = Depends(guard(ADMIN_BASE_DATA))
):
    rows = db.execute(select(Menu).order_by(Menu.sort)).scalars().all()
    return [
        {
            "id": m.id,
            "title": m.title,
            "path": m.path,
            "icon": m.icon,
            "sort": m.sort,
            "parent_id": m.parent_id,
            "roles": [r.code for r in m.roles],
        }
        for m in rows
    ]
