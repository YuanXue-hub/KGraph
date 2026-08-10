<template>
  <div class="page-container">
    <h2 class="page-title">知识图谱管理</h2>

    <el-card shadow="never">
      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索项目名称"
          style="width: 240px"
          clearable
          @clear="loadList"
          @keyup.enter="loadList"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" :icon="Plus" @click="openAdd">新建项目</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="filteredList"
        border
        stripe
        style="width: 100%"
      >
        <el-table-column type="index" label="#" width="60" align="center" />
        <el-table-column prop="projectName" label="项目名称" min-width="160">
          <template #default="{ row }">
            <el-link type="primary" @click="goModel(row)">{{ row.projectName }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="projectDescription" label="项目描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="createByName" label="创建人" width="120" align="center">
          <template #default="{ row }">
            {{ row.createByName || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="storageEngine" label="存储引擎" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.storageEngine || 'neo4j' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="已配置存储" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.isConfiguredStorage ? 'success' : 'info'" size="small">
              {{ row.isConfiguredStorage ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="已建存储空间" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.isGraphSpaceCreated ? 'success' : 'info'" size="small">
              {{ row.isGraphSpaceCreated ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" width="170" align="center">
          <template #default="{ row }">
            {{ formatTime(row.createTime) }}
          </template>
        </el-table-column>
        <el-table-column prop="updateTime" label="更新时间" width="170" align="center">
          <template #default="{ row }">
            {{ formatTime(row.updateTime) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" :icon="Delete" @click="handleDelete(row)">删除</el-button>
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

    <!-- 新建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑项目' : '新建项目'"
      width="520px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="项目名称" prop="projectName">
          <el-input v-model="form.projectName" placeholder="请输入项目名称" maxlength="50" />
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
import { Plus, Edit, Delete, Search } from '@element-plus/icons-vue'
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
  // 通过 query 传递 projectId
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
.page-container {
  padding: 20px;
}
</style>
