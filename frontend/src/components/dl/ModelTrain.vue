<template>
  <div class="model-train">
    <!-- 顶部：训练任务横向列表 -->
    <el-card shadow="never" class="task-bar-card">
      <div class="task-bar-header">
        <span class="bar-title">
          <el-icon><List /></el-icon>
          训练任务（{{ trainTasks.length }}）
        </span>
        <el-button type="primary" size="small" :icon="Plus" @click="openCreateDialog">新建训练</el-button>
      </div>
      <div v-if="trainTasks.length === 0" class="empty-mini">
        <el-empty description="暂无训练任务，点击右上角「新建训练」开始" :image-size="60" />
      </div>
      <div v-else class="task-bar-scroll">
        <div
          v-for="t in trainTasks"
          :key="t.id"
          class="task-chip"
          :class="{ active: currentTaskId === t.id }"
          @click="selectTask(t.id)"
        >
          <div class="chip-head">
            <span class="chip-name">{{ t.taskName }}</span>
            <el-tag :type="statusTagType(t.status)" size="small" effect="light">{{ statusText(t.status) }}</el-tag>
          </div>
          <div class="chip-meta">
            <span class="chip-arch">{{ t.architecture }}</span>
            <span class="chip-sep">·</span>
            <span>v{{ t.version }}</span>
          </div>
          <div v-if="t.status === 'training'" class="chip-progress">
            <el-progress :percentage="t.progress" :stroke-width="4" :show-text="false" />
            <span class="chip-progress-text">{{ t.currentEpoch }}/{{ t.epochs }} · {{ t.progress }}%</span>
          </div>
          <div v-else-if="t.metrics" class="chip-metrics">
            <span class="chip-f1">F1 {{ t.metrics.f1 }}</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 中间：训练配置 -->
    <el-card v-if="currentTask" shadow="never" class="config-card">
      <template #header>
        <div class="card-header">
          <span class="header-title">
            <el-icon><Setting /></el-icon>
            训练配置 · {{ currentTask.taskName }}
          </span>
          <div class="header-actions">
            <el-button
              v-if="currentTask.status === 'training'"
              type="danger"
              size="small"
              :icon="VideoPause"
              @click="stopTraining"
            >
              停止训练
            </el-button>
            <el-button
              v-else
              type="success"
              size="small"
              :icon="VideoPlay"
              :loading="creating"
              @click="startTraining"
            >
              {{ creating ? '训练中...' : (currentTask.status === 'pending' ? '启动训练' : '重新训练') }}
            </el-button>
          </div>
        </div>
      </template>

      <el-form :model="currentTask.config" label-width="100px" :disabled="currentTask.status === 'training'" class="train-form">
        <el-row :gutter="16">
          <el-col :span="6">
            <el-form-item label="训练数据集">
              <el-input v-model="currentTask.config.dataset" size="default" readonly placeholder="来自关联标注任务" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="模型架构">
              <el-select v-model="currentTask.config.architecture" style="width: 100%">
                <el-option label="BiLSTM-CRF" value="BiLSTM-CRF" />
                <el-option label="BERT-CRF" value="BERT-CRF" />
                <el-option label="SPAN-BERT" value="SPAN-BERT" />
                <el-option label="BERT-RE" value="BERT-RE" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="学习率">
              <el-input-number v-model="currentTask.config.learningRate" :min="0.00001" :max="1" :step="0.0001" :precision="5" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="Epoch 轮数">
              <el-input-number v-model="currentTask.config.epochs" :min="1" :max="200" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="6">
            <el-form-item label="Batch Size">
              <el-input-number v-model="currentTask.config.batchSize" :min="1" :max="256" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="嵌入维度">
              <el-select v-model="currentTask.config.embeddingDim" style="width: 100%">
                <el-option label="32 维" :value="32" />
                <el-option label="64 维" :value="64" />
                <el-option label="128 维" :value="128" />
                <el-option label="768 维（BERT）" :value="768" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="隐藏层维度">
              <el-input-number v-model="currentTask.config.hiddenDim" :min="16" :max="1024" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="Dropout">
              <el-input-number v-model="currentTask.config.dropout" :min="0" :max="0.9" :step="0.05" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="6">
            <el-form-item label="优化器">
              <el-select v-model="currentTask.config.optimizer" style="width: 100%">
                <el-option label="Adam" value="Adam" />
                <el-option label="SGD" value="SGD" />
                <el-option label="AdamW" value="AdamW" />
                <el-option label="RMSprop" value="RMSprop" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="验证集比例">
              <el-input-number v-model="currentTask.config.validationSplit" :min="0" :max="0.5" :step="0.05" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="梯度裁剪">
              <el-input-number v-model="currentTask.config.gradClip" :min="0" :max="10" :step="0.5" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="随机种子">
              <el-input-number v-model="currentTask.config.randomSeed" :min="0" :max="99999" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 底部：训练监控（日志 → 曲线 → 指标） -->
    <div v-if="currentTask && (currentTask.status === 'training' || currentTask.status === 'done')" class="monitor-section">
      <!-- 训练日志 -->
      <el-card shadow="never" class="log-card">
        <template #header>
          <div class="card-header">
            <span class="header-title">
              <el-icon><Document /></el-icon>
              训练日志（{{ trainLogs.length }}）
            </span>
            <el-button size="small" link :icon="Delete" @click="trainLogs = []">清空</el-button>
          </div>
        </template>
        <div class="log-content" ref="logContentRef">
          <div v-if="trainLogs.length === 0" class="log-empty">暂无日志</div>
          <div v-for="(log, i) in trainLogs" :key="i" class="log-line" :class="log.type">
            <span class="log-time">{{ log.time }}</span>
            <span class="log-level" :class="log.type">{{ levelText(log.type) }}</span>
            <span class="log-msg">{{ log.msg }}</span>
          </div>
        </div>
      </el-card>

      <!-- 指标切换 -->
      <div class="chart-switch-bar">
        <span class="switch-label">训练曲线：</span>
        <el-radio-group v-model="chartMetric" size="small">
          <el-radio-button label="all">全部指标</el-radio-button>
          <el-radio-button label="loss">仅 Loss</el-radio-button>
          <el-radio-button label="prf">仅 P/R/F1</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 训练曲线：左右分栏，Loss 独立 + P/R/F1 独立，避免双 Y 轴混乱 -->
      <el-row :gutter="12" class="chart-row">
        <el-col :span="chartMetric === 'all' ? 10 : 24">
          <el-card v-show="chartMetric === 'all' || chartMetric === 'loss'" shadow="never" class="chart-card">
            <template #header>
              <div class="card-header">
                <span class="header-title">
                  <el-icon><TrendCharts /></el-icon>
                  Loss 变化曲线
                </span>
                <el-tag type="danger" effect="plain" size="small">越小越好</el-tag>
              </div>
            </template>
            <div ref="lossChartRef" class="train-chart"></div>
          </el-card>
        </el-col>
        <el-col :span="chartMetric === 'all' ? 14 : 24">
          <el-card v-show="chartMetric === 'all' || chartMetric === 'prf'" shadow="never" class="chart-card">
            <template #header>
              <div class="card-header">
                <span class="header-title">
                  <el-icon><TrendCharts /></el-icon>
                  Precision / Recall / F1 曲线
                </span>
                <el-tag type="success" effect="plain" size="small">越大越好</el-tag>
              </div>
            </template>
            <div ref="prfChartRef" class="train-chart"></div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 指标卡 -->
      <el-row :gutter="12" class="metric-row">
        <el-col :span="6">
          <el-card shadow="never" class="metric-card loss-card">
            <div class="metric-card-body">
              <div class="metric-label">当前 Loss</div>
              <div class="metric-value">{{ formatNum(currentTask.metrics?.loss) }}</div>
              <div class="metric-trend">
                <el-icon><Bottom /></el-icon>
                <span>持续下降</span>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="metric-card p-card">
            <div class="metric-card-body">
              <div class="metric-label">Precision 精确率</div>
              <div class="metric-value">{{ formatPercent(currentTask.metrics?.precision) }}</div>
              <div class="metric-trend">
                <el-icon><Top /></el-icon>
                <span>稳步提升</span>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="metric-card r-card">
            <div class="metric-card-body">
              <div class="metric-label">Recall 召回率</div>
              <div class="metric-value">{{ formatPercent(currentTask.metrics?.recall) }}</div>
              <div class="metric-trend">
                <el-icon><Top /></el-icon>
                <span>稳步提升</span>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="metric-card f1-card">
            <div class="metric-card-body">
              <div class="metric-label">F1 Score 综合指标</div>
              <div class="metric-value">{{ formatPercent(currentTask.metrics?.f1) }}</div>
              <div class="metric-trend">
                <el-icon><Top /></el-icon>
                <span>表现优异</span>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 未选择任务占位 -->
    <el-card v-if="!currentTask && trainTasks.length > 0" shadow="never" class="empty-config">
      <el-empty description="请从上方选择一个训练任务" :image-size="80" />
    </el-card>

    <!-- 新建训练任务弹窗 -->
    <el-dialog v-model="createDialogVisible" title="新建训练任务" width="520px">
      <el-form :model="newTask" label-width="100px">
        <el-form-item label="任务名称">
          <el-input v-model="newTask.taskName" placeholder="如：BiLSTM-CRF 人物关系训练" />
        </el-form-item>
        <el-form-item label="标注任务">
          <div class="dataset-pick">
            <el-select v-model="newTask.annotationTaskId" style="flex: 1" placeholder="选择标注任务作为训练数据集">
              <el-option v-for="o in annotationOptions" :key="o.id" :label="o.label" :value="o.id" />
            </el-select>
            <el-button :icon="Refresh" circle size="small" @click="loadAnnotationDatasets" title="刷新标注任务" />
          </div>
        </el-form-item>
        <el-form-item label="模型架构">
          <el-select v-model="newTask.architecture" style="width: 100%">
            <el-option label="BiLSTM-CRF（双向 LSTM + CRF）" value="BiLSTM-CRF" />
            <el-option label="BERT-CRF（BERT + CRF）" value="BERT-CRF" />
            <el-option label="SPAN-BERT（SpanBERT 抽取）" value="SPAN-BERT" />
            <el-option label="BERT-RE（BERT 关系抽取）" value="BERT-RE" />
          </el-select>
        </el-form-item>
        <el-form-item label="Epoch 轮数">
          <el-input-number v-model="newTask.epochs" :min="1" :max="200" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false" :disabled="creating">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createTask">{{ creating ? '训练中...' : '创建并训练' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Bottom, Delete, Document, List, Plus, Refresh, Setting, Top, TrendCharts, VideoPause, VideoPlay } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { annotationTaskApi, trainTaskApi } from '@/api'

interface TrainConfig {
  dataset: string
  architecture: string
  learningRate: number
  epochs: number
  batchSize: number
  embeddingDim: number
  hiddenDim: number
  dropout: number
  optimizer: string
  validationSplit: number
  gradClip: number
  randomSeed: number
}
interface TrainMetrics {
  loss: number
  precision: number
  recall: number
  f1: number
}
interface TrainTask {
  id: number
  taskName: string
  dataset: string
  architecture: string
  version: string
  status: 'pending' | 'training' | 'done' | 'failed'
  progress: number
  currentEpoch: number
  epochs: number
  config: TrainConfig
  metrics?: TrainMetrics
  history: { epoch: number; loss: number; precision: number; recall: number; f1: number }[]
  createdAt: string
  // 关联字段（数据库扩展）
  projectId?: number | string
  annotationTaskId?: number | string
}
interface LogLine {
  time: string
  msg: string
  type: 'info' | 'success' | 'warning' | 'error'
}

// ============ 标注任务列表（作为训练数据集来源） ============
interface AnnotationTaskInfo {
  id: number | string
  taskName: string
  projectId: number | string
  corpusTitle?: string
  entities?: string
  relations?: string
}
const annotationTasks = ref<AnnotationTaskInfo[]>([])

function parseJsonLen(raw: any): number {
  if (!raw) return 0
  if (Array.isArray(raw)) return raw.length
  if (typeof raw === 'string') {
    try {
      const p = JSON.parse(raw)
      return Array.isArray(p) ? p.length : 0
    } catch {
      return 0
    }
  }
  return 0
}

async function loadAnnotationDatasets() {
  try {
    const res = await annotationTaskApi.list({ pageNum: 1, pageSize: 100 })
    const records = res.data?.records || res.data || []
    // 过滤掉示例占位任务（id = -1）
    annotationTasks.value = (records as AnnotationTaskInfo[]).filter(t => Number(t.id) > 0)
  } catch (e) {
    annotationTasks.value = []
  }
}

// 标注任务下拉选项（显示任务名 + 实体/关系数）
const annotationOptions = computed(() => annotationTasks.value.map(t => {
  const eCount = parseJsonLen(t.entities)
  const rCount = parseJsonLen(t.relations)
  return {
    id: t.id,
    label: `${t.taskName}（${eCount}实体/${rCount}关系）`,
    taskName: t.taskName,
  }
}))

const trainTasks = ref<TrainTask[]>([])
const currentTaskId = ref<number>()
const currentTask = computed(() => trainTasks.value.find(t => t.id === currentTaskId.value))
const trainLogs = ref<LogLine[]>([])
const lossChartRef = ref<HTMLElement>()
const prfChartRef = ref<HTMLElement>()
const logContentRef = ref<HTMLElement>()
const chartMetric = ref<'all' | 'loss' | 'prf'>('all')
let lossChart: echarts.ECharts | null = null
let prfChart: echarts.ECharts | null = null

function statusText(s: string): string {
  return { pending: '待训练', training: '训练中', done: '已完成', failed: '失败' }[s] || s
}
function statusTagType(s: string): string {
  return { pending: 'info', training: 'warning', done: 'success', failed: 'danger' }[s] || 'info'
}
function levelText(t: string): string {
  return { info: 'INFO', success: 'OK', warning: 'WARN', error: 'ERR' }[t] || 'INFO'
}
function formatNum(v?: number): string {
  if (v === undefined || v === null) return '-'
  return v.toFixed(4)
}
function formatPercent(v?: number): string {
  if (v === undefined || v === null) return '-'
  return (v * 100).toFixed(2) + '%'
}

// ============ 持久化：通过后端 API，不再使用 localStorage ============

function selectTask(id: number) {
  currentTaskId.value = id
  trainLogs.value = []
  nextTick(() => renderChart())
}

// ============ 新建任务 ============
const createDialogVisible = ref(false)
const creating = ref(false)
const newTask = reactive({
  taskName: '',
  annotationTaskId: undefined as (number | string) | undefined,
  architecture: 'BiLSTM-CRF',
  epochs: 20,
})

function openCreateDialog() {
  loadAnnotationDatasets()
  newTask.taskName = ''
  newTask.annotationTaskId = annotationOptions.value[0]?.id
  newTask.architecture = 'BiLSTM-CRF'
  newTask.epochs = 20
  createDialogVisible.value = true
}

// 解析后端返回的训练任务（history/metrics/config 为 JSON 字符串）
function parseTrainTask(raw: any): TrainTask {
  const configRaw = raw.config
  let config: TrainConfig
  if (typeof configRaw === 'string') {
    try { config = JSON.parse(configRaw) } catch { config = defaultConfig(raw) }
  } else if (configRaw && typeof configRaw === 'object') {
    config = { ...defaultConfig(raw), ...configRaw }
  } else {
    config = defaultConfig(raw)
  }
  let history: any[] = []
  if (typeof raw.history === 'string') {
    try { history = JSON.parse(raw.history) } catch { history = [] }
  } else if (Array.isArray(raw.history)) {
    history = raw.history
  }
  let metrics: TrainMetrics | undefined
  if (typeof raw.metrics === 'string') {
    try { metrics = JSON.parse(raw.metrics) } catch { metrics = undefined }
  } else if (raw.metrics && typeof raw.metrics === 'object') {
    metrics = raw.metrics
  }
  return {
    id: raw.id,
    taskName: raw.taskName,
    dataset: raw.dataset || config.dataset || '-',
    architecture: raw.architecture,
    version: raw.version,
    status: raw.status,
    progress: raw.progress ?? 0,
    currentEpoch: raw.currentEpoch ?? 0,
    epochs: raw.epochs ?? config.epochs ?? 20,
    config,
    metrics,
    history,
    createdAt: raw.createTime || new Date().toISOString(),
    projectId: raw.projectId,
    annotationTaskId: raw.annotationTaskId,
  }
}

function defaultConfig(raw: any): TrainConfig {
  return {
    dataset: raw.dataset || '-',
    architecture: raw.architecture || 'BiLSTM-CRF',
    learningRate: 0.001,
    epochs: raw.epochs || 20,
    batchSize: 32,
    embeddingDim: (raw.architecture || '').startsWith('BERT') ? 768 : 64,
    hiddenDim: 128,
    dropout: 0.3,
    optimizer: 'Adam',
    validationSplit: 0.2,
    gradClip: 5.0,
    randomSeed: 42,
  }
}

// 创建训练任务：调用后端 add 接口（同步训练，返回完整结果）
async function createTask() {
  if (!newTask.taskName) {
    ElMessage.warning('请填写任务名称')
    return
  }
  if (!newTask.annotationTaskId) {
    ElMessage.warning('请选择标注任务作为训练数据集')
    return
  }
  const annoTask = annotationTasks.value.find(t => t.id === newTask.annotationTaskId)
  creating.value = true
  try {
    const res = await trainTaskApi.add({
      taskName: newTask.taskName,
      projectId: annoTask?.projectId as number,
      annotationTaskId: newTask.annotationTaskId,
      dataset: annoTask?.taskName,
      architecture: newTask.architecture,
      epochs: newTask.epochs,
    })
    const saved = parseTrainTask(res.data)
    trainTasks.value.unshift(saved)
    currentTaskId.value = saved.id
    // 基于完整 history 生成训练日志
    buildLogsFromHistory(saved)
    createDialogVisible.value = false
    ElMessage.success(`训练完成！模型已保存为 v${saved.version}`)
    // 多次延迟渲染确保图表显示
    nextTick(() => { renderChart(); lossChart?.resize(); prfChart?.resize() })
    setTimeout(() => { renderChart(); lossChart?.resize(); prfChart?.resize() }, 200)
    setTimeout(() => { renderChart(); lossChart?.resize(); prfChart?.resize() }, 500)
  } catch (e: any) {
    ElMessage.error('训练任务创建失败：' + (e?.message || ''))
  } finally {
    creating.value = false
  }
}

// 基于完整 history 生成训练日志（保留训练过程的视觉感）
function buildLogsFromHistory(task: TrainTask) {
  trainLogs.value = []
  appendLog('info', `训练任务「${task.taskName}」已启动`)
  appendLog('info', `模型架构：${task.config.architecture} | 数据集：${task.config.dataset}`)
  appendLog('info', `Epoch=${task.config.epochs} | LR=${task.config.learningRate} | Batch=${task.config.batchSize} | Optimizer=${task.config.optimizer}`)
  task.history.forEach(h => {
    appendLog(h.epoch % 5 === 0 || h.epoch === 1 ? 'success' : 'info',
      `Epoch ${h.epoch}/${task.config.epochs} - loss: ${h.loss} - precision: ${h.precision} - recall: ${h.recall} - f1: ${h.f1}`)
  })
  if (task.metrics) {
    appendLog('success', `训练完成！最终 F1=${task.metrics.f1}，模型已保存为 v${task.version}`)
  }
  scrollLogToBottom()
}

// ============ 重新训练（基于当前任务配置创建新训练） ============
async function startTraining() {
  if (!currentTask.value) return
  const task = currentTask.value
  if (!task.annotationTaskId) {
    ElMessage.warning('当前任务缺少关联标注任务，无法重新训练')
    return
  }
  creating.value = true
  try {
    const res = await trainTaskApi.add({
      taskName: task.taskName + '_重训',
      projectId: task.projectId as number,
      annotationTaskId: task.annotationTaskId,
      dataset: task.config.dataset,
      architecture: task.config.architecture,
      epochs: task.config.epochs,
    })
    const saved = parseTrainTask(res.data)
    trainTasks.value.unshift(saved)
    currentTaskId.value = saved.id
    buildLogsFromHistory(saved)
    ElMessage.success(`重新训练完成！模型已保存为 v${saved.version}`)
    nextTick(() => { renderChart(); lossChart?.resize(); prfChart?.resize() })
    setTimeout(() => { renderChart(); lossChart?.resize(); prfChart?.resize() }, 200)
    setTimeout(() => { renderChart(); lossChart?.resize(); prfChart?.resize() }, 500)
  } catch (e: any) {
    ElMessage.error('重新训练失败：' + (e?.message || ''))
  } finally {
    creating.value = false
  }
}

// 后端训练为同步调用，无法中途停止；保留按钮但仅作提示
function stopTraining() {
  ElMessage.info('后端训练为同步执行，已发起的训练请求无法中途停止')
}

function appendLog(type: LogLine['type'], msg: string) {
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  trainLogs.value.push({ time, msg, type })
  if (trainLogs.value.length > 300) trainLogs.value.shift()
}

function scrollLogToBottom() {
  nextTick(() => {
    if (logContentRef.value) {
      logContentRef.value.scrollTop = logContentRef.value.scrollHeight
    }
  })
}

// ============ 图表 ============
function renderChart() {
  renderLossChart()
  renderPrfChart()
}

function renderLossChart() {
  if (!lossChartRef.value || !currentTask.value) return
  // dispose + re-init，避免容器尺寸变化导致渲染异常
  if (lossChart) {
    lossChart.dispose()
    lossChart = null
  }
  lossChart = echarts.init(lossChartRef.value)
  const history = currentTask.value.history
  if (history.length === 0) {
    lossChart.clear()
    return
  }

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: '#fde2e2',
      textStyle: { color: '#1d2129', fontSize: 12 },
      valueFormatter: (v: any) => Number(v).toFixed(4),
    },
    // top 留出 yAxis name 空间，right 留出 markLine label 空间
    grid: { top: 40, left: 60, right: 80, bottom: 60, containLabel: true },
    xAxis: {
      type: 'category',
      name: 'Epoch',
      nameLocation: 'middle',
      nameGap: 36,
      data: history.map(h => h.epoch),
      axisLine: { lineStyle: { color: '#c9cdd4' } },
      axisLabel: { color: '#86909c', interval: 0, rotate: history.length > 8 ? 35 : 0 },
    },
    yAxis: {
      type: 'value',
      name: 'Loss',
      nameLocation: 'end',
      nameGap: 12,
      nameTextStyle: { color: '#f56c6c', fontSize: 12, align: 'left', padding: [0, 0, 4, 0] },
      min: 0,
      axisLine: { lineStyle: { color: '#f56c6c' } },
      axisLabel: { color: '#f56c6c' },
      splitLine: { lineStyle: { type: 'dashed', color: '#ebeef5' } },
    },
    series: [{
      name: 'Loss',
      type: 'line',
      smooth: true,
      data: history.map(h => h.loss),
      itemStyle: { color: '#f56c6c' },
      lineStyle: { width: 2.5 },
      symbol: 'circle',
      symbolSize: 5,
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(245, 108, 108, 0.35)' },
          { offset: 1, color: 'rgba(245, 108, 108, 0.02)' },
        ]),
      },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', color: '#f56c6c', opacity: 0.5 },
        label: { show: false },
        data: [{ type: 'min', name: '最小值' }],
      },
      markPoint: {
        symbol: 'pin',
        symbolSize: 55,
        label: { formatter: '{c}', fontSize: 11, color: '#fff' },
        itemStyle: { color: '#f56c6c' },
        data: [{ type: 'min', name: '最小Loss' }],
      },
    }],
  }
  lossChart.setOption(option, true)
}

function renderPrfChart() {
  if (!prfChartRef.value || !currentTask.value) return
  // dispose + re-init，确保切换显示后图表正确渲染
  if (prfChart) {
    prfChart.dispose()
    prfChart = null
  }
  prfChart = echarts.init(prfChartRef.value)
  const history = currentTask.value.history
  if (history.length === 0) {
    prfChart.clear()
    return
  }

  const seriesConfig = [
    { name: 'Precision', key: 'precision', color: '#409eff' },
    { name: 'Recall', key: 'recall', color: '#e6a23c' },
    { name: 'F1', key: 'f1', color: '#67c23a' },
  ]

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: '#e5e6eb',
      textStyle: { color: '#1d2129', fontSize: 12 },
      valueFormatter: (v: any) => (Number(v) * 100).toFixed(2) + '%',
    },
    legend: {
      data: seriesConfig.map(s => s.name),
      top: 4,
      itemWidth: 14,
      itemHeight: 8,
      textStyle: { fontSize: 12, color: '#4e5969' },
    },
    grid: { top: 40, left: 70, right: 50, bottom: 60, containLabel: true },
    xAxis: {
      type: 'category',
      name: 'Epoch',
      nameLocation: 'middle',
      nameGap: 36,
      data: history.map(h => h.epoch),
      axisLine: { lineStyle: { color: '#c9cdd4' } },
      axisLabel: { color: '#86909c', interval: 0, rotate: history.length > 8 ? 35 : 0 },
    },
    yAxis: {
      type: 'value',
      name: 'P/R/F1',
      nameLocation: 'end',
      nameGap: 18,
      nameTextStyle: { color: '#409eff', fontSize: 12 },
      min: 0,
      max: 1,
      axisLine: { lineStyle: { color: '#409eff' } },
      axisLabel: { color: '#409eff', formatter: (v: number) => (v * 100).toFixed(0) + '%' },
      splitLine: { lineStyle: { type: 'dashed', color: '#ebeef5' } },
    },
    series: seriesConfig.map(s => ({
      name: s.name,
      type: 'line',
      smooth: true,
      data: history.map(h => h[s.key as keyof typeof h] as number),
      itemStyle: { color: s.color },
      lineStyle: { width: 2.5 },
      symbol: 'circle',
      symbolSize: 5,
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: s.color + '30' },
          { offset: 1, color: s.color + '02' },
        ]),
      },
    })),
  }
  prfChart.setOption(option, true)
}

// ============ 初始化：从后端加载训练任务列表 ============
async function loadTrainTasks() {
  try {
    const res = await trainTaskApi.list({ pageNum: 1, pageSize: 100 })
    const records = res.data?.records || res.data || []
    if (records.length === 0) return
    trainTasks.value = (records as any[]).map(parseTrainTask)
    currentTaskId.value = trainTasks.value[0].id
    buildLogsFromHistory(trainTasks.value[0])
  } catch (e) {
    // 接口异常时静默
  }
}

onMounted(async () => {
  await loadAnnotationDatasets()
  await loadTrainTasks()
  nextTick(() => renderChart())
  window.addEventListener('resize', handleResize)
})

watch(chartMetric, () => {
  nextTick(() => {
    renderChart()
    // 切换显示后需要重新 resize
    lossChart?.resize()
    prfChart?.resize()
  })
})

// 切换任务时重新渲染图表，确保已完成任务的曲线正确显示
watch(currentTaskId, () => {
  nextTick(() => {
    renderChart()
    lossChart?.resize()
    prfChart?.resize()
  })
})

// 任务状态变化时（如训练完成）重新渲染图表
watch(() => currentTask.value?.status, (newStatus) => {
  if (newStatus === 'done' || newStatus === 'training') {
    nextTick(() => {
      renderChart()
      lossChart?.resize()
      prfChart?.resize()
    })
  }
})

function handleResize() {
  lossChart?.resize()
  prfChart?.resize()
}

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  lossChart?.dispose()
  prfChart?.dispose()
})
</script>

<style scoped>
.model-train {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 任务横向列表 */
.task-bar-card {
  flex-shrink: 0;
}

.task-bar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.bar-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 14px;
  color: #1d2129;
}

.task-bar-scroll {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 6px;
}

.task-bar-scroll::-webkit-scrollbar {
  height: 6px;
}

.task-bar-scroll::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 3px;
}

.task-chip {
  flex-shrink: 0;
  width: 220px;
  padding: 10px 12px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}

.task-chip:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.12);
}

.task-chip.active {
  border-color: #409eff;
  background: linear-gradient(135deg, #ecf5ff 0%, #f0f9ff 100%);
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.2);
}

.chip-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.chip-name {
  font-weight: 600;
  font-size: 13px;
  color: #1d2129;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 140px;
}

.chip-meta {
  font-size: 11px;
  color: #86909c;
  display: flex;
  gap: 4px;
  align-items: center;
}

.chip-arch {
  color: #409eff;
}

.chip-sep {
  color: #c9cdd4;
}

.chip-progress {
  margin-top: 6px;
}

.chip-progress-text {
  font-size: 11px;
  color: #e6a23c;
  display: block;
  margin-top: 2px;
}

.chip-metrics {
  margin-top: 6px;
}

.chip-f1 {
  font-size: 12px;
  color: #67c23a;
  font-weight: 600;
}

/* 配置卡片 */
.config-card {
  flex-shrink: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 14px;
  color: #1d2129;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.train-form {
  padding-top: 4px;
}

.dataset-pick {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}

.empty-mini {
  padding: 16px 0;
}

.empty-config {
  padding: 40px 0;
}

/* 监控区 */
.monitor-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-row {
  margin-bottom: 0 !important;
}

.metric-card {
  border: none;
  border-left: 4px solid #409eff;
  border-radius: 8px;
  overflow: hidden;
}

.metric-card.loss-card { border-left-color: #f56c6c; }
.metric-card.p-card { border-left-color: #409eff; }
.metric-card.r-card { border-left-color: #e6a23c; }
.metric-card.f1-card { border-left-color: #67c23a; }

.metric-card :deep(.el-card__body) {
  padding: 0;
}

.metric-card-body {
  padding: 14px 16px;
  background: linear-gradient(135deg, #fafbfc 0%, #f7f8fa 100%);
}

.metric-label {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 6px;
}

.metric-value {
  font-size: 26px;
  font-weight: 700;
  color: #1d2129;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.loss-card .metric-value { color: #f56c6c; }
.p-card .metric-value { color: #409eff; }
.r-card .metric-value { color: #e6a23c; }
.f1-card .metric-value { color: #67c23a; }

.metric-trend {
  margin-top: 6px;
  font-size: 11px;
  color: #86909c;
  display: flex;
  align-items: center;
  gap: 3px;
}

.loss-card .metric-trend { color: #f56c6c; }
.p-card .metric-trend,
.r-card .metric-trend,
.f1-card .metric-trend { color: #67c23a; }

/* 图表 */
.chart-row {
  margin-bottom: 0 !important;
}

.chart-card {
  height: 100%;
}

.train-chart {
  width: 100%;
  height: 300px;
}

.chart-switch-bar {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}

.switch-label {
  font-size: 13px;
  color: #4e5969;
  font-weight: 500;
}

/* 日志 */
.log-card {
  flex-shrink: 0;
}

.log-content {
  max-height: 220px;
  overflow-y: auto;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.8;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 10px 14px;
  border-radius: 6px;
}

.log-content::-webkit-scrollbar {
  width: 6px;
}

.log-content::-webkit-scrollbar-thumb {
  background: #4a4a4a;
  border-radius: 3px;
}

.log-empty {
  color: #858585;
  text-align: center;
  padding: 20px 0;
}

.log-line {
  display: flex;
  gap: 8px;
  align-items: baseline;
}

.log-time {
  color: #858585;
  flex-shrink: 0;
  font-size: 11px;
}

.log-level {
  flex-shrink: 0;
  width: 40px;
  text-align: center;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 3px;
}

.log-level.info { color: #4ec9b0; background: rgba(78, 201, 176, 0.1); }
.log-level.success { color: #73c991; background: rgba(115, 201, 145, 0.1); }
.log-level.warning { color: #e6a23c; background: rgba(230, 162, 60, 0.1); }
.log-level.error { color: #f56c6c; background: rgba(245, 108, 108, 0.1); }

.log-line.info .log-msg { color: #d4d4d4; }
.log-line.success .log-msg { color: #73c991; }
.log-line.warning .log-msg { color: #e6a23c; }
.log-line.error .log-msg { color: #f56c6c; }
</style>
