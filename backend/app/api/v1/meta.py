"""基础数据与元信息：费用类别、发票类型、部门、用户。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.permissions import is_finance_like
from app.models.document import EXPENSE_CATEGORIES, INVOICE_TYPES
from app.models.user import Department, User

router = APIRouter()


@router.get("/meta")
def meta(user: User = Depends(get_current_user)):
    """前端下拉与字典数据。"""
    return {
        "expense_categories": EXPENSE_CATEGORIES,
        "invoice_types": INVOICE_TYPES,
        "statuses": ["DRAFT", "PENDING", "APPROVED", "REJECTED"],
        "can_review": is_finance_like(user.role.code),
    }


@router.get("/departments")
def departments(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    depts = db.execute(select(Department).order_by(Department.id)).scalars().all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "single_limit": float(d.single_limit or 0),
            "monthly_limit": float(d.monthly_limit or 0),
        }
        for d in depts
    ]


@router.get("/users")
def users(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """财务/管理员可查用户；员工仅返回自己。"""
    if not is_finance_like(user.role.code):
        rows = [user]
    else:
        rows = db.execute(select(User).order_by(User.id)).scalars().all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "name": u.name,
            "role": u.role.code,
            "dept": u.dept.name if u.dept else "",
            "status": u.status,
        }
        for u in rows
    ]
