"""报销单业务：草稿、金额聚合、提交预审、审核决策、状态机与留痕。"""
from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.document import Invoice, Reimbursement, ReviewLog
from app.models.user import User
from app.services import preaudit


def gen_code() -> str:
    return f"BX{datetime.now():%Y%m%d%H%M%S}{secrets.randbelow(900) + 100}"


def get_owned(db: Session, reimb_id: int, user: User) -> Reimbursement:
    """越权防护：员工只能访问本人单据，否则 403（验收标准：越权防护）。"""
    reimb = db.get(Reimbursement, reimb_id)
    if reimb is None:
        raise HTTPException(status_code=404, detail="报销单不存在")
    if reimb.applicant_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该报销单")
    return reimb


def recalc(db: Session, reimb: Reimbursement) -> Reimbursement:
    """重算发票张数与总金额（需求 4.2 聚合金额 + 冗余计数）。"""
    invoices = db.execute(
        select(Invoice).where(Invoice.reimbursement_id == reimb.id)
    ).scalars().all()
    reimb.invoice_count = len(invoices)
    reimb.total_amount = round(sum(float(i.total_amount or 0) for i in invoices), 2)
    db.flush()
    return reimb


def create_draft(db: Session, user: User, reason: str = "") -> Reimbursement:
    reimb = Reimbursement(
        code=gen_code(), applicant_id=user.id, reason=reason, status="DRAFT"
    )
    db.add(reimb)
    db.commit()
    db.refresh(reimb)
    return reimb


def attach_invoice(db: Session, reimb: Reimbursement, invoice: Invoice) -> None:
    if reimb.status != "DRAFT":
        raise HTTPException(status_code=400, detail="仅草稿状态可调整发票")
    invoice.reimbursement_id = reimb.id
    db.flush()
    recalc(db, reimb)


def detach_invoice(db: Session, reimb: Reimbursement, invoice: Invoice) -> None:
    if reimb.status != "DRAFT":
        raise HTTPException(status_code=400, detail="仅草稿状态可调整发票")
    invoice.reimbursement_id = None
    db.flush()
    recalc(db, reimb)


def log(
    db: Session,
    reimb: Reimbursement,
    operator_id: int,
    action: str,
    result: str,
    reason: str = "",
) -> None:
    db.add(
        ReviewLog(
            reimbursement_id=reimb.id,
            operator_id=operator_id,
            action=action,
            result=result,
            reason=reason,
        )
    )


def submit(db: Session, reimb: Reimbursement, user: User) -> preaudit.PreAuditResult:
    """提交：先存草稿再执行预审，命中硬拦截则阻止提交并列出原因（需求 3.1/4.4）。"""
    if reimb.status not in ("DRAFT", "REJECTED"):
        raise HTTPException(status_code=400, detail=f"当前状态 {reimb.status} 不可提交")
    recalc(db, reimb)
    invoices = db.execute(
        select(Invoice).where(Invoice.reimbursement_id == reimb.id)
    ).scalars().all()
    if not invoices:
        raise HTTPException(status_code=400, detail="请先添加发票再提交")

    dept_id = user.dept_id
    dept_name = user.dept.name if user.dept else "未知部门"
    result = preaudit.run_preaudit(
        db, reimb, invoices, float(reimb.total_amount or 0), dept_id, dept_name
    )

    if result.blocked:
        # 硬拦截：不落任何状态变更，仅返回原因供前端展示
        db.rollback()
        return result

    # 发票进入占用态；占用键唯一约束兜底并发重复提交
    try:
        with db.begin_nested():
            for inv in invoices:
                inv.occupy_state = "OCCUPIED"
            reimb.status = "PENDING"
            reimb.submitted_at = datetime.now()
            reimb.risk_level = result.risk_level
            reimb.risk_detail = "；".join(result.warnings)
            log(db, reimb, user.id, "SUBMIT", "PENDING", reimb.risk_detail)
            db.flush()
    except IntegrityError:
        db.rollback()
        result.blocked = True
        result.hard_blocks.append("发票查重唯一约束冲突：该发票已被其他单据占用")
        return result

    db.commit()
    db.refresh(reimb)
    return result


def review(
    db: Session,
    reimb: Reimbursement,
    reviewer: User,
    action: str,
    comment: str = "",
) -> Reimbursement:
    """财务通过 / 驳回；驳回必填原因，驳回释放发票占用（需求 3.2/4.3）。"""
    if reimb.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"当前状态 {reimb.status} 不可审核")

    if action == "REJECT" and not comment.strip():
        raise HTTPException(status_code=400, detail="驳回必须填写原因")

    reimb.reviewed_at = datetime.now()
    reimb.reviewer_id = reviewer.id
    reimb.review_comment = comment

    if action == "APPROVE":
        reimb.status = "APPROVED"
        log(db, reimb, reviewer.id, "APPROVE", "APPROVED", comment)
    elif action == "REJECT":
        reimb.status = "REJECTED"
        invoices = db.execute(
            select(Invoice).where(Invoice.reimbursement_id == reimb.id)
        ).scalars().all()
        for inv in invoices:
            inv.occupy_state = "FREE"
        log(db, reimb, reviewer.id, "REJECT", "REJECTED", comment)
    else:
        raise HTTPException(status_code=400, detail="未知审核动作")

    db.commit()
    db.refresh(reimb)
    return reimb


def resubmit_prepare(db: Session, reimb: Reimbursement, user: User) -> Reimbursement:
    """驳回后重新提交：回到 DRAFT，版本号 +1，历史轨迹保留（需求 4.3）。"""
    if reimb.status != "REJECTED":
        raise HTTPException(status_code=400, detail="仅已驳回的单据可重新提交")
    reimb.status = "DRAFT"
    reimb.version += 1
    reimb.review_comment = ""
    log(db, reimb, user.id, "RESUBMIT_DRAFT", "DRAFT", "驳回后重新编辑")
    db.commit()
    db.refresh(reimb)
    return reimb


def list_for_user(db: Session, user_id: int) -> list[Reimbursement]:
    return list(
        db.execute(
            select(Reimbursement)
            .options(selectinload(Reimbursement.invoices))
            .where(Reimbursement.applicant_id == user_id)
            .order_by(Reimbursement.id.desc())
        ).scalars().all()
    )


def list_pending(
    db: Session,
    status_filter: str | None = None,
    applicant: str | None = None,
    order: str = "submitted_at",
) -> list[Reimbursement]:
    """财务待办列表：按提交时间 / 金额 / 风险等级排序（需求 3.2）。"""
    stmt = select(Reimbursement).options(selectinload(Reimbursement.invoices))
    if status_filter:
        stmt = stmt.where(Reimbursement.status == status_filter)
    else:
        stmt = stmt.where(Reimbursement.status == "PENDING")
    if applicant:
        stmt = stmt.join(User, User.id == Reimbursement.applicant_id).where(
            User.name.like(f"%{applicant}%") | User.username.like(f"%{applicant}%")
        )
    if order == "amount":
        stmt = stmt.order_by(Reimbursement.total_amount.desc())
    elif order == "risk":
        stmt = stmt.order_by(Reimbursement.risk_level.desc(), Reimbursement.submitted_at)
    else:
        stmt = stmt.order_by(Reimbursement.submitted_at.asc())
    return list(db.execute(stmt).scalars().all())


def build_detail(db: Session, reimb: Reimbursement) -> dict:
    """单据详情：含申请人、部门、发票与留痕（需求 3.2 单据详情）。"""
    applicant = db.get(User, reimb.applicant_id)
    logs = db.execute(
        select(ReviewLog)
        .where(ReviewLog.reimbursement_id == reimb.id)
        .order_by(ReviewLog.id.asc())
    ).scalars().all()
    invoices = db.execute(
        select(Invoice).where(Invoice.reimbursement_id == reimb.id).order_by(Invoice.id)
    ).scalars().all()
    return {
        "id": reimb.id,
        "code": reimb.code,
        "applicant": {
            "id": applicant.id,
            "name": applicant.name,
            "username": applicant.username,
            "dept": applicant.dept.name if applicant and applicant.dept else "",
        },
        "reason": reimb.reason,
        "total_amount": float(reimb.total_amount or 0),
        "invoice_count": reimb.invoice_count,
        "status": reimb.status,
        "risk_level": reimb.risk_level,
        "risk_detail": reimb.risk_detail,
        "version": reimb.version,
        "submitted_at": reimb.submitted_at,
        "reviewed_at": reimb.reviewed_at,
        "review_comment": reimb.review_comment,
        "invoices": [
            {
                "id": i.id,
                "invoice_type": i.invoice_type,
                "invoice_code": i.invoice_code,
                "invoice_no": i.invoice_no,
                "invoice_date": i.invoice_date,
                "buyer_name": i.buyer_name,
                "seller_name": i.seller_name,
                "amount_excl_tax": float(i.amount_excl_tax or 0),
                "tax_amount": float(i.tax_amount or 0),
                "total_amount": float(i.total_amount or 0),
                "category": i.category,
                "ocr_confidence": float(i.ocr_confidence or 0),
                "need_confirm": bool(i.need_confirm),
                "occupy_state": i.occupy_state,
                "attachment_id": i.attachment_id,
            }
            for i in invoices
        ],
        "logs": [
            {
                "id": lg.id,
                "action": lg.action,
                "result": lg.result,
                "reason": lg.reason,
                "operator": (db.get(User, lg.operator_id).name if db.get(User, lg.operator_id) else ""),
                "created_at": lg.created_at,
            }
            for lg in logs
        ],
    }


def monthly_used(db: Session, dept_id: int | None) -> float:
    start, end = preaudit.month_range()
    stmt = (
        select(func.coalesce(func.sum(Reimbursement.total_amount), 0))
        .join(User, User.id == Reimbursement.applicant_id)
        .where(
            Reimbursement.status.in_(["PENDING", "APPROVED"]),
            Reimbursement.submitted_at >= start,
            Reimbursement.submitted_at < end,
        )
    )
    if dept_id:
        stmt = stmt.where(User.dept_id == dept_id)
    return float(db.execute(stmt).scalar_one() or 0)
