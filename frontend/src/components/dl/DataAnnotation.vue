<template>
  <div class="data-annotation">
    <!-- 顶部工具栏 -->
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-button type="primary" :icon="Plus" @click="openCreateTask">新建标注任务</el-button>
          <el-button :icon="Refresh" @click="loadTasks">刷新</el-button>
          <el-divider direction="vertical" />
          <el-select v-model="currentTaskId" placeholder="切换标注任务" style="width: 240px" @change="onTaskChange">
            <el-option v-for="t in tasks" :key="t.id" :label="t.taskName" :value="t.id" />
          </el-select>
        </div>
        <div class="toolbar-right">
          <el-tag v-if="currentTask" size="small" type="info">标注员：{{ currentTask.annotator }}</el-tag>
          <el-tag v-if="currentTask" size="small" type="warning">审核员：{{ currentTask.reviewer }}</el-tag>
          <el-tag v-if="currentTask" size="small" :type="progressTagType">进度：{{ annotationProgress }}%</el-tag>
          <el-button :icon="Download" @click="exportDataset" :disabled="!currentTask">导出数据集</el-button>
        </div>
      </div>
    </el-card>

    <div v-if="!currentTask" class="empty-state">
      <el-empty description="请选择或新建一个标注任务" />
    </div>

    <template v-else>
      <el-row :gutter="12" class="anno-main-row" align="stretch">
        <!-- 左侧：原文标注 -->
        <el-col :span="12">
          <el-card shadow="never" class="section-card anno-left-card anno-equal-card">
            <template #header>
              <div class="card-header">
                <span class="header-title">
                  <el-icon><Document /></el-icon>
                  原文标注 · {{ currentTask.taskName }}
                </span>
                <div class="header-actions">
                  <el-button-group>
                    <el-button size="small" :icon="Back" :disabled="!canUndo" @click="undo">撤销</el-button>
                    <el-button size="small" :icon="Right" :disabled="!canRedo" @click="redo">重做</el-button>
                  </el-button-group>
                  <el-button size="small" type="success" :icon="Check" :loading="saving" @click="saveProgress">保存进度</el-button>
                </div>
              </div>
            </template>

            <div class="text-container" ref="textContainerRef">
              <div
                v-for="(sentence, sIdx) in sentences"
                :key="sIdx"
                class="sentence-block"
              >
                <span class="sentence-index">#{{ sIdx + 1 }}</span>
                <span
                  class="sentence-text"
                  @mouseup="onTextSelect($event, sIdx)"
                >{{ sentence }}</span>
              </div>
            </div>

            <!-- 实体类型选择浮层 -->
            <div
              v-if="selectionMenu.visible"
              class="selection-menu"
              :style="{ left: selectionMenu.x + 'px', top: selectionMenu.y + 'px' }"
            >
              <div class="selection-info">
                已选：「<span class="sel-text">{{ selectionMenu.text }}</span>」
              </div>
              <div class="selection-types">
                <el-tag
                  v-for="t in ENTITY_TYPES"
                  :key="t.name"
                  :color="t.color"
                  effect="dark"
                  size="small"
                  class="type-tag"
                  @click="addEntityFromSelection(t.name)"
                >
                  {{ t.name }}
                </el-tag>
              </div>
              <div class="selection-divider"></div>
              <div class="selection-actions">
                <el-button size="small" type="success" plain :icon="Connection" @click="markAsRelationType">
                  标记为关系类型
                </el-button>
              </div>
            </div>

            <div class="anno-tip">
              <el-icon><InfoFilled /></el-icon>
              <span>选中文本标注实体，或选中动词「标记为关系类型」。</span>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧：实体 + 关系标注列表 -->
        <el-col :span="12" class="anno-right-col">
          <el-card shadow="never" class="section-card anno-right-top-card">
            <template #header>
              <div class="card-header">
                <span class="header-title">
                  <el-icon><Collection /></el-icon>
                  实体标注列表（{{ annotatedEntities.length }}）
                </span>
              </div>
            </template>
            <el-table :data="annotatedEntities" border size="small" max-height="260">
              <el-table-column type="index" width="50" align="center" />
              <el-table-column prop="text" label="实体文本" min-width="120" />
              <el-table-column prop="type" label="类型" width="90">
                <template #default="{ row }">
                  <el-tag :color="typeColorMap[row.type]" effect="dark" size="small">{{ row.type }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="sentenceIdx" label="所在句子" width="80" align="center" />
              <el-table-column label="操作" width="70" align="center">
                <template #default="{ $index }">
                  <el-button size="small" link type="danger" @click="removeEntity($index)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <el-card shadow="never" class="section-card" style="margin-top: 12px">
            <template #header>
              <div class="card-header">
                <span class="header-title">
                  <el-icon><Connection /></el-icon>
                  关系标注列表（{{ annotatedRelations.length }}）
                </span>
              </div>
            </template>

            <!-- 关系构建器 -->
            <div class="relation-builder">
              <el-row :gutter="8">
                <el-col :span="7">
                  <div class="rb-field">
                    <span class="rb-label">头实体</span>
                    <el-select v-model="relationBuilder.headId" placeholder="选择头实体" filterable size="small" style="width: 100%">
                      <el-option
                        v-for="(e, i) in annotatedEntities"
                        :key="i"
                        :label="`${e.text} (${e.type})`"
                        :value="i"
                      />
                    </el-select>
                  </div>
                </el-col>
                <el-col :span="7">
                  <div class="rb-field">
                    <span class="rb-label">关系类型</span>
                    <el-select
                      v-model="relationBuilder.relation"
                      placeholder="选择或输入"
                      filterable
                      allow-create
                      default-first-option
                      size="small"
                      style="width: 100%"
                    >
                      <el-option v-for="r in relationTypeOptions" :key="r" :label="r" :value="r" />
                    </el-select>
                  </div>
                </el-col>
                <el-col :span="7">
                  <div class="rb-field">
                    <span class="rb-label">尾实体</span>
                    <el-select v-model="relationBuilder.tailId" placeholder="选择尾实体" filterable size="small" style="width: 100%">
                      <el-option
                        v-for="(e, i) in annotatedEntities"
                        :key="i"
                        :label="`${e.text} (${e.type})`"
                        :value="i"
                      />
                    </el-select>
                  </div>
                </el-col>
                <el-col :span="3">
                  <el-button
                    type="primary"
                    size="small"
                    :icon="Plus"
                    :disabled="!canAddRelation"
                    @click="addRelation"
                    style="width: 100%"
                  >
                    添加
                  </el-button>
                </el-col>
              </el-row>
            </div>

            <el-table :data="annotatedRelations" border size="small" max-height="220" style="margin-top: 10px">
              <el-table-column type="index" width="50" align="center" />
              <el-table-column prop="head" label="头实体" min-width="100" />
              <el-table-column prop="relation" label="关系" width="100">
                <template #default="{ row }">
                  <el-tag type="success" size="small">{{ row.relation }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="tail" label="尾实体" min-width="100" />
              <el-table-column label="操作" width="70" align="center">
                <template #default="{ $index }">
                  <el-button size="small" link type="danger" @click="removeRelation($index)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </template>

    <!-- 新建任务弹窗 -->
    <el-dialog v-model="createDialogVisible" title="新建标注任务" width="480px">
      <el-form :model="newTask" label-width="100px">
        <el-form-item label="任务名称">
          <el-input v-model="newTask.taskName" placeholder="如：三国人物关系标注" />
        </el-form-item>
        <el-form-item label="所属项目">
          <el-select v-model="newTask.projectId" placeholder="选择项目" style="width: 100%" @change="onProjectChange">
            <el-option v-for="p in projects" :key="p.id" :label="p.projectName" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="语料来源">
          <el-select v-model="newTask.corpusId" placeholder="选择语料" filterable style="width: 100%">
            <el-option v-for="c in corpusList" :key="c.id" :label="c.title" :value="c.id">
              <span style="display: inline-flex; justify-content: space-between; width: 100%; gap: 12px; align-items: center;">
                <span style="font-weight: 500; color: #1f2329;">{{ c.title }}</span>
                <span v-if="projectNameById(c.projectId)" style="color: #86909c; font-size: 12px; flex-shrink: 0;">
                  {{ projectNameById(c.projectId) }}
                </span>
              </span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="标注员">
          <el-input v-model="newTask.annotator" placeholder="标注员姓名" />
        </el-form-item>
        <el-form-item label="审核员">
          <el-input v-model="newTask.reviewer" placeholder="审核员姓名" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createTask">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Back, Check, Collection, Connection, Document, Download, InfoFilled, Plus, Refresh, Right } from '@element-plus/icons-vue'
import { annotationTaskApi, corpusApi, projectApi } from '@/api'

interface Project { id: number | string; projectName: string }
interface Corpus { id: number | string; title: string; content?: string; projectId?: number | string }
interface AnnotationTask {
  id: number
  taskName: string
  projectId: number | string
  corpusId: number | string
  corpusTitle: string
  annotator: string
  reviewer: string
  text: string
  totalSentences: number
  annotatedSentences: number
  entities?: AnnotatedEntity[]
  relations?: AnnotatedRelation[]
}
interface AnnotatedEntity {
  text: string
  type: string
  sentenceIdx: number
  start: number
  end: number
}
interface AnnotatedRelation {
  head: string
  headId: number
  relation: string
  tail: string
  tailId: number
}

// 实体类型配置（与图谱模型本体 Schema 对齐）
const ENTITY_TYPES = [
  { name: '人物', color: '#409eff' },
  { name: '地点', color: '#67c23a' },
  { name: '组织', color: '#e6a23c' },
  { name: '时间', color: '#f56c6c' },
  { name: '概念', color: '#9c27b0' },
  { name: '技术', color: '#00bcd4' },
  { name: '事件', color: '#ff9800' },
]
// 关系类型：预置常用类型 + 支持自定义输入（allow-create）
const RELATION_PRESETS = ['出生于', '就职于', '创立', '效力', '相识', '亲属', '师生', '合作', '战胜', '籍贯', '位于', '属于', '发明', '著作']
const customRelations = ref<string[]>([])
const relationTypeOptions = computed(() => {
  const set = new Set([...RELATION_PRESETS, ...customRelations.value, ...annotatedRelations.value.map(r => r.relation)])
  return Array.from(set)
})

const PALETTE = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#9c27b0', '#00bcd4', '#ff9800']
const typeColorMap = computed(() => {
  const map: Record<string, string> = {}
  ENTITY_TYPES.forEach((t, i) => { map[t.name] = PALETTE[i % PALETTE.length] })
  return map
})

// 任务列表
const tasks = ref<AnnotationTask[]>([])
const currentTaskId = ref<number>()
const currentTask = computed(() => tasks.value.find(t => t.id === currentTaskId.value))

const sentences = computed(() => {
  if (!currentTask.value) return []
  return currentTask.value.text.split(/(?<=[。！？；])/).map(s => s.trim()).filter(Boolean)
})

// 标注数据
const annotatedEntities = ref<AnnotatedEntity[]>([])
const annotatedRelations = ref<AnnotatedRelation[]>([])

// 撤销/重做栈
const undoStack = ref<string[]>([])
const redoStack = ref<string[]>([])
const canUndo = computed(() => undoStack.value.length > 0)
const canRedo = computed(() => redoStack.value.length > 0)

function snapshot() {
  undoStack.value.push(JSON.stringify({
    entities: annotatedEntities.value,
    relations: annotatedRelations.value,
  }))
  if (undoStack.value.length > 50) undoStack.value.shift()
  redoStack.value = []
}
function undo() {
  if (!canUndo.value) return
  const current = JSON.stringify({
    entities: annotatedEntities.value,
    relations: annotatedRelations.value,
  })
  redoStack.value.push(current)
  const prev = JSON.parse(undoStack.value.pop()!)
  annotatedEntities.value = prev.entities
  annotatedRelations.value = prev.relations
}
function redo() {
  if (!canRedo.value) return
  const current = JSON.stringify({
    entities: annotatedEntities.value,
    relations: annotatedRelations.value,
  })
  undoStack.value.push(current)
  const next = JSON.parse(redoStack.value.pop()!)
  annotatedEntities.value = next.entities
  annotatedRelations.value = next.relations
}

// 选中文本浮层
const selectionMenu = reactive({
  visible: false,
  x: 0,
  y: 0,
  text: '',
  sentenceIdx: -1,
  start: 0,
  end: 0,
})
const textContainerRef = ref<HTMLElement>()

function onTextSelect(event: MouseEvent, sentenceIdx: number) {
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0) {
    selectionMenu.visible = false
    return
  }
  const text = sel.toString().trim()
  if (!text) {
    selectionMenu.visible = false
    return
  }
  const sentence = sentences.value[sentenceIdx] || ''
  const start = sentence.indexOf(text)
  if (start < 0) {
    selectionMenu.visible = false
    return
  }
  selectionMenu.text = text
  selectionMenu.sentenceIdx = sentenceIdx
  selectionMenu.start = start
  selectionMenu.end = start + text.length
  const containerRect = textContainerRef.value?.getBoundingClientRect()
  selectionMenu.x = event.clientX - (containerRect?.left || 0)
  selectionMenu.y = event.clientY - (containerRect?.top || 0) - 60
  selectionMenu.visible = true
}

function addEntityFromSelection(type: string) {
  snapshot()
  annotatedEntities.value.push({
    text: selectionMenu.text,
    type,
    sentenceIdx: selectionMenu.sentenceIdx,
    start: selectionMenu.start,
    end: selectionMenu.end,
  })
  if (currentTask.value) {
    currentTask.value.annotatedSentences = new Set(annotatedEntities.value.map(e => e.sentenceIdx)).size
  }
  selectionMenu.visible = false
  window.getSelection()?.removeAllRanges()
  ElMessage.success(`已标注实体：${selectionMenu.text} (${type})`)
}

function removeEntity(idx: number) {
  snapshot()
  const removed = annotatedEntities.value[idx]
  annotatedEntities.value.splice(idx, 1)
  annotatedRelations.value = annotatedRelations.value.filter(r => r.headId !== idx && r.tailId !== idx)
  if (currentTask.value) {
    currentTask.value.annotatedSentences = new Set(annotatedEntities.value.map(e => e.sentenceIdx)).size
  }
  ElMessage.success(`已删除实体：${removed.text}`)
}

// 将选中的原文标记为关系类型，自动加入关系类型选项并填充关系构建器
function markAsRelationType() {
  const text = selectionMenu.text.trim()
  if (!text) return
  if (!RELATION_PRESETS.includes(text) && !customRelations.value.includes(text)) {
    customRelations.value.push(text)
  }
  relationBuilder.relation = text
  selectionMenu.visible = false
  window.getSelection()?.removeAllRanges()
  ElMessage.success(`已标记为关系类型：「${text}」，请在下方选择头/尾实体完成关系标注`)
}

// 关系构建
const relationBuilder = reactive({
  headId: undefined as number | undefined,
  relation: '',
  tailId: undefined as number | undefined,
})
const canAddRelation = computed(() =>
  relationBuilder.headId !== undefined &&
  relationBuilder.tailId !== undefined &&
  relationBuilder.relation &&
  relationBuilder.headId !== relationBuilder.tailId,
)
function addRelation() {
  if (!canAddRelation.value) return
  snapshot()
  const head = annotatedEntities.value[relationBuilder.headId!]
  const tail = annotatedEntities.value[relationBuilder.tailId!]
  // 记录自定义关系类型
  if (!RELATION_PRESETS.includes(relationBuilder.relation) && !customRelations.value.includes(relationBuilder.relation)) {
    customRelations.value.push(relationBuilder.relation)
  }
  annotatedRelations.value.push({
    head: head.text,
    headId: relationBuilder.headId!,
    relation: relationBuilder.relation,
    tail: tail.text,
    tailId: relationBuilder.tailId!,
  })
  relationBuilder.headId = undefined
  relationBuilder.relation = ''
  relationBuilder.tailId = undefined
  ElMessage.success('已添加关系标注')
}
function removeRelation(idx: number) {
  snapshot()
  annotatedRelations.value.splice(idx, 1)
}

// 进度
const annotationProgress = computed(() => {
  if (!currentTask.value || currentTask.value.totalSentences === 0) return 0
  return Math.round((currentTask.value.annotatedSentences / currentTask.value.totalSentences) * 100)
})
const progressTagType = computed(() => {
  const p = annotationProgress.value
  if (p >= 100) return 'success'
  if (p >= 50) return 'warning'
  return 'info'
})

const saving = ref(false)
async function saveProgress() {
  if (!currentTask.value) return
  saving.value = true
  try {
    currentTask.value.entities = [...annotatedEntities.value]
    currentTask.value.relations = [...annotatedRelations.value]
    currentTask.value.annotatedSentences = new Set(annotatedEntities.value.map(e => e.sentenceIdx)).size
    await annotationTaskApi.update({
      id: currentTask.value.id,
      entities: JSON.stringify(annotatedEntities.value),
      relations: JSON.stringify(annotatedRelations.value),
      totalSentences: currentTask.value.totalSentences,
      annotatedSentences: currentTask.value.annotatedSentences,
    })
    ElMessage.success('标注进度已保存到数据库')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}
function exportDataset() {
  const data = {
    task: currentTask.value?.taskName,
    entities: annotatedEntities.value,
    relations: annotatedRelations.value,
    exportedAt: new Date().toISOString(),
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `annotation-${currentTask.value?.taskName || 'dataset'}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('数据集已导出（JSON 格式）')
}

// 新建任务
const createDialogVisible = ref(false)
const projects = ref<Project[]>([])
const corpusList = ref<Corpus[]>([])
const newTask = reactive({
  taskName: '',
  projectId: undefined as number | string | undefined,
  corpusId: undefined as number | string | undefined,
  annotator: '',
  reviewer: '',
})

function openCreateTask() {
  newTask.taskName = ''
  newTask.projectId = undefined
  newTask.corpusId = undefined
  newTask.annotator = ''
  newTask.reviewer = ''
  createDialogVisible.value = true
  if (projects.value.length === 0) loadProjects()
  // 主动预载语料列表，避免下拉为空
  if (corpusList.value.length === 0) loadCorpusList()
}

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

function projectNameById(pid: any): string {
  if (!pid) return ''
  const p = projects.value.find((x) => x.id === pid || String(x.id) === String(pid))
  return p?.projectName || ''
}

async function loadProjects() {
  const res = await projectApi.list({ pageNum: 1, pageSize: 100 })
  projects.value = extractRecords(res).slice().reverse()
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

async function onProjectChange() {
  newTask.corpusId = undefined
  // 语料列表不按项目过滤，切换项目时仅清空已选语料，保证列表始终可见
  if (corpusList.value.length === 0) {
    await loadCorpusList()
  }
}

async function createTask() {
  if (!newTask.taskName || !newTask.projectId || !newTask.corpusId) {
    ElMessage.warning('请填写完整任务信息')
    return
  }
  const corpus = corpusList.value.find(c => c.id === newTask.corpusId)
  let text = SAMPLE_TEXT
  if (corpus) {
    try {
      const res = await corpusApi.get(corpus.id as number)
      text = res.data?.content || SAMPLE_TEXT
    } catch {
      text = SAMPLE_TEXT
    }
  }
  try {
    const res = await annotationTaskApi.add({
      taskName: newTask.taskName,
      projectId: newTask.projectId,
      corpusId: newTask.corpusId,
      corpusTitle: corpus?.title || '',
      text,
      annotator: newTask.annotator || '当前用户',
      reviewer: newTask.reviewer || '管理员',
    })
    const saved = res.data as AnnotationTask
    saved.entities = []
    saved.relations = []
    saved.totalSentences = text.split(/(?<=[。！？；])/).filter(s => s.trim()).length
    saved.annotatedSentences = 0
    tasks.value.unshift(saved)
    currentTaskId.value = saved.id
    annotatedEntities.value = []
    annotatedRelations.value = []
    undoStack.value = []
    redoStack.value = []
    createDialogVisible.value = false
    ElMessage.success('标注任务已创建并保存到数据库')
  } catch (e) {
    ElMessage.error('创建任务失败')
  }
}

// ============ 解析数据库返回的 JSON 字段 ============
function parseJsonArray<T>(raw: any): T[] {
  if (!raw) return []
  if (Array.isArray(raw)) return raw as T[]
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }
  return []
}

function onTaskChange() {
  if (currentTask.value) {
    annotatedEntities.value = parseJsonArray<AnnotatedEntity>(currentTask.value.entities)
    annotatedRelations.value = parseJsonArray<AnnotatedRelation>(currentTask.value.relations)
  } else {
    annotatedEntities.value = []
    annotatedRelations.value = []
  }
  undoStack.value = []
  redoStack.value = []
}

// 初始化一个示例任务（无数据库数据时占位）
const SAMPLE_TEXT = `诸葛亮，字孔明，号卧龙，是三国时期蜀汉的杰出政治家与军事家。他出生于琅琊阳都，早年隐居于南阳隆中。刘备三顾茅庐后，诸葛亮出山辅佐刘备建立蜀汉政权。建兴五年，诸葛亮率军北伐曹魏，驻扎于汉中。`

async function loadTasks() {
  try {
    const res = await annotationTaskApi.list({ pageNum: 1, pageSize: 100 })
    const records = res.data?.records || res.data || []
    if (records.length === 0) {
      // 数据库无数据时使用示例任务占位（不写库，仅本地预览）
      const task: AnnotationTask = {
        id: -1,
        taskName: '三国人物关系标注（示例）',
        projectId: 1,
        corpusId: 1,
        corpusTitle: '三国人物语料',
        annotator: '当前用户',
        reviewer: '管理员',
        text: SAMPLE_TEXT,
        totalSentences: SAMPLE_TEXT.split(/(?<=[。！？；])/).filter(s => s.trim()).length,
        annotatedSentences: 0,
        entities: [],
        relations: [],
      }
      tasks.value = [task]
      currentTaskId.value = task.id
      annotatedEntities.value = []
      annotatedRelations.value = []
      return
    }
    tasks.value = records as AnnotationTask[]
    // 默认选中第一个任务，并加载其标注数据
    currentTaskId.value = tasks.value[0].id
    onTaskChange()
  } catch (e) {
    // 接口异常时使用示例任务
    const task: AnnotationTask = {
      id: -1,
      taskName: '三国人物关系标注（示例）',
      projectId: 1,
      corpusId: 1,
      corpusTitle: '三国人物语料',
      annotator: '当前用户',
      reviewer: '管理员',
      text: SAMPLE_TEXT,
      totalSentences: SAMPLE_TEXT.split(/(?<=[。！？；])/).filter(s => s.trim()).length,
      annotatedSentences: 0,
      entities: [],
      relations: [],
    }
    tasks.value = [task]
    currentTaskId.value = task.id
    annotatedEntities.value = []
    annotatedRelations.value = []
  }
}

onMounted(() => {
  loadTasks()
  document.addEventListener('click', onDocumentClick)
})

function onDocumentClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.selection-menu') && !target.closest('.sentence-text')) {
    selectionMenu.visible = false
  }
}
</script>

<style scoped>
.data-annotation {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.anno-main-row {
  align-items: stretch;
}

/* 左右两列等宽等高 */
.anno-main-row :deep(.el-col) {
  display: flex;
  flex-direction: column;
}

.anno-equal-card {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.anno-equal-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.anno-right-col {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.anno-right-top-card {
  flex: 1;
}

.anno-left-card :deep(.el-card__body) {
  max-height: 520px;
  overflow-y: auto;
}

.toolbar-card {
  flex-shrink: 0;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.empty-state {
  padding: 60px 0;
}

.section-card {
  width: 100%;
}

.text-container {
  position: relative;
  max-height: 320px;
  overflow-y: auto;
  padding: 12px;
  background: #f7f8fa;
  border: 1px solid #f0f2f5;
  border-radius: 8px;
  line-height: 2;
  font-size: 14px;
}

.sentence-block {
  margin-bottom: 10px;
  padding: 6px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.sentence-block:hover {
  background: #fff;
}

.sentence-index {
  display: inline-block;
  width: 32px;
  color: #909399;
  font-size: 12px;
  user-select: none;
}

.sentence-text {
  cursor: text;
  user-select: text;
}

.selection-menu {
  position: absolute;
  z-index: 100;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  padding: 8px 10px;
  min-width: 220px;
}

.selection-info {
  font-size: 12px;
  color: #606266;
  margin-bottom: 6px;
}

.sel-text {
  color: #165dff;
  font-weight: 600;
}

.selection-types {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.selection-divider {
  height: 1px;
  background: #e5e6eb;
  margin: 8px 0;
}

.selection-actions {
  display: flex;
  justify-content: center;
}

.type-tag {
  cursor: pointer;
  color: #fff;
}

.anno-tip {
  margin-top: 10px;
  padding: 8px 10px;
  background: #ecf5ff;
  border-radius: 4px;
  font-size: 12px;
  color: #409eff;
  display: flex;
  align-items: center;
  gap: 4px;
}

.relation-builder {
  padding: 14px;
  background: #f7f8fa;
  border-radius: 8px;
}

.rb-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rb-label {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
}
</style>
