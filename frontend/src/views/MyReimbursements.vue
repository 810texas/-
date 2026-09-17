<template>
  <div class="page">
    <h3 class="page-title">我的报销单</h3>

    <div class="page-card">
      <div class="toolbar">
        <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width: 160px">
          <el-option v-for="s in statuses" :key="s" :label="statusText(s)" :value="s" />
        </el-select>
        <el-button type="primary" @click="$router.push('/new-reimbursement')">新建报销单</el-button>
        <el-button @click="load">刷新</el-button>
      </div>

      <el-table :data="filtered" v-loading="loading" empty-text="暂无报销单，点击「新建报销单」开始">
        <el-table-column prop="code" label="报销单号" width="200" />
        <el-table-column prop="reason" label="报销事由" min-width="160" show-overflow-tooltip />
        <el-table-column label="金额（元）" width="130" align="right">
          <template #default="{ row }">{{ money(row.total_amount) }}</template>
        </el-table-column>
        <el-table-column prop="invoice_count" label="发票张数" width="90" align="center" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.risk_level === 'MID'" type="warning" size="small">中</el-tag>
            <el-tag v-else type="success" size="small">低</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="版本" prop="version" width="70" align="center" />
        <el-table-column label="提交时间" width="170">
          <template #default="{ row }">{{ timeText(row.submitted_at) }}</template>
        </el-table-column>
        <el-table-column label="驳回原因" min-width="180">
          <template #default="{ row }">
            <span v-if="row.status === 'REJECTED'" class="reject">{{ row.review_comment || '—' }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button v-if="row.status === 'DRAFT'" link type="primary" @click="edit(row)">继续填单</el-button>
            <el-button
              v-if="row.status === 'REJECTED'"
              link
              type="warning"
              @click="doResubmit(row)"
            >重新提交</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer v-model="drawer" title="报销单详情" size="720px">
      <div v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="报销单号">{{ detail.code }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(detail.status)" size="small">{{ statusText(detail.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="报销事由" :span="2">{{ detail.reason || '—' }}</el-descriptions-item>
          <el-descriptions-item label="总金额">￥{{ money(detail.total_amount) }}</el-descriptions-item>
          <el-descriptions-item label="发票张数">{{ detail.invoice_count }}</el-descriptions-item>
          <el-descriptions-item label="风险等级">
            {{ detail.risk_level === 'MID' ? '中（有预警）' : '低（无预警）' }}
          </el-descriptions-item>
          <el-descriptions-item label="版本号">{{ detail.version }}</el-descriptions-item>
          <el-descriptions-item label="风险明细" :span="2">{{ detail.risk_detail || '无' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.review_comment" label="驳回原因" :span="2">
            <span class="reject">{{ detail.review_comment }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <h4>发票明细</h4>
        <el-table :data="detail.invoices" size="small" border>
          <el-table-column label="发票号码" prop="invoice_no" width="130" />
          <el-table-column label="类型" prop="invoice_type" width="80" />
          <el-table-column label="销售方" prop="seller_name" min-width="150" show-overflow-tooltip />
          <el-table-column label="价税合计" width="110" align="right">
            <template #default="{ row }">￥{{ money(row.total_amount) }}</template>
          </el-table-column>
          <el-table-column label="费用类别" width="90">
            <template #default="{ row }">{{ row.category || '未填' }}</template>
          </el-table-column>
          <el-table-column label="置信度" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.ocr_confidence < 0.85 ? 'warning' : 'success'" size="small">
                {{ row.ocr_confidence }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="影像" width="90" align="center">
            <template #default="{ row }">
              <el-image
                :src="api.imageUrl(row.attachment_id)"
                :preview-src-list="[api.imageUrl(row.attachment_id)]"
                fit="cover"
                style="width: 40px; height: 40px"
                preview-teleported
              />
            </template>
          </el-table-column>
        </el-table>

        <h4>审核轨迹</h4>
        <el-timeline>
          <el-timeline-item
            v-for="log in detail.logs"
            :key="log.id"
            :timestamp="timeText(log.created_at)"
            placement="top"
          >
            <b>{{ ACTION_TEXT[log.action] || log.action }}</b>
            <span class="muted"> · {{ log.operator }} · 结果 {{ statusText(log.result) || log.result }}</span>
            <div v-if="log.reason" class="muted">{{ log.reason }}</div>
          </el-timeline-item>
        </el-timeline>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { ACTION_TEXT, money, statusText, statusType, timeText } from '../utils/format'

const router = useRouter()
const rows = ref([])
const loading = ref(false)
const statusFilter = ref('')
const statuses = ['DRAFT', 'PENDING', 'APPROVED', 'REJECTED']

const drawer = ref(false)
const detail = ref(null)

const filtered = computed(() =>
  statusFilter.value ? rows.value.filter((r) => r.status === statusFilter.value) : rows.value,
)

async function load() {
  loading.value = true
  try {
    rows.value = await api.myReimbursements()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function openDetail(row) {
  try {
    detail.value = await api.reimbursementDetail(row.id)
    drawer.value = true
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function edit(row) {
  router.push({ name: 'new-reimbursement', query: { id: row.id } })
}

async function doResubmit(row) {
  try {
    await ElMessageBox.confirm(
      `确认重新提交「${row.code}」？版本号将 +1，历史审核轨迹保留。`,
      '重新提交',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    const res = await api.resubmit(row.id)
    ElMessage.success(`已重新提交，当前版本 v${res.reimbursement.version}`)
    await load()
  } catch (e) {
    ElMessageBox.alert(
      `${e.message}\n\n${(e.reasons || []).map((r) => `· ${r}`).join('\n')}`,
      '提交被拦截',
      { type: 'error' },
    )
  }
}

onMounted(load)
</script>

<style scoped>
.reject { color: #f56c6c; }
h4 { margin: 20px 0 10px; font-size: 14px; }
</style>
