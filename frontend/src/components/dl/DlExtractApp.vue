<template>
  <div class="dl-extract-app">
    <el-row :gutter="12" align="stretch" class="extract-main-row">
      <!-- 左侧：配置与执行 -->
      <el-col :span="12" class="extract-col">
        <el-card shadow="never" class="config-card extract-equal-card">
          <template #header>
            <div class="card-header">
              <span class="header-title">
                <el-icon><Cpu /></el-icon>
                抽取配置
              </span>
              <el-button type="primary" size="small" :loading="extracting" :disabled="!canExtract" @click="handleExtract" class="ext-btn-action">
                开始抽取
              </el-button>
            </div>
          </template>

          <el-form label-width="100px" class="ext-form">
            <el-form-item label="所属项目">
              <el-select v-model="projectId" placeholder="选择项目" filterable style="width: 100%" @change="onProjectChange">
                <el-option v-for="p in projects" :key="p.id" :label="p.projectName" :value="p.id" />
              </el-select>
            </el-form-item>

            <el-form-item label="图谱模型">
              <el-select v-model="modelId" placeholder="请先选择项目" filterable style="width: 100%">
                <el-option v-for="m in models" :key="m.id" :label="m.modelName" :value="m.id" />
              </el-select>
            </el-form-item>

            <el-form-item label="语料来源">
              <div class="corpus-source">
                <div class="corpus-tabs">
                  <div class="corpus-tab" :class="{ active: corpusMode === 'corpus' }" @click="corpusMode = 'corpus'">
                    选择语料
                  </div>
                  <div class="corpus-tab" :class="{ active: corpusMode === 'manual' }" @click="corpusMode = 'manual'">
                    手动输入
                  </div>
                </div>
                <div class="corpus-content">
                  <el-select
                    v-if="corpusMode === 'corpus'"
                    v-model="corpusId"
                    placeholder="选择语料"
                    filterable
                    style="width: 100%"
                    @change="onCorpusChange"
                  >
                    <el-option v-for="c in corpusList" :key="c.id" :label="c.title" :value="c.id">
                      <span style="display: inline-flex; justify-content: space-between; width: 100%; gap: 12px; align-items: center;">
                        <span style="font-weight: 500; color: #1f2329;">{{ c.title }}</span>
                        <span v-if="projectNameById(c.projectId)" style="color: #86909c; font-size: 12px; flex-shrink: 0;">
                          {{ projectNameById(c.projectId) }}
                        </span>
                      </span>
                    </el-option>
                  </el-select>
                  <el-input
                    v-model="inputText"
                    type="textarea"
                    :rows="8"
                    :placeholder="corpusMode === 'corpus' ? '选择语料后，文本内容将展示在此' : '请输入需要抽取的文本内容'"
                    :disabled="corpusMode === 'corpus'"
                  />
                </div>
              </div>
            </el-form-item>

            <el-divider content-position="left">模型架构</el-divider>

            <div class="arch-tip">
              <el-icon><InfoFilled /></el-icon>
              <span>「DL 模型版本」是在模型训练模块训练完成的具体模型实例；「模型架构」是该版本所采用的网络结构（如 BiLSTM-CRF / BERT-CRF 等）。选择模型版本后会自动同步对应架构，也可手动切换。</span>
            </div>

            <el-form-item label="DL 模型版本">
              <el-select v-model="dlConfig.modelVersion" style="width: 100%" placeholder="选择已训练的模型版本" :no-data-text="'暂无已训练模型，请先在「模型训练」中完成训练'">
                <el-option v-for="m in dlModelVersions" :key="m.value" :label="m.label" :value="m.value" />
              </el-select>
            </el-form-item>

            <el-form-item label="模型架构">
              <el-select v-model="dlConfig.modelArchitecture" style="width: 100%">
                <el-option label="BiLSTM-CRF（双向 LSTM + CRF）" value="BiLSTM-CRF" />
                <el-option label="BERT-CRF（BERT + CRF）" value="BERT-CRF" />
                <el-option label="SPAN-BERT（SpanBERT 抽取）" value="SPAN-BERT" />
                <el-option label="BERT-RE（BERT 关系抽取）" value="BERT-RE" />
              </el-select>
            </el-form-item>

            <el-row :gutter="8">
              <el-col :span="12">
                <el-form-item label="嵌入维度">
                  <el-select v-model="dlConfig.embeddingDim" style="width: 100%">
                    <el-option label="32 维" :value="32" />
                    <el-option label="64 维" :value="64" />
                    <el-option label="128 维" :value="128" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="上下文窗口">
                  <el-input-number v-model="dlConfig.windowSize" :min="1" :max="15" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-divider content-position="left">实体识别</el-divider>

            <el-row :gutter="8">
              <el-col :span="12">
                <el-form-item label="置信度阈值">
                  <el-slider v-model="dlConfig.confidenceThreshold" :min="0" :max="1" :step="0.05" show-input :show-input-controls="false" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="最大实体数">
                  <el-input-number v-model="dlConfig.maxEntities" :min="1" :max="200" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-divider content-position="left">关系抽取</el-divider>

            <el-row :gutter="8">
              <el-col :span="12">
                <el-form-item label="启用关系抽取">
                  <el-select v-model="dlConfig.enableRelation" style="width: 100%">
                    <el-option label="是" value="是" />
                    <el-option label="否" value="否" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="关系置信度">
                  <el-slider v-model="dlConfig.relationThreshold" :min="0" :max="1" :step="0.05" show-input :show-input-controls="false" :disabled="dlConfig.enableRelation === '否'" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右侧：结果展示 -->
      <el-col :span="12" class="extract-col">
        <el-card shadow="never" class="result-card extract-equal-card">
          <template #header>
            <div class="card-header">
              <span class="header-title">
                <el-icon><DataAnalysis /></el-icon>
                抽取结果
              </span>
              <div v-if="result" class="ext-stat-tags">
                <el-tag type="primary" effect="plain" size="small">实体 {{ result.entities?.length || 0 }}</el-tag>
                <el-tag type="success" effect="plain" size="small">关系 {{ result.relations?.length || 0 }}</el-tag>
                <el-tag type="warning" effect="plain" size="small" v-if="result.costTime">耗时 {{ result.costTime }}ms</el-tag>
                <el-tag type="info" effect="plain" size="small" v-if="result.metrics?.modelArchitecture">{{ result.metrics.modelArchitecture }}</el-tag>
              </div>
            </div>
          </template>

          <el-empty v-if="!result" description="点击「开始抽取」查看结果" />

          <div v-else class="ext-result">
            <!-- 模型指标 -->
            <div v-if="result.metrics" class="ext-metrics-box">
              <el-descriptions :column="4" border size="small">
                <el-descriptions-item label="模型架构">{{ result.metrics.modelArchitecture || '-' }}</el-descriptions-item>
                <el-descriptions-item label="嵌入维度">{{ result.metrics.embeddingDim || '-' }}</el-descriptions-item>
                <el-descriptions-item label="隐藏层维度">{{ result.metrics.hiddenDim || '-' }}</el-descriptions-item>
                <el-descriptions-item label="平均置信度">{{ result.metrics.avgConfidence || 0 }}</el-descriptions-item>
              </el-descriptions>
              <div v-if="result.metrics.typeDistribution" class="ext-type-dist">
                <span class="ext-dist-label">类型分布：</span>
                <el-tag
                  v-for="(count, type) in result.metrics.typeDistribution"
                  :key="type"
                  :color="typeColorMap[String(type)]"
                  effect="dark"
                  size="small"
                  class="ext-dist-tag"
                >
                  {{ type }}: {{ count }}
                </el-tag>
              </div>
            </div>

            <!-- 原文高亮 -->
            <div v-if="highlightedText" class="ext-highlight-box">
              <h4 class="ext-section-title">原文标注</h4>
              <div class="ext-highlight-text" v-html="highlightedText"></div>
            </div>

            <el-tabs class="mt-12">
              <el-tab-pane :label="`实体列表 (${entities.length})`">
                <el-table :data="entities" border size="small" max-height="320">
                  <el-table-column type="index" width="50" align="center" />
                  <el-table-column prop="name" label="实体名称" min-width="120" />
                  <el-table-column prop="type" label="类型" width="100">
                    <template #default="{ row }">
                      <el-tag :color="typeColorMap[row.type]" effect="dark" size="small">{{ row.type }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="置信度" width="100" align="center">
                    <template #default="{ row }">
                      <el-progress :percentage="Math.round((row.confidence || 0) * 100)" :stroke-width="6" :show-text="false" />
                      <span class="ext-conf-text">{{ ((row.confidence || 0) * 100).toFixed(0) }}%</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="属性" min-width="180">
                    <template #default="{ row }">
                      <span v-if="!row.properties || !Object.keys(row.properties).length">-</span>
                      <el-tag v-for="(v, k) in row.properties" :key="k" size="small" class="ext-entity-tag">{{ k }}: {{ v }}</el-tag>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>

              <el-tab-pane :label="`关系列表 (${relations.length})`">
                <el-table :data="relations" border size="small" max-height="320">
                  <el-table-column type="index" width="50" align="center" />
                  <el-table-column prop="head" label="头实体" min-width="100" />
                  <el-table-column prop="relation" label="关系" width="100">
                    <template #default="{ row }">
                      <el-tag type="success" size="small">{{ row.relation }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="tail" label="尾实体" min-width="100" />
                  <el-table-column label="置信度" width="100" align="center">
                    <template #default="{ row }">
                      <el-progress :percentage="Math.round((row.confidence || 0) * 100)" :stroke-width="6" :show-text="false" />
                      <span class="ext-conf-text">{{ ((row.confidence || 0) * 100).toFixed(0) }}%</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="属性" min-width="160">
                    <template #default="{ row }">
                      <span v-if="!row.properties || !Object.keys(row.properties).length">-</span>
                      <el-tag v-for="(v, k) in row.properties" :key="k" size="small" class="ext-entity-tag">{{ k }}: {{ v }}</el-tag>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>

              <el-tab-pane label="抽取历史">
                <div class="history-toolbar">
                  <el-button size="small" :icon="Refresh" @click="loadHistory">刷新</el-button>
                </div>
                <el-table :data="history" border v-loading="historyLoading" size="small">
                  <el-table-column type="index" width="50" align="center" />
                  <el-table-column prop="extractionType" label="类型" width="80" align="center">
                    <template #default="{ row }">
                      <el-tag type="danger" size="small">{{ row.extractionType || 'DL' }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="duration" label="耗时(ms)" width="100" align="center" />
                  <el-table-column prop="status" label="状态" width="90" align="center">
                    <template #default="{ row }">
                      <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="createTime" label="抽取时间" min-width="160">
                    <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
                  </el-table-column>
                  <el-table-column label="操作" width="100" align="center">
                    <template #default="{ row }">
                      <el-button size="small" :icon="View" @click="viewHistory(row)">查看</el-button>
                    </template>
                  </el-table-column>
                </el-table>
                <div class="ext-pagination">
                  <el-pagination v-model:current-page="histPage" v-model:page-size="histSize" :total="histTotal" layout="total, prev, pager, next" @current-change="loadHistory" />
                </div>
              </el-tab-pane>
            </el-tabs>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Cpu, DataAnalysis, InfoFilled, Refresh, View } from '@element-plus/icons-vue'
import { projectApi, modelApi, corpusApi, extractionApi, trainTaskApi } from '@/api'

interface Project { id: number | string; projectName: string }
interface ModelInfo { id: number | string; modelName: string }
interface Corpus { id: number | string; title: string; content?: string; projectId?: number | string }
interface ExtractEntity { name: string; type: string; confidence?: number; properties?: Record<string, any> }
interface ExtractRelation { head: string; relation: string; tail: string; confidence?: number; properties?: Record<string, any> }
interface ExtractResult {
  entities: ExtractEntity[]
  relations: ExtractRelation[]
  costTime?: number
  metrics?: Record<string, any>
  inputText?: string
  text?: string
}

// 实体识别类型选项（扩展为更全面的 NER 类型集，默认全选）
const ENTITY_TYPES = [
  '人物', '地点', '组织', '时间', '日期', '概念', '技术', '事件',
  '作品', '文献', '朝代', '官职', '战争', '政策', '奖项', '产品',
  '机构', '国家', '城市', '金额', '艺术品', '法律',
]

const SAMPLE_TEXT = `诸葛亮，字孔明，号卧龙，是三国时期蜀汉的杰出政治家与军事家。他出生于琅琊阳都，
早年隐居于南阳隆中。刘备三顾茅庐后，诸葛亮出山辅佐刘备建立蜀汉政权。
建兴五年，诸葛亮率军北伐曹魏，驻扎于汉中。他发明了木牛流马与诸葛连弩，
并在五丈原病逝。诸葛亮精通兵法与奇门遁甲，其著作《出师表》流传千古。
司马懿是曹魏的重要将领，曾多次与诸葛亮对峙于祁山。赵云、关羽、张飞均为蜀汉名将。`

const projects = ref<Project[]>([])
const models = ref<ModelInfo[]>([])
const corpusList = ref<Corpus[]>([])
const projectId = ref<number | string | undefined>()
const modelId = ref<number | string | undefined>()
const corpusId = ref<number | string | undefined>()
const corpusMode = ref<'corpus' | 'manual'>('manual')
const inputText = ref(SAMPLE_TEXT)
const corpusLoading = ref(false)
const extracting = ref(false)
const result = ref<ExtractResult | null>(null)

// DL 模型版本选项：从后端 trainTask 接口加载已完成的训练任务
interface TrainTaskInfo {
  id: number
  taskName: string
  architecture: string
  version: string
  status: string
  metrics?: string | { f1: number; precision: number; recall: number; loss: number }
}
const dlModelVersions = ref<{ label: string; value: string; architecture: string; f1?: number }[]>([])

function parseMetrics(raw: any): { f1?: number; precision?: number; recall?: number; loss?: number } | undefined {
  if (!raw) return undefined
  if (typeof raw === 'string') {
    try { return JSON.parse(raw) } catch { return undefined }
  }
  if (typeof raw === 'object') return raw
  return undefined
}

async function loadTrainedModels() {
  try {
    const res = await trainTaskApi.list({ status: 'done', pageNum: 1, pageSize: 100 })
    const records = res.data?.records || res.data || []
    dlModelVersions.value = (records as TrainTaskInfo[])
      .filter(t => t.status === 'done')
      .map(t => {
        const m = parseMetrics(t.metrics)
        return {
          label: `${t.taskName} (v${t.version}, ${t.architecture}, F1=${m?.f1?.toFixed(4) || '-'})`,
          value: `train_${t.id}`,
          architecture: t.architecture,
          f1: m?.f1,
        }
      })
  } catch (e) {
    // 忽略
  }
}

// 当选择 DL 模型版本时，自动同步模型架构（watch 定义在 dlConfig 之后，避免 TDZ）
const dlConfig = reactive({
  entityTypes: [...ENTITY_TYPES],
  confidenceThreshold: 0.5,
  maxEntities: 50,
  enableRelation: '是',
  relationThreshold: 0.3,
  windowSize: 5,
  embeddingDim: 32,
  modelArchitecture: 'BiLSTM-CRF',
  modelVersion: '',
})

watch(() => dlConfig.modelVersion, (val) => {
  const found = dlModelVersions.value.find(m => m.value === val)
  if (found && found.architecture) {
    dlConfig.modelArchitecture = found.architecture
  }
})

const history = ref<any[]>([])
const historyLoading = ref(false)
const histPage = ref(1)
const histSize = ref(10)
const histTotal = ref(0)

const PALETTE = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#9c27b0', '#00bcd4', '#ff9800']
const typeColorMap = computed(() => {
  const map: Record<string, string> = {}
  const types = new Set((result.value?.entities || []).map((e) => e.type))
  Array.from(types).forEach((t, i) => {
    map[t] = PALETTE[i % PALETTE.length]
  })
  return map
})

const entities = computed(() => result.value?.entities || [])
const relations = computed(() => result.value?.relations || [])

const canExtract = computed(() => {
  if (!modelId.value) return false
  if (corpusMode.value === 'corpus') return !!corpusId.value
  return !!inputText.value.trim()
})

const highlightedText = computed(() => {
  if (!result.value) return ''
  const text = result.value.inputText || result.value.text || inputText.value
  if (!text) return ''
  let html = escapeHtml(text)
  const ents = result.value.entities || []
  const sorted = [...ents].sort((a, b) => b.name.length - a.name.length)
  for (const e of sorted) {
    if (!e.name) continue
    const color = typeColorMap.value[e.type] || '#409eff'
    const re = new RegExp(escapeReg(e.name), 'g')
    html = html.replace(re, `<span class="hl-entity" style="background:${color}33;color:${color};border:1px solid ${color};border-radius:3px;padding:0 2px">${escapeHtml(e.name)}</span>`)
  }
  return html
})

/** 兜底从分页响应里提取 records，兼容不同后端返回结构 */
function extractRecords(res: any): any[] {
  if (!res) return []
  const payload = res.data ?? res
  if (Array.isArray(payload)) return payload
  if (payload && Array.isArray(payload.records)) return payload.records
  if (payload && Array.isArray(payload.list)) return payload.list
  if (payload && typeof payload === 'object') {
    const arrVal = Object.values(payload).find(v => Array.isArray(v))
    if (arrVal) return arrVal as any[]
  }
  return []
}

async function loadProjects() {
  const res = await projectApi.list({ pageNum: 1, pageSize: 100 })
  projects.value = extractRecords(res).slice().reverse()
  if (projects.value.length > 0 && !projectId.value) {
    projectId.value = projects.value[0].id
    await onProjectChange()
  }
}

async function loadCorpusList() {
  // 始终拉取全部语料（不按项目过滤），确保"语料管理"中的语料都能在选择列表中看到
  try {
    const cRes = await corpusApi.list({ pageNum: 1, pageSize: 500 })
    corpusList.value = extractRecords(cRes)
  } catch {
    corpusList.value = []
  }
}

function projectNameById(pid: any): string {
  if (!pid) return ''
  const p = projects.value.find((x) => x.id === pid || String(x.id) === String(pid))
  return p?.projectName || ''
}

async function onProjectChange() {
  models.value = []
  corpusList.value = []
  modelId.value = undefined
  corpusId.value = undefined
  if (!projectId.value) {
    await loadCorpusList()
    return
  }
  const [mRes] = await Promise.all([
    modelApi.list(projectId.value),
    loadCorpusList(),
  ])
  models.value = extractRecords(mRes)
}

// 选择语料后，将语料内容加载到文本框中展示
async function onCorpusChange() {
  if (!corpusId.value) {
    inputText.value = ''
    return
  }
  corpusLoading.value = true
  try {
    const res = await corpusApi.get(corpusId.value as number)
    const content = (res.data as any)?.content || ''
    inputText.value = content
  } catch {
    // 获取失败时回退到列表中已带的内容
    const found = corpusList.value.find(c => c.id === corpusId.value)
    inputText.value = found?.content || ''
  } finally {
    corpusLoading.value = false
  }
}

// 切换到语料模式时：每次都强制刷新语料列表 + 同步已选语料内容
watch(corpusMode, async (mode) => {
  if (mode === 'corpus') {
    await loadCorpusList()
    if (corpusId.value) {
      await onCorpusChange()
    }
  }
})

function parseResult(data: any): ExtractResult | null {
  if (!data) return null
  if (data.entities) {
    return {
      entities: data.entities,
      relations: data.relations || [],
      costTime: data.duration,
      metrics: data.metrics,
      inputText: data.inputText,
    }
  }
  if (data.result && typeof data.result === 'string') {
    try {
      const parsed = JSON.parse(data.result)
      return {
        entities: parsed.entities || [],
        relations: parsed.relations || [],
        costTime: parsed.duration || data.duration,
        metrics: parsed.metrics,
        inputText: data.inputText,
      }
    } catch {
      return null
    }
  }
  return null
}

async function handleExtract() {
  if (!modelId.value) {
    ElMessage.warning('请选择图谱模型')
    return
  }
  extracting.value = true
  try {
    const res = await extractionApi.dl({
      projectId: projectId.value,
      modelId: modelId.value,
      corpusId: corpusMode.value === 'corpus' ? corpusId.value : undefined,
      inputText: corpusMode.value === 'manual' ? inputText.value : undefined,
      dlConfig: { ...dlConfig },
    })
    result.value = parseResult(res.data)
    ElMessage.success('深度学习抽取完成')
    await loadHistory()
  } catch {
    // 抽取失败
  } finally {
    extracting.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await extractionApi.list({
      projectId: projectId.value as number,
      extractionType: 'DL',
      pageNum: histPage.value,
      pageSize: histSize.value,
      sortField: 'createTime',
      sortOrder: 'descend',
    })
    history.value = res.data?.records || res.data || []
    histTotal.value = res.data?.total || history.value.length
  } finally {
    historyLoading.value = false
  }
}

async function viewHistory(row: any) {
  const res = await extractionApi.get(row.id)
  result.value = parseResult(res.data)
}

function statusType(status: number): string {
  return { 1: 'warning', 2: 'success', 3: 'danger' }[status] || 'info'
}
function statusText(status: number): string {
  return { 1: '进行中', 2: '成功', 3: '失败' }[status] || '未知'
}
function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function escapeReg(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
function formatTime(t?: string): string {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

onMounted(() => {
  loadProjects()
  loadHistory()
  loadTrainedModels()
})
</script>

<style scoped>
.dl-extract-app {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 左右等高 */
.extract-main-row {
  align-items: stretch;
}

.extract-col {
  display: flex;
}

.extract-equal-card {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.extract-equal-card :deep(.el-card__body) {
  flex: 1;
  overflow: auto;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  font-size: 14px;
  color: #1d2129;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ext-form :deep(.el-divider--horizontal) {
  margin: 16px 0;
}

.arch-tip {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 8px 12px;
  margin-bottom: 12px;
  background: #f0f5ff;
  border: 1px solid #d6e4ff;
  border-radius: 6px;
  font-size: 12px;
  color: #4e5969;
  line-height: 1.6;
}

.arch-tip :deep(.el-icon) {
  color: #165dff;
  margin-top: 2px;
  flex-shrink: 0;
}

.ext-btn-action {
  height: 36px;
  font-size: 14px;
  font-weight: 500;
}

.ext-stat-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ext-result {
  width: 100%;
}

.ext-metrics-box {
  margin-bottom: 16px;
}

.ext-type-dist {
  margin-top: 8px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.ext-dist-label {
  font-size: 13px;
  color: #606266;
}

.ext-dist-tag {
  color: #fff;
}

.ext-highlight-box {
  margin-bottom: 16px;
}

.ext-section-title {
  font-size: 14px;
  color: #1d2129;
  margin-bottom: 8px;
  font-weight: 600;
}

.ext-highlight-text {
  padding: 14px;
  background: #f7f8fa;
  border: 1px solid #f0f2f5;
  border-radius: 8px;
  line-height: 1.9;
  font-size: 14px;
  white-space: pre-wrap;
}

.ext-entity-tag {
  margin: 2px 4px 2px 0;
}

.ext-conf-text {
  font-size: 11px;
  color: #606266;
}

.ext-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.entity-type-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 0;
}

.history-toolbar {
  margin-bottom: 12px;
}

.mt-12 {
  margin-top: 12px;
}

/* 语料来源 tab 切换 */
.corpus-source {
  width: 100%;
}

.corpus-tabs {
  display: inline-flex;
  gap: 4px;
  background: var(--border-2);
  padding: 2px;
  border-radius: 6px;
  margin-bottom: 8px;
}

.corpus-tab {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-3);
  background: transparent;
  transition: all 0.2s;
  font-weight: 500;
}

.corpus-tab:hover {
  color: #165dff;
}

.corpus-tab.active {
  background: #fff;
  color: #165dff;
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 21, 41, 0.08);
}

.corpus-content {
  width: 100%;
}
</style>
