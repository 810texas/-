// 状态与标签映射：报销单状态机、风险等级、发票占用状态
export const STATUS_TEXT = {
  DRAFT: '草稿',
  PENDING: '待审核',
  APPROVED: '已通过',
  REJECTED: '已驳回',
}

export const STATUS_TYPE = {
  DRAFT: 'info',
  PENDING: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
}

export const OCCUPY_TEXT = {
  FREE: '未占用',
  OCCUPIED: '已占用',
}

export const ACTION_TEXT = {
  SUBMIT: '提交',
  APPROVE: '通过',
  REJECT: '驳回',
  RESUBMIT_DRAFT: '驳回后重新编辑',
}

export function statusText(value) {
  return STATUS_TEXT[value] || value
}

export function statusType(value) {
  return STATUS_TYPE[value] || 'info'
}

export function money(value) {
  const num = Number(value || 0)
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function timeText(value) {
  if (!value) return '—'
  return String(value).replace('T', ' ').slice(0, 19)
}
