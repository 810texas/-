"""模型包：导入即注册到 Base.metadata，供建表脚本使用。

导入顺序有依赖：rbac（角色/菜单）→ user（部门/用户）→ document（附件/发票/单据/留痕）。
"""
from app.models.rbac import Menu, RefreshToken, Role, role_menu
from app.models.user import Department, User
from app.models.document import (
    EXPENSE_CATEGORIES,
    INVOICE_TYPES,
    REIMB_STATUS,
    Attachment,
    FieldChangeLog,
    Invoice,
    OcrTask,
    Reimbursement,
    ReviewLog,
)

__all__ = [
    "Attachment",
    "Department",
    "EXPENSE_CATEGORIES",
    "FieldChangeLog",
    "INVOICE_TYPES",
    "Invoice",
    "Menu",
    "OcrTask",
    "REIMB_STATUS",
    "RefreshToken",
    "Reimbursement",
    "ReviewLog",
    "Role",
    "User",
    "role_menu",
]
