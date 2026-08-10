<template>
  <div class="page-container">
    <h2 class="page-title">语料管理</h2>

    <el-card shadow="never">
      <div class="toolbar">
        <div class="filter-row">
          <el-select
            v-model="projectId"
            placeholder="按项目筛选"
            clearable
            filterable
            style="width: 220px"
            @change="loadList"
          >
            <el-option v-for="p in projects" :key="p.id" :label="p.projectName" :value="p.id" />
          </el-select>
          <el-input
            v-model="keyword"
            placeholder="搜索标题"
            style="width: 220px"
            clearable
            @clear="loadList"
            @keyup.enter="loadList"
          />
        </div>
        <el-button type="primary" :icon="Plus" @click="openAdd">新增语料</el-button>
      </div>

      <el-table v-loading="loading" :data="filteredList" border stripe>
        <el-table-column type="index" label="#" width="60" align="center" />
        <el-table-column prop="title" label="标题" min-width="160" />
        <el-table-column prop="source" label="来源" width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" width="180">
          <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" align="center" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" link type="primary" :icon="View" @click="viewContent(row)">查看</el-button>
              <el-button size="small" link type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
              <el-button size="small" link type="danger" :icon="Delete" @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

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
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑语料' : '新增语料'" width="640px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="所属项目" v-if="!isEdit">
          <el-select v-model="form.projectId" placeholder="选择项目" filterable style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.projectName" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入标题" />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="form.source" placeholder="如：新闻、论文、百科" />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="10"
            placeholder="请输入语料内容"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 查看内容 -->
    <el-dialog v-model="viewDialog" title="语料内容" width="640px">
      <div class="view-content">
        <h3>{{ currentRow?.title }}</h3>
        <p class="view-meta">
          <el-tag size="small">{{ currentRow?.source || '未知来源' }}</el-tag>
          <span class="view-time">{{ formatTime(currentRow?.createTime) }}</span>
        </p>
        <div class="view-text">{{ currentRow?.content }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Edit, Delete, View } from '@element-plus/icons-vue'
import { projectApi, corpusApi } from '@/api'

interface Project { id: number; projectName: string }
interface Corpus {
  id: number
  title: string
  content: string
  source?: string
  status?: number
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
const currentRow = ref<Corpus | null>(null)

const form = ref({
  id: 0,
  projectId: undefined as number | undefined,
  title: '',
  content: '',
  source: ''
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
  projectId: [{ required: true, message: '请选择项目', trigger: 'change' }]
}

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
    total.value = res.data?.total || list.value.length
  } finally {
    loading.value = false
  }
}

function openAdd() {
  isEdit.value = false
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

async function handleSubmit() {
  if (!formRef.value) return
  try { await formRef.value.validate() } catch { return }
  submitting.value = true
  try {
    if (isEdit.value) {
      await corpusApi.update({ id: form.value.id, title: form.value.title, content: form.value.content })
      ElMessage.success('编辑成功')
    } else {
      await corpusApi.add({
        projectId: form.value.projectId!,
        title: form.value.title,
        content: form.value.content,
        source: form.value.source
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

function viewContent(row: Corpus) {
  currentRow.value = row
  viewDialog.value = true
}

function statusText(s?: number) {
  const map: Record<number, string> = { 0: '待处理', 1: '已处理', 2: '处理中' }
  return map[s ?? 0] || '待处理'
}
function statusType(s?: number) {
  const map: Record<number, string> = { 0: 'info', 1: 'success', 2: 'warning' }
  return map[s ?? 0] || 'info'
}
function formatTime(t?: string) {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

onMounted(() => {
  loadProjects()
  loadList()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
}
.filter-row {
  display: flex;
  gap: 12px;
}
.row-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.row-actions .el-button + .el-button {
  margin-left: 0;
}
.view-content h3 {
  font-size: 18px;
  margin-bottom: 8px;
}
.view-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  color: #909399;
  font-size: 13px;
}
.view-text {
  white-space: pre-wrap;
  line-height: 1.8;
  background: #fafafa;
  padding: 12px;
  border-radius: 4px;
  border: 1px solid #ebeef5;
  max-height: 400px;
  overflow: auto;
}
</style>
