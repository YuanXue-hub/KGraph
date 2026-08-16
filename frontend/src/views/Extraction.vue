<template>
  <ExtractionLayout
    theme-color="#409eff"
    config-title="抽取配置"
    result-title="抽取结果"
    history-title="抽取历史记录"
  >
    <template #config>
      <el-tabs v-model="activeConfigTab" class="config-tabs">
        <el-tab-pane label="抽取配置" name="extract">
          <el-form label-width="100px" class="ext-form">
            <el-form-item label="所属项目">
              <el-select v-model="projectId" placeholder="选择项目" filterable style="width: 100%" @change="onProjectChange">
                <el-option v-for="p in projects" :key="p.id" :label="p.projectName" :value="p.id" />
              </el-select>
            </el-form-item>

            <el-form-item label="图谱模型">
              <el-select v-model="modelId" placeholder="请先选择项目" filterable style="width: 100%" @change="onModelChange">
                <el-option v-for="m in models" :key="m.id" :label="m.modelName" :value="m.id" />
              </el-select>
            </el-form-item>

            <el-form-item label="语料来源">
              <div class="corpus-source">
                <div class="corpus-tabs">
                  <div class="corpus-tab" :class="{ active: corpusMode === 'corpus' }" @click="onCorpusModeChange('corpus')">
                    选择语料
                  </div>
                  <div class="corpus-tab" :class="{ active: corpusMode === 'manual' }" @click="onCorpusModeChange('manual')">
                    手动输入
                  </div>
                </div>
                <div class="corpus-content">
                  <el-select v-if="corpusMode === 'corpus'" v-model="corpusId" placeholder="选择语料" filterable style="width: 100%" @change="loadCorpusContent">
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

            <el-form-item>
              <el-button type="primary" :loading="extracting" :disabled="!canExtract" @click="handleExtract" class="ext-btn-action">
                开始抽取
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="实体关系配置" name="ontology">
          <div class="ontology-config">
            <div class="ontology-section">
              <h4 class="ontology-title">实体类型</h4>
              <p class="ontology-sub">从模型加载: {{ modelEntityTypes.length }} 个 | 自定义: {{ customEntityTypes.length }} 个</p>
              <div class="tag-list">
                <el-tag
                  v-for="t in modelEntityTypes"
                  :key="'m-' + t"
                  closable
                  type="info"
                  size="large"
                  @close="removeModelEntity(t)"
                  class="ontology-tag"
                >{{ t }}</el-tag>
                <el-tag
                  v-for="(t, i) in customEntityTypes"
                  :key="'c-' + i"
                  closable
                  type="primary"
                  size="large"
                  @close="customEntityTypes.splice(i, 1)"
                  class="ontology-tag"
                >{{ t }}</el-tag>
              </div>
              <div class="tag-input-row">
                <el-input v-model="newEntityType" placeholder="输入实体类型名称" @keyup.enter="addEntityType" />
                <el-button type="primary" @click="addEntityType">添加</el-button>
              </div>
            </div>

            <el-divider />

            <div class="ontology-section">
              <h4 class="ontology-title">关系类型</h4>
              <p class="ontology-sub">从模型加载: {{ modelRelationTypes.length }} 个 | 自定义: {{ customRelationTypes.length }} 个</p>
              <div class="tag-list">
                <el-tag
                  v-for="t in modelRelationTypes"
                  :key="'m-' + t"
                  closable
                  type="info"
                  size="large"
                  @close="removeModelRelation(t)"
                  class="ontology-tag"
                >{{ t }}</el-tag>
                <el-tag
                  v-for="(t, i) in customRelationTypes"
                  :key="'c-' + i"
                  closable
                  type="success"
                  size="large"
                  @close="customRelationTypes.splice(i, 1)"
                  class="ontology-tag"
                >{{ t }}</el-tag>
              </div>
              <div class="tag-input-row">
                <el-input v-model="newRelationType" placeholder="输入关系类型名称" @keyup.enter="addRelationType" />
                <el-button type="success" @click="addRelationType">添加</el-button>
              </div>
            </div>

            <el-divider />

            <div class="ontology-actions">
              <el-button @click="clearOntologyConfig">清空配置</el-button>
              <el-button type="primary" @click="activeConfigTab = 'extract'">返回抽取</el-button>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>

    <template #result-extra>
      <div v-if="result" class="ext-stat-tags">
        <el-tag type="primary" effect="plain">实体 {{ result.entities?.length || 0 }}</el-tag>
        <el-tag type="success" effect="plain">关系 {{ result.relations?.length || 0 }}</el-tag>
        <el-tag type="warning" effect="plain" v-if="result.costTime">耗时 {{ result.costTime }}ms</el-tag>
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
            <el-table :data="pagedEntities" border>
              <el-table-column type="index" width="60" align="center" :index="(i: number) => (entityPage - 1) * ENTITY_PAGE_SIZE + i + 1" />
              <el-table-column prop="name" label="实体名称" min-width="180" />
              <el-table-column prop="type" label="类型" width="140">
                <template #default="{ row }">
                  <el-tag :color="typeColorMap[row.type]" effect="dark">{{ row.type }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="属性" min-width="300">
                <template #default="{ row }">
                  <span v-if="!row.properties || !Object.keys(row.properties).length">-</span>
                  <el-tag v-for="(v, k) in row.properties" :key="k" class="entity-tag" style="margin: 2px 4px 2px 0;">{{ k }}: {{ v }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
            <div class="ext-pagination" v-if="entities.length > ENTITY_PAGE_SIZE">
              <el-pagination v-model:current-page="entityPage" :page-size="ENTITY_PAGE_SIZE" :total="entities.length" layout="total, prev, pager, next" />
            </div>
          </el-tab-pane>

          <el-tab-pane :label="`关系列表 (${relations.length})`">
            <el-table :data="pagedRelations" border>
              <el-table-column type="index" width="60" align="center" :index="(i: number) => (relPage - 1) * REL_PAGE_SIZE + i + 1" />
              <el-table-column prop="head" label="头实体" min-width="180" />
              <el-table-column prop="relation" label="关系" width="140">
                <template #default="{ row }">
                  <el-tag type="success">{{ row.relation }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="tail" label="尾实体" min-width="180" />
              <el-table-column label="属性" min-width="280">
                <template #default="{ row }">
                  <span v-if="!row.properties || !Object.keys(row.properties).length">-</span>
                  <el-tag v-for="(v, k) in row.properties" :key="k" class="entity-tag" style="margin: 2px 4px 2px 0;">{{ k }}: {{ v }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
            <div class="ext-pagination" v-if="relations.length > REL_PAGE_SIZE">
              <el-pagination v-model:current-page="relPage" :page-size="REL_PAGE_SIZE" :total="relations.length" layout="total, prev, pager, next" />
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </template>

    <template #history-extra>
      <el-button size="small" :icon="Refresh" @click="loadHistory">刷新</el-button>
    </template>

    <template #history>
      <el-table :data="history" border v-loading="historyLoading" size="small">
        <el-table-column type="index" width="50" align="center" />
        <el-table-column prop="extractionType" label="类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="extractionTypeColor(row.extractionType)" size="small">{{ row.extractionType || 'LLM' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="modelId" label="模型ID" width="120" align="center" />
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
    </template>
  </ExtractionLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, View } from '@element-plus/icons-vue'
import { projectApi, modelApi, corpusApi, extractionApi, entityTypeApi, relationTypeApi } from '@/api'
import ExtractionLayout from '@/components/ExtractionLayout.vue'

interface Project { id: number; projectName: string }
interface ModelInfo { id: number; modelName: string }
interface Corpus { id: number; title: string; content?: string; source?: string; projectId?: number | string }
interface ExtractEntity { name: string; type: string; properties?: Record<string, any> }
interface ExtractRelation { head: string; relation: string; tail: string; properties?: Record<string, any> }
interface ExtractResult {
  entities: ExtractEntity[]
  relations: ExtractRelation[]
  costTime?: number
  inputText?: string
  text?: string
}

const projects = ref<Project[]>([])
const models = ref<ModelInfo[]>([])
const corpusList = ref<Corpus[]>([])
const projectId = ref<number | undefined>()
const modelId = ref<number | undefined>()
const corpusId = ref<number | undefined>()
const corpusMode = ref<'corpus' | 'manual'>('manual')
const inputText = ref('')
const extracting = ref(false)
const result = ref<ExtractResult | null>(null)
const stepActive = ref(0)

// 实体关系配置
const activeConfigTab = ref('extract')
const modelEntityTypes = ref<string[]>([])
const modelRelationTypes = ref<string[]>([])
const customEntityTypes = ref<string[]>([])
const customRelationTypes = ref<string[]>([])
const newEntityType = ref('')
const newRelationType = ref('')

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

// 结果列表分页（替代原 max-height 滚动）
const ENTITY_PAGE_SIZE = 20
const REL_PAGE_SIZE = 20
const entityPage = ref(1)
const relPage = ref(1)
const pagedEntities = computed(() => {
  const start = (entityPage.value - 1) * ENTITY_PAGE_SIZE
  return entities.value.slice(start, start + ENTITY_PAGE_SIZE)
})
const pagedRelations = computed(() => {
  const start = (relPage.value - 1) * REL_PAGE_SIZE
  return relations.value.slice(start, start + REL_PAGE_SIZE)
})
watch(entities, () => { entityPage.value = 1 })
watch(relations, () => { relPage.value = 1 })

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
  inputText.value = ''
  if (!projectId.value) {
    await loadCorpusList()
    return
  }
  const [mRes] = await Promise.all([
    modelApi.list(projectId.value),
    loadCorpusList(),
  ])
  models.value = extractRecords(mRes)
  // 自动选择第一个模型并加载本体
  if (models.value.length > 0) {
    modelId.value = models.value[0].id
    await onModelChange()
  }
}

async function loadCorpusContent(id: number | undefined) {
  if (!id) {
    inputText.value = ''
    return
  }
  try {
    const res = await corpusApi.get(id)
    inputText.value = (res.data as Corpus)?.content || ''
  } catch {
    const found = corpusList.value.find(c => c.id === id)
    inputText.value = found?.content || ''
  }
}

async function onCorpusModeChange(mode: 'corpus' | 'manual') {
  corpusMode.value = mode
  if (mode === 'manual') {
    corpusId.value = undefined
  } else {
    // 每次切到语料选择 tab 都强制刷新，避免切项目/回来后无数据
    await loadCorpusList()
  }
}

async function onModelChange() {
  modelEntityTypes.value = []
  modelRelationTypes.value = []
  customEntityTypes.value = []
  customRelationTypes.value = []
  if (!modelId.value) return
  try {
    const [eRes, rRes] = await Promise.all([
      entityTypeApi.list(modelId.value),
      relationTypeApi.list(modelId.value)
    ])
    modelEntityTypes.value = (eRes.data || []).map((e: any) => e.entityName).filter(Boolean)
    modelRelationTypes.value = (rRes.data || []).map((r: any) => r.relationName).filter(Boolean)
  } catch {
    // 加载失败忽略
  }
}

function addEntityType() {
  const name = newEntityType.value.trim()
  if (!name) return
  if (modelEntityTypes.value.includes(name) || customEntityTypes.value.includes(name)) {
    ElMessage.warning('该实体类型已存在')
    return
  }
  customEntityTypes.value.push(name)
  newEntityType.value = ''
}

function addRelationType() {
  const name = newRelationType.value.trim()
  if (!name) return
  if (modelRelationTypes.value.includes(name) || customRelationTypes.value.includes(name)) {
    ElMessage.warning('该关系类型已存在')
    return
  }
  customRelationTypes.value.push(name)
  newRelationType.value = ''
}

function removeModelEntity(name: string) {
  modelEntityTypes.value = modelEntityTypes.value.filter(t => t !== name)
}

function removeModelRelation(name: string) {
  modelRelationTypes.value = modelRelationTypes.value.filter(t => t !== name)
}

function clearOntologyConfig() {
  customEntityTypes.value = []
  customRelationTypes.value = []
  newEntityType.value = ''
  newRelationType.value = ''
}

function getEffectiveEntityTypes(): string[] | undefined {
  const all = [...modelEntityTypes.value, ...customEntityTypes.value]
  return all.length > 0 ? all : undefined
}

function getEffectiveRelationTypes(): string[] | undefined {
  const all = [...modelRelationTypes.value, ...customRelationTypes.value]
  return all.length > 0 ? all : undefined
}

function parseResult(data: any): ExtractResult | null {
  if (!data) return null
  if (data.entities) return data as ExtractResult
  if (data.result && typeof data.result === 'string') {
    try {
      const parsed = JSON.parse(data.result)
      return {
        entities: parsed.entities || [],
        relations: parsed.relations || [],
        costTime: parsed.duration || data.duration,
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
    const res = await extractionApi.llm({
      projectId: projectId.value,
      modelId: modelId.value,
      corpusId: corpusMode.value === 'corpus' ? corpusId.value : undefined,
      inputText: corpusMode.value === 'manual' ? inputText.value : undefined,
      mode: 'zero_shot',
      customEntityTypes: getEffectiveEntityTypes(),
      customRelationTypes: getEffectiveRelationTypes()
    })
    result.value = parseResult(res.data)
    stepActive.value = 4
    ElMessage.success('抽取完成')
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
      projectId: projectId.value as number,
      extractionType: 'LLM',
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
function extractionTypeColor(type: string): string {
  if (type === 'DL') return 'danger'
  if (type === 'KOS') return 'success'
  if (type === 'STRUCTURE') return 'warning'
  return 'primary'
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

.ext-result {
  max-height: 560px;
  overflow: auto;
}

.ext-highlight-box {
  margin-bottom: 18px;
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
}

.ext-highlight-text :deep(.hl-entity) {
  border-radius: var(--r-sm);
}

.ext-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.mb-12 {
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

/* 实体关系配置 */
.config-tabs :deep(.el-tabs__header) {
  margin-bottom: 18px;
}

.config-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-2);
}

.config-tabs :deep(.el-tabs__item.is-active) {
  color: var(--brand-primary);
  font-weight: 600;
}

.config-tabs :deep(.el-tabs__active-bar) {
  background: linear-gradient(90deg, var(--brand-primary), var(--brand-accent));
  height: 3px;
  border-radius: 2px;
}

.ontology-config {
  padding: 4px 0;
}

.ontology-section {
  margin-bottom: 12px;
  padding: 16px;
  background: var(--bg-soft);
  border: 1px solid var(--border-2);
  border-radius: var(--r-md);
}

.ontology-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-1);
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.ontology-title::before {
  content: '';
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--brand-primary), var(--brand-accent));
}

.ontology-sub {
  font-size: 12px;
  color: var(--text-3);
  margin-bottom: 12px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  min-height: 36px;
  padding: 10px;
  background: var(--bg-card);
  border-radius: var(--r-md);
  border: 1px dashed var(--border-1);
}

.ontology-tag {
  border-radius: var(--r-sm);
}

.tag-input-row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 12px;
}

.tag-input-row > :deep(.el-input) {
  flex: 1 1 auto;
}

.tag-input-row > :deep(.el-button) {
  min-width: 88px;
}

.ontology-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 8px;
}
</style>
