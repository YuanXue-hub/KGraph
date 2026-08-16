<template>
  <div class="page-container">
    <div class="kg-card">
      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-left">
          <el-select
            v-model="projectId"
            placeholder="按项目筛选"
            clearable
            filterable
            class="filter-select"
            @change="loadList"
          >
            <el-option v-for="p in projects" :key="p.id" :label="p.projectName" :value="p.id" />
          </el-select>
          <el-input
            v-model="keyword"
            placeholder="搜索标题"
            class="search-input"
            clearable
            @clear="loadList"
            @keyup.enter="loadList"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        <div class="toolbar-right">
          <el-button :icon="Refresh" circle @click="loadList" />
          <el-button type="primary" :icon="Plus" @click="openAdd">新增语料</el-button>
        </div>
      </div>

      <!-- 表格 -->
      <div class="table-wrap">
        <el-table v-loading="loading" :data="filteredList" style="width: 100%">
          <el-table-column type="index" label="" width="56" align="center" />
          <el-table-column prop="title" label="标题" min-width="200">
            <template #default="{ row }">
              <div class="cell-corpus" @click="viewContent(row)">
                <div class="corpus-icon" :class="row.source === 'file' ? 'file-icon' : 'text-icon'">
                  <el-icon v-if="row.source === 'file'">
                    <Document v-if="row.fileType === 'pdf'" />
                    <Tickets v-else />
                  </el-icon>
                  <el-icon v-else><EditPen /></el-icon>
                </div>
                <div class="corpus-info">
                  <span class="corpus-title">{{ row.title }}</span>
                  <span class="corpus-source">
                    {{ row.source === 'file' ? (row.fileType || '文档').toUpperCase() + ' 文档' : '文本输入' }}
                  </span>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="140" align="center">
            <template #default="{ row }">
              <div class="status-cell">
                <span class="status-dot" :class="statusDotClass(row)"></span>
                <span class="status-text" :class="statusTextClass(row)">{{ statusText(row) }}</span>
                <el-icon v-if="effectiveStatus(row) === 0" class="is-loading status-spin"><Loading /></el-icon>
              </div>
              <el-tooltip v-if="effectiveStatus(row) === 2 && row.errorMsg" :content="row.errorMsg" placement="top">
                <el-icon class="error-icon"><WarningFilled /></el-icon>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="createTime" label="创建时间" width="170" align="center">
            <template #default="{ row }">
              <span class="time-cell">{{ formatTime(row.createTime) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="260" align="center" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 1 || row.source !== 'file'"
                size="small"
                @click="viewContent(row)"
              >查看</el-button>
              <el-button
                v-if="row.status === 2"
                size="small"
                type="warning"
                @click="handleReparse(row)"
              >重新解析</el-button>
              <el-button
                v-if="row.status === 1 || row.source !== 'file'"
                size="small"
                @click="openEdit(row)"
              >编辑</el-button>
              <el-button
                size="small"
                type="danger"
                @click="handleDelete(row)"
              >删除</el-button>
            </template>
          </el-table-column>

          <template #empty>
            <div class="empty-state">
              <el-icon :size="40" color="#c9cdd4"><Document /></el-icon>
              <p class="empty-title">暂无语料数据</p>
              <p class="empty-desc">点击右上角「新增语料」上传文档或输入文本</p>
            </div>
          </template>
        </el-table>
      </div>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pageNum"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadList"
          @current-change="loadList"
        />
      </div>
    </div>

    <!-- 新增语料对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑语料' : '新增语料'" width="640px" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="所属项目" v-if="!isEdit">
          <el-select v-model="form.projectId" placeholder="选择项目" filterable style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.projectName" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入标题" maxlength="100" show-word-limit />
        </el-form-item>

        <!-- 输入方式切换（仅新增时显示，小尺寸 segmented control） -->
        <el-form-item label="输入方式" v-if="!isEdit">
          <div class="mode-segment">
            <button
              type="button"
              class="seg-btn"
              :class="{ active: inputMode === 'text' }"
              @click="inputMode = 'text'"
            >
              <el-icon><EditPen /></el-icon>
              <span>文本输入</span>
            </button>
            <button
              type="button"
              class="seg-btn"
              :class="{ active: inputMode === 'file' }"
              @click="inputMode = 'file'"
            >
              <el-icon><Upload /></el-icon>
              <span>文档上传</span>
            </button>
          </div>
        </el-form-item>

        <!-- 文本输入模式 -->
        <el-form-item label="内容" prop="content" v-if="inputMode === 'text' || isEdit">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="10"
            placeholder="请输入语料内容"
          />
        </el-form-item>

        <!-- 文档上传模式 -->
        <el-form-item label="文档" v-if="inputMode === 'file' && !isEdit">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            accept=".pdf,.doc,.docx"
            drag
            class="corpus-upload"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              将文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">支持 PDF、DOC、DOCX 格式，上传后自动调用 MinerU 解析</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ inputMode === 'file' && !isEdit ? '上传并解析' : '确定' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 查看内容 -->
    <el-dialog v-model="viewDialog" title="语料内容" width="640px">
      <div class="view-content">
        <h3 class="view-title">{{ currentRow?.title }}</h3>
        <p class="view-meta">
          <el-tag size="small" type="info" effect="plain">
            {{ currentRow?.source === 'file' ? (currentRow?.fileType || '文档').toUpperCase() + ' 文档' : '文本输入' }}
          </el-tag>
          <span class="view-time">{{ formatTime(currentRow?.createTime) }}</span>
        </p>
        <div class="view-text" v-if="currentRow?.content">{{ currentRow.content }}</div>
        <div class="view-empty" v-else>
          <el-icon :size="32" color="#c9cdd4"><Loading /></el-icon>
          <p>正在解析中，请稍后刷新查看...</p>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, type UploadInstance } from 'element-plus'
import {
  Plus, Edit, Delete, View, Search, Refresh, RefreshRight,
  Document, EditPen, Upload, UploadFilled, Tickets, Loading, WarningFilled
} from '@element-plus/icons-vue'
import { projectApi, corpusApi } from '@/api'

interface Project { id: number; projectName: string }
interface Corpus {
  id: number
  title: string
  content: string
  source?: string
  filePath?: string
  fileType?: string
  status?: number
  errorMsg?: string
  createTime: string
}

const projects = ref<Project[]>([])
const projectId = ref<number | undefined>()
const list = ref<Corpus[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const loading = ref(false)

const dialogVisible = ref(false)
const viewDialog = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const uploadRef = ref<UploadInstance>()
const currentRow = ref<Corpus | null>(null)
const inputMode = ref<'text' | 'file'>('text')
const selectedFile = ref<File | null>(null)

let pollTimer: ReturnType<typeof setInterval> | null = null

const form = ref({
  id: 0,
  projectId: undefined as number | undefined,
  title: '',
  content: '',
  source: ''
})

const rules = computed<FormRules>(() => {
  const r: FormRules = {
    title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
    projectId: [{ required: true, message: '请选择项目', trigger: 'change' }]
  }
  if (inputMode.value === 'text' || isEdit.value) {
    r.content = [{ required: true, message: '请输入内容', trigger: 'blur' }]
  }
  return r
})

const filteredList = computed(() => {
  if (!keyword.value) return list.value
  return list.value.filter((i) => i.title.toLowerCase().includes(keyword.value.toLowerCase()))
})

async function loadProjects() {
  const res = await projectApi.list({ pageNum: 1, pageSize: 100 })
  projects.value = res.data?.records || res.data || []
}

async function loadList() {
  loading.value = true
  try {
    const res = await corpusApi.list({
      projectId: projectId.value,
      pageNum: pageNum.value,
      pageSize: pageSize.value
    })
    list.value = res.data?.records || res.data || []
    total.value = Number(res.data?.total) || list.value.length
    // 如果有处理中的语料，启动轮询
    checkPolling()
  } finally {
    loading.value = false
  }
}

function checkPolling() {
  const hasProcessing = list.value.some((item: Corpus) => item.source === 'file' && item.status === 0)
  if (hasProcessing && !pollTimer) {
    pollTimer = setInterval(async () => {
      const res = await corpusApi.list({
        projectId: projectId.value,
        pageNum: pageNum.value,
        pageSize: pageSize.value
      })
      const freshList = res.data?.records || res.data || []
      list.value = freshList
      // 如果没有文档类型处理中的了，停止轮询
      if (!freshList.some((item: Corpus) => item.source === 'file' && item.status === 0)) {
        stopPolling()
      }
    }, 5000)
  } else if (!hasProcessing) {
    stopPolling()
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function openAdd() {
  isEdit.value = false
  inputMode.value = 'text'
  selectedFile.value = null
  form.value = { id: 0, projectId: projectId.value, title: '', content: '', source: '' }
  dialogVisible.value = true
}

async function openEdit(row: Corpus) {
  isEdit.value = true
  const res = await corpusApi.get(row.id)
  const detail = res.data
  form.value = {
    id: row.id,
    projectId: detail.projectId || projectId.value,
    title: detail.title || row.title,
    content: detail.content || '',
    source: detail.source || row.source || ''
  }
  dialogVisible.value = true
}

function handleFileChange(file: any) {
  selectedFile.value = file.raw
}

function handleFileRemove() {
  selectedFile.value = null
}

function resetForm() {
  selectedFile.value = null
  inputMode.value = 'text'
  formRef.value?.resetFields()
}

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  // 文档上传模式
  if (inputMode.value === 'file' && !isEdit.value) {
    if (!selectedFile.value) {
      ElMessage.warning('请选择要上传的文件')
      return
    }
    submitting.value = true
    try {
      await corpusApi.upload(selectedFile.value, form.value.projectId!, form.value.title || undefined)
      ElMessage.success('文件已上传，正在后台解析...')
      dialogVisible.value = false
      loadList()
    } catch {
      ElMessage.error('上传失败')
    } finally {
      submitting.value = false
    }
    return
  }

  // 文本输入模式
  submitting.value = true
  try {
    if (isEdit.value) {
      await corpusApi.update({ id: form.value.id, title: form.value.title, content: form.value.content })
      ElMessage.success('编辑成功')
    } else {
      await corpusApi.add({
        projectId: form.value.projectId!,
        title: form.value.title,
        content: form.value.content
      })
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    loadList()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: Corpus) {
  try {
    await ElMessageBox.confirm(`确定删除语料「${row.title}」？`, '提示', { type: 'warning' })
    await corpusApi.delete(row.id)
    ElMessage.success('删除成功')
    loadList()
  } catch {}
}

async function handleReparse(row: Corpus) {
  try {
    await ElMessageBox.confirm(`确定重新解析「${row.title}」？`, '提示', { type: 'warning' })
    await corpusApi.reparse(row.id)
    ElMessage.success('已提交重新解析')
    loadList()
  } catch {}
}

function viewContent(row: Corpus) {
  // 处理中的语料点击刷新获取最新内容
  if (row.status === 0) {
    corpusApi.get(row.id).then((res) => {
      currentRow.value = res.data
      viewDialog.value = true
    })
  } else {
    currentRow.value = row
    viewDialog.value = true
  }
}

/**
 * 有效状态：文本类型（source !== 'file'）永远视为已完成(1)
 * 文档类型按实际 status 显示
 */
function effectiveStatus(row: Corpus): number {
  if (row.source !== 'file') return 1
  return row.status ?? 0
}

function statusText(row: Corpus) {
  const s = effectiveStatus(row)
  const map: Record<number, string> = { 0: '处理中', 1: '已完成', 2: '失败' }
  return map[s] || '处理中'
}
function statusDotClass(row: Corpus) {
  const s = effectiveStatus(row)
  const map: Record<number, string> = { 0: 'warning', 1: 'success', 2: 'danger' }
  return map[s] || 'warning'
}
function statusTextClass(row: Corpus) {
  const s = effectiveStatus(row)
  const map: Record<number, string> = { 0: 'text-warning', 1: 'text-success', 2: 'text-danger' }
  return map[s] || 'text-warning'
}
function formatTime(t?: string) {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

onMounted(() => {
  loadProjects()
  loadList()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 18px;
}

.page-head-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  margin: 0;
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-3);
  font-weight: 400;
}

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
}

.toolbar-right {
  display: flex;
  gap: 8px;
  align-items: center;
}

.filter-select {
  width: 200px;
}

.search-input {
  width: 220px;
}

.table-wrap {
  padding: 4px 12px 8px;
}

/* 语料单元格 */
.cell-corpus {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  padding: 4px 0;
}

.corpus-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  transition: all 0.2s;
}

.corpus-icon.text-icon {
  background: linear-gradient(135deg, #e8f3ff 0%, #eef0ff 100%);
  color: #165dff;
}

.corpus-icon.file-icon {
  background: linear-gradient(135deg, #fff7e8 0%, #fff1f0 100%);
  color: #ff7d00;
}

.cell-corpus:hover .corpus-icon {
  transform: scale(1.05);
  filter: brightness(1.1);
}

.cell-corpus:hover .text-icon {
  background: linear-gradient(135deg, #165dff 0%, #6366f1 100%);
  color: #fff;
}

.cell-corpus:hover .file-icon {
  background: linear-gradient(135deg, #ff7d00 0%, #fa8c16 100%);
  color: #fff;
}

.corpus-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.corpus-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
  line-height: 1.4;
  transition: color 0.2s;
}

.cell-corpus:hover .corpus-title {
  color: #165dff;
}

.corpus-source {
  font-size: 12px;
  color: var(--text-3);
}

/* 状态单元格 */
.status-cell {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.status-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.status-dot.success {
  background: #00b42c;
  box-shadow: 0 0 0 3px rgba(0, 180, 44, 0.12);
}

.status-dot.warning {
  background: #ff7d00;
  box-shadow: 0 0 0 3px rgba(255, 125, 0, 0.12);
}

.status-dot.danger {
  background: #f53f3f;
  box-shadow: 0 0 0 3px rgba(245, 63, 63, 0.12);
}

.status-text {
  font-size: 12px;
}

.status-text.text-success {
  color: #00b42c;
}

.status-text.text-warning {
  color: #ff7d00;
}

.status-text.text-danger {
  color: #f53f3f;
}

.status-spin {
  font-size: 12px;
  color: #ff7d00;
}

.error-icon {
  font-size: 13px;
  color: #f53f3f;
  margin-left: 4px;
  cursor: help;
}

.time-cell {
  font-size: 12px;
  color: var(--text-3);
  font-variant-numeric: tabular-nums;
}

/* 空态 */
.empty-state {
  padding: 48px 20px;
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

.pagination-wrapper {
  padding: 12px 20px 16px;
  margin: 0;
  border-top: 1px solid var(--border-2);
}

/* 输入方式切换（小尺寸 segmented control） */
.mode-segment {
  display: inline-flex;
  gap: 4px;
  background: var(--border-2);
  padding: 2px;
  border-radius: 6px;
}

.seg-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-3);
  background: transparent;
  transition: all 0.2s var(--ease);
  font-weight: 500;
  line-height: 1.4;
}

.seg-btn .el-icon {
  font-size: 13px;
}

.seg-btn:hover {
  color: var(--brand-primary);
}

.seg-btn.active {
  background: #fff;
  color: var(--brand-primary);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 21, 41, 0.08);
}

/* 上传区 */
.corpus-upload {
  width: 100%;
}

.corpus-upload :deep(.el-upload-dragger) {
  width: 100%;
  border-radius: var(--r-md);
  transition: border-color 0.2s;
}

.corpus-upload :deep(.el-upload-dragger:hover) {
  border-color: var(--brand-primary);
}

/* 查看内容弹窗 */
.view-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.view-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-1);
  margin: 0;
}

.view-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-3);
  font-size: 12px;
  margin: 0;
}

.view-text {
  white-space: pre-wrap;
  line-height: 1.8;
  background: #fafbfc;
  padding: 16px;
  border-radius: var(--r-md);
  border: 1px solid var(--border-2);
  max-height: 400px;
  overflow: auto;
  font-size: 13px;
  color: var(--text-2);
}

.view-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px;
  color: var(--text-3);
  font-size: 13px;
}

.view-empty .is-loading {
  animation: spin 1.5s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
