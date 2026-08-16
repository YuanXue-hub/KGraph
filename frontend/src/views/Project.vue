<template>
  <div class="page-container">
    <div class="kg-card">
      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="keyword"
            placeholder="搜索项目名称"
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
          <el-button type="primary" :icon="Plus" @click="openAdd">新建项目</el-button>
        </div>
      </div>

      <!-- 表格 -->
      <div class="table-wrap">
        <el-table
          v-loading="loading"
          :data="filteredList"
          style="width: 100%"
          :header-cell-style="{ background: 'transparent' }"
        >
          <el-table-column type="index" label="" width="56" align="center" />
          <el-table-column prop="projectName" label="项目名称" min-width="180">
            <template #default="{ row }">
              <div class="cell-project" @click="goModel(row)">
                <div class="project-icon">
                  <el-icon><FolderOpened /></el-icon>
                </div>
                <div class="project-info">
                  <span class="project-name">{{ row.projectName }}</span>
                  <span class="project-desc">{{ row.projectDescription || '暂无描述' }}</span>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="createByName" label="创建人" width="120" align="center">
            <template #default="{ row }">
              <div class="user-cell">
                <el-avatar :size="22" class="user-avatar">{{ (row.createByName || 'U').charAt(0).toUpperCase() }}</el-avatar>
                <span>{{ row.createByName || '-' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="storageEngine" label="存储引擎" width="110" align="center">
            <template #default="{ row }">
              <el-tag size="small" type="info" effect="plain">{{ row.storageEngine || 'neo4j' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="存储配置" width="100" align="center">
            <template #default="{ row }">
              <span class="status-dot" :class="row.isConfiguredStorage ? 'success' : 'muted'"></span>
              <span class="status-text">{{ row.isConfiguredStorage ? '已配置' : '未配置' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="存储空间" width="100" align="center">
            <template #default="{ row }">
              <span class="status-dot" :class="row.isGraphSpaceCreated ? 'success' : 'muted'"></span>
              <span class="status-text">{{ row.isGraphSpaceCreated ? '已创建' : '未创建' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="createTime" label="创建时间" width="170" align="center">
            <template #default="{ row }">
              <span class="time-cell">{{ formatTime(row.createTime) }}</span>
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
              <el-icon :size="40" color="#c9cdd4"><FolderOpened /></el-icon>
              <p class="empty-title">暂无知识图谱项目</p>
              <p class="empty-desc">点击右上角「新建项目」开始构建你的第一个知识图谱</p>
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

    <!-- 新建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑项目' : '新建项目'"
      width="520px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="项目名称" prop="projectName">
          <el-input v-model="form.projectName" placeholder="请输入项目名称" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="项目描述" prop="projectDescription">
          <el-input
            v-model="form.projectDescription"
            type="textarea"
            :rows="4"
            placeholder="请输入项目描述"
            maxlength="500"
            show-word-limit
          />
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
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Edit, Delete, Search, Refresh, FolderOpened } from '@element-plus/icons-vue'
import { projectApi } from '@/api'

interface Project {
  id: number
  projectName: string
  projectDescription: string
  storageEngine?: string
  isConfiguredStorage?: number | boolean
  isGraphSpaceCreated?: number | boolean
  createBy?: number
  createByName?: string
  createTime: string
  updateTime?: string
}

const router = useRouter()
const loading = ref(false)
const list = ref<Project[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const keyword = ref('')

const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = ref({
  id: 0,
  projectName: '',
  projectDescription: ''
})

const rules: FormRules = {
  projectName: [{ required: true, message: '请输入项目名称', trigger: 'blur' }]
}

const filteredList = computed(() => {
  if (!keyword.value) return list.value
  return list.value.filter((item) =>
    item.projectName.toLowerCase().includes(keyword.value.toLowerCase())
  )
})

async function loadList() {
  loading.value = true
  try {
    const res = await projectApi.list({ pageNum: pageNum.value, pageSize: pageSize.value })
    list.value = res.data?.records || res.data || []
    total.value = res.data?.total || list.value.length
  } finally {
    loading.value = false
  }
}

function openAdd() {
  isEdit.value = false
  form.value = { id: 0, projectName: '', projectDescription: '' }
  dialogVisible.value = true
}

function openEdit(row: Project) {
  isEdit.value = true
  form.value = {
    id: row.id,
    projectName: row.projectName,
    projectDescription: row.projectDescription
  }
  dialogVisible.value = true
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
    if (isEdit.value) {
      await projectApi.update({
        id: form.value.id,
        projectName: form.value.projectName,
        projectDescription: form.value.projectDescription
      })
      ElMessage.success('编辑成功')
    } else {
      await projectApi.add({
        projectName: form.value.projectName,
        projectDescription: form.value.projectDescription
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadList()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: Project) {
  try {
    await ElMessageBox.confirm(`确定要删除项目「${row.projectName}」吗？`, '提示', {
      type: 'warning'
    })
    await projectApi.delete(row.id)
    ElMessage.success('删除成功')
    loadList()
  } catch {
    // 取消
  }
}

function goModel(row: Project) {
  router.push({ path: '/model', query: { projectId: String(row.id) } })
}

function formatTime(t?: string): string {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

onMounted(() => {
  loadList()
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

.search-input {
  width: 260px;
}

.table-wrap {
  padding: 4px 12px 8px;
}

/* 项目名称单元格 */
.cell-project {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  padding: 4px 0;
}

.project-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #e8f3ff 0%, #eef0ff 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #165dff;
  font-size: 18px;
  flex-shrink: 0;
  transition: all 0.2s;
}

.cell-project:hover .project-icon {
  background: linear-gradient(135deg, #165dff 0%, #6366f1 100%);
  color: #fff;
  transform: scale(1.05);
}

.project-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.project-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
  line-height: 1.4;
  transition: color 0.2s;
}

.cell-project:hover .project-name {
  color: #165dff;
}

.project-desc {
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.4;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 用户单元格 */
.user-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-2);
}

.user-avatar {
  background: linear-gradient(135deg, #165dff 0%, #6366f1 100%);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
}

/* 状态点 */
.status-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}

.status-dot.success {
  background: #00b42c;
  box-shadow: 0 0 0 3px rgba(0, 180, 44, 0.12);
}

.status-dot.muted {
  background: #c9cdd4;
}

.status-text {
  font-size: 12px;
  color: var(--text-2);
  vertical-align: middle;
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
</style>
