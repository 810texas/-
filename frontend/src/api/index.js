import axios from 'axios'

// 开发期走 vite proxy（/api → 127.0.0.1:8000），Cookie 同源无需额外配置
const http = axios.create({ baseURL: '/api/v1', timeout: 60000, withCredentials: true })

// CSRF 双提交 Token：从 Cookie 读，写操作放进请求头
let csrfToken = readCookie('csrf_token')

export function readCookie(name) {
  const hit = document.cookie.split('; ').find((row) => row.startsWith(`${name}=`))
  return hit ? decodeURIComponent(hit.split('=').slice(1).join('=')) : ''
}

export function setCsrfToken(token) {
  csrfToken = token || readCookie('csrf_token')
  if (csrfToken) {
    document.cookie = `csrf_token=${encodeURIComponent(csrfToken)}; path=/`
  }
}

http.interceptors.request.use((config) => {
  const method = (config.method || 'get').toUpperCase()
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    config.headers['X-CSRF-Token'] = csrfToken || readCookie('csrf_token')
  }
  return config
})

// 统一错误提示：把后端 detail 列表（硬拦截原因）抛给调用方
http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const detail = error.response?.data?.detail
    let message = '请求失败'
    let reasons = []
    if (typeof detail === 'string') message = detail
    else if (detail && typeof detail === 'object') {
      message = detail.message || '请求失败'
      reasons = detail.reasons || []
    } else if (error.message) message = error.message
    return Promise.reject(Object.assign(new Error(message), { reasons, status: error.response?.status }))
  },
)

export const api = {
  // 鉴权
  login: (payload) => http.post('/auth/login', payload).then((r) => r.data),
  logout: () => http.post('/auth/logout', {}).then((r) => r.data),
  me: () => http.get('/auth/me').then((r) => r.data),

  // 元数据
  meta: () => http.get('/meta').then((r) => r.data),
  departments: () => http.get('/departments').then((r) => r.data),

  // 员工
  createReimbursement: (payload) => http.post('/reimbursements', payload).then((r) => r.data),
  myReimbursements: () => http.get('/reimbursements/mine').then((r) => r.data),
  reimbursementDetail: (id) => http.get(`/reimbursements/${id}`).then((r) => r.data),
  updateReason: (id, reason) => http.put(`/reimbursements/${id}`, { reason }).then((r) => r.data),
  removeInvoice: (rid, iid) => http.delete(`/reimbursements/${rid}/invoices/${iid}`).then((r) => r.data),
  uploadInvoices: (rid, files) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    if (rid) form.append('reimbursement_id', String(rid))
    return http.post('/invoices/upload', form).then((r) => r.data)
  },
  patchInvoice: (id, payload) => http.patch(`/invoices/${id}`, payload).then((r) => r.data),
  invoiceChanges: (id) => http.get(`/invoices/${id}/changes`).then((r) => r.data),
  auditPreview: (rid) =>
    http.get('/reimbursements/audit', { params: { reimbursement_id: rid } }).then((r) => r.data),
  submit: (id) => http.post(`/reimbursements/${id}/submit`, {}).then((r) => r.data),
  resubmit: (id) => http.post(`/reimbursements/${id}/resubmit`, {}).then((r) => r.data),
  imageUrl: (attachmentId) => `/api/v1/attachments/${attachmentId}/raw`,

  // 财务
  todos: (params) => http.get('/review/todos', { params }).then((r) => r.data),
  reviewDetail: (id) => http.get(`/review/${id}`).then((r) => r.data),
  approve: (id, comment) => http.post(`/review/${id}/approve`, { comment }).then((r) => r.data),
  reject: (id, comment) => http.post(`/review/${id}/reject`, { comment }).then((r) => r.data),
  logs: (params) => http.get('/review/logs/query', { params }).then((r) => r.data),

  // 管理员
  users: () => http.get('/admin/users').then((r) => r.data),
  createUser: (payload) => http.post('/admin/users', payload).then((r) => r.data),
  updateUser: (id, payload) => http.put(`/admin/users/${id}`, payload).then((r) => r.data),
  resetPassword: (id, newPassword) =>
    http.post(`/admin/users/${id}/reset-password`, { new_password: newPassword }).then((r) => r.data),
  unlockUser: (id) => http.post(`/admin/users/${id}/unlock`, {}).then((r) => r.data),
  adminDepartments: () => http.get('/admin/departments').then((r) => r.data),
  createDepartment: (payload) => http.post('/admin/departments', payload).then((r) => r.data),
  updateDepartment: (id, payload) => http.put(`/admin/departments/${id}`, payload).then((r) => r.data),
  roles: () => http.get('/admin/roles').then((r) => r.data),
  menus: () => http.get('/admin/menus').then((r) => r.data),
}

export default http
