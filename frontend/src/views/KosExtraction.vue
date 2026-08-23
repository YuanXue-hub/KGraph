<template>
  <ExtractionLayout
    theme-color="#67c23a"
    config-title="抽取配置"
    result-title="抽取结果"
    history-title="抽取历史记录"
  >
    <template #config>
      <el-form label-width="110px" class="ext-form">
        <el-form-item label="所属项目">
          <el-select
            v-model="projectId"
            placeholder="选择项目"
            filterable
            style="width: 100%"
            @change="onProjectChange"
          >
            <el-option v-for="p in projects" :key="p.id" :label="p.projectName" :value="p.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="图谱模型">
          <el-select
            v-model="modelId"
            placeholder="请先选择项目"
            filterable
            style="width: 100%"
          >
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
              <el-select v-if="corpusMode === 'corpus'" v-model="corpusId" placeholder="选择语料" filterable style="width: 100%" @change="onCorpusChange">
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

        <el-divider content-position="left">KOS 参数设置</el-divider>

        <div class="kos-num-row">
          <el-form-item label="高频术语" label-width="64px">
            <el-input-number v-model="kosConfig.termCount" :min="1" :max="9999" controls-position="right" class="kos-num-input" />
          </el-form-item>
          <el-form-item label="高频概念" label-width="64px">
            <el-input-number v-model="kosConfig.conceptCount" :min="1" :max="9999" controls-position="right" class="kos-num-input" />
          </el-form-item>
          <el-form-item label="高频范畴" label-width="64px">
            <el-input-number v-model="kosConfig.categoryCount" :min="1" :max="9999" controls-position="right" class="kos-num-input" />
          </el-form-item>
        </div>

        <el-form-item label="实体识别类型">
          <el-checkbox-group v-model="kosConfig.entityTypes" class="entity-type-group">
            <el-checkbox v-for="t in ENTITY_TYPES" :key="t" :label="t">{{ t }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="extracting"
            :disabled="!canExtract"
            @click="handleExtract"
            class="ext-btn-action"
          >
            开始抽取
          </el-button>
        </el-form-item>
      </el-form>
    </template>

    <template #result-extra>
      <div v-if="result" class="ext-stat-tags">
        <el-tag type="primary" effect="plain">实体 {{ result.entities?.length || 0 }}</el-tag>
        <el-tag type="success" effect="plain">关系 {{ result.relations?.length || 0 }}</el-tag>
        <el-tag type="warning" effect="plain" v-if="result.costTime">耗时 {{ result.costTime }}ms</el-tag>
        <el-tag type="info" effect="plain" v-if="result.metrics">
          术语 {{ result.metrics.termCount || 0 }} / 概念 {{ result.metrics.conceptCount || 0 }} / 范畴 {{ result.metrics.categoryCount || 0 }}
        </el-tag>
      </div>
    </template>

    <template #result>
      <el-empty v-if="!result" description="点击「开始抽取」查看结果" />

      <div v-else class="ext-result">
        <div v-if="highlightedText" class="ext-highlight-box">
          <h4 class="ext-section-title">原文标注</h4>
          <div class="ext-highlight-text" v-html="highlightedText"></div>
        </div>

        <el-tabs class="mt-12">
          <el-tab-pane :label="`实体列表 (${entities.length})`">
            <el-table :data="entities" border size="small" max-height="320">
              <el-table-column type="index" width="50" align="center" />
              <el-table-column prop="name" label="实体名称" min-width="120" show-overflow-tooltip />
              <el-table-column prop="type" label="类型" width="100">
                <template #default="{ row }">
                  <el-tag :color="typeColorMap[row.type]" effect="dark" size="small">{{ row.type }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="属性" min-width="180">
                <template #default="{ row }">
                  <span v-if="!row.properties || !Object.keys(row.properties).length">-</span>
                  <el-tag
                    v-for="(v, k) in row.properties"
                    :key="k"
                    size="small"
                    class="entity-tag"
                  >
                    {{ k }}: {{ v }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane :label="`关系列表 (${relations.length})`">
            <el-table :data="relations" border size="small" max-height="320">
              <el-table-column type="index" width="50" align="center" />
              <el-table-column prop="head" label="头实体" min-width="100" show-overflow-tooltip />
              <el-table-column prop="relation" label="关系" width="100">
                <template #default="{ row }">
                  <el-tag type="success" size="small">{{ row.relation }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="tail" label="尾实体" min-width="100" show-overflow-tooltip />
              <el-table-column label="属性" min-width="160">
                <template #default="{ row }">
                  <span v-if="!row.properties || !Object.keys(row.properties).length">-</span>
                  <el-tag
                    v-for="(v, k) in row.properties"
                    :key="k"
                    size="small"
                    class="entity-tag"
                  >
                    {{ k }}: {{ v }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </div>
    </template>

    <template #history-extra>
      <el-button size="small" :icon="Refresh" @click="loadHistory">刷新</el-button>
    </template>

    <template #history>
      <el-table :data="history" border v-loading="historyLoading" size="small">
        <el-table-column type="index" min-width="50" align="center" />
        <el-table-column prop="extractionType" label="类型" min-width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.extractionType === 'KOS' ? 'success' : 'primary'" size="small">
              {{ row.extractionType || 'LLM' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="modelId" label="模型ID" min-width="110" align="center" />
        <el-table-column prop="duration" label="耗时(ms)" min-width="90" align="center" />
        <el-table-column prop="status" label="状态" min-width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="抽取时间" min-width="150">
          <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="130" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="viewHistory(row)">查看</el-button>
            <el-button size="small" @click="exportExtractionTask(row)">导出</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="ext-pagination">
        <el-pagination
          v-model:current-page="histPage"
          v-model:page-size="histSize"
          :total="histTotal"
          layout="total, prev, pager, next"
          @current-change="loadHistory"
        />
      </div>
    </template>
  </ExtractionLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { projectApi, modelApi, corpusApi, extractionApi } from '@/api'
import { exportExtractionTask } from '@/utils/export'
import ExtractionLayout from '@/components/ExtractionLayout.vue'

interface Project { id: number | string; projectName: string }
interface ModelInfo { id: number | string; modelName: string }
interface Corpus { id: number | string; title: string; projectId?: number | string; content?: string }
interface ExtractEntity { name: string; type: string; properties?: Record<string, any> }
interface ExtractRelation { head: string; relation: string; tail: string; properties?: Record<string, any> }
interface ExtractResult {
  entities: ExtractEntity[]
  relations: ExtractRelation[]
  costTime?: number
  metrics?: Record<string, any>
  inputText?: string
  text?: string
}

// 实体识别类型选项
const ENTITY_TYPES = [
  '高频术语', '主题概念', '范畴分类',
  '组织机构', '专家学者', '学术期刊',
]

const SAMPLE_TEXT = `近年来，人工智能与深度学习技术快速发展，知识图谱作为认知智能的核心技术之一，
被广泛应用于数据分析与数据挖掘领域。中国农业科学院在水稻、小麦等农作物的育种与栽培技术上取得重要成果，
同时利用大数据与机器学习算法推动智慧农业发展。在医药卫生领域，糖尿病、高血压等慢性病的防治受到关注，
疫苗研发与基因检测技术不断突破。袁隆平院士的杂交水稻研究为全球粮食安全作出巨大贡献。
清华大学与中国科学院在计算机视觉、自然语言处理等方向发表大量论文于 Nature 与 Science 等学术期刊。
数字经济与高质量发展成为产业经济转型的新动能，企业通过供应链管理与创新驱动提升绩效。`

const projects = ref<Project[]>([])
const models = ref<ModelInfo[]>([])
const corpusList = ref<Corpus[]>([])
const projectId = ref<number | string | undefined>()
const modelId = ref<number | string | undefined>()
const corpusId = ref<number | string | undefined>()
const corpusMode = ref<'corpus' | 'manual'>('manual')
const inputText = ref(SAMPLE_TEXT)
const extracting = ref(false)
const result = ref<ExtractResult | null>(null)
const stepActive = ref(0)

const kosConfig = reactive({
  termCount: 10,
  conceptCount: 10,
  categoryCount: 10,
  entityTypes: ['高频术语', '主题概念', '范畴分类', '组织机构', '专家学者', '学术期刊'],
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
  // 按长度倒序避免重叠替换
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

// 选择语料后：把语料内容填充到 textarea（disabled 状态展示）
async function onCorpusChange() {
  if (!corpusId.value) {
    inputText.value = ''
    return
  }
  try {
    const res = await corpusApi.get(corpusId.value as number)
    inputText.value = (res.data as Corpus)?.content || ''
  } catch {
    const found = corpusList.value.find(c => c.id === corpusId.value)
    inputText.value = found?.content || ''
  }
}

async function onProjectChange() {
  models.value = []
  corpusList.value = []
  modelId.value = undefined
  corpusId.value = undefined
  if (!projectId.value) {
    await loadCorpusList()  // 项目被清空时仍刷新一次全量语料
    return
  }
  const [mRes] = await Promise.all([
    modelApi.list(projectId.value),
    loadCorpusList(),
  ])
  models.value = extractRecords(mRes)
}

// 切换到「选择语料」tab 时：每次都强制刷新（避免切项目/切回来后列表没更新）
watch(corpusMode, async (mode) => {
  if (mode === 'corpus') {
    await loadCorpusList()
  }
})

function parseResult(data: any): ExtractResult | null {
  if (!data) return null
  // 如果 data 本身就是 ExtractResult（包含 entities 字段）
  if (data.entities) {
    return {
      entities: data.entities,
      relations: data.relations || [],
      costTime: data.duration,
      metrics: data.metrics,
      inputText: data.inputText,
    }
  }
  // 如果 data 是 ExtractionTask，从 result 字段解析 JSON
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
  stepActive.value = 2
  try {
    const res = await extractionApi.kos({
      projectId: projectId.value,
      modelId: modelId.value,
      corpusId: corpusMode.value === 'corpus' ? corpusId.value : undefined,
      inputText: corpusMode.value === 'manual' ? inputText.value : undefined,
      kosConfig: { ...kosConfig },
    })
    result.value = parseResult(res.data)
    stepActive.value = 4
    ElMessage.success('KOS 抽取完成')
    await loadHistory()
  } catch {
    stepActive.value = 0
  } finally {
    extracting.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await extractionApi.list({
      extractionType: 'KOS',
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
  stepActive.value = 4
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
})
</script>

<style scoped>
.ext-form :deep(.el-divider--horizontal) {
  margin: 18px 0;
}

.ext-form :deep(.el-divider__text) {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
  background: var(--bg-card);
}

.ext-btn-action {
  width: 100%;
  height: 40px;
  font-size: 15px;
  font-weight: 500;
  transition: transform var(--t-fast), box-shadow var(--t-fast);
}

.ext-btn-action:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(22, 93, 255, 0.22);
}

.ext-btn-action:active {
  transform: translateY(0);
}

.ext-stat-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* 结果区不再固定高度，随面板自适应；由面板体统一滚动 */
.ext-result {
  display: flex;
  flex-direction: column;
}

.ext-highlight-box {
  margin-bottom: 12px;
  flex-shrink: 0;
}

.ext-section-title {
  font-size: 14px;
  color: var(--text-1);
  margin-bottom: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.ext-section-title::before {
  content: '';
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--brand-primary), var(--brand-accent));
}

.ext-highlight-text {
  padding: 16px;
  background: var(--bg-soft);
  border: 1px solid var(--border-2);
  border-radius: var(--r-md);
  line-height: 1.9;
  font-size: 14px;
  color: var(--text-2);
  white-space: pre-wrap;
  /* 长文本限高滚动，避免挤压下方实体/关系列表 */
  max-height: 240px;
  overflow: auto;
}

.ext-highlight-text :deep(.hl-entity) {
  border-radius: var(--r-sm);
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

.entity-tag {
  margin: 2px 4px 2px 0;
}

.mb-12 {
  margin-bottom: 12px;
}

.mt-12 {
  margin-top: 12px;
}

/* KOS 参数：三个数量输入横排，均匀分布填满行宽 */
.kos-num-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 18px;
}

.kos-num-row :deep(.el-form-item) {
  margin-right: 0;
  margin-bottom: 0;
}

/* KOS 参数：数量输入框，宽度容纳四位数字 + 箭头 */
.kos-num-input {
  width: 95px;
}

.kos-num-input :deep(.el-input__inner) {
  text-align: center;
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
  transition: all var(--t-fast);
  user-select: none;
  font-weight: 500;
}

.corpus-tab:hover {
  color: var(--brand-primary);
}

.corpus-tab.active {
  background: #fff;
  color: var(--brand-primary);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 21, 41, 0.08);
}

.corpus-content {
  width: 100%;
}
</style>
