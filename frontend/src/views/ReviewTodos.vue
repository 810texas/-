<template>
  <div class="page">
    <h3 class="page-title">待办审核</h3>

    <div class="page-card">
      <div class="toolbar">
        <el-select v-model="filters.status" placeholder="状态（默认待审核）" clearable style="width: 170px">
          <el-option v-for="s in statuses" :key="s" :label="statusText(s)" :value="s" />
        </el-select>
        <el-input v-model="filters.applicant" placeholder="申请人姓名/账号" clearable style="width: 180px" />
        <el-select v-model="filters.order" style="width: 170px">
          <el-option label="按提交时间" value="submitted_at" />
          <el-option label="按金额从高到低" value="amount" />
          <el-option label="按风险等级" value="risk" />
        </el-select>
        <el-button type="primary" @click="load">查询</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" empty-text="暂无待办单据">
        <el-table-column prop="code" label="报销单号" width="200" />
        <el-table-column prop="applicant" label="申请人" width="90" />
        <el-table-column prop="dept" label="部门" width="100" />
        <el-table-column prop="reason" label="报销事由" min-width="160" show-overflow-tooltip />
        <el-table-column label="金额（元）" width="120" align="right">
          <template #default="{ row }">{{ money(row.total_amount) }}</template>
        </el-table-column>
        <el-table-column prop="invoice_count" label="发票张数" width="90" align="center" />
        <el-table-column label="风险" width="90">
          <template #default="{ row }">
            <el-tag :type="row.risk_level === 'MID' ? 'warning' : 'success'" size="small">
              {{ row.risk_level === 'MID' ? '中（有预警）' : '低' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" width="165">
          <template #default="{ row }">{{ timeText(row.submitted_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="open(row)">审核</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer v-model="drawer" title="单据审核" size="860px">
      <div v-if="detail" v-loading="detailLoading">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="报销单号">{{ detail.code }}</el-descriptions-item>
          <el-descriptions-item label="申请人">{{ detail.applicant.name }}（{{ detail.applicant.dept || '—' }}）</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(detail.status)" size="small">{{ statusText(detail.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="报销事由" :span="3">{{ detail.reason || '—' }}</el-descriptions-item>
          <el-descriptions-item label="总金额">￥{{ money(detail.total_amount) }}</el-descriptions-item>
          <el-descriptions-item label="发票张数">{{ detail.invoice_count }}</el-descriptions-item>
          <el-descriptions-item label="版本号">v{{ detail.version }}</el-descriptions-item>
          <el-descriptions-item label="预审预警" :span="3">
            <span :class="detail.risk_level === 'MID' ? 'warn' : 'muted'">
              {{ detail.risk_detail || '无预警' }}
            </span>
          </el-descriptions-item>
        </el-descriptions>

        <h4>发票明细与 OCR 结果</h4>
        <el-table :data="detail.invoices" size="small" border>
          <el-table-column label="影像" width="70" align="center">
            <template #default="{ row }">
              <el-image
                :src="api.imageUrl(row.attachment_id)"
                :preview-src-list="[api.imageUrl(row.attachment_id)]"
                fit="cover"
                style="width: 44px; height: 44px"
                preview-teleported
              />
            </template>
          </el-table-column>
          <el-table-column label="类型" prop="invoice_type" width="80" />
          <el-table-column label="发票代码" width="110">
            <template #default="{ row }">{{ row.invoice_code || '—（数电票）' }}</template>
          </el-table-column>
          <el-table-column label="发票号码" prop="invoice_no" width="120" />
          <el-table-column label="开票日期" prop="invoice_date" width="110" />
          <el-table-column label="销售方" prop="seller_name" min-width="150" show-overflow-tooltip />
          <el-table-column label="不含税" width="100" align="right">
            <template #default="{ row }">{{ money(row.amount_excl_tax) }}</template>
          </el-table-column>
          <el-table-column label="税额" width="90" align="right">
            <template #default="{ row }">{{ money(row.tax_amount) }}</template>
          </el-table-column>
          <el-table-column label="价税合计" width="105" align="right">
            <template #default="{ row }">{{ money(row.total_amount) }}</template>
          </el-table-column>
          <el-table-column label="费用类别" width="90">
            <template #default="{ row }">{{ row.category || '未填' }}</template>
          </el-table-column>
          <el-table-column label="置信度" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="row.ocr_confidence < 0.85 ? 'warning' : 'success'" size="small">{{ row.ocr_confidence }}</el-tag>
              <div v-if="row.need_confirm" class="muted">待人工确认</div>
            </template>
          </el-table-column>
        </el-table>

        <h4>审核轨迹</h4>
        <el-timeline>
          <el-timeline-item v-for="log in detail.logs" :key="log.id" :timestamp="timeText(log.created_at)" placement="top">
            <b>{{ ACTION_TEXT[log.action] || log.action }}</b>
            <span class="muted"> · {{ log.operator }}</span>
            <div v-if="log.reason" class="muted">{{ log.reason }}</div>
          </el-timeline-item>
        </el-timeline>

        <div v-if="detail.status === 'PENDING'" class="decision">
          <el-input v-model="comment" type="textarea" :rows="3" maxlength="200" show-word-limit
                    placeholder="驳回必须填写原因，例如：发票抬头与公司主体不一致，请补充说明" />
          <div class="toolbar decision-actions">
            <el-button type="success" :loading="acting" @click="decide('approve')">通过</el-button>
            <el-button type="danger" :loading="acting" @click="decide('reject')">驳回</el-button>
            <span class="muted">通过意见可选；驳回必填原因，原因对申请人可见</span>
          </div>
        </div>
        <el-alert v-else type="info" :closable="false" show-icon
                  :title="`当前状态为 ${statusText(detail.status)}，不可再次审核`" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { ACTION_TEXT, money, statusText, statusType, timeText } from '../utils/format'

const rows = ref([])
const loading = ref(false)
const drawer = ref(false)
const detail = ref(null)
const detailLoading = ref(false)
const acting = ref(false)
const comment = ref('')
const filters = reactive({ status: '', applicant: '', order: 'submitted_at' })
const statuses = ['DRAFT', 'PENDING', 'APPROVED', 'REJECTED']

async function load() {
  loading.value = true
  try {
    rows.value = await api.todos({
      status: filters.status || undefined,
      applicant: filters.applicant || undefined,
      order: filters.order,
    })
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function open(row) {
  drawer.value = true
  detailLoading.value = true
  comment.value = ''
  try {
    detail.value = await api.reviewDetail(row.id)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    detailLoading.value = false
  }
}

async function decide(action) {
  if (action === 'reject' && !comment.value.trim()) {
    ElMessage.warning('驳回必须填写原因')
    return
  }
  const label = action === 'approve' ? '通过' : '驳回'
  try {
    await ElMessageBox.confirm(`确认${label}单据「${detail.value.code}」？`, `${label}确认`, {
      type: action === 'approve' ? 'success' : 'warning',
    })
  } catch {
    return
  }
  acting.value = true
  try {
    if (action === 'approve') await api.approve(detail.value.id, comment.value)
    else await api.reject(detail.value.id, comment.value)
    ElMessage.success(`已${label}`)
    drawer.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    acting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
h4 { margin: 20px 0 10px; font-size: 14px; }
.warn { color: #e6a23c; }
.decision { margin-top: 18px; }
.decision-actions { margin-top: 12px; }
</style>
