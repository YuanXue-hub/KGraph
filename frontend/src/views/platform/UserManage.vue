<template>
  <div class="user-manage-page">
    <!-- 无权限提示 -->
    <el-empty v-if="!isAdmin" description="无权限：仅管理员可访问用户管理页面" />

    <template v-else>
      <!-- 搜索栏 -->
      <el-card shadow="never" class="search-card">
        <el-form :inline="true" class="search-form" @submit.prevent>
          <el-form-item label="用户名">
            <el-input
              v-model="searchForm.userName"
              placeholder="请输入用户名"
              clearable
              style="width: 180px"
              @keyup.enter="handleSearch"
            />
          </el-form-item>
          <el-form-item label="账号">
            <el-input
              v-model="searchForm.userAccount"
              placeholder="请输入账号"
              clearable
              style="width: 180px"
              @keyup.enter="handleSearch"
            />
          </el-form-item>
          <el-form-item label="角色">
            <el-select
              v-model="searchForm.userRole"
              placeholder="全部"
              clearable
              style="width: 140px"
            >
              <el-option label="全部" value="" />
              <el-option label="管理员" value="admin" />
              <el-option label="普通用户" value="user" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
            <el-button :icon="Refresh" @click="handleReset">重置</el-button>
            <el-button type="success" :icon="Plus" @click="openAdd">新增用户</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 用户表格 -->
      <el-card shadow="never">
        <el-table
          v-loading="loading"
          :data="tableData"
          border
          stripe
          highlight-current-row
        >
          <el-table-column label="头像" width="80" align="center">
            <template #default="{ row }">
              <el-avatar :size="32" :src="row.userAvatar" />
            </template>
          </el-table-column>
          <el-table-column prop="userAccount" label="账号" min-width="140" show-overflow-tooltip />
          <el-table-column prop="userName" label="昵称" min-width="140" show-overflow-tooltip />
          <el-table-column label="角色" width="110" align="center">
            <template #default="{ row }">
              <el-tag :type="row.userRole === 'admin' ? 'danger' : 'primary'" size="small">
                {{ row.userRole === 'admin' ? '管理员' : '普通用户' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="userProfile" label="简介" min-width="200" show-overflow-tooltip />
          <el-table-column label="创建时间" width="180">
            <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="140" align="center" fixed="right">
            <template #default="{ row }">
              <el-button size="small" link type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
              <el-button size="small" link type="danger" :icon="Delete" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="pageNum"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50]"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="loadList"
          />
        </div>
      </el-card>

      <!-- 新增/编辑对话框 -->
      <el-dialog
        v-model="dialogVisible"
        :title="isEdit ? '编辑用户' : '新增用户'"
        width="560px"
        @closed="resetForm"
      >
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="90px"
        >
          <el-form-item label="昵称" prop="userName">
            <el-input v-model="form.userName" placeholder="请输入昵称" />
          </el-form-item>
          <el-form-item label="账号" prop="userAccount">
            <el-input
              v-model="form.userAccount"
              placeholder="请输入账号"
              :disabled="isEdit"
            />
          </el-form-item>
          <el-form-item label="头像URL">
            <el-input v-model="form.userAvatar" placeholder="请输入头像地址" />
          </el-form-item>
          <el-form-item label="简介">
            <el-input
              v-model="form.userProfile"
              type="textarea"
              :rows="3"
              placeholder="请输入简介"
            />
          </el-form-item>
          <el-form-item label="角色" prop="userRole">
            <el-select v-model="form.userRole" placeholder="请选择角色" style="width: 100%">
              <el-option label="管理员" value="admin" />
              <el-option label="普通用户" value="user" />
            </el-select>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Search, Refresh, Edit, Delete } from '@element-plus/icons-vue'
import { userApi } from '@/api'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const isAdmin = userStore.isAdmin

interface UserRow {
  id: string
  userAccount: string
  userName?: string
  userAvatar?: string
  userProfile?: string
  userRole?: string
  createTime?: string
}

const loading = ref(false)
const tableData = ref<UserRow[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)

const searchForm = reactive({
  userName: '',
  userAccount: '',
  userRole: ''
})

const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  id: '' as string,
  userName: '',
  userAccount: '',
  userAvatar: '',
  userProfile: '',
  userRole: 'user'
})

const rules: FormRules = {
  userName: [{ required: true, message: '请输入昵称', trigger: 'blur' }],
  userAccount: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  userRole: [{ required: true, message: '请选择角色', trigger: 'change' }]
}

async function loadList() {
  loading.value = true
  try {
    const res = await userApi.listPage({
      pageNum: pageNum.value,
      pageSize: pageSize.value,
      userName: searchForm.userName || undefined,
      userAccount: searchForm.userAccount || undefined,
      userRole: searchForm.userRole || undefined
    })
    const data = res.data || ({} as any)
    tableData.value = data.records || []
    // total 可能是字符串（后端 Long 序列化为 String）
    total.value = Number(data.total) || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pageNum.value = 1
  loadList()
}

function handleReset() {
  searchForm.userName = ''
  searchForm.userAccount = ''
  searchForm.userRole = ''
  pageNum.value = 1
  loadList()
}

function handleSizeChange(size: number) {
  pageSize.value = size
  pageNum.value = 1
  loadList()
}

function openAdd() {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: UserRow) {
  isEdit.value = true
  resetForm()
  form.id = row.id
  form.userName = row.userName || ''
  form.userAccount = row.userAccount || ''
  form.userAvatar = row.userAvatar || ''
  form.userProfile = row.userProfile || ''
  form.userRole = row.userRole || 'user'
  dialogVisible.value = true
}

function resetForm() {
  form.id = ''
  form.userName = ''
  form.userAccount = ''
  form.userAvatar = ''
  form.userProfile = ''
  form.userRole = 'user'
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
    if (isEdit.value) {
      await userApi.update({
        id: form.id,
        userName: form.userName,
        userAvatar: form.userAvatar,
        userProfile: form.userProfile,
        userRole: form.userRole
      })
      ElMessage.success('编辑成功')
    } else {
      await userApi.add({
        userName: form.userName,
        userAccount: form.userAccount,
        userAvatar: form.userAvatar,
        userProfile: form.userProfile,
        userRole: form.userRole
      })
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    loadList()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: UserRow) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.userName || row.userAccount}」？`,
      '提示',
      { type: 'warning' }
    )
    await userApi.delete(row.id)
    ElMessage.success('删除成功')
    // 删除后若当前页无数据，回到上一页
    if (tableData.value.length === 1 && pageNum.value > 1) {
      pageNum.value -= 1
    }
    loadList()
  } catch {
    // 用户取消，不做处理
  }
}

function formatTime(t?: string) {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

onMounted(() => {
  if (isAdmin) {
    loadList()
  }
})
</script>

<style scoped>
.user-manage-page {
  padding: 20px;
}
.search-card {
  margin-bottom: 16px;
}
.search-form {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
}
.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
:deep(.el-table__row:hover > td) {
  background-color: #f5f7fa !important;
}
</style>
