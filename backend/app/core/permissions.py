"""权限码常量（需求 4.1：本期不做可配置权限矩阵，三角色边界固定）。"""
from fastapi import HTTPException, status

ROLE_EMPLOYEE = "EMPLOYEE"
ROLE_FINANCE = "FINANCE"
ROLE_ADMIN = "ADMIN"

# 权限码
INVOICE_UPLOAD = "invoice:upload"        # 员工：上传发票
INVOICE_EDIT = "invoice:edit"            # 员工：修正识别字段
REIMB_SUBMIT = "reimb:submit"            # 员工：提交报销单
REIMB_VIEW_OWN = "reimb:view_own"        # 员工：查看本人单据
REIMB_REVIEW = "reimb:review"            # 财务：通过 / 驳回
REIMB_VIEW_ALL = "reimb:view_all"        # 财务：跨用户查询
REVIEW_LOG_VIEW = "review:log"           # 审核轨迹查询
ADMIN_USER_MANAGE = "admin:user"         # 管理员：用户管理
ADMIN_DEPT_MANAGE = "admin:dept"         # 管理员：部门维护
ADMIN_BASE_DATA = "admin:base"           # 管理员：基础数据

ROLE_PERMISSIONS: dict[str, set[str]] = {
    ROLE_EMPLOYEE: {
        INVOICE_UPLOAD,
        INVOICE_EDIT,
        REIMB_SUBMIT,
        REIMB_VIEW_OWN,
    },
    ROLE_FINANCE: {
        REIMB_REVIEW,
        REIMB_VIEW_ALL,
        REVIEW_LOG_VIEW,
    },
    ROLE_ADMIN: {
        ADMIN_USER_MANAGE,
        ADMIN_DEPT_MANAGE,
        ADMIN_BASE_DATA,
        REIMB_VIEW_ALL,
        REVIEW_LOG_VIEW,
    },
}


def has_permission(role_code: str, permission: str) -> bool:
    """三角色边界固定，管理员不隐式继承财务的全部业务权限。"""
    return permission in ROLE_PERMISSIONS.get(role_code, set())


def require_permission(role_code: str, permission: str) -> None:
    """后端权限码校验，失败抛 403（需求 5.2 前后端双重校验）。"""
    if not has_permission(role_code, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权执行该操作"
        )


def is_finance_like(role_code: str) -> bool:
    """财务与管理员可跨用户查询数据（需求 3.2）。"""
    return role_code in (ROLE_FINANCE, ROLE_ADMIN)
