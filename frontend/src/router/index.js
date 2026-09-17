import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/Login.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('../layout/AppLayout.vue'),
    children: [
      { path: '', redirect: '/my-reimbursements' },
      {
        path: 'my-reimbursements',
        name: 'my-reimbursements',
        component: () => import('../views/MyReimbursements.vue'),
        meta: { roles: ['EMPLOYEE'] },
      },
      {
        path: 'new-reimbursement',
        name: 'new-reimbursement',
        component: () => import('../views/NewReimbursement.vue'),
        meta: { roles: ['EMPLOYEE'] },
      },
      {
        path: 'review/todos',
        name: 'review-todos',
        component: () => import('../views/ReviewTodos.vue'),
        meta: { roles: ['FINANCE'] },
      },
      {
        path: 'review/logs',
        name: 'review-logs',
        component: () => import('../views/ReviewLogs.vue'),
        meta: { roles: ['FINANCE', 'ADMIN'] },
      },
      {
        path: 'admin/users',
        name: 'admin-users',
        component: () => import('../views/AdminUsers.vue'),
        meta: { roles: ['ADMIN'] },
      },
      {
        path: 'admin/departments',
        name: 'admin-departments',
        component: () => import('../views/AdminDepartments.vue'),
        meta: { roles: ['ADMIN'] },
      },
      {
        path: 'admin/base',
        name: 'admin-base',
        component: () => import('../views/AdminBase.vue'),
        meta: { roles: ['ADMIN'] },
      },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.loaded) await auth.fetchMe()
  if (to.meta.public) return auth.isLogin ? '/my-reimbursements' : true
  if (!auth.isLogin) return { name: 'login', query: { redirect: to.fullPath } }
  const roles = to.meta.roles
  if (roles && !roles.includes(auth.role)) {
    // 角色不匹配时回落到该角色自己的首页
    return auth.role === 'FINANCE' ? '/review/todos' : auth.role === 'ADMIN' ? '/admin/users' : '/my-reimbursements'
  }
  return true
})

export default router
