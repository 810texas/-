<template>
  <el-container class="shell">
    <el-aside width="212px" class="aside">
      <div class="brand">智能发票报销审核</div>
      <el-menu :default-active="route.path" router class="menu">
        <el-menu-item v-for="m in auth.menus" :key="m.path" :index="m.path">
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="muted">{{ roleLabel }}</span>
        <div class="right">
          <span class="user">{{ auth.user?.name }}（{{ auth.user?.dept || '未分配部门' }}）</span>
          <el-button link type="primary" @click="onLogout">退出登录</el-button>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const roleLabel = computed(() => {
  const map = { EMPLOYEE: '员工工作台', FINANCE: '财务审核工作台', ADMIN: '系统管理' }
  return map[auth.role] || ''
})

async function onLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.shell { height: 100vh; }
.aside { background: #1f2d3d; color: #fff; }
.brand { padding: 18px 16px; font-size: 15px; font-weight: 600; color: #fff; letter-spacing: 1px; }
.menu { border-right: none; background: transparent; }
.menu :deep(.el-menu-item) { color: #c0c4cc; }
.menu :deep(.el-menu-item.is-active) { color: #fff; background: #2b3a4d; }
.header {
  display: flex; align-items: center; justify-content: space-between;
  background: #fff; border-bottom: 1px solid #ebeef5;
}
.right { display: flex; align-items: center; gap: 16px; }
.user { font-size: 13px; }
</style>
