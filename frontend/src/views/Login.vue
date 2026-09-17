<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2 class="title">智能发票报销审核系统</h2>
      <p class="muted">OCR 自动填单 · 规则化预审 · 全程留痕</p>
      <el-form :model="form" @submit.prevent="onSubmit" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" @keyup.enter="onSubmit" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" @keyup.enter="onSubmit" />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="submit" @click="onSubmit">登录</el-button>
      </el-form>
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="alert" />
      <div class="demo muted">
        演示账号（密码均 123456）：employee / finance / admin
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const form = reactive({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function onSubmit() {
  if (!form.username || !form.password) {
    error.value = '请输入用户名与密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const user = await auth.login(form.username, form.password)
    const fallback = user.role === 'FINANCE' ? '/review/todos' : user.role === 'ADMIN' ? '/admin/users' : '/my-reimbursements'
    router.push(route.query.redirect || fallback)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #1f2d3d, #3a5169);
}
.login-card { width: 380px; padding: 8px 12px; }
.title { margin: 0 0 4px; font-size: 19px; }
.submit { width: 100%; margin-top: 6px; }
.alert { margin-top: 14px; }
.demo { margin-top: 14px; line-height: 1.6; }
</style>
