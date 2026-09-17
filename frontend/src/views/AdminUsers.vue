<template>
  <div class="page">
    <h3 class="page-title">用户管理</h3>

    <div class="page-card">
      <div class="toolbar">
        <el-button type="primary" @click="openCreate">新建用户</el-button>
        <el-button @click="load">刷新</el-button>
        <span class="muted">密码使用 BCrypt 散列存储；重置密码会使该用户已登录的凭证立即失效。</span>
      </div>

      <el-table :data="rows" v-loading="loading" empty-text="暂无用户">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="登录账号" width="130" />
        <el-table-column prop="name" label="姓名" width="110" />
        <el-table-column label="角色" width="110">
          <template #default="{ row }">{{ roleName(row.role) }}</template>
        </el-table-column>
        <el-table-column prop="dept" label="部门" width="120" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'NORMAL' ? 'success' : 'danger'" size="small">
              {{ row.status === 'NORMAL' ? '正常' : '锁定/停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="锁定截止" width="170">
          <template #default="{ row }">{{ timeText(row.locked_until) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="280">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="warning" @click="resetPwd(row)">重置密码</el-button>
            <el-button link type="success" @click="unlock(row)">解锁</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialog" :title="form.id ? '编辑用户' : '新建用户'" width="460px">
      <el-form label-width="90px">
        <el-form-item label="登录账号">
          <el-input v-model="form.username" :disabled="!!form.id" />
        </el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item v-if="!form.id" label="初始密码">
          <el-input v-model="form.password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role_id" style="width: 100%">
            <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门">
          <el-select v-model="form.dept_id" clearable style="width: 100%">
            <el-option v-for="d in depts" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio value="NORMAL">正常</el-radio>
            <el-radio value="LOCKED">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { timeText } from '../utils/format'

const rows = ref([])
const roles = ref([])
const depts = ref([])
const loading = ref(false)
const saving = ref(false)
const dialog = ref(false)
const form = reactive({ id: null, username: '', name: '', password: '', role_id: null, dept_id: null, status: 'NORMAL' })

function roleName(code) {
  return roles.value.find((r) => r.code === code)?.name || code
}

async function load() {
  loading.value = true
  try {
    const [users, roleList, deptList] = await Promise.all([api.users(), api.roles(), api.adminDepartments()])
    rows.value = users
    roles.value = roleList
    depts.value = deptList
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, { id: null, username: '', name: '', password: '', role_id: roles.value[0]?.id, dept_id: depts.value[0]?.id, status: 'NORMAL' })
  dialog.value = true
}

function openEdit(row) {
  Object.assign(form, {
    id: row.id, username: row.username, name: row.name, password: '',
    role_id: row.role_id, dept_id: row.dept_id, status: row.status === 'NORMAL' ? 'NORMAL' : 'LOCKED',
  })
  dialog.value = true
}

async function save() {
  saving.value = true
  try {
    if (form.id) {
      await api.updateUser(form.id, {
        username: form.username, name: form.name, role_id: form.role_id,
        dept_id: form.dept_id, status: form.status,
      })
    } else {
      await api.createUser({
        username: form.username, name: form.name, password: form.password,
        role_id: form.role_id, dept_id: form.dept_id, status: 'NORMAL',
      })
    }
    ElMessage.success('已保存')
    dialog.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function resetPwd(row) {
  try {
    const { value } = await ElMessageBox.prompt(`为「${row.name}」设置新密码（至少 6 位）`, '重置密码', {
      inputType: 'password',
      inputValidator: (v) => (v && v.length >= 6) || '密码至少 6 位',
    })
    await api.resetPassword(row.id, value)
    ElMessage.success('已重置，该用户需重新登录')
  } catch (e) {
    if (e !== 'cancel' && e?.message) ElMessage.error(e.message)
  }
}

async function unlock(row) {
  try {
    await api.unlockUser(row.id)
    ElMessage.success('已解锁并恢复为正常状态')
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(load)
</script>
