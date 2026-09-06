<template>
  <div class="page-container llm-model-page">
    <div class="kg-card">
      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-left">
          <el-select
            v-model="providerFilter"
            placeholder="全部供应商"
            clearable
            class="provider-select"
            @change="loadList"
          >
            <el-option
              v-for="p in providers"
              :key="p.key"
              :label="p.label"
              :value="p.key"
            />
          </el-select>
          <el-button :icon="Refresh" @click="loadList">刷新</el-button>
        </div>
        <div class="toolbar-right">
          <el-button type="primary" :icon="Plus" @click="openAdd">新增模型</el-button>
        </div>
      </div>

      <!-- 表格 -->
      <div class="table-wrap">
        <el-table
          v-loading="loading"
          :data="filteredRows"
          style="width: 100%"
          :header-cell-style="{ background: 'transparent' }"
        >
          <el-table-column type="index" label="" width="56" align="center" />
          <el-table-column label="模型" min-width="220">
            <template #default="{ row }">
              <div class="cell-model">
                <span class="model-name">{{ row.displayName }}</span>
                <span class="model-id">{{ row.modelName }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="供应商" width="150" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="providerTagType(row.provider)" effect="light">
                {{ providerLabel(row.provider) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="接口地址" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="mono-text">{{ row.baseUrl }}</span>
            </template>
          </el-table-column>
          <el-table-column label="API Key" width="160" align="center">
            <template #default="{ row }">
              <span v-if="row.hasKey" class="mono-text">{{ row.apiKeyMasked }}</span>
              <span v-else class="no-key">无需密钥</span>
            </template>
          </el-table-column>
          <el-table-column label="推理模型" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.isReasoner" size="small" type="warning" effect="plain">思维链</el-tag>
              <span v-else class="plain-text">—</span>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="90" align="center">
            <template #default="{ row }">
              <el-switch
                :model-value="row.enabled"
                :loading="row._toggling"
                @change="(v: any) => handleToggle(row, v)"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130" align="center" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>

          <template #empty>
            <div class="empty-state">
              <el-icon :size="40" color="#c9cdd4"><Cpu /></el-icon>
              <p class="empty-title">暂无模型配置</p>
              <p class="empty-desc">点击右上角「新增模型」接入 Ollama / OpenAI / DeepSeek / Qwen</p>
            </div>
          </template>
        </el-table>
      </div>
    </div>

    <!-- 用量监控 -->
    <div class="kg-card usage-card">
      <div class="usage-header">
        <div class="usage-title">
          <el-icon><DataLine /></el-icon>
          <span>模型调用监控</span>
        </div>
        <el-radio-group v-model="usageDays" size="small" @change="loadUsage">
          <el-radio-button :value="7">近 7 天</el-radio-button>
          <el-radio-button :value="14">近 14 天</el-radio-button>
          <el-radio-button :value="30">近 30 天</el-radio-button>
        </el-radio-group>
      </div>

      <div class="usage-summary">
        <div class="summary-item">
          <div class="summary-label">总调用次数</div>
          <div class="summary-value">{{ usage.totalCalls.toLocaleString() }}</div>
          <div class="summary-unit">次</div>
        </div>
        <div class="summary-divider" />
        <div class="summary-item">
          <div class="summary-label">Token 总消耗</div>
          <div class="summary-value">{{ formatTokens(usage.totalTokens) }}</div>
          <div class="summary-unit">tokens</div>
        </div>
        <div class="summary-divider" />
        <div class="summary-item">
          <div class="summary-label">使用模型数</div>
          <div class="summary-value">{{ usage.byModel.length }}</div>
          <div class="summary-unit">个</div>
        </div>
      </div>

      <div class="usage-charts">
        <div class="chart-card">
          <div class="chart-card-title">
            <span>API 请求次数</span>
            <span class="chart-card-value">{{ usage.totalCalls.toLocaleString() }}</span>
          </div>
          <div ref="callsChartRef" class="chart-canvas" />
        </div>
        <div class="chart-card">
          <div class="chart-card-title">
            <span>Tokens</span>
            <span class="chart-card-value">{{ usage.totalTokens.toLocaleString() }}</span>
          </div>
          <div ref="tokensChartRef" class="chart-canvas" />
        </div>
      </div>

      <div v-if="usage.byModel.length" class="usage-models">
        <div class="usage-models-title">各模型用量明细</div>
        <div class="model-rows">
          <div v-for="m in usage.byModel" :key="m.modelName" class="model-row">
            <div class="model-row-header">
              <span class="model-dot" />
              <span class="model-row-name">{{ m.modelName }}</span>
              <span class="model-row-stats">
                {{ Number(m.callCount).toLocaleString() }} 次 · {{ formatTokens(Number(m.totalTokens)) }} tokens · 平均 {{ m.avgDuration ? (Number(m.avgDuration) / 1000).toFixed(1) + 's' : '-' }}
              </span>
            </div>
            <div class="model-row-charts">
              <div class="mini-chart-card">
                <div class="mini-chart-title">
                  <span>调用次数</span>
                  <span class="mini-chart-value">{{ Number(m.callCount).toLocaleString() }}</span>
                </div>
                <div :ref="el => setModelCallsRef(m.modelName, el)" class="mini-chart-canvas" />
              </div>
              <div class="mini-chart-card">
                <div class="mini-chart-title">
                  <span>Tokens</span>
                  <span class="mini-chart-value">{{ formatTokens(Number(m.totalTokens)) }}</span>
                </div>
                <div :ref="el => setModelTokensRef(m.modelName, el)" class="mini-chart-canvas" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑模型' : '新增模型'"
      width="560px"
      @closed="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="90px"
      >
        <el-form-item label="供应商" prop="provider">
          <el-select
            v-model="form.provider"
            placeholder="请选择供应商"
            style="width: 100%"
            :disabled="isEdit"
            @change="handleProviderChange"
          >
            <el-option
              v-for="p in providers"
              :key="p.key"
              :label="p.label"
              :value="p.key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模型名称" prop="modelName">
          <el-input v-model="form.modelName" placeholder="API 调用名，如 deepseek-chat / qwen-plus / llama3" />
        </el-form-item>
        <el-form-item label="显示名称" prop="displayName">
          <el-input v-model="form.displayName" placeholder="前端下拉展示名，留空则同模型名称" />
        </el-form-item>
        <el-form-item label="接口地址" prop="baseUrl">
          <el-input v-model="form.baseUrl" placeholder="供应商 OpenAI 兼容 API 地址" />
        </el-form-item>
        <el-form-item label="API Key" prop="apiKey">
          <el-input
            v-model="form.apiKey"
            type="password"
            show-password
            :placeholder="apiKeyPlaceholder"
          />
          <div v-if="isEdit && editRowHasKey" class="form-tip">留空表示保持原 Key 不变</div>
        </el-form-item>
        <el-form-item label="推理模型">
          <el-switch v-model="form.isReasoner" active-text="思维链" />
          <span class="switch-desc">推理模型会输出思考过程，耗时更长</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
          <span class="switch-desc">关闭后问答与抽取中不可选</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Refresh, Cpu, DataLine } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { llmModelApi, type LlmProvider, type LlmModelManageRow, type LlmUsageData } from '@/api'

const loading = ref(false)
const rows = ref<(LlmModelManageRow & { _toggling?: boolean })[]>([])
const providers = ref<LlmProvider[]>([])
const providerFilter = ref('')

// 用量统计
const usageDays = ref(7)
const usage = ref<LlmUsageData>({ totalCalls: 0, totalTokens: 0, daily: [], byModel: [] })
const callsChartRef = ref<HTMLElement>()
const tokensChartRef = ref<HTMLElement>()
let callsChart: echarts.ECharts | null = null
let tokensChart: echarts.ECharts | null = null
const modelCallsEls = new Map<string, HTMLElement>()
const modelTokensEls = new Map<string, HTMLElement>()
const modelCallsCharts = new Map<string, echarts.ECharts>()
const modelTokensCharts = new Map<string, echarts.ECharts>()

function setModelCallsRef(name: string, el: Element | null) {
  if (el) modelCallsEls.set(name, el as HTMLElement)
}
function setModelTokensRef(name: string, el: Element | null) {
  if (el) modelTokensEls.set(name, el as HTMLElement)
}

const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number>(0)
const editRowHasKey = ref(false)

const form = reactive({
  provider: '',
  modelName: '',
  displayName: '',
  baseUrl: '',
  apiKey: '',
  isReasoner: false,
  enabled: true
})

const currentProvider = computed(
  () => providers.value.find(p => p.key === form.provider)
)

const apiKeyPlaceholder = computed(() => {
  if (!currentProvider.value) return 'API 密钥'
  return currentProvider.value.apiKeyRequired ? '请输入 API Key' : '无需密钥，可留空'
})

const filteredRows = computed(() =>
  providerFilter.value ? rows.value.filter(r => r.provider === providerFilter.value) : rows.value
)

/** 动态校验：需要 key 的供应商创建时必填 */
const validateApiKey = (_rule: any, value: string, callback: (err?: Error) => void) => {
  if (isEdit.value) {
    callback() // 编辑时留空 = 保持不变
    return
  }
  if (currentProvider.value?.apiKeyRequired && !value?.trim()) {
    callback(new Error(`${currentProvider.value.label} 需要填写 API Key`))
    return
  }
  callback()
}

const rules: FormRules = {
  provider: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  modelName: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  baseUrl: [{ required: true, message: '请输入接口地址', trigger: 'blur' }],
  apiKey: [{ validator: validateApiKey, trigger: 'blur' }]
}

function providerLabel(key: string) {
  return providers.value.find(p => p.key === key)?.label || key
}

function providerTagType(key: string): 'primary' | 'success' | 'warning' | 'info' {
  switch (key) {
    case 'deepseek': return 'primary'
    case 'qwen': return 'success'
    case 'openai': return 'warning'
    case 'ollama': return 'info'
    default: return 'info'
  }
}

async function loadProviders() {
  try {
    providers.value = await llmModelApi.providers()
  } catch (e: any) {
    ElMessage.error(e?.message || '供应商预设加载失败')
  }
}

async function loadList() {
  loading.value = true
  try {
    rows.value = (await llmModelApi.list()) || []
  } catch (e: any) {
    ElMessage.error(e?.message || '模型列表加载失败')
  } finally {
    loading.value = false
  }
}

/** 选择供应商后自动填充预设接口地址 */
function handleProviderChange(key: string) {
  const preset = providers.value.find(p => p.key === key)
  if (preset?.baseUrl && !form.baseUrl) {
    form.baseUrl = preset.baseUrl
  }
  formRef.value?.clearValidate('apiKey')
}

function openAdd() {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: LlmModelManageRow) {
  isEdit.value = true
  resetForm()
  editingId.value = row.id
  editRowHasKey.value = row.hasKey
  form.provider = row.provider
  form.modelName = row.modelName
  form.displayName = row.displayName
  form.baseUrl = row.baseUrl
  form.isReasoner = row.isReasoner
  form.enabled = row.enabled
  dialogVisible.value = true
}

function resetForm() {
  form.provider = ''
  form.modelName = ''
  form.displayName = ''
  form.baseUrl = ''
  form.apiKey = ''
  form.isReasoner = false
  form.enabled = true
  editingId.value = 0
  editRowHasKey.value = false
  formRef.value?.clearValidate()
}

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    const payload = {
      provider: form.provider,
      modelName: form.modelName.trim(),
      displayName: form.displayName.trim() || form.modelName.trim(),
      baseUrl: form.baseUrl.trim(),
      apiKey: form.apiKey.trim(),
      isReasoner: form.isReasoner,
      enabled: form.enabled
    }
    if (isEdit.value) {
      await llmModelApi.update(editingId.value, payload)
      ElMessage.success('模型已更新')
    } else {
      await llmModelApi.create(payload)
      ElMessage.success('模型已添加')
    }
    dialogVisible.value = false
    loadList()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

/** 启用状态快速切换（仅自己的模型） */
async function handleToggle(row: LlmModelManageRow & { _toggling?: boolean }, enabled: boolean) {
  row._toggling = true
  try {
    await llmModelApi.update(row.id, {
      provider: row.provider,
      modelName: row.modelName,
      displayName: row.displayName,
      baseUrl: row.baseUrl,
      apiKey: '', // 留空保持不变
      isReasoner: row.isReasoner,
      enabled
    })
    row.enabled = enabled
    ElMessage.success(enabled ? '已启用' : '已停用')
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  } finally {
    row._toggling = false
  }
}

async function handleDelete(row: LlmModelManageRow) {
  try {
    await ElMessageBox.confirm(
      `确定删除模型「${row.displayName}」？删除后问答与抽取中将不可再选择该模型。`,
      '提示',
      { type: 'warning' }
    )
    await llmModelApi.remove(row.id)
    ElMessage.success('删除成功')
    loadList()
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e?.message || '删除失败')
    }
  }
}

/** 加载用量统计 */
async function loadUsage() {
  try {
    usage.value = await llmModelApi.usage(usageDays.value)
    await nextTick()
    // 等待一帧确保布局计算完成，避免 ECharts 初始化时容器尺寸为 0
    requestAnimationFrame(() => {
      renderCallsChart()
      renderTokensChart()
      renderModelCharts()
    })
  } catch (e: any) {
    console.warn('[KGraph] 用量统计加载失败:', e)
  }
}

/** 窗口缩放时重绘所有图表 */
function handleResize() {
  callsChart?.resize()
  tokensChart?.resize()
  modelCallsCharts.forEach(c => c.resize())
  modelTokensCharts.forEach(c => c.resize())
}

onMounted(() => {
  loadProviders()
  loadList()
  loadUsage()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  callsChart?.dispose()
  tokensChart?.dispose()
  modelCallsCharts.forEach(c => c.dispose())
  modelTokensCharts.forEach(c => c.dispose())
})

/** Token 格式化：万/亿 */
function formatTokens(n: number): string {
  if (n >= 1e8) return (n / 1e8).toFixed(2) + ' 亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + ' 万'
  return n.toLocaleString()
}

/** Y 轴标签格式化（K/M） */
function formatAxisValue(v: number): string {
  if (v >= 1e6) return (v / 1e6).toFixed(0) + 'M'
  if (v >= 1e3) return (v / 1e3).toFixed(0) + 'K'
  return String(v)
}

/** 通用坐标轴样式 */
function baseAxisOpts(dates: string[]) {
  return {
    grid: { left: 40, right: 16, top: 16, bottom: 30 },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: '#e4e7ed' } },
      axisTick: { show: false },
      axisLabel: { color: '#909399', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#909399', fontSize: 11, formatter: (v: number) => formatAxisValue(v) },
      splitLine: { lineStyle: { color: '#f0f2f5', type: 'dashed' } },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.96)',
      borderColor: '#e4e7ed',
      borderWidth: 1,
      textStyle: { color: '#303133', fontSize: 12 },
      padding: [8, 12],
      extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,0.12); border-radius: 10px;',
    },
  }
}

/** API 请求次数 —— 平滑面积折线图（浅蓝渐变填充） */
function renderCallsChart() {
  if (!callsChartRef.value) return
  if (!callsChart) callsChart = echarts.init(callsChartRef.value)
  const data = usage.value.daily || []
  const dates = data.map(d => String(d.date).slice(5))
  const calls = data.map(d => d.callCount)
  callsChart.setOption({
    ...baseAxisOpts(dates),
    series: [
      {
        type: 'line',
        data: calls,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: false,
        lineStyle: { color: '#4a90d9', width: 2 },
        itemStyle: { color: '#4a90d9' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(74,144,217,0.35)' },
            { offset: 1, color: 'rgba(74,144,217,0.02)' },
          ]),
        },
        emphasis: { focus: 'series' },
      },
    ],
  })
  callsChart.resize()
}

/** Tokens —— 双色堆叠柱状图（深蓝底 + 浅蓝顶） */
function renderTokensChart() {
  if (!tokensChartRef.value) return
  if (!tokensChart) tokensChart = echarts.init(tokensChartRef.value)
  const data = usage.value.daily || []
  const dates = data.map(d => String(d.date).slice(5))
  const tokens = data.map(d => d.totalTokens)
  // 拆成两段模拟双色堆叠：底部 65% 深蓝，顶部 35% 浅蓝
  const bottom = tokens.map(v => Math.round(v * 0.65))
  const top = tokens.map((v, i) => v - bottom[i])
  tokensChart.setOption({
    ...baseAxisOpts(dates),
    series: [
      {
        type: 'bar',
        data: bottom,
        barWidth: '45%',
        stack: 'tokens',
        itemStyle: { color: '#4a90d9', borderRadius: [0, 0, 0, 0] },
        emphasis: { focus: 'series' },
      },
      {
        type: 'bar',
        data: top,
        barWidth: '45%',
        stack: 'tokens',
        itemStyle: { color: '#9ec5ef', borderRadius: [3, 3, 0, 0] },
        emphasis: { focus: 'series' },
      },
    ],
  })
  tokensChart.resize()
}

/** 各模型 mini 图表：每个模型一行，左折线（调用次数）+ 右柱状（Tokens） */
function renderModelCharts() {
  const models = usage.value.byModel || []
  const data = usage.value.daily || []
  const dates = data.map(d => String(d.date).slice(5))
  // 清理旧图表
  modelCallsCharts.forEach(c => c.dispose())
  modelTokensCharts.forEach(c => c.dispose())
  modelCallsCharts.clear()
  modelTokensCharts.clear()

  models.forEach(m => {
    const callsEl = modelCallsEls.get(m.modelName)
    const tokensEl = modelTokensEls.get(m.modelName)
    const callsVal = Number(m.callCount)
    const tokensVal = Number(m.totalTokens)

    if (callsEl) {
      const c = echarts.init(callsEl)
      c.setOption({
        ...baseAxisOpts(dates),
        series: [{
          type: 'line',
          data: data.map(() => 0),
          smooth: true,
          showSymbol: false,
          lineStyle: { color: '#4a90d9', width: 1.5 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(74,144,217,0.3)' },
              { offset: 1, color: 'rgba(74,144,217,0.02)' },
            ]),
          },
        }],
      })
      modelCallsCharts.set(m.modelName, c)
      c.resize()
    }
    if (tokensEl) {
      const c = echarts.init(tokensEl)
      const bottom = Math.round(tokensVal * 0.65)
      const top = tokensVal - bottom
      c.setOption({
        ...baseAxisOpts(dates),
        series: [
          { type: 'bar', data: dates.map(() => bottom), barWidth: '45%', stack: 't', itemStyle: { color: '#4a90d9' } },
          { type: 'bar', data: dates.map(() => top), barWidth: '45%', stack: 't', itemStyle: { color: '#9ec5ef', borderRadius: [3, 3, 0, 0] } },
        ],
      })
      modelTokensCharts.set(m.modelName, c)
      c.resize()
    }
  })
}
</script>

<style scoped>
.toolbar {
  padding: 16px 20px;
  margin: 0;
  border-bottom: 1px solid var(--border-2);
  background: #fbfcfd;
  border-radius: var(--r-lg) var(--r-lg) 0 0;
}

.toolbar-left {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.toolbar-right {
  display: flex;
  gap: 8px;
  align-items: center;
}

.provider-select {
  width: 220px;
}

.table-wrap {
  padding: 4px 12px 8px;
}

/* 模型单元格 */
.cell-model {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 0;
}

.model-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-id {
  font-size: 12px;
  color: var(--text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mono-text {
  font-size: 12px;
  color: var(--text-2);
  font-family: 'SF Mono', Menlo, Consolas, monospace;
}

.no-key {
  font-size: 12px;
  color: var(--text-3);
}

.plain-text {
  font-size: 12px;
  color: var(--text-3);
}

.form-tip {
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.6;
  margin-top: 2px;
}

.switch-desc {
  font-size: 12px;
  color: var(--text-3);
  margin-left: 10px;
}

/* 空态 */
.empty-state {
  padding: 64px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.empty-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-2);
  margin-top: 8px;
}

.empty-desc {
  font-size: 12px;
  color: var(--text-3);
}

/* 用量监控 */
.usage-card {
  margin-top: 16px;
}

.usage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-2);
}

.usage-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-1);
}

.usage-title .el-icon {
  color: #409eff;
}

.usage-summary {
  display: flex;
  align-items: center;
  padding: 20px 20px 16px;
  gap: 24px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-label {
  font-size: 12px;
  color: var(--text-3);
}

.summary-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-1);
  line-height: 1.2;
}

.summary-unit {
  font-size: 12px;
  color: var(--text-3);
}

.summary-divider {
  width: 1px;
  height: 36px;
  background: var(--border-2);
}

.usage-charts {
  display: flex;
  gap: 16px;
  padding: 0 20px 20px;
}

.chart-card {
  flex: 1;
  min-width: 0;
  background: #f7f9fc;
  border-radius: 14px;
  padding: 16px 18px 8px;
}

.chart-card-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.chart-card-title > span:first-child {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.chart-card-value {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
}

.chart-canvas {
  width: 100%;
  height: 260px;
}

/* 各模型明细：每个模型一行，行内左折线+右柱状 */
.usage-models {
  padding: 0 20px 20px;
}

.usage-models-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 12px;
}

.model-rows {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.model-row {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.model-row-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 0 4px;
}

.model-row-name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.model-row-stats {
  font-size: 12px;
  color: #6b7280;
}

.model-row-charts {
  display: flex;
  gap: 16px;
}

.mini-chart-card {
  flex: 1;
  min-width: 0;
  background: #f7f9fc;
  border-radius: 14px;
  padding: 16px 18px 8px;
}

.mini-chart-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.mini-chart-title > span:first-child {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.mini-chart-value {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
}

.mini-chart-canvas {
  width: 100%;
  height: 180px;
}

@media (max-width: 900px) {
  .usage-charts {
    flex-direction: column;
  }
  .model-row-charts {
    flex-direction: column;
  }
}
</style>
